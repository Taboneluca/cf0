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
        max_tokens: int = 20000,
        timeout_seconds: float = 120.0,
        repetition_threshold: int = 3,
        stall_timeout_seconds: float = 10.0
    ):
        self.stream = stream
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.repetition_threshold = repetition_threshold
        self.stall_timeout_seconds = stall_timeout_seconds
        
        # Internal state
        self.token_count = 0
        self.start_time = time.time()
        self.last_content_time = time.time()
        self.recent_chunks = []
        self.repetition_count = 0
    
    def __aiter__(self):
        # Changed to a non-async version - this should return self, not a coroutine
        return self
    
    async def __anext__(self):
        # Check timeout
        current_time = time.time()
        if current_time - self.start_time > self.timeout_seconds:
            print(f"⚠️ Stream timeout after {self.timeout_seconds}s")
            raise StopAsyncIteration
            
        # Check stall timeout (no new content)
        if current_time - self.last_content_time > self.stall_timeout_seconds:
            print(f"⚠️ Stream stalled - no new content for {self.stall_timeout_seconds}s")
            raise StopAsyncIteration
            
        # Check token limit
        if self.token_count >= self.max_tokens:
            print(f"⚠️ Stream reached maximum token limit ({self.max_tokens})")
            raise StopAsyncIteration
        
        try:
            # Get next chunk with timeout
            chunk = await asyncio.wait_for(
                self.stream.__anext__(), 
                timeout=self.stall_timeout_seconds
            )
            
            # Extract content for analysis
            content = ""
            if hasattr(chunk, "content") and chunk.content:
                content = chunk.content
                
            # Calculate rough token count (simple approximation)
            if content:
                # Reset stall timer
                self.last_content_time = time.time()
                
                # Count tokens (rough approximation: 4 chars = 1 token)
                self.token_count += len(content) // 4
                
                # Check for repetition
                if content in self.recent_chunks:
                    self.repetition_count += 1
                    if self.repetition_count >= self.repetition_threshold:
                        print(f"⚠️ Detected content repetition in stream")
                        raise StopAsyncIteration
                else:
                    self.repetition_count = 0
                    
                # Update recent chunks (sliding window)
                self.recent_chunks = (self.recent_chunks + [content])[-5:]
            
            return chunk
            
        except (StopAsyncIteration, asyncio.TimeoutError):
            print(f"🏁 Stream completed or timed out after {time.time() - self.start_time:.2f}s")
            raise StopAsyncIteration

def wrap_stream_with_guard(stream: AsyncGenerator) -> AsyncGenerator:
    """
    Wrap an async generator stream with protection against infinite loops.
    
    Args:
        stream: The original async generator stream
        
    Returns:
        Protected async generator with safeguards
    """
    return StreamGuard(stream)

# Ensure all exports are explicitly defined
__all__ = ["StreamGuard", "wrap_stream_with_guard"] 