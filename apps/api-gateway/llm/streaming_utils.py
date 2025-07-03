import time
import asyncio
import os  # Add os import for environment variables
from typing import AsyncGenerator, Any, List, Dict, Optional
import re  # Add import for regex

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
        
        # For smoothing out streaming
        self._remainder_queue = []
    
    def __aiter__(self):
        # Return self directly, not as a coroutine
        return self
    
    async def __anext__(self):
        try:
            # Check if we have any remainder chunks from previous processing
            if self._remainder_queue:
                chunk = self._remainder_queue.pop(0)
                if DEBUG_CHUNKING:
                    print(f"🔄 Yielding queued remainder chunk: {chunk[:30]}...")
                return chunk
            
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
                # Look for natural break points: periods, question marks, exclamation marks, or newlines
                if re.search(r'[.!?]|\n', chunk):
                    # Split on sentence boundaries or newlines, preserving the delimiters
                    parts = []
                    # First, split by newlines to preserve paragraph structure
                    paragraphs = chunk.split('\n')
                    for paragraph in paragraphs:
                        # If paragraph is empty, just add the newline
                        if not paragraph:
                            parts.append('\n')
                            continue
                        
                        # Then split each paragraph by sentence
                        sentences = re.split(r'([.!?])', paragraph)
                        i = 0
                        while i < len(sentences) - 1:
                            # Combine the sentence content with its delimiter
                            if i + 1 < len(sentences):
                                # Add the sentence with its punctuation
                                sentence = sentences[i] + sentences[i+1]
                                if sentence:  # Only add non-empty strings
                                    parts.append(sentence)
                                i += 2
                            else:
                                # Handle odd-length arrays (though this shouldn't happen)
                                if sentences[i]:  # Only add non-empty strings
                                    parts.append(sentences[i])
                                i += 1
                        
                        # Add newline after paragraph if not the last paragraph
                        if paragraph != paragraphs[-1]:
                            parts.append('\n')
                    
                    # Filter out empty parts and ensure we have at least one part
                    parts = [p for p in parts if p]
                    if not parts:
                        parts = [chunk]  # Fallback to original if splitting failed
                    
                    if DEBUG_CHUNKING:
                        print(f"🔍 Split chunk #{self.chunk_counter} into {len(parts)} smaller parts")
                    
                    # Return just the first part and queue the rest
                    first_part = parts[0]
                    # Store the remaining parts for later processing
                    self._remainder_queue = parts[1:]
                    chunk = first_part
                else:
                    # If no sentence boundaries, split into smaller chunks by characters
                    # This ensures even large paragraphs get streamed smoothly
                    if len(chunk) > 100:
                        # Split into roughly 50-character chunks at word boundaries
                        parts = []
                        remaining = chunk
                        while remaining and len(remaining) > 50:
                            # Find a word boundary near the 50-character mark
                            cut_point = remaining[:50].rfind(' ')
                            if cut_point <= 0:  # No space found or at position 0
                                cut_point = 50  # Just cut at 50 if no good word boundary
                            
                            parts.append(remaining[:cut_point+1])
                            remaining = remaining[cut_point+1:]
                        
                        if remaining:  # Add any remaining text
                            parts.append(remaining)
                        
                        if DEBUG_CHUNKING:
                            print(f"🔍 Split large chunk #{self.chunk_counter} into {len(parts)} word breaks")
                        
                        # Return first part and queue the rest
                        first_part = parts[0]
                        self._remainder_queue = parts[1:]
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
        while guard._remainder_queue:
            remainder_chunk = guard._remainder_queue.pop(0)
            if DEBUG_CHUNKING:
                print(f"🔄 Yielding remainder chunk: {remainder_chunk[:20]}...")
            yield remainder_chunk

# Ensure all exports are explicitly defined
__all__ = ["StreamGuard", "wrap_stream_with_guard"] 