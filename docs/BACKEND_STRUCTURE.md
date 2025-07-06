# Backend Structure Guide

This guide explains the FastAPI backend architecture, agent system, and service organization.

## Directory Structure

```
apps/api-gateway/
├── agents/               # AI agent implementations
├── api/                  # REST API routes and schemas
├── db/                   # Database connections
├── infrastructure/       # System prompts and config
├── llm/                  # LLM provider abstraction
├── spreadsheet_engine/   # Core spreadsheet logic
├── streaming/            # SSE streaming handlers
├── state/               # State management
└── main.py              # FastAPI application entry
```

## Core Architecture

### FastAPI Application

The main application is structured with middleware and routers:

```python
app = FastAPI(title="Intelligent Spreadsheet Assistant")

# Middleware
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # Detailed validation error logging
```

### Startup and Shutdown

```python
@app.on_event("startup")
async def startup_event():
    await initialize_workbook_store()
    
@app.on_event("shutdown")
async def shutdown_event():
    await cleanup_resources()
```

## Agent System

### Agent Hierarchy

```
BaseAgent (Abstract)
├── AskAgent      # Read-only analysis
│   └── Tools: get_cell, get_range, calculate, sheet_summary
└── AnalystAgent  # Can modify spreadsheets
    └── Tools: All read tools + set_cell, add_row, delete_row, etc.
```

### BaseAgent Implementation

```python
class BaseAgent:
    def __init__(self, llm: LLMClient, fallback_prompt: str = None, tools: list = None):
        self.llm = llm
        self.system_prompt = fallback_prompt or self.default_prompt()
        self.tools = tools or self.get_tools()
    
    async def run(self, message: str, history: list = None) -> dict:
        # Main agent execution logic
        
    async def run_iter(self, message: str, history: list = None) -> AsyncGenerator[ChatStep, None]:
        # Streaming execution with yield points
```

### Tool System

Tools are Python functions exposed to agents:

```python
def get_cell(cell_ref: str, sheet: Spreadsheet) -> dict:
    """Get value and metadata for a specific cell."""
    # Implementation
    
def set_cell(cell_ref: str, value: Any, sheet: Spreadsheet) -> dict:
    """Set cell value and trigger recalculation."""
    # Implementation
```

Tool registration:
```python
class AskAgent(BaseAgent):
    def get_tools(self):
        return [
            {"name": "get_cell", "function": get_cell},
            {"name": "get_range", "function": get_range},
            # ... more tools
        ]
```

## LLM Provider Abstraction

### LLMClient Protocol

```python
class LLMClient(Protocol):
    model: str
    name: str
    supports_tools: bool
    supports_streaming: bool
    
    async def complete(self, messages: list, **kwargs) -> str:
        """Non-streaming completion"""
        
    async def stream(self, messages: list, **kwargs) -> AsyncGenerator[str, None]:
        """Streaming completion"""
```

### Provider Implementations

```python
# OpenAI
class OpenAIClient(LLMClient):
    def __init__(self, model="gpt-4o", api_key=None):
        self.client = AsyncOpenAI(api_key=api_key)
        
# Anthropic
class AnthropicClient(LLMClient):
    def __init__(self, model="claude-3-opus", api_key=None):
        self.client = AsyncAnthropic(api_key=api_key)
        
# Groq
class GroqClient(LLMClient):
    def __init__(self, model="llama-70b", api_key=None):
        self.client = AsyncGroq(api_key=api_key)
```

### Factory Pattern

```python
def get_client(model_id: str) -> LLMClient:
    """Get appropriate client for model ID."""
    provider = get_provider_for_model(model_id)
    
    if provider == "openai":
        return OpenAIClient(model=model_id)
    elif provider == "anthropic":
        return AnthropicClient(model=model_id)
    # ... etc
```

## Spreadsheet Engine

### Core Components

1. **Spreadsheet Model**
   ```python
   class Spreadsheet:
       cells: List[List[Any]]
       n_rows: int
       n_cols: int
       formulas: Dict[str, str]
       dependencies: Dict[str, Set[str]]
   ```

2. **Operations Module**
   - Cell operations: get_cell, set_cell, clear_cell
   - Range operations: get_range, set_range, sort_range
   - Row/column operations: add_row, delete_row, add_column
   - Sheet operations: create_sheet, delete_sheet

3. **Formula Engine**
   ```python
   class FormulaEngine:
       def evaluate(self, formula: str, sheet: Spreadsheet) -> Any:
           # Parse and evaluate formulas
           
       def extract_dependencies(self, formula: str) -> Set[str]:
           # Extract cell references from formula
   ```

4. **Dependency Tracking**
   ```python
   def recalculate_dependents(cell_ref: str, sheet: Spreadsheet):
       """Recalculate all cells that depend on the changed cell."""
       dependents = sheet.get_dependents(cell_ref)
       for dep in topological_sort(dependents):
           recalculate_cell(dep, sheet)
   ```

