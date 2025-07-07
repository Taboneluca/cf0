/**
 * React hook for handling chat streaming with SSE.
 */
import { useState, useCallback, useRef, useEffect } from 'react';
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
}

interface StreamingState {
  isStreaming: boolean;
  currentMessage: MessageType | null;
  accumulatedContent: string;
  accumulatedReasoning: string;
  toolCalls: Map<string, any>;
  error: string | null;
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
  });
  
  const [pendingUpdates, setPendingUpdates] = useState<PendingUpdate[]>([]);
  const [wb, dispatch] = useWorkbook();
  const { wid, active } = wb;

  const clientRef = useRef<SSEClient | null>(null);
  const streamIdRef = useRef<number>(0);

  // Initialize SSE client
  useEffect(() => {
    clientRef.current = new SSEClient();
    return () => {
      clientRef.current?.close();
    };
  }, []);

  // Immediate content update - ChatGPT style (no batching)
  const appendContent = useCallback((delta: string) => {
    console.log('[useChatStreamSSE] appendContent called with delta:', delta);
    
    setMessages(prev => {
      const newMessages = [...prev];
      const lastIndex = newMessages.length - 1;
      console.log('[useChatStreamSSE] Messages array length:', newMessages.length, 'Last message role:', newMessages[lastIndex]?.role);
      
      if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
        const oldContent = newMessages[lastIndex].content || '';
        const newContent = oldContent + delta;
        console.log('[useChatStreamSSE] Updating content:', { oldLength: oldContent.length, newLength: newContent.length, delta });
        
        newMessages[lastIndex] = {
          ...newMessages[lastIndex],
          content: newContent,
          timestamp: Date.now(), // Force re-render
        };
      } else {
        console.log('[useChatStreamSSE] Not updating - no assistant message found');
      }
      return newMessages;
    });

    // Update accumulated content in state
    setState(prev => ({
      ...prev,
      accumulatedContent: prev.accumulatedContent + delta,
    }));
  }, [setMessages]);

  const sendMessage = useCallback(async (message: string, contexts: string[], model: string) => {
    // Generate new stream ID first
    const currentStreamId = ++streamIdRef.current;
    
    // Only cancel if there's an active stream
    if (state.isStreaming && clientRef.current?.isConnected()) {
      console.log('[useChatStreamSSE] Canceling existing stream before starting new one');
      cancelStream();
    }

    // Add user message
    const userMessage: MessageType = {
      role: 'user',
      content: message,
      status: 'complete',
    };
    setMessages(prev => [...prev, userMessage]);

    // Initialize assistant message  
    const assistantMessage: MessageType = {
      role: 'assistant',
      content: '',
      status: 'streaming',
    };
    setMessages(prev => [...prev, assistantMessage]);

    // Reset state
    setState({
      isStreaming: true,
      currentMessage: assistantMessage,
      accumulatedContent: '',
      accumulatedReasoning: '',
      toolCalls: new Map(),
      error: null,
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

    console.log('[useChatStreamSSE] Starting stream with request:', {
      message: message.substring(0, 50) + '...',
      wid,
      sid: active,
      model,
      mode,
      contextsCount: contexts.length
    });

    try {
      if (!clientRef.current) {
        throw new Error('SSE client not initialized');
      }

      await clientRef.current.streamChat(request, {
        onStatus: (data) => {
          console.log('Status:', data);
          
          // Update status if it's thinking
          if (data.status === 'thinking') {
            setMessages(prev => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                newMessages[lastIndex] = {
                  ...newMessages[lastIndex],
                  status: 'thinking',
                };
              }
              return newMessages;
            });
          }
        },

        onReasoning: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
          // For DeepSeek models, reasoning is shown as content
          if (data.thinking) {
            appendContent(`[Thinking: ${data.content}]\n`);
          }
        },

        onContent: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
          console.log('[useChatStreamSSE] onContent called with:', data);
          
          // Buffer content updates
          appendContent(data.delta || '');
        },

        onToolCall: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
          // Tool calls are shown as content for now
          const toolName = data.tool || 'unknown';
          appendContent(`\nUsing tool: ${toolName}\n`);
        },

        onToolResult: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
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
          if (streamIdRef.current !== currentStreamId) return;
          
          // Handle workbook update events
          if (data.updates && Array.isArray(data.updates)) {
            setPendingUpdates(prev => [...prev, ...data.updates]);
          }
        },

        onError: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
          console.error('Stream error:', data);
          setState(prev => ({
            ...prev,
            error: data.error || 'Unknown error',
            isStreaming: false,
          }));

          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0) {
              newMessages[lastIndex] = {
                ...newMessages[lastIndex],
                content: newMessages[lastIndex].content || `Error: ${data.error || 'Unknown error'}`,
                status: 'error',
              };
            }
            return newMessages;
          });
        },

        onDone: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
          // Flush any remaining updates
          appendContent('');

          // Handle final sheet state if provided
          if (data.sheet) {
            const uiSheet = backendSheetToUI(data.sheet);
            dispatch({ type: 'UPDATE_SHEET', sid: active, data: uiSheet });
          }

          setState(prev => ({
            ...prev,
            isStreaming: false,
            currentMessage: null,
          }));

          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0) {
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
        },

        onHeartbeat: () => {
          console.log('Heartbeat received');
        },
      });
      
      console.log('[useChatStreamSSE] Stream completed successfully');
    } catch (error) {
      console.error('[useChatStreamSSE] Failed to start stream:', error);
      
      // Only update state if this is still the current stream
      if (streamIdRef.current === currentStreamId) {
        setState(prev => ({
          ...prev,
          error: error instanceof Error ? error.message : 'Failed to start stream',
          isStreaming: false,
        }));

        setMessages(prev => {
          const newMessages = [...prev];
          const lastIndex = newMessages.length - 1;
          if (lastIndex >= 0) {
            newMessages[lastIndex] = {
              ...newMessages[lastIndex],
              content: `Error: ${error instanceof Error ? error.message : 'Failed to start stream'}`,
              status: 'error',
            };
          }
          return newMessages;
        });
      }
    }
  }, [appendContent, mode, wid, active, setMessages, dispatch, state.isStreaming]);

  const cancelStream = useCallback(() => {
    clientRef.current?.abort();
    streamIdRef.current++;
    
    appendContent('');
    
    setState(prev => ({
      ...prev,
      isStreaming: false,
      currentMessage: null,
    }));
  }, [appendContent]);

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
    };
  }, []); // Empty dependency array - only run on mount/unmount

  return {
    sendMessage,
    cancelStream,
    isStreaming: state.isStreaming,
    pendingUpdates,
    applyPendingUpdates,
    rejectPendingUpdates,
  };
} 