"""
SSE (Server-Sent Events) handler for streaming responses.
Converts agent streaming output to SSE format.
"""

import json
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime
from fastapi import Request
from sse_starlette.sse import EventSourceResponse

from api.schemas import ChatRequest
from agents.base_agent import ChatStep
from agents.ask_agent import build as build_ask_agent
from agents.analyst_agent import build as build_analyst_agent
from spreadsheet_engine.summary import sheet_summary
from workbook_store import get_sheet, get_workbook
from api.memory import get_history
from api.router import process_message_streaming
from llm.factory import get_client, get_default_client
from streaming.event_types import EventType, StreamEvent


class StreamingHandler:
    """Handles conversion of agent streaming to SSE format."""
    
    def __init__(self):
        self.heartbeat_interval = 30  # seconds
    
    async def stream_response(
        self, 
        request: Request, 
        chat_request: ChatRequest
    ) -> EventSourceResponse:
        """
        Stream chat responses in SSE format.
        
        Args:
            request: FastAPI request object
            chat_request: The chat request containing message, model, etc.
            
        Returns:
            EventSourceResponse for SSE streaming
        """
        return EventSourceResponse(
            self._event_generator(chat_request),
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable Nginx buffering
            }
        )
    
    async def _event_generator(
        self, 
        chat_request: ChatRequest
    ) -> AsyncGenerator[str, None]:
        """Generate SSE events from agent streaming."""
        heartbeat_task = None
        heartbeat_queue = asyncio.Queue()
        
        try:
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self._heartbeat_generator(heartbeat_queue)
            )
            
            # Send initial status event
            yield StreamEvent(
                type=EventType.STATUS,
                data={
                    "status": "starting",
                    "model": chat_request.model,
                    "mode": getattr(chat_request, 'mode', 'ask')
                }
            ).to_sse()
            
            # Process the streaming response
            # Call process_message_streaming with all required parameters
            mode = getattr(chat_request, 'mode', 'ask')
            chunk_count = 0
            async for chunk in process_message_streaming(
                mode=mode,
                message=chat_request.message,
                wid=chat_request.wid,
                sid=chat_request.sid,
                model=chat_request.model
            ):
                chunk_count += 1
                print(f"[SSE] Chunk #{chunk_count}: Type={type(chunk).__name__}, Value={repr(chunk)[:100]}")
                
                # Check for heartbeat events
                try:
                    heartbeat = heartbeat_queue.get_nowait()
                    yield heartbeat
                except asyncio.QueueEmpty:
                    pass
                
                # Convert legacy streaming format to SSE events
                if hasattr(chunk, 'role'):  # ChatStep object
                    print(f"[SSE] Converting ChatStep: role={chunk.role}, content={chunk.content}, toolCall={chunk.toolCall}, toolResult={chunk.toolResult}")
                    event = self._convert_legacy_chunk(chunk)
                    if event:
                        print(f"[SSE] Generated event: {event.type.value}")
                        yield event.to_sse()
                    else:
                        print(f"[SSE] No event generated from ChatStep")
                elif isinstance(chunk, dict):
                    print(f"[SSE] Converting dict chunk: {list(chunk.keys())}")
                    event = self._convert_legacy_chunk(chunk)
                    if event:
                        yield event.to_sse()
                elif isinstance(chunk, str):
                    print(f"[SSE] String chunk: {repr(chunk)}")
                    # Plain text content
                    yield StreamEvent(
                        type=EventType.CONTENT,
                        data={"delta": chunk}
                    ).to_sse()
                else:
                    print(f"[SSE] Unknown chunk type: {type(chunk)}")
                
                # Small delay to prevent overwhelming client
                await asyncio.sleep(0.001)
            
            # Send completion event
            yield StreamEvent(
                type=EventType.DONE,
                data={"status": "completed"}
            ).to_sse()
            
        except Exception as e:
            # Send error event
            yield StreamEvent(
                type=EventType.ERROR,
                data={
                    "error": str(e),
                    "code": "STREAM_ERROR",
                    "recoverable": True
                }
            ).to_sse()
        
        finally:
            # Clean up heartbeat task
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
    
    async def _heartbeat_generator(self, queue: asyncio.Queue) -> None:
        """Generate periodic heartbeat events."""
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            heartbeat = StreamEvent(
                type=EventType.HEARTBEAT,
                data={"status": "alive"}
            ).to_sse()
            await queue.put(heartbeat)
    
    def _convert_legacy_chunk(self, chunk: Dict[str, Any]) -> Optional[StreamEvent]:
        """Convert legacy streaming chunk to StreamEvent."""
        # Handle ChatStep objects
        if hasattr(chunk, 'role'):
            # This is a ChatStep object
            if chunk.toolCall:
                return StreamEvent(
                    type=EventType.TOOL_CALL,
                    data={
                        "tool": chunk.toolCall.get("name", "unknown"),
                        "arguments": chunk.toolCall.get("arguments", {}),
                        "id": chunk.toolCall.get("id", None)
                    }
                )
            elif chunk.toolResult is not None:
                return StreamEvent(
                    type=EventType.TOOL_RESULT,
                    data={
                        "result": chunk.toolResult
                    }
                )
            elif chunk.content:
                return StreamEvent(
                    type=EventType.CONTENT,
                    data={
                        "delta": chunk.content,
                        "role": chunk.role
                    }
                )
            return None
            
        # Handle different chunk types from legacy streaming (dict format)
        
        # Handle {'type': 'chunk', 'text': '...'} format
        if isinstance(chunk, dict):
            # Handle {'type': 'chunk', 'text': '...'} format
            if chunk.get('type') == 'chunk' and 'text' in chunk:
                return StreamEvent(
                    type=EventType.CONTENT,
                    data={
                        "delta": chunk['text']  # Changed from 'text' to 'delta'
                    }
                )
            
            # Handle {'type': 'complete', ...} format
            if chunk.get('type') == 'complete':
                # This is the final completion, can include sheet state
                return StreamEvent(
                    type=EventType.DONE,  # Changed from STATUS to DONE
                    data={
                        "status": "completed",
                        "sheet": chunk.get('sheet')
                    }
                )
        
        # Tool call chunks
        if "tool_call" in chunk:
            return StreamEvent(
                type=EventType.TOOL_CALL,
                data={
                    "tool": chunk["tool_call"].get("function", {}).get("name", "unknown"),
                    "arguments": chunk["tool_call"].get("function", {}).get("arguments", ""),
                    "id": chunk.get("id", None)
                }
            )
        
        # Tool result chunks
        if "tool_result" in chunk:
            return StreamEvent(
                type=EventType.TOOL_RESULT,
                data={
                    "tool_id": chunk.get("tool_id"),
                    "result": chunk["tool_result"]
                }
            )
        
        # Content chunks
        if "content" in chunk:
            return StreamEvent(
                type=EventType.CONTENT,
                data={
                    "delta": chunk["content"],
                    "finish_reason": chunk.get("finish_reason")
                }
            )
        
        # Reasoning chunks (for models like DeepSeek)
        if "reasoning" in chunk:
            return StreamEvent(
                type=EventType.REASONING,
                data={
                    "content": chunk["reasoning"],
                    "thinking": True
                }
            )
        
        # Status updates
        if "status" in chunk:
            return StreamEvent(
                type=EventType.STATUS,
                data=chunk
            )
        
        # Unknown chunk type
        return None 