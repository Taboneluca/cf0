from anthropic import AsyncAnthropic
import json
import os
from ..base import LLMClient
from ..chat_types import Message, AIResponse, ToolCall
from typing import List, Dict, Any, Optional, AsyncGenerator, Union

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

    def to_provider_messages(self, messages: List[Message]) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Convert standard messages to Anthropic format"""
        # Extract system message if present
        system_message = None
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
                break
        
        # Handle all non-system messages
        result = []
        for msg in messages:
            # Skip system messages as they're handled separately
            if msg.role == "system":
                continue
                
            # Convert tool results to assistant responses with content
            if msg.role == "tool":
                # Tool results are mapped to assistant responses in Anthropic
                result.append({
                    "role": "assistant",
                    "content": f"Tool result: {msg.content}"
                })
                continue
                
            # Map user/assistant directly
            if msg.role in ["user", "assistant"]:
                anthropic_msg = {"role": msg.role}
                
                # Handle content and tool calls
                if msg.content is not None:
                    # For Claude: content must be a list of blocks
                    if msg.tool_calls:
                        # Messages with tool calls need special structure
                        anthropic_msg["content"] = [
                            {"type": "text", "text": msg.content or ""}
                        ]
                        # Add tool_calls in proper format
                        for tc in msg.tool_calls:
                            anthropic_msg["content"].append({
                                "type": "tool_use",
                                "name": tc.name,
                                "input": tc.args,
                                "id": tc.id or f"call_{tc.name}"
                            })
                    else:
                        # Simple text content
                        anthropic_msg["content"] = msg.content
                        
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

    def chat(self, messages: List[Message], stream: bool = False, tools: Optional[List[Dict[str, Any]]] = None, **params) -> Union[AsyncGenerator[AIResponse, None], AIResponse]:
        """
        Send a chat request to Anthropic.
        
        IMPORTANT: This is deliberately NOT async to avoid coroutine issue with async generators.
        """
        if stream:
            # Return the async generator directly without being wrapped in a coroutine
            return self._stream_chat_impl(messages, tools, **params)
        else:
            # For non-streaming, use async helper
            return self._chat_sync(messages, tools, **params)

    async def _chat_sync(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, **params):
        """Internal async helper for non-streaming chat"""
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

    async def _stream_chat_impl(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, **params) -> AsyncGenerator[AIResponse, None]:
        """
        Internal implementation for streaming chat.
        This must be properly implemented as an async generator.
        """
        # CRITICAL: We must yield at least once before any await statements
        # Otherwise, the function becomes a coroutine, not an async generator
        yield AIResponse(content="", tool_calls=[])
        
        try:
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
            
            # Now it's safe to await since we've already yielded once
            with_stream = await self.client.messages.create(
                model=self.model,
                messages=claude_messages,
                system=system_message,
                tools=anthropic_tools,
                stream=True,
                **self.kw, 
                **params,
            )
            
            current_content = ""
            current_tool_calls = {}  # id -> tool call
            
            # Process each streaming event by directly iterating the stream object
            async for event in with_stream:
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
                    
                elif event.type == "tool_use_block_start" and hasattr(event, "tool_use"):
                    # Beginning of a tool call
                    tool = event.tool_use
                    tool_id = tool.id
                    
                    # Initialize the tool call data structure
                    current_tool_calls[tool_id] = {
                        "id": tool_id,
                        "name": tool.name,
                        "input": tool.input or {}
                    }
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
        except Exception as e:
            # We already yielded at least once
            print(f"Error in anthropic stream processing: {str(e)}")
            yield AIResponse(content=f"Error: {str(e)}", tool_calls=[])

    # Implement the required abstract method to meet the interface contract
    async def stream_chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, **params) -> AsyncGenerator[AIResponse, None]:
        """
        Stream a chat response from Anthropic.
        
        IMPORTANT: This must be properly implemented as an async generator.
        """
        # Yield immediately to make this a proper async generator
        yield AIResponse(content="", tool_calls=[])
        
        # Now delegate to the actual implementation
        generator = self._stream_chat_impl(messages, tools, **params)
        # Skip the first chunk since we've already yielded an empty one
        first = True
        
        async for chunk in generator:
            if first:
                first = False
                continue
            yield chunk
            
    @property
    def supports_tool_calls(self) -> bool:
        return True  # Claude 3.5+ supports tools 