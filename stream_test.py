from inspect import isasyncgen, isawaitable
from llm.providers.groq_client import GroqClient
from llm.providers.openai_client import OpenAIClient
from llm.providers.anthropic_client import AnthropicClient
import os, asyncio

# Set environment variables for API keys
os.environ["GROQ_API_KEY"] = "sk-xxx"
os.environ["OPENAI_API_KEY"] = "sk-xxx"
os.environ["ANTHROPIC_API_KEY"] = "sk-xxx"

async def p():
    # Test Groq client
    print("\n=== Testing Groq Client ===")
    groq_client = GroqClient(api_key="dummy", model="groq:llama-3-3-70b")
    
    print("\nDirect stream_chat test:")
    s = groq_client.stream_chat([{"role":"user","content":"hi"}])
    print("stream_chat return: awaitable:", isawaitable(s), "| async-gen:", isasyncgen(s))
    print(f"Type of stream_chat result: {type(s)}")
    
    print("\nChat with stream=True test:")
    c = groq_client.chat([{"role":"user","content":"hi"}], stream=True)
    print("chat return: awaitable:", isawaitable(c), "| async-gen:", isasyncgen(c))
    print(f"Type of chat result: {type(c)}")
    
    # Test OpenAI client
    print("\n\n=== Testing OpenAI Client ===")
    openai_client = OpenAIClient(api_key="dummy", model="gpt-4o")
    
    print("\nDirect stream_chat test:")
    s = openai_client.stream_chat([{"role":"user","content":"hi"}])
    print("stream_chat return: awaitable:", isawaitable(s), "| async-gen:", isasyncgen(s))
    print(f"Type of stream_chat result: {type(s)}")
    
    print("\nChat with stream=True test:")
    c = openai_client.chat([{"role":"user","content":"hi"}], stream=True)
    print("chat return: awaitable:", isawaitable(c), "| async-gen:", isasyncgen(c))
    print(f"Type of chat result: {type(c)}")
    
    # Test Anthropic client
    print("\n\n=== Testing Anthropic Client ===")
    anthropic_client = AnthropicClient(api_key="dummy", model="claude-3-5-sonnet")
    
    print("\nDirect stream_chat test:")
    s = anthropic_client.stream_chat([{"role":"user","content":"hi"}])
    print("stream_chat return: awaitable:", isawaitable(s), "| async-gen:", isasyncgen(s))
    print(f"Type of stream_chat result: {type(s)}")
    
    print("\nChat with stream=True test:")
    c = anthropic_client.chat([{"role":"user","content":"hi"}], stream=True)
    print("chat return: awaitable:", isawaitable(c), "| async-gen:", isasyncgen(c))
    print(f"Type of chat result: {type(c)}")
    
asyncio.run(p()) 