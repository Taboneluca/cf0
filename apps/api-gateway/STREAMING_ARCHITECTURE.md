# Streaming Architecture for Multi-Modal LLM Responses

## Overview

This document outlines the recommended streaming architecture for CF0's API Gateway to handle complex LLM responses including reasoning tokens, tool calls, and content generation across multiple providers (OpenAI, Anthropic, Groq, DeepSeek).

## Requirements Analysis

### Current Streaming Needs

1. **Multiple Stream Types**
   - Reasoning/thinking tokens (DeepSeek-R1 style)
   - Tool call invocations and results
   - Content generation tokens
   - Status updates and errors

2. **Provider Compatibility**
   - OpenAI: Standard streaming format
   - Anthropic: Claude's streaming with native tools
   - Groq: Fast streaming with JSON mode
   - DeepSeek: Reasoning tokens in `additional_kwargs`

3. **Frontend Requirements**
   - Real-time updates in UI
   - Separate handling for different stream types
   - Progress indicators for long-running operations
   - Graceful error handling

## Recommended Architecture: Unified SSE Streaming

### Why Server-Sent Events (SSE)?

1. **Native Browser Support** - No additional libraries needed
2. **Automatic Reconnection** - Built-in retry logic
3. **Event Types** - Native support for different event categories
4. **Unidirectional** - Perfect for LLM streaming use case
5. **HTTP/2 Compatible** - Efficient multiplexing

### Architecture Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │     │   API Gateway   │     │  LLM Providers  │
│   (Next.js)     │     │   (FastAPI)     │     │                 │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│                 │     │                 │     │                 │
│  EventSource    │────▶│  SSE Handler    │────▶│  OpenAI API     │
│  Client         │     │                 │     │                 │
│                 │◀────│  Event          │◀────│  Anthropic API  │
│  UI Updates     │     │  Formatter      │     │                 │
│                 │     │                 │     │  Groq API       │
│                 │     │  Provider       │     │                 │
│  State Mgmt     │     │  Normalizer     │     │  DeepSeek API   │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Implementation Details

### 1. Event Types and Format

```python
# apps/api-gateway/streaming/event_types.py
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel
import json

class EventType(Enum):
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    CONTENT = "content"
    ERROR = "error"
    STATUS = "status"
    DONE = "done"

class StreamEvent(BaseModel):
    type: EventType
    data: Dict[str, Any]
    id: Optional[str] = None
    timestamp: Optional[int] = None
    
    def to_sse(self) -> str:
        """Convert to SSE format"""
        event_data = {
            "event": self.type.value,
            "data": json.dumps(self.data),
        }
        if self.id:
            event_data["id"] = self.id
        
        return "\n".join(f"{k}: {v}" for k, v in event_data.items()) + "\n\n"
```

### 2. Provider-Specific Normalizers

```python
# apps/api-gateway/streaming/normalizers.py
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Any
import asyncio

class ProviderNormalizer(ABC):
    """Base class for provider-specific stream normalizers"""
    
    @abstractmethod
    def normalize(self, chunk: Any) -> List[StreamEvent]:
        """Convert provider-specific chunk to standard events"""
        pass

class OpenAINormalizer(ProviderNormalizer):
    def normalize(self, chunk: Any) -> List[StreamEvent]:
        events = []
        
        if hasattr(chunk, 'choices') and chunk.choices:
            choice = chunk.choices[0]
            
            # Handle content
            if choice.delta.content:
                events.append(StreamEvent(
                    type=EventType.CONTENT,
                    data={"delta": choice.delta.content}
                ))
            
            # Handle tool calls
            if choice.delta.tool_calls:
                for tool_call in choice.delta.tool_calls:
                    events.append(StreamEvent(
                        type=EventType.TOOL_CALL,
                        data={
                            "id": tool_call.id,
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    ))
        
        return events

class DeepSeekNormalizer(ProviderNormalizer):
    def normalize(self, chunk: Any) -> List[StreamEvent]:
        events = []
        
        # Handle reasoning tokens (DeepSeek specific)
        if hasattr(chunk, 'additional_kwargs') and 'reasoning_content' in chunk.additional_kwargs:
            events.append(StreamEvent(
                type=EventType.REASONING,
                data={
                    "content": chunk.additional_kwargs['reasoning_content'],
                    "thinking": True
                }
            ))
        
        # Handle regular content
        if chunk.content:
            events.append(StreamEvent(
                type=EventType.CONTENT,
                data={
                    "delta": chunk.content,
                    "thinking": False
                }
            ))
        
        return events

class AnthropicNormalizer(ProviderNormalizer):
    def normalize(self, chunk: Any) -> List[StreamEvent]:
        events = []
        
        # Handle different event types from Anthropic
        if chunk.type == "content_block_delta":
            if chunk.delta.type == "text_delta":
                events.append(StreamEvent(
                    type=EventType.CONTENT,
                    data={
                        "delta": chunk.delta.text,
                        "index": chunk.index
                    }
                ))
        
        elif chunk.type == "tool_use":
            events.append(StreamEvent(
                type=EventType.TOOL_CALL,
                data={
                    "id": chunk.id,
                    "name": chunk.name,
                    "input": chunk.input
                }
            ))
        
        return events
```

