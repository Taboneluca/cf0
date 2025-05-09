# cf0.ai - MVP FINALIZATION ROADMAP  
*(Last updated 2025-05-09 – Internal use only)*  

---

## 0. Reading Guide  
• Each numbered **Phase** is meant to be executed sequentially.  
• Inside a phase, tasks are in the exact order they should be coded.  
• Every task block contains: **Goal ▸ Affected Files ▸ Exact Edits ▸ Test/Done-When**.  
• Paths are **relative to workspace root**.  
• Search tokens like `{{ NEW }}` or `// <<< ADD` are literal strings you will insert to make PR diffs obvious.  
• After finishing a task, run the matching "Done-When" check before moving on.

---

## TABLE OF CONTENTS
1. Guiding Principles & Coding Standards  
2. Project Topology Cheat-Sheet  
3. PHASE 1 – LLM Provider Abstraction  
4. PHASE 2 – Secure Per-User API Keys & Multi-Tenancy  
5. PHASE 3 – Template Spreadsheet Tools (3-Stmt, DCF, M&A)  
6. PHASE 4 – Agent Loop Enhancements & Stepwise Debug Mode  
7. PHASE 5 – Prompt Versioning & Live Editing  
8. PHASE 6 – Logging, Metrics & Observability  
9. PHASE 7 – Front-End (Model Selector, Dashboard, Debug Panel, Waitlist)  
10. Infrastructure, Deployment & Scaling Notes  
11. Testing Matrix & CI hooks  
12. Roll-Out Timeline / Milestones  

---

## 1. GUIDING PRINCIPLES & CODING STANDARDS
* 100 % type-hint coverage (MyPy –strict passes).  
* Replace **all** `print()` with `logger.*`.  
* No secret literals in repo; rely on `.env`, Doppler or Supabase Vault.  
* Follow the "Open-Closed" rule: every new provider/model is added without changing existing agent code.  
* Every tool gets (a) JSON-schema entry in `agents/tools.py` **and** (b) pytest in `apps/api-gateway/tests/tools/`.

---

## 2. PROJECT TOPOLOGY CHEAT-SHEET
```
apps/
 └─ api-gateway/
     ├─ agents/              ← current agent & tool code
     ├─ spreadsheet_engine/  ← cell ops, template builders
     ├─ db/                  ← SQLAlchemy models (will extend)
     └─ chat/                ← FastAPI routers
 frontend/
     app/…                   ← Next.js (App Router) code
```
Keep these paths in mind as we reference files.

---

## 3. PHASE 1 – LLM PROVIDER ABSTRACTION (MULTI-MODEL)

### 3-1. Create Generic Interface
**Goal** Decouple agents from OpenAI.  
**Affected Files**  
* `apps/api-gateway/agents/base_agent.py`  
* `apps/api-gateway/llm/` `__init__.py`, `base.py` (**new dir**)  

**Exact Edits**  
1.  Add folder:
    ```
    mkdir -p apps/api-gateway/llm/providers
    touch apps/api-gateway/llm/{__init__,base}.py
    ```
2.  **`apps/api-gateway/llm/base.py`** ⤵︎
    ```python
    from abc import ABC, abstractmethod
    from typing import Iterable, Dict, Any

    class LLMClient(ABC):
        name: str                  # "openai:gpt-4o-mini", "anthropic:claude-3-opus" …

        def __init__(self, api_key: str, model: str, **kw): ...

        @abstractmethod
        async def chat(
            self,
            messages: list[dict[str, str|dict]],
            stream: bool = False,
            functions: list[dict[str, Any]] | None = None,
            **params
        ) -> dict: ...

        @property
        @abstractmethod
        def supports_function_call(self) -> bool: ...
    ```
3.  **`apps/api-gateway/agents/base_agent.py`**
    *Top-of-file imports*  
    ```python
    # ... existing code ...
    from llm.base import LLMClient          # <<< ADD
    ```
    *Class signature*  
    ```python
    class BaseAgent:
        def __init__(self, llm: LLMClient, mode: AgentMode, *, user_id: str):
            self.llm = llm
            # ... existing code ...
    ```
    *Replace every direct `openai.chat.completions.create(…)` call with*  
    ```python
    completion = await self.llm.chat(
        messages=chat_messages,
        stream=want_stream,
        functions=tool_schema if self.llm.supports_function_call else None,
        **params,
    )
    ```
    *Remove* `openai_client.py` import lines (they move to providers).

**Done-When** : BaseAgent unit tests pass with a mocked `DummyLLM` implementing the interface.

---

### 3-2. Provider Implementations
**Goal** Support OpenAI, Anthropic, Groq (LLAMA) out-of-box.  
**Affected Files**  
* NEW: `apps/api-gateway/llm/providers/openai_client.py`  
* NEW: `apps/api-gateway/llm/providers/anthropic_client.py`  
* NEW: `apps/api-gateway/llm/providers/groq_client.py`  