## Streaming Architecture

### SSE Handler

```python
class StreamingHandler:
    async def stream_response(self, request: Request, chat_request: ChatRequest):
        return EventSourceResponse(
            self._event_generator(chat_request),
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )
```

### Event Generation

```python
async def _event_generator(self, chat_request: ChatRequest):
    # Initialize agent
    agent = build_agent(chat_request.mode)
    
    # Stream execution
    async for step in agent.run_iter(chat_request.message):
        event = self._convert_to_sse_event(step)
        yield event
    
    # Send completion
    yield {"event": "done", "data": json.dumps({"status": "completed"})}
```

### Event Types

```python
class EventType(Enum):
    REASONING = "reasoning"      # AI thinking process
    TOOL_CALL = "tool_call"      # Tool invocation
    TOOL_RESULT = "tool_result"  # Tool result
    CONTENT = "content"          # Text content
    UPDATE = "update"            # Cell updates
    ERROR = "error"              # Errors
    STATUS = "status"            # Status updates
    DONE = "done"                # Completion
    HEARTBEAT = "heartbeat"      # Keep-alive
```

## State Management

### Workbook Store

In-memory cache for active workbooks:

```python
# Global store
workbooks: Dict[str, Workbook] = {}

def get_workbook(wid: str) -> Workbook:
    if wid not in workbooks:
        workbooks[wid] = Workbook(wid)
    return workbooks[wid]

def get_sheet(wid: str, sid: str) -> Spreadsheet:
    wb = get_workbook(wid)
    return wb.sheet(sid)
```

### Pending Updates Store

Tracks optimistic updates during streaming:

```python
PENDING_STORE: Dict[tuple[str, str], Any] = {}

# Store snapshot before updates
PENDING_STORE[(wid, sid)] = sheet.copy()

# Apply or reject updates
if user_accepts:
    # Keep changes
    PENDING_STORE.pop((wid, sid), None)
else:
    # Restore snapshot
    sheet = PENDING_STORE.pop((wid, sid))
```

## Database Integration

### Supabase Client

```python
from supabase import create_client

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"]
)

# Workbook operations
async def save_workbook(workbook: Workbook):
    await supabase.table("workbooks").upsert({
        "id": workbook.wid,
        "sheets": workbook.list_sheets(),
        "updated_at": datetime.now()
    }).execute()
```

### Schema Access

```python
# Get prompts
prompts = await supabase.table("prompts")\
    .select("*")\
    .eq("role", "analyst")\
    .eq("is_active", True)\
    .single()\
    .execute()

# Save chat history
await supabase.table("chat_history").insert({
    "workbook_id": wid,
    "message": message,
    "response": response,
    "timestamp": datetime.now()
}).execute()
```

## API Patterns

### Request/Response Models

```python
# Pydantic models for validation
class ChatRequest(BaseModel):
    message: str
    wid: str
    sid: str
    model: str
    mode: Optional[str] = "ask"
    contexts: Optional[List[str]] = []

class SheetUpdateRequest(BaseModel):
    cell: str
    value: Any
```

### Error Handling

```python
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "code": "VALIDATION_ERROR"}
    )

# In endpoints
try:
    result = await process_request(request)
    return result
except Exception as e:
    logger.error(f"Error processing request: {e}")
    raise HTTPException(status_code=500, detail=str(e))
```

## Performance Considerations

### 1. Concurrency Control
```python
# Limit concurrent LLM requests
llm_concurrency = int(os.getenv("LLM_CONCURRENCY", "5"))
chat_limiter = asyncio.Semaphore(llm_concurrency)

async with chat_limiter:
    response = await agent.run(message)
```

### 2. Caching Strategy
- In-memory workbook cache
- LRU eviction for inactive workbooks
- Periodic persistence to database

### 3. Streaming Optimizations
- Chunk batching for UI updates
- Heartbeat events for connection health
- Graceful degradation on errors

## Testing Patterns

### Unit Tests
```python
@pytest.mark.asyncio
async def test_set_cell():
    sheet = Spreadsheet(rows=10, cols=10)
    result = set_cell("A1", 42, sheet)
    assert result["new_value"] == 42
    assert sheet.get_cell("A1") == 42
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_agent_calculation():
    agent = AskAgent(MockLLMClient())
    result = await agent.run("What is the sum of A1:A10?")
    assert "sum" in result["reply"].lower()
```

### Debugging Tools
```python
# Enable debug logging
DEBUG_STREAMING = os.getenv("DEBUG_STREAMING", "0") == "1"

if DEBUG_STREAMING:
    print(f"[{request_id}] Processing chunk: {chunk}")
```

## Best Practices

1. **Always validate inputs** with Pydantic models
2. **Use dependency injection** for testability
3. **Handle errors gracefully** with proper status codes
4. **Log important events** with structured logging
5. **Keep state minimal** - prefer stateless operations
6. **Use async/await** throughout for scalability
7. **Document tools clearly** for LLM understanding 