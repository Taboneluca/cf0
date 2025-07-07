from __future__ import annotations
from typing import List, Dict, Any, Optional, AsyncGenerator, Callable, Union
import os
import asyncio
import json
import re
import time
import traceback
from dotenv import load_dotenv
from .tools import TOOL_CATALOG
from api.token_utils import trim_history
from agents.json_utils import safe_json_loads
from llm.base import LLMClient
from pydantic import BaseModel
from types import SimpleNamespace
from llm.chat_types import AIResponse, Message
from llm.catalog import normalise, normalize_model_name  # Import the normalize_model_name function
from abc import ABC, abstractmethod
from collections import defaultdict

load_dotenv()
MAX_RETRIES = 3
RETRY_DELAY = 1.0
MAX_TOKENS = 4096
# Token limits for various models
MODEL_LIMITS = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 32_768,
    "o4-mini": 32_768,
    "llama-3.1-70b": 8_192,
    "llama-3.1-8b": 8_192, 
    "llama-3.1-405b": 128_000,
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    "claude-3.5-sonnet": 200_000,
    "claude-3.7-sonnet": 200_000,
    "llama-3.3-70b-versatile": 32_768,
    "claude-3-7-sonnet-20250219": 200_000,
    "claude-3-5-sonnet-20240620": 200_000,
}
DEFAULT_MODEL_LIMIT = 16_384  # Default for most other models

class StreamingToolCallHandler:
    """Handles proper accumulation of streaming tool calls from OpenAI API"""
    
    def __init__(self):
        self.tool_calls = {}  # id -> {name, args_buffer, last_ping_kib}
        self.completed_calls = []
        self.debug = os.getenv("DEBUG_STREAMING_TOOLS", "0") == "1"
        self.keep_alive_chunks = []  # Store keep-alive chunks to yield
    
    def process_delta(self, delta) -> List[Dict[str, Any]]:
        """Enhanced delta processing with better error handling and keep-alive chunks"""
        completed_calls = []
        
        if self.debug:
            print(f"[StreamingToolCallHandler] Processing delta: {delta}")
            print(f"[StreamingToolCallHandler] Delta type: {type(delta)}")
            print(f"[StreamingToolCallHandler] Delta attributes: {dir(delta)}")
        
        # Handle OpenAI format tool calls
        if hasattr(delta, 'tool_calls') and delta.tool_calls:
            for tool_call_delta in delta.tool_calls:
                # Validate tool call structure
                if not hasattr(tool_call_delta, 'function'):
                    if self.debug:
                        print(f"[StreamingToolCallHandler] Skipping malformed tool call: {tool_call_delta}")
                    continue
                
                # Check for function arguments
                if hasattr(tool_call_delta.function, 'arguments'):
                    args_chunk = tool_call_delta.function.arguments
                    
                    # Skip empty argument chunks
                    if not args_chunk or args_chunk.strip() == '':
                        if self.debug:
                            print(f"[StreamingToolCallHandler] Skipping empty arguments chunk")
                        continue
                    
                    # Accumulate arguments properly
                    tool_id = tool_call_delta.id
                    if tool_id not in self.tool_calls:
                        self.tool_calls[tool_id] = {
                            'name': tool_call_delta.function.name,
                            'arguments': '',
                            'id': tool_id,
                            'last_ping_kib': 0  # Track keep-alive pings
                        }
                    
                    # Add to buffer
                    self.tool_calls[tool_id]['arguments'] += args_chunk
                    
                    # NEW: Keep-alive logic - send empty chunk every 1KB to keep socket alive
                    current_buffer = self.tool_calls[tool_id]['arguments']
                    current_kib = len(current_buffer) // 1024
                    last_ping_kib = self.tool_calls[tool_id]['last_ping_kib']
                    
                    if current_kib > last_ping_kib:
                        # Send keep-alive chunk
                        self.tool_calls[tool_id]['last_ping_kib'] = current_kib
                        # Store keep-alive chunk to be yielded by caller
                        self.keep_alive_chunks.append({"role": "assistant", "content": ""})
                        if self.debug:
                            print(f"[StreamingToolCallHandler] Keep-alive ping at {current_kib}KB for tool {tool_id}")
                    
                    # Check if arguments are complete
                    try:
                        # Attempt to parse JSON to check completeness
                        parsed_args = json.loads(self.tool_calls[tool_id]['arguments'])
                        
                        # Validate parsed arguments
                        if isinstance(parsed_args, dict) and len(parsed_args) > 0:
                            completed_call = self.tool_calls.pop(tool_id)
                            completed_call['arguments'] = parsed_args
                            completed_calls.append(completed_call)
                            
                            if self.debug:
                                print(f"[StreamingToolCallHandler] Completed tool call: {completed_call}")
                        else:
                            if self.debug:
                                print(f"[StreamingToolCallHandler] Empty or invalid arguments: {parsed_args}")
                    except json.JSONDecodeError:
                        # Arguments not complete yet
                        if self.debug:
                            print(f"[StreamingToolCallHandler] Arguments incomplete, continuing accumulation")
        
        return completed_calls
    
    def get_keep_alive_chunks(self) -> List[Dict[str, Any]]:
        """Get and clear any pending keep-alive chunks"""
        chunks = self.keep_alive_chunks.copy()
        self.keep_alive_chunks.clear()
        return chunks

def get_max_tokens(model: str) -> int:
    """Get the max token limit for a given model, with fallback"""
    try:
        # Normalize to standardized model name
        model_id = normalize_model_name(model)
        # Try to find in MODEL_LIMITS
        if model_id in MODEL_LIMITS:
            return MODEL_LIMITS[model_id]
        # For OpenAI models with specific pattern
        if "gpt-" in model_id:
            return MODEL_LIMITS.get("gpt-4o", DEFAULT_MODEL_LIMIT)
        # For Claude models
        if "claude" in model_id:
            return MODEL_LIMITS.get("claude-3-sonnet", DEFAULT_MODEL_LIMIT)
        # For Llama models
        if "llama" in model_id:
            return MODEL_LIMITS.get("llama-3-70b", DEFAULT_MODEL_LIMIT)
        # Fallback to default
        return DEFAULT_MODEL_LIMIT
    except Exception as e:
        print(f"Error getting max tokens for model {model}: {str(e)}")
        return DEFAULT_MODEL_LIMIT  # Safe fallback

def _serialize_tool(tool: dict) -> dict:
    """Convert tool dict into function schema for OpenAI v1+ function-calling API."""
    return {
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["parameters"],
    }

def _dicts_to_messages(msgs: list[dict | Message]) -> list[Message]:
    """Ensure every element is a Message dataclass."""
    converted = []
    for m in msgs:
        if isinstance(m, Message):
            converted.append(m)
        else:
            # Message.from_dict already understands both
            # {role, content, tool_calls:[{function:{name,arguments}}]} and
            # flat {role, content, tool_calls:[{name,args}]}
            converted.append(Message.from_dict(m))
    return converted

def _airesponse_to_message(resp: AIResponse):
    """
    Convert unified AIResponse into an object that looks like the
    OpenAI-style `message` expected by the legacy agent loop
    (i.e. has .content, .tool_calls, .function_call, model_dump()).
    """
    import json, uuid
    class _PseudoMsg:
        def __init__(self, r: AIResponse):
            self.role = "assistant"
            self.content = r.content
            self.tool_calls = []
            self.function_call = None
            if r.tool_calls:
                for i, tc in enumerate(r.tool_calls):
                    fn = SimpleNamespace(
                        name=tc.name,
                        arguments=json.dumps(tc.args)
                    )
                    call = SimpleNamespace(
                        id=tc.id or f"call_{i}",
                        type="function",
                        function=fn,
                        # --- add the two lines below ---
                        name=tc.name,          # make them available at top level
                        args=tc.args,
                    )
                    self.tool_calls.append(call)
                # expose first call for convenience
                first = r.tool_calls[0]
                self.function_call = SimpleNamespace(
                    name=first.name,
                    arguments=json.dumps(first.args)
                )
        # the agent later calls .model_dump()
        def model_dump(self):
            data = {"role": self.role}
            if self.content is not None:
                data["content"] = self.content
            if self.tool_calls:
                data["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {
                            "name": c.function.name,
                            "arguments": c.function.arguments,
                        },
                    } for c in self.tool_calls
                ]
            return data
    return _PseudoMsg(resp)

