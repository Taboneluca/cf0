from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from agents.openai_client import client, OpenAIError, APIStatusError

def chat_completion(**kw):
    """
    Wrapper around OpenAI's chat completion API with exponential backoff retry logic.
    
    This function will automatically retry on rate limits and API errors, with an 
    exponential backoff strategy to handle temporary failures gracefully.
    
    Args:
        **kw: Keyword arguments to pass to the OpenAI chat completions API
        
    Returns:
        OpenAI API response object
    """
    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((OpenAIError, APIStatusError))
    )
    def _call():
        return client.chat.completions.create(**kw)
    
    return _call() 