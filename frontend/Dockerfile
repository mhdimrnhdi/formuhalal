FROM python:3.14.4-latest

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY src/ ./src/
COPY dist/ ./dist/

RUN pip install uv==0.8.24
RUN uv sync --frozen

ENTRYPOINT ["uv", "run", "uvicorn"]
CMD ["--app-dir", "src", "--host", "0.0.0.0", "app:app"]