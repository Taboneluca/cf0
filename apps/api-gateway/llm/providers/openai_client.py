from openai import AsyncOpenAI, RateLimitError
import json
import os
import asyncio
from ..base import LLMClient
from ..chat_types import Message, AIResponse, ToolCall
from typing import List, Dict, Any, Optional, AsyncGenerator

class OpenAIClient(LLMClient):
    name = "openai"

    def __init__(self, api_key: str, model: str, **kw):
        super().__init__(api_key, model, **kw)
        # Add organization support
        org_id = os.environ.get("OPENAI_ORG")
        self.client = AsyncOpenAI(api_key=api_key, organization=org_id)
        
    def to_provider_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert standard messages to OpenAI format"""
        result = []
        for msg in messages:
            # ----- tool-result messages -----
            if msg.role == "tool":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content or ""
                })
                continue

            openai_msg = {"role": msg.role}
            
            if msg.content is not None:
                openai_msg["content"] = msg.content
                
            if msg.tool_calls:
                # OpenAI expects tool_calls array with function objects
                openai_msg["tool_calls"] = [
                    {
                        "id": tc.id or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.args) if isinstance(tc.args, dict) else tc.args
                        }
                    }
                    for i, tc in enumerate(msg.tool_calls)
                ]
                
            if msg.name:
                openai_msg["name"] = msg.name
                
            result.append(openai_msg)
        return result
    
    def from_provider_response(self, response: Any) -> AIResponse:
        """Convert OpenAI response to standard format"""
        if not response or not hasattr(response, "choices") or not response.choices:
            return AIResponse()
            
        message = response.choices[0].message
        tool_calls = []
        
        # Extract tool calls if present
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                args = {}
                try:
                    if isinstance(tc.function.arguments, str):
                        args = json.loads(tc.function.arguments)
                    else:
                        args = tc.function.arguments
                except:
                    args = tc.function.arguments  # Keep as string if can't parse
                    
                tool_calls.append(ToolCall(
                    name=tc.function.name,
                    args=args,
                    id=tc.id
                ))
                
        # Extract usage info if available
        usage = None
        if hasattr(response, "usage"):
            usage = response.usage.model_dump()
            
        return AIResponse(
            content=message.content,
            tool_calls=tool_calls,
            usage=usage
        )

    async def chat(self, messages: List[Message], stream: bool = False, tools: Optional[List[Dict[str, Any]]] = None, **params):
        """Send a chat completion request to OpenAI with simple retry"""
        def _wrap_tools(tools):
            if not tools:
                return None
            wrapped = []
            for t in tools:
                wrapped.append({
                    "type": "function",
                    "function": {
                        "name":        t["name"],
                        "description": t.get("description", ""),
                        "parameters":  t.get("parameters", {})
                    }
                })
            return wrapped
            
        if stream:
            return await self.stream_chat(messages, tools, **params)
            
        openai_messages = self.to_provider_messages(messages)
        
        # -- o-series compatibility layer ---------------------------------
        if self.model.startswith(("o3", "o4-", "o5-", "o")):        # future-proof
            # 1. Param rename
            if "max_tokens" in params:
                params["max_completion_tokens"] = params.pop("max_tokens")
            if "max_tokens" in self.kw:
                self.kw["max_completion_tokens"] = self.kw.pop("max_tokens")

            # 2. Temperature hard-limit (only `1` is allowed)
            if params.get("temperature") not in (None, 1):
                params.pop("temperature", None)
            if self.kw.get("temperature") not in (None, 1):
                self.kw.pop("temperature", None)
        
        # Simple retry logic for rate limits
        max_retries = 3
        retry_count = 0
        while True:
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    stream=False,
                    tools=_wrap_tools(tools),
                    **self.kw, 
                    **params,
                )
                return self.from_provider_response(response)
            except RateLimitError as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise  # Re-raise if we've reached max retries
                # Exponential backoff: 1s, 2s, 4s, etc.
                wait_time = 2 ** (retry_count - 1)
                print(f"Rate limit exceeded, retrying in {wait_time}s (attempt {retry_count}/{max_retries})...")
                await asyncio.sleep(wait_time)
    
    async def stream_chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, **params) -> AsyncGenerator[AIResponse, None]:
        """Stream a chat completion from OpenAI with simple retry"""
        def _wrap_tools(tools):
            if not tools:
                return None
            wrapped = []
            for t in tools:
                wrapped.append({
                    "type": "function",
                    "function": {
                        "name":        t["name"],
                        "description": t.get("description", ""),
                        "parameters":  t.get("parameters", {})
                    }
                })
            return wrapped
            
        openai_messages = self.to_provider_messages(messages)
        
        # -- o-series compatibility layer ---------------------------------
        if self.model.startswith(("o3", "o4-", "o5-", "o")):        # future-proof
            # 1. Param rename
            if "max_tokens" in params:
                params["max_completion_tokens"] = params.pop("max_tokens")
            if "max_tokens" in self.kw:
                self.kw["max_completion_tokens"] = self.kw.pop("max_tokens")

            # 2. Temperature hard-limit (only `1` is allowed)
            if params.get("temperature") not in (None, 1):
                params.pop("temperature", None)
            if self.kw.get("temperature") not in (None, 1):
                self.kw.pop("temperature", None)
        
        # Simple retry logic for rate limits
        max_retries = 3
        retry_count = 0
        while True:
            try:
                response_stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    stream=True,
                    tools=_wrap_tools(tools),
                    **self.kw,
                    **params,
                )
                
                current_content = ""
                current_tool_calls = {}  # id -> tool call
                
                async for chunk in response_stream:
                    delta = chunk.choices[0].delta
                    
                    # Handle new content
                    if delta.content:
                        current_content += delta.content
                    
                    # Handle tool calls
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            tc_id = tc_delta.id
                            
                            # Initialize tool call if new
                            if tc_id not in current_tool_calls:
                                current_tool_calls[tc_id] = {
                                    "id": tc_id,
                                    "name": "",
                                    "arguments": ""
                                }
                            
                            # Update tool call with new data
                            if hasattr(tc_delta, "function"):
                                if hasattr(tc_delta.function, "name") and tc_delta.function.name:
                                    current_tool_calls[tc_id]["name"] = tc_delta.function.name
                                    
                                if hasattr(tc_delta.function, "arguments") and tc_delta.function.arguments:
                                    current_tool_calls[tc_id]["arguments"] += tc_delta.function.arguments
                    
                    # Convert current state to AIResponse
                    tool_calls = []
                    for tc_data in current_tool_calls.values():
                        # Only add if we have a name
                        if tc_data["name"]:
                            # Try to parse arguments as JSON
                            args = tc_data["arguments"]
                            try:
                                args = json.loads(args)
                            except:
                                pass  # Keep as string if not valid JSON
                                
                            tool_calls.append(ToolCall(
                                name=tc_data["name"],
                                args=args,
                                id=tc_data["id"]
                            ))
                    
                    yield AIResponse(
                        content=current_content,
                        tool_calls=tool_calls
                    )
                break  # Success, exit retry loop
            except RateLimitError as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise  # Re-raise if we've reached max retries
                # Exponential backoff: 1s, 2s, 4s, etc.
                wait_time = 2 ** (retry_count - 1)
                print(f"Rate limit exceeded, retrying in {wait_time}s (attempt {retry_count}/{max_retries})...")
                await asyncio.sleep(wait_time)
            
    @property
    def supports_tool_calls(self) -> bool:
        return True 