### 3. SSE Endpoint Implementation

```python
# apps/api-gateway/routers/streaming.py
from fastapi import APIRouter, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator
import asyncio

router = APIRouter(prefix="/stream", tags=["streaming"])

@router.post("/chat")
async def stream_chat(request: Request, chat_request: ChatRequest):
    """Stream chat completion with multi-modal responses"""
    
    async def event_generator() -> AsyncGenerator[str, None]:
        orchestrator = StreamingOrchestrator(
            provider=chat_request.provider,
            model=chat_request.model
        )
        
        try:
            async for event in orchestrator.stream_completion(
                messages=chat_request.messages,
                tools=chat_request.tools,
                temperature=chat_request.temperature
            ):
                yield event.to_sse()
                
                # Small delay to prevent overwhelming client
                await asyncio.sleep(0.001)
                
        except Exception as e:
            error_event = StreamEvent(
                type=EventType.ERROR,
                data={"error": str(e), "code": "STREAM_ERROR"}
            )
            yield error_event.to_sse()
    
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        }
    )

@router.post("/chat/with-tools")
async def stream_chat_with_tools(request: Request, chat_request: ChatWithToolsRequest):
    """Stream chat with automatic tool execution"""
    
    async def event_generator() -> AsyncGenerator[str, None]:
        orchestrator = ToolStreamingOrchestrator(
            provider=chat_request.provider,
            model=chat_request.model,
            tools=chat_request.available_tools
        )
        
        async for event in orchestrator.stream_with_tool_execution(
            messages=chat_request.messages,
            max_iterations=chat_request.max_tool_iterations
        ):
            yield event.to_sse()
    
    return EventSourceResponse(event_generator())
```

### 4. Streaming Orchestrator

