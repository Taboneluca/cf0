from groq import AsyncGroq
import json
from ..base import LLMClient
from ..chat_types import Message, AIResponse, ToolCall
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
import time

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

    def chat(self, messages: List[Message], stream: bool = False, tools: Optional[List[Dict[str, Any]]] = None, **params) -> Union[AsyncGenerator[AIResponse, None], AIResponse]:
        """
        Send a chat completion request to Groq.
        
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
    
    # Renamed to _stream_chat_impl to avoid confusion with the abstract method
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
                # Convert to Groq tool objects
                return [
                    {
                        "type": "function",
                        "function": {
                            "name": tool["function"]["name"],
                            "description": tool["function"].get("description", ""),
                            "parameters": tool["function"].get("parameters", {})
                        }
                    }
                    for tool in tools
                ]
            
            # Prepare tools for Groq
            wrapped_tools = _wrap_tools(tools)
            
            # Set JSON mode for responses with Llama models where it's needed
            use_json_mode = "llama" in self.model.lower() or params.get("json_mode", False)
            
            # Convert messages to Groq format
            groq_messages = self.to_provider_messages(messages)
            
            # Add explicit debug print to track groq client streaming calls
            print(f"[GROQ DEBUG] Starting stream for model: {self.model}")
            
            # Create stream with all parameters
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=groq_messages,
                tools=wrapped_tools,
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 1024),
                stream=True,
                top_p=params.get("top_p", 0.95),
                response_format={"type": "json_object"} if use_json_mode else None
            )
            
            # Tracking variables for chunk delivery metrics
            chunk_counter = 0
            last_chunk_time = time.time()
            content_so_far = ""
            
            # Initialize variables to accumulate the response
            tool_calls = []
            content = ""
            
            # Process the stream
            async for chunk in stream:
                chunk_counter += 1
                current_time = time.time()
                chunk_interval = current_time - last_chunk_time
                last_chunk_time = current_time
                
                delta = chunk.choices[0].delta
                
                # Extract the content from the delta
                if delta.content is not None:
                    content += delta.content
                    content_so_far += delta.content
                    # Explicitly log every chunk to debug streaming issues
                    print(f"[GROQ DEBUG] Chunk #{chunk_counter} after {chunk_interval:.4f}s - Content len: {len(delta.content)}")
                    
                    # Yield immediately for real-time streaming
                    yield AIResponse(content=content, tool_calls=tool_calls)
                
                # Handle tool calls
                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        # Add null checks for function attribute
                        if not hasattr(tool_call_delta, 'function') or tool_call_delta.function is None:
                            print(f"[GROQ DEBUG] Skipping tool_call_delta with no function: {tool_call_delta}")
                            continue
                            
                        # Find or create the tool call
                        tool_call_id = tool_call_delta.index
                        if tool_call_id >= len(tool_calls):
                            # Add new tool call with safe access to function attributes
                            function_name = getattr(tool_call_delta.function, 'name', '') or ""
                            function_args = getattr(tool_call_delta.function, 'arguments', '') or ""
                            
                            tool_calls.append({
                                "id": f"call_{len(tool_calls)}",
                                "type": "function",
                                "function": {
                                    "name": function_name,
                                    "arguments": function_args
                                }
                            })
                        else:
                            # Update existing tool call with safe access
                            if hasattr(tool_call_delta.function, 'name') and tool_call_delta.function.name:
                                tool_calls[tool_call_id]["function"]["name"] = tool_call_delta.function.name
                            
                            if hasattr(tool_call_delta.function, 'arguments') and tool_call_delta.function.arguments:
                                tool_calls[tool_call_id]["function"]["arguments"] += tool_call_delta.function.arguments
                    
                    # Yield after each tool call update
                    yield AIResponse(content=content, tool_calls=tool_calls)
            
            # Print final streaming stats
            print(f"[GROQ DEBUG] Completed stream with {chunk_counter} chunks, total content: {len(content_so_far)} chars")
            
        except Exception as e:
            print(f"Error in Groq streaming: {str(e)}")
            yield AIResponse(content=f"Error: {str(e)}", tool_calls=[])
    
    # Implement the required abstract method to meet the interface contract
    async def stream_chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, **params) -> AsyncGenerator[AIResponse, None]:
        """
        Stream a chat completion from Groq.
        
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
        return True  # Groq supports OpenAI-compatible tool calling 