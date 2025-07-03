# Chat Router

`router.py` is the thin glue between FastAPI routes and the agent layer.
It decides which agent to invoke and assembles the unified response shape
expected by the frontend.

```python
def process_message(mode: str, message: str) -> dict:
    ...
    return { "reply": "...", "updates": [...] }
```

If you later add multi-user sessions, this file is where you'll store / retrieve a per-session Spreadsheet and conversation history. 