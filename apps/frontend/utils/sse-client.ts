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
    // Always use the Next.js proxy endpoint which handles backend routing
    const url = '/api/langserve/chat';

    // Close any existing connection
    this.close();

    // Create new abort controller for this stream
    this.abortController = new AbortController();

    // Log the request details for debugging
    console.log('[SSE] Starting stream with fetch:', {
      url,
      method: 'POST',
      body: request
    });

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(request),
        credentials: 'include',
        signal: this.abortController.signal,
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
      if (error.name === 'AbortError') {
        console.log('[SSE] Stream aborted');
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
        const { done, value } = await reader.read();
        
        if (done) {
          console.log('[SSE] Stream completed');
          if (handlers.onDone) {
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
          this.handleSSEEvent(event, handlers);
        }
      }
    } catch (error) {
      console.error('[SSE] Error reading stream:', error);
      throw error;
    } finally {
      reader.releaseLock();
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
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    if (this.currentStream) {
      this.currentStream.releaseLock();
      this.currentStream = null;
    }
  }

  abort(): void {
    this.close();
  }

  isConnected(): boolean {
    return this.abortController !== null && !this.abortController.signal.aborted;
  }
} 