```python
# apps/api-gateway/streaming/orchestrator.py
from typing import AsyncGenerator, Optional, Dict, Any, List
import asyncio
from llm.factory import get_client

class StreamingOrchestrator:
    """Orchestrates streaming across different providers"""
    
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.client = get_client(f"{provider}:{model}")
        self.normalizer = self._get_normalizer(provider)
    
    def _get_normalizer(self, provider: str) -> ProviderNormalizer:
        normalizers = {
            "openai": OpenAINormalizer(),
            "anthropic": AnthropicNormalizer(),
            "groq": GroqNormalizer(),
            "deepseek": DeepSeekNormalizer()
        }
        return normalizers.get(provider, OpenAINormalizer())
    
    async def stream_completion(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream completion with normalized events"""
        
        # Send initial status
        yield StreamEvent(
            type=EventType.STATUS,
            data={"status": "starting", "provider": self.provider}
        )
        
        try:
            # Create streaming request
            stream = await self.client.stream_chat(
                messages=messages,
                tools=tools,
                temperature=temperature
            )
            
            # Process stream chunks
            async for chunk in stream:
                # Normalize provider-specific chunk
                events = self.normalizer.normalize(chunk)
                
                for event in events:
                    yield event
            
            # Send completion event
            yield StreamEvent(
                type=EventType.DONE,
                data={"status": "completed"}
            )
            
        except Exception as e:
            yield StreamEvent(
                type=EventType.ERROR,
                data={
                    "error": str(e),
                    "provider": self.provider,
                    "recoverable": True
                }
            )

class ToolStreamingOrchestrator(StreamingOrchestrator):
    """Extended orchestrator that handles tool execution"""
    
    def __init__(self, provider: str, model: str, tools: List[Dict]):
        super().__init__(provider, model)
        self.tools = {tool["name"]: tool["function"] for tool in tools}
    
    async def stream_with_tool_execution(
        self,
        messages: List[Dict],
        max_iterations: int = 5
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream with automatic tool execution"""
        
        iteration = 0
        current_messages = messages.copy()
        
        while iteration < max_iterations:
            tool_calls_pending = []
            
            async for event in self.stream_completion(current_messages, list(self.tools.values())):
                yield event
                
                # Collect tool calls
                if event.type == EventType.TOOL_CALL:
                    tool_calls_pending.append(event.data)
            
            # Execute tools if any
            if tool_calls_pending:
                for tool_call in tool_calls_pending:
                    result = await self._execute_tool(tool_call)
                    
                    # Stream tool result
                    yield StreamEvent(
                        type=EventType.TOOL_RESULT,
                        data={
                            "tool_id": tool_call["id"],
                            "result": result
                        }
                    )
                    
                    # Add to messages
                    current_messages.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call["id"]
                    })
                
                iteration += 1
            else:
                # No more tools to execute
                break
    
    async def _execute_tool(self, tool_call: Dict) -> Any:
        """Execute a tool and return result"""
        tool_name = tool_call["name"]
        tool_args = json.loads(tool_call["arguments"])
        
        if tool_name in self.tools:
            # Execute tool function
            result = await self.tools[tool_name](**tool_args)
            return result
        else:
            return {"error": f"Unknown tool: {tool_name}"}
```

## Frontend Integration

### 1. SSE Client Implementation

```typescript
// apps/frontend/utils/sse-client.ts
import { EventSourcePolyfill } from 'event-source-polyfill';

export interface StreamEvent {
  type: 'reasoning' | 'tool_call' | 'tool_result' | 'content' | 'error' | 'status' | 'done';
  data: any;
  id?: string;
  timestamp?: number;
}

export class SSEClient {
  private eventSource: EventSourcePolyfill | null = null;
  
  async streamChat(
    request: ChatRequest,
    handlers: {
      onReasoning?: (data: any) => void;
      onToolCall?: (data: any) => void;
      onToolResult?: (data: any) => void;
      onContent?: (data: any) => void;
      onError?: (data: any) => void;
      onStatus?: (data: any) => void;
      onDone?: () => void;
    }
  ): Promise<void> {
    const url = `${process.env.NEXT_PUBLIC_API_URL}/stream/chat`;
    
    this.eventSource = new EventSourcePolyfill(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    
    // Set up event handlers
    this.eventSource.addEventListener('reasoning', (e: any) => {
      if (handlers.onReasoning) {
        handlers.onReasoning(JSON.parse(e.data));
      }
    });
    
    this.eventSource.addEventListener('tool_call', (e: any) => {
      if (handlers.onToolCall) {
        handlers.onToolCall(JSON.parse(e.data));
      }
    });
    
    this.eventSource.addEventListener('tool_result', (e: any) => {
      if (handlers.onToolResult) {
        handlers.onToolResult(JSON.parse(e.data));
      }
    });
    
    this.eventSource.addEventListener('content', (e: any) => {
      if (handlers.onContent) {
        handlers.onContent(JSON.parse(e.data));
      }
    });
    
    this.eventSource.addEventListener('error', (e: any) => {
      if (handlers.onError) {
        handlers.onError(JSON.parse(e.data));
      }
    });
    
    this.eventSource.addEventListener('status', (e: any) => {
      if (handlers.onStatus) {
        handlers.onStatus(JSON.parse(e.data));
      }
    });
    
    this.eventSource.addEventListener('done', () => {
      if (handlers.onDone) {
        handlers.onDone();
      }
      this.close();
    });
    
    this.eventSource.onerror = (error) => {
      console.error('SSE Error:', error);
      if (handlers.onError) {
        handlers.onError({ error: 'Connection lost', code: 'SSE_ERROR' });
      }
    };
  }
  
  close(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
  
  abort(): void {
    this.close();
  }
}
```

