import time
import asyncio
import os  # Add os import for environment variables
from typing import AsyncGenerator, Any, List, Dict, Optional

# Debug flag to enable detailed tracing of chunk flow
DEBUG_CHUNKING = os.getenv("DEBUG_CHUNKING", "0") == "1"

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
        
        # For debugging purposes, track chunks
        self.chunk_counter = 0
    
    def __aiter__(self):
        # Return self directly, not as a coroutine
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
            self.chunk_counter += 1
            
            if DEBUG_CHUNKING:
                chunk_type = type(chunk).__name__
                content_preview = ""
                if isinstance(chunk, str):
                    content_preview = chunk[:20]
                elif hasattr(chunk, "content") and chunk.content:
                    content_preview = str(chunk.content)[:20]
                print(f"🔍 StreamGuard chunk #{self.chunk_counter}: {chunk_type}, preview: {content_preview}...")
            
            # Break down larger text chunks into smaller ones for smoother streaming
            if isinstance(chunk, str) and len(chunk) > 20:
                # Split long text into sentences or smaller chunks for smoother streaming
                if '.' in chunk or '\n' in chunk:
                    # Try to split on sentence boundaries or newlines
                    parts = []
                    for part in chunk.replace('\n', '.\n').split('.'):
                        if part:
                            parts.append(part + ('.' if not part.endswith('\n') else ''))
                    
                    if DEBUG_CHUNKING:
                        print(f"🔍 Split chunk #{self.chunk_counter} into {len(parts)} smaller parts")
                    
                    # Return just the first part and queue the rest
                    first_part = parts[0]
                    # Store the remaining parts for later processing
                    self._remainder = parts[1:]
                    chunk = first_part
            
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
        if DEBUG_CHUNKING:
            chunk_type = type(chunk).__name__
            content_preview = ""
            if isinstance(chunk, str):
                content_preview = chunk[:20]
            elif hasattr(chunk, "content") and chunk.content:
                content_preview = str(chunk.content)[:20]
            print(f"🔄 wrap_stream_with_guard yielding: {chunk_type}, preview: {content_preview}...")
            
        yield chunk

        # If we have remainder chunks from splitting, yield them too
        if hasattr(guard, '_remainder') and guard._remainder:
            for remainder_chunk in guard._remainder:
                if DEBUG_CHUNKING:
                    print(f"🔄 Yielding remainder chunk: {remainder_chunk[:20]}...")
                yield remainder_chunk
            # Clear the remainder after yielding
            guard._remainder = []

# Ensure all exports are explicitly defined
__all__ = ["StreamGuard", "wrap_stream_with_guard"] 