from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union

@dataclass
class ToolCall:
    """Standardized tool call representation"""
    name: str
    args: Dict[str, Any]
    id: Optional[str] = None

@dataclass
class Message:
    """Standardized message representation for all providers"""
    role: str
    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    name: Optional[str] = None  # For function responses
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary for serialization"""
        result = {"role": self.role}
        if self.content is not None:
            result["content"] = self.content
        if self.tool_calls:
            result["tool_calls"] = [
                {
                    "name": tc.name,
                    "args": tc.args,
                    **({"id": tc.id} if tc.id else {})
                }
                for tc in self.tool_calls
            ]
        if self.name:
            result["name"] = self.name
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create a Message from a dictionary"""
        tool_calls = []
        if "tool_calls" in data:
            tool_calls = [
                ToolCall(
                    name=tc.get("name", tc.get("function", {}).get("name")),
                    args=tc.get("args", tc.get("function", {}).get("arguments", {})),
                    id=tc.get("id")
                )
                for tc in data["tool_calls"]
            ]
        elif "function_call" in data:
            # Handle legacy OpenAI format
            fc = data["function_call"]
            tool_calls = [
                ToolCall(
                    name=fc.get("name"),
                    args=fc.get("arguments", {}),
                    id=None
                )
            ]
            
        return cls(
            role=data["role"],
            content=data.get("content"),
            tool_calls=tool_calls,
            name=data.get("name")
        )

@dataclass
class AIResponse:
    """Standardized AI response for all providers"""
    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    
    def has_tool_calls(self) -> bool:
        """Check if the response contains tool calls"""
        return len(self.tool_calls) > 0 