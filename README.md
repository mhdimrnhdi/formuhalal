# Halal Formulation & Sourcing Engine

A digital B2B decision-support system for SME food manufacturers to find Halal-certified ingredient substitutes and source from local Malaysian suppliers.

## Project Overview

Malaysian SMEs often lack food science expertise to find Halal-compliant substitutes when ingredients become unavailable.

## Python tooling

All Python services (`frontend`, `backend`, `etl_pipeline`) use:

- **Python** `3.14.*` (see each service’s `.python-version`)
- **uv** `0.8.*` (`required-version` in each `pyproject.toml`; Docker images install `uv==0.8.24`)
- **Ruff** `0.15.*` for formatting (`uv run --group dev ruff format …`)

From the repo root:

```bash
./scripts/format-python.sh
```

Per service (example for ETL):

```bash
cd etl_pipeline && uv sync --group dev && uv run --group dev ruff format src/
```

## Setup & Installation

```bash
# Frontend (FastAPI server with uv)
cd frontend
# Build CSS
node build.mjs
# Run development server (auto-reload)
uv run dev.py
# Or run directly
uv run uvicorn --app-dir src --host 0.0.0.0 --port 8000 app:app
```

```bash
# Backend (Flask API)
cd backend
uv sync --group dev
uv run flask --app src.app run --host 0.0.0.0 --port 8001

# ETL pipeline (see etl_pipeline/README.md)
cd etl_pipeline
uv sync --group dev
export DATA_DIR=../data
uv run python src/run.py
```

## Features

- Ingredient substitution with chemical property matching (mock data for demo)
- Verified Malaysian Halal supplier recommendations
- Responsive B2B dashboard interface (form + results)
- Toast notifications and loading states
- Frosted glass UI design

## Architecture

Two-tier architecture (following kyouth/week3 pattern):

* **Frontend (FastAPI + Templates):**
  * Serves HTML pages via Jinja2 templates at `/`, `/about`, `/formulation`
  * `frontend/src/app.py` handles routing and static file serving
  * Tailwind CSS compiled to `/dist/styles.css`
  * Mounts `/dist` as static files endpoint

* **Backend (Flask + AI):**
  * `backend/src/app.py` — formulation API, SQLite lookups, Ollama substitutes
* **ETL (`etl_pipeline/`):**
  * Crawls supplier data, cleans FDA CSV, loads `database.sqlite` under `DATA_DIR`
  * Python 3.14 + uv 0.8 + Ruff 0.15 (same as frontend/backend)