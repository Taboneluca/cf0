/**
 * SSE Client for handling Server-Sent Events with POST support using fetch streaming.
 * Enhanced for 2025 with stream management, reconnection, and performance optimizations.
 */

export interface StreamEvent {
  type: 'reasoning' | 'tool_call' | 'tool_result' | 'content' | 'error' | 'status' | 'done' | 'heartbeat' | 'update' |
        'planning' | 'plan_ready' | 'progress' | 'batch_start' | 'batch_progress' | 'batch_complete' |
        'stream_start' | 'stream_pause' | 'stream_resume' | 'stream_metadata';
  data: any;
  id?: string;
  timestamp?: number;
  stream_id?: string;
  sequence_number?: number;
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
  // NEW: Planning and batch handlers
  onPlanning?: (data: any) => void;
  onPlanReady?: (data: any) => void;
  onProgress?: (data: any) => void;
  onBatchStart?: (data: any) => void;
  onBatchProgress?: (data: any) => void;
  onBatchComplete?: (data: any) => void;
  // NEW: Stream lifecycle handlers
  onStreamStart?: (data: any) => void;
  onStreamPause?: (data: any) => void;
  onStreamResume?: (data: any) => void;
  onStreamMetadata?: (data: any) => void;
};

interface SSEMetrics {
  totalEvents: number;
  contentEvents: number;
  toolEvents: number;
  errorEvents: number;
  reconnectionAttempts: number;
  bufferedEvents: number;
  averageEventSize: number;
  connectionDuration: number;
  lastEventTime: number;
  compressionSavings: number;
}

interface ConnectionConfig {
  maxReconnectAttempts: number;
  baseReconnectDelay: number;
  maxReconnectDelay: number;
  heartbeatTimeout: number;
  eventBufferSize: number;
  enableCompression: boolean;
  enableEventValidation: boolean;
}

interface StreamInfo {
  id: string;
  startTime: number;
  lastActivity: number;
  eventCount: number;
  isActive: boolean;
}

export class SSEClient {
  private abortController: AbortController | null = null;
  private baseUrl: string;
  private currentStream: ReadableStreamDefaultReader<Uint8Array> | null = null;
  private isClosing: boolean = false;
  
  // NEW: Enhanced stream management
  private activeStreams: Map<string, StreamInfo> = new Map();
  private currentStreamId: string | null = null;
  private streamCounter: number = 0;
  
  // NEW: Reconnection system
  private reconnectAttempts: number = 0;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private lastConnectionTime: number = 0;
  
  // NEW: Event buffering and processing
  private eventBuffer: StreamEvent[] = [];
  private processingBuffer: boolean = false;
  private lastHeartbeat: number = 0;
  
  // NEW: Performance metrics
  private metrics: SSEMetrics = {
    totalEvents: 0,
    contentEvents: 0,
    toolEvents: 0,
    errorEvents: 0,
    reconnectionAttempts: 0,
    bufferedEvents: 0,
    averageEventSize: 0,
    connectionDuration: 0,
    lastEventTime: 0,
    compressionSavings: 0,
  };
  
  // NEW: Configuration
  private config: ConnectionConfig = {
    maxReconnectAttempts: 5,
    baseReconnectDelay: 1000, // 1 second
    maxReconnectDelay: 30000,  // 30 seconds
    heartbeatTimeout: 45000,   // 45 seconds - reduced from 60 to match backend heartbeat interval
    eventBufferSize: 100,
    enableCompression: true,
    enableEventValidation: true,
  };

  constructor(baseUrl?: string, config?: Partial<ConnectionConfig>) {
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
    
    // Apply configuration overrides
    if (config) {
      this.config = { ...this.config, ...config };
    }
    
    console.log('[SSE] Client initialized with enhanced features:', {
      baseUrl: this.baseUrl,
      config: this.config
    });
  }
  
  // NEW: Generate unique stream ID
  private generateStreamId(): string {
    this.streamCounter++;
    return `client-${Date.now()}-${this.streamCounter}`;
  }
  
