from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any

class LLMClient(ABC):
    name: str                  # "openai:gpt-4o-mini", "anthropic:claude-3-opus" …

    def __init__(self, api_key: str, model: str, **kw): 
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str|dict]],
        stream: bool = False,
        functions: list[dict[str, Any]] | None = None,
        **params
    ) -> dict: 
        pass

    @property
    @abstractmethod
    def supports_function_call(self) -> bool: 
        pass 