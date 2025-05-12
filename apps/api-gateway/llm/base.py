from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any, List, Optional, AsyncGenerator
from .chat_types import Message, AIResponse

class LLMClient(ABC):
    name: str  # "openai", "anthropic", "groq", etc.
    
    def __init__(self, api_key: str, model: str, **kw): 
        self.api_key = api_key
        self.model = model
        self.kw = kw

    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        **params
    ) -> AIResponse: 
        """
        Send a chat request to the provider and return a standardized response.
        
        Args:
            messages: List of chat messages in standardized format
            stream: Whether to stream the response
            tools: List of tools to make available to the model
            params: Additional parameters for the provider
            
        Returns:
            Standardized AIResponse with content and/or tool_calls
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **params
    ) -> AsyncGenerator[AIResponse, None]:
        """
        Stream a chat response from the provider.
        
        Args:
            messages: List of chat messages in standardized format
            tools: List of tools to make available to the model
            params: Additional parameters for the provider
            
        Yields:
            AIResponse chunks as they are generated
        """
        pass
    
    @abstractmethod
    def to_provider_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert standardized messages to provider-specific format.
        
        Args:
            messages: List of standardized Message objects
            
        Returns:
            List of messages in the provider's API format
        """
        pass
        
    @abstractmethod
    def from_provider_response(self, response: Any) -> AIResponse:
        """
        Convert provider-specific response to standardized AIResponse.
        
        Args:
            response: Raw response from the provider
            
        Returns:
            Standardized AIResponse object
        """
        pass

    @property
    def supports_tool_calls(self) -> bool:
        """Whether this model supports tool calling"""
        return True 