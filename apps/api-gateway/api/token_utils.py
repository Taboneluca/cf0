try:
    import tiktoken
except ImportError:
    tiktoken = None  # fallback: disable token trimming
    print("WARNING: tiktoken not found, token counting/trimming will be disabled")

from typing import List, Dict, Any
from llm.catalog import get_model_info

# Default maximum tokens for conversation history if not specified by model
DEFAULT_MAX_HISTORY_TOKENS = 4000

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Count the number of tokens in a string
    
    Args:
        text: The text to count tokens for
        model: The model to use for tokenization
        
    Returns:
        Number of tokens
    """
    if tiktoken is None:
        # Fallback approximation if tiktoken is not available
        return len(text) // 4
        
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fall back to cl100k_base for newer models not yet in tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
    
    return len(encoding.encode(text))

def count_message_tokens(messages: List[Dict[str, Any]], model: str = "gpt-4o") -> int:
    """
    Count tokens in a list of chat messages
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        model: Model to use for tokenization
        
    Returns:
        Total token count of all messages
    """
    # Initialize token count (per-message overhead)
    num_tokens = 0
    
    if tiktoken is None:
        # Fallback approximation if tiktoken is not available
        for message in messages:
            content = message.get("content", "")
            num_tokens += (len(content if content else "") // 4) + 4
        return num_tokens
        
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    
    # Count tokens for each message
    for message in messages:
        # Every message has a base token count for the format
        num_tokens += 4  # Format overhead for each message
        
        # Add tokens for role
        num_tokens += len(encoding.encode(message.get("role", "")))
        
        # Add tokens for content
        if "content" in message and message["content"] is not None:
            num_tokens += len(encoding.encode(message["content"]))
            
        # Add tokens for name if present
        if "name" in message:
            num_tokens += len(encoding.encode(message["name"]))
            num_tokens += 1  # Format overhead for name field
    
    # Additional tokens to account for the overall structure
    num_tokens += 2  # Final overhead for completion format
    
    return num_tokens

def get_max_history_tokens(model_key: str) -> int:
    """
    Get the maximum tokens allowed for history based on the model
    
    Args:
        model_key: The model key (e.g., "openai:gpt-4o")
        
    Returns:
        Maximum tokens for history
    """
    try:
        # Get max_tokens from the model catalog
        model_info = get_model_info(model_key)
        max_context = model_info.get("max_tokens", 0)
        
        # Use 1/3 of the model's context window for history
        # but never more than 32k tokens to avoid excessive token usage
        if max_context > 0:
            return min(max_context // 3, 32000)
        
        # Fallback to default if not found
        return DEFAULT_MAX_HISTORY_TOKENS
    except Exception as e:
        print(f"Error getting max tokens for model {model_key}: {e}")
        return DEFAULT_MAX_HISTORY_TOKENS

def trim_history(messages: List[Dict[str, Any]], system_message: Dict[str, Any], 
                max_tokens: int = None, model: str = "openai:gpt-4o") -> List[Dict[str, Any]]:
    """
    Trim conversation history to fit within token limit
    
    Args:
        messages: List of message dictionaries (history + current message)
        system_message: The system message to preserve
        max_tokens: Maximum tokens allowed for all messages (optional)
        model: Model key (e.g., "openai:gpt-4o") for tokenization and context window size
        
    Returns:
        Trimmed message list that fits within token limit
    """
    # If max_tokens is not provided, determine it from the model
    if max_tokens is None:
        max_tokens = get_max_history_tokens(model)
    
    # If tiktoken is not available, return a conservative subset of history
    if tiktoken is None:
        # Simplified approach: keep system message and last 5 messages
        if len(messages) <= 6:  # system + 5 messages
            return messages
        else:
            # Keep the system message and last 5 messages
            return [system_message] + messages[-5:]
            
    # Always keep system message and the most recent message (typically user's query)
    if len(messages) <= 2:
        return messages
    
    # Start with just the system message and the latest message
    essential_messages = [system_message, messages[-1]]
    essential_tokens = count_message_tokens(essential_messages, model.split(":", 1)[1])
    
    # Calculate how many tokens we can use for history
    available_tokens = max_tokens - essential_tokens
    
    # Start from the most recent history (excluding the current message)
    # and work backwards until we hit the token limit
    history = []
    current_tokens = 0
    
    for msg in reversed(messages[1:-1]):
        msg_tokens = count_message_tokens([msg], model.split(":", 1)[1])
        if current_tokens + msg_tokens <= available_tokens:
            history.insert(0, msg)  # Insert at beginning to maintain order
            current_tokens += msg_tokens
        else:
            # Stop adding messages if we exceed the token limit
            break
    
    # Combine the system message, history, and current message
    return [system_message] + history + [messages[-1]] 