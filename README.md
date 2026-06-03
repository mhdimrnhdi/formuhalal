# Halal Formulation & Sourcing Engine (FormuHalal)

A digital B2B decision-support system that helps Malaysian SME food manufacturers
find Halal-compatible ingredient substitutes and source them from verified local
suppliers listed in the JAKIM / My e-Halal directory.

## Project Overview

### Problem Statement

Malaysian SME food manufacturers frequently face ingredient disruptions: a
supplier discontinues a product, an additive loses its Halal status, or a raw
material becomes unavailable or too expensive. Unlike large manufacturers, most
SMEs do not have in-house food scientists who can identify a functionally
equivalent substitute, nor the time to manually cross-check whether a candidate
ingredient is available from a Halal-certified Malaysian supplier. The result is
costly reformulation delays and compliance risk.

### Target Users

- SME food manufacturers in Malaysia who need to reformulate products quickly.
- Product development and quality teams that must keep formulations Halal-compliant.
- Procurement staff looking for local, Halal-certified suppliers for a given ingredient.

### System Goal

Given a product, its full ingredient list, and the ingredient that must be
replaced, the system aims to:

1. Find functionally equivalent substitute ingredients (matched by technical effect).
2. Use an LLM to recommend the best substitutes with a short justification.
3. Match each recommended substitute to a real Halal-certified Malaysian supplier.
4. Return a single, structured recommendation the manufacturer can act on.

## System Architecture

The project is a containerized, multi-service application following a clear
input → processing → output flow.

### Data Flow

```
                         ETL (scheduled / on start)
   FDA Food Substances CSV ─┐
                            ├─► clean + normalize ─► SQLite (substances, suppliers)
   My e-Halal directory ────┘        crawl

                         Request flow (per formulation)
   User form ─► Frontend (FastAPI) ─► Backend (Flask) ─► SQLite lookup
                                            │
                                            ├─► LLM #1 (Ollama): pick best substitutes
                                            │
                                            ├─► LLM #2 (Gemini/OpenAI): match suppliers
                                            │
                                            └─► merge + enrich ─► JSON result ─► UI
```

- Input: A formulation request (`product_name`, `ingredients`, `substitute_for`)
  plus a `Bearer` key sent from the browser to the backend.
- Processing:
  1. The backend looks up the target ingredient in the `substances` table and
     finds candidates that share the same `used_for` technical effect.
  2. An Ollama model selects the three best substitutes with reasons.
  3. The backend pulls candidate suppliers from the `suppliers` table by keyword,
     and a Gemini or OpenAI model matches each substitute to one supplier.
  4. Supplier records are enriched from the database (location, certifications,
     source URL) and merged into final recommendations.
- Output: A structured JSON payload (also persisted under
  `data/formulation_results/`) rendered as cards in the web UI, plus
  intermediate `.txt`/`.json` artifacts for traceability.

### Module Breakdown

| Module | Path | Responsibility |
| --- | --- | --- |
| Frontend | `frontend/` | FastAPI app serving Jinja2 pages (`/`, `/about`, `/formulation`) and compiled Tailwind CSS; collects the form and calls the backend. |
| Backend | `backend/src/app.py` | Flask API exposing `/health` and `/api/formulation`; SQLite lookups, result preparation, persistence, and orchestration of the two LLM stages. |
| LLM layer | `backend/src/llm.py` | Prompt building, Ollama call for substitutes, Gemini/OpenAI call for supplier matching, and parsing of LLM text output. |
| ETL pipeline | `etl_pipeline/src/` | `run.py` orchestrates the pipeline; `fda_processor.py` cleans the FDA CSV; `crawler.py` scrapes the My e-Halal directory; `load_db.py` loads both into SQLite. |
| Data store | `data/` | SQLite database (`database.sqlite`), raw inputs (`raw/`), cleaned CSV, and saved formulation results. |
| Orchestration | `docker-compose.yml` | Wires together `ollama`, `etl`, `backend`, and `frontend` services with shared volumes. |

## Setup & Installation

### Dependencies & Environment

