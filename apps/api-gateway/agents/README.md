# Agents – LLM logic

This package contains every Large-Language-Model "persona" used by the
spreadsheet assistant.  Two concrete agents ship with the MVP:

| Agent          | Mode in UI | Permissions | Primary prompt file |
|----------------|-----------|-------------|---------------------|
| `AskAgent`     | **Ask**   | Read-only   | `ask_agent.py`      |
| `AnalystAgent` | **Analyst** | Read + Write | `analyst_agent.py` |

Both inherit from `BaseAgent`, which implements:

* prompt construction (`system + history + user`)
* OpenAI **function-calling** with retry / timeout
* the _run loop_ that keeps calling the model until a
  "final" message is produced (no further tool calls).

A shared **tool catalogue** lives in `tools.py`.  
Each entry exposes a spreadsheet operation to the model by providing:

```python
{
  "name": "get_row_by_header",
  "description": "...",
  "parameters": { ... JSON schema ... },
  "func": spreadsheet_engine.operations.get_row_by_header
}
```

When the model asks to invoke a tool, BaseAgent looks it up in this catalogue, executes func(**arguments), appends the result message to the conversation, and continues the loop.

## Add a new capability

1. Implement a pure Python function in `spreadsheet_engine/operations.py`.

2. Append a matching descriptor to `backend/agents/tools.TOOL_CATALOG`.

3. (Optional) update the system prompt of either agent to mention the new tool if it changes behaviour significantly.

That's it—no further wiring needed.
