#!/usr/bin/env bash
# Requires installed backend/frontend dependencies, migrated test PostgreSQL and Playwright Chromium.
set -euo pipefail
cd "$(dirname "$0")/.."
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 >/tmp/smartestimate-e2e-api.log 2>&1 &
api_pid=$!
npm --prefix frontend run dev -- --host 127.0.0.1 >/tmp/smartestimate-e2e-web.log 2>&1 &
web_pid=$!
cleanup() { kill "$api_pid" "$web_pid" 2>/dev/null || true; }
trap cleanup EXIT
for attempt in {1..30}; do
  if curl --noproxy '*' -fsS http://127.0.0.1:8000/api/ready >/dev/null && curl --noproxy '*' -fsS http://127.0.0.1:5173 >/dev/null; then break; fi
  sleep 1
done
curl --noproxy '*' -fsS http://127.0.0.1:8000/api/ready >/dev/null
kill -0 "$api_pid" "$web_pid"
cd frontend
npm run test:e2e
