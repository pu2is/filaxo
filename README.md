# Filax.One — CRM Reporting Chatbot

AI-powered chatbot for Filax.One, a CRM system for automotive dealerships. Users ask natural-language questions against the CRM database and get back charts, tables, and a saveable personal dashboard.

> Developer Challenge 2026 submission.

## Overview

_TODO: short product description and demo screenshot/GIF._

## Tech Stack

_TODO: backend, AI/LLM, database, frontend — see project docs._

## Getting Started

_TODO: prerequisites, environment setup, and run instructions for backend/frontend._

### Dev Environment (Docker: Ollama + SQL Server)

Brings up a local SQL Server 2022 instance restored from the sample `FilaksOne.bak`, plus an Ollama instance with `qwen2.5-coder:7b` pulled — everything the backend needs to run against locally.

**Prerequisites:** Docker Desktop running, and `FilaksOne/FilaksOne.bak` present locally (see [Database Connection](#) in project docs — the file is git-ignored and must be supplied separately).

```bash
# CPU only (default)
docker compose up -d

# With NVIDIA GPU acceleration for Ollama
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

This starts four services:
- `sqlserver` — SQL Server 2022 on `localhost,14330` (`sa` / `Filaks!Pass2026`)
- `db-init` — runs once, restores `FilaksOne` from the mounted `.bak` if it doesn't already exist, then exits
- `ollama` — Ollama API on `localhost:11434`
- `ollama-init` — runs once, pulls `qwen2.5-coder:7b`, then exits

**Verify it worked:**

```bash
# Model is present
docker compose exec ollama ollama list

# Database is restored and queryable from the host
sqlcmd -S localhost,14330 -U sa -P "Filaks!Pass2026" -C -Q "SELECT COUNT(*) FROM sys.tables"
```

Re-running `docker compose up` is safe — `db-init` checks whether `FilaksOne` already exists before restoring, and `ollama pull` is a no-op if the model is already present.

## Project Structure

```
backend/              FastAPI app, LLM integration, DB queries
frontend/             Vue 3 SPA
docker/               Per-service Dockerfiles and container config
scripts/              Dev/ops scripts (e.g. DB restore)
docker-compose.yml    Local dev environment (Ollama + SQL Server)
FilaksOne/            Local sample database backup (git-ignored)
docs/                 Design docs and database domain documentation (git-ignored, WIP)
```

## Documentation

_TODO: link to architecture, database domain docs, and API reference once published._

## License

_TODO._
