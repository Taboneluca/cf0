import { useState, useEffect, useCallback, useRef } from 'react';
import { useWorkbook } from '@/context/workbook-context';
import { Message } from '@/types/spreadsheet';
import { backendSheetToUI } from '@/utils/transform';

// Utility function to yield to the DOM - improved for better streaming performance
const yieldToDom = (): Promise<void> => {
  return new Promise(resolve => {
    // Use double requestAnimationFrame for better performance and smoother rendering
    if (typeof requestAnimationFrame !== 'undefined') {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          resolve();
        });
      });
    } else {
      // Fallback for environments without requestAnimationFrame
      setTimeout(resolve, 0);
    }
  });
};

type StreamEvent = 
  | { type: 'start' }
  | { type: 'chunk', text: string }
  | { type: 'update', payload: any }
  | { type: 'pending', updates: any[] }
  | { type: 'complete', sheet: any }
  | { type: 'error', error: string }
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
  console.log(`[${timestamp}] 🔍 [${category}] ${message}`, data ? data : '');
};

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
  
  // Track processed chunks to prevent duplicates
  const processedChunks = useRef(new Set<string>());
  
  // Add streaming status tracking
  const streamingStats = useRef({
    chunksReceived: 0,
    bytesReceived: 0,
    lastChunkTime: 0,
    averageChunkDelay: 0
  });
  
  // Add a function to scroll to bottom of messages
  const scrollToBottom = useCallback(() => {
    if (typeof document !== 'undefined') {
      // Find all message containers and scroll the last one into view
      const messageContainers = document.querySelectorAll('.message-streaming');
      if (messageContainers.length > 0) {
        const lastMessage = messageContainers[messageContainers.length - 1];
        lastMessage?.scrollIntoView({ behavior: 'smooth' });
      }
      
      // Also try scrolling the messages container if available
      const messagesContainer = document.querySelector('.overflow-y-auto');
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    }
  }, []);

  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      if (DEBUG_STREAMING) console.log('[Stream DEBUG] Cancelling stream');
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  const applyPendingUpdates = useCallback(() => {
    if (pendingUpdates.length > 0 && wb) {
      if (DEBUG_STREAMING) console.log(`[Stream DEBUG] Applying ${pendingUpdates.length} pending updates`);
      
      // Make a local copy of the active sheet
      const sheetId = wb.active;
      const sheet = { ...wb.data[sheetId] };

      pendingUpdates.forEach(update => {
        if (!update || !update.cell) return;

        const value = update.new_value ?? update.value ?? update.new;
        if (value === undefined) return;

        // Convert "B4" -> row 3, col 1 (zero-based)
        const match = String(update.cell).match(/^([A-Za-z]+)(\d+)$/);
        if (!match) return;
        const [, colLetters, rowStr] = match;

        const row = parseInt(rowStr, 10) - 1;
        const col = colLetters
          .toUpperCase()
          .split('')
          .reduce((acc, ch) => acc * 26 + (ch.charCodeAt(0) - 64), 0) - 1;

        // Ensure the sheet has necessary structures
        if (!sheet.rows) sheet.rows = [];
        if (!sheet.columns) sheet.columns = [];
        if (!sheet.cells) sheet.cells = {};
        
        // Expand rows/columns arrays if needed
        while (sheet.rows.length <= row) {
          sheet.rows.push(sheet.rows.length + 1);
        }
        
        while (sheet.columns.length <= col) {
          const colNum = sheet.columns.length;
          // Convert column index to letter (0=A, 1=B, etc.)
          const colLetter = String.fromCharCode(65 + colNum);
          sheet.columns.push(colLetter);
        }

        sheet.cells[`${row},${col}`] = value;
      });

      // Push the new sheet back into context
      dispatch({
        type: "UPDATE_SHEET",
        payload: { id: sheetId, data: sheet }
      });

      setPendingUpdates([]);
    }
  }, [pendingUpdates, wb, dispatch]);

  const rejectPendingUpdates = useCallback(() => {
    if (DEBUG_STREAMING) console.log(`[Stream DEBUG] Rejecting ${pendingUpdates.length} pending updates`);
    setPendingUpdates([]);
  }, [pendingUpdates]);

  // Helper function to apply tool updates to the sheet
  const applyUpdatesToSheet = useCallback((updates: any[]) => {
    if (!wb || !updates || updates.length === 0) return;
    
    const sheetId = wb.active;
    const sheet = { ...wb.data[sheetId] };
    
    updates.forEach(update => {
      if (!update || !update.cell) return;
      
      const value = update.new_value ?? update.value ?? update.new;
      if (value === undefined) return;
      
      // Convert "B4" -> row 3, col 1 (zero-based)
      const match = String(update.cell).match(/^([A-Za-z]+)(\d+)$/);
      if (!match) return;
      const [, colLetters, rowStr] = match;
      
      const row = parseInt(rowStr, 10) - 1;
      const col = colLetters
        .toUpperCase()
        .split('')
        .reduce((acc, ch) => acc * 26 + (ch.charCodeAt(0) - 64), 0) - 1;
      
      // Ensure the sheet has necessary structures
      if (!sheet.rows) sheet.rows = [];
      if (!sheet.columns) sheet.columns = [];
      if (!sheet.cells) sheet.cells = {};
      
      // Expand rows/columns arrays if needed
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
    
    // Update the workbook context
    dispatch({
      type: "UPDATE_SHEET",
      payload: { id: sheetId, data: sheet }
    });
    
    if (DEBUG_STREAMING) console.log(`[Stream DEBUG] Applied ${updates.length} updates to sheet`);
  }, [wb, dispatch]);

  // Helper function to handle tool errors gracefully
  const handleToolError = useCallback((toolName: string, error: any) => {
    if (DEBUG_STREAMING) {
      console.warn(`[Stream DEBUG] Tool ${toolName} failed:`, error);
    }
    
    // Show user-friendly error message
    let errorMessage = `Tool ${toolName} encountered an issue`;
    
    if (typeof error === 'object' && error.error) {
      errorMessage = error.error;
      
      // If there's an example, show it to help the user
      if (error.example) {
        console.log(`[Stream DEBUG] Example for ${toolName}:`, error.example);
      }
    } else if (typeof error === 'string') {
      errorMessage = error;
    }
    
    // Don't break the stream, just log the error
    console.warn(`Tool error: ${errorMessage}`);
  }, []);

  const sendMessage = useCallback(async (message: string, contexts: string[] = [], model?: string) => {
    if (!wb || !wb.wid || !wb.active || loading) {
      debugLog('VALIDATION', 'Cannot send message - workbook not ready', { wb, loading });
      return;
    }
    
    // Reset debugging counters and streaming content
    debugChunkCount.current = 0;
    debugLastChunkTime.current = Date.now();
    
    debugLog('STREAM_START', 'Starting new streaming request', { 
      message: message.slice(0, 100) + (message.length > 100 ? '...' : ''), 
      mode, 
      wid: wb.wid, 
      sid: wb.active,
      model 
    });
    
    // Cancel any existing stream
    cancelStream();
    
    // Create a new abort controller
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    
    // Show that we're waiting for a response
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
    
    // Fallback: If no start event is received within 2 seconds, switch to streaming anyway
    const fallbackTimer = setTimeout(() => {
      if (currentMessageIdRef.current === id) {
        debugLog('FALLBACK', 'Switching to streaming status after 2s delay');
        setMessages(prev => {
          const newMessages = [...prev];
          const index = newMessages.findIndex(m => m.id === id);
          if (index >= 0 && newMessages[index].status === 'thinking') {
            newMessages[index] = {
              ...newMessages[index],
              status: 'streaming'
            };
          }
          return newMessages;
        });
      }
    }, 2000);
    
    setIsStreaming(true);
    
    try {
      const url = '/api/chat/stream';
      
      debugLog('HTTP_REQUEST', 'Sending HTTP request', { url, mode, wid: wb.wid, sid: wb.active, model });
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
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
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      debugLog('HTTP_RESPONSE', 'Stream connection established', { 
        status: response.status,
        headers: Object.fromEntries(response.headers.entries())
      });
      
      // Stream handle
      const reader = response.body?.getReader();
      if (!reader) throw new Error("Failed to get stream reader");
      
      // We need to decode the stream chunks
      const decoder = new TextDecoder();
      let buffer = '';
      
      // For streaming performance analysis
      let totalCharsReceived = 0;
      let totalEvents = 0;
      let eventsByType: Record<string, number> = {};
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        // Decode the chunk and add to buffer
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        totalCharsReceived += chunk.length;
        
        if (DEBUG_SSE) {
          const now = Date.now();
          const timeSinceLastChunk = now - debugLastChunkTime.current;
          debugChunkCount.current++;
          debugLog('SSE_CHUNK', `Raw chunk #${debugChunkCount.current}`, {
            length: chunk.length,
            timeSince: `${timeSinceLastChunk}ms`,
            preview: chunk.slice(0, 100) + (chunk.length > 100 ? '...' : '')
          });
          debugLastChunkTime.current = now;
        }
        
        // Process all complete events in the buffer
        let eventStart = buffer.indexOf('event: ');
        let eventCount = 0; // Count events in this chunk
        
        while (eventStart >= 0) {
          eventCount++;
          const dataIndex = buffer.indexOf('data: ', eventStart);
          if (dataIndex < 0) break;
          
          const eventEnd = buffer.indexOf('\n', eventStart);
          if (eventEnd < 0) break;
          
          const dataEnd = buffer.indexOf('\n\n', dataIndex);
          if (dataEnd < 0) break;
          
          // Extract the event type and data
          const eventType = buffer.substring(eventStart + 7, eventEnd).trim();
          const eventData = buffer.substring(dataIndex + 6, dataEnd).trim();
          
          totalEvents++;
          eventsByType[eventType] = (eventsByType[eventType] || 0) + 1;
          
          if (DEBUG_SSE) {
            const timeSinceLast = formatTimeSince(debugLastChunkTime.current);
            debugLog('SSE_EVENT', `Event #${totalEvents}: ${eventType}`, {
              dataLength: eventData.length,
              timeSince: timeSinceLast,
              preview: eventData.slice(0, 200) + (eventData.length > 200 ? '...' : '')
            });
            debugLastChunkTime.current = Date.now();
          }
          
          try {
            // Parse the event data as JSON
            const event: StreamEvent = {
              ...JSON.parse(eventData),
              type: eventType as any
            };
            
            debugLog('EVENT_PARSED', `Processing ${eventType} event`, event);
            
            // Generate unique chunk ID
            const chunkId = `${event.type}-${event.type === 'chunk' ? event.text?.slice(0, 20) : 'no-text'}-${Date.now()}`;
            
            if (processedChunks.current.has(chunkId)) {
              debugLog('DUPLICATE_CHUNK', 'Duplicate chunk detected and skipped', { chunkId });
              return;
            }
            
            processedChunks.current.add(chunkId);
            
            // Process the event based on type
            if (event.type === 'start') {
              // Clear fallback timer since we got the real start event
              clearTimeout(fallbackTimer);
              
              debugLog('STREAM_STARTED', 'Stream officially started');
              
              // Just mark that streaming has started
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
            }
            else if (event.type === 'chunk') {
              // CRITICAL FIX: Don't accumulate here - just append the new text
              const newText = event.text;
              
              debugLog('CONTENT_CHUNK', 'Received text chunk', {
                newText: event.text,
                chunkLength: event.text.length
              });
              
              // Update the message by appending the new content
              setMessages(prev => {
                const newMessages = [...prev];
                const index = newMessages.findIndex(m => m.id === id);
                if (index >= 0) {
                  // Get existing content and append new text
                  const existingContent = newMessages[index].content || '';
                  const updatedContent = existingContent + newText;
                  
                  newMessages[index] = {
                    ...newMessages[index],
                    content: updatedContent,
                    status: 'streaming' as const,
                    timestamp: Date.now()
                  };
                }
                return newMessages;
              });
              
              // Force immediate scroll after content update
              requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                  scrollToBottom();
                });
              });
            }
            else if (event.type === 'update') {
              debugLog('TOOL_UPDATE', 'Received tool update', event.payload);
              
              // Add to pending updates and immediately apply the update
              setPendingUpdates(prev => {
                const newUpdates = [...prev, event.payload];
                
                // Auto-apply immediately - don't wait for user confirmation
                if (wb && event.payload) {
                  const sheetId = wb.active;
                  const sheet = { ...wb.data[sheetId] };
                  
                  const update = event.payload;
                  if (!update || !update.cell) return newUpdates;

                  const value = update.new_value ?? update.value ?? update.new;
                  if (value === undefined) return newUpdates;

                  // Parse cell reference
                  const match = String(update.cell).match(/^([A-Za-z]+)(\d+)$/);
                  if (!match) return newUpdates;
                  
                  const [, colLetters, rowStr] = match;
                  const row = parseInt(rowStr, 10) - 1;
                  const col = colLetters
                    .toUpperCase()
                    .split('')
                    .reduce((acc, ch) => acc * 26 + (ch.charCodeAt(0) - 64), 0) - 1;

                  // Ensure needed structures
                  if (!sheet.rows) sheet.rows = [];
                  if (!sheet.columns) sheet.columns = [];
                  if (!sheet.cells) sheet.cells = {};
                  
                  // Expand as needed
                  while (sheet.rows.length <= row) {
                    sheet.rows.push(sheet.rows.length + 1);
                  }
                  
                  while (sheet.columns.length <= col) {
                    const colNum = sheet.columns.length;
                    const colLetter = String.fromCharCode(65 + colNum);
                    sheet.columns.push(colLetter);
                  }

                  // Update the cell
                  sheet.cells[`${row},${col}`] = {value};
                  
                  // Apply the change immediately
                  dispatch({
                    type: "UPDATE_SHEET",
                    payload: { id: sheetId, data: sheet }
                  });
                  
                  debugLog('SHEET_UPDATE', 'Auto-applied streaming update', {
                    cell: update.cell,
                    value,
                    sheetId
                  });
                }
                
                return newUpdates;
              });
            }
            else if (event.type === 'complete') {
              // Clear fallback timer
              clearTimeout(fallbackTimer);
              
              debugLog('STREAM_COMPLETE', 'Stream completed', {
                totalChars: totalCharsReceived,
                totalEvents,
                eventsByType,
                sheet: !!event.sheet
              });
              
              // Stream is complete
              setMessages(prev => {
                const newMessages = [...prev];
                const index = newMessages.findIndex(m => m.id === id);
                if (index >= 0) {
                  newMessages[index] = {
                    ...newMessages[index],
                    status: 'complete'
                  };
                }
                return newMessages;
              });
              
              // If we have a sheet update, apply it
              if (event.sheet) {
                const sheetUI = backendSheetToUI(event.sheet);
                // Use the dispatch to update sheet data
                dispatch({
                  type: 'UPDATE_SHEET',
                  payload: { id: wb.active, data: sheetUI }
                });
                debugLog('FINAL_SHEET_UPDATE', 'Applied final sheet state');
              }
              
              setIsStreaming(false);
            }
            else if (event.type === 'error') {
              // Clear fallback timer
              clearTimeout(fallbackTimer);
              
              debugLog('STREAM_ERROR', 'Stream error received', { error: event.error });
              
              // Handle error
              setMessages(prev => {
                const newMessages = [...prev];
                const index = newMessages.findIndex(m => m.id === id);
                if (index >= 0) {
                  newMessages[index] = {
                    ...newMessages[index],
                    content: `Error: ${event.error}`,
                    status: 'complete' // Change to 'complete' to make it display properly
                  };
                }
                return newMessages;
              });
              setIsStreaming(false);
            }
            else if (event.type === 'tool_start') {
              debugLog('TOOL_START', 'Tool execution started', event.payload);
              
              // Simple logging only - no complex tracking needed
            }
            else if (event.type === 'tool_complete') {
              debugLog('TOOL_COMPLETE', 'Tool execution completed', event.payload);
              
              // Handle tool complete results
              const updates = event.payload.updates || [];
              if (updates.length > 0) {
                setPendingUpdates(prev => [...prev, ...updates]);
                debugLog('TOOL_UPDATES', 'Added tool updates to pending', { count: updates.length });
              }
            }
            else if (event.type === 'tool_error') {
              debugLog('TOOL_ERROR', 'Tool execution failed', event.payload);
              
              // Handle tool error gracefully
              const error = event.payload.error;
              const toolName = event.payload.name;
              
              if (toolName && error) {
                handleToolError(toolName, error);
              }
            }
          } catch (e) {
            console.error('Error parsing SSE event', e);
            debugLog('PARSE_ERROR', 'Failed to parse SSE event', { error: e, eventData });
          }
          
          // Remove the processed event from the buffer
          buffer = buffer.substring(dataEnd + 2);
          
          // Look for next event
          eventStart = buffer.indexOf('event: ');
        }
      }
      
      debugLog('STREAM_FINAL', 'Stream processing completed', {
        totalChars: totalCharsReceived,
        totalEvents,
        eventsByType
      });
      
    } catch (e) {
      // Clear fallback timer in case of any error
      clearTimeout(fallbackTimer);
      
      if ((e as Error).name === 'AbortError') {
        debugLog('STREAM_ABORTED', 'Stream aborted by user');
        
        // The request was aborted, handle gracefully
        setMessages(prev => {
          const newMessages = [...prev];
          const index = newMessages.findIndex(m => m.id === id);
          if (index >= 0) {
            // Get the current content from the message or use empty string
            const currentContent = newMessages[index].content || '';
            newMessages[index] = {
              ...newMessages[index],
              content: currentContent + "\n\n[Stopped by user]",
              status: 'complete'
            };
          }
          return newMessages;
        });
      } else {
        console.error('Error in streaming', e);
        debugLog('STREAM_ERROR', 'Error in streaming process', { error: e });
        
        setMessages(prev => {
          const newMessages = [...prev];
          const index = newMessages.findIndex(m => m.id === id);
          if (index >= 0) {
            newMessages[index] = {
              ...newMessages[index],
              content: `Error: ${(e as Error).message}`,
              status: 'complete' // Change to 'complete' to make it display properly
            };
          }
          return newMessages;
        });
      }
      setIsStreaming(false);
    } finally {
      abortControllerRef.current = null;
    }
  }, [wb, loading, dispatch, mode, cancelStream, setMessages, handleToolError]);

  return {
    sendMessage,
    cancelStream,
    isStreaming,
    pendingUpdates,
    applyPendingUpdates,
    rejectPendingUpdates,
    applyUpdatesToSheet,
    handleToolError
  };
} 