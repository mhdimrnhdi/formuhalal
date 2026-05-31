# Week 4 Independent Project: The Halal Formulation & Sourcing Engine

## 1. Background
Malaysia is a global leader in the Halal economy, and local ecosystem leaders (including Khazanah Nasional, GLCs, and Sunway) are heavily focused on SME digitalization and supply chain resilience. For food and beverage manufacturers, maintaining Halal compliance while managing supply chain volatility is a constant challenge. When raw materials face shortages, price spikes, or compliance issues, businesses must pivot quickly without compromising the chemical integrity or certification of their products.

## 2. The Problem We Are Solving
Small and Medium Enterprises (SMEs) and local food manufacturers often lack in-house food science expertise. When a critical ingredient (e.g., a specific emulsifier or gelatin) becomes unavailable or loses Halal certification, SMEs struggle to:
1. Identify a structurally and chemically sound substitute for their specific recipe.
2. Source that substitute from a verified local supplier.

This leads to halted production lines, compromised product quality, and lost revenue. There is a need for a digital B2B decision-support system that bridges the gap between food science and local supply chain logistics.

## 3. System Structure & Architecture
The system is divided into three distinct layers, ensuring clean separation of concerns and robust error handling.

* **Data Component (ETL Layer):** * **The Science (FDA):** Ingests and cleans the US FDA "Substances Added to Food" dataset to establish a factual, scientific baseline for ingredient technical effects (e.g., Stabilizer, Humectant).
    * **The Supply Chain (Crawler):** A custom Python web crawler (using `BeautifulSoup` or `httpx`) extracts real Malaysian B2B supplier listings from public directories. 
    * Both streams are merged and loaded into a structured `SQLite` database.
* **AI Component (Reasoning Layer):** * An LLM acts as a Food Technologist. It takes the missing ingredient and the FDA baseline to calculate a viable chemical replacement.
    * The output is strictly validated against a **Pydantic** schema to ensure a deterministic JSON payload containing the substitute, ratio, reasoning, and matched local suppliers.
    * Includes a programmatic rule-based fallback if the AI hallucinates or fails JSON validation.
* **Application & Integration Layer:**
    * **Backend:** Built with Python 3.14.* and FastAPI, securely managing environment variables (`.env`) and database queries.
    * **Frontend:** A responsive, enterprise-grade B2B dashboard built with Angular, styled using Tailwind CSS, and utilizing PrimeNG components for complex data tables and formulation cards.
    * **Deployment:** Containerized via Docker (`docker-compose.yml`) for a seamless, demo-ready environment.

## 4. Project Directory Structure
This optimized monorepo structure strictly separates the ETL pipeline, the AI reasoning, and the web application while perfectly accommodating the environment constraints (`uv` 0.8.*, `ruff` 0.15.*, and Python 3.14.*).

```text
halal-formulation-engine/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
│
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
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── prompts.py
│   │   ├── models/
│   │   │   └── schemas.py
│   │   └── services/
│   │       ├── ai_engine.py
│   │       └── db_service.py
│
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── index.html
│   │   ├── styles/
│   │   ├── components/
│   │   │   ├── FormulationCard
│   │   │   ├── SupplierList
│   │   │   └── ErrorState
│   │   └── api/
│   │       └── client.js
│
└── tests/
    ├── test_etl.py
    └── test_ai_fallback.py
```

## 5. Division of Tasks
To maintain velocity and prevent blocking, the workload is divided horizontally across the tech stack:

### Developer A: Data & AI Architect
*Focus: `etl_pipeline/` and AI constraints.*
* Write the FDA dataset cleaning script.
* Develop the web scraper for Malaysian B2B suppliers.
* Design the LLM prompts and configure the Pydantic JSON validation schemas.
* Write the programmatic fallback logic and defensive testing scripts.

### Developer B: Fullstack & Integration Engineer
*Focus: `frontend/`, `backend/`, and DevOps.*
* Configure the project environment, package management (`uv`), and FastAPI routing.
* Develop the user interface from system design to deployment using Angular, Tailwind, and PrimeNG.
* Integrate the backend logic to seamlessly query the SQLite database and serve data to the frontend.
* Manage containerization (Docker) and code quality checks (`ruff`).


to add:
landing page
function page 
product, full ingredient, ingredient swap
sqlite