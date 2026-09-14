# Multi-Hospital Post-Discharge Outreach Platform

End-to-end, multi-tenant, queue-driven, safety-conscious AI outreach platform.
Backend (FastAPI + PostgreSQL) + Frontend (Next.js) are fully wired: login,
dashboards, campaigns, AI call pipeline, queue, escalations, EHR mock, AI
observability, safety benchmark, and health monitoring all work out of the box
with **zero real API keys** (offline mock AI + simulated voice).

## 60-second demo (do this first)

```bash
# 1) backend (needs PostgreSQL running; tables + demo data auto-seed)
uvicorn app.main:app --app-dir backend
# 2) frontend (new terminal)
cd frontend && npm install && npm run dev
# 3) open http://localhost:3000 → Sign in:
#    admin@stmarys.demo / Demo@123   (hospital user — dashboards, campaigns, calls)
#    admin@platform.local / Demo@123 (platform admin — onboarding)
# 4) Dashboard → "Run 10 AI calls now" → every chart fills (calls, escalations, AI logs)
```

Demo accounts (password `Demo@123` for all): `admin@platform.local`
(PLATFORM_ADMIN), `admin@stmarys.demo` (HOSPITAL_ADMIN),
`campaign@stmarys.demo` (CAMPAIGN_MANAGER), `clinical@stmarys.demo`
(CLINICAL_REVIEWER) — plus the same four roles at `@riverside.demo`.

## What's implemented end-to-end

- **Auth/RBAC/multi-tenancy**: JWT + `TenantContextMiddleware`; every query
  scoped by JWT `hospital_id`; 401/403/404 verified (`python smoke_test.py`,
  `backend/tests/test_auth.py`, `test_tenant_isolation.py`).
- **Full call pipeline** (`backend/app/services/call_orchestrator.py`):
  simulated voice intake → protocol-grounded triage → 3-agent consensus →
  documentation → EHR write → escalation on urgent/uncertain → queue advance.
  Idempotent per queue task (replays return the existing Call, no duplicate
  side effects). Trigger: `POST /api/v1/calls/process-next`,
  `POST /api/v1/calls/demo-batch?count=N`, or `POST /api/v1/calls/process/{task_id}`.
- **Dashboards**: `GET /api/v1/dashboard/campaign-manager|admin|platform`,
  `GET /api/v1/queue/status`, WS `GET /api/v1/ws/queue-stream` + UI at
  `/dashboard`, `/campaigns`, `/campaigns/[id]/live`, `/calls`, `/escalations`,
  `/patients`, `/admin/{ai-inspector,safety,health,onboard}`.
- **AI layer**: provider-neutral adapter (`app/ai/llm_provider.py`), protocol
  RAG (`app/ai/rag/protocol_retriever.py`), consensus council
  (`app/ai/consensus_council.py`), observability (`ai_logs` +
  `GET /api/v1/ai/metrics|logs|provider-status`), fixed 30-case safety
  benchmark (`POST /api/v1/safety/run-eval`, `/admin/safety`).
- **Queue**: priority + concurrency semaphore (Redis w/ in-memory fallback),
  retry backoff + calling-hours, stuck-task reclaimer, manual follow-ups,
  campaign lifecycle (DRAFT→RUNNING→PAUSED→COMPLETED).

## API keys / external keys (free open-model chain, zero cost)

| Priority | Provider | Env vars (`backend/.env`) | Free key from | Model |
|---|---|---|---|---|
| 1 | **Groq** (default) | `GROQ_API_KEY GROQ_MODEL` | console.groq.com/keys | `openai/gpt-oss-120b` |
| 2 | OpenRouter | `OPENROUTER_API_KEY OPENROUTER_MODEL` | openrouter.ai/keys | free models (`:free`) |
| 3 | Google Gemini | `GOOGLE_API_KEY GOOGLE_MODEL` | aistudio.google.com/apikey | `gemini-2.5-flash` |
| — | Ollama (local) | `AI_PROVIDER=ollama` | none needed | `llama3.2` |
| — | Deterministic fallback | automatic | none | built-in, fail-closed |

If a provider fails, the next takes over automatically; if all fail, triage
fail-closes to the deterministic adapter — nothing ever breaks. Until you paste
your free keys, triage runs deterministic (chain shown on the AI inspector page).
Full map: `docs/EXTERNAL_KEYS.md`. Integration points:
`app/ai/llm_provider.py` (chain implemented, OpenAI-compatible + Ollama),
`app/services/voice_provider.py::place_call()` (telephony).

## Local setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL / JWT_SECRET_KEY for your machine
```

You'll need a running PostgreSQL instance matching `DATABASE_URL` in `.env`.
Tables are created automatically on startup via `Base.metadata.create_all`
for this milestone (a real Alembic migration chain should replace this
before production).

Run the API:
```bash
uvicorn app.main:app --reload --app-dir backend
```

## Running tests

Tests never touch your real Postgres DB — `tests/conftest.py` forces
`DATABASE_URL=sqlite://` (in-memory) before the app is imported, so the
suite is fully self-contained.

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

Run the frontend after installing its dependencies:

```bash
cd frontend
npm install
npm run dev
```

For a full local stack, use `docker compose up --build` from the repository root.

## Environment variables

See `backend/.env.example`. All secrets (DB connection string, JWT secret)
are loaded exclusively from environment variables — nothing is hardcoded.

