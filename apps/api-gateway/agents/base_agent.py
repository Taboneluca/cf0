from __future__ import annotations
from typing import List, Dict, Any, Optional
import os
import asyncio
import json
import time
from dotenv import load_dotenv
from agents.openai_client import client, OpenAIError, APIStatusError
from agents.openai_rate import chat_completion
from .tools import TOOL_CATALOG
from chat.token_utils import trim_history

load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
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
        # Prepare the basic message structure with system prompt
        system_message = {"role": "system", "content": self.system_prompt}
        messages = [system_message]
        
        # Add conversation history if provided
        if history:
            messages.extend(history)
            
        # Add the current user message
        messages.append({"role": "user", "content": user_message})
        
        # Trim history to fit within token limits
        messages = trim_history(messages, system_message, MAX_TOKENS, MODEL)

        # Allow many small tool calls without bailing out too early (env: MAX_TOOL_ITERATIONS, default 40)
        max_iterations = int(os.getenv("MAX_TOOL_ITERATIONS", "40"))
        iterations = 0
        collected_updates: list = []
        mutating_calls = 0
        
        while iterations < max_iterations:
            iterations += 1
            
            # Try to call the model with retries for transient errors
            try:
                response = chat_completion(
                    model=MODEL,
                    messages=messages,
                    functions=[_serialize_tool(t) for t in self.tools],
                    function_call="auto",
                    temperature=0.3,  # Reduced from 1.0 to 0.3 for more consistent responses
                )
            except (OpenAIError, APIStatusError) as e:
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
                
                # Check if this is a mutating call
                is_mutating = not next((t for t in self.tools if t["name"] == name), {}).get("read_only", False)
                if is_mutating:
                    mutating_calls += 1
                    
                # Enforce single set_cells mutation per task
                if mutating_calls > 1 and name != "set_cells" and is_mutating:
                    return {
                        "reply": "Error: use a single set_cells call for multiple updates.",
                        "updates": collected_updates
                    }
                
                # Invoke the Python function
                fn = next(t["func"] for t in self.tools if t["name"] == name)
                result = fn(**args)
                
                # Accumulate updates if provided
                if isinstance(result, dict):
                    if "updates" in result and isinstance(result["updates"], list):
                        collected_updates.extend(result["updates"])
                    # Normalise single-cell result (handles keys 'new', 'new_value' or 'value')
                    elif "cell" in result:
                        collected_updates.append(result)
                
                # Add the function's output back into the conversation
                messages.append({
                    "role": "assistant",  # use assistant role since Groq rejects 'function'
                    "name": name,
                    "content": json.dumps(result)
                })
                
                # Continue the loop so the model can decide whether to call more functions or give a final answer
                continue
            
            # 2) No function call - model gave a direct answer
            elif msg.content:
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
                                    print(f"Found {len(updates)} updates in extracted JSON")
                                    actually_applied_updates = []
                                    
                                    for update in updates:
                                        if "cell" in update and ("new_value" in update or "new" in update or "value" in update):
                                            cell = update["cell"]
                                            value = update.get("new_value", update.get("new", update.get("value")))
                                            print(f"Executing set_cell from JSON for {cell} = {value}")
                                            
                                            # Apply the update directly
                                            for t in self.tools:
                                                if t["name"] == "set_cell":
                                                    tool_result = t["func"](cell_ref=cell, value=value)
                                                    actually_applied_updates.append(tool_result)
                                                    break
                                    
                                    # Include the applied updates in the result, or fallback to collected_updates
                                    extracted_json["updates"] = actually_applied_updates if actually_applied_updates else collected_updates
                                    return extracted_json
                        except json.JSONDecodeError as e:
                            print(f"Error parsing extracted JSON: {e}")
                
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
                            for update in updates:
                                if "cell" in update and ("new_value" in update or "new" in update or "value" in update):
                                    cell = update["cell"]
                                    value = update.get("new_value", update.get("new", update.get("value")))
                                    
                                    print(f"Executing set_cell from direct JSON for {cell} = {value}")
                                    
                                    # Apply the update directly
                                    tool_result = None
                                    for t in self.tools:
                                        if t["name"] == "set_cell":
                                            tool_result = t["func"](cell_ref=cell, value=value)
                                            actually_applied_updates.append(tool_result)
                                            break
                            
                            # Include the applied updates in the result
                            json_result["updates"] = actually_applied_updates if actually_applied_updates else collected_updates
                            return json_result
                    except json.JSONDecodeError:
                        # If we can't parse JSON, just treat it as a regular message
                        pass
                
                # Process as a regular message
                reply = msg.content.strip()
                return {
                    "reply": reply,
                    "updates": collected_updates
                }
        
        # If we get here, we've exceeded the maximum iterations
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