### 2. React Hook for Streaming

```typescript
// apps/frontend/hooks/useChatStream.ts
import { useState, useCallback, useRef } from 'react';
import { SSEClient, StreamEvent } from '@/utils/sse-client';

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  reasoning?: string;
  toolCalls?: any[];
}

export function useChatStream() {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const clientRef = useRef<SSEClient | null>(null);
  
  const startStream = useCallback(async (request: ChatRequest) => {
    setIsStreaming(true);
    setEvents([]);
    
    clientRef.current = new SSEClient();
    
    await clientRef.current.streamChat(request, {
      onReasoning: (data) => {
        setEvents(prev => [...prev, {
          id: Date.now().toString(),
          type: 'reasoning',
          data,
          timestamp: Date.now()
        }]);
      },
      
      onToolCall: (data) => {
        setEvents(prev => [...prev, {
          id: data.id,
          type: 'tool_call',
          data,
          timestamp: Date.now()
        }]);
      },
      
      onContent: (data) => {
        setEvents(prev => {
          const last = prev[prev.length - 1];
          if (last?.type === 'content') {
            // Append to existing content
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                data: {
                  ...last.data,
                  delta: last.data.delta + data.delta
                }
              }
            ];
          }
          return [...prev, {
            id: Date.now().toString(),
            type: 'content',
            data,
            timestamp: Date.now()
          }];
        });
      },
      
      onDone: () => {
        setIsStreaming(false);
      },
      
      onError: (data) => {
        setIsStreaming(false);
        console.error('Stream error:', data);
      }
    });
  }, []);
  
  const stopStream = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.abort();
      setIsStreaming(false);
    }
  }, []);
  
  return {
    events,
    isStreaming,
    startStream,
    stopStream
  };
}
```

## Performance Considerations

### 1. Buffering Strategy

```python
class AdaptiveBuffer:
    """Adaptive buffering based on client consumption rate"""
    
    def __init__(self, initial_size: int = 10):
        self.buffer = asyncio.Queue(maxsize=initial_size)
        self.consumption_rate = 0
        self.production_rate = 0
        
    async def adapt_buffer_size(self):
        """Adjust buffer size based on rates"""
        if self.production_rate > self.consumption_rate * 1.5:
            # Client is slow, increase buffer
            new_size = min(self.buffer.maxsize * 2, 1000)
            # Recreate queue with new size
            # ...
        elif self.consumption_rate > self.production_rate * 1.5:
            # Client is fast, decrease buffer
            new_size = max(self.buffer.maxsize // 2, 10)
            # ...
```

### 2. Connection Management

```python
class ConnectionManager:
    """Manages SSE connections with health checks"""
    
    def __init__(self):
        self.connections = {}
        self.heartbeat_interval = 30  # seconds
    
    async def add_connection(self, conn_id: str, request: Request):
        self.connections[conn_id] = {
            "request": request,
            "last_heartbeat": time.time(),
            "active": True
        }
        
        # Start heartbeat task
        asyncio.create_task(self._heartbeat_loop(conn_id))
    
    async def _heartbeat_loop(self, conn_id: str):
        """Send periodic heartbeats to keep connection alive"""
        while conn_id in self.connections and self.connections[conn_id]["active"]:
            await asyncio.sleep(self.heartbeat_interval)
            
            # Send heartbeat event
            heartbeat = StreamEvent(
                type=EventType.STATUS,
                data={"status": "heartbeat", "connection_id": conn_id}
            )
            # Send to client...
```

## Testing Strategy

### 1. Unit Tests for Normalizers

