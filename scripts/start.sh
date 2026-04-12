#!/bin/sh
set -e

echo "=== Patent Drafting Tool ==="
echo "Waiting for PostgreSQL..."

# Wait for DB to be ready
for i in $(seq 1 30); do
  python -c "
import psycopg
try:
    conn = psycopg.connect('$DATABASE_URL', connect_timeout=3)
    conn.close()
    exit(0)
except:
    exit(1)
" && break
  echo "  DB not ready, retrying ($i/30)..."
  sleep 2
done

echo "Running migrations..."
python -m alembic upgrade head

echo "Starting server on port ${APP_PORT:-8000}..."
exec python -m uvicorn app.main:app \
  --host ${APP_HOST:-0.0.0.0} \
  --port ${APP_PORT:-8000}
