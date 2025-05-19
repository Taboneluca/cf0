from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any, List, Optional, AsyncGenerator, Callable, Union
from .chat_types import Message, AIResponse

class LLMClient(ABC):
    name: str  # "openai", "anthropic", "groq", etc.
    
    def __init__(self, api_key: str, model: str, **kw): 
        self.api_key = api_key
        self.model = model
        self.kw = kw

    @abstractmethod
    def chat(
        self,
        messages: List[Message],
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        **params
    ) -> Union[AsyncGenerator[AIResponse, None], AIResponse]:
        """
        Send a chat request to the provider and return a standardized response.
        
        IMPORTANT: This is deliberately NOT async to avoid the coroutine issue with async generators.
        The correct implementation pattern is:
        
        def chat(self, messages, stream=False, tools=None, **params):
            if stream:
                return self.stream_chat(messages, tools, **params)
            return self._chat_sync(messages, tools, **params)
            
        async def _chat_sync(self, messages, tools=None, **params):
            # Implementation for non-streaming case
            
        Args:
            messages: List of chat messages in standardized format
            stream: Whether to stream the response
            tools: List of tools to make available to the model
            params: Additional parameters for the provider
            
        Returns:
            If stream=False: AIResponse with content and/or tool_calls
            If stream=True: AsyncGenerator yielding AIResponse chunks
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
        
        IMPORTANT: This method MUST yield at least once BEFORE any await statements
        to ensure it's properly recognized as an async generator.
        
        The correct implementation pattern is:
        
        async def stream_chat(self, messages, tools=None, **params):
            # Yield immediately BEFORE any awaits
            yield AIResponse(content="", tool_calls=[])
            
            try:
                # Now it's safe to await
                stream = await self.client.create_stream(...)
                
                # Process the stream...
                async for chunk in stream:
                    # ...
                    yield AIResponse(...)
            except Exception as e:
                yield AIResponse(content=f"Error: {str(e)}")
        
        Args:
            messages: List of chat messages in standardized format
            tools: List of tools to make available to the model
            params: Additional parameters for the provider
            
        Yields:
            AIResponse chunks as they are generated
        """
        pass
    
    async def consume_stream(
        self, 
        messages: List[Message],
        on_chunk: Callable[[AIResponse], None] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **params
    ) -> AIResponse:
        """
        Helper function to consume a stream and gather full response.
        Properly iterates through the async generator.
        
        Args:
            messages: List of standardized Message objects
            on_chunk: Optional callback function to process each chunk
            tools: List of tools to make available to the model
            params: Additional parameters for the provider
            
        Returns:
            Final complete AIResponse
        """
        current_content = ""
        current_tool_calls = []
        
        # Properly iterate through the async generator with async for
        async for chunk in self.stream_chat(messages=messages, tools=tools, **params):
            # Call the callback function if provided
            if on_chunk:
                on_chunk(chunk)
                
            # Accumulate content if present
            if chunk.content is not None:
                current_content = chunk.content
            
            # Use the latest tool calls from the stream
            if chunk.tool_calls:
                current_tool_calls = chunk.tool_calls
        
        # Return the final complete response
        return AIResponse(
            content=current_content,
            tool_calls=current_tool_calls
        )
    
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
        
    @property
    def supports_function_call(self) -> bool:
        """
        Legacy alias used by BaseAgent. Kept here so every concrete client
        (OpenAI, Groq, Anthropic, …) automatically reports identical support.
        """
        return self.supports_tool_calls 