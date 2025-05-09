from anthropic import AsyncAnthropic
from ..base import LLMClient

class AnthropicClient(LLMClient):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, **kw):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.kw = kw

    async def chat(self, messages, stream=False, functions=None, **params):
        # Anthropic uses a different format for messages
        # Convert to Claude format
        system_message = None
        claude_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                claude_messages.append(msg)
                
        return await self.client.messages.create(
            model=self.model,
            messages=claude_messages,
            system=system_message,
            stream=stream,
            **self.kw, 
            **params,
        )

    @property
    def supports_function_call(self) -> bool:
        return False  # Anthropic doesn't support OpenAI's function calling format yet 