import json
import ast
import re

def safe_json_loads(s: str):
    """
    Parse JSON more leniently to handle malformed responses from OpenAI API.
    Uses multiple fallback strategies to avoid hard errors.
    """
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # 1️⃣ remove trailing commas before } ]
        s = re.sub(r',\s*([}\]])', r'\1', s)
        
        # 2️⃣ try again
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # 3️⃣ try to fix quotes
            try:
                # Look for unterminated strings and fix them
                s = re.sub(r'([^\\])"([^"]*?)([^\\])$', r'\1"\2\3"', s)
                s = re.sub(r'([^\\])"([^"]*?)([^\\])(,\s*[}\]])', r'\1"\2\3"\4', s)
                return json.loads(s)
            except json.JSONDecodeError:
                # 4️⃣ last resort – python literal_eval
                try:
                    return ast.literal_eval(s)
                except Exception as exc:
                    raise ValueError(f"Cannot parse JSON: {exc}") from exc 