import { useState, useEffect, useCallback, useRef } from 'react';
import { flushSync } from 'react-dom';
import { useWorkbook } from '@/context/workbook-context';
import { Message } from '@/types/spreadsheet';

// =========================================
// 2025 LLM STREAMING IMPLEMENTATION
// Using fetch + ReadableStream (not EventSource)
// =========================================

type StreamEvent = 
  | { type: 'start' }
  | { type: 'chunk', text: string }
  | { type: 'update', payload: any }
  | { type: 'pending', updates: any[] }
  | { type: 'complete', sheet: any }
  | { type: 'error', error: string }
  | { type: 'ping' }
  | { type: 'tool_start', payload: { id: string, name: string } }
  | { type: 'tool_complete', payload: { id: string, result: any, updates?: any[] } }
  | { type: 'tool_error', payload: { id: string, error: any, name: string } };

// Enable more detailed debug logging for streaming
const DEBUG_STREAMING = process.env.NODE_ENV === 'development' || process.env.NEXT_PUBLIC_DEBUG_STREAMING === '1';
const DEBUG_SSE = process.env.NEXT_PUBLIC_DEBUG_SSE === '1';
const DEBUG_TOOLS = process.env.NEXT_PUBLIC_DEBUG_TOOLS === '1';

// Function to format time elapsed since last event
const formatTimeSince = (lastEventTime: number): string => {
  const elapsed = Date.now() - lastEventTime;
  return `${elapsed}ms`;
};

// Add detailed logging helper
const debugLog = (category: string, message: string, data?: any) => {
  if (!DEBUG_STREAMING) return;
  
  const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
  console.log(`[${timestamp}] 🚀 [${category}] ${message}`, data ? data : '');
};

