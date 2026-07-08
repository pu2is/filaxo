# CRM Reporting Chatbot MVP 1

AI-powered chatbot for Filax.One, a CRM system for automotive dealerships. Users ask natural-language questions against the CRM database and get back charts, tables, and a saveable personal dashboard.

> Developer Challenge 2026 submission.

## Overview

Instead of dropping users in front of a blank prompt box, the bot leads a **guided funnel**: the user walks down a **thema tree** (theme → sub-theme → sub-sub-theme, max 3 levels — one tree per database domain doc in `docs/`, see decision D5 in [`docs/mvp-request.md`](docs/mvp-request.md)) until the query scope is a small, well-defined set of tables, then picks search conditions (e.g. time range) derived from what those tables actually support. Only at that point does the local LLM translate the natural-language question into T-SQL against that narrow scope — which is what keeps a 7B model accurate and hallucination-poor by construction. Results render as tables (charts, narration, and a pinnable live dashboard follow).

**Status:** The funnel walks the D5 scope tree (thema → leaf) with a breadcrumb undo — pick a thema, drill to a leaf (e.g. "Verkauf & Leads" → "Bewertung & Scoring"), optionally enter a date range with native von/bis date pickers (D6), then ask a question — typed, or picked from a collapsible suggestion panel of recommended questions (D8) — and see a real result table. After every answer the bot offers to continue the same topic, change the Zeitraum, or switch topics entirely (D7), so a session never has to restart just to ask a second question. Click a breadcrumb chip's × to cut back to that level and re-pick without restarting the whole conversation. Charts, narration, and the pinnable dashboard follow.

## Tech Stack

| Layer      | Choice                                                        |
|------------|----------------------------------------------------------------|
| Backend    | Python 3.12 + FastAPI + SQLAlchemy (pyodbc)                    |
| AI/LLM     | Ollama (local) + `qwen2.5-coder:7b`, structured JSON output    |
| SQL safety | sqlglot (T-SQL parse/validate/repair) + read-only DB login     |
| Database   | SQL Server 2022 (ODBC Driver 18)                               |
| Frontend   | Vue 3 + Vite + Tailwind CSS + shadcn-vue + Pinia               |

## Getting Started

### 0. Prerequisite: unpack the sample database

The challenge provides the sample database as `FilaksOne.zip` (git-ignored, ~9.3GB uncompressed — never committed). Extract it into the project root **before** running anything, so that this exact path exists:

```
FilaksOne/FilaksOne.bak
```

If you skip this, `docker compose up` fails within seconds with a `[preflight]` error telling you to do this — it won't silently proceed or hang on a half-broken restore.

### 1. One-command full stack (Docker: SQL Server + Ollama + backend + frontend)

The simplest way to see the app running — no local Python/Node toolchain needed:

```bash
# CPU only (default)
docker compose up -d --build

# With NVIDIA GPU acceleration for Ollama
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

Dev environment tested with an **NVIDIA GeForce RTX 3070 (8GB VRAM)** — `qwen2.5-coder:7b` fits comfortably within that. GPU mode requires the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) installed on the host; without it, `-f docker-compose.gpu.yml` will fail to start `ollama`.

Open **http://localhost:8080** once it's up (first run takes a few minutes: DB restore + pulling the 7B model). This starts:
- `preflight` — fails fast with a clear message if `FilaksOne/FilaksOne.bak` is missing (see step 0)
- `sqlserver` — SQL Server 2022 on `localhost,14330` (`sa` / `Filaks!Pass2026`, admin — used for restore only)
- `db-init` — runs once, restores `FilaksOne` from the mounted `.bak` if it doesn't already exist, then exits
- `db-readonly-init` — runs once after `db-init`, creates the `filaks_readonly` login/user (see below), then exits
- `ollama` — Ollama API on `localhost:11434`
- `ollama-init` — runs once, pulls `qwen2.5-coder:7b`, then exits
- `backend` — FastAPI on `localhost:8000` (built from [`backend/Dockerfile`](backend/Dockerfile); waits for the DB/model init steps above)
- `frontend` — the built Vue SPA served by nginx on `localhost:8080` (built from [`frontend/Dockerfile`](frontend/Dockerfile); waits for `backend`)

**Verify it worked:**

```bash
# Model is present
docker compose exec ollama ollama list

# Database is restored and queryable from the host (admin login)
sqlcmd -S localhost,14330 -U sa -P "Filaks!Pass2026" -C -Q "SELECT COUNT(*) FROM sys.tables"

# Backend is up
curl http://localhost:8000/health   # {"status":"ok"}
```

Re-running `docker compose up` is safe — `db-init` checks whether `FilaksOne` already exists before restoring, `db-readonly-init` checks whether the login/user already exist, and `ollama pull` is a no-op if the model is already present.

### 2. Native dev (Docker: SQL Server + Ollama only)

For active development with hot-reload, run just the infra in Docker and the backend/frontend natively — see [Backend](#backend) and [Frontend](#frontend) below. Bring up only the infra services:

```bash
docker compose up -d sqlserver db-init db-readonly-init ollama ollama-init
```

### Application Database Login (Read-Only)

The app must never connect with `sa`. `docker/create-readonly-user.sql` (applied automatically by `db-readonly-init`) creates a `filaks_readonly` login scoped to `db_datareader` on `FilaksOne` only — `SELECT` works, `INSERT`/`UPDATE`/`DELETE`/`DDL` are rejected by SQL Server itself regardless of what the app or an LLM-generated query attempts. See [`.env.example`](.env.example) for the connection string the backend should use.

```bash
# Read-only connectivity check from the host
sqlcmd -S localhost,14330 -U filaks_readonly -P "Filaks!ReadOnly2026" -d FilaksOne -C -Q "SELECT COUNT(*) FROM cobra.CrmLead"
```

### Backend

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Verify
curl http://127.0.0.1:8000/health   # {"status":"ok"}

# Chat endpoint (guided funnel, Phase 1) -- session_id: null starts a fresh session
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": null, "action": "start"}'
```

