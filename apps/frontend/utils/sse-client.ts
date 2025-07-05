/**
 * SSE Client for handling Server-Sent Events with POST support.
 */
import { EventSourcePolyfill } from 'event-source-polyfill';

export interface StreamEvent {
  type: 'reasoning' | 'tool_call' | 'tool_result' | 'content' | 'error' | 'status' | 'done' | 'heartbeat';
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
  onDone?: () => void;
  onHeartbeat?: () => void;
};

export class SSEClient {
  private eventSource: EventSourcePolyfill | null = null;
  private baseUrl: string;

  constructor(baseUrl?: string) {
    const envBase =
      process.env.NEXT_PUBLIC_BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      process.env.API_URL;

    const resolved = baseUrl || envBase || 'http://localhost:8000';
    // Remove trailing slash to avoid '//'
    this.baseUrl = resolved.replace(/\/$/, '');
  }

  async streamChat(
    request: ChatRequest,
    handlers: StreamHandlers
  ): Promise<void> {
    // Determine endpoint based on mode
    const endpoint = request.mode === 'analyst' 
      ? '/analyst/stream' 
      : '/ask/stream';
    
    const url = `${this.baseUrl}${endpoint}`;

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
      console.error('SSE Error:', error);
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
      console.log('SSE connection opened');
    };
  }

  private setupEventHandlers(handlers: StreamHandlers): void {
    if (!this.eventSource) return;

    // Reasoning events
    if (handlers.onReasoning) {
      this.eventSource.addEventListener('reasoning', (e: any) => {
        try {
          const data = JSON.parse(e.data);
          handlers.onReasoning!(data);
        } catch (err) {
          console.error('Error parsing reasoning event:', err);
        }
      });
    }

    // Tool call events
    if (handlers.onToolCall) {
      this.eventSource.addEventListener('tool_call', (e: any) => {
        try {
          const data = JSON.parse(e.data);
          handlers.onToolCall!(data);
        } catch (err) {
          console.error('Error parsing tool_call event:', err);
        }
      });
    }

    // Tool result events
    if (handlers.onToolResult) {
      this.eventSource.addEventListener('tool_result', (e: any) => {
        try {
          const data = JSON.parse(e.data);
          handlers.onToolResult!(data);
        } catch (err) {
          console.error('Error parsing tool_result event:', err);
        }
      });
    }

    // Content events
    if (handlers.onContent) {
      this.eventSource.addEventListener('content', (e: any) => {
        try {
          const data = JSON.parse(e.data);
          handlers.onContent!(data);
        } catch (err) {
          console.error('Error parsing content event:', err);
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
      this.eventSource.addEventListener('done', () => {
        handlers.onDone!();
        this.close();
      });
    }

    // Heartbeat events
    if (handlers.onHeartbeat) {
      this.eventSource.addEventListener('heartbeat', () => {
        handlers.onHeartbeat!();
      });
    }
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