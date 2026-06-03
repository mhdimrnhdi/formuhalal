#!/usr/bin/env bash
# Format all Python (backend, frontend, etl_pipeline) with ruff 0.15.* dev deps.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"
uv run --group dev ruff format \
  backend/src \
  frontend/src \
  frontend/dev.py \
  etl_pipeline/src
