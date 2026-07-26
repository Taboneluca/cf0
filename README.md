# cf0 — AI spreadsheet analyst (2025 prototype)

> **Archived.** The original 2025 prototype of cf0, kept public as a record of the early
> architecture. It is no longer maintained, and the hosted services it depended on (Supabase,
> Railway) have been torn down. The product was later rebuilt on a different stack; this
> repository is not that system.

An AI assistant that works directly inside a spreadsheet, in two modes:

- **Ask** — answer questions about the data in the open workbook.
- **Analyst** — build and edit financial models, writing real formulas into cells.

The core problem was keeping a language model and a live spreadsheet in agreement. The model
plans and proposes changes; a deterministic engine applies them, recalculates, and validates the
result. Numbers come from the sheet, not from the model.

## Architecture

**Agent layer** (`apps/api-gateway/agents/`) — a planner decomposes a request, an orchestrator
routes it to the `ask` or `analyst` agent, and an evaluator checks the output before it is
committed to the workbook.

| File | Role |
| --- | --- |
| `planner.py` | Breaks a request into steps |
| `orchestrator.py` | Routes work between agents and tools |
| `ask_agent.py` / `analyst_agent.py` | The two user-facing modes |
| `evaluator_agent.py` | Validates proposed changes before they land |
| `tools.py` | Tool definitions exposed to the model |

**Spreadsheet engine** (`apps/api-gateway/spreadsheet_engine/`) — an independent, deterministic
cell model that never asks the model to do arithmetic.

| File | Role |
| --- | --- |
| `formula_engine.py` | Formula parsing and evaluation |
| `dag_recalc.py` | Dependency-graph recalculation on cell change |
| `model.py` / `dataframe_model.py` | Cell and workbook representation |
| `operations.py` | Mutations applied to the workbook |
| `templates/` | DCF, three-statement, FSM and M&A model templates |

Financial model structure lives in those template modules rather than in prompts. The model
selects and parameterises a template; the engine generates the formulas.

## Layout

```
apps/frontend      Next.js + React + Tailwind — spreadsheet grid and chat panel
apps/api-gateway   FastAPI — agents, chat routing, spreadsheet engine
apps/workers       Python workers for background jobs
libs/common        Shared types and utilities
supabase/          Database schema migrations
```

## Stack

Nx monorepo · Next.js · FastAPI · Python 3.12 · Postgres via Supabase · OpenAI (with Anthropic
support) · Docker Compose · Vercel and Railway · Sentry.

## Running locally

Requires Node.js 18+, Python 3.12+, Docker Desktop, and your own Supabase project.

```bash
docker compose up --build     # API + workers
nx serve frontend             # UI on :3000, API docs on :8000/docs
```

Environment files — see `.env.example` for the full list. No real credentials belong in this
repository.

`apps/frontend/.env.local`

```
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
```

`apps/api-gateway/.env` and `apps/workers/.env`

```
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/postgres?sslmode=require
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
OPENAI_API_KEY=<openai-key>
```

## Commands

```bash
npm start            # all services in dev mode
npm run dev:frontend # or dev:api, dev:workers
npm run build
npm run test
npm run lint
```

## Database

Migrations live in `supabase/migrations/` and are committed to Git.

```bash
supabase link --project-ref <project-ref>
supabase db pull      # sync current schema
supabase db push      # apply new migrations
```

## Deployment (as originally configured)

Frontend deployed to Vercel on push to `main`. API gateway and workers deployed to Railway via
GitHub Actions, using a matrix build so each service built independently, with watch paths to
skip unaffected services. These pipelines are inactive now that the backing services are gone.
