import os
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError, APIStatusError

# Load environment variables
load_dotenv()

# Initialize the OpenAI client
client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
    http2=True  # Enable HTTP/2 for connection reuse and better performance
)
# Export the client and error classes
__all__ = ["client", "OpenAIError", "APIStatusError"] 