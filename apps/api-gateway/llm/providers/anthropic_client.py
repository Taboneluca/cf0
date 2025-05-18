from anthropic import AsyncAnthropic
import json
from ..base import LLMClient
from ..chat_types import Message, AIResponse, ToolCall
from typing import List, Dict, Any, Optional, AsyncGenerator

def _prune_none(d: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of d without keys whose value is None."""
    return {k: v for k, v in d.items() if v is not None}

class AnthropicClient(LLMClient):
    name = "anthropic"
    provider = "anthropic"  # Add provider property for detection

    def __init__(self, api_key: str, model: str, **kw):
        super().__init__(api_key, model, **kw)
        self.client = AsyncAnthropic(api_key=api_key)

    def with_options(self, **options):
        """Create a new client with additional options"""
        new_kw = dict(self.kw)
        # Update with new options
        extra_headers = None
        force_function_usage = False
        
        # Extract special options
        for k, v in options.items():
            if k == 'extra_headers':
                extra_headers = v
            elif k == 'force_function_usage':
                force_function_usage = v
            else:
                new_kw[k] = v
        
        # Create new client with updated options
        new_client = AnthropicClient(self.api_key, self.model, **new_kw)
        
        # Handle headers separately if needed
        if extra_headers:
            # Anthropic client takes headers at client creation
            new_client.client = AsyncAnthropic(api_key=self.api_key, headers=extra_headers)
        
        return new_client

    def to_provider_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert standard messages to Anthropic format"""
        result = []
        system_message = None
        
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
                continue
            
            # Handle tool messages from OpenAI/Groq format and convert to Anthropic format
            if msg.role == "tool":
                # Convert tool result to Anthropic format
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content or ""
                    }]
                })
                continue
                
            anthropic_msg = {"role": msg.role}
            
            if msg.content is not None:
                anthropic_msg["content"] = msg.content
            
            # Anthropic uses tool_use/tool_result instead of tool_calls
            if msg.tool_calls and msg.role == "assistant":
                anthropic_msg["content"] = []
                
                if msg.content:
                    anthropic_msg["content"].append({
                        "type": "text",
                        "text": msg.content
                    })
                    
                for tc in msg.tool_calls:
                    # Make sure input is always a dictionary (Claude requires this)
                    input_obj = tc.args if isinstance(tc.args, dict) else {"value": tc.args}
                    
                    anthropic_msg["content"].append({
                        "type": "tool_use",
                        "id": tc.id or f"call_{len(anthropic_msg['content'])}",
                        "name": tc.name,
                        "input": input_obj
                    })
                    
            result.append(anthropic_msg)
            
        return result, system_message
        
    def from_provider_response(self, response: Any) -> AIResponse:
        """Convert Anthropic response to standard format"""
        if not response:
            return AIResponse()
            
        # Extract content
        content = None
        if hasattr(response, "content") and response.content:
            if isinstance(response.content, list):
                # If content is a list of blocks, extract text content
                text_blocks = [block.text for block in response.content 
                              if hasattr(block, "type") and block.type == "text"]
                content = "\n".join(text_blocks) if text_blocks else None
            else:
                content = response.content
                
        # Extract tool calls
        tool_calls = []
        if hasattr(response, "content") and isinstance(response.content, list):
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        name=block.name,
                        args=block.input,
                        id=block.id
                    ))
                    
        return AIResponse(
            content=content,
            tool_calls=tool_calls,
            usage=None  # Anthropic doesn't provide usage info
        )

    async def chat(self, messages: List[Message], stream: bool = False, tools: Optional[List[Dict[str, Any]]] = None, **params):
        """Send a chat request to Anthropic"""
        if stream:
            # Return the async generator directly - don't use 'return await' which unwraps the generator
            return self.stream_chat(messages, tools, **params)
            
        claude_messages, system_message = self.to_provider_messages(messages)
        
        # Convert tools to Anthropic tool format if provided
        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for tool in tools:
                anthropic_tool = {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters", {})
                }
                anthropic_tools.append(anthropic_tool)
        
        # Remove None values from parameters
        params = _prune_none(params)
        self.kw = _prune_none(self.kw)
        
        response = await self.client.messages.create(
            model=self.model,
            messages=claude_messages,
            system=system_message,
            tools=anthropic_tools,
            stream=False,
            **self.kw, 
            **params,
        )
        
        return self.from_provider_response(response)
        
    async def stream_chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, **params) -> AsyncGenerator[AIResponse, None]:
        """Stream a chat response from Anthropic"""
        claude_messages, system_message = self.to_provider_messages(messages)
        
        # Convert tools to Anthropic tool format if provided
        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for tool in tools:
                anthropic_tool = {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters", {})
                }
                anthropic_tools.append(anthropic_tool)
        
        # Remove None values from parameters
        params = _prune_none(params)
        self.kw = _prune_none(self.kw)
        
        # Get the stream response
        # Use async with pattern for Anthropic streaming which works better
        current_content = ""
        current_tool_calls = {}  # id -> tool call
        
        # Use the Anthropic recommended streaming pattern
        async with self.client.messages.stream(
            model=self.model,
            messages=claude_messages,
            system=system_message,
            tools=anthropic_tools,
            **self.kw, 
            **params,
        ) as stream:
            # Process each streaming event
            async for event in stream:
                new_content = None
                new_tool_data = None
                
                # Process different types of events from Claude's streaming API
                if event.type == "content_block_start":
                    # Content block started
                    pass
                    
                elif event.type == "content_block_delta":
                    # Handle content delta (the most common event type)
                    if hasattr(event, "delta") and hasattr(event.delta, "text"):
                        new_content = event.delta.text
                        current_content += new_content
                
                elif event.type == "content_block_stop":
                    # Content block completed
                    pass
                    
                elif event.type == "message_start":
                    # Message started
                    pass
                    
                elif event.type == "message_delta":
                    # Message metadata changed
                    pass
                    
                elif event.type == "message_stop":
                    # Message completed
                    pass
                    
                elif event.type == "content_block_delta" and hasattr(event, "delta") and hasattr(event.delta, "type") and event.delta.type == "tool_use":
                    # Handle tool use delta
                    tool_use = event.delta
                    
                    if hasattr(tool_use, "id") and tool_use.id:
                        tool_id = tool_use.id
                        
                        # Initialize tool call if it doesn't exist
                        if tool_id not in current_tool_calls:
                            current_tool_calls[tool_id] = {
                                "id": tool_id,
                                "name": getattr(tool_use, "name", "") if hasattr(tool_use, "name") else "",
                                "input": {}
                            }
                        
                        # Update tool data
                        if hasattr(tool_use, "name") and tool_use.name:
                            current_tool_calls[tool_id]["name"] = tool_use.name
                            
                        if hasattr(tool_use, "input") and tool_use.input:
                            # Merge input dictionaries (Claude may stream tool input in parts)
                            if isinstance(tool_use.input, dict):
                                current_tool_calls[tool_id]["input"].update(tool_use.input)
                            
                        # Signal that we have new tool data
                        new_tool_data = True
                
                # If we have new content or tool data, emit an AIResponse
                if new_content or new_tool_data:
                    # Convert current state to AIResponse
                    tool_calls = []
                    for tc_data in current_tool_calls.values():
                        # Only include valid tool calls with a name
                        if tc_data["name"]:
                            tool_calls.append(ToolCall(
                                name=tc_data["name"],
                                args=tc_data["input"],
                                id=tc_data["id"]
                            ))
                    
                    yield AIResponse(
                        content=current_content,
                        tool_calls=tool_calls
                    )

    @property
    def supports_tool_calls(self) -> bool:
        return True  # Claude 3.5+ supports tools 