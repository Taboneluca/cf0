from openai import AsyncOpenAI, RateLimitError
import json
import os
import asyncio
from ..base import LLMClient
from ..chat_types import Message, AIResponse, ToolCall
from typing import List, Dict, Any, Optional, AsyncGenerator, Union

def _prune_none(d: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of d without keys whose value is None."""
    return {k: v for k, v in d.items() if v is not None}

def _adapt_o_series_params(params: dict, model: str = None) -> dict:
    """Adapt parameters for o-series models"""
    result = params.copy()
    
    # Only apply adaptations to o-series models
    if model and any(model.startswith(prefix) for prefix in ("o3", "o4-", "o5-", "o")):
        # 1. Param rename for o-series models
        if "max_tokens" in result:
            result["max_completion_tokens"] = result.pop("max_tokens")
            
        # 2. Force temperature=1 for o-series models
        result.setdefault("temperature", 1)
    
    return result

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

    def chat(self, messages: List[Message], stream: bool = False, tools: Optional[List[Dict[str, Any]]] = None, **params) -> Union[AsyncGenerator[AIResponse, None], AIResponse]:
        """
        Send a chat completion request to OpenAI with simple retry.
        
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
        
        # Apply o-series adaptations to both params and self.kw
        params = _adapt_o_series_params(params, self.model)
        self.kw = _adapt_o_series_params(self.kw, self.model)

        # Remove "temperature=None" and any other None values
        params = _prune_none(params)
        self.kw = _prune_none(self.kw)
        
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

    async def _stream_chat_impl(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, **params) -> AsyncGenerator[AIResponse, None]:
        """
        Internal implementation for streaming chat.
        This must be properly implemented as an async generator.
        """
        # CRITICAL: We must yield at least once before any await statements
        # Otherwise, the function becomes a coroutine, not an async generator
        yield AIResponse(content="", tool_calls=[])
        
        try:
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
            
            # Apply o-series adaptations to both params and self.kw
            params = _adapt_o_series_params(params, self.model)
            self.kw = _adapt_o_series_params(self.kw, self.model)

            # Remove "temperature=None" and any other None values
            params = _prune_none(params)
            self.kw = _prune_none(self.kw)
            
            # Simple retry logic for rate limits
            max_retries = 3
            retry_count = 0
            
            while True:
                try:
                    # Now we can safely await since we've already yielded once
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
                    
                    # Now iterate on the response stream
                    async for chunk in response_stream:
                        delta = chunk.choices[0].delta
                        
                        # Handle new content - CRITICAL: Only yield the delta, not accumulated
                        if delta.content:
                            new_content_delta = delta.content  # This is already a delta from OpenAI
                            current_content += new_content_delta  # Track total for tool calls if needed
                            
                            # Yield only the NEW content delta
                            yield AIResponse(
                                content=new_content_delta,  # Send only the delta
                                tool_calls=[]  # Don't send tool calls with content deltas
                            )
                        
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
                            
                            # Convert completed tool calls to AIResponse
                            tool_calls = []
                            for tc_data in current_tool_calls.values():
                                # Only add if we have a name and completed arguments
                                if tc_data["name"] and tc_data["arguments"]:
                                    # Try to parse arguments as JSON
                                    args = tc_data["arguments"]
                                    try:
                                        args = json.loads(args)
                                        # Only yield tool calls when arguments are complete JSON
                                        tool_calls.append(ToolCall(
                                            name=tc_data["name"],
                                            args=args,
                                            id=tc_data["id"]
                                        ))
                                    except json.JSONDecodeError:
                                        pass  # Keep accumulating until valid JSON
                            
                            # Only yield tool calls when we have complete ones
                            if tool_calls:
                                yield AIResponse(
                                    content="",  # No content with tool calls
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
        except Exception as e:
            # We already yielded at least once
            print(f"Error in OpenAI stream processing: {str(e)}")
            yield AIResponse(content=f"Error: {str(e)}", tool_calls=[])

    # Implement the required abstract method to meet the interface contract
    async def stream_chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, **params) -> AsyncGenerator[AIResponse, None]:
        """
        Stream a chat completion from OpenAI with simple retry.
        
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
        return True 