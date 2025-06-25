from fastapi import FastAPI
from langserve import add_routes
import sys
import os

# Add the current directory to Python path to ensure relative imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the orchestrator that already implements stream_run
from agents.orchestrator import Orchestrator
from llm.factory import get_client
from spreadsheet_engine.model import Spreadsheet

# ---------------------------------------------------------------------------
# FastAPI application that exposes /ask/* and /analyst/* endpoints.
# /ask/stream     -> Server-Sent Events (SSE)  (POST JSON payload)
# /ask/invoke     -> Blocking JSON response   (POST JSON payload)
# Same for /analyst/…
# This relies on `langserve.add_routes`, which takes a Runnable or async
# generator and automatically wires fully-compliant streaming endpoints.
# ---------------------------------------------------------------------------

# Create a single LLM client to be shared across both agents
llm = get_client()  # Uses default model env-var or config

# Create a dummy spreadsheet for the orchestrator (since LangServe needs it)
# In production, this would be replaced with actual workbook data
dummy_sheet = Spreadsheet("Sheet1", rows=100, cols=30)

# Instantiate the orchestrator once (it builds ask & analyst agents internally)
orch = Orchestrator(llm=llm, sheet=dummy_sheet)

app = FastAPI(title="cf0.ai Streaming API", version="1.0.0")

# Custom LangServe wrapper to handle our specific input format
from typing import Dict, Any, AsyncGenerator
from pydantic import BaseModel

class ChatRequest(BaseModel):
    mode: str
    message: str
    wid: str = "default"
    sid: str = "Sheet1"
    contexts: list = []
    model: str = ""

async def stream_wrapper(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Wrapper to convert our orchestrator output to LangServe format"""
    async for step in orch.stream_run(
        mode=request.mode,
        message=request.message,
        history=[]  # TODO: Add history support
    ):
        if hasattr(step, 'content') and step.content:
            yield step.content

# Add routes for ASK mode -----------------------------------------------------
add_routes(
    app,
    stream_wrapper,
    path="/ask",
    input_type=ChatRequest,
)

# Add routes for ANALYST mode -------------------------------------------------
add_routes(
    app,
    stream_wrapper,
    path="/analyst", 
    input_type=ChatRequest,
)

# Health check – helps Docker / k8s
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"} 