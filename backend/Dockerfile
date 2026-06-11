FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY src/ ./src/

RUN pip install uv==0.8.24
RUN uv sync --frozen

ENV HOME=/tmp
ENV UV_CACHE_DIR=/tmp/.cache/uv

EXPOSE 8001

ENTRYPOINT ["uv", "run", "flask"]
CMD ["--app", "src.app", "run", "--host", "0.0.0.0", "--port", "8001"]
