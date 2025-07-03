/**
 * React hook for handling chat streaming with SSE.
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { SSEClient, StreamEvent, ChatRequest } from '@/utils/sse-client';

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
  currentMessage: ChatMessage | null;
  accumulatedContent: string;
  accumulatedReasoning: string;
  toolCalls: Map<string, any>;
  error: string | null;
}

interface UseChatStreamReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  startStream: (request: ChatRequest) => Promise<void>;
  stopStream: () => void;
  clearMessages: () => void;
}

export function useChatStreamSSE(): UseChatStreamReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [state, setState] = useState<StreamingState>({
    isStreaming: false,
    currentMessage: null,
    accumulatedContent: '',
    accumulatedReasoning: '',
    toolCalls: new Map(),
    error: null,
  });

  const clientRef = useRef<SSEClient | null>(null);
  const streamIdRef = useRef<number>(0);
  const updateBufferRef = useRef<string>('');
  const updateTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize SSE client
  useEffect(() => {
    clientRef.current = new SSEClient();
    return () => {
      clientRef.current?.close();
    };
  }, []);

  // Batched UI updates for performance
  const flushUpdates = useCallback(() => {
    if (updateBufferRef.current && state.currentMessage) {
      setState(prev => ({
        ...prev,
        accumulatedContent: prev.accumulatedContent + updateBufferRef.current,
      }));
      
      setMessages(prev => {
        const newMessages = [...prev];
        const lastIndex = newMessages.length - 1;
        if (lastIndex >= 0) {
          newMessages[lastIndex] = {
            ...newMessages[lastIndex],
            content: state.accumulatedContent + updateBufferRef.current,
          };
        }
        return newMessages;
      });
      
      updateBufferRef.current = '';
    }
  }, [state.accumulatedContent, state.currentMessage]);

  // Set up timer for batched updates
  const scheduleUpdate = useCallback(() => {
    if (updateTimerRef.current) {
      clearTimeout(updateTimerRef.current);
    }
    updateTimerRef.current = setTimeout(flushUpdates, 50); // 50ms batching
  }, [flushUpdates]);

  const startStream = useCallback(async (request: ChatRequest) => {
    // Clear any existing stream
    stopStream();

    // Generate new stream ID
    const currentStreamId = ++streamIdRef.current;

    // Add user message
    const userMessage: ChatMessage = {
      role: 'user',
      content: request.message,
      status: 'complete',
    };
    setMessages(prev => [...prev, userMessage]);

    // Initialize assistant message
    const assistantMessage: ChatMessage = {
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

    try {
      await clientRef.current?.streamChat(request, {
        onStatus: (data) => {
          console.log('Status:', data);
        },

        onReasoning: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
          setState(prev => ({
            ...prev,
            accumulatedReasoning: prev.accumulatedReasoning + (data.content || ''),
          }));

          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0) {
              newMessages[lastIndex] = {
                ...newMessages[lastIndex],
                reasoning: prev[lastIndex].reasoning 
                  ? prev[lastIndex].reasoning + (data.content || '')
                  : data.content || '',
              };
            }
            return newMessages;
          });
        },

        onContent: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
          // Buffer content updates
          updateBufferRef.current += data.delta || '';
          scheduleUpdate();
        },

        onToolCall: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
          const toolCall = {
            id: data.id || `tool_${Date.now()}`,
            tool: data.tool,
            arguments: data.arguments,
          };

          setState(prev => {
            const newToolCalls = new Map(prev.toolCalls);
            newToolCalls.set(toolCall.id, toolCall);
            return { ...prev, toolCalls: newToolCalls };
          });

          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0) {
              const existingCalls = newMessages[lastIndex].toolCalls || [];
              newMessages[lastIndex] = {
                ...newMessages[lastIndex],
                toolCalls: [...existingCalls, toolCall],
              };
            }
            return newMessages;
          });
        },

        onToolResult: (data) => {
          if (streamIdRef.current !== currentStreamId) return;
          
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].toolCalls) {
              newMessages[lastIndex].toolCalls = newMessages[lastIndex].toolCalls!.map(
                call => call.id === data.tool_id 
                  ? { ...call, result: data.result }
                  : call
              );
            }
            return newMessages;
          });
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
                status: 'error',
              };
            }
            return newMessages;
          });
        },

        onDone: () => {
          if (streamIdRef.current !== currentStreamId) return;
          
          // Flush any remaining updates
          flushUpdates();

          setState(prev => ({
            ...prev,
            isStreaming: false,
            currentMessage: null,
          }));

          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0) {
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
    } catch (error) {
      console.error('Failed to start stream:', error);
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to start stream',
        isStreaming: false,
      }));
    }
  }, [flushUpdates, scheduleUpdate]);

  const stopStream = useCallback(() => {
    clientRef.current?.abort();
    streamIdRef.current++;
    
    if (updateTimerRef.current) {
      clearTimeout(updateTimerRef.current);
      updateTimerRef.current = null;
    }
    
    flushUpdates();
    
    setState(prev => ({
      ...prev,
      isStreaming: false,
      currentMessage: null,
    }));
  }, [flushUpdates]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setState({
      isStreaming: false,
      currentMessage: null,
      accumulatedContent: '',
      accumulatedReasoning: '',
      toolCalls: new Map(),
      error: null,
    });
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (updateTimerRef.current) {
        clearTimeout(updateTimerRef.current);
      }
      stopStream();
    };
  }, [stopStream]);

  return {
    messages,
    isStreaming: state.isStreaming,
    error: state.error,
    startStream,
    stopStream,
    clearMessages,
  };
} 