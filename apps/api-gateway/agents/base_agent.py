from __future__ import annotations
from typing import List, Dict, Any, Optional, AsyncGenerator
import os
import asyncio
import json
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

load_dotenv()
MAX_RETRIES = 3
RETRY_DELAY = 1.0
MAX_TOKENS = 4096

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
    ):
        """
        Parameters
        ----------
        fallback_prompt :
            Hard-coded constant kept as last-resort safety valve.
        agent_mode :
            When provided we fetch the *active* prompt for that mode
            from Supabase with a 60 s TTL LRU cache.
        """
        self.llm = llm
        self.tools = tools

        if agent_mode:
            try:
                self.system_prompt = get_active_prompt(agent_mode)
            except Exception as e:
                # Don't crash the session – fall back silently and log.
                print(f"⚠️  Prompt DB lookup failed for mode={agent_mode}: {e}")
                self.system_prompt = fallback_prompt
        else:
            self.system_prompt = fallback_prompt

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
        messages = trim_history(messages, system_message, MAX_TOKENS, self.llm.model)
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
                response = await self.llm.chat(
                    messages=_dicts_to_messages(messages),
                    stream=False,
                    tools=[_serialize_tool(t) for t in self.tools] if self.llm.supports_tool_calls else None,
                    temperature=0.3,  # Reduced from 1.0 to 0.3 for more consistent responses
                    max_tokens=400    # Limit response size while still allowing sufficient explanation
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
                    args = safe_json_loads(msg.function_call.arguments)
                    print(f"[{agent_id}] 🛠️ Tool call: {name}")
                    
                    # Yield a ChatStep for the function call
                    yield ChatStep(
                        role="assistant",
                        toolCall={
                            "name": name,
                            "arguments": args
                        },
                        usage=response.usage.model_dump() if hasattr(response, 'usage') else None
                    )
                    
                except ValueError as e:
                    print(f"[{agent_id}] ❌ Error parsing function arguments: {str(e)}")
                    yield ChatStep(
                        role="assistant",
                        content=f"Sorry, I encountered an error while processing your request. Please try again with simpler instructions.",
                        usage=response.usage.model_dump() if hasattr(response, 'usage') else None
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
                            usage=response.usage.model_dump() if hasattr(response, 'usage') else None
                        )
                        return
                
                # Add the function's output back into the conversation
                messages.append({
                    "role": "assistant",  # use assistant role since Groq rejects 'function'
                    "name": name,
                    "content": json.dumps(result)
                })
                
                loop_time = time.time() - loop_start
                print(f"[{agent_id}] ⏱️ Iteration {iterations} completed in {loop_time:.2f}s")
                
                # Continue the loop so the model can decide whether to call more functions or give a final answer
                continue
            
            # 2) No function call - model gave a direct answer
            elif msg.content:
                print(f"[{agent_id}] 💬 Model returned direct response, length: {len(msg.content)}")
                
                # Look for updates embedded in JSON
                if isinstance(msg.content, str):
                    # Try to extract JSON wrapped in ```json ... ``` or other code blocks
                    import re
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
                                        usage=response.usage.model_dump() if hasattr(response, 'usage') else None
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
                                usage=response.usage.model_dump() if hasattr(response, 'usage') else None
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
                    usage=response.usage.model_dump() if hasattr(response, 'usage') else None
                )
                return
        
        # If we get here, we've exceeded the maximum iterations
        total_time = time.time() - start_time
        print(f"[{agent_id}] ⚠️ Reached maximum iterations ({max_iterations}) after {total_time:.2f}s")
        
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
        
        # Trim history to fit within token limits
        orig_message_count = len(messages)
        messages = trim_history(messages, system_message, MAX_TOKENS, self.llm.model)
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
                
                response_stream = await self.llm.chat(
                    messages=_dicts_to_messages(messages),
                    stream=True,
                    tools=[_serialize_tool(t) for t in self.tools] if self.llm.supports_tool_calls else None,
                    temperature=0.3,
                    max_tokens=400  # Limit response size while still allowing sufficient explanation
                )
                
                # Process the streaming response
                current_content = ""
                function_name = None
                function_args = ""
                is_function_call = False
                
                # Collect the response chunks
                async for chunk in response_stream:
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
                            current_content += delta.content
                            if in_tool_calling_phase:
                                # We've transitioned from tool calling to final answer
                                in_tool_calling_phase = False
                                print(f"[{agent_id}] 💬 Transitioning to final answer")
                            
                            # Only yield content chunks, not function calls
                            yield delta.content
                    else:
                        # Handle AIResponse format
                        if chunk.content:
                            content_chunk = chunk.content
                            if isinstance(content_chunk, str) and not current_content and not in_tool_calling_phase:
                                in_tool_calling_phase = False
                                print(f"[{agent_id}] 💬 Transitioning to final answer (AIResponse)")
                            
                            current_content += content_chunk
                            yield content_chunk
                        
                        if chunk.tool_calls and not is_function_call and chunk.tool_calls:
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
                    
                    # Add results to messages
                    messages.append({
                        "role": "assistant", 
                        "name": function_name,
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
        yield "\n[max-tool-iterations exceeded] I've reached the maximum number of operations allowed. Please simplify your request or break it into smaller steps."