class ToolCallRetryManager:
    """Manages retry logic for failed tool calls with intelligent prompting"""
    
    def __init__(self, max_retries: int = 3, max_consecutive_errors: int = 5):
        self.max_retries = max_retries
        self.max_consecutive_errors = max_consecutive_errors
        self.retry_counts = {}
        self.last_errors = {}
        self.consecutive_error_count = 0
        self.last_error_signature = None
        
    def should_retry(self, tool_name: str, error: str) -> bool:
        """Determine if we should retry a failed tool call"""
        key = f"{tool_name}:{error}"
        
        # Create error signature for circuit breaker
        error_signature = f"{tool_name}:{error[:50]}"  # First 50 chars
        
        # Check for consecutive identical errors (circuit breaker)
        if error_signature == self.last_error_signature:
            self.consecutive_error_count += 1
        else:
            self.consecutive_error_count = 1
            self.last_error_signature = error_signature
        
        # Circuit breaker: Stop if too many consecutive identical errors
        if self.consecutive_error_count >= self.max_consecutive_errors:
            print(f"[CIRCUIT_BREAKER] Stopping after {self.consecutive_error_count} consecutive identical errors")
            return False
        
        self.retry_counts[key] = self.retry_counts.get(key, 0) + 1
        self.last_errors[tool_name] = error
        
        return self.retry_counts[key] <= self.max_retries
    
    def get_retry_prompt(self, tool_name: str, error: str) -> str:
        """Generate an intelligent retry prompt based on the error"""
        retry_num = self.retry_counts.get(f"{tool_name}:{error}", 1)
        
        # Special handling for repeated empty argument errors
        if "empty" in error.lower() and self.consecutive_error_count >= 3:
            return f"""CRITICAL: You have made {self.consecutive_error_count} consecutive empty tool calls. 

STOP calling {tool_name} with empty arguments. 

Instead:
1. If you need to set a cell, use: set_cell(cell='A1', value='50')  
2. If you're trying to build something, describe what you want instead of using tools
3. If confused, just provide a text response without any tool calls

Do NOT repeat the same empty tool call."""
            
        if "empty arguments" in error.lower() or "json parse error" in error.lower():
            if tool_name == "apply_updates_and_reply":
                return f"""Retry {retry_num}/{self.max_retries}: The apply_updates_and_reply tool requires:
1. updates: An array of cell updates, each with 'cell' and 'value'
2. reply: A text explanation of the changes

Correct example:
apply_updates_and_reply(
    updates=[
        {{"cell": "A1", "value": "Product"}},
        {{"cell": "B1", "value": "Price"}}
    ],
    reply="Added product headers"
)

Please provide the complete arguments."""
            
            elif tool_name == "set_cell":
                return f"""Retry {retry_num}/{self.max_retries}: The set_cell tool requires both parameters:
- cell: The cell reference (e.g., 'A1')  
- value: The value to set

Example: set_cell(cell='A1', value='Hello')"""
            
            elif tool_name == "set_cells":
                return f"""Retry {retry_num}/{self.max_retries}: The set_cells tool requires:
- updates: An array of cell updates

Example: set_cells(updates=[{{"cell": "A1", "value": "Hello"}}, {{"cell": "B1", "value": "World"}}])"""
        
        return f"Retry {retry_num}/{self.max_retries}: Tool {tool_name} failed with: {error}. Please check the parameters and try again."
    
    def reset(self):
        """Reset retry counts for a new conversation"""
        self.retry_counts.clear()
        self.last_errors.clear()
        self.consecutive_error_count = 0
        self.last_error_signature = None
    
    def is_circuit_broken(self) -> bool:
        """Check if circuit breaker is active"""
        return self.consecutive_error_count >= self.max_consecutive_errors

class ChatStep(BaseModel):
    role: str                       # "assistant" | "tool"
    content: str | None = None      # natural-language text
    toolCall: dict | None = None    # {name, args}
    toolResult: Any | None = None   # dict or list or any value returned by Python fn
    usage: dict | None = None       # token counts etc.

class StreamingMetrics:
    def __init__(self):
        self.chunk_count = 0
        self.tool_call_count = 0
        self.error_count = 0
        self.start_time = time.time()
        self.chunk_times = []
    
    def log_chunk(self, chunk_type: str, size: int):
        self.chunk_count += 1
        chunk_time = time.time()
        self.chunk_times.append(chunk_time)
        
        # Log inter-chunk timing
        if len(self.chunk_times) > 1:
            inter_chunk_time = chunk_time - self.chunk_times[-2]
            print(f"[METRICS] Inter-chunk time: {inter_chunk_time:.3f}s")
        
        print(f"[METRICS] Chunk #{self.chunk_count} - Type: {chunk_type}, Size: {size}")

