"""
Event types and data structures for SSE streaming.
Enhanced for 2025 with planning events, batch operations, and stream lifecycle management.
"""
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, validator, Field
import json
import time
import uuid


class EventType(Enum):
    """Types of events that can be streamed - Enhanced for 2025."""
    # Core content events
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    CONTENT = "content"
    ERROR = "error"
    STATUS = "status"
    DONE = "done"
    HEARTBEAT = "heartbeat"
    UPDATE = "update"  # For workbook cell updates
    
    # NEW: Planning phase events
    PLANNING = "planning"  # When the agent is creating a plan
    PLAN_READY = "plan_ready"  # When a plan is complete and ready for execution
    PROGRESS = "progress"  # For progress updates during long operations
    
    # NEW: Batch operation events
    BATCH_START = "batch_start"  # Beginning of a batch operation
    BATCH_PROGRESS = "batch_progress"  # Progress within a batch
    BATCH_COMPLETE = "batch_complete"  # Completion of a batch operation
    
    # NEW: Stream lifecycle events
    STREAM_START = "stream_start"  # Stream initialization with ID
    STREAM_PAUSE = "stream_pause"  # Temporary pause (for planning)
    STREAM_RESUME = "stream_resume"  # Resume after pause
    STREAM_METADATA = "stream_metadata"  # Stream metadata updates


class PlanPhase(Enum):
    """Planning phases for execution tracking."""
    ANALYZE = "analyze"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"


class BatchStrategy(Enum):
    """Batch execution strategies."""
    INDIVIDUAL = "individual"
    SMALL_BATCH = "small_batch"
    LARGE_BATCH = "large_batch"
    PROGRESSIVE = "progressive"


