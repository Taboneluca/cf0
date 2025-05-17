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
      
      // Add empty assistant message with "thinking" status
      let eventSource = new TextDecoder();
      let isFirstChunk = true;
      
      // Process the stream
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log('Stream complete - reader done');
          break;
        }
        
        const chunk = eventSource.decode(value);
        console.debug('[SSE raw chunk]', chunk);
        
        // Parse the SSE events correctly
        const events: StreamEvent[] = [];
        for (const block of chunk.split('\n\n')) {
          if (!block.trim()) continue;
          
          console.debug('[SSE processing block]', block);
          const dataLine = block.split('\n').find(line => line.startsWith('data: '));
          
          if (!dataLine) {
            console.debug('[SSE skip] No data line in block');
            continue;
          }
          
          try {
            const parsed = JSON.parse(dataLine.slice(6)); // Remove 'data: ' prefix
            events.push(parsed);
            console.debug('[SSE parsed event]', parsed);
          } catch (e) {
            console.error('Error parsing SSE event:', e, dataLine);
          }
        }
        
        console.debug(`[SSE chunk] Parsed ${events.length} events`);
        
        // Process each event
        for (const event of events) {
          if (event.type === 'start') {
            console.log('Received start event');
            // Add a thinking message
            setMessages(prev => [
              ...prev, 
              { 
                role: 'assistant',
                content: '',
                id: `assistant_${Date.now()}`,
                status: 'thinking'
              }
            ]);
          } 
          else if (event.type === 'chunk') {
            // Update the assistant message with new text
            console.debug(`Received text chunk: ${event.text.length} chars`);
            setMessages(prev => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];
              
              if (lastMessage.role === 'assistant') {
                // Append the new text to the existing message
                lastMessage.content += event.text;
                lastMessage.status = 'streaming';
                
                // Detect if this is a section header being added
                // This will help the UI create nice visual transitions as sections form
                const sectionHeaderMatch = event.text.match(/^##\s+([^\n]+)$/);
                if (sectionHeaderMatch) {
                  lastMessage.lastAddedSection = sectionHeaderMatch[1];
                }
              } else {
                // If there's somehow no assistant message, add one
                newMessages.push({
                  role: 'assistant',
                  content: event.text,
                  id: `assistant_${Date.now()}`,
                  status: 'streaming'
                });
              }
              
              return newMessages;
            });
          }
          else if (event.type === 'update') {
            // Handle sheet update from tool
            console.log('Sheet update received:', event.payload);
            // We can optimistically update the UI here
          }
          else if (event.type === 'pending') {
            // Store updates for later application
            console.log(`Received ${event.updates.length} pending updates`);
            setPendingUpdates(event.updates);
          }
          else if (event.type === 'complete') {
            // Mark the streaming as complete and update the sheet
            console.log('Received completion event');
            setMessages(prev => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];
              
              if (lastMessage.role === 'assistant') {
                lastMessage.status = 'complete';
              }
              
              return newMessages;
            });
            
            // Update the spreadsheet with the final state
            if (event.sheet) {
              console.log('Updating sheet with final state from server');
              const uiSheet = backendSheetToUI(event.sheet);
              dispatch({
                type: 'UPDATE_SHEET',
                payload: { id: active, data: uiSheet }
              });
            }
          }
          else if (event.type === 'error') {
            console.error('Streaming error:', event.error);
            // Add an error message
            setMessages(prev => [
              ...prev,
              { 
                role: 'system', 
                content: `Error: ${event.error}`,
                id: `error_${Date.now()}`
              }
            ]);
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