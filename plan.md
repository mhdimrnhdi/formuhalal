# Week 4 Independent Project: The Halal Formulation & Sourcing Engine

## 1. Background
Malaysia is a global leader in the Halal economy, and local ecosystem leaders (including Khazanah Nasional, GLCs, and Sunway) are heavily focused on SME digitalization and supply chain resilience. For food and beverage manufacturers, maintaining Halal compliance while managing supply chain volatility is a constant challenge. When raw materials face shortages, price spikes, or compliance issues, businesses must pivot quickly without compromising the chemical integrity or certification of their products.

## 2. The Problem We Are Solving
Small and Medium Enterprises (SMEs) and local food manufacturers often lack in-house food science expertise. When a critical ingredient (e.g., a specific emulsifier or gelatin) becomes unavailable or loses Halal certification, SMEs struggle to:
1. Identify a structurally and chemically sound substitute for their specific recipe.
2. Source that substitute from a verified local supplier.

This leads to halted production lines, compromised product quality, and lost revenue. There is a need for a digital B2B decision-support system that bridges the gap between food science and local supply chain logistics.

## 3. System Structure & Architecture
The system follows a three-tier architecture:

* **Data Component (ETL Layer):**
    * **The Science (FDA):** Ingests and cleans the US FDA "Substances Added to Food" dataset to establish a factual, scientific baseline for ingredient technical effects (e.g., Stabilizer, Humectant).
    * **The Supply Chain (Crawler):** A custom Python web crawler (using `BeautifulSoup` or `httpx`) extracts real Malaysian B2B supplier listings from public directories.
    * Both streams are merged and loaded into a structured `SQLite` database.

* **AI Component (Reasoning Layer):**
    * An LLM acts as a Food Technologist. It takes the missing ingredient and the FDA baseline to calculate a viable chemical replacement.
    * The output is strictly validated against a **Pydantic** schema to ensure a deterministic JSON payload containing the substitute, ratio, reasoning, and matched local suppliers.
    * Includes a programmatic rule-based fallback if the AI hallucinates or fails JSON validation.

* **Frontend (FastAPI + Templates):**
    * Serves HTML pages via Jinja2 templates at `/`, `/about`, `/formulation`
    * `frontend/src/app.py` handles routing and static file serving
    * Tailwind CSS compiled to `/dist/styles.css`
    * Mounts `/dist` as static files endpoint

* **Backend (FastAPI + ETL + AI):**
    * Separate FastAPI service at `backend/src/app.py`
    * Handles database queries, AI reasoning, and API endpoints
    * Uses SQLite database, FDA dataset, and LLM integration
    * Communicates with frontend via HTTP API calls

* **Deployment:**
    * Containerized via `docker-compose.yml` with two services
    * Frontend: port 8000, Backend: port 8001
    * Shared network for inter-container communication

## 4. Project Directory Structure
```text
formuhalal/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── ruff.toml
│
├── data/
│   ├── raw/
│   └── database.sqlite
│
├── etl_pipeline/
│   ├── __init__.py
│   ├── crawler.py
│   ├── fda_processor.py
│   └── load_db.py
│
├── backend/
│   ├── Dockerfile
│   ├── secrets/
│   │   └── google_api_key.txt
│   └── src/
│       ├── app.py           # Main FastAPI backend
│       ├── api/
│       ├── core/
│       ├── models/
│       └── services/
│
├── frontend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .python-version
│   ├── build.mjs
│   ├── package.json
│   ├── styles/
│   │   └── input.css
│   ├── dev.py
│   ├── dist/
│   │   ├── styles.css
│   │   └── pattern_bg.jpg
│   └── src/
│       ├── app.py           # FastAPI serving templates
│       └── templates/
│           ├── index.html
│           ├── about.html
│           └── formulation.html
│
└── tests/
    ├── test_etl.py
    └── test_ai_fallback.py
```

## 5. Division of Tasks

### Developer A: Data & AI Architect
*Focus: `etl_pipeline/`*
* Write the FDA dataset cleaning script (`etl_pipeline/fda_processor.py`)
* Develop the web scraper for Malaysian B2B suppliers (`etl_pipeline/crawler.py`)
* Design the LLM prompts and Pydantic JSON validation schemas
* Write the programmatic fallback logic and defensive testing scripts

### Developer B: Fullstack & Integration Engineer (Frontend Complete)
*Focus: `frontend/`, `backend/`, Docker, DevOps*
* ✅ Configure the project environment and package management (`uv`, `npm`)
* ✅ Develop the user interface with Alpine.js + Tailwind CSS
* ✅ Implement FastAPI template serving and static file handling
* ✅ Create Dockerfile for frontend
* ⏳ Implement backend FastAPI endpoints and business logic
* ⏳ Manage `docker-compose.yml` for local development and deployment
* ⏳ Run `ruff` for code quality checks