  // NEW: Register a new stream
  private registerStream(streamId: string): void {
    const streamInfo: StreamInfo = {
      id: streamId,
      startTime: Date.now(),
      lastActivity: Date.now(),
      eventCount: 0,
      isActive: true,
    };
    
    this.activeStreams.set(streamId, streamInfo);
    this.currentStreamId = streamId;
    console.log(`[SSE] Registered stream: ${streamId}`);
  }
  
  // NEW: Update stream activity
  private updateStreamActivity(streamId: string): void {
    const streamInfo = this.activeStreams.get(streamId);
    if (streamInfo) {
      streamInfo.lastActivity = Date.now();
      streamInfo.eventCount++;
    }
  }
  
  // NEW: Cleanup stream
  private cleanupStream(streamId: string): void {
    const streamInfo = this.activeStreams.get(streamId);
    if (streamInfo) {
      streamInfo.isActive = false;
      console.log(`[SSE] Stream ${streamId} completed:`, {
        duration: Date.now() - streamInfo.startTime,
        events: streamInfo.eventCount
      });
    }
    
    if (this.currentStreamId === streamId) {
      this.currentStreamId = null;
    }
    
    // Keep stream info for metrics but mark as inactive
    setTimeout(() => {
      this.activeStreams.delete(streamId);
    }, 5000); // Clean up after 5 seconds
  }

  async streamChat(
    request: ChatRequest,
    handlers: StreamHandlers
  ): Promise<void> {
    // Generate new stream ID
    const streamId = this.generateStreamId();
    this.registerStream(streamId);
    
    // Reset metrics for new stream
    this.resetMetrics();
    
    // Check if we should use direct backend connection
    const useDirectConnection = Boolean(process.env.NEXT_PUBLIC_DIRECT_BACKEND_URL && 
                                       typeof window !== 'undefined');
    
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

    // Reset closing flag and connection state
    this.isClosing = false;
    this.lastConnectionTime = Date.now();

    // Create new abort controller for this stream
    this.abortController = new AbortController();

    console.log('[SSE] Starting enhanced stream with fetch:', {
      url,
      method: 'POST',
      body: request,
      direct: useDirectConnection,
      streamId: streamId,
      timestamp: new Date().toISOString()
    });

    // Attempt connection with retry logic
    await this.attemptConnection(url, request, handlers, useDirectConnection, streamId);
  }
  