class BaseAgent:
    def __init__(
        self,
        llm: LLMClient,
        fallback_prompt: str,
        tools: list[dict],
        *,
        agent_mode: str | None = None,
        **kwargs
    ):
        """
        Lightweight BaseAgent constructor.
        Accepts a fallback prompt directly rather than querying the database,
        since the database query is already done in orchestrator.
        """
        self.llm = llm
        
        # Set the system prompt
        self.system_prompt = fallback_prompt
        # Store the original prompt for reset functionality
        self._original_prompt = fallback_prompt
        self.tools = tools or []

    def clone_with_tools(self, tool_functions: dict[str, callable]) -> 'BaseAgent':
        """
        Create a new agent with the same system prompt but updated tool functions.
        This is used for per-session sheets.
        
        Args:
            tool_functions: Dictionary mapping tool names to new functions
            
        Returns:
            A new BaseAgent instance with updated tools
        """
        # Create a deep copy of the tools
        new_tools = []
        for tool in self.tools:
            # Copy the tool definition
            new_tool = tool.copy()
            
            # Update the function if provided
            if tool["name"] in tool_functions:
                new_tool["func"] = tool_functions[tool["name"]]
                
            new_tools.append(new_tool)
            
        # Create and return a new agent with the same prompt (no DB lookup)
        return BaseAgent(
            llm=self.llm, 
            fallback_prompt=self.system_prompt, 
            tools=new_tools
        )

    async def run_iter(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[ChatStep, None]:
        """
        Core agent loop – yields ChatStep after:
        1. every LLM function-call decision
        2. every local tool execution
        3. the final plain-text assistant answer
        """
        start_time = time.time()
        agent_id = f"agent-{int(start_time*1000)}"
        print(f"[{agent_id}] 🤖 Starting agent run with message length: {len(user_message)}")
        
        # Add variable to track tool call ID for error handling
        call_id = None
        
        # Prepare the basic message structure with system prompt
        system_message = {"role": "system", "content": self.system_prompt}
        messages = [system_message]
        
        # Add conversation history if provided
        if history:
            print(f"[{agent_id}] 📚 Adding {len(history)} history messages")
            messages.extend(history)
            
        # Add the current user message
        messages.append({"role": "user", "content": user_message})
        
        # Trim history to fit within token limits - use model name from the LLM client
        orig_message_count = len(messages)
        # Construct full model key (provider:model_id) for context window calculation
        model_key = f"{self.llm.name}:{self.llm.model}"
        messages = trim_history(messages, system_message, None, model_key)
        if len(messages) < orig_message_count:
            print(f"[{agent_id}] ✂️ Trimmed history from {orig_message_count} to {len(messages)} messages")

        # Allow many small tool calls without bailing out too early (env: MAX_TOOL_ITERATIONS, default 50)
        max_iterations = int(os.getenv("MAX_TOOL_ITERATIONS", "50"))
        iterations = 0
        collected_updates: list = []
        mutating_calls = 0
        error_count = {}  # Track repeated errors to prevent infinite loops
        mutating_tools = {
            "set_cell", "set_cells", "apply_updates_and_reply",
            "add_row", "add_column", "delete_row", "delete_column",
            "sort_range", "find_replace", "apply_scalar_to_row",
            "apply_scalar_to_column", "create_new_sheet"
        }
        
        print(f"[{agent_id}] 🔄 Starting tool loop with max_iterations={max_iterations}")
        
        # Prevent infinite tool call loops
        tool_call_attempts = defaultdict(int)
        
        while iterations < max_iterations:
            iterations += 1
            loop_start = time.time()
            print(f"[{agent_id}] ⏱️ Iteration {iterations}/{max_iterations}")
            
            # Try to call the model with retries for transient errors
            try:
                call_start = time.time()
                print(f"[{agent_id}] 🔌 Calling LLM model: {self.llm.model}")
                
                # Sanitize legacy fields so Groq/OpenAI v2 accept the history
                for m in messages:
                    m.pop("executed_tools", None)   # Groq legacy
                    # Convert for both OpenAI and Groq, leave Anthropic untouched
                    if self.llm.name in {"openai", "groq"} and "function_call" in m and "tool_calls" not in m:
                        m["tool_calls"] = [{
                            "id": "auto-" + str(time.time_ns()),
                            "type": "function",
                            "function": m.pop("function_call")
                        }]
                
                # Use the LLM interface instead of direct OpenAI call
                # Calculate appropriate token reservation for the model
                model_name = self.llm.model.lower()
                model_limit = get_max_tokens(model_name)
                
                # Reserve at least 400 tokens, or more for larger models
                # For o-series models, ensure we have more output room
                reserve_tokens = 400
                if any(prefix in model_name for prefix in ["gpt-4o", "o4-", "claude-3", "llama-3.1-405b"]):
                    reserve_tokens = min(2048, model_limit // 16)  # More tokens for advanced models
                
                response = await self.llm.chat(
                    messages=_dicts_to_messages(messages),
                    stream=False,
                    tools=[_serialize_tool(t) for t in self.tools] if self.llm.supports_tool_calls else None,
                    temperature=None,  # let the per-model filter decide
                    max_tokens=reserve_tokens
                )
                
                call_time = time.time() - call_start
                print(f"[{agent_id}] ⏱️ LLM call completed in {call_time:.2f}s")
            except Exception as e:
                print(f"[{agent_id}] ❌ Error calling LLM: {str(e)}")
                yield ChatStep(
                    role="assistant", 
                    content=f"Sorry, I encountered an error: {str(e)}"
                )
                return
            
            # Process the response (works for both raw OpenAI/Groq objects
            # and our unified AIResponse dataclass)
            if hasattr(response, "choices"):
                msg = response.choices[0].message
            else:
                msg = _airesponse_to_message(response)
            
            # Add the model's response to the conversation, remapping 'function' role to 'assistant' for Groq
            msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg.__dict__
            if msg_dict.get("role") == "function":
                msg_dict["role"] = "assistant"
            messages.append(msg_dict)
            
            # 1) Function call detected
            if msg.tool_calls and len(msg.tool_calls) > 0:
                tc = msg.tool_calls[0]
                
                # Get the name and arguments
                name = tc.name
                args = tc.args
                
                # ENHANCED DEBUGGING for tool call parsing
                print(f"[{agent_id}] 🔍 RAW TOOL CALL DEBUG:")
                print(f"[{agent_id}] 📝 Tool name: '{name}'")
                print(f"[{agent_id}] 📝 Raw args type: {type(args)}")
                print(f"[{agent_id}] 📝 Raw args content: {repr(args)}")
                print(f"[{agent_id}] 📝 Raw args str: '{str(args)}'")
                if hasattr(tc, 'id'):
                    print(f"[{agent_id}] 📝 Tool call ID: {tc.id}")
                
                # Additional debugging for the raw message
                print(f"[{agent_id}] 🔍 RAW MESSAGE DEBUG:")
                print(f"[{agent_id}] 📝 Message type: {type(msg)}")
                print(f"[{agent_id}] 📝 Message dict: {msg.model_dump() if hasattr(msg, 'model_dump') else str(msg.__dict__)}")
                
                # Get the call ID for error handling
                call_id = tc.id
                if call_id is None:
                    call_id = f"call_{int(time.time()*1000)}"
                
                # Enhanced args validation and conversion
                print(f"[{agent_id}] 🔍 ARGS VALIDATION:")
                print(f"[{agent_id}] 📝 Args is None: {args is None}")
                print(f"[{agent_id}] 📝 Args is empty string: {args == ''}")
                print(f"[{agent_id}] 📝 Args is empty dict: {args == {}}")
                
                # Make sure args is a dictionary before calling the function
                if not isinstance(args, dict):
                    print(f"[{agent_id}] ⚠️ Args is not a dict, converting...")
                    if isinstance(args, list):
                        print(f"[{agent_id}] 🔄 Converting list args to dict with 'updates' key")
                        args = {"updates": args}
                    elif isinstance(args, str):
                        print(f"[{agent_id}] 🔄 Args is string: '{args}'")
                        if args.strip() == "":
                            print(f"[{agent_id}] ⚠️ Empty string args detected!")
                            # For empty string args, add error and skip
                            if name == "apply_updates_and_reply":
                                print(f"[{agent_id}] 🔄 Empty apply_updates_and_reply detected, adding error and continuing...")
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": call_id,
                                    "content": json.dumps({"error": f"Empty arguments provided for {name}. apply_updates_and_reply requires updates array with at least one update containing 'cell' and 'value' fields."})
                                })
                                # Add a system message to force retry with proper arguments
                                messages.append({
                                    "role": "system",
                                    "content": f"The tool call to {name} failed because empty arguments were provided. You MUST provide specific arguments:\n\nFor apply_updates_and_reply, you need:\n- updates: array of cell updates, each with 'cell' and 'value'\n- reply: explanation of what was done\n\nExample: apply_updates_and_reply(updates=[{{\"cell\": \"A1\", \"value\": \"Title\"}}], reply=\"Added title\")\n\nPlease retry with proper arguments or use set_cell for individual updates."
                                })
                                continue
                            elif name == "set_cell":
                                print(f"[{agent_id}] 🔄 Empty set_cell detected, adding error and continuing...")
                                messages.append({
                                    "role": "tool", 
                                    "tool_call_id": call_id,
                                    "content": json.dumps({"error": "No cell reference provided for set_cell. Please specify cell and value parameters."})
                                })
                                # Add system message for retry
                                messages.append({
                                    "role": "system",
                                    "content": "The set_cell tool requires both 'cell' and 'value' parameters. Example: set_cell(cell='A1', value='Revenue'). Please retry with proper arguments."
                                })
                                continue
                            else:
                                # Add error message and force retry for other tools
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": call_id,
                                    "content": json.dumps({"error": f"Empty arguments provided for {name}. Please provide specific parameters."})
                                })
                                messages.append({
                                    "role": "system", 
                                    "content": f"The tool call to {name} failed because no arguments were provided. Please call the tool again with proper arguments."
                                })
                                continue
                        else:
                            # Try to parse as JSON if it looks like JSON
                            if args.strip().startswith('{') or args.strip().startswith('['):
                                try:
                                    args = json.loads(args)
                                    print(f"[{agent_id}] ✅ Successfully parsed JSON args: {args}")
                                except json.JSONDecodeError as e:
                                    print(f"[{agent_id}] ❌ Failed to parse JSON args: {e}")
                                    args = {"value": args}
                            else:
                                args = {"value": args}
                    else:
                        print(f"[{agent_id}] 🔄 Converting {type(args)} to dict with 'value' key")
                        args = {"value": args}
                
                print(f"[{agent_id}] 📝 Final processed args: {args}")
                
                try:
                    print(f"[{agent_id}] 🛠️ Tool call: {name}")
                    
                    # Yield a ChatStep for the function call
                    yield ChatStep(
                        role="assistant",
                        toolCall={
                            "name": name,
                            "arguments": args
                        },
                        usage=getattr(response.usage, "model_dump", lambda: None)() if getattr(response, "usage", None) else None
                    )
                    
                except ValueError as e:
                    print(f"[{agent_id}] ❌ Error parsing function arguments: {str(e)}")
                    # Add a compensating tool message with error
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps({"error": str(e)})
                    })
                    yield ChatStep(
                        role="assistant",
                        content=f"Sorry, I encountered an error while processing your request. Please try again with simpler instructions.",
                        usage=getattr(response.usage, "model_dump", lambda: None)() if getattr(response, "usage", None) else None
                    )
                    return
                
                # Track mutating calls
                if name in mutating_tools:
                    mutating_calls += 1
                    print(f"[{agent_id}] ✏️ Mutating call #{mutating_calls}: {name}")
                    
                    # If this is more than the 5th mutation, warn but don't abort anymore
                    if mutating_calls > 5 and name not in {"set_cells", 
                                                          "apply_updates_and_reply",
                                                          "set_cell"}:
                        print(f"[{agent_id}] ⚠️ High # of single-cell mutations – consider batching.")
                        # NO hard stop any more

                # Invoke the Python function
                fn = None
                for t in self.tools:
                    if t["name"] == name:
                        fn = t["func"]
                        break
                
                if fn is None:
                    print(f"[{agent_id}] ❌ Function {name} not found in available tools")
                    # Add a compensating tool message with error
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps({"error": f"Function '{name}' is not available"})
                    })
                    yield ChatStep(
                        role="assistant",
                        content=f"Sorry, the function '{name}' is not available.",
                        usage=None
                    )
                    return
                
                print(f"[{agent_id}] 🧰 Executing {name}")
                
                # Add detailed logging for debugging tool calls
                print(f"[{agent_id}] 🔧 Tool: {name}, Args: {json.dumps(args, default=str)[:200]}...")
                
                try:
                    fn_start = time.time()
                    result = fn(**args)
                    fn_time = time.time() - fn_start
                    
                    print(f"[{agent_id}] ⏱️ Function executed in {fn_time:.2f}s")
                    
                    # Track repeated errors to prevent infinite loops
                    if isinstance(result, dict) and "error" in result:
                        error_key = f"{name}:{result.get('error', 'unknown')}"
                        error_count[error_key] = error_count.get(error_key, 0) + 1
                        print(f"[{agent_id}] ⚠️ Error in {name}: {result['error']} (count: {error_count[error_key]})")
                        
                        # Break infinite loops on repeated errors
                        if error_count[error_key] >= 3:
                            print(f"[{agent_id}] 🛑 Breaking loop - same error repeated {error_count[error_key]} times")
                            yield ChatStep(
                                role="assistant",
                                content=f"I'm having trouble with the {name} operation. The error '{result.get('message', result['error'])}' keeps occurring. Please check your request and try again with different parameters.",
                                usage=None
                            )
                            return
                    
                    # Yield a ChatStep for the tool result
                    yield ChatStep(role="tool", toolResult=result)
                    
                    # Add the required tool-result message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result)
                    })
                    
                    # Accumulate updates if provided
                    if isinstance(result, dict):
                        if "updates" in result and isinstance(result["updates"], list):
                            update_count = len(result["updates"])
                            print(f"[{agent_id}] 📊 Collected {update_count} updates from function result")
                            collected_updates.extend(result["updates"])
                        # Normalise single-cell result (handles keys 'new', 'new_value' or 'value')
                        elif "cell" in result:
                            print(f"[{agent_id}] 📝 Added single cell update to collected updates")
                            collected_updates.append(result)

                        # ---------- EARLY EXIT for single-shot pattern ----------
                        if "reply" in result:          # tool already returned the final answer
                            total_time = time.time() - start_time
                            print(f"[{agent_id}] ✅ Early exit via apply_updates_and_reply "
                                  f"in {total_time:.2f}s with {len(collected_updates)} updates")
                            
                            # Stream updates one by one BEFORE the final reply
                            if collected_updates:
                                for i, update in enumerate(collected_updates):
                                    yield ChatStep(
                                        role="tool", 
                                        content=f"Updating {update.get('cell', 'cell')}...",
                                        toolResult=update,
                                        toolCall=type('obj', (object,), {'name': 'set_cell'})()
                                    )
                                    # Small delay between updates for better visualization
                                    await asyncio.sleep(0.1)
                            
                            # Split final reply into smaller parts for streaming
                            reply = result['reply']
                            if len(reply) > 50:
                                parts = []
                                for sentence in reply.split('.'):
                                    if sentence.strip():
                                        parts.append(sentence.strip() + '.')
                                
                                # Yield each part separately for smooth streaming
                                for part in parts:
                                    yield ChatStep(role="assistant", content=f"\n{part}")
                            else:
                                yield ChatStep(role="assistant", content=f"\n{reply}")
                                
                            return
                    
                except Exception as e:
                    print(f"[{agent_id}] ❌ Error executing function {name}: {str(e)}")
                    # Add a compensating tool message with error
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps({"error": str(e)})
                    })
                    yield ChatStep(
                        role="assistant",
                        content=f"Sorry, I encountered an error: {e}",
                        usage=None
                    )
                    return
                
                loop_time = time.time() - loop_start
                print(f"[{agent_id}] ⏱️ Iteration {iterations} completed in {loop_time:.2f}s")
                
                # Continue the loop so the model can decide whether to call more functions or give a final answer
                continue
            
            # 2) No function call - model gave a direct answer
            elif msg.content:
                print(f"[{agent_id}] 💬 Model returned direct response, length: {len(msg.content)}")
                
                
                # Check for Groq Llama models function-call text format
                if isinstance(msg.content, str) and msg.content.lstrip().startswith("<function="):
                    function_match = re.search(r'<function=([a-zA-Z0-9_]+)[>,](.*)', msg.content.strip())
                    if function_match:
                        function_name = function_match.group(1)
                        payload_str = function_match.group(2)
                        
                        try:
                            # Grab text between first "{" and the last "}"
                            candidate = re.search(r'\{.*\}', payload_str, re.S)
                            payload_json = candidate.group(0) if candidate else "{}"
                            payload = json.loads(payload_json)
                            print(f"[{agent_id}] 🧰 Detected Groq function call to {function_name}")
                            
                            # Find the function
                            fn = next((t["func"] for t in self.tools if t["name"] == function_name), None)
                            if fn:
                                # Extract args if any
                                args = {}
                                if isinstance(payload, dict):
                                    # Handle apply_updates_and_reply or other function formats
                                    if function_name == "apply_updates_and_reply":
                                        args = payload
                                    elif "args" in payload:
                                        args = payload["args"]
                                    elif "arguments" in payload:
                                        args = payload["arguments"]
                                    else:
                                        args = payload
                                
                                # Execute the function and get result
                                fn_start = time.time()
                                result = fn(**args)
                                fn_time = time.time() - fn_start
                                print(f"[{agent_id}] ⏱️ Function executed in {fn_time:.2f}s")
                                
                                # Fake a "tool" step
                                yield ChatStep(role="tool", toolResult=result)
                                
                                # Early exit if reply is included
                                if isinstance(result, dict) and "reply" in result:
                                    total_time = time.time() - start_time
                                    print(f"[{agent_id}] ✅ Agent run completed in {total_time:.2f}s")
                                    yield ChatStep(
                                        role="assistant",
                                        content=result["reply"],
                                        usage=None
                                    )
                                    return
                                
                                # Continue the loop to get a final answer
                                continue
                            else:
                                print(f"[{agent_id}] ❌ Function {function_name} not found in available tools")
                                yield ChatStep(
                                    role="assistant",
                                    content=f"Sorry, the function '{function_name}' is not available.",
                                    usage=None
                                )
                                return
                        except (json.JSONDecodeError, Exception) as e:
                            print(f"[{agent_id}] ⚠️ Error processing function call string: {e}")
                            # Fall through to treat as regular text
                
                # Look for updates embedded in JSON
                if isinstance(msg.content, str):
                    # Try to extract JSON wrapped in ```json ... ``` or other code blocks
                    json_matches = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', msg.content)
                    
                    for json_str in json_matches:
                        try:
                            extracted_json = json.loads(json_str)
                            if isinstance(extracted_json, dict) and "reply" in extracted_json:
                                # We found a valid message structure, extract updates
                                updates = extracted_json.get("updates", [])
                                
                                if updates and isinstance(updates, list):
                                    print(f"[{agent_id}] 📄 Found {len(updates)} updates in extracted JSON")
                                    actually_applied_updates = []
                                    
                                    for update in updates:
                                        if "cell" in update and ("new_value" in update or "new" in update or "value" in update):
                                            cell = update["cell"]
                                            value = update.get("new_value", update.get("new", update.get("value")))
                                            
                                            # Validate cell reference before attempting to execute
                                            if not cell or not str(cell).strip():
                                                print(f"[{agent_id}] ⚠️ Skipping update with invalid cell reference: '{cell}'")
                                                continue
                                            
                                            print(f"[{agent_id}] 📝 Executing set_cell from JSON for {cell} = {value}")
                                            
                                            # Apply the update directly
                                            for t in self.tools:
                                                if t["name"] == "set_cell":
                                                    tool_result = t["func"](cell_ref=cell, value=value)
                                                    actually_applied_updates.append(tool_result)
                                                    break
                                    
                                    # Include the applied updates in the result, or fallback to collected_updates
                                    extracted_json["updates"] = actually_applied_updates if actually_applied_updates else collected_updates
                                    
                                    total_time = time.time() - start_time
                                    print(f"[{agent_id}] ✅ Agent run completed in {total_time:.2f}s with {len(extracted_json['updates'])} updates")
                                    
                                    yield ChatStep(
                                        role="assistant",
                                        content=extracted_json["reply"],
                                        usage=None
                                    )
                                    return
                        except json.JSONDecodeError as e:
                            print(f"[{agent_id}] ⚠️ Error parsing extracted JSON: {e}")
                
                # Attempt to parse JSON response if it starts with a brace
                if isinstance(msg.content, str) and msg.content.strip().startswith("{"):
                    try:
                        json_result = json.loads(msg.content)
                        
                        # Check if the JSON response is describing a JSON structure with updates
                        # but not actually executing the updates with tool calls
                        if "reply" in json_result and isinstance(json_result.get("updates"), list):
                            # Extract the updates from the JSON response
                            updates = json_result.get("updates", [])
                            
                            # Check if there are updates described in JSON but no tool calls were made to apply them
                            actually_applied_updates = []
                            print(f"[{agent_id}] 📄 Found {len(updates)} updates in direct JSON response")
                            
                            for update in updates:
                                if "cell" in update and ("new_value" in update or "new" in update or "value" in update):
                                    cell = update["cell"]
                                    value = update.get("new_value", update.get("new", update.get("value")))
                                    
                                    # Validate cell reference before attempting to execute
                                    if not cell or not str(cell).strip():
                                        print(f"[{agent_id}] ⚠️ Skipping update with invalid cell reference: '{cell}'")
                                        continue
                                    
                                    print(f"[{agent_id}] 📝 Executing set_cell from direct JSON for {cell} = {value}")
                                    
                                    # Apply the update directly
                                    tool_result = None
                                    for t in self.tools:
                                        if t["name"] == "set_cell":
                                            tool_result = t["func"](cell_ref=cell, value=value)
                                            actually_applied_updates.append(tool_result)
                                            break
                            
                            # Include the applied updates in the result
                            json_result["updates"] = actually_applied_updates if actually_applied_updates else collected_updates
                            
                            total_time = time.time() - start_time
                            print(f"[{agent_id}] ✅ Agent run completed in {total_time:.2f}s with {len(json_result['updates'])} updates")
                            
                            yield ChatStep(
                                role="assistant",
                                content=json_result["reply"],
                                usage=None
                            )
                            return
                    except json.JSONDecodeError:
                        # If we can't parse JSON, just treat it as a regular message
                        print(f"[{agent_id}] ℹ️ Could not parse response as JSON, treating as regular message")
                
                # Process as a regular message
                reply = msg.content.strip()
                
                total_time = time.time() - start_time
                print(f"[{agent_id}] ✅ Agent run completed in {total_time:.2f}s with {len(collected_updates)} updates")
                
                yield ChatStep(
                    role="assistant",
                    content=reply,
                    usage=None
                )
                return
        
        # If we get here, we've exceeded the maximum iterations
        total_time = time.time() - start_time
        print(f"[{agent_id}] ⚠️ Reached maximum iterations ({max_iterations}) after {total_time:.2f}s")
        
        # Add a system message to reset context for the next prompt
        messages.append({"role": "system",
                         "content": "Previous request exhausted tool iterations. "
                                    "Start a new plan from scratch."})
        
        yield ChatStep(
            role="assistant",
            content="[max-tool-iterations exceeded] I've reached the maximum number of operations allowed. Please simplify your request or break it into smaller steps."
        )
        return

    async def run(self, user_message: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Execute the tool-loop until the model produces a final answer.
        Returns { 'reply': str, 'updates': list }
        """
        collected_updates = []
        final: ChatStep | None = None
        
        async for step in self.run_iter(user_message, history):
            final = step          # remember the last thing we saw
            
            # Collect updates from tool results
            if step.role == "tool" and step.toolResult:
                if isinstance(step.toolResult, dict):
                    if "updates" in step.toolResult and isinstance(step.toolResult["updates"], list):
                        collected_updates.extend(step.toolResult["updates"])
                    elif "cell" in step.toolResult:
                        collected_updates.append(step.toolResult)
        
        # final must be the plain-text assistant answer
        if final and final.role == "assistant":
            # If we collected >1 single-cell updates, automatically batch them
            if len(collected_updates) > 1:
                # Import the batcher function
                from ..spreadsheet_engine.operations import batch_updates_from_single_calls
                
                # Check if we have multiple single-cell updates to batch
                single_cell_updates = [u for u in collected_updates if isinstance(u, dict) and "cell" in u]
                if len(single_cell_updates) > 1:
                    print(f"[BaseAgent] 🔄 Auto-batching {len(single_cell_updates)} single-cell updates")
                    # Note: We don't have direct sheet access here, batching will happen at router level
                    
            return {"reply": final.content or "", "updates": collected_updates}
        else:
            return {"reply": "Sorry, something went wrong.", "updates": collected_updates}

    def add_system_message(self, additional_message: str) -> None:
        """
        Add additional instruction to the system prompt.
        
        Args:
            additional_message: The message to add to the system prompt
        """
        self.system_prompt = f"{self.system_prompt}\n\n{additional_message}"

    def reset_system_prompt(self) -> None:
        """
        Reset the system prompt to its original state.
        This is useful when switching between agent modes to avoid prompt pollution.
        """
        if hasattr(self, '_original_prompt'):
            self.system_prompt = self._original_prompt
        
    def set_system_prompt(self, new_prompt: str) -> None:
        """
        Replace the current system prompt entirely.
        
        Args:
            new_prompt: The new system prompt to use
        """
        self.system_prompt = new_prompt

    async def stream_run(self, user_message: str, history: Optional[List[Dict[str, Any]]] = None) -> AsyncGenerator[ChatStep, None]:
        """
        Streaming version of the agent run with enhanced termination conditions.
        
        This method implements comprehensive safeguards to prevent infinite loops:
        1. Explicit finish_reason detection from LLM responses
        2. Content-based termination for natural stopping points
        3. Streaming timeout and token budget limits
        4. Enhanced circuit breaker logic for repeated errors
        5. Streaming metrics and repetition detection
        6. Improved tool call validation
        
        Args:
            user_message: The user's message to respond to
            history: Optional conversation history
            
        Yields:
            ChatStep objects with the assistant's response
        """
        agent_id = f"stream-agent-{int(time.time()*1000)}"
        print(f"[{agent_id}] 🤖 Starting streaming agent run with message length: {len(user_message)}")
        print(f"[{agent_id}] 🔧 Using LLM: {self.llm.__class__.__name__} - {getattr(self.llm, 'model', 'unknown')}")
        print(f"[{agent_id}] 🛠️ Available tools: {[tool['name'] for tool in self.tools]}")
        print(f"[{agent_id}] 📝 Message preview: {user_message[:150]}{'...' if len(user_message) > 150 else ''}")

        # Initialize enhanced retry manager and streaming metrics
        retry_manager = ToolCallRetryManager()
        streaming_metrics = StreamingMetrics()
        
        # Streaming safeguards configuration
        max_streaming_duration = float(os.getenv("MAX_STREAMING_DURATION", "60"))  # 60 seconds
        max_response_tokens = int(os.getenv("MAX_RESPONSE_TOKENS", "4000"))
        max_consecutive_empty_chunks = int(os.getenv("MAX_CONSECUTIVE_EMPTY_CHUNKS", "10"))
        max_content_repetition_ratio = float(os.getenv("MAX_CONTENT_REPETITION_RATIO", "0.7"))
        
        # Termination detection state
        consecutive_empty_chunks = 0
        content_history = []
        tokens_generated = 0
        natural_stopping_phrases = [
            "I hope this helps", "Let me know if you need", "Feel free to ask",
            "Is there anything else", "That's all", "I've completed",
            "The analysis is complete", "This concludes", "To summarize"
        ]
        
        # Prepare the basic message structure with system prompt
        print(f"[{agent_id}] 📋 Preparing system message")
        system_message = {"role": "system", "content": self.system_prompt}
        messages = [system_message]
        print(f"[{agent_id}] 💬 System prompt length: {len(self.system_prompt)} chars")
        
        # Add conversation history if provided
        if history:
            print(f"[{agent_id}] 📚 Adding {len(history)} history messages")
            messages.extend(history)
            
        # Add the current user message
        messages.append({"role": "user", "content": user_message})
        
        # Trim history to fit within token limits
        orig_message_count = len(messages)
        model_key = f"{self.llm.name}:{self.llm.model}"
        messages = trim_history(messages, system_message, None, model_key)
        if len(messages) < orig_message_count:
            print(f"[{agent_id}] ✂️ Trimmed history from {orig_message_count} to {len(messages)} messages")

        # Enhanced iteration and error tracking
        max_iterations = int(os.getenv("MAX_TOOL_ITERATIONS", "50"))
        iterations = 0
        collected_updates: list = []
        mutating_calls = 0
        error_count = {}
        mutating_tools = {
            "set_cell", "set_cells", "apply_updates_and_reply",
            "add_row", "add_column", "delete_row", "delete_column",
            "sort_range", "find_replace", "apply_scalar_to_row",
            "apply_scalar_to_column", "create_new_sheet"
        }
        final_text_buffer = ""
        start_time = time.time()
        
        # Enhanced debug flags
        debug_streaming = os.getenv("DEBUG_STREAMING", "0") == "1"
        debug_delta = os.getenv("DEBUG_STREAMING_DELTA", "0") == "1"
        debug_tools = os.getenv("DEBUG_STREAMING_TOOLS", "0") == "1"
        debug_termination = os.getenv("DEBUG_TERMINATION", "0") == "1"
        
        print(f"[{agent_id}] 🔄 Starting enhanced streaming loop with max_iterations={max_iterations}")
        print(f"[{agent_id}] ⏱️ Streaming safeguards: duration={max_streaming_duration}s, tokens={max_response_tokens}, empty_chunks={max_consecutive_empty_chunks}")
        print(f"[{agent_id}] 🐛 Debug flags: streaming={debug_streaming}, delta={debug_delta}, tools={debug_tools}, termination={debug_termination}")
        in_tool_calling_phase = True
        
        # Create tool function mapping for easy lookup
        tool_functions = {t["name"]: t["func"] for t in self.tools}
        
        # Main streaming loop with enhanced termination conditions
        while iterations < max_iterations:
            iterations += 1
            loop_start = time.time()
            elapsed_time = loop_start - start_time
            
            print(f"[{agent_id}] ⏱️ Iteration {iterations}/{max_iterations} (elapsed: {elapsed_time:.1f}s)")
            
            # ENHANCED TERMINATION CONDITIONS
            
            # 1. Check streaming timeout
            if elapsed_time > max_streaming_duration:
                print(f"[{agent_id}] ⏰ TERMINATION: Maximum streaming duration ({max_streaming_duration}s) exceeded")
                yield ChatStep(
                    role="assistant",
                    content="\n\n[Streaming timeout reached. Response may be incomplete.]"
                )
                return
            
            # 2. Check token budget
            if tokens_generated > max_response_tokens:
                print(f"[{agent_id}] 📊 TERMINATION: Token budget ({max_response_tokens}) exceeded")
                yield ChatStep(
                    role="assistant",
                    content="\n\n[Response limit reached.]"
                )
                return
            
            # 3. Check circuit breaker
            if retry_manager.is_circuit_broken():
                print(f"[{agent_id}] 🔥 TERMINATION: Circuit breaker activated due to repeated errors")
                yield ChatStep(
                    role="assistant",
                    content="I'm having trouble with tool calls and need to stop to prevent errors. Let me help you with a direct response instead."
                )
                return
            
            # 4. Check consecutive empty chunks
            if consecutive_empty_chunks > max_consecutive_empty_chunks:
                print(f"[{agent_id}] 🔄 TERMINATION: Too many consecutive empty chunks ({consecutive_empty_chunks})")
                yield ChatStep(
                    role="assistant",
                    content="\n\n[Stream appears to have stalled.]"
                )
                return
            
            # 5. Check content repetition
            if len(content_history) > 5:
                recent_content = " ".join(content_history[-5:])
                if len(recent_content) > 50:
                    unique_words = len(set(recent_content.split()))
                    total_words = len(recent_content.split())
                    repetition_ratio = 1 - (unique_words / total_words) if total_words > 0 else 0
                    
                    if repetition_ratio > max_content_repetition_ratio:
                        print(f"[{agent_id}] 🔄 TERMINATION: High content repetition detected ({repetition_ratio:.2f})")
                        yield ChatStep(
                            role="assistant",
                            content="\n\n[Detected repetitive content, stopping generation.]"
                        )
                        return
            
            # Initialize streaming tool call handler for this iteration
            tool_handler = StreamingToolCallHandler()
            current_content = ""
            previous_content = ""
            
            # Call the LLM model with streaming enabled
            print(f"[{agent_id}] 🔌 Calling LLM model in streaming mode: {self.llm.model}")
            
            try:
                # Sanitize legacy fields for LLM compatibility
                for m in messages:
                    m.pop("executed_tools", None)
                    if self.llm.name in {"openai", "groq"} and "function_call" in m and "tool_calls" not in m:
                        m["tool_calls"] = [{
                            "id": "auto-" + str(time.time_ns()),
                            "type": "function",
                            "function": m.pop("function_call")
                        }]
                
                # Get the stream object from llm.chat
                stream = self.llm.chat(
                    messages=_dicts_to_messages(messages),
                    stream=True,
                    tools=[_serialize_tool(t) for t in self.tools] if self.llm.supports_tool_calls else None,
                    temperature=None,
                    max_tokens=min(max_response_tokens - tokens_generated, 1000)  # Respect remaining budget
                )
                
                # Ensure we have an async generator
                import inspect
                if inspect.isawaitable(stream) and not inspect.isasyncgen(stream):
                    print(f"[{agent_id}] ⚠️ Provider returned a coroutine instead of an async generator - converting")
                    stream_result = await stream
                    async def _one_shot():
                        yield stream_result
                    stream = _one_shot()
                
                # Enhanced streaming metrics tracking
                chunk_count = 0
                tool_call_chunks = 0
                content_chunks = 0
                has_received_content = False
                has_received_finish_reason = False
                iteration_start_time = time.time()
                
                # Process streaming chunks with enhanced termination detection
                async for chunk in stream:
                    chunk_count += 1
                    chunk_time = time.time()
                    iteration_elapsed = chunk_time - iteration_start_time
                    
                    # Track streaming metrics
                    streaming_metrics.log_chunk("received", 1)
                    
                    if debug_streaming:
                        print(f"[{agent_id}] 📦 Chunk #{chunk_count}: {type(chunk)} (iteration_time: {iteration_elapsed:.2f}s)")
                    
                    # ENHANCED FINISH REASON DETECTION
                    finish_reason = None
                    if hasattr(chunk, "choices") and chunk.choices:
                        choice = chunk.choices[0]
                        if hasattr(choice, "finish_reason") and choice.finish_reason:
                            finish_reason = choice.finish_reason
                            has_received_finish_reason = True
                            if debug_termination:
                                print(f"[{agent_id}] 🏁 FINISH REASON detected: {finish_reason}")
                    
                    # Check if this is an OpenAI-style response
                    if hasattr(chunk, "choices") and chunk.choices:
                        delta = chunk.choices[0].delta
                        
                        if debug_delta:
                            print(f"[{agent_id}] 🔍 Processing OpenAI-style delta: {delta}")
                        
                        # Process tool calls using the enhanced handler
                        completed_calls = tool_handler.process_delta(delta)
                        
                        # Yield keep-alive chunks during tool call accumulation
                        keep_alive_chunks = tool_handler.get_keep_alive_chunks()
                        for keep_alive_chunk in keep_alive_chunks:
                            if debug_streaming:
                                print(f"[{agent_id}] 💓 Sending keep-alive chunk")
                            yield ChatStep(role="assistant", content="")
                        
                        if completed_calls:
                            tool_call_chunks += 1
                            consecutive_empty_chunks = 0  # Reset on successful tool call
                            if debug_tools:
                                print(f"[{agent_id}] 🔧 Got {len(completed_calls)} completed tool calls")
                        
                        # Execute completed tool calls with enhanced validation
                        for tool_call in completed_calls:
                            name = tool_call['name']
                            args = tool_call['arguments']
                            tool_call_id = tool_call['id']
                            
                            print(f"[{agent_id}] 🔧 Executing tool call: {name}")
                            
                            # ENHANCED TOOL CALL VALIDATION
                            validation_result = self._validate_tool_call(name, args, retry_manager, agent_id)
                            if not validation_result["valid"]:
                                if validation_result["should_retry"]:
                                    messages.append({
                                        "role": "system",
                                        "content": validation_result["retry_prompt"]
                                    })
                                    continue
                                else:
                                    messages.append({
                                        "role": "system",
                                        "content": validation_result["stop_message"]
                                    })
                                    continue
                            
                            # Execute the validated tool call
                            try:
                                tool_fn = tool_functions.get(name)
                                if tool_fn:
                                    if name in mutating_tools:
                                        mutating_calls += 1
                                        print(f"[{agent_id}] ✏️ Mutating call #{mutating_calls}: {name}")
                                    
                                    execution_start = time.time()
                                    
                                    if isinstance(args, dict):
                                        result = tool_fn(**args)
                                    elif isinstance(args, list):
                                        result = tool_fn(*args)
                                    else:
                                        result = tool_fn(args)
                                    
                                    execution_time = time.time() - execution_start
                                    
                                    if debug_tools:
                                        print(f"[{agent_id}] ✅ Tool {name} executed in {execution_time:.3f}s")
                                    
                                    # Add tool call and result to messages
                                    messages.append({
                                        "role": "assistant",
                                        "tool_calls": [{
                                            "id": tool_call_id,
                                            "type": "function",
                                            "function": {"name": name, "arguments": json.dumps(args)}
                                        }]
                                    })
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call_id,
                                        "content": json.dumps(result) if result is not None else "null"
                                    })
                                    
                                    yield ChatStep(role="tool", toolCall={"name": name, "args": args}, toolResult=result)
                                    consecutive_empty_chunks = 0  # Reset on successful tool execution
                                    
                                else:
                                    print(f"[{agent_id}] ❌ Unknown tool: {name}")
                                    
                            except Exception as e:
                                print(f"[{agent_id}] ❌ Tool execution error: {e}")
                                error_msg = str(e)
                                
                                if retry_manager.should_retry(name, error_msg):
                                    retry_prompt = retry_manager.get_retry_prompt(name, error_msg)
                                    messages.append({
                                        "role": "system",
                                        "content": f"Tool execution failed: {error_msg}. {retry_prompt}"
                                    })
                                else:
                                    yield ChatStep(
                                        role="assistant",
                                        content=f"I encountered an error with {name}: {error_msg}. Let me try a different approach."
                                    )
                        
                        # Handle regular content with enhanced termination detection
                        if hasattr(delta, "content") and delta.content:
                            content_chunks += 1
                            new_content = delta.content
                            has_received_content = True
                            consecutive_empty_chunks = 0  # Reset on content
                            
                            # Track content for repetition detection
                            content_history.append(new_content)
                            if len(content_history) > 20:  # Keep sliding window
                                content_history.pop(0)
                            
                            # Update token count (rough estimation)
                            tokens_generated += len(new_content.split())
                            
                            if debug_streaming:
                                print(f"[{agent_id}] 💬 Content delta #{content_chunks}: '{new_content}' (tokens: {tokens_generated})")
                            
                            if in_tool_calling_phase:
                                in_tool_calling_phase = False
                                print(f"[{agent_id}] 💬 Transitioning to final answer")
                            
                            # Check for natural stopping phrases
                            if any(phrase.lower() in new_content.lower() for phrase in natural_stopping_phrases):
                                if debug_termination:
                                    print(f"[{agent_id}] 🏁 Natural stopping phrase detected in content")
                            
                            yield ChatStep(role="assistant", content=new_content)
                        
                        # Handle empty content chunks
                        elif not hasattr(delta, "content") or not delta.content:
                            consecutive_empty_chunks += 1
                            if debug_termination:
                                print(f"[{agent_id}] ⭕ Empty chunk #{consecutive_empty_chunks}")
                    
                    # Handle AIResponse format with similar termination logic
                    elif hasattr(chunk, 'content') or hasattr(chunk, 'tool_calls'):
                        if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                            consecutive_empty_chunks = 0
                            # Process AIResponse tool calls (similar to OpenAI format)
                            for tool_call in chunk.tool_calls:
                                if hasattr(tool_call, 'name') and hasattr(tool_call, 'args'):
                                    name = tool_call.name
                                    args = tool_call.args
                                    tool_call_id = getattr(tool_call, 'id', f"airesponse-{int(time.time_ns())}")
                                    
                                    print(f"[{agent_id}] 🔧 Executing AIResponse tool call: {name}")
                                    
                                    # Apply same validation as OpenAI format
                                    validation_result = self._validate_tool_call(name, args, retry_manager, agent_id)
                                    if not validation_result["valid"]:
                                        if validation_result["should_retry"]:
                                            messages.append({
                                                "role": "system",
                                                "content": validation_result["retry_prompt"]
                                            })
                                            continue
                                        else:
                                            continue
                                    
                                    # Execute tool call (same logic as OpenAI format)
                                    try:
                                        tool_fn = tool_functions.get(name)
                                        if tool_fn:
                                            if name in mutating_tools:
                                                mutating_calls += 1
                                            
                                            execution_start = time.time()
                                            
                                            if isinstance(args, dict):
                                                result = tool_fn(**args)
                                            elif isinstance(args, list):
                                                result = tool_fn(*args)
                                            else:
                                                result = tool_fn(args)
                                            
                                            execution_time = time.time() - execution_start
                                            
                                            if debug_tools:
                                                print(f"[{agent_id}] ✅ AIResponse tool {name} executed in {execution_time:.3f}s")
                                            
                                            messages.append({
                                                "role": "assistant",
                                                "tool_calls": [{
                                                    "id": tool_call_id,
                                                    "type": "function",
                                                    "function": {"name": name, "arguments": json.dumps(args)}
                                                }]
                                            })
                                            messages.append({
                                                "role": "tool",
                                                "tool_call_id": tool_call_id,
                                                "content": json.dumps(result) if result is not None else "null"
                                            })
                                            
                                            yield ChatStep(role="tool", toolCall={"name": name, "args": args}, toolResult=result)
                                    except Exception as e:
                                        print(f"[{agent_id}] ❌ AIResponse tool execution error: {e}")
                                        yield ChatStep(
                                            role="assistant",
                                            content=f"I encountered an error with {name}: {str(e)}. Let me try a different approach."
                                        )
                        
                        if hasattr(chunk, 'content') and chunk.content:
                            content_chunks += 1
                            new_content = chunk.content
                            has_received_content = True
                            consecutive_empty_chunks = 0
                            
                            # Track content and tokens
                            content_history.append(new_content)
                            if len(content_history) > 20:
                                content_history.pop(0)
                            tokens_generated += len(new_content.split())
                            
                            if debug_streaming:
                                print(f"[{agent_id}] 💬 Content delta #{content_chunks} (AIResponse): '{new_content}'")
                            
                            if in_tool_calling_phase:
                                in_tool_calling_phase = False
                                print(f"[{agent_id}] 💬 Transitioning to final answer")
                            
                            yield ChatStep(role="assistant", content=new_content)
                        else:
                            consecutive_empty_chunks += 1
                
                # POST-STREAM TERMINATION ANALYSIS
                print(f"[{agent_id}] 📊 Stream iteration completed: chunks={chunk_count}, content_chunks={content_chunks}, tool_chunks={tool_call_chunks}")
                print(f"[{agent_id}] 📊 Termination analysis: has_content={has_received_content}, has_finish_reason={has_received_finish_reason}, empty_chunks={consecutive_empty_chunks}")
                
                # Decide whether to continue or terminate based on multiple factors
                should_terminate = False
                termination_reason = ""
                
                # 1. Explicit finish reason from LLM
                if has_received_finish_reason:
                    should_terminate = True
                    termination_reason = "LLM indicated completion via finish_reason"
                
                # 2. No content generated and no tool calls in this iteration
                elif not has_received_content and tool_call_chunks == 0:
                    should_terminate = True
                    termination_reason = "No content or tool calls generated"
                
                # 3. Only received empty chunks
                elif chunk_count > 0 and content_chunks == 0 and tool_call_chunks == 0:
                    should_terminate = True
                    termination_reason = "Only empty chunks received"
                
                # 4. Natural stopping point detection
                elif has_received_content and len(content_history) > 0:
                    recent_content = " ".join(content_history[-3:]).lower()
                    if any(phrase.lower() in recent_content for phrase in natural_stopping_phrases):
                        should_terminate = True
                        termination_reason = "Natural stopping phrase detected"
                
                # 5. Content appears complete (ends with punctuation and contains complete thoughts)
                elif has_received_content and len(content_history) > 0:
                    last_content = content_history[-1].strip()
                    if last_content.endswith(('.', '!', '?', ':', ';')) and len(last_content) > 10:
                        # Additional check: does this look like a complete response?
                        if any(indicator in last_content.lower() for indicator in 
                               ['complete', 'done', 'finished', 'ready', 'hope this helps', 'let me know']):
                            should_terminate = True
                            termination_reason = "Content appears complete"
                
                if should_terminate:
                    print(f"[{agent_id}] 🏁 TERMINATION: {termination_reason}")
                    break
                else:
                    print(f"[{agent_id}] 🔄 Continuing to next iteration")
                    
            except Exception as e:
                print(f"[{agent_id}] ❌ Error in LLM call: {str(e)}")
                import traceback
                traceback.print_exc()
                yield ChatStep(role="assistant", content=f"\nError communicating with AI service: {str(e)}")
                return
        
        # Final status update with enhanced metrics
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"[{agent_id}] ✅ Enhanced streaming loop completed:")
        print(f"[{agent_id}]   - Duration: {elapsed:.2f}s")
        print(f"[{agent_id}]   - Iterations: {iterations}")
        print(f"[{agent_id}]   - Mutations: {mutating_calls}")
        print(f"[{agent_id}]   - Tokens generated: {tokens_generated}")
        print(f"[{agent_id}]   - Content chunks: {len(content_history)}")
        
        # Log final streaming metrics
        streaming_metrics.log_completion(elapsed, tokens_generated, iterations)

    def _validate_tool_call(self, name: str, args: Any, retry_manager: ToolCallRetryManager, agent_id: str) -> Dict[str, Any]:
        """
        Enhanced tool call validation with comprehensive checks.
        
        Returns:
            Dict with validation result: {"valid": bool, "should_retry": bool, "retry_prompt": str, "stop_message": str}
        """
        # Early validation - reject completely empty or malformed calls
        if not args or (isinstance(args, dict) and len(args) == 0):
            print(f"[{agent_id}] ⚠️ Rejecting tool call with completely empty arguments")
            error_msg = "Empty arguments provided"
            if retry_manager.should_retry(name, error_msg):
                return {
                    "valid": False,
                    "should_retry": True,
                    "retry_prompt": retry_manager.get_retry_prompt(name, error_msg)
                }
            else:
                return {
                    "valid": False,
                    "should_retry": False,
                    "stop_message": f"STOP: Tool {name} has failed multiple times with empty arguments. Do NOT call this tool again without proper arguments. Provide a text response instead."
                }
        
        # Specific validation for problematic tools
        if name == "set_cell":
            if isinstance(args, dict):
                cell = args.get('cell', '') or args.get('cell_ref', '')
                value = args.get('value', '')
                if not cell or not str(cell).strip():
                    print(f"[{agent_id}] ⚠️ Rejecting set_cell with empty cell reference")
                    error_msg = "Empty cell reference"
                    if retry_manager.should_retry(name, error_msg):
                        return {
                            "valid": False,
                            "should_retry": True,
                            "retry_prompt": retry_manager.get_retry_prompt(name, error_msg)
                        }
                    else:
                        return {
                            "valid": False,
                            "should_retry": False,
                            "stop_message": "STOP: set_cell requires a valid cell reference like 'A1'. Do not call set_cell with empty arguments. Provide a text response instead."
                        }
        
        elif name == "apply_updates_and_reply":
            if not args or not isinstance(args, dict):
                args = {}
            
            updates = args.get('updates', [])
            
            if not updates or not isinstance(updates, list) or len(updates) == 0:
                print(f"[{agent_id}] ⚠️ Empty updates for apply_updates_and_reply")
                error_msg = "Empty updates array"
                if retry_manager.should_retry(name, error_msg):
                    return {
                        "valid": False,
                        "should_retry": True,
                        "retry_prompt": retry_manager.get_retry_prompt(name, error_msg)
                    }
                else:
                    return {
                        "valid": False,
                        "should_retry": False,
                        "stop_message": "I'll use individual cell updates instead of batch updates."
                    }
            
            # Validate each update in the array
            valid_updates = []
            for j, update in enumerate(updates):
                if isinstance(update, dict) and 'cell' in update and 'value' in update:
                    valid_updates.append(update)
                else:
                    print(f"[{agent_id}] ⚠️ Invalid update format {j}: {update}")
            
            if len(valid_updates) != len(updates):
                print(f"[{agent_id}] ⚠️ Some updates were invalid, using {len(valid_updates)}/{len(updates)}")
                args['updates'] = valid_updates
            
            if not valid_updates:
                error_msg = "No valid updates found"
                if retry_manager.should_retry(name, error_msg):
                    return {
                        "valid": False,
                        "should_retry": True,
                        "retry_prompt": retry_manager.get_retry_prompt(name, error_msg)
                    }
                else:
                    return {
                        "valid": False,
                        "should_retry": False,
                        "stop_message": "Skipping tool call due to invalid updates"
                    }
        
        elif name == "set_cells":
            if not args or not isinstance(args, dict):
                args = {}
            
            if 'updates' not in args or not isinstance(args['updates'], list):
                error_msg = "Missing or invalid updates parameter"
                print(f"[{agent_id}] ❌ set_cells missing parameters: {error_msg}")
                if retry_manager.should_retry(name, error_msg):
                    return {
                        "valid": False,
                        "should_retry": True,
                        "retry_prompt": retry_manager.get_retry_prompt(name, error_msg)
                    }
                else:
                    return {
                        "valid": False,
                        "should_retry": False,
                        "stop_message": "set_cells requires a valid updates array"
                    }
        
        # Handle parsing errors
        if isinstance(args, dict) and 'error' in args:
            error_msg = args.get('error', 'Unknown error')
            print(f"[{agent_id}] ❌ Tool call parsing error: {error_msg}")
            
            if retry_manager.should_retry(name, error_msg):
                return {
                    "valid": False,
                    "should_retry": True,
                    "retry_prompt": retry_manager.get_retry_prompt(name, error_msg)
                }
            else:
                return {
                    "valid": False,
                    "should_retry": False,
                    "stop_message": f"Sorry, I'm having trouble with the {name} tool. Let me try a different approach."
                }
        
        # If we get here, the tool call passed validation
        return {"valid": True, "should_retry": False, "retry_prompt": "", "stop_message": ""}
