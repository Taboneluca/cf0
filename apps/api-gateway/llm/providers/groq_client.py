from groq import AsyncGroq
import json
from ..base import LLMClient
from ..chat_types import Message, AIResponse, ToolCall
from typing import List, Dict, Any, Optional, AsyncGenerator

# Model alias mapping to normalize model names
MODEL_ALIASES = {
    "llama3-8b-8192": "llama3-8b-8192",          # official slug
    "llama-3-8b": "llama3-8b-8192",              # fall-back
    "llama3-70b-8192": "llama3-70b-8192",        # official slug
    "llama-3-70b": "llama3-70b-8192",            # fall-back
    "llama-3.3-70b-versatile": "llama-3.3-70b-versatile", # official slug
    "llama-3-3-70b": "llama-3.3-70b-versatile",  # fall-back
}

def _prune_none(d: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of d without keys whose value is None."""
    return {k: v for k, v in d.items() if v is not None}

class GroqClient(LLMClient):
    name = "groq"
    provider = "groq"  # Add provider property for detection

    def __init__(self, api_key: str, model: str, **kw):
        # Normalize model name - strip 'groq:' prefix if present 
        # and map through aliases if needed
        if model.startswith("groq:"):
            model = model.removeprefix("groq:")
        # Look up in alias table for standardization
        model = MODEL_ALIASES.get(model, model)
        
        super().__init__(api_key, model, **kw)
        self.client = AsyncGroq(api_key=api_key)
        self.force_json = False
    
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
        new_client = GroqClient(self.api_key, self.model, **new_kw)
        
        # Handle headers separately - No longer pass headers to AsyncGroq constructor as it's not supported
        if extra_headers:
            # Create a new client instance without headers parameter
            new_client.client = AsyncGroq(api_key=self.api_key)
            # Store headers elsewhere if needed
            new_client._extra_headers = extra_headers
        
        # Set JSON mode flag
        new_client.force_json = force_function_usage
        return new_client
    
    def to_provider_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert standard messages to Groq format"""
        result = []
        for msg in messages:
            if msg.role == "tool":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content or ""
                })
                continue

            groq_msg = {"role": msg.role}
            
            if msg.content is not None:
                groq_msg["content"] = msg.content
                
            if msg.tool_calls:
                # Groq expects tool_calls array with function objects (similar to OpenAI)
                groq_msg["tool_calls"] = [
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
                groq_msg["name"] = msg.name
                
            result.append(groq_msg)
        return result
    
    def from_provider_response(self, response: Any) -> AIResponse:
        """Convert Groq response to standard format"""
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

    # We need a non-async method to return an async generator without becoming a coroutine
    def chat(self, messages: List[Message], stream: bool = False, tools: Optional[List[Dict[str, Any]]] = None, **params):
        """Send a chat completion request to Groq"""
        # CRITICAL FIX: This method is no longer async, so it won't turn into a coroutine
        # when returning an async generator from stream_chat
        
        if stream:
            # This now works correctly - returning an async generator from a non-async method
            return self.stream_chat(messages, tools, **params)
            
        # For non-streaming, we use a special helper that runs the async code
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
            
        groq_messages = self.to_provider_messages(messages)
        
        # Remove None values from parameters
        params = _prune_none(params)
        self.kw = _prune_none(self.kw)
        
        # Force JSON response format if needed
        if self.force_json and tools:
            params["response_format"] = {"type": "json_object"}
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=groq_messages,
            stream=False,
            tools=_wrap_tools(tools),
            **self.kw, 
            **params,
        )
        
        return self.from_provider_response(response)
    
    async def stream_chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, **params) -> AsyncGenerator[AIResponse, None]:
        """Stream a chat completion from Groq"""
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
            
        groq_messages = self.to_provider_messages(messages)
        
        # Remove None values from parameters
        params = _prune_none(params)
        self.kw = _prune_none(self.kw)
        
        # Don't force JSON response format when streaming
        # JSON format conflicts with streaming and causes errors
        if "response_format" in params:
            del params["response_format"]
        
        # CRITICAL FIX: Yield immediately to ensure this is an async generator
        # This initial yield must happen before any awaits
        yield AIResponse(content="", tool_calls=[])
            
        try:
            # Create the stream - awaiting happens after our first yield
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=groq_messages,
                stream=True, 
                tools=_wrap_tools(tools),
                **self.kw,
                **params,
            )
            
            current_content = ""
            current_tool_calls = {}  # id -> tool call
            
            # Now iterate on the response stream
            async for chunk in stream:
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
        except Exception as e:
            # We already yielded at least once
            print(f"Error in stream processing: {str(e)}")
            yield AIResponse(content=f"Error: {str(e)}", tool_calls=[])
            
    @property
    def supports_tool_calls(self) -> bool:
        return True  # Groq supports OpenAI-compatible tool calling 