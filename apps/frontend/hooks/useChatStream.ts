import { useState, useEffect, useCallback, useRef } from 'react';
import { useWorkbook } from '@/context/workbook-context';
import { Message } from '@/types/spreadsheet';
import { backendSheetToUI } from '@/utils/transform';

// Utility function to yield to the DOM
const yieldToDom = (): Promise<void> => {
  return new Promise(resolve => setTimeout(resolve, 0));
};

type StreamEvent = 
  | { type: 'start' }
  | { type: 'chunk', text: string }
  | { type: 'update', payload: any }
  | { type: 'pending', updates: any[] }
  | { type: 'complete', sheet: any }
  | { type: 'error', error: string };

// Enable more detailed debug logging for streaming
const DEBUG_STREAMING = true;

// Function to format time elapsed since last event
const formatTimeSince = (lastEventTime: number): string => {
  const elapsed = Date.now() - lastEventTime;
  return `${elapsed}ms`;
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
  
  // Track current streaming content for incremental updates
  const streamingContentRef = useRef<string>('');
  
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

  // Helper function for updating message content that forces re-render
  const updateMessageContent = useCallback((id: string, text: string) => {
    streamingContentRef.current = text;
    
    setMessages(prev => {
      // Create a new array with all messages
      const newMessages = [...prev];
      
      // Find the message index
      const index = newMessages.findIndex(m => m.id === id);
      if (index >= 0) {
        // Create a new message object with updated content and a new timestamp
        // The timestamp forces React to see this as a new state value
        newMessages[index] = {
          ...newMessages[index],
          content: text,
          status: 'streaming' as const,
          timestamp: Date.now() // Force re-render
        };
      }
      
      return newMessages;
    });
    
    // Ensure the UI scrolls to show new content
    requestAnimationFrame(scrollToBottom);
  }, [setMessages, scrollToBottom]);

  const sendMessage = useCallback(async (message: string, contexts: string[] = [], model?: string) => {
    if (!wb || !wb.wid || !wb.active || loading) {
      if (DEBUG_STREAMING) console.log('[Stream DEBUG] Cannot send message - workbook not ready', { wb, loading });
      return;
    }
    
    // Reset debugging counters and streaming content
    debugChunkCount.current = 0;
    debugLastChunkTime.current = Date.now();
    streamingContentRef.current = '';
    
    if (DEBUG_STREAMING) console.log('[Stream DEBUG] Starting new streaming request', { message, mode, wid: wb.wid, sid: wb.active });
    
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
        if (DEBUG_STREAMING) console.log('[Stream DEBUG] Fallback: switching to streaming status after 2s delay');
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
      
      if (DEBUG_STREAMING) console.log('[Stream DEBUG] Stream connection established');
      
      // Stream handle
      const reader = response.body?.getReader();
      if (!reader) throw new Error("Failed to get stream reader");
      
      // We need to decode the stream chunks
      const decoder = new TextDecoder();
      let buffer = '';
      
      // For streaming performance analysis
      let totalCharsReceived = 0;
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        // Decode the chunk and add to buffer
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        totalCharsReceived += chunk.length;
        
        if (DEBUG_STREAMING) {
          const now = Date.now();
          const timeSinceLastChunk = now - debugLastChunkTime.current;
          debugChunkCount.current++;
          console.log(`[Stream DEBUG] Raw chunk #${debugChunkCount.current}, length: ${chunk.length}, after: ${timeSinceLastChunk}ms`);
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
          
          if (DEBUG_STREAMING) {
            const timeSinceLast = formatTimeSince(debugLastChunkTime.current);
            console.log(`[Stream DEBUG] Received event: ${eventType} (data length: ${eventData.length}) after ${timeSinceLast}`);
            debugLastChunkTime.current = Date.now();
          }
          
          try {
            // Parse the event data as JSON
            const event: StreamEvent = {
              ...JSON.parse(eventData),
              type: eventType as any
            };
            
            // Process the event based on type
            if (event.type === 'start') {
              // Clear fallback timer since we got the real start event
              clearTimeout(fallbackTimer);
              
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
              // Add the new text to the current content
              const newContent = streamingContentRef.current + event.text;
              
              // Update with immediate rendering
              updateMessageContent(id, newContent);
              
              // Add extra debug for the chunk content
              if (DEBUG_STREAMING) {
                console.log(`[Stream DEBUG] Chunk content: "${event.text}"`);
              }
              
              // Give React a chance to flush before parsing the next event
              // eslint-disable-next-line no-await-in-loop
              await yieldToDom();
            }
            else if (event.type === 'update') {
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
                  
                  if (DEBUG_STREAMING) console.log(`[Stream DEBUG] Auto-applied streaming update to ${update.cell}`);
                }
                
                return newUpdates;
              });
            }
            else if (event.type === 'complete') {
              // Clear fallback timer
              clearTimeout(fallbackTimer);
              
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
              }
              
              setIsStreaming(false);
              
              if (DEBUG_STREAMING) {
                console.log(`[Stream DEBUG] Stream complete - received ${totalCharsReceived} total characters in ${debugChunkCount.current} chunks (${eventCount} events parsed in last chunk)`);
              }
            }
            else if (event.type === 'error') {
              // Clear fallback timer
              clearTimeout(fallbackTimer);
              
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
              if (DEBUG_STREAMING) console.log(`[Stream DEBUG] Error: ${event.error}`);
            }
          } catch (e) {
            console.error('Error parsing SSE event', e);
          }
          
          // Remove the processed event from the buffer
          buffer = buffer.substring(dataEnd + 2);
          
          // Look for next event
          eventStart = buffer.indexOf('event: ');
        }
      }
    } catch (e) {
      // Clear fallback timer in case of any error
      clearTimeout(fallbackTimer);
      
      if ((e as Error).name === 'AbortError') {
        if (DEBUG_STREAMING) console.log('[Stream DEBUG] Stream aborted by user');
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
  }, [wb, loading, dispatch, mode, cancelStream, setMessages, updateMessageContent]);

  return {
    sendMessage,
    cancelStream,
    isStreaming,
    pendingUpdates,
    applyPendingUpdates,
    rejectPendingUpdates
  };
} 