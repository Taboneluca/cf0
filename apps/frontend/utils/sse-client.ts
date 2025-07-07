/**
 * SSE Client for handling Server-Sent Events with POST support using fetch streaming.
 */

export interface StreamEvent {
  type: 'reasoning' | 'tool_call' | 'tool_result' | 'content' | 'error' | 'status' | 'done' | 'heartbeat' | 'update';
  data: any;
  id?: string;
  timestamp?: number;
}

export interface ChatRequest {
  message: string;
  wid: string;
  sid: string;
  model: string;
  mode?: 'ask' | 'analyst';
  contexts?: any[];
}

export type StreamHandlers = {
  onReasoning?: (data: any) => void;
  onToolCall?: (data: any) => void;
  onToolResult?: (data: any) => void;
  onContent?: (data: any) => void;
  onError?: (data: any) => void;
  onStatus?: (data: any) => void;
  onDone?: (data: any) => void;
  onHeartbeat?: () => void;
  onUpdate?: (data: any) => void;
};

export class SSEClient {
  private abortController: AbortController | null = null;
  private baseUrl: string;
  private currentStream: ReadableStreamDefaultReader<Uint8Array> | null = null;
  private isClosing: boolean = false;

  constructor(baseUrl?: string) {
    // In the browser, always use the relative proxy endpoint
    // This ensures we go through Next.js proxy which handles auth and CORS
    if (typeof window !== 'undefined') {
      this.baseUrl = '';  // Use relative URLs for client-side
    } else {
      // Server-side can use backend URL directly if needed
      const envBase =
        process.env.NEXT_PUBLIC_BACKEND_URL ||
        process.env.NEXT_PUBLIC_API_URL ||
        process.env.API_URL;
      this.baseUrl = baseUrl || envBase || 'http://localhost:8000';
    }
  }

