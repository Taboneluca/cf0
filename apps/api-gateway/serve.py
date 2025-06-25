from fastapi import FastAPI
from langserve import add_routes

# Import the orchestrator that already implements stream_run
from agents.orchestrator import Orchestrator
from llm.factory import get_client

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

# Instantiate the orchestrator once (it builds ask & analyst agents internally)
orch = Orchestrator(llm=llm)

app = FastAPI(title="cf0.ai Streaming API")

# Add routes for ASK mode -----------------------------------------------------
add_routes(
    app,
    orch.stream_run,              # async generator that yields ChatStep
    path="/ask",
    config={"mode": "ask"},      # extra kwargs forwarded to stream_run
)

# Add routes for ANALYST mode -------------------------------------------------
add_routes(
    app,
    orch.stream_run,
    path="/analyst",
    config={"mode": "analyst"},
)

# Health check – helps Docker / k8s
@app.get("/health")
async def health():
    return {"status": "ok"} 