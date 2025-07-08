/**
 * React hook for handling chat streaming with SSE.
 * Enhanced for 2025 with React 19 optimizations and real-time rendering.
 */
import { useState, useCallback, useRef, useEffect, useTransition, useMemo } from 'react';
import { SSEClient, StreamEvent, ChatRequest } from '@/utils/sse-client';
import { useWorkbook } from '@/context/workbook-context';
import type { Message as MessageType } from '@/types/spreadsheet';
import { backendSheetToUI } from '@/utils/transform';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  reasoning?: string;
  toolCalls?: Array<{
    id: string;
    tool: string;
    arguments: any;
    result?: any;
  }>;
  status?: 'streaming' | 'complete' | 'error';
  streamId?: string;  // NEW: Track which stream this message belongs to
  stepNumber?: number;  // NEW: Track step number in stream
}

interface StreamingState {
  isStreaming: boolean;
  currentMessage: MessageType | null;
  accumulatedContent: string;
  accumulatedReasoning: string;
  toolCalls: Map<string, any>;
  error: string | null;
  activeStreamId: string | null;  // NEW: Track active stream
  contentBuffer: string;  // NEW: Micro-batching buffer
}

interface PendingUpdate {
  cell: string;
  old_value: any;
  new_value: any;
  kind: string;
}

interface UseChatStreamReturn {
  sendMessage: (message: string, contexts: string[], model: string) => void;
  cancelStream: () => void;
  isStreaming: boolean;
  pendingUpdates: PendingUpdate[];
  applyPendingUpdates: () => Promise<void>;
  rejectPendingUpdates: () => Promise<void>;
  streamingMetrics: StreamingMetrics;  // NEW: Performance metrics
}

interface StreamingMetrics {
  totalChunks: number;
  contentChunks: number;
  toolChunks: number;
  renderLatency: number;
  averageChunkSize: number;
  streamDuration: number;
  lastUpdateTime: number;
}

