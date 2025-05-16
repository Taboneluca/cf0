# API Package

This package contains the FastAPI routing and API endpoints:

- `router.py`: Main chat and streaming endpoints
- `schemas.py`: Pydantic models for requests/responses
- `memory.py`: Conversation memory management
- `validators.py`: Input validation logic
- `admin_prompts.py`: Admin router for prompt management

This reorganization was part of Phase 8 of the AI Spreadsheet Assistant enhancement project to improve code organization and maintainability.

```python
def process_message(mode: str, message: str) -> dict:
    ...
    return { "reply": "...", "updates": [...] }
```

If you later add multi-user sessions, this file is where you'll store / retrieve a per-session Spreadsheet and conversation history. 