# Filax.One — CRM Reporting Chatbot

AI-powered chatbot for Filax.One, a CRM system for automotive dealerships. Users ask natural-language questions against the CRM database and get back charts, tables, and a saveable personal dashboard.

> Developer Challenge 2026 submission.

## Overview

Instead of dropping users in front of a blank prompt box, the bot leads a **guided funnel**: the user walks down a **thema tree** (theme → sub-theme → sub-sub-theme, max 3 levels — one tree per database domain doc in `docs/`, see decision D5 in [`docs/mvp-request.md`](docs/mvp-request.md)) until the query scope is a small, well-defined set of tables, then picks search conditions (e.g. time range) derived from what those tables actually support. Only at that point does the local LLM translate the natural-language question into T-SQL against that narrow scope — which is what keeps a 7B model accurate and hallucination-poor by construction. Results render as tables (charts, narration, and a pinnable live dashboard follow).

**Status:** First full demo: funnel → question → live data table. Click through the guided funnel, type a natural-language question, and see a real result table rendered from the CRM database (Big Goal 4, Wave 1). Charts, narration, and the pinnable dashboard follow.

_TODO: demo screenshot/GIF._

## Tech Stack

| Layer      | Choice                                                        |
|------------|----------------------------------------------------------------|
| Backend    | Python 3.12 + FastAPI + SQLAlchemy (pyodbc)                    |
| AI/LLM     | Ollama (local) + `qwen2.5-coder:7b`, structured JSON output    |
| SQL safety | sqlglot (T-SQL parse/validate/repair) + read-only DB login     |
| Database   | SQL Server 2022 (ODBC Driver 18)                               |
| Frontend   | Vue 3 + Vite + Tailwind CSS + shadcn-vue + Pinia               |

## Getting Started

### Dev Environment (Docker: Ollama + SQL Server)

Brings up a local SQL Server 2022 instance restored from the sample `FilaksOne.bak`, plus an Ollama instance with `qwen2.5-coder:7b` pulled — everything the backend needs to run against locally.

**Prerequisites:** Docker Desktop running, and `FilaksOne/FilaksOne.bak` present locally (see [Database Connection](#) in project docs — the file is git-ignored and must be supplied separately).

```bash
# CPU only (default)
docker compose up -d

# With NVIDIA GPU acceleration for Ollama
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

This starts these services:
- `sqlserver` — SQL Server 2022 on `localhost,14330` (`sa` / `Filaks!Pass2026`, admin — used for restore only)
- `db-init` — runs once, restores `FilaksOne` from the mounted `.bak` if it doesn't already exist, then exits
- `db-readonly-init` — runs once after `db-init`, creates the `filaks_readonly` login/user (see below), then exits
- `ollama` — Ollama API on `localhost:11434`
- `ollama-init` — runs once, pulls `qwen2.5-coder:7b`, then exits

**Verify it worked:**

```bash
# Model is present
docker compose exec ollama ollama list

# Database is restored and queryable from the host (admin login)
sqlcmd -S localhost,14330 -U sa -P "Filaks!Pass2026" -C -Q "SELECT COUNT(*) FROM sys.tables"
```

Re-running `docker compose up` is safe — `db-init` checks whether `FilaksOne` already exists before restoring, `db-readonly-init` checks whether the login/user already exist, and `ollama pull` is a no-op if the model is already present.

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
├── src/features/chat/         Chat UI: components + Pinia store (stores/chat.store.ts) + contract types
├── src/features/{result,dashboard,traceability}/   Later goals (placeholders)
└── src/shared/api/            Typed fetch client for the /api/chat contract
docker/                  create-readonly-user.sql (read-only DB login, run by db-readonly-init)
scripts/                 DB restore (restore-db.sh/.sql) + LLM smoke test (smoke_test_llm.py)
docker-compose.yml       Local dev environment (SQL Server + Ollama)
docker-compose.gpu.yml   Optional GPU overlay for Ollama (see Dev Environment above)
.env.example             Backend config template (DB + LLM connection settings)
FilaksOne/               Local sample database backup (git-ignored)
docs/                    Design docs and database domain documentation (git-ignored, WIP)
```

## Documentation

_TODO: link to architecture, database domain docs, and API reference once published._

## License

_TODO._
