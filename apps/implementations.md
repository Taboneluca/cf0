## Implementation Roadmap – AI Spreadsheet Assistant Enhancements

This document is the **single-source of truth** for the next engineering cycle.  It is organised into **9 sequential phases**.  Each phase contains:

• Goal & success criteria  
• Detailed technical steps (backend ☁️ / frontend 💻)  
• Concrete code-diff sketches (`path/to/file.py:+new-lines|-deleted`)  
• Rationale / gotchas

Follow the phases in order – later phases assume earlier refactors are in place.  Every checklist item must close via PR referencing the relevant task-id in Linear.

---

### Phase 0 — Project Preparation

| Checklist | Owner |
|-----------|-------|
| ☐ Create *enhancement* branch `feat/assistant-v2` from trunk | Lead Dev |
| ☐ Enable **CI required checks**: `pytest`, `ruff`, `mypy` | Dev-Ops |
| ☐ Add `.env.example` keys `PROMPTS_SUPABASE_URL`, `PROMPTS_SUPABASE_KEY` | Docs |

---

### Phase 1 — Robust & Role-Specific Prompting

**Goal**: Each agent (Ask 📰 / Analyst ✏️) always receives
1. A stable, versioned role prompt pulled from Supabase.
2. A *dynamic* sheet snippet so the model knows the live context.

#### 1.1  Supabase prompt table migration ☁️
Schema (run via `supabase/migrations`):
```sql
create table role_prompts (
  id bigint generated always as identity primary key,
  mode text not null check (mode in ('ask','analyst')),
  version text default 'v1.0',
  content text not null,
  active boolean default false,
  inserted_at timestamptz default now(),
  unique (mode) where active  -- only one active per mode
);
```
➡️  Insert v1.0 rows manually (see `/docs/prompts/*.md`).

#### 1.2  Backend: add `sheet_context` injection
`apps/api-gateway/agents/base_agent.py`
```python:@@class BaseAgent.__init__@
-        self.system_prompt = get_active_prompt(agent_mode)
+        base_prompt = get_active_prompt(agent_mode)
+
+        # Allow caller to pass an optional runtime context.
+        sheet_ctx: str | None = kwargs.pop('sheet_context', None)
+
+        # Concatenate keeping a blank line separator so formatting is stable.
+        self.system_prompt = base_prompt.strip()
+        if sheet_ctx:
+            self.system_prompt += f"\n\n{sheet_ctx.strip()}"
```

**Why**: keeps DB prompt untouched while enriching with volatile sheet data.

#### 1.3  Router augmentation
`apps/api-gateway/chat/router.py`
```python:+40  (inside process_message & _streaming/_common helper)
summary = sheet_summary(sheet)
ctx = f"[Context] Active sheet '{summary['name']}' has {summary['rows']} rows × {summary['columns']} cols; Headers: {summary['headers']}."

agent_extra = dict(sheet_context=ctx)
...
agent = build_ask_agent(llm).clone_with_tools(tool_functions)
agent.add_system_message(ctx)  # For back-compat in existing BaseAgent
```
(Once BaseAgent signature is refactored we will switch to `BaseAgent(..., sheet_context=ctx)`.)

**File changes (Phase 1)**
• `supabase/migrations/xxxxxxxx_role_prompts.sql` – new table.  
• `apps/api-gateway/agents/base_agent.py` – constructor patch above.  
• `apps/api-gateway/chat/router.py` – context snippet injection.  
• `db/prompts.py` – add `@lru_cache` TTL=60 s if missing.  
• `.env.example` – new keys `PROMPTS_SUPABASE_URL` & `PROMPTS_SUPABASE_KEY`.

---

### Phase 2 — Token-by-token Streaming Across Providers

**Goal**: Uniform streaming for OpenAI, Anthropic, Groq.

1. **LLM client audit** – ensure each `*.stream_chat()` yields `AIResponse` with incremental `content` _and_ partial `tool_calls`.
2. **Router SSE contract** – currently emits `{type:'chunk', text}`.  
   • Extend with `event: update` when a tool result mutates the copy-sheet.  
   • Close stream with `{type:'complete', sheet:sheet_snapshot}`.
