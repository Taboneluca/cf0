from openai import AsyncOpenAI
from ..base import LLMClient

class OpenAIClient(LLMClient):
    name = "openai"

    def __init__(self, api_key: str, model: str, **kw):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.kw = kw

    async def chat(self, messages, stream=False, functions=None, **params):
        return await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
            functions=functions,
            **self.kw, **params,
        )

    @property
    def supports_function_call(self) -> bool:
        return True 