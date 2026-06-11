#!/bin/sh
set -eu

APP_UID="${APP_UID:-1000}"
APP_GID="${APP_GID:-1000}"

mkdir -p /data/formulation_results
chown "${APP_UID}:${APP_GID}" /data/formulation_results

CRON_SCHEDULE="${ETL_CRON:-0 2 * * 0}"
CRON_FILE="/tmp/etl-crontab"

{
  printf 'SHELL=/bin/sh\n'
  printf 'PATH=/usr/local/bin:/usr/bin:/bin\n'
  printf '%s /bin/sh /app/run-etl.sh\n' "$CRON_SCHEDULE"
} > "$CRON_FILE"

if [ "${RUN_ON_START:-true}" = "true" ]; then
  echo "Running initial ETL pipeline..."
  uv run python src/run.py
fi

echo "Starting ETL scheduler (${CRON_SCHEDULE})"
exec /usr/local/bin/supercronic -passthrough-logs "$CRON_FILE"
