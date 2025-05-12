from anthropic import AsyncAnthropic
from ..base import LLMClient
from types import SimpleNamespace

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
                
        msg = await self.client.messages.create(
            model=self.model,
            messages=claude_messages,
            system=system_message,
            stream=stream,
            **self.kw, 
            **params,
        )
        
        # Wrap into an OpenAI-look-alike object to make it compatible with base_agent.py
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg)],
            usage=None  # Claude does not yet return token counts
        )

    @property
    def supports_function_call(self) -> bool:
        return False  # Anthropic doesn't support OpenAI's function calling format yet 