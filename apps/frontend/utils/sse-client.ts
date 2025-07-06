/**
 * SSE Client for handling Server-Sent Events with POST support.
 */
import { EventSourcePolyfill } from 'event-source-polyfill';

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
  private eventSource: EventSourcePolyfill | null = null;
  private baseUrl: string;

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

    // Create new EventSource with POST support via polyfill
    this.eventSource = new EventSourcePolyfill(
      url,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(request),
        withCredentials: true,
      } as any // cast to allow non-standard props like method
    );

    // Set up event handlers
    this.setupEventHandlers(handlers);

    // Handle connection errors
    this.eventSource.onerror = (error: any) => {
      console.error('[SSE] Connection error:', error);
      console.error('[SSE] ReadyState:', this.eventSource?.readyState);
      if (handlers.onError) {
        handlers.onError({
          error: 'Connection lost',
          code: 'SSE_CONNECTION_ERROR',
          recoverable: true
        });
      }
      // EventSource will automatically reconnect
    };

    // Handle connection open
    this.eventSource.onopen = () => {
      console.log('[SSE] Connection opened successfully');
      console.log('[SSE] URL:', url);
      console.log('[SSE] ReadyState:', this.eventSource?.readyState);
    };
  }

  private setupEventHandlers(handlers: StreamHandlers): void {
    if (!this.eventSource) return;

    console.log('[SSE] Setting up event handlers');

    // Reasoning events
    if (handlers.onReasoning) {
      this.eventSource.addEventListener('reasoning', (e: any) => {
        try {
          console.log('[SSE] Received reasoning event:', e.data);
          const data = JSON.parse(e.data);
          handlers.onReasoning!(data);
        } catch (err) {
          console.error('[SSE] Error parsing reasoning event:', err);
        }
      });
    }

    // Tool call events
    if (handlers.onToolCall) {
      this.eventSource.addEventListener('tool_call', (e: any) => {
        try {
          console.log('[SSE] Received tool_call event:', e.data);
          const data = JSON.parse(e.data);
          handlers.onToolCall!(data);
        } catch (err) {
          console.error('[SSE] Error parsing tool_call event:', err);
        }
      });
    }

    // Tool result events
    if (handlers.onToolResult) {
      this.eventSource.addEventListener('tool_result', (e: any) => {
        try {
          console.log('[SSE] Received tool_result event:', e.data);
          const data = JSON.parse(e.data);
          handlers.onToolResult!(data);
        } catch (err) {
          console.error('[SSE] Error parsing tool_result event:', err);
        }
      });
    }

    // Content events
    if (handlers.onContent) {
      this.eventSource.addEventListener('content', (e: any) => {
        try {
          console.log('[SSE] Received content event:', e.data);
          const data = JSON.parse(e.data);
          handlers.onContent!(data);
        } catch (err) {
          console.error('[SSE] Error parsing content event:', err);
        }
      });
    }

    // Status events
    if (handlers.onStatus) {
      this.eventSource.addEventListener('status', (e: any) => {
        try {
          const data = JSON.parse(e.data);
          handlers.onStatus!(data);
        } catch (err) {
          console.error('Error parsing status event:', err);
        }
      });
    }

    // Error events
    if (handlers.onError) {
      this.eventSource.addEventListener('error', (e: any) => {
        try {
          const data = JSON.parse(e.data);
          handlers.onError!(data);
        } catch (err) {
          console.error('Error parsing error event:', err);
        }
      });
    }

    // Done events
    if (handlers.onDone) {
      this.eventSource.addEventListener('done', (e: any) => {
        try {
          console.log('[SSE] Received done event:', e.data);
          const data = e.data ? JSON.parse(e.data) : {};
          handlers.onDone!(data);
        } catch (err) {
          console.error('[SSE] Error handling done event:', err);
        }
      });
    }

    // Heartbeat events
    if (handlers.onHeartbeat) {
      this.eventSource.addEventListener('heartbeat', (e: any) => {
        try {
          console.log('[SSE] Received heartbeat event');
          handlers.onHeartbeat!();
        } catch (err) {
          console.error('[SSE] Error handling heartbeat event:', err);
        }
      });
    }

    // Update events for workbook modifications
    if (handlers.onUpdate) {
      this.eventSource.addEventListener('update', (e: any) => {
        try {
          console.log('[SSE] Received update event:', e.data);
          const data = JSON.parse(e.data);
          handlers.onUpdate!(data);
        } catch (err) {
          console.error('[SSE] Error parsing update event:', err);
        }
      });
    }

    // Default message handler for unknown events
    this.eventSource.addEventListener('message', (e: any) => {
      try {
        console.log('[SSE] Received unknown message event:', e);
        const data = JSON.parse(e.data);
        console.log('[SSE] Unknown event data:', data);
      } catch (err) {
        console.error('[SSE] Error parsing unknown event:', err);
      }
    });
  }

  close(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  abort(): void {
    this.close();
  }

  isConnected(): boolean {
    return this.eventSource !== null && 
           this.eventSource.readyState === EventSourcePolyfill.OPEN;
  }
} 