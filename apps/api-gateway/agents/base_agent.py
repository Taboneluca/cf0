from __future__ import annotations
from typing import List, Dict, Any, Optional, AsyncGenerator
import os
import asyncio
import json
import time
import traceback
from dotenv import load_dotenv
from agents.openai_client import client, OpenAIError, APIStatusError
from agents.openai_rate import chat_completion
from .tools import TOOL_CATALOG
from chat.token_utils import trim_history

load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
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

class BaseAgent:
    def __init__(self, system_prompt: str, tools: list[dict]):
        self.system_prompt = system_prompt
        self.tools = tools

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
            
        # Create and return a new agent
        return BaseAgent(self.system_prompt, new_tools)

    async def run(self, user_message: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Execute the tool-loop until the model produces a final answer.
        Returns { 'reply': str, 'updates': list }
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
        
        # Trim history to fit within token limits
        orig_message_count = len(messages)
        messages = trim_history(messages, system_message, MAX_TOKENS, MODEL)
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
                print(f"[{agent_id}] 🔌 Calling LLM model: {MODEL}")
                
                response = chat_completion(
                    model=MODEL,
                    messages=messages,
                    functions=[_serialize_tool(t) for t in self.tools],
                    function_call="auto",
                    temperature=0.3,  # Reduced from 1.0 to 0.3 for more consistent responses
                    max_tokens=400    # Limit response size while still allowing sufficient explanation
                )
                
                call_time = time.time() - call_start
                print(f"[{agent_id}] ⏱️ LLM call completed in {call_time:.2f}s")
            except (OpenAIError, APIStatusError) as e:
                print(f"[{agent_id}] ❌ Error calling LLM: {str(e)}")
                return {
                    "reply": f"Sorry, I encountered an error: {str(e)}",
                    "updates": []
                }
            
            # Process the response
            msg = response.choices[0].message
            
            # Add the model's response to the conversation, remapping 'function' role to 'assistant' for Groq
            msg_dict = msg.model_dump()
            if msg_dict.get("role") == "function":
                msg_dict["role"] = "assistant"
            messages.append(msg_dict)
            
            # 1) Did the model pick a function?
            if msg.function_call:
                name = msg.function_call.name
                args = json.loads(msg.function_call.arguments)
                print(f"[{agent_id}] 🛠️ Tool call: {name}")
                
                # Track mutating calls
                if name in mutating_tools:
                    mutating_calls += 1
                    print(f"[{agent_id}] ✏️ Mutating call #{mutating_calls}: {name}")
                    
                    # If this is more than the first mutation and not a set_cells call, abort
                    if mutating_calls > 1 and name not in {"set_cells", "apply_updates_and_reply"}:
                        print(f"[{agent_id}] ⛔ Too many mutating calls. Use set_cells for batch updates.")
                        return {
                            "reply": "Error: You should use a single set_cells call to make multiple updates. Please try again with a single batch operation.",
                            "updates": collected_updates
                        }

                # Invoke the Python function
                fn = next(t["func"] for t in self.tools if t["name"] == name)
                print(f"[{agent_id}] 🧰 Executing {name} with args: {json.dumps(args)[:100]}...")
                
                fn_start = time.time()
                result = fn(**args)
                fn_time = time.time() - fn_start
                
                print(f"[{agent_id}] ⏱️ Function executed in {fn_time:.2f}s")
                
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
                        return {
                            "reply": result["reply"],
                            "updates": collected_updates or result.get("updates", [])
                        }
                
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
                                    return extracted_json
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
                            return json_result
                    except json.JSONDecodeError:
                        # If we can't parse JSON, just treat it as a regular message
                        print(f"[{agent_id}] ℹ️ Could not parse response as JSON, treating as regular message")
                
                # Process as a regular message
                reply = msg.content.strip()
                
                total_time = time.time() - start_time
                print(f"[{agent_id}] ✅ Agent run completed in {total_time:.2f}s with {len(collected_updates)} updates")
                
                return {
                    "reply": reply,
                    "updates": collected_updates
                }
        
        # If we get here, we've exceeded the maximum iterations
        total_time = time.time() - start_time
        print(f"[{agent_id}] ⚠️ Reached maximum iterations ({max_iterations}) after {total_time:.2f}s")
        
        return {
            "reply": "[max-tool-iterations exceeded] I've reached the maximum number of operations allowed. Please simplify your request or break it into smaller steps.",
            "updates": collected_updates
        }

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
        messages = trim_history(messages, system_message, MAX_TOKENS, MODEL)
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
            print(f"[{agent_id}] 🔌 Calling LLM model in streaming mode: {MODEL}")
            
            try:
                response_stream = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    functions=[_serialize_tool(t) for t in self.tools],
                    function_call="auto",
                    temperature=0.3,
                    max_tokens=400,  # Limit response size while still allowing sufficient explanation
                    stream=True  # Enable streaming
                )
                
                # Process the streaming response
                current_content = ""
                function_name = None
                function_args = ""
                is_function_call = False
                
                # Collect the response chunks
                async for chunk in response_stream:
                    # Skip empty chunks
                    if not chunk.choices:
                        continue
                        
                    delta = chunk.choices[0].delta
                    
                    # Check if this is the start of a function call
                    if delta.function_call and not is_function_call:
                        is_function_call = True
                        function_name = delta.function_call.name
                        print(f"[{agent_id}] 🔧 Starting function call: {function_name}")
                    
                    # Accumulate function arguments
                    if is_function_call and delta.function_call and delta.function_call.arguments:
                        function_args += delta.function_call.arguments
                    
                    # Accumulate content for text response
                    if delta.content:
                        current_content += delta.content
                        if in_tool_calling_phase:
                            # We've transitioned from tool calling to final answer
                            in_tool_calling_phase = False
                            print(f"[{agent_id}] 💬 Transitioning to final answer")
                        
                        # Only yield content chunks, not function calls
                        yield delta.content
                
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
                    args = json.loads(function_args)
                    
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
                    print(f"[{agent_id}] ❌ Error executing function {function_name}: {str(e)}")
                    yield f"\nError executing {function_name}: {str(e)}"
                    return
            else:
                # No function call means we have a text response
                # Already yielded incrementally, so we can exit the loop
                break
        
        # If we reach here via break, we're done
        # If we reach here via iteration limit, yield a warning
        if iterations >= max_iterations:
            print(f"[{agent_id}] ⚠️ Reached max iterations: {max_iterations}")
            yield f"\n[Reached maximum number of operations ({max_iterations}). Consider simplifying your request.]"
        
        print(f"[{agent_id}] ✅ Streaming run complete in {iterations} iterations")
        return