**Exact Edits (OpenAI as example)**  
```python
# apps/api-gateway/llm/providers/openai_client.py
from openai import AsyncOpenAI
from llm.base import LLMClient

class OpenAIClient(LLMClient):
    name = "openai"

    def __init__(self, api_key: str, model: str, **kw):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.kw = kw

    async def chat(self, messages, stream=False, functions=None, **params):
        return await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
            functions=functions,
            **self.kw, **params,
        )

    @property
    def supports_function_call(self) -> bool:
        return True
```
Replicate pattern for **Anthropic** (use `anthropic.AsyncAnthropic`) and **Groq** (`groq.AsyncGroq`).  
*Store provider mapping* in `apps/api-gateway/llm/__init__.py`:
```python
from .providers.openai_client import OpenAIClient
from .providers.anthropic_client import AnthropicClient
from .providers.groq_client import GroqClient

PROVIDERS = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "groq": GroqClient,
}
```

**Done-When** :  
`pytest apps/api-gateway/tests/llm/test_provider_interface.py` passes, verifying `.supports_function_call` & `.chat()`.

---

### 3-3. Provider Selection Router
**Goal** Instantiate correct client per request, default `openai:gpt-4o-mini`.  
**Affected Files**  
* `apps/api-gateway/chat/routes.py` (or whichever FastAPI router has `/chat`)  
* `apps/api-gateway/db/models.py` (add `preferred_model`)  
* `apps/api-gateway/chat/schemas.py` (`model` field on ChatRequest)  

**Exact Edits**  
1.  **DB** – Alembic migration:  
    ```sql
    ALTER TABLE users ADD COLUMN preferred_model VARCHAR(64) DEFAULT 'openai:gpt-4o-mini';
    ```
2.  **Pydantic Schema**  
    ```python
    class ChatRequest(BaseModel):
        message: str
        model: str | None = None     # e.g. "anthropic:claude-3-haiku"
        ...
    ```
3.  **Router Logic**  
    ```python
    model_name = req.model or user.preferred_model
    provider_key, model_id = model_name.split(":", 1)
    LLMCls = llm.PROVIDERS[provider_key]
    llm_client = LLMCls(api_key=resolve_user_api_key(user, provider_key), model=model_id)
    agent = AnalystAgent(llm_client, mode=req.mode, user_id=user.id)
    ```
4.  **Frontend** will supply `model` – see Phase 7.

**Done-When** : Switching `model` param in the playground cURL returns from different providers.

---

## 4. PHASE 2 – SECURE PER-USER API KEYS

### 4-1. Database Layer
**Goal** Encrypt & store arbitrary provider keys.  
**Affected Files**  
* `apps/api-gateway/db/models.py`  
* NEW Alembic migration  

**Exact Edits**  
```python
class APIKey(db.Model):
    __tablename__ = "api_keys"
    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"))
    provider = Column(String, nullable=False)     # "openai", "anthropic"
    key_enc = Column(LargeBinary, nullable=False) # AES-GCM encrypted
    created_at = Column(DateTime, default=datetime.utcnow)
```

Encryption helper in `db/crypto.py` using Fernet + env `CF0_MASTER_KEY`.

### 4-2. CRUD Endpoints
* `apps/api-gateway/chat/routes_keys.py` (new router)  
  * POST `/keys/{provider}` – store  
  * DELETE `/keys/{provider}` – revoke  

### 4-3. Injection at Runtime
`resolve_user_api_key(user, provider)` returns decrypted secret or falls back to platform key (env var).

**Done-When** : Unit test proves OpenAI call uses user key when present.

---

## 5. PHASE 3 – TEMPLATE SPREADSHEET TOOLS

### 5-1. Convert Excel Templates ➜ Python Builders
**Goal** Insert 3-Stmt, DCF, M&A models programmatically.  
**Affected Files**  
* NEW `apps/api-gateway/spreadsheet_engine/templates/{three_stmt.py, dcf.py, mna.py}`  
* `apps/api-gateway/agents/tools.py` (schema + dispatcher)  

**Exact Edits (DCF example)**  
1.  **`templates/dcf.py`**  
    ```python
    from .workbook_writer import SheetBuilder

    def build_dcf(
        wb: Workbook,
        sheet_name: str,
        periods: int = 5,
        discount_rate: float = 0.1,
    ) -> None:
        s = wb.create_sheet(sheet_name)
        headers = ["Year"] + [f"Year {i}" for i in range(1, periods+1)]
        s.append(headers)
        # write cash-flow rows ...
    ```
