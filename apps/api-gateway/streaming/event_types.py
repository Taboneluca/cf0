"""
Event types and data structures for SSE streaming.
"""
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel
import json
import time


class EventType(Enum):
    """Types of events that can be streamed."""
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    CONTENT = "content"
    ERROR = "error"
    STATUS = "status"
    DONE = "done"
    HEARTBEAT = "heartbeat"


class StreamEvent(BaseModel):
    """Represents a single streaming event."""
    type: EventType
    data: Dict[str, Any]
    id: Optional[str] = None
    timestamp: Optional[int] = None
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = int(time.time() * 1000)
        super().__init__(**data)
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        lines = []
        
        # Add event type
        lines.append(f"event: {self.type.value}")
        
        # Add data
        lines.append(f"data: {json.dumps(self.data)}")
        
        # Add ID if present
        if self.id:
            lines.append(f"id: {self.id}")
        
        # Double newline to end the event
        return "\n".join(lines) + "\n\n"
    
    @classmethod
    def heartbeat(cls) -> "StreamEvent":
        """Create a heartbeat event"""
        return cls(
            type=EventType.HEARTBEAT,
            data={"status": "alive", "timestamp": time.time()}
        )
    
    @classmethod
    def error(cls, error: str, code: Optional[str] = None, recoverable: bool = True) -> "StreamEvent":
        """Create an error event"""
        return cls(
            type=EventType.ERROR,
            data={
                "error": error,
                "code": code or "UNKNOWN_ERROR",
                "recoverable": recoverable
            }
        )
    
    @classmethod
    def status(cls, status: str, **kwargs) -> "StreamEvent":
        """Create a status event"""
        return cls(
            type=EventType.STATUS,
            data={"status": status, **kwargs}
        )
    
    @classmethod
    def content(cls, delta: str, finish_reason: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a content event"""
        data = {"delta": delta}
        if finish_reason:
            data["finish_reason"] = finish_reason
        data.update(kwargs)
        return cls(type=EventType.CONTENT, data=data)
    
    @classmethod
    def tool_call(cls, tool_name: str, arguments: Any, call_id: str, **kwargs) -> "StreamEvent":
        """Create a tool call event"""
        return cls(
            type=EventType.TOOL_CALL,
            data={
                "tool": tool_name,
                "arguments": arguments,
                "id": call_id,
                **kwargs
            },
            id=call_id
        )
    
    @classmethod
    def tool_result(cls, tool_id: str, result: Any, **kwargs) -> "StreamEvent":
        """Create a tool result event"""
        return cls(
            type=EventType.TOOL_RESULT,
            data={
                "tool_id": tool_id,
                "result": result,
                **kwargs
            },
            id=tool_id
        )
    
    @classmethod
    def reasoning(cls, content: str, thinking: bool = True, **kwargs) -> "StreamEvent":
        """Create a reasoning event"""
        return cls(
            type=EventType.REASONING,
            data={
                "content": content,
                "thinking": thinking,
                **kwargs
            }
        )
    
    @classmethod
    def done(cls, **kwargs) -> "StreamEvent":
        """Create a completion event"""
        return cls(
            type=EventType.DONE,
            data={"status": "completed", **kwargs}
        ) 