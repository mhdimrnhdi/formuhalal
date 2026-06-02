FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY src/ ./src/
COPY dist/ ./dist/

RUN pip install uv==0.8.24
RUN uv sync --frozen

EXPOSE 8000

ENTRYPOINT ["uv", "run", "uvicorn"]
CMD ["--app-dir", "src", "--host", "0.0.0.0", "--port", "8000", "app:app"]