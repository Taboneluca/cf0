from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from db.prompts import list_prompts, create_prompt

router = APIRouter(prefix="/admin/prompts", tags=["Prompts"])

class PromptCreate(BaseModel):
    agent_mode: str
    text: str
    created_by: str = "admin-console"   # replace with auth user id

@router.get("/{mode}")
def get_prompts(mode: str) -> List[dict]:
    """Return every stored prompt version (latest first)."""
    return list_prompts(mode)

@router.post("/")
def add_prompt(body: PromptCreate) -> dict:
    try:
        return create_prompt(body.agent_mode, body.text, body.created_by)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 