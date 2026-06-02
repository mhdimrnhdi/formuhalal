#!/bin/sh
set -eu

cd /app
exec uv run python src/run.py