```python
# tests/test_normalizers.py
import pytest
from streaming.normalizers import OpenAINormalizer, DeepSeekNormalizer

class TestOpenAINormalizer:
    def test_content_normalization(self):
        normalizer = OpenAINormalizer()
        chunk = MockOpenAIChunk(content="Hello")
        
        events = normalizer.normalize(chunk)
        
        assert len(events) == 1
        assert events[0].type == EventType.CONTENT
        assert events[0].data["delta"] == "Hello"
    
    def test_tool_call_normalization(self):
        normalizer = OpenAINormalizer()
        chunk = MockOpenAIChunk(tool_calls=[{
            "id": "call_123",
            "function": {
                "name": "get_weather",
                "arguments": '{"location": "NYC"}'
            }
        }])
        
        events = normalizer.normalize(chunk)
        
        assert len(events) == 1
        assert events[0].type == EventType.TOOL_CALL
        assert events[0].data["name"] == "get_weather"
```

### 2. Integration Tests

```python
# tests/test_streaming_integration.py
import pytest
from httpx import AsyncClient
import json

@pytest.mark.asyncio
async def test_full_streaming_flow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/stream/chat",
            json={
                "provider": "openai",
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}]
            },
            headers={"Accept": "text/event-stream"}
        )
        
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)
        
        # Verify event sequence
        assert any(e["type"] == "status" for e in events)
        assert any(e["type"] == "content" for e in events)
        assert any(e["type"] == "done" for e in events)
```

### 3. Load Testing

```javascript
// k6/streaming-load-test.js
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const streamDuration = new Trend('stream_duration');
const firstByteTime = new Trend('first_byte_time');

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 50 },
    { duration: '30s', target: 0 },
  ],
};

export default function() {
  const start = Date.now();
  let firstByte = null;
  
  const res = http.post(
    'http://localhost:8000/stream/chat',
    JSON.stringify({
      provider: 'openai',
      model: 'gpt-4',
      messages: [{ role: 'user', content: 'Write a story' }]
    }),
    {
      headers: { 'Content-Type': 'application/json' },
      responseType: 'stream',
    }
  );
  
  // Process stream
  res.body.on('data', (chunk) => {
    if (!firstByte) {
      firstByte = Date.now();
      firstByteTime.add(firstByte - start);
    }
  });
  
  res.body.on('end', () => {
    streamDuration.add(Date.now() - start);
  });
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'has event-stream header': (r) => 
      r.headers['Content-Type'].includes('text/event-stream'),
  });
}
```

## Deployment Considerations

### 1. Reverse Proxy Configuration

```nginx
# nginx.conf
location /stream/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Cache-Control "no-cache";
    proxy_set_header X-Accel-Buffering "no";
    
    # SSE specific
    proxy_buffering off;
    proxy_read_timeout 86400;
    keepalive_timeout 86400;
}
```

### 2. CDN Considerations

- Disable caching for streaming endpoints
- Configure appropriate timeouts
- Consider using dedicated streaming infrastructure

### 3. Monitoring & Observability

```python
# apps/api-gateway/streaming/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Metrics
stream_started = Counter('stream_started_total', 'Total streams started')
stream_completed = Counter('stream_completed_total', 'Total streams completed')
stream_errors = Counter('stream_errors_total', 'Total stream errors')
stream_duration = Histogram('stream_duration_seconds', 'Stream duration')
active_streams = Gauge('active_streams', 'Currently active streams')

# Usage in streaming code
@stream_duration.time()
async def stream_with_metrics(...):
    stream_started.inc()
    active_streams.inc()
    
    try:
        async for event in stream:
            yield event
        stream_completed.inc()
    except Exception as e:
        stream_errors.inc()
        raise
    finally:
        active_streams.dec()
```

## Best Practices

1. **Always use connection pooling** for provider clients
2. **Implement exponential backoff** for retries
3. **Set reasonable timeouts** (30s for most operations)
4. **Monitor memory usage** - streams can accumulate data
5. **Use structured logging** with correlation IDs
6. **Implement graceful shutdown** for active streams
7. **Test with slow/interrupted connections**
8. **Document event schemas** thoroughly

## Conclusion

This streaming architecture provides:

1. **Unified interface** across all LLM providers
2. **Flexible event system** for different content types
3. **Robust error handling** and recovery
4. **Performance monitoring** and optimization
5. **Scalable design** for production use

