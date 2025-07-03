# Streaming Architecture Recommendations
*Generated: January 2025*

## Executive Summary

This document provides comprehensive recommendations for implementing efficient streaming of chat completions and tool calls while supporting multi-model selection across Anthropic, OpenAI, and Groq providers. The current implementation has a solid foundation but requires architectural improvements to achieve optimal performance, reliability, and maintainability.

## Current Architecture Analysis

### Streaming Pipeline Overview

```
Frontend (React) → API Gateway → LangServe → LLM Provider → Response Stream
                         ↓
                  Model Selection
                   (Factory Pattern)
```

### Current Implementation Strengths

1. **Working SSE Implementation**: Proper Server-Sent Events format
2. **Model Flexibility**: Factory pattern for provider selection
3. **Agentic Framework**: Orchestrator, reviewer, and tool execution
4. **Latency Optimization**: LiveMind-style incomplete prompt processing

### Critical Weaknesses

1. **No Unified Streaming Interface**: Each provider has different streaming APIs
2. **Inefficient Buffer Management**: Multiple JSON parse/stringify operations
3. **Sequential Tool Execution**: No parallelization of independent tools
4. **Missing Stream Control**: No pause, resume, or cancellation
5. **Provider-Specific Handling**: Hardcoded logic for each provider

## Recommended Streaming Architecture

### 1. Unified Streaming Interface

Create a provider-agnostic streaming interface that normalizes differences between providers:

```python
# streaming/interfaces.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, Optional
import asyncio

class StreamProvider(ABC):
    """Base interface for all streaming providers"""
    
    @abstractmethod
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        """Stream completion with optional tool support"""
        pass
    
    @abstractmethod
    async def cancel_stream(self, stream_id: str) -> bool:
        """Cancel an ongoing stream"""
        pass

class StreamEvent:
    """Unified stream event format"""
    def __init__(
        self,
        type: str,  # 'text', 'tool_call', 'tool_result', 'error', 'done'
        content: Optional[str] = None,
        tool_call: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ):
        self.type = type
        self.content = content
        self.tool_call = tool_call
        self.metadata = metadata or {}
        self.timestamp = asyncio.get_event_loop().time()
```

### 2. Provider Implementations

Implement the unified interface for each provider:

```python
# streaming/providers/anthropic.py
from anthropic import AsyncAnthropic
from typing import AsyncIterator
import json

class AnthropicStreamProvider(StreamProvider):
    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)
        self.active_streams = {}
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        model: str = "claude-3-7-sonnet",
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        stream_id = generate_stream_id()
        
        try:
            # Create Anthropic-specific request
            request = {
                "model": model,
                "messages": messages,
                "stream": True,
                "max_tokens": kwargs.get("max_tokens", 4096)
            }
            
            if tools:
                request["tools"] = self._convert_tools_to_anthropic(tools)
            
            # Start streaming
            stream = await self.client.messages.create(**request)
            self.active_streams[stream_id] = stream
            
            # Convert Anthropic events to unified format
            async for event in stream:
                if stream_id not in self.active_streams:
                    break  # Stream was cancelled
                
                yield self._convert_event(event)
                
        finally:
            self.active_streams.pop(stream_id, None)
    
    def _convert_event(self, event) -> StreamEvent:
        """Convert Anthropic event to unified format"""
        if event.type == "content_block_delta":
            return StreamEvent(
                type="text",
                content=event.delta.text
            )
        elif event.type == "tool_use":
            return StreamEvent(
                type="tool_call",
                tool_call={
                    "id": event.id,
                    "name": event.name,
                    "arguments": event.input
                }
            )
        # ... handle other event types
```

```python
# streaming/providers/openai.py
from openai import AsyncOpenAI
import json

class OpenAIStreamProvider(StreamProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        model: str = "gpt-4o",
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        
        # OpenAI streaming with tool support
        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            stream=True,
            stream_options={"include_usage": True}
        )
        
        current_tool_call = None
        
        async for chunk in stream:
            delta = chunk.choices[0].delta
            
            # Handle text content
            if delta.content:
                yield StreamEvent(type="text", content=delta.content)
            
            # Handle tool calls
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    if tool_call.id:  # New tool call
                        if current_tool_call:
                            yield StreamEvent(
                                type="tool_call",
                                tool_call=current_tool_call
                            )
                        current_tool_call = {
                            "id": tool_call.id,
                            "name": tool_call.function.name,
                            "arguments": ""
                        }
                    
                    if tool_call.function.arguments:
                        current_tool_call["arguments"] += tool_call.function.arguments
        
        # Yield final tool call if exists
        if current_tool_call:
            current_tool_call["arguments"] = json.loads(current_tool_call["arguments"])
            yield StreamEvent(type="tool_call", tool_call=current_tool_call)
        
        yield StreamEvent(type="done")
```