3. **Frontend** — `/hooks/useChatStream.ts`
   ```ts
   if (evt.type==='chunk') appendToMessage(evt.text);
   else if (evt.type==='update') optimisticSheetPatch(evt.payload);
   else if (evt.type==='complete') setSheet(evt.sheet);
   ```

**Diff sketch** (router streaming loop):
```python:@@async for chunk in agent.stream_run@
if chunk.kind=='tool_result' and chunk.name!='get_cell':
    yield { 'type':'update', 'payload': chunk.toolResult }
elif chunk.kind=='text':
    yield { 'type':'chunk', 'text': chunk.content }
```

#### 2.4  "Thinking…" placeholder bubble

**Problem**: Users see no visual feedback for ~500 ms while the first tokens arrive.  We surface an immediate *thinking* bubble that is later replaced by streamed text.

1. **Backend**  `apps/api-gateway/chat/router.py`
   ```python:+12  (inside process_message_streaming before agent.stream_run)
   # Notify client that the assistant has started processing
   yield { 'type': 'start' }   # <-- new event
   ```

2. **Frontend**  `frontend/hooks/useChatStream.ts`
   ```ts:+25
   else if (evt.type==='start') {
     // Insert a blank assistant bubble with spinner
     dispatch(addAssistantThinkingMessage())
   }
   ```

3. **Frontend**  `frontend/components/chat/Message.tsx`
   ```tsx:+15
   if (msg.status==='thinking') return <Bubble> <Spinner/> …thinking… </Bubble>;
   ```

4. **Stream replacement logic**  – first `chunk` for that message id swaps `status` to `streaming` and appends text; `done` event sets `status:'complete'`.

**File changes (Phase 2)**
• `apps/api-gateway/chat/router.py` – emit `'start'`, include update/complete events.  
• `frontend/hooks/useChatStream.ts` – handle `'start' | 'chunk' | 'update' | 'complete'`.  
• `frontend/components/chat/Message.tsx` – add `thinking` rendering branch.  
• Optional: `frontend/types.ts` – extend SSE union type.

---

### Phase 3 — Pending Edits & Accept / Reject UI

#### 3.1  Agent **dry-run** execution
Inside `chat/router.process_message[_streaming]`
```python
sheet_copy = sheet.clone()
# bind mutating tools to copy
...
agent = agent.clone_with_tools(tool_functions_copy)
result = await agent.run(...)
proposed_updates = result.get('updates', [])
```
No changes are committed yet.

#### 3.2  SSE `pending` event
```python
yield { 'type':'pending', 'updates': proposed_updates }
```

#### 3.3  Frontend UX
* Location:* just above `<MessageInput />` :
```tsx
<PendingBar visible={pending.length>0}>
  <Button onClick={applyAll}>Apply All</Button>
  <Button variant="ghost" onClick={rejectAll}>Reject All</Button>
</PendingBar>
```
* Chat bubble annotations:* while streaming, render grey bubbles e.g. "→ Editing *Revenue* column…". Map from each `update` group.

#### 3.4  Commit endpoint
`POST /workbook/{wid}/sheet/{sid}/apply`
Input: `{updates:[...]}`  – calls current `set_cells_with_xref`.

**File changes (Phase 3)**
• `apps/api-gateway/chat/router.py`
  – clone `sheet` → `sheet_copy` and wire mutating tools.  
  – emit `'pending'` SSE event.  
  – new `POST /apply` FastAPI route (or reuse existing).  
• `frontend/components/PendingBar.tsx` – new component.  
• `frontend/hooks/useChatStream.ts` – handle `'pending'`.  
• `frontend/pages/api/apply.ts` – call workbook apply endpoint.

---

### Phase 4 — Model Swapping Without Context Loss

1. Add `<ModelSelect />` in header – populates options via `/api/models` (already returns catalog).
2. Extend chat request schema with `model` field (already supported).  
3. Persist conversation history `memory.py` keyed by workbook; unchanged between models.
4. `trim_history` update – use `llm.max_context` from catalog (`llm.catalog[key]['max_tokens']`).

