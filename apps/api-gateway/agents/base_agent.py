from __future__ import annotations
from typing import List, Dict, Any, Optional, AsyncGenerator
import os
import asyncio
import json
import re
import time
import traceback
from dotenv import load_dotenv
from .tools import TOOL_CATALOG
from chat.token_utils import trim_history
from agents.json_utils import safe_json_loads
from llm.base import LLMClient
from pydantic import BaseModel
from db.prompts import get_active_prompt
from types import SimpleNamespace
from llm.chat_types import AIResponse, Message
from llm.catalog import normalise, normalize_model_name  # Import the normalize_model_name function
from llm import wrap_stream_with_guard

load_dotenv()
MAX_RETRIES = 3
RETRY_DELAY = 1.0
MAX_TOKENS = 4096
# Token limits for various models
MODEL_LIMITS = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 32_768,
    "o4-mini": 32_768,
    "o4-preview": 128_000,
    "gpt-4-turbo": 128_000,
    "llama-3-70b": 8_192,
    "llama-3-8b": 8_192,
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

class ChatStep(BaseModel):
    role: str                       # "assistant" | "tool"
    content: str | None = None      # natural-language text
    toolCall: dict | None = None    # {name, args}
    toolResult: Any | None = None   # dict or list or any value returned by Python fn
    usage: dict | None = None       # token counts etc.

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
        Parameters
        ----------
        fallback_prompt :
            Hard-coded constant kept as last-resort safety valve.
        agent_mode :
            When provided we fetch the *active* prompt for that mode
            from Supabase with a 60 s TTL LRU cache.
        kwargs :
            Additional parameters that can be passed to the agent.
            sheet_context: Optional runtime sheet context to append to the prompt.
        """
        self.llm = llm
        self.tools = tools

        if agent_mode:
            try:
                base_prompt = get_active_prompt(agent_mode)
            except Exception as e:
                # Don't crash the session – fall back silently and log.
                print(f"⚠️  Prompt DB lookup failed for mode={agent_mode}: {e}")
                base_prompt = fallback_prompt
        else:
            base_prompt = fallback_prompt

        # Allow caller to pass an optional runtime context.
        sheet_ctx: str | None = kwargs.pop('sheet_context', None)

        # Concatenate keeping a blank line separator so formatting is stable.
        self.system_prompt = base_prompt.strip()
        if sheet_ctx:
            self.system_prompt += f"\n\n{sheet_ctx.strip()}"

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

        # Allow many small tool calls without bailing out too early (env: MAX_TOOL_ITERATIONS, default 10)
        max_iterations = int(os.getenv("MAX_TOOL_ITERATIONS", "10"))
        iterations = 0
        collected_updates: list = []
        mutating_calls = 0
        mutating_tools = {
            "set_cell", "set_cells", "apply_updates_and_reply",
            "add_row", "add_column", "delete_row", "delete_column",
            "sort_range", "find_replace", "apply_scalar_to_row",
            "apply_scalar_to_column", "create_new_sheet"
        }
        
        print(f"[{agent_id}] 🔄 Starting tool loop with max_iterations={max_iterations}")
        
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
            
            # 1) Did the model pick a function?
            if msg.function_call:
                name = msg.function_call.name
                try:
                    # Guard against empty-dict / None
                    raw = msg.function_call.arguments
                    if raw in ("{}", "null", "", None):
                        print(f"[{agent_id}] ❌ Empty arguments for function call: {name}")
                        tool_id = (msg.tool_calls[0].id if hasattr(msg, "tool_calls") and msg.tool_calls else None)
                        # 1) tell Claude why it failed, 2) satisfy the protocol
                        messages.extend([
                            {"role": "tool", "tool_call_id": tool_id,
                            "content": json.dumps({"error": "empty-args"})},
                            {"role": "assistant",
                             "content": f"Function call `{name}` had empty arguments. "
                                    "Please resend the call with valid JSON arguments."}
                        ])
                        continue        # go to next iteration instead of aborting
                    
                    try:
                        # First try normal parsing
                        args = safe_json_loads(raw)
                    except ValueError as e:
                        print(f"[{agent_id}] ❌ Error parsing function arguments: {str(e)}")
                        
                        try:
                            # lenient fallback: remove line-continuations and trailing commas
                            cleaned = re.sub(r'\\\s*\n', '', raw)           # 1) unwrap "\\↵"
                            cleaned = re.sub(r',\s*}', '}', cleaned)        # 2) strip ", }"
                            args = safe_json_loads(cleaned)
                        except ValueError:
                            # If still fails, ask model to retry
                            messages.append(
                                {"role": "assistant",
                                 "content": f"Function call `{name}` had invalid JSON arguments. "
                                            "Please resend the call with valid JSON arguments."})
                            continue        # go to next iteration instead of aborting
                    
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
                    
                    # If this is more than the first mutation and not a set_cells call, abort
                    if mutating_calls > 1 and name not in {"set_cells", "apply_updates_and_reply"}:
                        print(f"[{agent_id}] ⛔ Too many mutating calls. Use set_cells for batch updates.")
                        yield ChatStep(
                            role="assistant",
                            content="Error: You should use a single set_cells call to make multiple updates. Please try again with a single batch operation."
                        )
                        return

                # Invoke the Python function
                fn = next(t["func"] for t in self.tools if t["name"] == name)
                print(f"[{agent_id}] 🧰 Executing {name} with args: {json.dumps(args)[:100]}...")
                
                fn_start = time.time()
                result = fn(**args)
                fn_time = time.time() - fn_start
                
                print(f"[{agent_id}] ⏱️ Function executed in {fn_time:.2f}s")
                
                # Yield a ChatStep for the tool result
                yield ChatStep(role="tool", toolResult=result)
                
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
                        yield ChatStep(
                            role="assistant",
                            content=result["reply"],
                            usage=getattr(response.usage, "model_dump", lambda: None)() if getattr(response, "usage", None) else None
                        )
                        return
                
                # -------- NEW: add the required tool-result message --------
                call_id = None
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    call_id = getattr(msg.tool_calls[0], "id", None)
                if call_id is None:                     # fallback
                    call_id = f"call_{int(time.time()*1000)}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(result)
                })
                
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
                                        usage=getattr(response.usage, "model_dump", lambda: None)() if getattr(response, "usage", None) else None
                                    )
                                    return
                                
                                # Continue the loop to get a final answer
                                continue
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
                                        usage=getattr(response.usage, "model_dump", lambda: None)() if getattr(response, "usage", None) else None
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
                                usage=getattr(response.usage, "model_dump", lambda: None)() if getattr(response, "usage", None) else None
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
                    usage=getattr(response.usage, "model_dump", lambda: None)() if getattr(response, "usage", None) else None
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

    async def stream_run(self, user_message: str, history: Optional[List[Dict[str, Any]]] = None) -> AsyncGenerator[str, None]:
        """
        Execute the tool-loop in streaming mode, yielding text chunks as they are generated.
        
        Args:
            user_message: The user message to process
            history: Optional conversation history
            
        Yields:
            Text chunks of the assistant's response
        """
        agent_id = f"stream-agent-{int(time.time()*1000)}"
        print(f"[{agent_id}] 🤖 Starting streaming agent run with message length: {len(user_message)}")
        
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

        # Allow many small tool calls without bailing out too early
        max_iterations = int(os.getenv("MAX_TOOL_ITERATIONS", "10"))
        iterations = 0
        collected_updates: list = []
        mutating_calls = 0
        mutating_tools = {
            "set_cell", "set_cells", "apply_updates_and_reply",
            "add_row", "add_column", "delete_row", "delete_column",
            "sort_range", "find_replace", "apply_scalar_to_row",
            "apply_scalar_to_column", "create_new_sheet"
        }
        final_text_buffer = ""
        start_time = time.time()
        
        print(f"[{agent_id}] 🔄 Starting streaming tool loop with max_iterations={max_iterations}")
        in_tool_calling_phase = True
        
        while iterations < max_iterations:
            iterations += 1
            loop_start = time.time()
            print(f"[{agent_id}] ⏱️ Iteration {iterations}/{max_iterations}")
            
            # Call the LLM model with streaming enabled
            print(f"[{agent_id}] 🔌 Calling LLM model in streaming mode: {self.llm.model}")
            
            try:
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
                
                # Setup for collecting the streaming response
                current_content = ""
                previous_content = ""  # Track previous content to calculate delta
                function_name = None
                function_args = ""
                is_function_call = False
                current_tool_calls = {}  # Track accumulating tool calls
                
                # Get the stream object from llm.chat
                max_resp_tokens = int(os.getenv("MAX_RESPONSE_TOKENS", "4000"))
                stream = self.llm.chat(
                    messages=_dicts_to_messages(messages),
                    stream=True,
                    tools=[_serialize_tool(t) for t in self.tools] if self.llm.supports_tool_calls else None,
                    temperature=None,  # let the per-model filter decide
                    max_tokens=max_resp_tokens
                )
                
                # ――― guard rail ―――
                import inspect
                if inspect.isawaitable(stream) and not inspect.isasyncgen(stream):
                    # somebody returned a coroutine by mistake – await it once & wrap
                    print(f"[{agent_id}] ⚠️ Provider returned a coroutine instead of an async generator - converting")
                    stream_result = await stream
                    async def _one_shot():
                        yield stream_result
                    stream = _one_shot()
                # ――― end guard rail ―――
                
                # Wrap the stream with our guard to protect against infinite loops
                guarded_stream = wrap_stream_with_guard(stream)
                
                # Instead of awaiting the generator, iterate through it with async for
                async for chunk in guarded_stream:
                    # Check if this is an AIResponse or OpenAI format
                    if hasattr(chunk, "choices") and chunk.choices:
                        delta = chunk.choices[0].delta
                        
                        # Check if this is the start of a function call
                        if hasattr(delta, "function_call") and delta.function_call and not is_function_call:
                            is_function_call = True
                            function_name = delta.function_call.name
                            print(f"[{agent_id}] 🔧 Starting function call: {function_name}")
                        
                        # Accumulate function arguments
                        if is_function_call and hasattr(delta, "function_call") and delta.function_call and hasattr(delta.function_call, "arguments") and delta.function_call.arguments:
                            function_args += delta.function_call.arguments
                        
                        # Accumulate content for text response
                        if hasattr(delta, "content") and delta.content:
                            # Get just the new content (delta)
                            new_content = delta.content
                            current_content += new_content
                            
                            if in_tool_calling_phase:
                                # We've transitioned from tool calling to final answer
                                in_tool_calling_phase = False
                                print(f"[{agent_id}] 💬 Transitioning to final answer")
                            
                            # Only yield content chunks, not function calls
                            yield new_content
                    else:
                        # Handle AIResponse format
                        if hasattr(chunk, "content") and chunk.content:
                            # Handle both string and non-string content
                            content_chunk = chunk.content
                            # Check if content is a string before trying to process it as one
                            if isinstance(content_chunk, str):
                                if not current_content and not in_tool_calling_phase:
                                    in_tool_calling_phase = False
                                    print(f"[{agent_id}] 💬 Transitioning to final answer (AIResponse)")
                                
                                # Calculate the delta/new content only
                                if content_chunk.startswith(current_content):
                                    # Most LLM providers send the full content each time
                                    # Extract only the new part
                                    new_content = content_chunk[len(current_content):]
                                    current_content = content_chunk
                                    
                                    # Only yield if there's actually new content
                                    if new_content:
                                        yield new_content
                                else:
                                    # If we can't determine the delta for some reason, 
                                    # yield the whole chunk but update current_content
                                    current_content = content_chunk
                                    yield content_chunk
                            else:
                                # Handle non-string content (log it but don't yield)
                                print(f"[{agent_id}] ⚠️ Non-string content received: {type(content_chunk)}")
                        
                        if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                            is_function_call = True
                            first_tool = chunk.tool_calls[0]
                            function_name = first_tool.name
                            function_args = json.dumps(first_tool.args)
                            print(f"[{agent_id}] 🔧 Starting function call (AIResponse): {function_name}")
                
                # Construct the complete message from gathered chunks
                if is_function_call:
                    msg = {
                        "role": "assistant",
                        "function_call": {
                            "name": function_name,
                            "arguments": function_args
                        }
                    }
                else:
                    msg = {"role": "assistant", "content": current_content}
                    final_text_buffer += current_content
                
                # Add to messages for context
                messages.append(msg)
                
                print(f"[{agent_id}] ⏱️ LLM response received: {'function_call' if is_function_call else 'text'}")
                
            except Exception as e:
                print(f"[{agent_id}] ❌ Error in LLM call: {str(e)}")
                yield f"\nError communicating with AI service: {str(e)}"
                return
            
            # If it's a function call, process it
            if is_function_call and function_name:
                try:
                    # Parse function arguments
                    try:
                        args = safe_json_loads(function_args)
                    except ValueError as e:
                        print(f"[{agent_id}] ❌ Error parsing function arguments: {str(e)}")
                        yield f"\nSorry, I encountered an error processing your request. Please try again with simpler instructions."
                        return
                    
                    # Check mutating call limits
                    if function_name in mutating_tools:
                        mutating_calls += 1
                        print(f"[{agent_id}] ✏️ Mutating call #{mutating_calls}: {function_name}")
                        
                        # If this is more than the first mutation and not a set_cells call, abort
                        if mutating_calls > 1 and function_name not in {"set_cells", "apply_updates_and_reply"}:
                            print(f"[{agent_id}] ⛔ Too many mutating calls. Use set_cells for batch updates.")
                            yield "\nError: You should use a single set_cells call to make multiple updates."
                            return
                    
                    # Find the function
                    fn = next(t["func"] for t in self.tools if t["name"] == function_name)
                    print(f"[{agent_id}] 🧰 Executing {function_name}")
                    
                    # Execute the function
                    fn_start = time.time()
                    result = fn(**args)
                    fn_time = time.time() - fn_start
                    print(f"[{agent_id}] ⏱️ Function executed in {fn_time:.2f}s")
                    
                    # Collect updates
                    if isinstance(result, dict):
                        if "updates" in result and isinstance(result["updates"], list):
                            collected_updates.extend(result["updates"])
                        elif "cell" in result:
                            collected_updates.append(result)
                            
                        # ---------- EARLY EXIT for single-shot pattern ----------
                        if "reply" in result:          # tool already returned the final answer
                            total_time = time.time() - start_time
                            print(f"[{agent_id}] ✅ Early exit via apply_updates_and_reply "
                                  f"in {total_time:.2f}s with {len(collected_updates)} updates")
                            yield f"\n{result['reply']}"
                            return
                    
                    # -------- NEW: add the required tool-result message --------
                    call_id = f"call_{int(time.time()*1000)}"
                    if is_function_call and function_name:
                        # Try to extract the tool call ID from function_call/delta
                        for tc_data in current_tool_calls.values() if 'current_tool_calls' in locals() else []:
                            if tc_data.get("name") == function_name:
                                call_id = tc_data.get("id", call_id)
                                break

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result)
                    })
                    
                    # Continue the loop for another iteration
                    continue
                    
                except Exception as e:
                    print(f"[{agent_id}] ❌ Error executing function: {str(e)}")
                    traceback.print_exc()
                    yield f"\nError executing {function_name}: {str(e)}"
                    return
            
            # If we got a final text answer not a function call, we're done
            if not is_function_call and current_content:
                total_time = time.time() - start_time
                print(f"[{agent_id}] ✅ Streaming completed in {total_time:.2f}s with final message length: {len(current_content)}")
                return
        
        # If we get here, we've exceeded the maximum iterations
        total_time = time.time() - start_time
        print(f"[{agent_id}] ⚠️ Reached maximum iterations ({max_iterations}) after {total_time:.2f}s")
        
        # Add a system message to reset context for the next prompt
        messages.append({"role": "system",
                         "content": "Previous request exhausted tool iterations. "
                                    "Start a new plan from scratch."})
        
        yield "\n[max-tool-iterations exceeded] I've reached the maximum number of operations allowed. Please simplify your request or break it into smaller steps."
        return
