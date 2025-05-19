import time
import asyncio
from typing import AsyncGenerator, Any, List, Dict, Optional

class StreamGuard:
    """
    Robust protection against infinite streaming loops.
    Wraps an async generator and implements multiple safeguards:
    1. Maximum token limit
    2. Timeout
    3. Repetition detection
    4. Stall detection (no new content for a period)
    """
    
    def __init__(
        self, 
        stream: AsyncGenerator,
        max_tokens: Optional[int] = None,  # None disables token limit
        timeout_seconds: float = 120.0,
        repetition_threshold: int = 3,
        stall_timeout_seconds: float = 60.0  # Increased from 10.0 to 60.0
    ):
        self.stream = stream
        # None == "no hard cap"
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.repetition_threshold = repetition_threshold
        self.stall_timeout_seconds = stall_timeout_seconds
        
        # Tracking state
        self.start_time = time.time()
        self.last_yield_time = time.time()
        self.token_count = 0
        self.cumulative_content = ""  # Track all content to avoid double-counting
        self.repetition_count = 0
        self.last_content = None
    
    async def __aiter__(self):
        return self
    
    async def __anext__(self):
        try:
            # 1. Check if we've timed out
            if time.time() - self.start_time > self.timeout_seconds:
                print(f"⚠️ Stream reached maximum time limit of {self.timeout_seconds}s")
                raise StopAsyncIteration
                
            # 2. Check if we've received no content for a while (stall detection)
            stall_time = time.time() - self.last_yield_time
            if stall_time > self.stall_timeout_seconds:
                print(f"⚠️ Stream stalled - no new content for {stall_time:.1f}s")
                raise StopAsyncIteration
            
            # Get the next chunk from the stream
            chunk = await self.stream.__anext__()
            self.last_yield_time = time.time()
            
            # Count tokens only for text content
            content_to_count = None
            if isinstance(chunk, str):
                content_to_count = chunk
            elif hasattr(chunk, "content") and chunk.content:
                content_to_count = chunk.content
            
            # Process content for token counting and repetition detection
            if content_to_count:
                # Only count new content by tracking cumulative content
                # This prevents double-counting when a provider repeats content
                new_content_length = len(content_to_count)
                if content_to_count in self.cumulative_content:
                    # Content already seen, don't count again
                    new_tokens = 0
                else:
                    # For simplicity: approximate 1 token ≈ 4 chars
                    new_tokens = (new_content_length + 3) // 4
                    self.cumulative_content += content_to_count
                
                self.token_count += new_tokens
                
                # 3. Check if we've reached the maximum token limit (if enabled)
                if self.max_tokens is not None and self.token_count > self.max_tokens:
                    print(f"⚠️ Stream reached maximum token limit of {self.max_tokens}")
                    raise StopAsyncIteration
                
                # 4. Check for exact repetition (same content multiple times)
                if content_to_count == self.last_content:
                    self.repetition_count += 1
                    if self.repetition_count >= self.repetition_threshold:
                        print(f"⚠️ Stream repeated the same content {self.repetition_count} times")
                        raise StopAsyncIteration
                else:
                    self.repetition_count = 0
                    self.last_content = content_to_count
            
            return chunk
            
        except StopAsyncIteration:
            elapsed = time.time() - self.start_time
            print(f"⏹️ StreamGuard completed after {elapsed:.2f}s and ~{self.token_count} tokens")
            raise

async def wrap_stream_with_guard(stream: AsyncGenerator, max_tokens: Optional[int] = None) -> AsyncGenerator:
    """
    Wrap a stream with guard rails to prevent infinite generation.
    
    Args:
        stream: The async generator to wrap
        max_tokens: Optional maximum number of tokens to generate
        
    Returns:
        A wrapped async generator with guard rails
    """
    guard = StreamGuard(stream, max_tokens=max_tokens)
    async for chunk in guard:
        yield chunk

# Ensure all exports are explicitly defined
__all__ = ["StreamGuard", "wrap_stream_with_guard"] 