**File changes (Phase 4)**
• `frontend/components/header/ModelSelect.tsx` – dropdown.  
• `frontend/hooks/useChat.ts` – include `model` in POST body.  
• `apps/api-gateway/chat/router.py` – pass model → `get_client`.  
• `apps/api-gateway/chat/token_utils.py` – read per-model `max_tokens`.  
• `apps/api-gateway/llm/catalog.py` – add `max_tokens` & `supports_tools`.

---

### Phase 5 — Professional Sheet Output

*Prompt additions*
```md
• When outputting tables, use the first row as **bold headers**.  
• Prefer horizontal grouping: metrics in columns, observations in rows.  
• Separate logical sections by one blank row.  
• Use provided templates (insert_dcf_template, insert_fsm_template) when relevant.
```
Add to Supabase prompt `analyst` v1.1.

Optional: add new tool `format_range(style:str)` later.

**File changes (Phase 5)**
• `/docs/prompts/analyst_v1.1.md` – new prompt text.  
• `supabase` – INSERT new row in `role_prompts`.  
• (optional) `agents/tools.py` – new `format_range` spec & Python stub.

---

### Phase 6 — Advanced Reasoning & Guardrails

1. **Orchestrator** (`agents/orchestrator.py`) – routes ask/analyst or multi-step plan.  
2. **Evaluator** – after Analyst draft, run AskAgent with policy prompt _"judge compliance"_.  If `score<0.5` -> inject system retry.
3. **Rule checks** – implement `validate_updates(updates)` inside router; raise if cell beyond `J30` or formula when not allowed.

**File changes (Phase 6)**
• `apps/api-gateway/agents/orchestrator.py` – new class.  
• `apps/api-gateway/agents/evaluator_agent.py` – policy checker.  
• `apps/api-gateway/chat/router.py` – call `orchestrator.run(...)`.  
• `apps/api-gateway/chat/validators.py` – `validate_updates`.  
• `requirements.txt` – add `pydantic[email]` if evaluator uses scoring.

---

### Phase 7 — UI Polish

• "Section bubble" rendering: when `chunk` starts with `## <title>` create a sub-bubble header.  
• Scroll anchoring & typing indicator remain.

**File changes (Phase 7)**
• `frontend/components/chat/Message.tsx`
  – detect `##` heading in stream and spawn sub-bubble.  
• `frontend/styles/chat.css` – nested bubble styling.

---

### Phase 8 — Codebase Structure Improvements

1. **Create sub-packages**
```
apps/api-gateway/
  core/
    agents/
    llm/
    sheets/
  api/          # FastAPI routers
  infrastructure/
```
2. Migrate modules; update import paths.
3. Introduce `pyproject.toml` and enable `poetry` for dependency locking.

**File changes (Phase 8)**
• Move packages into `apps/api-gateway/core/**`.  
• Update every `import` via `sed` or `ruff --fix-import-s`.  
• `pyproject.toml` – new Poetry config.  
• `Dockerfile` – switch from `pip install -r` → `poetry install`.

---

### Phase 9 — Testing & Roll-out

• Unit tests for each tool & validator (`pytest -k tool`).  
• Integration test: fake LLM that echoes tool calls – assert router returns `pending` event.
• Canary deploy to `staging.assistant.app` → internal QA.  
• Gradual rollout 10% → 100%.

**File changes (Phase 9)**
• `.github/workflows/ci.yml` – add `pytest`, `ruff`, `mypy` jobs.  
• `apps/api-gateway/tests/test_tools.py` – unit tests.  
• `apps/api-gateway/tests/test_router_stream.py` – SSE integration test.  
• `vercel.json` / Railway config – streaming timeouts.

---

### Appendix — Reference Snippets

1. **Event payloads**
```json
{ "type":"pending", "updates":[{ "cell":"B2", "new":42 }] }
{ "type":"update",  "payload":{"cell":"B2","new":42} }
{ "type":"chunk",   "text":"Computing total…" }
```

2. **Tool schema** (no change)
```python
TOOL_CATALOG = [
  {"name":"set_cell", "description":..., "parameters":...},
  ...
]
```

3. **Supabase prompt fetch** (60 s LRU cache) already in `db/prompts.py`.

---

> **End-to-end completion target:** *3 engineering weeks*.  Track progress in Linear project `SPRS-AI-V2`.