// 2025 Streaming Parser for SSE events
async function* parseSSEStream(response: Response): AsyncGenerator<StreamEvent, void, unknown> {
  if (!response.body) {
    throw new Error('Response body is null');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      
      // Process complete SSE events
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line
      
      let currentEvent: { event?: string; data?: string; id?: string } = {};
      
      for (const line of lines) {
        if (line === '') {
          // Empty line marks end of event
          if (currentEvent.data !== undefined) {
            try {
              const eventData = JSON.parse(currentEvent.data);
              yield {
                ...eventData,
                type: currentEvent.event || 'message'
              } as StreamEvent;
            } catch (e) {
              debugLog('PARSE_ERROR', 'Failed to parse SSE event', { line, error: e });
            }
          }
          currentEvent = {};
        } else if (line.startsWith('event: ')) {
          currentEvent.event = line.slice(7);
        } else if (line.startsWith('data: ')) {
          currentEvent.data = line.slice(6);
        } else if (line.startsWith('id: ')) {
          currentEvent.id = line.slice(4);
        }
        // Ignore other fields like 'retry:'
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export function useChatStream(
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
  mode: 'ask' | 'analyst'
) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [pendingUpdates, setPendingUpdates] = useState<any[]>([]);
  const currentMessageIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [wb, dispatch, loading] = useWorkbook();
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  
  // Debugging references
  const debugChunkCount = useRef(0);
  const debugLastChunkTime = useRef(Date.now());
  
  // Track processed chunks to prevent duplicates - improved with better IDs
  const processedChunks = useRef(new Set<string>());
  const chunkSequence = useRef(0);
  
  // Add streaming status tracking
  const streamingStats = useRef({
    chunksReceived: 0,
    bytesReceived: 0,
    lastChunkTime: 0,
    averageChunkDelay: 0
  });
  
  // Performance tracking
  const streamStats = useRef({
    startTime: 0,
    firstChunkTime: 0,
    chunkCount: 0
  });
  
  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      const messagesContainer = document.querySelector('.overflow-y-auto');
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    });
  }, []);

  // Cancel any active stream
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      debugLog('STREAM_CANCEL', 'Aborting fetch request');
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  // Apply tool updates to workbook
  const applyUpdatesToSheet = useCallback((updates: any[]) => {
    if (!wb || !updates || updates.length === 0) return;
    
    const sheetId = wb.active;
    const sheet = { ...wb.data[sheetId] };
    
    updates.forEach(update => {
      if (!update || !update.cell) return;
      
      const value = update.new_value ?? update.value ?? update.new;
      if (value === undefined) return;
      
      const match = String(update.cell).match(/^([A-Za-z]+)(\d+)$/);
      if (!match) return;
      const [, colLetters, rowStr] = match;
      
      const row = parseInt(rowStr, 10) - 1;
      const col = colLetters
        .toUpperCase()
        .split('')
        .reduce((acc, ch) => acc * 26 + (ch.charCodeAt(0) - 64), 0) - 1;
      
      if (!sheet.rows) sheet.rows = [];
      if (!sheet.columns) sheet.columns = [];
      if (!sheet.cells) sheet.cells = {};
      
      while (sheet.rows.length <= row) {
        sheet.rows.push(sheet.rows.length + 1);
      }
      
      while (sheet.columns.length <= col) {
        const colNum = sheet.columns.length;
        const colLetter = String.fromCharCode(65 + colNum);
        sheet.columns.push(colLetter);
      }
      
      sheet.cells[`${row},${col}`] = { value };
    });
    
    dispatch({
      type: "UPDATE_SHEET",
      payload: { id: sheetId, data: sheet }
    });
    
    debugLog('SHEET_UPDATE', `Applied ${updates.length} updates to sheet`);
  }, [wb, dispatch]);

  // Apply pending updates
  const applyPendingUpdates = useCallback(() => {
    if (pendingUpdates.length > 0) {
      applyUpdatesToSheet(pendingUpdates);
      setPendingUpdates([]);
    }
  }, [pendingUpdates, applyUpdatesToSheet]);

  // Reject pending updates
  const rejectPendingUpdates = useCallback(() => {
    debugLog('UPDATES_REJECTED', `Rejecting ${pendingUpdates.length} pending updates`);
    setPendingUpdates([]);
  }, [pendingUpdates]);

  // Main streaming function - 2025 LLM optimized
  const sendMessage = useCallback(async (message: string, contexts: string[] = [], model?: string) => {
    if (!wb || !wb.wid || !wb.active || loading) {
      debugLog('VALIDATION', 'Cannot send message - workbook not ready', { wb, loading });
      return;
    }
    
    // Cancel any existing stream
    cancelStream();
    
    // Initialize performance tracking
    streamStats.current = {
      startTime: Date.now(),
      firstChunkTime: 0,
      chunkCount: 0
    };
    
    debugLog('STREAM_START', 'Starting fetch-based streaming for LLM', { 
      message: message.slice(0, 100) + (message.length > 100 ? '...' : ''), 
      mode, 
      wid: wb.wid, 
      sid: wb.active,
      model 
    });
    
    const id = `msg-${Date.now()}`;
    currentMessageIdRef.current = id;
    
    // Create abort controller for this request
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    
    // Add user message
    setMessages(prev => [...prev, {
      id: `user-${id}`,
      role: 'user',
      content: message,
      status: 'complete'
    }]);
    
    // Add assistant message with thinking status
    setMessages(prev => [...prev, {
      id,
      role: 'assistant',
      content: '',
      status: 'thinking'
    }]);
    
    setIsStreaming(true);
    
    // Intelligent batching for smooth rendering
    let accumulatedText = '';
    let lastUpdateTime = 0;
    const MIN_UPDATE_INTERVAL = 50; // Update UI every 50ms max for smooth streaming
    let pendingUpdate = false;
    
    const flushAccumulatedText = () => {
      if (accumulatedText && !pendingUpdate) {
        pendingUpdate = true;
        flushSync(() => {
        setMessages(prev => {
          const newMessages = [...prev];
          const index = newMessages.findIndex(m => m.id === id);
            if (index >= 0) {
              const currentContent = newMessages[index].content || '';
            newMessages[index] = {
              ...newMessages[index],
                content: currentContent + accumulatedText,
                status: 'streaming' as const,
                timestamp: Date.now() // Mark as streamed
            };
          }
          return newMessages;
        });
        });
        accumulatedText = '';
        lastUpdateTime = Date.now();
        pendingUpdate = false;
        scrollToBottom();
      }
    };
    
    try {
      // Use Next.js API route with proper authentication
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        body: JSON.stringify({
          mode,
          message,
          wid: wb.wid,
          sid: wb.active,
          contexts,
          model
        }),
        signal: abortController.signal
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      debugLog('HTTP_RESPONSE', 'Fetch request successful', { 
        status: response.status,
        contentType: response.headers.get('content-type')
      });

      // Process the streaming response
      let hasStarted = false;
      
      for await (const event of parseSSEStream(response)) {
        streamStats.current.chunkCount++;
        
        if (streamStats.current.firstChunkTime === 0) {
          streamStats.current.firstChunkTime = Date.now();
          const ttft = streamStats.current.firstChunkTime - streamStats.current.startTime;
          debugLog('PERFORMANCE', `Time to first token: ${ttft}ms`);
        }
        
        debugLog('SSE_EVENT', `Event #${streamStats.current.chunkCount}: ${event.type}`, event);
        
        // Handle different event types
        switch (event.type) {
          case 'start':
              debugLog('STREAM_STARTED', 'Stream officially started');
            hasStarted = true;
              flushSync(() => {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const index = newMessages.findIndex(m => m.id === id);
                  if (index >= 0) {
                    newMessages[index] = {
                      ...newMessages[index],
                      status: 'streaming'
                    };
                  }
                  return newMessages;
                });
              });
            break;
            
          case 'chunk':
            if (!hasStarted) {
              // Start streaming on first chunk if no start event
              hasStarted = true;
              flushSync(() => {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const index = newMessages.findIndex(m => m.id === id);
                  if (index >= 0) {
                    newMessages[index] = {
                      ...newMessages[index],
                      status: 'streaming'
                    };
                  }
                  return newMessages;
                });
              });
            }
            
            const newText = event.text;
            debugLog('CONTENT_CHUNK', `Chunk #${streamStats.current.chunkCount}`, { 
              text: newText, 
              length: newText.length 
            });
            
            // Intelligent batching: accumulate text and update UI at reasonable intervals
            accumulatedText += newText;
            const now = Date.now();
            
            // Update immediately if enough time has passed or if it's a significant chunk
            if (now - lastUpdateTime >= MIN_UPDATE_INTERVAL || newText.includes('\n') || newText.length > 10) {
              flushAccumulatedText();
            }
            break;
            
          case 'update':
            debugLog('TOOL_UPDATE', 'Received tool update', event.payload);
            if (event.payload) {
              applyUpdatesToSheet([event.payload]);
            }
            break;
            
          case 'pending':
            debugLog('PENDING_UPDATES', 'Received pending updates', event.updates);
            if (event.updates && event.updates.length > 0) {
              setPendingUpdates(event.updates);
            }
            break;
            
          case 'complete':
            debugLog('STREAM_COMPLETE', 'Stream completed successfully');
            const totalTime = Date.now() - streamStats.current.startTime;
            debugLog('PERFORMANCE', `Total stream time: ${totalTime}ms, chunks: ${streamStats.current.chunkCount}`);
            
            // Flush any remaining accumulated text
            flushAccumulatedText();
            
              flushSync(() => {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const index = newMessages.findIndex(m => m.id === id);
                  if (index >= 0) {
                    newMessages[index] = {
                      ...newMessages[index],
                    status: 'complete' as const
                    };
                  }
                  return newMessages;
                });
              });
              
            // SAFETY CHECK: Only update sheet if data is valid
            if (event.sheet && event.sheet.columns && event.sheet.rows) {
                dispatch({
                type: "UPDATE_SHEET",
                payload: { id: wb.active, data: event.sheet }
                });
            } else if (event.sheet) {
              debugLog('SHEET_UPDATE_SKIPPED', 'Skipping incomplete sheet data', event.sheet);
              }
              
              setIsStreaming(false);
            return; // Exit the loop
            
          case 'tool_start':
            debugLog('TOOL_START', `Tool started: ${event.payload.name}`, event.payload);
              break;
            
          case 'tool_complete':
            debugLog('TOOL_COMPLETE', `Tool completed: ${event.payload.id}`, event.payload);
            if (event.payload.updates && event.payload.updates.length > 0) {
              applyUpdatesToSheet(event.payload.updates);
            }
            break;
            
          case 'tool_error':
            debugLog('TOOL_ERROR', `Tool error: ${event.payload.name}`, event.payload);
            break;
            
          case 'error':
            debugLog('STREAM_ERROR', 'Stream error received', event.error);
            // Flush any remaining text before showing error
            flushAccumulatedText();
            
              flushSync(() => {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const index = newMessages.findIndex(m => m.id === id);
                  if (index >= 0) {
                    newMessages[index] = {
                      ...newMessages[index],
                    content: newMessages[index].content + `\n\nError: ${event.error}`,
                    status: 'complete' as const
                    };
                  }
                  return newMessages;
                });
              });
              setIsStreaming(false);
            return; // Exit on error
            
          case 'ping':
            // Ignore ping events silently
              break;
            
          default:
            debugLog('UNKNOWN_EVENT', 'Unknown event type', event);
        }
      }
      
      // Flush any remaining accumulated text
      flushAccumulatedText();
      
      // If we reach here without a complete event, stream ended unexpectedly
      if (hasStarted) {
        debugLog('STREAM_ENDED', 'Stream ended without complete event');
        flushSync(() => {
        setMessages(prev => {
          const newMessages = [...prev];
          const index = newMessages.findIndex(m => m.id === id);
            if (index >= 0 && newMessages[index].status === 'streaming') {
            newMessages[index] = {
              ...newMessages[index],
                status: 'complete' as const
            };
          }
          return newMessages;
        });
        });
      }
      
    } catch (error: any) {
      debugLog('SEND_ERROR', 'Error in streaming request', error);
      
      if (error.name === 'AbortError') {
        debugLog('STREAM_ABORTED', 'Stream was cancelled');
        // Don't show error for user cancellation
        return;
      }
      
      flushSync(() => {
        setMessages(prev => {
          const newMessages = [...prev];
          const index = newMessages.findIndex(m => m.id === id);
          if (index >= 0) {
            newMessages[index] = {
              ...newMessages[index],
              content: `Error: ${error.message || 'Connection failed. Please try again.'}`,
              status: 'complete' as const
            };
          }
          return newMessages;
        });
      });
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [wb, dispatch, mode, loading, cancelStream, applyUpdatesToSheet, scrollToBottom]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelStream();
    };
  }, [cancelStream]);

  return {
    sendMessage,
    isStreaming,
    pendingUpdates,
    applyPendingUpdates,
    rejectPendingUpdates,
    cancelStream
  };
} 