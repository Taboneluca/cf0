import json
import ast
import re
import logging
from typing import Dict, Any, Union, Optional

def _trim_to_last_complete_json(s: str) -> str:
    """
    Find the last position where braces and brackets are balanced.
    Returns a trimmed string up to that position.
    """
    depth_curly = 0
    depth_square = 0
    last_balanced_pos = -1
    
    for i, char in enumerate(s):
        if char == '{':
            depth_curly += 1
        elif char == '}':
            depth_curly -= 1
        elif char == '[':
            depth_square += 1
        elif char == ']':
            depth_square -= 1
        
        # Check if we're balanced at this position
        if depth_curly == 0 and depth_square == 0 and ('{' in s[:i+1] or '[' in s[:i+1]):
            last_balanced_pos = i
    
    # If we found a balanced position, trim the string
    if last_balanced_pos != -1:
        if last_balanced_pos < len(s) - 1:
            logging.warning(f"Truncating incomplete JSON at position {last_balanced_pos+1}. Original length: {len(s)}")
        return s[:last_balanced_pos + 1]
    return s

def safe_json_loads(s: str) -> Dict[str, Any]:
    """
    Parse JSON more leniently to handle malformed responses from OpenAI API.
    Uses multiple fallback strategies to avoid hard errors.
    """
    if not s:
        return {}
    
    # Check if JSON is balanced and trim if necessary
    s = _trim_to_last_complete_json(s)
    
    # First attempt: standard JSON parsing
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # 1️⃣ remove trailing commas before } ]
        s = re.sub(r',\s*([}\]])', r'\1', s)
        
        # 2️⃣ try again
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # 3️⃣ try to fix quotes and common issues
            try:
                # Look for unterminated strings and fix them
                s = re.sub(r'([^\\])"([^"]*?)([^\\])$', r'\1"\2\3"', s)
                s = re.sub(r'([^\\])"([^"]*?)([^\\])(,\s*[}\]])', r'\1"\2\3"\4', s)
                
                # Try with fixed quotes
                return json.loads(s)
            except json.JSONDecodeError:
                # 4️⃣ last resort – python literal_eval with detailed error report
                try:
                    result = ast.literal_eval(s)
                    # Make sure we have a dictionary
                    if isinstance(result, dict):
                        return result
                    else:
                        return {"value": result}
                except Exception as exc:
                    logging.error(f"JSON parse failure. Input: {s[:100]}{'...' if len(s) > 100 else ''}")
                    raise ValueError(f"Cannot parse JSON: {exc}") from exc 