The SSE-based approach offers the best balance of simplicity, browser compatibility, and features for CF0's multi-modal streaming requirements.

### 5. Advanced Features

#### 5.1 Stream Multiplexing

```python
# apps/api-gateway/streaming/multiplexer.py
class StreamMultiplexer:
    """Handles multiple concurrent streams for complex scenarios"""
    
    async def multiplex_streams(
        self,
        primary_request: ChatRequest,
        secondary_requests: List[ChatRequest]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Run multiple streams concurrently"""
        
        # Create queues for each stream
        queues = {
            "primary": asyncio.Queue(),
            **{f"secondary_{i}": asyncio.Queue() for i in range(len(secondary_requests))}
        }
        
        # Start all streams
        tasks = []
        
        # Primary stream
        tasks.append(asyncio.create_task(
            self._run_stream(primary_request, queues["primary"], priority=1)
        ))
        
        # Secondary streams
        for i, req in enumerate(secondary_requests):
            tasks.append(asyncio.create_task(
                self._run_stream(req, queues[f"secondary_{i}"], priority=2)
            ))
        
        # Merge streams with priority
        try:
            while any(not q.empty() for q in queues.values()) or any(not t.done() for t in tasks):
                # Check primary queue first
                if not queues["primary"].empty():
                    yield await queues["primary"].get()
                
                # Then check secondary queues
                for key in queues:
                    if key != "primary" and not queues[key].empty():
                        yield await queues[key].get()
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.001)
        
        finally:
            # Cancel any remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
```

#### 5.2 Stream Caching and Replay

```python
# apps/api-gateway/streaming/cache.py
from typing import List, Optional
import time

class StreamCache:
    """Caches stream events for replay and debugging"""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, List[StreamEvent]] = {}
        self._timestamps: Dict[str, float] = {}
        self.ttl_seconds = ttl_seconds
    
    async def cache_stream(
        self,
        stream_id: str,
        stream_generator: AsyncGenerator[StreamEvent, None]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Cache events while streaming"""
        
        events = []
        self._timestamps[stream_id] = time.time()
        
        async for event in stream_generator:
            events.append(event)
            yield event
        
        self._cache[stream_id] = events
        self._cleanup_expired()
    
    async def replay_stream(
        self,
        stream_id: str,
        speed_multiplier: float = 1.0
    ) -> Optional[AsyncGenerator[StreamEvent, None]]:
        """Replay a cached stream"""
        
        if stream_id not in self._cache:
            return None
        
        events = self._cache[stream_id]
        
        async def replay_generator():
            last_timestamp = None
            
            for event in events:
                # Simulate original timing
                if last_timestamp and event.timestamp:
                    delay = (event.timestamp - last_timestamp) / 1000 / speed_multiplier
                    await asyncio.sleep(delay)
                
                yield event
                last_timestamp = event.timestamp
        
        return replay_generator()
```

#### 5.3 Stream Transformers

```python
# apps/api-gateway/streaming/transformers.py
class StreamTransformer:
    """Base class for stream transformations"""
    
    async def transform(
        self,
        stream: AsyncGenerator[StreamEvent, None]
    ) -> AsyncGenerator[StreamEvent, None]:
        async for event in stream:
            transformed = await self.process_event(event)
            if transformed:
                yield transformed
    
    async def process_event(self, event: StreamEvent) -> Optional[StreamEvent]:
        """Override in subclasses"""
        return event

class ContentFilterTransformer(StreamTransformer):
    """Filters sensitive content from streams"""
    
    def __init__(self, filter_patterns: List[str]):
        self.filter_patterns = filter_patterns
    
    async def process_event(self, event: StreamEvent) -> Optional[StreamEvent]:
        if event.type == EventType.CONTENT:
            # Filter sensitive content
            content = event.data.get("delta", "")
            for pattern in self.filter_patterns:
                content = content.replace(pattern, "[FILTERED]")
            
            event.data["delta"] = content
        
        return event

class TokenCounterTransformer(StreamTransformer):
    """Counts tokens in the stream"""
    
    def __init__(self):
        self.token_count = 0
    
    async def process_event(self, event: StreamEvent) -> Optional[StreamEvent]:
        if event.type in [EventType.CONTENT, EventType.REASONING]:
            # Rough token estimation
            content = event.data.get("delta", "") or event.data.get("content", "")
            self.token_count += len(content.split()) * 1.3
            
            # Add token count to event
            event.data["cumulative_tokens"] = int(self.token_count)
        
        return event
```

