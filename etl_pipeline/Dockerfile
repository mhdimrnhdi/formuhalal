FROM python:3.14-slim

ARG SUPERCRONIC_VERSION=v0.2.43
ARG TARGETARCH=amd64

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSLo /usr/local/bin/supercronic \
        "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${TARGETARCH}" \
    && chmod +x /usr/local/bin/supercronic \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY src/ ./src/

RUN pip install --no-cache-dir uv==0.8.24 \
    && uv sync --frozen --no-dev

ENV PYTHONPATH=/app/src
ENV DATA_DIR=/data
ENV ETL_CRON="0 2 * * 0"
ENV RUN_ON_START=true

COPY entrypoint.sh /entrypoint.sh
COPY run-etl.sh /app/run-etl.sh
RUN chmod +x /entrypoint.sh /app/run-etl.sh

ENTRYPOINT ["/entrypoint.sh"]