### 3. Stream Orchestrator

Implement a smart orchestrator that handles provider selection, failover, and stream management:

```python
# streaming/orchestrator.py
from typing import Dict, List, Optional, AsyncIterator
import asyncio
from .interfaces import StreamProvider, StreamEvent

class StreamOrchestrator:
    def __init__(self):
        self.providers: Dict[str, StreamProvider] = {}
        self.model_mapping = {
            "gpt-4o": "openai",
            "claude-3-7-sonnet": "anthropic",
            "llama-3-3-70b": "groq"
        }
        self.fallback_chain = {
            "openai": "anthropic",
            "anthropic": "groq",
            "groq": "openai"
        }
    
    def register_provider(self, name: str, provider: StreamProvider):
        self.providers[name] = provider
    
    async def stream_with_model(
        self,
        model: str,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        """Stream with automatic provider selection and failover"""
        
        # Determine primary provider
        provider_name = self._get_provider_for_model(model)
        
        # Try primary provider
        try:
            async for event in self._stream_with_provider(
                provider_name, model, messages, tools, **kwargs
            ):
                yield event
                
        except Exception as e:
            # Log error
            yield StreamEvent(
                type="error",
                content=f"Primary provider {provider_name} failed: {str(e)}"
            )
            
            # Try fallback provider
            fallback = self.fallback_chain.get(provider_name)
            if fallback and fallback in self.providers:
                # Map model to fallback provider's equivalent
                fallback_model = self._map_model_to_provider(model, fallback)
                
                yield StreamEvent(
                    type="error",
                    content=f"Switching to {fallback} with {fallback_model}"
                )
                
                async for event in self._stream_with_provider(
                    fallback, fallback_model, messages, tools, **kwargs
                ):
                    yield event
    
    async def _stream_with_provider(
        self,
        provider_name: str,
        model: str,
        messages: List[Dict],
        tools: Optional[List[Dict]],
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        """Stream with specific provider"""
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not registered")
        
        async for event in provider.stream_completion(
            messages, tools, model=model, **kwargs
        ):
            # Add provider metadata
            event.metadata["provider"] = provider_name
            event.metadata["model"] = model
            yield event
```

### 4. Efficient Buffer Management

Implement zero-copy buffering and efficient stream processing:

```python
# streaming/buffer.py
import asyncio
from collections import deque
from typing import Optional, AsyncIterator
import time

class StreamBuffer:
    """Efficient buffer for streaming with backpressure"""
    
    def __init__(self, max_size: int = 1000, max_age_ms: int = 100):
        self.buffer = deque(maxlen=max_size)
        self.max_age_ms = max_age_ms
        self.last_flush = time.time() * 1000
        self.lock = asyncio.Lock()
        self.not_empty = asyncio.Condition(self.lock)
        self.closed = False
    
    async def write(self, event: StreamEvent) -> bool:
        """Write event to buffer, returns False if buffer is full"""
        async with self.lock:
            if self.closed:
                return False
            
            if len(self.buffer) >= self.buffer.maxlen:
                return False  # Apply backpressure
            
            self.buffer.append(event)
            self.not_empty.notify()
            
            # Check if we should flush based on time
            current_time = time.time() * 1000
            if current_time - self.last_flush > self.max_age_ms:
                self.not_empty.notify_all()
                
            return True
    
    async def read_batch(self, max_items: int = 10) -> List[StreamEvent]:
        """Read a batch of events from buffer"""
        async with self.lock:
            # Wait for items or timeout
            try:
                await asyncio.wait_for(
                    self.not_empty.wait_for(lambda: len(self.buffer) > 0 or self.closed),
                    timeout=self.max_age_ms / 1000
                )
            except asyncio.TimeoutError:
                pass
            
            # Collect batch
            batch = []
            for _ in range(min(max_items, len(self.buffer))):
                batch.append(self.buffer.popleft())
            
            self.last_flush = time.time() * 1000
            return batch
    
    async def close(self):
        """Close the buffer"""
        async with self.lock:
            self.closed = True
            self.not_empty.notify_all()
```

### 5. Parallel Tool Execution

Implement efficient parallel tool execution with dependency analysis:

```python
# streaming/tools.py
from typing import List, Dict, Set, Any
import asyncio
import networkx as nx

class ToolExecutor:
    """Execute tools in parallel with dependency resolution"""
    
    def __init__(self, tool_registry: Dict[str, callable]):
        self.tool_registry = tool_registry
        self.execution_cache = {}
    
    async def execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> AsyncIterator[StreamEvent]:
        """Execute tool calls in parallel when possible"""
        
        # Build dependency graph
        graph = self._build_dependency_graph(tool_calls)
        
        # Execute in topological order with parallelization
        for level in nx.topological_generations(graph):
            # Execute all tools in this level in parallel
            tasks = []
            for tool_id in level:
                tool_call = next(tc for tc in tool_calls if tc["id"] == tool_id)
                task = self._execute_single_tool(tool_call)
                tasks.append((tool_id, task))
            
            # Wait for all tools in this level
            results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True
            )
            
            # Yield results as they complete
            for (tool_id, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    yield StreamEvent(
                        type="tool_result",
                        tool_call={"id": tool_id, "error": str(result)}
                    )
                else:
                    yield StreamEvent(
                        type="tool_result",
                        tool_call={"id": tool_id, "result": result}
                    )
    
    def _build_dependency_graph(self, tool_calls: List[Dict]) -> nx.DiGraph:
        """Build dependency graph based on tool inputs/outputs"""
        graph = nx.DiGraph()
        
        for tool_call in tool_calls:
            graph.add_node(tool_call["id"])
            
            # Analyze dependencies based on arguments
            args = tool_call.get("arguments", {})
            for arg_value in args.values():
                if isinstance(arg_value, str) and arg_value.startswith("$"):
                    # Reference to another tool's output
                    ref_tool_id = arg_value[1:]  # Remove $
                    if ref_tool_id in [tc["id"] for tc in tool_calls]:
                        graph.add_edge(ref_tool_id, tool_call["id"])
        
        return graph
    
    async def _execute_single_tool(self, tool_call: Dict) -> Any:
        """Execute a single tool with caching"""
        tool_name = tool_call["name"]
        args = tool_call["arguments"]
        
        # Check cache
        cache_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        if cache_key in self.execution_cache:
            return self.execution_cache[cache_key]
        
        # Execute tool
        tool_func = self.tool_registry.get(tool_name)
        if not tool_func:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        result = await tool_func(**args)
        
        # Cache result
        self.execution_cache[cache_key] = result
        return result
```

### 6. Client-Side Stream Handler

Implement an efficient client-side handler with proper error recovery:

```typescript
// frontend/lib/streaming.ts
import { EventSourcePolyfill } from 'event-source-polyfill';

interface StreamConfig {
  onText?: (text: string) => void;
  onToolCall?: (tool: ToolCall) => void;
  onToolResult?: (result: ToolResult) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
}

class StreamingClient {
  private abortController: AbortController | null = null;
  private reconnectAttempts = 0;
  private maxReconnects = 3;
  private buffer: string[] = [];
  private flushInterval: number | null = null;
  
  async streamCompletion(
    endpoint: string,
    request: ChatRequest,
    config: StreamConfig
  ): Promise<void> {
    // Cancel any existing stream
    this.cancel();
    
    this.abortController = new AbortController();
    this.buffer = [];
    
    // Start flush interval for smooth rendering
    this.flushInterval = window.setInterval(() => {
      this.flushBuffer(config);
    }, 50); // Flush every 50ms
    
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(request),
        signal: this.abortController.signal,
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      // Process stream
      await this.processStream(response.body!, config);
      
    } catch (error) {
      if (error.name !== 'AbortError') {
        // Attempt reconnection for network errors
        if (this.reconnectAttempts < this.maxReconnects) {
          this.reconnectAttempts++;
          await this.delay(1000 * this.reconnectAttempts);
          return this.streamCompletion(endpoint, request, config);
        }
        
        config.onError?.(error);
      }
    } finally {
      this.cleanup();
    }
  }
  
  private async processStream(
    stream: ReadableStream<Uint8Array>,
    config: StreamConfig
  ): Promise<void> {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              this.flushBuffer(config);
              config.onDone?.();
              return;
            }
            
            try {
              const event = JSON.parse(data);
              this.handleEvent(event, config);
            } catch (e) {
              console.error('Failed to parse SSE event:', e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }
  
  private handleEvent(event: StreamEvent, config: StreamConfig): void {
    switch (event.type) {
      case 'text':
        // Buffer text for smooth rendering
        this.buffer.push(event.content);
        break;
        
      case 'tool_call':
        this.flushBuffer(config);
        config.onToolCall?.(event.tool_call);
        break;
        
      case 'tool_result':
        config.onToolResult?.(event.tool_call);
        break;
        
      case 'error':
        config.onError?.(new Error(event.content));
        break;
    }
  }
  
  private flushBuffer(config: StreamConfig): void {
    if (this.buffer.length > 0) {
      const text = this.buffer.join('');
      this.buffer = [];
      config.onText?.(text);
    }
  }
  
  private cleanup(): void {
    if (this.flushInterval) {
      clearInterval(this.flushInterval);
      this.flushInterval = null;
    }
    this.abortController = null;
    this.reconnectAttempts = 0;
  }
  
  cancel(): void {
    this.abortController?.abort();
    this.cleanup();
  }
  
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export default StreamingClient;
```