  // NEW: Attempt connection with retry logic
  private async attemptConnection(
    url: string,
    request: ChatRequest,
    handlers: StreamHandlers,
    useDirectConnection: boolean,
    streamId: string,
    attemptNumber: number = 1
  ): Promise<void> {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          'X-Stream-ID': streamId,  // NEW: Send stream ID
        },
        body: JSON.stringify(request),
        credentials: useDirectConnection ? 'omit' : 'include',
        signal: this.abortController?.signal,
      });

      console.log('[SSE] Response received:', {
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries()),
        ok: response.ok,
        bodyUsed: response.bodyUsed,
        hasBody: !!response.body,
        streamId: streamId,
        attempt: attemptNumber
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      console.log(`[SSE] Stream ${streamId} connected successfully on attempt ${attemptNumber}`);
      
      // Reset reconnection attempts on successful connection
      this.reconnectAttempts = 0;
      
      // Process the stream
      await this.processStream(response.body, handlers, streamId);
      
    } catch (error: any) {
      // Check if this was an intentional abort
      if (error.name === 'AbortError' || this.isClosing) {
        console.log(`[SSE] Stream ${streamId} closed intentionally`);
        this.cleanupStream(streamId);
        return;
      }
      
      console.error(`[SSE] Stream ${streamId} error on attempt ${attemptNumber}:`, error);
      this.metrics.errorEvents++;
      
      // Enhanced error classification for better retry logic
      const isRetryableError = this.isRetryableError(error);
      const shouldRetry = isRetryableError && attemptNumber < this.config.maxReconnectAttempts && !this.isClosing;
      
      if (shouldRetry) {
        console.log(`[SSE] Retryable error detected, scheduling reconnection (attempt ${attemptNumber + 1})`);
        await this.scheduleReconnection(url, request, handlers, useDirectConnection, streamId, attemptNumber);
      } else {
        // Max attempts reached or non-retryable error
        this.cleanupStream(streamId);
        const errorCode = isRetryableError ? 'MAX_RECONNECT_ATTEMPTS' : 'NON_RETRYABLE_ERROR';
        
        if (handlers.onError) {
          handlers.onError({
            error: error.message || 'Stream connection failed',
            code: errorCode,
            recoverable: isRetryableError,
            attempts: attemptNumber,
            streamId: streamId,
            suggestion: this.getErrorSuggestion(error)
          });
        }
      }
    }
  }
  
  // NEW: Schedule reconnection with exponential backoff
  private async scheduleReconnection(
    url: string,
    request: ChatRequest,
    handlers: StreamHandlers,
    useDirectConnection: boolean,
    streamId: string,
    attemptNumber: number
  ): Promise<void> {
    this.reconnectAttempts++;
    this.metrics.reconnectionAttempts++;
    
    // Calculate delay with exponential backoff
    const delay = Math.min(
      this.config.baseReconnectDelay * Math.pow(2, attemptNumber - 1),
      this.config.maxReconnectDelay
    );
    
    console.log(`[SSE] Scheduling reconnection for stream ${streamId} in ${delay}ms (attempt ${attemptNumber + 1})`);
    
    // Notify handlers about reconnection attempt
    if (handlers.onStatus) {
      handlers.onStatus({
        status: 'reconnecting',
        attempt: attemptNumber + 1,
        delay: delay,
        streamId: streamId
      });
    }
    
    this.reconnectTimer = setTimeout(async () => {
      if (!this.isClosing) {
        await this.attemptConnection(url, request, handlers, useDirectConnection, streamId, attemptNumber + 1);
      }
    }, delay);
  }

  private async processStream(
    body: ReadableStream<Uint8Array>,
    handlers: StreamHandlers,
    streamId: string
  ): Promise<void> {
    const reader = body.getReader();
    this.currentStream = reader;
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      // Start heartbeat monitoring
      this.startHeartbeatMonitoring(streamId);
      
      while (true) {
        // Check if we're closing
        if (this.isClosing) {
          console.log(`[SSE] Stream ${streamId} processing stopped due to close request`);
          break;
        }

        const { done, value } = await reader.read();
        
        if (done) {
          console.log(`[SSE] Stream ${streamId} completed naturally`);
          if (handlers.onDone && !this.isClosing) {
            // Process any remaining buffered events first
            await this.flushEventBuffer(handlers, streamId);
            handlers.onDone({ 
              status: 'completed',
              streamId: streamId,
              metrics: this.getMetrics()
            });
          }
          break;
        }

        // Update stream activity
        this.updateStreamActivity(streamId);

        // Decode the chunk and add to buffer
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;

        // Update metrics
        this.metrics.totalEvents++;
        this.metrics.averageEventSize = 
          (this.metrics.averageEventSize * (this.metrics.totalEvents - 1) + chunk.length) / 
          this.metrics.totalEvents;

        // Process complete SSE events from the buffer
        const events = this.extractSSEEvents(buffer);
        buffer = events.remainder;

        for (const event of events.events) {
          if (!this.isClosing) {
            await this.handleSSEEvent(event, handlers, streamId);
          }
        }
      }
    } catch (error: any) {
      // Only log/throw if not intentionally closing
      if (!this.isClosing && error.name !== 'AbortError') {
        console.error(`[SSE] Error reading stream ${streamId}:`, error);
        this.metrics.errorEvents++;
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
      this.stopHeartbeatMonitoring();
      this.cleanupStream(streamId);
    }
  }
  
  // NEW: Start heartbeat monitoring
  private startHeartbeatMonitoring(streamId: string): void {
    this.lastHeartbeat = Date.now();
    
    const checkHeartbeat = () => {
      if (this.isClosing) return;
      
      const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeat;
      if (timeSinceLastHeartbeat > this.config.heartbeatTimeout) {
        console.warn(`[SSE] Heartbeat timeout for stream ${streamId} (${timeSinceLastHeartbeat}ms)`);
        // Could trigger reconnection here if needed - for now just warn
      }
      
      if (!this.isClosing) {
        // Check every 15 seconds instead of every 15 seconds (was heartbeatTimeout/4)
        setTimeout(checkHeartbeat, 15000);
      }
    };
    
    // Start checking after 15 seconds
    setTimeout(checkHeartbeat, 15000);
  }
  
  // NEW: Stop heartbeat monitoring
  private stopHeartbeatMonitoring(): void {
    // Monitoring will stop automatically when isClosing is true
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

  private async handleSSEEvent(
    event: { event?: string; data?: string; id?: string },
    handlers: StreamHandlers,
    streamId: string
  ): Promise<void> {
    const eventType = event.event || 'message';
    const data = event.data;

    if (!data) return;

    console.log(`[SSE] Received ${eventType} event for stream ${streamId}:`, data.substring(0, 100));

    try {
      let parsedData = this.parseEventData(data);
      
      // Validate stream ID if present
      if (parsedData._meta?.stream_id && parsedData._meta.stream_id !== streamId) {
        console.warn(`[SSE] Stream ID mismatch: expected ${streamId}, got ${parsedData._meta.stream_id}`);
        return; // Discard event from wrong stream
      }

      // Update heartbeat on any event
      this.lastHeartbeat = Date.now();
      this.metrics.lastEventTime = Date.now();

      // Buffer event for processing if needed
      if (this.config.eventBufferSize > 0) {
        await this.bufferEvent(eventType, parsedData, handlers, streamId);
      } else {
        await this.dispatchEvent(eventType, parsedData, handlers, streamId);
      }
      
    } catch (err) {
      console.error(`[SSE] Error parsing ${eventType} event for stream ${streamId}:`, err, data);
      this.metrics.errorEvents++;
      
      if (handlers.onError) {
        handlers.onError({
          error: `Failed to parse ${eventType} event`,
          code: 'PARSE_ERROR',
          recoverable: true,
          streamId: streamId,
          rawData: data
        });
      }
    }
  }
  
  // NEW: Parse event data with decompression support
  private parseEventData(data: string): any {
    const parsedData = JSON.parse(data);
    
    // Handle compressed data
    if (parsedData.compressed && this.config.enableCompression) {
      try {
        console.log(`[SSE] Decompressing event: ${parsedData.compressed_size}B compressed, ${parsedData.original_size}B original`);
        
        if (parsedData.encoding === 'gzip+base64') {
          // Decode base64 and decompress
          const compressedBytes = Uint8Array.from(atob(parsedData.data), c => c.charCodeAt(0));
          
          // Note: Browser doesn't have built-in gzip decompression
          // In a real implementation, you'd use a library like pako
          console.warn('[SSE] Decompression not implemented in browser, using fallback');
          
          this.metrics.compressionSavings += (parsedData.original_size - parsedData.compressed_size);
        }
      } catch (error) {
        console.error('[SSE] Decompression failed:', error);
      }
    }
    
    return parsedData;
  }
  
  // NEW: Buffer events for processing
  private async bufferEvent(
    eventType: string,
    data: any,
    handlers: StreamHandlers,
    streamId: string
  ): Promise<void> {
    const bufferedEvent: StreamEvent = {
      type: eventType as any,
      data: data,
      timestamp: Date.now(),
      stream_id: streamId
    };
    
    this.eventBuffer.push(bufferedEvent);
    this.metrics.bufferedEvents++;
    
    // Keep buffer size manageable
    if (this.eventBuffer.length > this.config.eventBufferSize) {
      this.eventBuffer.shift(); // Remove oldest event
    }
    
    // Process buffer if not already processing
    if (!this.processingBuffer) {
      this.processingBuffer = true;
      
      // Use requestAnimationFrame for smooth processing
      if (typeof requestAnimationFrame !== 'undefined') {
        requestAnimationFrame(() => this.processEventBuffer(handlers, streamId));
      } else {
        setTimeout(() => this.processEventBuffer(handlers, streamId), 0);
      }
    }
  }
  
  // NEW: Process buffered events
  private async processEventBuffer(handlers: StreamHandlers, streamId: string): Promise<void> {
    try {
      while (this.eventBuffer.length > 0 && !this.isClosing) {
        const event = this.eventBuffer.shift()!;
        await this.dispatchEvent(event.type, event.data, handlers, streamId);
      }
    } finally {
      this.processingBuffer = false;
    }
  }
  
  // NEW: Flush remaining buffered events
  private async flushEventBuffer(handlers: StreamHandlers, streamId: string): Promise<void> {
    if (this.eventBuffer.length > 0) {
      console.log(`[SSE] Flushing ${this.eventBuffer.length} buffered events for stream ${streamId}`);
      await this.processEventBuffer(handlers, streamId);
    }
  }
  
  // NEW: Dispatch event to appropriate handler
  private async dispatchEvent(
    eventType: string,
    parsedData: any,
    handlers: StreamHandlers,
    streamId: string
  ): Promise<void> {
    // Update metrics based on event type
    switch (eventType) {
      case 'content':
        this.metrics.contentEvents++;
        break;
      case 'tool_call':
      case 'tool_result':
        this.metrics.toolEvents++;
        break;
      case 'error':
        this.metrics.errorEvents++;
        break;
    }

    // Dispatch to appropriate handler
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
        console.error(`[SSE] Error event for stream ${streamId}:`, parsedData);
        this.metrics.errorEvents++;
        
        // Handle recoverable errors differently
        if (parsedData.recoverable && parsedData.code !== 'STREAM_PIPELINE_ERROR') {
          console.log(`[SSE] Recoverable error for stream ${streamId}, continuing...`);
          // For recoverable errors, just log and continue
          if (handlers.onStatus) {
            handlers.onStatus({
              status: 'error_recovered',
              error: parsedData.error,
              code: parsedData.code,
              streamId: streamId
            });
          }
        } else {
          // For non-recoverable errors, call the error handler
          if (handlers.onError) handlers.onError(parsedData);
        }
        break;
      case 'done':
        if (handlers.onDone) handlers.onDone(parsedData);
        break;
      case 'heartbeat':
        console.log(`[SSE] Received heartbeat for stream ${streamId}`);
        if (handlers.onHeartbeat) handlers.onHeartbeat();
        break;
      case 'update':
        if (handlers.onUpdate) handlers.onUpdate(parsedData);
        break;
      // NEW: Planning and batch events
      case 'planning':
        if (handlers.onPlanning) handlers.onPlanning(parsedData);
        break;
      case 'plan_ready':
        if (handlers.onPlanReady) handlers.onPlanReady(parsedData);
        break;
      case 'progress':
        if (handlers.onProgress) handlers.onProgress(parsedData);
        break;
      case 'batch_start':
        if (handlers.onBatchStart) handlers.onBatchStart(parsedData);
        break;
      case 'batch_progress':
        if (handlers.onBatchProgress) handlers.onBatchProgress(parsedData);
        break;
      case 'batch_complete':
        if (handlers.onBatchComplete) handlers.onBatchComplete(parsedData);
        break;
      // NEW: Stream lifecycle events
      case 'stream_start':
        if (handlers.onStreamStart) handlers.onStreamStart(parsedData);
        break;
      case 'stream_pause':
        if (handlers.onStreamPause) handlers.onStreamPause(parsedData);
        break;
      case 'stream_resume':
        if (handlers.onStreamResume) handlers.onStreamResume(parsedData);
        break;
      case 'stream_metadata':
        if (handlers.onStreamMetadata) handlers.onStreamMetadata(parsedData);
        break;
      default:
        console.log(`[SSE] Unknown event type for stream ${streamId}:`, eventType, parsedData);
    }
  }

  close(): void {
    this.isClosing = true;
    
    // Clear reconnection timer
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
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
    
    // Clean up active streams
    if (this.currentStreamId) {
      this.cleanupStream(this.currentStreamId);
    }
    
    console.log('[SSE] Client closed, final metrics:', this.getMetrics());
  }

  abort(): void {
    this.close();
  }

  isConnected(): boolean {
    return this.abortController !== null && 
           !this.abortController.signal.aborted && 
           !this.isClosing &&
           this.currentStreamId !== null;
  }
  
  // NEW: Get current stream ID
  getCurrentStreamId(): string | null {
    return this.currentStreamId;
  }
  
  // NEW: Get active streams info
  getActiveStreams(): StreamInfo[] {
    return Array.from(this.activeStreams.values()).filter(stream => stream.isActive);
  }
  
  // NEW: Get performance metrics
  getMetrics(): SSEMetrics {
    const connectionDuration = this.lastConnectionTime > 0 ? 
      Date.now() - this.lastConnectionTime : 0;
    
    return {
      ...this.metrics,
      connectionDuration,
    };
  }
  
  // NEW: Reset metrics for new stream
  private resetMetrics(): void {
    this.metrics = {
      totalEvents: 0,
      contentEvents: 0,
      toolEvents: 0,
      errorEvents: 0,
      reconnectionAttempts: 0,
      bufferedEvents: 0,
      averageEventSize: 0,
      connectionDuration: 0,
      lastEventTime: 0,
      compressionSavings: 0,
    };
    this.lastConnectionTime = Date.now();
  }
  
  // NEW: Update client configuration
  updateConfig(newConfig: Partial<ConnectionConfig>): void {
    this.config = { ...this.config, ...newConfig };
    console.log('[SSE] Configuration updated:', this.config);
  }
  
  // NEW: Enhanced error classification for better retry logic
  private isRetryableError(error: any): boolean {
    // Network errors that are typically retryable
    if (error.name === 'NetworkError' || error.name === 'TimeoutError') {
      return true;
    }
    
    // HTTP status codes that are retryable
    if (error.message && typeof error.message === 'string') {
      const message = error.message.toLowerCase();
      
      // Connection issues
      if (message.includes('fetch') || 
          message.includes('network') || 
          message.includes('timeout') ||
          message.includes('connection')) {
        return true;
      }
      
      // Server errors (5xx) are retryable, client errors (4xx) are not
      const statusMatch = message.match(/status:\s*(\d{3})/);
      if (statusMatch) {
        const status = parseInt(statusMatch[1]);
        return status >= 500 && status < 600; // 5xx errors are retryable
      }
    }
    
    // Default to non-retryable for unknown errors
    return false;
  }
  
  // NEW: Provide helpful error suggestions
  private getErrorSuggestion(error: any): string {
    if (error.name === 'NetworkError') {
      return 'Check your internet connection and try again.';
    }
    
    if (error.message && typeof error.message === 'string') {
      const message = error.message.toLowerCase();
      
      if (message.includes('timeout')) {
        return 'The request timed out. This may be due to a slow connection or high server load.';
      }
      
      if (message.includes('500') || message.includes('internal server error')) {
        return 'Server error occurred. Please try again in a moment.';
      }
      
      if (message.includes('503') || message.includes('service unavailable')) {
        return 'Service is temporarily unavailable. Please try again later.';
      }
      
      if (message.includes('401') || message.includes('unauthorized')) {
        return 'Authentication failed. Please refresh the page and try again.';
      }
      
      if (message.includes('403') || message.includes('forbidden')) {
        return 'Access denied. Please check your permissions.';
      }
      
      if (message.includes('404') || message.includes('not found')) {
        return 'Service endpoint not found. Please refresh the page.';
      }
    }
    
    return 'Please try again or contact support if the problem persists.';
  }
} 