## Performance Considerations

### 1. Connection Management

```python
# apps/api-gateway/streaming/connection_manager.py
class ConnectionManager:
    """Manages SSE connections efficiently"""
    
    def __init__(self, max_connections: int = 1000):
        self.active_connections: Dict[str, EventSourceResponse] = {}
        self.max_connections = max_connections
        self._lock = asyncio.Lock()
    
    async def add_connection(self, connection_id: str, response: EventSourceResponse):
        async with self._lock:
            if len(self.active_connections) >= self.max_connections:
                # Remove oldest connection
                oldest = min(self.active_connections.items(), key=lambda x: x[1].created_at)
                await self.remove_connection(oldest[0])
            
            self.active_connections[connection_id] = response
    
    async def remove_connection(self, connection_id: str):
        async with self._lock:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
```

### 2. Rate Limiting

```python
# apps/api-gateway/streaming/rate_limiter.py
from aioredis import Redis
import time

class StreamRateLimiter:
    """Rate limits streaming requests"""
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.window_seconds = 60
        self.max_streams_per_window = 10
    
    async def check_rate_limit(self, user_id: str) -> bool:
        """Check if user can start a new stream"""
        key = f"stream_rate:{user_id}"
        current_time = int(time.time())
        window_start = current_time - self.window_seconds
        
        # Remove old entries
        await self.redis.zremrangebyscore(key, 0, window_start)
        
        # Count current streams
        stream_count = await self.redis.zcard(key)
        
        if stream_count >= self.max_streams_per_window:
            return False
        
        # Add new stream
        await self.redis.zadd(key, {str(current_time): current_time})
        await self.redis.expire(key, self.window_seconds)
        
        return True
```

### 3. Monitoring and Metrics

```python
# apps/api-gateway/streaming/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Metrics
stream_started = Counter('stream_started_total', 'Total streams started', ['provider', 'model'])
stream_completed = Counter('stream_completed_total', 'Total streams completed', ['provider', 'model'])
stream_errors = Counter('stream_errors_total', 'Total stream errors', ['provider', 'error_type'])
stream_duration = Histogram('stream_duration_seconds', 'Stream duration', ['provider', 'model'])
active_streams = Gauge('active_streams', 'Currently active streams', ['provider'])
tokens_streamed = Counter('tokens_streamed_total', 'Total tokens streamed', ['provider', 'model'])

class MetricsCollector:
    """Collects streaming metrics"""
    
    async def track_stream(
        self,
        provider: str,
        model: str,
        stream: AsyncGenerator[StreamEvent, None]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Track metrics for a stream"""
        
        start_time = time.time()
        stream_started.labels(provider=provider, model=model).inc()
        active_streams.labels(provider=provider).inc()
        
        try:
            token_count = 0
            
            async for event in stream:
                yield event
                
                # Count tokens
                if event.type in [EventType.CONTENT, EventType.REASONING]:
                    content = event.data.get("delta", "") or event.data.get("content", "")
                    token_count += len(content.split())
            
            # Success metrics
            stream_completed.labels(provider=provider, model=model).inc()
            tokens_streamed.labels(provider=provider, model=model).inc(token_count)
            
        except Exception as e:
            # Error metrics
            stream_errors.labels(provider=provider, error_type=type(e).__name__).inc()
            raise
        
        finally:
            # Duration and cleanup
            duration = time.time() - start_time
            stream_duration.labels(provider=provider, model=model).observe(duration)
            active_streams.labels(provider=provider).dec()
```

## Testing Strategy

### 1. Unit Tests