2.  **`agents/tools.py`** add catalog entry  
    ```python
    {
      "name": "insert_dcf_model",
      "description": "Insert a standard discounted cash-flow template.",
      "parameters": {
        "type": "object",
        "properties": {
          "sheet_name": {"type": "string"},
          "periods": {"type": "integer", "default": 5},
          "discount_rate": {"type": "number", "default": 0.1}
        },
        "required": ["sheet_name"]
      }
    }
    ```
3.  **Dispatcher** case:  
    ```python
    elif name == "insert_dcf_model":
        from spreadsheet_engine.templates.dcf import build_dcf
        build_dcf(wb, **args)
    ```

**Done-When** : Manual agent prompt "Create a 5-year DCF" produces correctly-formatted sheet.

---

## 6. PHASE 4 – AGENT LOOP ENHANCEMENTS & STEPWISE DEBUG

### 6-1. Extract Generator Loop
**Affected File**  
`apps/api-gateway/agents/base_agent.py`

**Exact Edits**  
*Refactor* `run()` into:  
```python
async def run_iter(self, user_msg: str) -> AsyncGenerator[ChatResponse, None]:
    # yields after every tool call or model response
```
`run()` becomes a thin wrapper that consumes the generator.

### 6-2. Debug Mode Router
* New FastAPI WS endpoint `/chat/step` streams JSON of each yield (`role`, `content`, `toolCall`, `toolResult`, `usage`).

**Done-When** : Front-end debug panel (Phase 7) shows live steps.

---

## 7. PHASE 5 – PROMPT VERSIONING & LIVE EDITING

### 7-1. DB & API
* Table `prompts` (`id`, `agent_mode`, `text`, `version`, `created_at`, `created_by`, `is_active`).  
* GET `/admin/prompts/{mode}`, POST `/admin/prompts`.

### 7-2. Agent Load
On session start, `BaseAgent` loads active prompt from cache (LRU, 60 s TTL) else DB.

**Done-When** : Changing prompt via admin UI changes behavior on new chat without redeploy.

---

## 8. PHASE 6 – LOGGING, METRICS & OBSERVABILITY

* Install `structlog` + `python-json-logger`.  
* Add ASGI middleware timing all requests.  
* Expose Prometheus `/metrics`.  
* Capture `usage.prompt_tokens` & `usage.completion_tokens` from every provider into histogram `cf0_tokens_total{provider=…,model=…}`.  

---

## 9. PHASE 7 – FRONT-END TASKS

### 9-1. Model Selector Dropdown
**Files**  
* `frontend/components/ui/ModelSelect.tsx` (new)  
* Integrate inside `chat/InputBar.tsx`

```tsx
// ModelSelect.tsx
export const MODELS = [
  { label: "GPT-4o mini", value: "openai:gpt-4o-mini" },
  { label: "Claude 3 Haiku", value: "anthropic:claude-3-haiku" },
  { label: "LLAMA 3 (Groq)", value: "groq:llama3-70b" },
];
...
```

Send selected `.value` along with POST `/chat`.

### 9-2. Dashboard
* Route `frontend/app/dashboard/page.tsx`
* Fetch `/workbooks` list.
* Use shadcn `Card`, `DataTable`.

### 9-3. Debug Panel
* `components/debug/DebugPanel.tsx`
  * Connect to `/chat/step` websocket.
  * Render timeline entries with icons.
  * "Stop" button => `socket.close()`.

### 9-4. Waitlist Page
`frontend/app/waitlist/page.tsx` simple email form hitting `/api/waitlist`.

### 9-5. Visual Polish
* Tailwind theme overrides in `styles/globals.css`  
* Replace default buttons with `shadcn/ui` Button.

**Done-When** : UX walkthrough passes Figma parity checklist.

---

## 10. INFRASTRUCTURE NOTES
* Add `docker-compose.groq.yml` with Groq API sidecar if self-hosted.  
* Horizontal scaling: use `uvicorn --workers ${CPU_CORES}`; global semaphore moved to Redis.  
* Health probes `/health` and Prometheus metrics scraped by Grafana Cloud.

---

## 11. TESTING MATRIX
| Layer | Tool | Location |
|-------|------|----------|
| Unit  | pytest | `apps/api-gateway/tests/` |
| Contract (LLM ↔️ Tools) | `pytest --tags tool-call` | new tests |
| E2E   | Playwright | `frontend/tests/` |
| Load  | Locust | `infra/load/` |

CI job in `.github/workflows/ci.yml` runs all above on PR.

---

## 12. ROLL-OUT PLAN
1. Phase 1 & 2 in a single backend PR – behind `MULTI_MODEL=true` flag.  
2. Phase 3 template tools (demo value add) – demo to finance SME.  
3. Phase 4 & 7 (Debug mode) – flag `DEBUG_UI=true`.  
4. Prompt editor & observability – enable for internal team.  
5. Public waitlist landing & gradual user invites.  

---

### END OF DOCUMENT
