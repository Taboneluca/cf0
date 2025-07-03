from collections import deque
from typing import Dict, List, Any, Optional, Deque

# Maximum conversation turns to remember per session
MAX_HISTORY_LENGTH = 8

# Store conversation history per session
conversation_history: Dict[str, Deque[Dict[str, Any]]] = {}

def get_history(session_id: str) -> List[Dict[str, Any]]:
    """
    Get the conversation history for a specific session
    
    Args:
        session_id: Unique identifier for the user session
        
    Returns:
        List of conversation messages (dicts with role and content)
    """
    if session_id not in conversation_history:
        conversation_history[session_id] = deque(maxlen=MAX_HISTORY_LENGTH)
    
    return list(conversation_history[session_id])

def add_to_history(session_id: str, role: str, content: str) -> None:
    """
    Add a new message to the conversation history
    
    Args:
        session_id: Unique identifier for the user session
        role: Message role ('user' or 'assistant')
        content: Message content
    """
    if session_id not in conversation_history:
        conversation_history[session_id] = deque(maxlen=MAX_HISTORY_LENGTH)
    
    conversation_history[session_id].append({
        "role": role, 
        "content": content
    })

def clear_history(session_id: str) -> None:
    """
    Clear the conversation history for a specific session
    
    Args:
        session_id: Unique identifier for the user session
    """
    if session_id in conversation_history:
        conversation_history[session_id].clear() 