export function useChatStreamSSE(
  setMessages: React.Dispatch<React.SetStateAction<MessageType[]>>,
  mode: 'ask' | 'analyst'
): UseChatStreamReturn {
  const [state, setState] = useState<StreamingState>({
    isStreaming: false,
    currentMessage: null,
    accumulatedContent: '',
    accumulatedReasoning: '',
    toolCalls: new Map(),
    error: null,
    activeStreamId: null,
    contentBuffer: '',
  });
  
  const [pendingUpdates, setPendingUpdates] = useState<PendingUpdate[]>([]);
  const [wb, dispatch] = useWorkbook();
  const { wid, active } = wb;

  // React 19 transition for non-blocking updates
  const [isPending, startTransition] = useTransition();
  
  const clientRef = useRef<SSEClient | null>(null);
  const streamIdRef = useRef<number>(0);
  
  // NEW: Micro-batching system
  const batchingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const contentBufferRef = useRef<string>('');
  const lastRenderTimeRef = useRef<number>(0);
  const BATCH_INTERVAL_MS = 16; // One frame at 60fps
  
  // NEW: Performance metrics tracking
  const [streamingMetrics, setStreamingMetrics] = useState<StreamingMetrics>({
    totalChunks: 0,
    contentChunks: 0,
    toolChunks: 0,
    renderLatency: 0,
    averageChunkSize: 0,
    streamDuration: 0,
    lastUpdateTime: 0,
  });
  
  // NEW: Stream performance monitoring
  const streamStartTimeRef = useRef<number>(0);
  const chunkSizesRef = useRef<number[]>([]);
  
  // Track the current active stream ID in a ref so callbacks always have fresh value
  const activeStreamIdRef = useRef<string | null>(null);
  
  // Initialize SSE client
  useEffect(() => {
    clientRef.current = new SSEClient();
    return () => {
      clientRef.current?.close();
      if (batchingTimerRef.current) {
        clearTimeout(batchingTimerRef.current);
      }
    };
  }, []);

  // NEW: Optimized content update with proper micro-batching and React 19 transitions
  const appendContent = useCallback((delta: string, streamId?: string) => {
    const chunkStartTime = performance.now();
    
    // Discard updates from stale streams
    if (streamId && activeStreamIdRef.current && streamId !== activeStreamIdRef.current) {
      console.log('[useChatStreamSSE] Discarding update from stale stream:', streamId);
      return;
    }
    
    // Add to content buffer for batching
    contentBufferRef.current += delta;
    
    // Clear existing timer to batch rapid updates
    if (batchingTimerRef.current) {
      clearTimeout(batchingTimerRef.current);
    }
    
    // Track metrics for this chunk
    chunkSizesRef.current.push(delta.length);
    if (chunkSizesRef.current.length > 100) {
      chunkSizesRef.current = chunkSizesRef.current.slice(-100);
    }
    
    // Update performance metrics (but don't trigger re-render yet)
    setStreamingMetrics(prev => ({
      ...prev,
      contentChunks: prev.contentChunks + 1,
      totalChunks: prev.totalChunks + 1,
      renderLatency: (prev.renderLatency * prev.contentChunks + (performance.now() - chunkStartTime)) / (prev.contentChunks + 1),
      averageChunkSize: chunkSizesRef.current.reduce((a, b) => a + b, 0) / chunkSizesRef.current.length,
      lastUpdateTime: Date.now(),
    }));
    
    // Schedule batched update - shorter timeout for better responsiveness
    batchingTimerRef.current = setTimeout(() => {
      const bufferedContent = contentBufferRef.current;
      contentBufferRef.current = '';
      
      if (bufferedContent) {
        // Reduced logging for better performance
        if (bufferedContent.length > 10) { // Only log substantial updates
          console.log('[useChatStreamSSE] Batched content update:', `${bufferedContent.length} chars, sample: "${bufferedContent.slice(0, 30)}..."`);
        }
        
        // Use React 19's startTransition for non-blocking updates
        startTransition(() => {
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = {
                ...newMessages[lastIndex],
                content: (newMessages[lastIndex].content || '') + bufferedContent,
                timestamp: Date.now(),
                streamId: streamId,
              };
            }
            return newMessages;
          });
        });
      }
    }, BATCH_INTERVAL_MS);
    
    // Update accumulated content in state (for tracking)
    setState(prev => ({
      ...prev,
      accumulatedContent: prev.accumulatedContent + delta,
    }));
  }, [setMessages]);
  
  // NEW: Enhanced stream management with ID tracking
  const generateStreamId = useCallback(() => {
    const id = `stream-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    streamIdRef.current++;
    return id;
  }, []);
  
  // NEW: Stream cleanup helper
  const cleanupStream = useCallback((streamId: string) => {
    console.log('[useChatStreamSSE] Cleaning up stream:', streamId);
    
    // Clear any pending micro-batch
    if (batchingTimerRef.current) {
      clearTimeout(batchingTimerRef.current);
      batchingTimerRef.current = null;
    }
    
    // Flush any remaining content
    if (contentBufferRef.current) {
      const remaining = contentBufferRef.current;
      contentBufferRef.current = '';
      
      startTransition(() => {
        setMessages(prev => {
          const newMessages = [...prev];
          const lastIndex = newMessages.length - 1;
          if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
            newMessages[lastIndex] = {
              ...newMessages[lastIndex],
              content: (newMessages[lastIndex].content || '') + remaining,
              timestamp: Date.now(),
            };
          }
          return newMessages;
        });
      });
    }
    
    // Update final metrics
    const streamEndTime = performance.now();
    if (streamStartTimeRef.current > 0) {
      setStreamingMetrics(prev => ({
        ...prev,
        streamDuration: streamEndTime - streamStartTimeRef.current,
      }));
    }
    
    // Clear active stream ref if matches
    if (activeStreamIdRef.current === streamId) {
      activeStreamIdRef.current = null;
    }
  }, [setMessages]);

  const sendMessage = useCallback(async (message: string, contexts: string[], model: string) => {
    // Generate new stream ID first
    const currentStreamId = generateStreamId();
    
    // Initialize performance tracking and set active stream ref
    activeStreamIdRef.current = currentStreamId;
    streamStartTimeRef.current = performance.now();
    chunkSizesRef.current = [];
    
    // Reset metrics
    setStreamingMetrics({
      totalChunks: 0,
      contentChunks: 0,
      toolChunks: 0,
      renderLatency: 0,
      averageChunkSize: 0,
      streamDuration: 0,
      lastUpdateTime: Date.now(),
    });
    
    // Cancel existing stream if there is one
    if (state.isStreaming && clientRef.current?.isConnected()) {
      console.log('[useChatStreamSSE] Canceling existing stream before starting new one');
      cancelStream();
    }

    // Add user message
    const userMessage: MessageType = {
      role: 'user',
      content: message,
      status: 'complete',
      streamId: currentStreamId,
    };
    
    // Use transition for user message too
    startTransition(() => {
      setMessages(prev => [...prev, userMessage]);
    });

    // Initialize assistant message  
    const assistantMessage: MessageType = {
      role: 'assistant',
      content: '',
      status: 'streaming',
      streamId: currentStreamId,
    };
    
    startTransition(() => {
      setMessages(prev => [...prev, assistantMessage]);
    });

    // Reset state with new stream ID
    setState({
      isStreaming: true,
      currentMessage: assistantMessage,
      accumulatedContent: '',
      accumulatedReasoning: '',
      toolCalls: new Map(),
      error: null,
      activeStreamId: currentStreamId,
      contentBuffer: '',
    });
    
    // Clear pending updates
    setPendingUpdates([]);

    const request: ChatRequest = {
      message,
      wid,
      sid: active,
      model,
      mode,
      contexts: contexts.length > 0 ? contexts : undefined,
    };

    console.log('[useChatStreamSSE] Starting enhanced stream with request:', {
      message: message.substring(0, 50) + '...',
      wid,
      sid: active,
      model,
      mode,
      contextsCount: contexts.length,
      streamId: currentStreamId,
    });

    try {
      if (!clientRef.current) {
        throw new Error('SSE client not initialized');
      }

      await clientRef.current.streamChat(request, {
        onStatus: (data) => {
          console.log('Status:', data);
          
          // Handle various status updates
          if (data.status === 'thinking') {
            startTransition(() => {
              setMessages(prev => {
                const newMessages = [...prev];
                const lastIndex = newMessages.length - 1;
                if (lastIndex >= 0 && 
                    newMessages[lastIndex].role === 'assistant' && 
                    newMessages[lastIndex].streamId === currentStreamId) {
                  newMessages[lastIndex] = {
                    ...newMessages[lastIndex],
                    status: 'thinking',
                  };
                }
                return newMessages;
              });
            });
          } else if (data.status === 'processing' && data.reason === 'long_operation') {
            // Show user that we're processing a long operation
            console.log(`[useChatStreamSSE] Long operation in progress: ${data.time_since_content}s since last content`);
          } else if (data.status === 'timeout') {
            // Handle timeout status
            console.warn(`[useChatStreamSSE] Stream timeout: ${data.reason}`);
            setState(prev => ({
              ...prev,
              error: `Stream timeout: ${data.reason}`,
              isStreaming: false,
            }));
          } else if (data.status === 'error_recovered') {
            // Handle recovered errors
            console.log(`[useChatStreamSSE] Recovered from error: ${data.error}`);
          }
        },

        onReasoning: (data) => {
          // Check stream ID to prevent race conditions
          if (state.activeStreamId !== currentStreamId) return;
          
          // For DeepSeek models, reasoning is shown as content
          if (data.thinking) {
            appendContent(`[Thinking: ${data.content}]\n`, currentStreamId);
          }
        },

        onContent: (data) => {
          // Check stream ID to prevent race conditions
          if (state.activeStreamId !== currentStreamId) return;
          
          console.log('[useChatStreamSSE] onContent called with:', data);
          
          // Enhanced content update with stream ID
          appendContent(data.delta || '', currentStreamId);
        },

        onToolCall: (data) => {
          // Check stream ID to prevent race conditions
          if (state.activeStreamId !== currentStreamId) return;
          
          // Update tool metrics
          setStreamingMetrics(prev => ({
            ...prev,
            toolChunks: prev.toolChunks + 1,
            totalChunks: prev.totalChunks + 1,
          }));
          
          // Tool calls are shown as content for now
          const toolName = data.tool || 'unknown';
          appendContent(`\nUsing tool: ${toolName}\n`, currentStreamId);
        },

        onToolResult: (data) => {
          // Check stream ID to prevent race conditions
          if (state.activeStreamId !== currentStreamId) return;
          
          // Handle tool results that may contain cell updates
          if (data.result && typeof data.result === 'object') {
            if ('cell' in data.result && 'new_value' in data.result) {
              // Single cell update
              setPendingUpdates(prev => [...prev, data.result as PendingUpdate]);
            } else if ('updates' in data.result && Array.isArray(data.result.updates)) {
              // Multiple cell updates
              setPendingUpdates(prev => [...prev, ...data.result.updates]);
            }
          }
        },

        onUpdate: (data) => {
          // Check stream ID to prevent race conditions
          if (state.activeStreamId !== currentStreamId) return;
          
          // Handle workbook update events
          if (data.updates && Array.isArray(data.updates)) {
            setPendingUpdates(prev => [...prev, ...data.updates]);
          }
        },

        onError: (data) => {
          // Check stream ID to prevent race conditions
          if (state.activeStreamId !== currentStreamId) return;
          
          console.error('Stream error:', data);
          setState(prev => ({
            ...prev,
            error: data.error || 'Unknown error',
            isStreaming: false,
          }));

          startTransition(() => {
            setMessages(prev => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].streamId === currentStreamId) {
                newMessages[lastIndex] = {
                  ...newMessages[lastIndex],
                  content: newMessages[lastIndex].content || `Error: ${data.error || 'Unknown error'}`,
                  status: 'error',
                };
              }
              return newMessages;
            });
          });
        },

        onDone: (data) => {
          // Check stream ID to prevent race conditions
          if (state.activeStreamId !== currentStreamId) return;
          
          console.log('[useChatStreamSSE] Stream completed for:', currentStreamId);
          
          // Clean up the stream
          cleanupStream(currentStreamId);

          // Handle final sheet state if provided
          if (data.sheet) {
            const uiSheet = backendSheetToUI(data.sheet);
            dispatch({ type: 'UPDATE_SHEET', sid: active, data: uiSheet });
          }

          setState(prev => ({
            ...prev,
            isStreaming: false,
            currentMessage: null,
            activeStreamId: null,
          }));

          startTransition(() => {
            setMessages(prev => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].streamId === currentStreamId) {
                // Ensure we have some content in the message
                if (!newMessages[lastIndex].content || newMessages[lastIndex].content.trim() === '') {
                  newMessages[lastIndex].content = mode === 'analyst' 
                    ? 'I\'ve completed the updates to your spreadsheet.' 
                    : 'Analysis complete.';
                }
                newMessages[lastIndex] = {
                  ...newMessages[lastIndex],
                  status: 'complete',
                };
              }
              return newMessages;
            });
          });
        },

        onHeartbeat: () => {
          console.log('Heartbeat received for stream:', currentStreamId);
        },
      });
      
      console.log('[useChatStreamSSE] Enhanced stream completed successfully');
    } catch (error) {
      console.error('[useChatStreamSSE] Failed to start stream:', error);
      
      // Only update state if this is still the current stream
      if (state.activeStreamId === currentStreamId) {
        setState(prev => ({
          ...prev,
          error: error instanceof Error ? error.message : 'Failed to start stream',
          isStreaming: false,
          activeStreamId: null,
        }));

        startTransition(() => {
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].streamId === currentStreamId) {
              newMessages[lastIndex] = {
                ...newMessages[lastIndex],
                content: `Error: ${error instanceof Error ? error.message : 'Failed to start stream'}`,
                status: 'error',
              };
            }
            return newMessages;
          });
        });
      }
    }
  }, [appendContent, mode, wid, active, setMessages, dispatch, state.isStreaming, state.activeStreamId, generateStreamId, cleanupStream]);

  const cancelStream = useCallback(() => {
    const currentStreamId = state.activeStreamId;
    
    clientRef.current?.abort();
    
    if (currentStreamId) {
      cleanupStream(currentStreamId);
    }
    
    setState(prev => ({
      ...prev,
      isStreaming: false,
      currentMessage: null,
      activeStreamId: null,
    }));
  }, [state.activeStreamId, cleanupStream]);

  const applyPendingUpdates = useCallback(async () => {
    if (pendingUpdates.length === 0) return;
    
    try {
      const response = await fetch(`/api/workbooks/${wid}/sheets/${active}/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: pendingUpdates }),
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.sheet) {
          const uiSheet = backendSheetToUI(result.sheet);
          dispatch({ type: 'UPDATE_SHEET', sid: active, data: uiSheet });
        }
        setPendingUpdates([]);
      }
    } catch (error) {
      console.error('Failed to apply updates:', error);
    }
  }, [pendingUpdates, wid, active, dispatch]);

  const rejectPendingUpdates = useCallback(async () => {
    if (pendingUpdates.length === 0) return;
    
    try {
      const response = await fetch(`/api/workbooks/${wid}/sheets/${active}/reject`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.sheet) {
          const uiSheet = backendSheetToUI(result.sheet);
          dispatch({ type: 'UPDATE_SHEET', sid: active, data: uiSheet });
        }
        setPendingUpdates([]);
      }
    } catch (error) {
      console.error('Failed to reject updates:', error);
    }
  }, [pendingUpdates, wid, active, dispatch]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clientRef.current?.abort();
      if (batchingTimerRef.current) {
        clearTimeout(batchingTimerRef.current);
      }
    };
  }, []); // Empty dependency array - only run on mount/unmount

  // NEW: Memoized return object for performance
  const returnValue = useMemo(() => ({
    sendMessage,
    cancelStream,
    isStreaming: state.isStreaming,
    pendingUpdates,
    applyPendingUpdates,
    rejectPendingUpdates,
    streamingMetrics,
  }), [
    sendMessage,
    cancelStream,
    state.isStreaming,
    pendingUpdates,
    applyPendingUpdates,
    rejectPendingUpdates,
    streamingMetrics,
  ]);

  return returnValue;
} 