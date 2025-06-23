import { useState, useEffect, useCallback, useRef } from 'react';
import { flushSync } from 'react-dom';
import { useWorkbook } from '@/context/workbook-context';
import { Message } from '@/types/spreadsheet';
import { backendSheetToUI } from '@/utils/transform';

// =========================================
// 2025 OPTIMIZED STREAMING IMPLEMENTATION
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

export function useChatStream(
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
  mode: 'ask' | 'analyst'
) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [pendingUpdates, setPendingUpdates] = useState<any[]>([]);
  const currentMessageIdRef = useRef<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
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
    if (eventSourceRef.current) {
      debugLog('STREAM_CANCEL', 'Closing EventSource connection');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
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

  // Main streaming function - 2025 optimized
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
    
    debugLog('STREAM_START', 'Starting optimized EventSource streaming', { 
      message: message.slice(0, 100) + (message.length > 100 ? '...' : ''), 
      mode, 
      wid: wb.wid, 
      sid: wb.active,
      model 
    });
    
    const id = `msg-${Date.now()}`;
    currentMessageIdRef.current = id;
    
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
    
    try {
             // Build the SSE URL with query parameters for instant connection
       const streamUrl = '/api/chat/stream';
       
       // Create EventSource with POST data as URL parameters (2025 optimization)
       const params = new URLSearchParams({
         mode,
         message,
         wid: wb.wid,
         sid: wb.active,
         contexts: JSON.stringify(contexts),
         model: model || ''
       });
       
       // Use the optimized Next.js API route with GET for EventSource compatibility
       const eventSource = new EventSource(`${streamUrl}?${params.toString()}`);
      eventSourceRef.current = eventSource;
      
      // Fallback timer - if no data in 3 seconds, show error
      const timeoutTimer = setTimeout(() => {
        if (currentMessageIdRef.current === id) {
          debugLog('TIMEOUT', 'Stream timeout - no data received in 3 seconds');
          flushSync(() => {
            setMessages(prev => {
              const newMessages = [...prev];
              const index = newMessages.findIndex(m => m.id === id);
              if (index >= 0) {
                               newMessages[index] = {
                 ...newMessages[index],
                 content: 'Request timed out. Please try again.',
                 status: 'complete' as const
               };
              }
              return newMessages;
            });
          });
          cancelStream();
        }
      }, 3000);
      
      // Handle stream events
      eventSource.onopen = () => {
        debugLog('SSE_CONNECTED', 'EventSource connection established');
        clearTimeout(timeoutTimer);
      };
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as StreamEvent;
          debugLog('SSE_EVENT', `Received event: ${data.type}`, data);
          
          streamStats.current.chunkCount++;
          if (streamStats.current.firstChunkTime === 0) {
            streamStats.current.firstChunkTime = Date.now();
            const ttft = streamStats.current.firstChunkTime - streamStats.current.startTime;
            debugLog('PERFORMANCE', `Time to first token: ${ttft}ms`);
          }
          
          // Handle different event types
          switch (data.type) {
            case 'start':
              debugLog('STREAM_STARTED', 'Stream officially started');
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
              const newText = data.text;
              debugLog('CONTENT_CHUNK', `Chunk #${streamStats.current.chunkCount}`, { 
                text: newText, 
                length: newText.length 
              });
              
              // CRITICAL: Use flushSync for instant rendering
              flushSync(() => {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const index = newMessages.findIndex(m => m.id === id);
                  if (index >= 0) {
                    newMessages[index] = {
                      ...newMessages[index],
                      content: (newMessages[index].content || '') + newText,
                      status: 'streaming' as const,
                      timestamp: Date.now() // Mark as streamed
                    };
                  }
                  return newMessages;
                });
              });
              
              // Auto-scroll after content update
              scrollToBottom();
              break;
              
            case 'update':
              debugLog('TOOL_UPDATE', 'Received tool update', data.payload);
              if (data.payload) {
                applyUpdatesToSheet([data.payload]);
              }
              break;
              
            case 'pending':
              debugLog('PENDING_UPDATES', 'Received pending updates', data.updates);
              if (data.updates && data.updates.length > 0) {
                setPendingUpdates(data.updates);
              }
              break;
              
            case 'complete':
              debugLog('STREAM_COMPLETE', 'Stream completed successfully');
              const totalTime = Date.now() - streamStats.current.startTime;
              debugLog('PERFORMANCE', `Total stream time: ${totalTime}ms, chunks: ${streamStats.current.chunkCount}`);
              
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
              
              if (data.sheet) {
                // Apply final sheet updates
                dispatch({
                  type: "UPDATE_SHEET",
                  payload: { id: wb.active, data: data.sheet }
                });
              }
              
              setIsStreaming(false);
              eventSource.close();
              break;
              
            case 'tool_start':
              debugLog('TOOL_START', `Tool started: ${data.payload.name}`, data.payload);
              break;
              
            case 'tool_complete':
              debugLog('TOOL_COMPLETE', `Tool completed: ${data.payload.id}`, data.payload);
              if (data.payload.updates && data.payload.updates.length > 0) {
                applyUpdatesToSheet(data.payload.updates);
              }
              break;
              
            case 'tool_error':
              debugLog('TOOL_ERROR', `Tool error: ${data.payload.name}`, data.payload);
              break;
              
            case 'error':
              debugLog('STREAM_ERROR', 'Stream error received', data.error);
              flushSync(() => {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const index = newMessages.findIndex(m => m.id === id);
                  if (index >= 0) {
                                   newMessages[index] = {
                 ...newMessages[index],
                 content: newMessages[index].content + `\n\nError: ${data.error}`,
                 status: 'complete' as const
               };
                  }
                  return newMessages;
                });
              });
              break;
              
            case 'ping':
              // Ignore ping events silently
              break;
              
            default:
              debugLog('UNKNOWN_EVENT', 'Unknown event type', data);
          }
        } catch (error) {
          debugLog('PARSE_ERROR', 'Failed to parse SSE event', { error, data: event.data });
        }
      };
      
      eventSource.onerror = (error) => {
        debugLog('SSE_ERROR', 'EventSource error', error);
        clearTimeout(timeoutTimer);
        
        flushSync(() => {
          setMessages(prev => {
            const newMessages = [...prev];
            const index = newMessages.findIndex(m => m.id === id);
                         if (index >= 0 && newMessages[index].status === 'thinking') {
               newMessages[index] = {
                 ...newMessages[index],
                 content: 'Connection error. Please try again.',
                 status: 'complete' as const
               };
             }
            return newMessages;
          });
        });
        
        setIsStreaming(false);
        eventSource.close();
      };
      
    } catch (error) {
      debugLog('SEND_ERROR', 'Error starting stream', error);
      
      flushSync(() => {
        setMessages(prev => {
          const newMessages = [...prev];
          const index = newMessages.findIndex(m => m.id === id);
          if (index >= 0) {
                       newMessages[index] = {
             ...newMessages[index],
             content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
             status: 'complete' as const
           };
          }
          return newMessages;
        });
      });
      
      setIsStreaming(false);
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