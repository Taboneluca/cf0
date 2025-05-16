from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ChatRequest(BaseModel):
    mode: str
    message: str
    wid: str
    sid: str
    contexts: Optional[List[str]] = []
    model: Optional[str] = None  # Provider:model_id format, e.g. "openai:gpt-4o-mini"

class ChatResponse(BaseModel):
    reply: str
    sheet: Dict[str, Any]
    log: List[Dict[str, Any]] 