## Integration with Current Architecture

### 1. Minimal Changes Approach

To integrate with the current codebase while maintaining the agentic framework:

```python
# api/streaming_adapter.py
from typing import AsyncIterator
from .router import process_message_streaming
from streaming.orchestrator import StreamOrchestrator
from streaming.interfaces import StreamEvent

class AgenticStreamAdapter:
    """Adapter to integrate new streaming with existing agent framework"""
    
    def __init__(self, orchestrator: StreamOrchestrator):
        self.orchestrator = orchestrator
    
    async def stream_with_agents(
        self,
        mode: str,
        message: str,
        wid: str,
        sid: str,
        model: str,
        contexts: List[str] = []
    ) -> AsyncIterator[Dict]:
        """Adapt new streaming to existing agent framework"""
        
        # Use existing process_message_streaming for agent logic
        agent_stream = process_message_streaming(
            mode, message, wid, sid, 
            model=model, 
            workbook_metadata={"contexts": contexts}
        )
        
        # Process agent events and convert to new format
        async for chunk in agent_stream:
            if isinstance(chunk, dict):
                # Convert agent events to StreamEvent
                if chunk.get("type") == "chunk":
                    yield StreamEvent(
                        type="text",
                        content=chunk.get("text", "")
                    )
                elif chunk.get("type") == "update":
                    # Tool execution result
                    yield StreamEvent(
                        type="tool_result",
                        tool_call=chunk.get("payload")
                    )
                else:
                    # Pass through other events
                    yield chunk
```

### 2. Gradual Migration Path

Phase 1: Implement streaming providers and orchestrator alongside existing code
Phase 2: Create adapter layer to use new streaming with existing agents
Phase 3: Migrate agent framework to use new streaming natively
Phase 4: Remove legacy streaming code

## Performance Optimizations

### 1. Stream Compression

For large responses, implement compression:

```python
# streaming/compression.py
import zlib
import base64

class CompressedStream:
    def __init__(self, compression_threshold: int = 1024):
        self.compression_threshold = compression_threshold
        self.compressor = zlib.compressobj()
    
    async def compress_event(self, event: StreamEvent) -> StreamEvent:
        """Compress large events"""
        if event.type == "text" and len(event.content) > self.compression_threshold:
            compressed = self.compressor.compress(event.content.encode())
            compressed += self.compressor.flush(zlib.Z_SYNC_FLUSH)
            
            event.content = base64.b64encode(compressed).decode()
            event.metadata["compressed"] = True
            
        return event
```

### 2. Connection Pooling

Implement provider-specific connection pools:

```python
# streaming/pools.py
from typing import Dict, Optional
import asyncio
import aiohttp

class ProviderConnectionPool:
    def __init__(self, max_connections: int = 10):
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
        self.max_connections = max_connections
    
    async def get_session(self, provider: str) -> aiohttp.ClientSession:
        """Get or create session for provider"""
        if provider not in self.sessions:
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                ttl_dns_cache=300
            )
            self.sessions[provider] = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=300)
            )
            self.semaphores[provider] = asyncio.Semaphore(self.max_connections)
        
        return self.sessions[provider]
    
    async def close_all(self):
        """Close all sessions"""
        for session in self.sessions.values():
            await session.close()
```

## Monitoring and Observability

### 1. Stream Metrics

Implement comprehensive metrics collection:

```python
# streaming/metrics.py
from dataclasses import dataclass
from typing import Dict
import time

@dataclass
class StreamMetrics:
    provider: str
    model: str
    start_time: float
    first_token_time: Optional[float] = None
    end_time: Optional[float] = None
    token_count: int = 0
    tool_calls: int = 0
    errors: int = 0
    
    @property
    def time_to_first_token(self) -> Optional[float]:
        if self.first_token_time:
            return self.first_token_time - self.start_time
        return None
    
    @property
    def total_duration(self) -> Optional[float]:
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def tokens_per_second(self) -> Optional[float]:
        duration = self.total_duration
        if duration and duration > 0:
            return self.token_count / duration
        return None

class MetricsCollector:
    def __init__(self):
        self.active_streams: Dict[str, StreamMetrics] = {}
        self.completed_streams: List[StreamMetrics] = []
    
    def start_stream(self, stream_id: str, provider: str, model: str):
        self.active_streams[stream_id] = StreamMetrics(
            provider=provider,
            model=model,
            start_time=time.time()
        )
    
    def record_first_token(self, stream_id: str):
        if stream_id in self.active_streams:
            metrics = self.active_streams[stream_id]
            if not metrics.first_token_time:
                metrics.first_token_time = time.time()
    
    def end_stream(self, stream_id: str):
        if stream_id in self.active_streams:
            metrics = self.active_streams.pop(stream_id)
            metrics.end_time = time.time()
            self.completed_streams.append(metrics)
```

### 2. Error Tracking

Implement comprehensive error tracking:

```python
# streaming/errors.py
from enum import Enum
from typing import Optional, Dict, Any
import traceback

class StreamErrorType(Enum):
    PROVIDER_ERROR = "provider_error"
    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    INVALID_REQUEST = "invalid_request"
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"

class StreamError:
    def __init__(
        self,
        error_type: StreamErrorType,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        self.error_type = error_type
        self.message = message
        self.provider = provider
        self.model = model
        self.details = details or {}
        self.recoverable = recoverable
        self.timestamp = time.time()
        self.traceback = traceback.format_exc()
    
    def to_event(self) -> StreamEvent:
        return StreamEvent(
            type="error",
            content=self.message,
            metadata={
                "error_type": self.error_type.value,
                "provider": self.provider,
                "model": self.model,
                "recoverable": self.recoverable,
                "details": self.details
            }
        )
```

## Testing Strategy

### 1. Provider Mock

Create mocks for testing:

```python
# tests/mocks/stream_provider.py
from streaming.interfaces import StreamProvider, StreamEvent
from typing import AsyncIterator, List, Dict

class MockStreamProvider(StreamProvider):
    def __init__(self, responses: List[StreamEvent]):
        self.responses = responses
        self.call_count = 0
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        self.call_count += 1
        
        for response in self.responses:
            await asyncio.sleep(0.01)  # Simulate network delay
            yield response
        
        yield StreamEvent(type="done")
    
    async def cancel_stream(self, stream_id: str) -> bool:
        return True
```

### 2. Integration Tests

Test the complete streaming pipeline:

```python
# tests/test_streaming_integration.py
import pytest
import asyncio

@pytest.mark.asyncio
async def test_multi_provider_failover():
    """Test failover between providers"""
    orchestrator = StreamOrchestrator()
    
    # Register mock providers
    failing_provider = MockStreamProvider([])
    failing_provider.stream_completion = AsyncMock(
        side_effect=Exception("Provider failed")
    )
    
    working_provider = MockStreamProvider([
        StreamEvent(type="text", content="Hello"),
        StreamEvent(type="text", content=" world!")
    ])
    
    orchestrator.register_provider("primary", failing_provider)
    orchestrator.register_provider("fallback", working_provider)
    
    # Configure failover
    orchestrator.fallback_chain["primary"] = "fallback"
    
    # Stream should failover to working provider
    events = []
    async for event in orchestrator.stream_with_model(
        "gpt-4", [{"role": "user", "content": "Hi"}]
    ):
        events.append(event)
    
    # Verify failover occurred
    assert any(e.type == "error" for e in events)
    assert any(e.content == "Hello world!" for e in events)
```

## Conclusion

This streaming architecture provides:

1. **Unified Interface**: Single API for all providers
2. **High Performance**: Zero-copy buffers, parallel tools
3. **Reliability**: Automatic failover, error recovery
4. **Flexibility**: Easy to add new providers
5. **Observability**: Comprehensive metrics and monitoring

The architecture maintains compatibility with the existing agentic framework while providing a clear path for modernization and performance improvements. By implementing these recommendations, the system will be well-positioned to handle high-throughput streaming across multiple providers with optimal performance and reliability.