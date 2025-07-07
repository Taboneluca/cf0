"""
SSE (Server-Sent Events) handler for streaming responses.
Converts agent streaming output to SSE format.
Enhanced for 2025 with stream ID management, intelligent event conversion, and performance optimizations.
"""

import json
import asyncio
import gzip
import time
import os
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


class StreamingMetrics:
    """Track streaming performance metrics."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all metrics for a new stream."""
        self.start_time = time.time()
        self.total_events = 0
        self.content_events = 0
        self.tool_events = 0
        self.error_events = 0
        self.heartbeat_events = 0
        self.total_content_size = 0
        self.compression_savings = 0
        self.last_heartbeat = time.time()
        self.event_timestamps = []
    
    def log_event(self, event_type: str, size: int = 0, compressed_size: int = None):
        """Log an event and its metrics."""
        self.total_events += 1
        
        if event_type == EventType.CONTENT.value:
            self.content_events += 1
            self.total_content_size += size
        elif event_type in [EventType.TOOL_CALL.value, EventType.TOOL_RESULT.value]:
            self.tool_events += 1
        elif event_type == EventType.ERROR.value:
            self.error_events += 1
        elif event_type == EventType.HEARTBEAT.value:
            self.heartbeat_events += 1
            self.last_heartbeat = time.time()
        
        if compressed_size is not None and compressed_size < size:
            self.compression_savings += (size - compressed_size)
        
        self.event_timestamps.append(time.time())
        # Keep only last 100 events for performance
        if len(self.event_timestamps) > 100:
            self.event_timestamps = self.event_timestamps[-100:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive streaming statistics."""
        duration = time.time() - self.start_time
        events_per_second = self.total_events / duration if duration > 0 else 0
        
        return {
            'duration': duration,
            'total_events': self.total_events,
            'content_events': self.content_events,
            'tool_events': self.tool_events,
            'error_events': self.error_events,
            'heartbeat_events': self.heartbeat_events,
            'events_per_second': events_per_second,
            'total_content_size': self.total_content_size,
            'compression_savings': self.compression_savings,
            'average_event_interval': self._calculate_average_interval(),
        }
    
    def _calculate_average_interval(self) -> float:
        """Calculate average time between events."""
        if len(self.event_timestamps) < 2:
            return 0.0
        
        intervals = []
        for i in range(1, len(self.event_timestamps)):
            intervals.append(self.event_timestamps[i] - self.event_timestamps[i-1])
        
        return sum(intervals) / len(intervals) if intervals else 0.0


class StreamingHandler:
    """Handles conversion of agent streaming to SSE format with enhanced features."""
    
    def __init__(self):
        # Enhanced configuration for 2025
        self.base_heartbeat_interval = float(os.getenv('SSE_HEARTBEAT_INTERVAL', '30'))  # seconds
        self.adaptive_heartbeat = os.getenv('SSE_ADAPTIVE_HEARTBEAT', '1') == '1'
        self.enable_compression = os.getenv('SSE_ENABLE_COMPRESSION', '1') == '1'
        self.compression_threshold = int(os.getenv('SSE_COMPRESSION_THRESHOLD', '1024'))  # bytes
        self.max_event_size = int(os.getenv('SSE_MAX_EVENT_SIZE', '65536'))  # 64KB
        self.enable_detailed_errors = os.getenv('SSE_DETAILED_ERRORS', '1') == '1'
        
        # Metrics tracking
        self.metrics = StreamingMetrics()
        
        # Stream management
        self.active_streams = {}  # stream_id -> stream_info
        self.stream_counter = 0
    
    def generate_stream_id(self) -> str:
        """Generate a unique stream ID."""
        self.stream_counter += 1
        return f"stream-{int(time.time() * 1000)}-{self.stream_counter}"
    
    async def stream_response(
        self, 
        request: Request, 
        chat_request: ChatRequest
    ) -> EventSourceResponse:
        """
        Stream chat responses in SSE format with enhanced features.
        
        Args:
            request: FastAPI request object
            chat_request: The chat request containing message, model, etc.
            
        Returns:
            EventSourceResponse for SSE streaming
        """
        # Generate stream ID
        stream_id = self.generate_stream_id()
        
        # Register stream
        self.active_streams[stream_id] = {
            'start_time': time.time(),
            'request': chat_request,
            'client_ip': request.client.host if request.client else 'unknown',
        }
        
        print(f"[SSE-{stream_id}] Starting enhanced SSE stream for {chat_request.mode} mode")
        
        try:
            return EventSourceResponse(
                self._event_generator(chat_request, stream_id),
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",  # Disable Nginx buffering
                    "X-Stream-ID": stream_id,  # NEW: Stream ID header
                    "X-SSE-Version": "2025.1",  # NEW: Version tracking
                }
            )
        finally:
            # Cleanup stream registration
            self.active_streams.pop(stream_id, None)
    
    async def _event_generator(
        self, 
        chat_request: ChatRequest,
        stream_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate SSE events from agent streaming with enhanced features."""
        self.metrics.reset()
        heartbeat_task = None
        heartbeat_queue = asyncio.Queue()
        
        try:
            # Start adaptive heartbeat task
            heartbeat_task = asyncio.create_task(
                self._adaptive_heartbeat_generator(heartbeat_queue, stream_id)
            )
            
            # Send initial status event with stream metadata
            initial_status = {
                "status": "starting",
                "model": chat_request.model,
                "mode": getattr(chat_request, 'mode', 'ask'),
                "stream_id": stream_id,
                "timestamp": time.time(),
                "sse_version": "2025.1"
            }
            
            yield await self._create_sse_event(
                EventType.STATUS, 
                initial_status,
                stream_id
            )
            
            # Process the streaming response with enhanced event handling
            mode = getattr(chat_request, 'mode', 'ask')
            chunk_count = 0
            last_progress_update = time.time()
            progress_update_interval = 2.0  # Update progress every 2 seconds for long operations
            
            async for chunk in process_message_streaming(
                mode=mode,
                message=chat_request.message,
                wid=chat_request.wid,
                sid=chat_request.sid,
                model=chat_request.model
            ):
                chunk_count += 1
                chunk_time = time.time()
                
                print(f"[SSE-{stream_id}] Processing chunk #{chunk_count}: Type={type(chunk).__name__}")
                
                # Check for heartbeat events
                try:
                    heartbeat = heartbeat_queue.get_nowait()
                    yield heartbeat
                except asyncio.QueueEmpty:
                    pass
                
                # Convert legacy streaming format to enhanced SSE events
                events = await self._convert_chunk_to_events(chunk, stream_id)
                
                for event in events:
                    if event:
                        yield event
                
                # Adaptive progress updates for long operations
                if (mode == 'analyst' and 
                    chunk_time - last_progress_update > progress_update_interval and
                    chunk_count > 10):  # Only for substantial operations
                    
                    progress_event = await self._create_progress_event(
                        chunk_count, 
                        chunk_time - self.metrics.start_time,
                        stream_id
                    )
                    if progress_event:
                        yield progress_event
                        last_progress_update = chunk_time
                
                # Small delay to prevent overwhelming client (adaptive based on activity)
                await asyncio.sleep(0.001 if chunk_count < 100 else 0.005)
            
            # Send enhanced completion event
            completion_stats = self.metrics.get_stats()
            yield await self._create_sse_event(
                EventType.DONE,
                {
                    "status": "completed",
                    "stream_id": stream_id,
                    "timestamp": time.time(),
                    "statistics": completion_stats
                },
                stream_id
            )
            
            print(f"[SSE-{stream_id}] Stream completed successfully: {completion_stats}")
            
        except Exception as e:
            print(f"[SSE-{stream_id}] Stream error: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Send enhanced error event
            error_data = {
                "error": str(e),
                "code": "STREAM_ERROR",
                "recoverable": True,
                "stream_id": stream_id,
                "timestamp": time.time(),
            }
            
            if self.enable_detailed_errors:
                error_data.update({
                    "error_type": type(e).__name__,
                    "chunk_count": chunk_count,
                    "stream_duration": time.time() - self.metrics.start_time,
                })
            
            yield await self._create_sse_event(EventType.ERROR, error_data, stream_id)
        
        finally:
            # Clean up heartbeat task
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
    
    async def _adaptive_heartbeat_generator(self, queue: asyncio.Queue, stream_id: str) -> None:
        """Generate adaptive heartbeat events based on activity level."""
        last_activity = time.time()
        
        while True:
            # Calculate dynamic heartbeat interval based on activity
            if self.adaptive_heartbeat:
                time_since_activity = time.time() - self.metrics.last_heartbeat
                
                if time_since_activity < 5:  # High activity
                    interval = self.base_heartbeat_interval * 2  # Less frequent heartbeats
                elif time_since_activity < 15:  # Medium activity
                    interval = self.base_heartbeat_interval
                else:  # Low activity
                    interval = self.base_heartbeat_interval * 0.5  # More frequent heartbeats
            else:
                interval = self.base_heartbeat_interval
            
            await asyncio.sleep(interval)
            
            heartbeat_event = await self._create_sse_event(
                EventType.HEARTBEAT,
                {
                    "status": "alive",
                    "timestamp": time.time(),
                    "stream_id": stream_id,
                    "interval": interval
                },
                stream_id
            )
            
            await queue.put(heartbeat_event)
    
    async def _convert_chunk_to_events(self, chunk: Any, stream_id: str) -> list[Dict[str, Any]]:
        """Convert a chunk to one or more SSE events with enhanced processing."""
        events = []
        
        try:
            # Handle ChatStep objects
            if hasattr(chunk, 'role'):
                events.extend(await self._process_chatstep(chunk, stream_id))
            
            # Handle dictionary format chunks
            elif isinstance(chunk, dict):
                events.extend(await self._process_dict_chunk(chunk, stream_id))
            
            # Handle string chunks
            elif isinstance(chunk, str):
                events.append(await self._create_sse_event(
                    EventType.CONTENT,
                    {"delta": chunk, "stream_id": stream_id},
                    stream_id
                ))
            
            else:
                print(f"[SSE-{stream_id}] Unknown chunk type: {type(chunk)}")
        
        except Exception as e:
            print(f"[SSE-{stream_id}] Error converting chunk: {e}")
            events.append(await self._create_sse_event(
                EventType.ERROR,
                {
                    "error": f"Chunk conversion error: {str(e)}",
                    "code": "CONVERSION_ERROR",
                    "recoverable": True,
                    "stream_id": stream_id
                },
                stream_id
            ))
        
        return events
    
    async def _process_chatstep(self, step: ChatStep, stream_id: str) -> list[Dict[str, Any]]:
        """Process a ChatStep object into SSE events."""
        events = []
        
        # Add stream metadata to step if available
        step_data = {
            "stream_id": stream_id,
            "timestamp": time.time(),
        }
        
        # Copy any existing metadata
        if hasattr(step, '__dict__'):
            step_data.update({
                k: v for k, v in step.__dict__.items() 
                if k in ['step_number', 'plan_id', 'current_phase']
            })
        
        if step.toolCall:
            # Enhanced tool call event
            tool_data = {
                "tool": step.toolCall.get("name", "unknown"),
                "arguments": step.toolCall.get("arguments", {}),
                "id": step.toolCall.get("id", None),
                **step_data
            }
            events.append(await self._create_sse_event(EventType.TOOL_CALL, tool_data, stream_id))
        
        if step.toolResult is not None:
            # Enhanced tool result event
            result_data = {
                "result": step.toolResult,
                **step_data
            }
            events.append(await self._create_sse_event(EventType.TOOL_RESULT, result_data, stream_id))
        
        if step.content:
            # Enhanced content event
            content_data = {
                "delta": step.content,
                "role": step.role,
                **step_data
            }
            events.append(await self._create_sse_event(EventType.CONTENT, content_data, stream_id))
        
        return events
    
    async def _process_dict_chunk(self, chunk: Dict[str, Any], stream_id: str) -> list[Dict[str, Any]]:
        """Process a dictionary chunk into SSE events."""
        events = []
        
        # Enhanced chunk processing with better type detection
        chunk_type = chunk.get('type')
        
        if chunk_type == 'chunk' and 'text' in chunk:
            # Content chunk
            events.append(await self._create_sse_event(
                EventType.CONTENT,
                {
                    "delta": chunk['text'],
                    "stream_id": stream_id,
                    "timestamp": time.time()
                },
                stream_id
            ))
        
        elif chunk_type == 'complete':
            # Completion chunk with optional sheet state
            completion_data = {
                "status": "completed",
                "stream_id": stream_id,
                "timestamp": time.time()
            }
            if 'sheet' in chunk:
                completion_data['sheet'] = chunk['sheet']
            
            events.append(await self._create_sse_event(EventType.DONE, completion_data, stream_id))
        
        elif chunk_type == 'update':
            # Workbook update chunk
            events.append(await self._create_sse_event(
                EventType.UPDATE,
                {
                    "updates": chunk.get('payload', []),
                    "sheet_id": chunk.get('sheet_id'),
                    "workbook_id": chunk.get('workbook_id'),
                    "stream_id": stream_id,
                    "timestamp": time.time()
                },
                stream_id
            ))
        
        elif 'tool_call' in chunk:
            # Tool call chunk
            events.append(await self._create_sse_event(
                EventType.TOOL_CALL,
                {
                    "tool": chunk["tool_call"].get("function", {}).get("name", "unknown"),
                    "arguments": chunk["tool_call"].get("function", {}).get("arguments", ""),
                    "id": chunk.get("id", None),
                    "stream_id": stream_id,
                    "timestamp": time.time()
                },
                stream_id
            ))
        
        elif 'tool_result' in chunk:
            # Tool result chunk
            events.append(await self._create_sse_event(
                EventType.TOOL_RESULT,
                {
                    "tool_id": chunk.get("tool_id"),
                    "result": chunk["tool_result"],
                    "stream_id": stream_id,
                    "timestamp": time.time()
                },
                stream_id
            ))
        
        elif 'content' in chunk:
            # Content chunk
            events.append(await self._create_sse_event(
                EventType.CONTENT,
                {
                    "delta": chunk["content"],
                    "finish_reason": chunk.get("finish_reason"),
                    "stream_id": stream_id,
                    "timestamp": time.time()
                },
                stream_id
            ))
        
        elif 'reasoning' in chunk:
            # Reasoning chunk (for models like DeepSeek)
            events.append(await self._create_sse_event(
                EventType.REASONING,
                {
                    "content": chunk["reasoning"],
                    "thinking": True,
                    "stream_id": stream_id,
                    "timestamp": time.time()
                },
                stream_id
            ))
        
        elif 'status' in chunk:
            # Status update
            status_data = {**chunk, "stream_id": stream_id, "timestamp": time.time()}
            events.append(await self._create_sse_event(EventType.STATUS, status_data, stream_id))
        
        return events
    
    async def _create_progress_event(self, chunk_count: int, duration: float, stream_id: str) -> Optional[Dict[str, Any]]:
        """Create a progress event for long-running operations."""
        if duration < 5:  # Only show progress for operations longer than 5 seconds
            return None
        
        # Estimate progress based on chunk count and duration
        # This is a rough heuristic that can be improved with better planning integration
        estimated_total_chunks = max(chunk_count * 2, 50)  # Conservative estimate
        progress_percentage = min(int((chunk_count / estimated_total_chunks) * 100), 95)  # Cap at 95%
        
        return await self._create_sse_event(
            EventType.STATUS,
            {
                "status": "progress",
                "progress_percentage": progress_percentage,
                "chunks_processed": chunk_count,
                "duration": duration,
                "stream_id": stream_id,
                "timestamp": time.time()
            },
            stream_id
        )
    
    async def _create_sse_event(self, event_type: EventType, data: Dict[str, Any], stream_id: str) -> Dict[str, Any]:
        """Create an SSE event with compression and size optimization."""
        # Serialize data
        data_json = json.dumps(data, separators=(',', ':'))  # Compact JSON
        data_size = len(data_json.encode('utf-8'))
        
        # Apply compression for large payloads
        compressed_data = None
        if (self.enable_compression and 
            data_size > self.compression_threshold and 
            event_type in [EventType.TOOL_RESULT, EventType.UPDATE]):  # Only compress large data events
            
            try:
                compressed_bytes = gzip.compress(data_json.encode('utf-8'))
                compressed_size = len(compressed_bytes)
                
                if compressed_size < data_size * 0.8:  # Only use compression if it saves at least 20%
                    # Use base64 encoding for compressed data
                    import base64
                    compressed_data = base64.b64encode(compressed_bytes).decode('ascii')
                    data = {
                        "compressed": True,
                        "encoding": "gzip+base64",
                        "data": compressed_data,
                        "original_size": data_size,
                        "compressed_size": compressed_size
                    }
                    data_json = json.dumps(data, separators=(',', ':'))
                    print(f"[SSE-{stream_id}] Compressed event {event_type.value}: {data_size}B -> {compressed_size}B ({compressed_size/data_size*100:.1f}%)")
            except Exception as e:
                print(f"[SSE-{stream_id}] Compression failed: {e}")
                # Fall back to uncompressed data
        
        # Truncate extremely large events
        final_size = len(data_json.encode('utf-8'))
        if final_size > self.max_event_size:
            print(f"[SSE-{stream_id}] Event too large ({final_size}B), truncating")
            data = {
                "error": "Event truncated due to size limit",
                "original_size": final_size,
                "max_size": self.max_event_size,
                "event_type": event_type.value,
                "stream_id": stream_id
            }
            data_json = json.dumps(data, separators=(',', ':'))
        
        # Log metrics
        self.metrics.log_event(
            event_type.value, 
            data_size, 
            len(compressed_data.encode('utf-8')) if compressed_data else None
        )
        
        # Return SSE event
        return {
            "event": event_type.value,
            "data": data_json,
            "id": f"{stream_id}-{self.metrics.total_events}"
        }
    
    def get_active_streams(self) -> Dict[str, Dict[str, Any]]:
        """Get information about currently active streams."""
        current_time = time.time()
        
        return {
            stream_id: {
                **stream_info,
                'duration': current_time - stream_info['start_time'],
                'mode': stream_info['request'].mode,
                'model': stream_info['request'].model,
            }
            for stream_id, stream_info in self.active_streams.items()
        }
    
    def get_streaming_stats(self) -> Dict[str, Any]:
        """Get overall streaming statistics."""
        return {
            'active_streams': len(self.active_streams),
            'total_events_current_stream': self.metrics.total_events,
            'compression_enabled': self.enable_compression,
            'adaptive_heartbeat': self.adaptive_heartbeat,
            'current_stream_stats': self.metrics.get_stats(),
        } 