- Python `3.14.*` for all three services (see each `.python-version`).
- [uv](https://docs.astral.sh/uv/) `0.8.24` as the package manager (`required-version` in each `pyproject.toml`).
- Ruff `0.15.15` for formatting.
- Node.js for building the frontend CSS (`frontend/build.mjs`).
- Docker & Docker Compose (recommended path).
- An LLM backend: a running Ollama instance (substitutes) and a Gemini or OpenAI API key (supplier matching).

Per-service runtime dependencies:

- Frontend: `fastapi`, `uvicorn`, `jinja2`, `python-dotenv`.
- Backend: `flask`, `flask-cors`, `python-dotenv`.
- ETL: `httpx`, `beautifulsoup4`.

Copy the example environment file and fill in your own values before running:

```bash
cp .env.example .env
```

Key variables (see `.env.example` for the full list):

- `DB_URL` — path to the SQLite database.
- `OLLAMA_URL`, `OLLAMA_PRESET`, `OLLAMA_MODEL` — substitute-generation model.
- `GEMINI_API_KEY` / `OPENAI_API_KEY` — supplier-matching model (Gemini is preferred when a key is present).
- `ETL_CRON`, `ETL_RUN_ON_START` — ETL schedule and whether to run once at container start.

### Option A — Run everything with Docker Compose (recommended)

```bash
docker compose up --build
```

This starts:

- `ollama` — local model server for substitutes.
- `etl` — builds the SQLite database (runs once on start when `ETL_RUN_ON_START=true`, then on the `ETL_CRON` schedule).
- `backend` — Flask API on port `8001`.
- `frontend` — web UI on port `8000`.

Then open http://localhost:8000.

### Option B — Run each service locally

```bash
# Frontend (FastAPI)
cd frontend
node build.mjs                     # build Tailwind CSS into dist/
uv sync --group dev
uv run dev.py                      # dev server with auto-reload
# or: uv run uvicorn --app-dir src --host 0.0.0.0 --port 8000 app:app
```

```bash
# Backend (Flask API)
cd backend
uv sync --group dev
uv run flask --app src.app run --host 0.0.0.0 --port 8001
```

```bash
# ETL pipeline (builds data/database.sqlite)
cd etl_pipeline
uv sync --group dev
export DATA_DIR=../data
uv run python src/run.py           # add --skip-crawl / --skip-download to reuse cached inputs
```

### Python tooling

From the repo root, format all services at once:

```bash
./scripts/format-python.sh
```

Per service (example for ETL):

```bash
cd etl_pipeline && uv sync --group dev && uv run --group dev ruff format src/
```

## Features

- Technical-effect substitute matching — Looks up the ingredient to replace in
  the FDA-derived `substances` table and groups alternative substances that share
  the same `used_for` technical effect (e.g. stabilizer/thickener, texturizer).

- LLM-assisted substitute selection — An Ollama model (configurable preset:
  `fast` / `balanced` / `quality`) picks the three best substitutes from the
  database candidates and gives a one-line reason for each, constrained to only
  choose from the supplied list.

- Halal supplier matching — Candidate suppliers are pulled from the crawled My
  e-Halal directory by keyword, and a Gemini or OpenAI model assigns one
  real supplier to each substitute. Gemini is used when a key is present,
  otherwise OpenAI is the fallback.

- Database-enriched recommendations — Each recommended supplier is matched back
  to its database record so the response includes verified location,
  certifications, and source URL, with a `matched_in_database` flag for honesty.

- Result persistence & traceability — Every request is hashed (from its Bearer
  key) and saved under `data/formulation_results/` as raw JSON, prepared JSON,
  and intermediate substitute/supplier text files.

- Scheduled ETL refresh — The pipeline cleans the FDA Food Substances CSV and
  crawls the JAKIM directory on a cron schedule (and optionally once at startup)
  to keep the database current.

- Web dashboard — A responsive FastAPI + Jinja2 frontend with a frosted-glass UI,
  landing/about/formulation pages, form submission, loading states, and result cards.

- Health endpoint — `GET /health` for liveness checks of the backend.

## Technical Decisions

### Architecture Choices

- Multi-service split (frontend / backend / ETL): Each concern is isolated with
  its own dependencies, `pyproject.toml`, and Docker image, making services
  independently deployable and testable.
- SQLite as the data store: A single-file database is sufficient for read-heavy
  lookups and ships easily inside a shared Docker volume, avoiding the operational
  overhead of a dedicated database server.
- Two-stage LLM pipeline: Substitute selection (local Ollama) is separated from
  supplier matching (hosted Gemini/OpenAI). This keeps the bulkier reasoning step
  local/cheap while using a hosted model only where higher quality matching helps.
- Constrained prompting: Both LLM prompts force the model to pick only from
  database-provided candidates, reducing hallucinated ingredients and suppliers.
- Stateless backend with file-based results: Results are derived per request and
  written to disk keyed by a hash of the Bearer key, avoiding session state while
  still giving reproducible, inspectable artifacts.
- ETL via cron in-container (supercronic): The ETL image runs on a schedule
  inside its own container rather than relying on host cron, keeping the whole
  system self-contained under Docker Compose.

### Trade-offs Made

- SQLite over a client/server database: Simpler to ship, but limits concurrent
  writes and horizontal scaling.
- Keyword-based supplier candidate filtering: Fast and dependency-free, but
  coarse — it can over- or under-include suppliers compared to a semantic search.
- LLM text parsing via regex: Lightweight (no extra deps), but brittle if the
  model deviates from the requested numbered-list format.
- Bearer-key hashing for result identity: Gives stable, private file names
  without storing the key, but is not a real authentication/authorization system.
- Local Ollama dependency: Keeps substitute generation free and private, but
  requires a running model server and adds setup/latency cost.

## Limitations

### Known Issues

- The Bearer key is used only to namespace saved results — there is no real
  authentication, authorization, or rate limiting on the backend.
- LLM output parsing depends on the model strictly following the numbered-list
  format; malformed responses silently drop entries.
- Supplier matching quality is bounded by keyword filtering and directory data
  freshness; a "matched" supplier may not actually stock the substance.
- The supplier crawler is tightly coupled to the My e-Halal portal's HTML/SSL
  quirks and can break if the site changes.
- Substitute data is limited to what the FDA "Used for (Technical Effect)" field
  captures and is not Halal-status-aware at the substance level.

### Future Improvements

- Replace keyword supplier filtering with semantic / embedding-based search.
- Add real authentication, authorization, and request rate limiting.
- Validate and schema-check LLM responses instead of regex parsing.
- Persist results to a proper database and add a history/lookup view.
- Add automated tests and CI for the backend logic and ETL transforms.
- Track per-substance Halal certification status, not just supplier certification.
- Add observability (structured logging, metrics) around the LLM and ETL stages.