Requires ODBC Driver 18 for SQL Server on the host (needed by `pyodbc`). Copy [`.env.example`](.env.example) to `.env` to override defaults (DB/LLM connection settings).

### AI Core Eval (`run_query`)

Requires the Docker dev environment above to be running (SQL Server + Ollama). No frontend needed — this is the pure-backend proof that the NL-to-SQL core works end to end.

```bash
cd backend
python scripts/eval_query.py
```

Runs every DB-verified question in `modules/schema/question_bank.yaml`, plus 2 planted out-of-scope probes, through `run_query()` — the single entry point chaining schema cards → LLM SQL generation (with a deterministic `TOP N` template for ranking questions) → sqlglot validation → DB execution, with error-feedback retry. Prints per-question SQL, row sample, pass/fail, and latency, then a summary (pass rate, avg/min/max latency).

```bash
# One-off manual check
python -c "from modules.query.engine import run_query; print(run_query('Wie viele Leads gibt es?', ['cobra.CrmLead']))"
```

### Frontend

Chat UI (guided funnel walking skeleton): conversation history, choice buttons pinned above the input, and session restart, backed by a Pinia store. Expects the backend on `http://localhost:8000` (override via `.env`, see [`frontend/.env.example`](frontend/.env.example)); the backend's CORS allowlist covers the default Vite port 5173 only.

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### LLM Smoke Test (T-SQL generation quality/latency)

Requires the Docker dev environment above to be running (Ollama on `localhost:11434`).

```bash
python scripts/smoke_test_llm.py
```

Sends a `cobra.CrmLead` schema card + 1 few-shot example + 5 German questions to Ollama, printing the generated T-SQL and wall-clock latency per question. First-run findings (dialect errors, markdown-fence output, cold-start latency) are recorded in `docs/mvp-request.md`'s 7B risk/mitigation table.

### LangGraph Spike

No external dependencies — pure Python.

```bash
cd backend
python spikes/langgraph_hello.py
```

Toy 3-node `StateGraph` (`generate_sql` → `validate_sql` → `finish`) with a conditional edge and a retry cycle; prints the execution log and a mermaid diagram. De-risks LangGraph mechanics ahead of the real Phase 2 pipeline.

## Project Structure

```
backend/
├── main.py                    FastAPI app entrypoint
├── Dockerfile                 Python 3.12 + ODBC Driver 18, serves on :8000
├── modules/
│   ├── chat/
│   │   ├── router.py          POST /api/chat (single endpoint for every action)
│   │   ├── service.py         Phase 1 canned conversation steps (greeting -> scope confirmation)
│   │   ├── session_store.py   In-memory {session_id: SessionState}
│   │   └── schemas.py         ChatRequest / ChatResponse wire format (frozen contract)
│   ├── query/
│   │   ├── executor.py        Read-only DB execution gateway
│   │   ├── validator.py       sqlglot T-SQL parse/validate/repair (blocks DML/DDL, injects TOP)
│   │   ├── engine.py          run_query() — the AI core's single entry point
│   │   └── ranking.py         Deterministic TOP-N template for ranking questions
│   └── schema/
│       ├── schema_cards.py    Compressed DDL + column whitelist per table
│       ├── question_bank.py   Loader for question_bank.yaml (few-shots + eval set)
│       └── question_bank.yaml DB-verified question -> SQL base set
├── shared/                    db.py, llm.py (LLMProvider/OllamaProvider), prompts.py, config.py, exceptions.py
├── scripts/eval_query.py      AI core eval harness (see AI Core Eval above)
└── spikes/                    LangGraph POC
frontend/                Vue 3 + Vite + Tailwind + shadcn-vue SPA
├── Dockerfile                 Multi-stage: npm build → served by nginx on :80
├── nginx.conf                 SPA fallback (try_files -> index.html)
├── src/features/chat/         Chat UI: components + Pinia store (stores/chat.store.ts) + contract types
├── src/features/{result,dashboard,traceability}/   Later goals (placeholders)
└── src/shared/api/            Typed fetch client for the /api/chat contract
docker/                  create-readonly-user.sql (read-only DB login, run by db-readonly-init)
scripts/                 DB restore (restore-db.sh/.sql) + LLM smoke test (smoke_test_llm.py)
docker-compose.yml       Local dev environment: preflight, SQL Server, Ollama, backend, frontend
docker-compose.gpu.yml   Optional GPU overlay for Ollama (see Getting Started above)
.env.example             Backend config template (DB + LLM connection settings)
FilaksOne/               Local sample database backup (git-ignored — extract FilaksOne.zip here, see Getting Started step 0)
docs/                    Design docs and database domain documentation (git-ignored, WIP)
```