class StreamEvent(BaseModel):
    """
    Represents a single streaming event with enhanced metadata and validation.
    """
    type: EventType
    data: Dict[str, Any]
    id: Optional[str] = None
    timestamp: Optional[int] = None
    stream_id: Optional[str] = None  # NEW: Stream identifier
    sequence_number: Optional[int] = None  # NEW: Event sequence in stream
    
    # NEW: Performance and planning metadata
    plan_id: Optional[str] = None
    plan_phase: Optional[PlanPhase] = None
    batch_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = int(time.time() * 1000)
        if 'id' not in data and data.get('stream_id'):
            data['id'] = f"{data['stream_id']}-{data.get('sequence_number', int(time.time() * 1000))}"
        super().__init__(**data)
    
    @validator('data')
    def validate_data_content(cls, v, values):
        """Validate event data based on event type."""
        event_type = values.get('type')
        if not event_type:
            return v
        
        # Type-specific validation
        if event_type == EventType.CONTENT:
            if 'delta' not in v:
                raise ValueError("Content events must have 'delta' field")
        elif event_type == EventType.TOOL_CALL:
            required_fields = ['tool', 'arguments']
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"Tool call events must have '{field}' field")
        elif event_type == EventType.PLANNING:
            if 'phase' not in v:
                raise ValueError("Planning events must have 'phase' field")
        elif event_type == EventType.BATCH_START:
            required_fields = ['strategy', 'estimated_items']
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"Batch start events must have '{field}' field")
        
        return v
    
    def to_sse(self) -> str:
        """Convert to SSE format with enhanced metadata."""
        lines = []
        
        # Add event type
        lines.append(f"event: {self.type.value}")
        
        # Enhanced data with metadata
        enhanced_data = {
            **self.data,
            "_meta": {
                "timestamp": self.timestamp,
                "stream_id": self.stream_id,
                "sequence_number": self.sequence_number,
                "plan_id": self.plan_id,
                "plan_phase": self.plan_phase.value if self.plan_phase else None,
                "batch_id": self.batch_id,
                "parent_event_id": self.parent_event_id,
            }
        }
        
        # Add data
        lines.append(f"data: {json.dumps(enhanced_data, separators=(',', ':'))}")
        
        # Add ID if present
        if self.id:
            lines.append(f"id: {self.id}")
        
        # Double newline to end the event
        return "\n".join(lines) + "\n\n"
    
    @classmethod
    def heartbeat(cls, stream_id: Optional[str] = None) -> "StreamEvent":
        """Create a heartbeat event with stream context."""
        return cls(
            type=EventType.HEARTBEAT,
            data={"status": "alive", "timestamp": time.time()},
            stream_id=stream_id
        )
    
    @classmethod
    def error(cls, error: str, code: Optional[str] = None, recoverable: bool = True, 
              stream_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create an enhanced error event."""
        return cls(
            type=EventType.ERROR,
            data={
                "error": error,
                "code": code or "UNKNOWN_ERROR",
                "recoverable": recoverable,
                **kwargs
            },
            stream_id=stream_id
        )
    
    @classmethod
    def status(cls, status: str, stream_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a status event with stream context."""
        return cls(
            type=EventType.STATUS,
            data={"status": status, **kwargs},
            stream_id=stream_id
        )
    
    @classmethod
    def content(cls, delta: str, finish_reason: Optional[str] = None, 
                stream_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a content event with enhanced metadata."""
        data = {"delta": delta}
        if finish_reason:
            data["finish_reason"] = finish_reason
        data.update(kwargs)
        return cls(type=EventType.CONTENT, data=data, stream_id=stream_id)
    
    @classmethod
    def tool_call(cls, tool_name: str, arguments: Any, call_id: str, 
                  stream_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a tool call event with enhanced tracking."""
        return cls(
            type=EventType.TOOL_CALL,
            data={
                "tool": tool_name,
                "arguments": arguments,
                "id": call_id,
                **kwargs
            },
            id=call_id,
            stream_id=stream_id
        )
    
    @classmethod
    def tool_result(cls, tool_id: str, result: Any, stream_id: Optional[str] = None, 
                    **kwargs) -> "StreamEvent":
        """Create a tool result event with enhanced tracking."""
        return cls(
            type=EventType.TOOL_RESULT,
            data={
                "tool_id": tool_id,
                "result": result,
                **kwargs
            },
            id=tool_id,
            stream_id=stream_id
        )
    
    @classmethod
    def reasoning(cls, content: str, thinking: bool = True, stream_id: Optional[str] = None, 
                  **kwargs) -> "StreamEvent":
        """Create a reasoning event with enhanced context."""
        return cls(
            type=EventType.REASONING,
            data={
                "content": content,
                "thinking": thinking,
                **kwargs
            },
            stream_id=stream_id
        )
    
    @classmethod
    def done(cls, stream_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a completion event with final metrics."""
        return cls(
            type=EventType.DONE,
            data={"status": "completed", **kwargs},
            stream_id=stream_id
        )
    
    @classmethod
    def update(cls, updates: list, stream_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a workbook update event with enhanced tracking."""
        return cls(
            type=EventType.UPDATE,
            data={"updates": updates, **kwargs},
            stream_id=stream_id
        )
    
    # NEW: Planning phase events
    
    @classmethod
    def planning(cls, phase: str, description: str, stream_id: Optional[str] = None, 
                 plan_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a planning phase event."""
        return cls(
            type=EventType.PLANNING,
            data={
                "phase": phase,
                "description": description,
                **kwargs
            },
            stream_id=stream_id,
            plan_id=plan_id,
            plan_phase=PlanPhase(phase) if phase in [p.value for p in PlanPhase] else None
        )
    
    @classmethod
    def plan_ready(cls, plan_summary: str, complexity_score: int, estimated_duration: float,
                   tool_groups: int, stream_id: Optional[str] = None, plan_id: Optional[str] = None, 
                   **kwargs) -> "StreamEvent":
        """Create a plan ready event."""
        return cls(
            type=EventType.PLAN_READY,
            data={
                "plan_summary": plan_summary,
                "complexity_score": complexity_score,
                "estimated_duration": estimated_duration,
                "tool_groups": tool_groups,
                **kwargs
            },
            stream_id=stream_id,
            plan_id=plan_id
        )
    
    @classmethod
    def progress(cls, percentage: int, current_step: str, total_steps: Optional[int] = None,
                 stream_id: Optional[str] = None, plan_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a progress update event."""
        return cls(
            type=EventType.PROGRESS,
            data={
                "percentage": percentage,
                "current_step": current_step,
                "total_steps": total_steps,
                **kwargs
            },
            stream_id=stream_id,
            plan_id=plan_id
        )
    
    # NEW: Batch operation events
    
    @classmethod
    def batch_start(cls, strategy: str, estimated_items: int, description: str,
                    stream_id: Optional[str] = None, batch_id: Optional[str] = None, 
                    **kwargs) -> "StreamEvent":
        """Create a batch operation start event."""
        if not batch_id:
            batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        
        return cls(
            type=EventType.BATCH_START,
            data={
                "strategy": strategy,
                "estimated_items": estimated_items,
                "description": description,
                **kwargs
            },
            stream_id=stream_id,
            batch_id=batch_id
        )
    
    @classmethod
    def batch_progress(cls, items_completed: int, total_items: int, current_item: str,
                       stream_id: Optional[str] = None, batch_id: Optional[str] = None, 
                       **kwargs) -> "StreamEvent":
        """Create a batch progress event."""
        percentage = int((items_completed / total_items) * 100) if total_items > 0 else 0
        
        return cls(
            type=EventType.BATCH_PROGRESS,
            data={
                "items_completed": items_completed,
                "total_items": total_items,
                "current_item": current_item,
                "percentage": percentage,
                **kwargs
            },
            stream_id=stream_id,
            batch_id=batch_id
        )
    
    @classmethod
    def batch_complete(cls, items_processed: int, duration: float, success_count: int,
                       stream_id: Optional[str] = None, batch_id: Optional[str] = None, 
                       **kwargs) -> "StreamEvent":
        """Create a batch completion event."""
        return cls(
            type=EventType.BATCH_COMPLETE,
            data={
                "items_processed": items_processed,
                "duration": duration,
                "success_count": success_count,
                "failure_count": items_processed - success_count,
                **kwargs
            },
            stream_id=stream_id,
            batch_id=batch_id
        )
    
    # NEW: Stream lifecycle events
    
    @classmethod
    def stream_start(cls, stream_id: str, mode: str, model: str, **kwargs) -> "StreamEvent":
        """Create a stream initialization event."""
        return cls(
            type=EventType.STREAM_START,
            data={
                "mode": mode,
                "model": model,
                "stream_version": "2025.1",
                **kwargs
            },
            stream_id=stream_id
        )
    
    @classmethod
    def stream_pause(cls, reason: str, stream_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a stream pause event."""
        return cls(
            type=EventType.STREAM_PAUSE,
            data={
                "reason": reason,
                **kwargs
            },
            stream_id=stream_id
        )
    
    @classmethod
    def stream_resume(cls, reason: str, stream_id: Optional[str] = None, **kwargs) -> "StreamEvent":
        """Create a stream resume event."""
        return cls(
            type=EventType.STREAM_RESUME,
            data={
                "reason": reason,
                **kwargs
            },
            stream_id=stream_id
        )
    
    @classmethod
    def stream_metadata(cls, metadata: Dict[str, Any], stream_id: Optional[str] = None) -> "StreamEvent":
        """Create a stream metadata event."""
        return cls(
            type=EventType.STREAM_METADATA,
            data=metadata,
            stream_id=stream_id
        )


class EventValidator:
    """Validates streaming events for consistency and completeness."""
    
    @staticmethod
    def validate_event_sequence(events: List[StreamEvent]) -> List[str]:
        """Validate a sequence of events for logical consistency."""
        errors = []
        
        if not events:
            return errors
        
        # Check for required stream start
        if events[0].type != EventType.STREAM_START:
            errors.append("Stream should start with STREAM_START event")
        
        # Check for proper termination
        last_event = events[-1]
        if last_event.type not in [EventType.DONE, EventType.ERROR]:
            errors.append("Stream should end with DONE or ERROR event")
        
        # Check batch event pairing
        batch_starts = {}
        for event in events:
            if event.type == EventType.BATCH_START:
                if event.batch_id in batch_starts:
                    errors.append(f"Duplicate batch start for batch {event.batch_id}")
                batch_starts[event.batch_id] = event
            elif event.type == EventType.BATCH_COMPLETE:
                if event.batch_id not in batch_starts:
                    errors.append(f"Batch complete without start for batch {event.batch_id}")
                else:
                    del batch_starts[event.batch_id]
        
        # Check for unclosed batches
        for batch_id in batch_starts:
            errors.append(f"Unclosed batch: {batch_id}")
        
        # Check planning phase sequence
        planning_phases = []
        for event in events:
            if event.type == EventType.PLANNING and event.plan_phase:
                planning_phases.append(event.plan_phase)
        
        # Validate planning phase order
        expected_order = [PlanPhase.ANALYZE, PlanPhase.PLAN, PlanPhase.EXECUTE, PlanPhase.VERIFY]
        if planning_phases:
            # Check if phases follow expected order (not all phases required)
            last_phase_index = -1
            for phase in planning_phases:
                try:
                    phase_index = expected_order.index(phase)
                    if phase_index < last_phase_index:
                        errors.append(f"Planning phases out of order: {phase.value} after phase {expected_order[last_phase_index].value}")
                    last_phase_index = max(last_phase_index, phase_index)
                except ValueError:
                    errors.append(f"Unknown planning phase: {phase.value}")
        
        return errors
    
    @staticmethod
    def validate_event_data(event: StreamEvent) -> List[str]:
        """Validate individual event data integrity."""
        errors = []
        
        # Check required metadata
        if not event.timestamp:
            errors.append("Event missing timestamp")
        
        if not event.stream_id:
            errors.append("Event missing stream_id")
        
        # Type-specific validation
        if event.type == EventType.CONTENT:
            if 'delta' not in event.data or not isinstance(event.data['delta'], str):
                errors.append("Content event must have string 'delta' field")
        
        elif event.type == EventType.TOOL_CALL:
            required_fields = ['tool', 'arguments', 'id']
            for field in required_fields:
                if field not in event.data:
                    errors.append(f"Tool call event missing '{field}' field")
        
        elif event.type == EventType.PROGRESS:
            if 'percentage' not in event.data or not isinstance(event.data['percentage'], int):
                errors.append("Progress event must have integer 'percentage' field")
            elif not 0 <= event.data['percentage'] <= 100:
                errors.append("Progress percentage must be between 0 and 100")
        
        elif event.type == EventType.BATCH_PROGRESS:
            required_fields = ['items_completed', 'total_items']
            for field in required_fields:
                if field not in event.data or not isinstance(event.data[field], int):
                    errors.append(f"Batch progress event must have integer '{field}' field")
            
            if (event.data.get('items_completed', 0) > event.data.get('total_items', 0)):
                errors.append("Batch progress: items_completed cannot exceed total_items")
        
        return errors
    
    @staticmethod
    def get_event_size(event: StreamEvent) -> int:
        """Calculate the size of an event in bytes."""
        return len(event.to_sse().encode('utf-8'))
    
    @staticmethod
    def should_compress_event(event: StreamEvent, threshold: int = 1024) -> bool:
        """Determine if an event should be compressed based on size and type."""
        if event.type not in [EventType.TOOL_RESULT, EventType.UPDATE]:
            return False
        
        return EventValidator.get_event_size(event) > threshold


class EventBatch:
    """Manages batches of related events for efficient transmission."""
    
    def __init__(self, batch_id: str, strategy: BatchStrategy, max_size: int = 10):
        self.batch_id = batch_id
        self.strategy = strategy
        self.max_size = max_size
        self.events: List[StreamEvent] = []
        self.created_at = time.time()
    
    def add_event(self, event: StreamEvent) -> bool:
        """Add an event to the batch. Returns True if batch is now full."""
        event.batch_id = self.batch_id
        self.events.append(event)
        return len(self.events) >= self.max_size
    
    def get_batch_event(self, stream_id: Optional[str] = None) -> StreamEvent:
        """Create a single event containing the entire batch."""
        return StreamEvent(
            type=EventType.BATCH_COMPLETE,
            data={
                "batch_id": self.batch_id,
                "strategy": self.strategy.value,
                "events": [event.dict() for event in self.events],
                "event_count": len(self.events),
                "batch_duration": time.time() - self.created_at
            },
            stream_id=stream_id,
            batch_id=self.batch_id
        )
    
    def is_empty(self) -> bool:
        """Check if the batch is empty."""
        return len(self.events) == 0
    
    def is_full(self) -> bool:
        """Check if the batch is full."""
        return len(self.events) >= self.max_size 