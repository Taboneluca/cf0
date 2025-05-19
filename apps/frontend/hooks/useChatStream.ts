import { useState, useEffect, useCallback, useRef } from 'react';
import { useWorkbook } from '@/context/workbook-context';
import { Message } from '@/types/spreadsheet';
import { backendSheetToUI } from '@/utils/transform';

type StreamEvent = 
  | { type: 'start' }
  | { type: 'chunk', text: string }
  | { type: 'update', payload: any }
  | { type: 'pending', updates: any[] }
  | { type: 'complete', sheet: any }
  | { type: 'error', error: string };

// Enable more detailed debug logging for streaming
const DEBUG_STREAMING = true;

export function useChatStream(
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
  mode: 'ask' | 'analyst'
) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [pendingUpdates, setPendingUpdates] = useState<any[]>([]);
  const currentMessageIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [wb, dispatch, loading] = useWorkbook();
  
  // Debugging references
  const debugChunkCount = useRef(0);
  const debugLastChunkTime = useRef(Date.now());
  
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
      // Process & apply the updates
      pendingUpdates.forEach(update => {
        // TODO: Apply the update
      });
      setPendingUpdates([]);
    }
  }, [pendingUpdates, wb]);

  const rejectPendingUpdates = useCallback(() => {
    if (DEBUG_STREAMING) console.log(`[Stream DEBUG] Rejecting ${pendingUpdates.length} pending updates`);
    setPendingUpdates([]);
  }, [pendingUpdates]);

  const sendMessage = useCallback(async (message: string, contexts: string[] = [], model?: string) => {
    if (!wb || !wb.wid || !wb.active || loading) {
      if (DEBUG_STREAMING) console.log('[Stream DEBUG] Cannot send message - workbook not ready', { wb, loading });
      return;
    }
    
    // Reset debugging counters
    debugChunkCount.current = 0;
    debugLastChunkTime.current = Date.now();
    
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
      let content = '';
      
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
        while (eventStart >= 0) {
          const dataIndex = buffer.indexOf('data: ', eventStart);
          if (dataIndex < 0) break;
          
          const eventEnd = buffer.indexOf('\n', eventStart);
          if (eventEnd < 0) break;
          
          const dataEnd = buffer.indexOf('\n\n', dataIndex);
          if (dataEnd < 0) break;
          
          // Extract the event type and data
          const eventType = buffer.substring(eventStart + 7, eventEnd).trim();
          const eventData = buffer.substring(dataIndex + 6, dataEnd).trim();
          
          if (DEBUG_STREAMING) console.log(`[Stream DEBUG] Received event: ${eventType} (data length: ${eventData.length})`);
          
          try {
            // Parse the event data as JSON
            const event: StreamEvent = {
              ...JSON.parse(eventData),
              type: eventType as any
            };
            
            // Process the event based on type
            if (event.type === 'start') {
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
              // Update the message content with the new chunk
              content += event.text;
              setMessages(prev => {
                const newMessages = [...prev];
                const index = newMessages.findIndex(m => m.id === id);
                if (index >= 0) {
                  newMessages[index] = {
                    ...newMessages[index],
                    content: content,
                    status: 'streaming'
                  };
                }
                return newMessages;
              });
            }
            else if (event.type === 'update') {
              // Add to pending updates for now
              setPendingUpdates(prev => [...prev, event.payload]);
            }
            else if (event.type === 'complete') {
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
                console.log(`[Stream DEBUG] Stream complete - received ${totalCharsReceived} total characters in ${debugChunkCount.current} chunks`);
              }
            }
            else if (event.type === 'error') {
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
  }, [wb, loading, dispatch, mode, cancelStream, setMessages]);

  return {
    sendMessage,
    cancelStream,
    isStreaming,
    pendingUpdates,
    applyPendingUpdates,
    rejectPendingUpdates
  };
} 