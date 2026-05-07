#!/usr/bin/env bash
# Run the IT Ops API, the FastAPI backend, and the React frontend in one terminal.
# Cleans up child processes on Ctrl+C.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "[dev.sh] .env not found, copying from .env.example"
  cp .env.example .env
  echo "[dev.sh] Edit .env and set ANTHROPIC_API_KEY before continuing." >&2
fi

if [ ! -d .venv ]; then
  echo "[dev.sh] No virtualenv found. Run 'make setup' first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# This project pins Python 3.11. Warn (but don't fail) if a different version
# is in the venv so the user knows things may not be reproducible.
PY_VER="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$PY_VER" != "3.11" ]; then
  echo "[dev.sh] WARNING: venv is on Python $PY_VER but this project pins 3.11."
  echo "[dev.sh]          Recreate with: rm -rf .venv && make setup"
fi

PIDS=()
cleanup() {
  echo
  echo "[dev.sh] Shutting down…"
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "[dev.sh] Starting IT Ops API on :8001"
uvicorn services.it_ops_api.main:app --port 8001 --reload &
PIDS+=($!)

# Give the ops API a moment so the backend's startup probe sees it ready.
sleep 1.5

echo "[dev.sh] Starting backend on :8000"
uvicorn backend.main:app --port 8000 --reload &
PIDS+=($!)

echo "[dev.sh] Starting frontend on :5173"
( cd frontend && npm run dev -- --host ) &
PIDS+=($!)

echo "[dev.sh] All services starting. Open http://localhost:5173"
echo "[dev.sh] Ctrl+C to stop everything."
wait
