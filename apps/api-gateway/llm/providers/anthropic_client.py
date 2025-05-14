from anthropic import AsyncAnthropic
import json
from ..base import LLMClient
from ..chat_types import Message, AIResponse, ToolCall
from typing import List, Dict, Any, Optional, AsyncGenerator

class AnthropicClient(LLMClient):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, **kw):
        super().__init__(api_key, model, **kw)
        self.client = AsyncAnthropic(api_key=api_key)

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
                    anthropic_msg["content"].append({
                        "type": "tool_use",
                        "id": tc.id or f"call_{len(anthropic_msg['content'])}",
                        "name": tc.name,
                        "input": tc.args
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
            return await self.stream_chat(messages, tools, **params)
            
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
        
        response_stream = await self.client.messages.create(
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
        
        async for chunk in response_stream:
            if hasattr(chunk, "delta") and hasattr(chunk.delta, "text"):
                current_content += chunk.delta.text
                
            if hasattr(chunk, "delta") and hasattr(chunk.delta, "tool_use"):
                tool_use = chunk.delta.tool_use
                
                # Get or initialize tool call
                if tool_use.id not in current_tool_calls:
                    current_tool_calls[tool_use.id] = {
                        "id": tool_use.id,
                        "name": tool_use.name if hasattr(tool_use, "name") else "",
                        "input": {}
                    }
                
                # Update the tool call with new data
                if hasattr(tool_use, "name") and tool_use.name:
                    current_tool_calls[tool_use.id]["name"] = tool_use.name
                    
                if hasattr(tool_use, "input") and tool_use.input:
                    # Merge the input dictionaries
                    current_tool_calls[tool_use.id]["input"].update(tool_use.input)
            
            # Convert current state to AIResponse
            tool_calls = []
            for tc_data in current_tool_calls.values():
                # Only add if we have a name
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