  async streamChat(
    request: ChatRequest,
    handlers: StreamHandlers
  ): Promise<void> {
    // Check if we should use direct backend connection
    const useDirectConnection = process.env.NEXT_PUBLIC_DIRECT_BACKEND_URL && 
                               typeof window !== 'undefined';
    
    let url: string;
    if (useDirectConnection) {
      // Direct connection to backend, bypassing Next.js proxy
      const backendUrl = process.env.NEXT_PUBLIC_DIRECT_BACKEND_URL;
      const mode = request.mode || 'ask';
      url = `${backendUrl}/${mode}/stream`;
      console.log('[SSE] Using direct backend connection:', url);
    } else {
      // Use Next.js proxy endpoint (default)
      url = '/api/langserve/chat';
      console.log('[SSE] Using Next.js proxy endpoint');
    }

    // Close any existing connection
    this.close();

    // Reset closing flag
    this.isClosing = false;

    // Create new abort controller for this stream
    this.abortController = new AbortController();

    // Log the request details for debugging
    console.log('[SSE] Starting stream with fetch:', {
      url,
      method: 'POST',
      body: request,
      direct: useDirectConnection
    });

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(request),
        credentials: useDirectConnection ? 'omit' : 'include', // Omit credentials for CORS
        signal: this.abortController.signal,
      });

      console.log('[SSE] Response received:', {
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries()),
        ok: response.ok,
        bodyUsed: response.bodyUsed,
        hasBody: !!response.body
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      console.log('[SSE] Stream connected successfully');
      
      // Process the stream
      await this.processStream(response.body, handlers);
      
    } catch (error: any) {
      // Check if this was an intentional abort
      if (error.name === 'AbortError' || this.isClosing) {
        console.log('[SSE] Stream closed intentionally');
        return;
      }
      
      console.error('[SSE] Stream error:', error);
      if (handlers.onError) {
        handlers.onError({
          error: error.message || 'Stream connection failed',
          code: 'STREAM_ERROR',
          recoverable: true
        });
      }
    }
  }

  private async processStream(
    body: ReadableStream<Uint8Array>,
    handlers: StreamHandlers
  ): Promise<void> {
    const reader = body.getReader();
    this.currentStream = reader;
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        // Check if we're closing
        if (this.isClosing) {
          console.log('[SSE] Stream processing stopped due to close request');
          break;
        }

        const { done, value } = await reader.read();
        
        if (done) {
          console.log('[SSE] Stream completed naturally');
          if (handlers.onDone && !this.isClosing) {
            handlers.onDone({ status: 'completed' });
          }
          break;
        }

        // Decode the chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE events from the buffer
        const events = this.extractSSEEvents(buffer);
        buffer = events.remainder;

        for (const event of events.events) {
          if (!this.isClosing) {
            this.handleSSEEvent(event, handlers);
          }
        }
      }
    } catch (error: any) {
      // Only log/throw if not intentionally closing
      if (!this.isClosing && error.name !== 'AbortError') {
        console.error('[SSE] Error reading stream:', error);
        throw error;
      }
    } finally {
      // Ensure reader is released
      try {
        reader.releaseLock();
      } catch (e) {
        // Reader might already be released
      }
      this.currentStream = null;
    }
  }

  private extractSSEEvents(buffer: string): { events: Array<{ event?: string; data?: string; id?: string }>, remainder: string } {
    const events = [];
    const lines = buffer.split('\n');
    let currentEvent: any = {};
    let i = 0;

    for (; i < lines.length; i++) {
      const line = lines[i].trim();

      if (line === '') {
        // Empty line signals end of event
        if (currentEvent.data !== undefined) {
          events.push(currentEvent);
        }
        currentEvent = {};
      } else if (line.startsWith('event:')) {
        currentEvent.event = line.substring(6).trim();
      } else if (line.startsWith('data:')) {
        const data = line.substring(5).trim();
        if (currentEvent.data === undefined) {
          currentEvent.data = data;
        } else {
          currentEvent.data += '\n' + data;
        }
      } else if (line.startsWith('id:')) {
        currentEvent.id = line.substring(3).trim();
      } else if (line.startsWith(':')) {
        // Comment, ignore
      } else {
        // If we hit an incomplete line, put it back in the buffer
        break;
      }
    }

    // Reconstruct the remainder
    const remainder = lines.slice(i).join('\n');

    return { events, remainder };
  }

  private handleSSEEvent(
    event: { event?: string; data?: string; id?: string },
    handlers: StreamHandlers
  ): void {
    const eventType = event.event || 'message';
    const data = event.data;

    if (!data) return;

    console.log(`[SSE] Received ${eventType} event:`, data);

    try {
      const parsedData = JSON.parse(data);

      switch (eventType) {
        case 'reasoning':
          if (handlers.onReasoning) handlers.onReasoning(parsedData);
          break;
        case 'tool_call':
          if (handlers.onToolCall) handlers.onToolCall(parsedData);
          break;
        case 'tool_result':
          if (handlers.onToolResult) handlers.onToolResult(parsedData);
          break;
        case 'content':
          if (handlers.onContent) handlers.onContent(parsedData);
          break;
        case 'status':
          if (handlers.onStatus) handlers.onStatus(parsedData);
          break;
        case 'error':
          if (handlers.onError) handlers.onError(parsedData);
          break;
        case 'done':
          if (handlers.onDone) handlers.onDone(parsedData);
          break;
        case 'heartbeat':
          console.log('[SSE] Received heartbeat');
          if (handlers.onHeartbeat) handlers.onHeartbeat();
          break;
        case 'update':
          if (handlers.onUpdate) handlers.onUpdate(parsedData);
          break;
        default:
          console.log('[SSE] Unknown event type:', eventType, parsedData);
      }
    } catch (err) {
      console.error(`[SSE] Error parsing ${eventType} event:`, err, data);
    }
  }

  close(): void {
    this.isClosing = true;
    
    if (this.abortController && !this.abortController.signal.aborted) {
      this.abortController.abort();
    }
    this.abortController = null;
    
    if (this.currentStream) {
      try {
        this.currentStream.cancel();
      } catch (e) {
        // Stream might already be canceled
      }
      this.currentStream = null;
    }
  }

  abort(): void {
    this.close();
  }

  isConnected(): boolean {
    return this.abortController !== null && !this.abortController.signal.aborted && !this.isClosing;
  }
} 