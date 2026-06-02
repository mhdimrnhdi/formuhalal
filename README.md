# Halal Formulation & Sourcing Engine

A digital B2B decision-support system for SME food manufacturers to find Halal-certified ingredient substitutes and source from local Malaysian suppliers.

## Project Overview

Malaysian SMEs often lack food science expertise to find Halal-compliant substitutes when ingredients become unavailable.

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

* **Backend (FastAPI + ETL + AI):**
  * Separate FastAPI service (planned)
  * Handles database queries, AI reasoning, and API endpoints
  * Uses SQLite database, FDA dataset, and LLM integration