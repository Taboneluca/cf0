# Prompt Template for cf0.ai

Use this template when creating or editing prompts via the `/admin/prompts` endpoint.

## Best Practices from "A Practical Guide to Building Agents"

1. **Use existing documents**: Start with existing operating procedures, support scripts, or policy documents.

2. **Break down tasks**: Provide smaller, clearer steps from dense resources to minimize ambiguity.

3. **Define clear actions**: Every step should correspond to a specific action or output.

4. **Capture edge cases**: Anticipate common variations and include instructions for handling them.

## Template Structure

```json
{
  "agent_mode": "analyst",  // or "ask" or any other agent type
  "text": "You are an [agent role].\n\n[Main Instructions]\n\n[Guidelines]\n\n[Key Points]\n\n[Edge Cases]",
  "created_by": "username"  // Your identifier
}
```

## Example: Analyst Agent

```json
{
  "agent_mode": "analyst",
  "text": "You are an advanced spreadsheet analyst...",
  "created_by": "john.doe"
}
```

## Submitting a New Prompt

POST to `/admin/prompts` with your JSON body.

This will automatically:
1. Deactivate the previous active prompt for this mode
2. Assign a new version number
3. Make your new prompt the active prompt
4. Clear the cache so the new prompt takes effect immediately

## Testing Your Prompt

After submission, you can use the spreadsheet UI to test if your prompt behaves as expected. 