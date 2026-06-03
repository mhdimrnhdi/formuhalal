# ETL pipeline

Scheduled ETL for FDA substances and Malaysian Halal supplier listings.

## Tooling

Same standards as `frontend` and `backend`:

| Tool | Version | Where |
|------|---------|--------|
| Python | `3.14.*` | `.python-version`, `requires-python` in `pyproject.toml`, Docker `python:3.14-slim` |
| uv | `0.8.*` | `required-version = "==0.8.24"`, Docker `pip install uv==0.8.24` |
| Ruff | `0.15.*` | dev dependency `ruff==0.15.15`, `[tool.ruff]` in `pyproject.toml` |

## Local development

```bash
cd etl_pipeline
uv sync --group dev
uv run python -V          # Python 3.14.x
uv run --group dev ruff --version

# Format
uv run --group dev ruff format src/
uv run --group dev ruff check src/

# Run (DATA_DIR defaults to /data; set for local runs)
export DATA_DIR=../data
uv run python src/run.py
```

From the repo root, `./scripts/format-python.sh` also formats `etl_pipeline/src/`.

## Docker

Built from this directory (`docker-compose` service `etl`). Runtime uses `uv run python src/run.py` via `entrypoint.sh` / supercronic.