```python
# tests/test_streaming.py
import pytest
from streaming.normalizers import OpenAINormalizer, DeepSeekNormalizer

@pytest.mark.asyncio
async def test_openai_normalizer():
    normalizer = OpenAINormalizer()
    
    # Mock OpenAI chunk
    chunk = MockChunk(
        choices=[MockChoice(
            delta=MockDelta(content="Hello, world!")
        )]
    )
    
    events = normalizer.normalize(chunk)
    assert len(events) == 1
    assert events[0].type == EventType.CONTENT
    assert events[0].data["delta"] == "Hello, world!"

@pytest.mark.asyncio
async def test_streaming_orchestrator():
    orchestrator = StreamingOrchestrator("openai", "gpt-4")
    
    events = []
    async for event in orchestrator.stream_completion(
        messages=[{"role": "user", "content": "Hello"}]
    ):
        events.append(event)
    
    # Verify event sequence
    assert events[0].type == EventType.STATUS
    assert events[-1].type == EventType.DONE
```

### 2. Integration Tests

```python
# tests/test_integration.py
from httpx import AsyncClient
import asyncio

@pytest.mark.asyncio
async def test_sse_streaming():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/stream/chat",
            json={
                "provider": "openai",
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Test"}]
            },
            headers={"Accept": "text/event-stream"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"
        
        # Parse SSE events
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))
        
        assert any(e["type"] == "content" for e in events)
```

### 3. Load Testing

```javascript
// k6/streaming-load-test.js
import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const streamDuration = new Trend('stream_duration');
const firstByteTime = new Trend('first_byte_time');

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 50 },
    { duration: '30s', target: 0 },
  ],
};

export default function() {
  const start = Date.now();
  let firstByte = null;
  
  const res = http.post(
    'http://localhost:8000/stream/chat',
    JSON.stringify({
      provider: 'openai',
      model: 'gpt-4',
      messages: [{ role: 'user', content: 'Write a story' }]
    }),
    {
      headers: { 'Content-Type': 'application/json' },
      responseType: 'stream',
    }
  );
  
  // Process stream
  res.body.on('data', (chunk) => {
    if (!firstByte) {
      firstByte = Date.now();
      firstByteTime.add(firstByte - start);
    }
  });
  
  res.body.on('end', () => {
    streamDuration.add(Date.now() - start);
  });
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'has event-stream header': (r) => 
      r.headers['Content-Type'].includes('text/event-stream'),
  });
}
```

## Deployment Considerations

### 1. Reverse Proxy Configuration

```nginx
# nginx.conf
location /stream/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Cache-Control "no-cache";
    proxy_set_header X-Accel-Buffering "no";
    
    # SSE specific
    proxy_buffering off;
    proxy_read_timeout 86400;
    keepalive_timeout 86400;
}
```

### 2. CDN Considerations

- Disable caching for streaming endpoints
- Configure appropriate timeouts
- Consider using dedicated streaming infrastructure

### 3. Monitoring & Observability

```python
# apps/api-gateway/streaming/monitoring.py
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer(__name__)

class TracedOrchestrator(StreamingOrchestrator):
    """Orchestrator with OpenTelemetry tracing"""
    
    async def stream_completion(self, messages, tools=None, temperature=0.7):
        with tracer.start_as_current_span("stream_completion") as span:
            span.set_attribute("provider", self.provider)
            span.set_attribute("model", self.model)
            span.set_attribute("message_count", len(messages))
            
            try:
                async for event in super().stream_completion(messages, tools, temperature):
                    span.add_event(f"stream_event_{event.type.value}")
                    yield event
                
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
```

## Best Practices

1. **Always use connection pooling** for provider clients
2. **Implement exponential backoff** for retries
3. **Set reasonable timeouts** (30s for most operations)
4. **Monitor memory usage** - streams can accumulate data
5. **Use structured logging** with correlation IDs
6. **Implement graceful shutdown** for active streams
7. **Test with slow/interrupted connections**
8. **Document event schemas** thoroughly

## Conclusion

This streaming architecture provides:

1. **Unified interface** across all LLM providers
2. **Flexible event system** for different content types
3. **Robust error handling** and recovery
4. **Performance monitoring** and optimization
5. **Scalable design** for production use

The SSE-based approach offers the best balance of simplicity, browser compatibility, and features for CF0's multi-modal streaming requirements. 