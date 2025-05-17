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

export function useChatStream(
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>,
  mode: 'ask' | 'analyst'
) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [pendingUpdates, setPendingUpdates] = useState<any[]>([]);
  const currentMessageIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [wb, dispatch] = useWorkbook();
  const { wid, active } = wb;

  // Clean up any active streams when component unmounts
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const sendMessage = useCallback(async (
    message: string, 
    contexts: string[] = [],
    model?: string
  ) => {
    if (isStreaming || !message.trim()) return;
    
    setIsStreaming(true);
    setPendingUpdates([]);
    
    // Add user message immediately
    const messageId = `msg_${Date.now()}`;
    currentMessageIdRef.current = messageId;
    
    // Add the user message to the chat
    setMessages(prev => [
      ...prev,
      { role: 'user', content: message, id: messageId }
    ]);
    
    // Create abort controller for this request
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;
    
    try {
      console.log(`Starting chat stream request: mode=${mode}, wid=${wid}, sid=${active}, model=${model || 'default'}`);
      // Create unique request URL
      const apiUrl = `/api/chat/stream`;
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          message,
          wid,
          sid: active,
          contexts,
          model
        }),
        signal
      });
      
      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
      }
      
      console.log('Stream response initiated successfully');
      
      // Set up server-sent events
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body reader available');
      
      // Add empty assistant message immediately (no need to wait for 'start' event)
      setMessages(prev => [
        ...prev, 
        { 
          role: 'assistant',
          content: '',
          id: `assistant_${Date.now()}`,
          status: 'thinking'
        }
      ]);
      
      // Streaming parser variables
      const decoder = new TextDecoder();
      let buffer = ''; // Buffer to accumulate partial chunks
      let firstChunkProcessed = false;
      
      // Process the stream
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log('Stream complete - reader done');
          break;
        }
        
        // Decode and add to our buffer
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        console.debug('[SSE raw chunk]', buffer);
        
        // Process complete SSE events (split on double newlines)
        while (true) {
          const eventEnd = buffer.indexOf('\n\n');
          if (eventEnd === -1) break;
          
          // Extract an event from the buffer
          const eventText = buffer.substring(0, eventEnd);
          buffer = buffer.substring(eventEnd + 2);
          
          // Skip ping events (Anthropic sends these)
          if (eventText.startsWith('event: ping')) {
            console.debug('[SSE ping] Heartbeat received');
            continue;
          }
          
          // Parse the event (format: "event: type\ndata: JSON")
          const eventLines = eventText.split('\n');
          const eventType = eventLines.find(line => line.startsWith('event:'))?.substring(7)?.trim();
          const dataLine = eventLines.find(line => line.startsWith('data:'));
          
          if (!dataLine) {
            console.debug('[SSE skip] No data line in event:', eventText);
            continue;
          }
          
          try {
            const eventData = JSON.parse(dataLine.substring(5).trim());
            console.debug(`[SSE ${eventType || 'unknown'}]`, eventData);
            
            // Process different providers' event types:
            
            // 1. Our standard internal event types
            if (eventType === 'start' || eventData.type === 'start') {
              console.log('Start event received');
              // Already added message above, just noting the start
              firstChunkProcessed = true;
            }
            else if (eventType === 'chunk' || eventData.type === 'chunk') {
              // This is our standard format for text chunks (all providers mapped to this)
              if (typeof eventData.text === 'string') {
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  
                  if (lastMessage.role === 'assistant') {
                    // Append the new text to the existing message
                    lastMessage.content += eventData.text;
                    lastMessage.status = 'streaming';
                    
                    // Detect section headers for better UI transitions
                    if (lastMessage.content.endsWith('\n## ')) {
                      lastMessage.sectionStart = true;
                    }
                    const fullSectionMatch = /##\s+([^\n]+)$/.exec(lastMessage.content);
                    if (fullSectionMatch) {
                      lastMessage.lastAddedSection = fullSectionMatch[1];
                    }
                  }
                  
                  return newMessages;
                });
              }
            }
            
            // 2. Anthropic specific events (these should be translated on the server side, 
            // but we handle them here just in case they come through directly)
            else if (eventType === 'content_block_delta' && eventData.delta?.text) {
              // Anthropic sends content_block_delta with text property
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMessage = newMessages[newMessages.length - 1];
                
                if (lastMessage.role === 'assistant') {
                  lastMessage.content += eventData.delta.text;
                  lastMessage.status = 'streaming';
                }
                
                return newMessages;
              });
            }
            else if (eventType === 'content_block_delta' && eventData.delta?.type === 'tool_use') {
              // Anthropic tool use events (handled by the server)
              console.debug('[SSE Anthropic tool]', eventData.delta);
            }
            
            // 3. Standard spreadsheet events
            else if (eventType === 'update' || eventData.type === 'update') {
              // Handle spreadsheet update events
              console.log('Sheet update received:', eventData.payload);
            }
            else if (eventType === 'pending' || eventData.type === 'pending') {
              // Store pending updates for user approval
              console.log(`Received ${eventData.updates?.length || 0} pending updates`);
              if (eventData.updates && Array.isArray(eventData.updates)) {
                setPendingUpdates(eventData.updates);
              }
            }
            else if (eventType === 'complete' || eventData.type === 'complete') {
              // Mark the streaming as complete
              console.log('Stream complete event received');
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMessage = newMessages[newMessages.length - 1];
                
                if (lastMessage.role === 'assistant') {
                  lastMessage.status = 'complete';
                }
                
                return newMessages;
              });
              
              // Update the spreadsheet with final state
              if (eventData.sheet) {
                console.log('Applying final sheet state from server');
                const uiSheet = backendSheetToUI(eventData.sheet);
                dispatch({
                  type: 'UPDATE_SHEET',
                  payload: { id: active, data: uiSheet }
                });
              }
            }
            else if (eventType === 'error' || eventData.type === 'error') {
              // Handle error events
              const errorMsg = eventData.error || 'Unknown streaming error';
              console.error('Stream error:', errorMsg);
              
              setMessages(prev => [
                ...prev,
                { 
                  role: 'system', 
                  content: `Error: ${errorMsg}`,
                  id: `error_${Date.now()}`
                }
              ]);
            }
          } catch (e) {
            console.error('Error parsing SSE event:', e, dataLine);
          }
        }
      }
    } catch (error) {
      console.error('Error in chat stream:', error);
      // Add an error message if it's not an abort error
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        setMessages(prev => [
          ...prev,
          { 
            role: 'system', 
            content: `Error: ${error instanceof Error ? error.message : String(error)}`,
            id: `error_${Date.now()}`
          }
        ]);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
      console.log('Chat stream request completed');
    }
  }, [active, dispatch, isStreaming, mode, setMessages, wid]);

  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      console.log('Manually cancelling active stream');
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  const applyPendingUpdates = useCallback(async () => {
    if (pendingUpdates.length === 0) return;
    
    console.log(`Applying ${pendingUpdates.length} pending updates to workbook`);
    try {
      const response = await fetch(`/api/workbook/${wid}/sheet/${active}/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: pendingUpdates })
      });
      
      if (!response.ok) {
        throw new Error('Failed to apply updates');
      }
      
      // Clear pending updates
      setPendingUpdates([]);
      
      // Refresh the sheet data
      const data = await response.json();
      if (data.sheet) {
        console.log('Updates applied, refreshing sheet data');
        const uiSheet = backendSheetToUI(data.sheet);
        dispatch({
          type: 'UPDATE_SHEET',
          payload: { id: active, data: uiSheet }
        });
      }
    } catch (error) {
      console.error('Error applying updates:', error);
    }
  }, [active, dispatch, pendingUpdates, wid]);

  const rejectPendingUpdates = useCallback(() => {
    // Simply clear pending updates without applying them
    console.log('Rejecting pending updates');
    setPendingUpdates([]);
  }, []);

  return {
    sendMessage,
    cancelStream,
    isStreaming,
    pendingUpdates,
    applyPendingUpdates,
    rejectPendingUpdates
  };
} 