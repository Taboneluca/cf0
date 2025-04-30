import tiktoken
from typing import List, Dict, Any

# Maximum tokens for conversation history
MAX_HISTORY_TOKENS = 4000

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Count the number of tokens in a string
    
    Args:
        text: The text to count tokens for
        model: The model to use for tokenization
        
    Returns:
        Number of tokens
    """
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

def trim_history(messages: List[Dict[str, Any]], system_message: Dict[str, Any], 
                max_tokens: int = MAX_HISTORY_TOKENS, model: str = "gpt-4o") -> List[Dict[str, Any]]:
    """
    Trim conversation history to fit within token limit
    
    Args:
        messages: List of message dictionaries (history + current message)
        system_message: The system message to preserve
        max_tokens: Maximum tokens allowed for all messages
        model: Model used for tokenization
        
    Returns:
        Trimmed message list that fits within token limit
    """
    # Always keep system message and the most recent message (typically user's query)
    if len(messages) <= 2:
        return messages
    
    # Start with just the system message and the latest message
    essential_messages = [system_message, messages[-1]]
    essential_tokens = count_message_tokens(essential_messages, model)
    
    # Calculate how many tokens we can use for history
    available_tokens = max_tokens - essential_tokens
    
    # Start from the most recent history (excluding the current message)
    # and work backwards until we hit the token limit
    history = []
    current_tokens = 0
    
    for msg in reversed(messages[1:-1]):
        msg_tokens = count_message_tokens([msg], model)
        if current_tokens + msg_tokens <= available_tokens:
            history.insert(0, msg)  # Insert at beginning to maintain order
            current_tokens += msg_tokens
        else:
            # Stop adding messages if we exceed the token limit
            break
    
    # Combine the system message, history, and current message
    return [system_message] + history + [messages[-1]] 