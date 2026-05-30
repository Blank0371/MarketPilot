#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PYTHON="$ROOT_DIR/env/bin/python"
if [[ ! -x "$BACKEND_PYTHON" ]]; then
  BACKEND_PYTHON="$ROOT_DIR/.venv/bin/python"
fi

DATA_ENGINEER_PORT="${DATA_ENGINEER_PORT:-8002}"
TRANSLATION_PORT="${TRANSLATION_PORT:-8003}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

PIDS=()

cleanup() {
  if ((${#PIDS[@]} > 0)); then
    echo
    echo "Stopping MarketPilot services..."
    kill "${PIDS[@]}" >/dev/null 2>&1 || true
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

trap cleanup EXIT INT TERM

cd "$ROOT_DIR"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "Warning: .env not found. Copy .env-example to .env if you need local secrets."
fi

if [[ ! -x "$BACKEND_PYTHON" ]]; then
  echo "Python virtualenv not found at env/ (or .venv/ fallback)." >&2
  echo "Run:" >&2
  echo "  python3 -m venv env" >&2
  echo "  source env/bin/activate" >&2
  echo "  pip install -r backend/requirements.txt" >&2
  exit 1
fi

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Frontend dependencies are not installed." >&2
  echo "Run:" >&2
  echo "  cd frontend" >&2
  echo "  npm install" >&2
  exit 1
fi

require_command npm

echo "Starting MarketPilot..."
echo "Data-Engineer: http://localhost:$DATA_ENGINEER_PORT"
echo "Translation:    http://localhost:$TRANSLATION_PORT"
echo "Frontend:       http://localhost:$FRONTEND_PORT"
echo

"$BACKEND_PYTHON" -m uvicorn backend.data_engineer:app --reload --port "$DATA_ENGINEER_PORT" &
PIDS+=("$!")

"$BACKEND_PYTHON" -m uvicorn backend.translation_agent:app --reload --port "$TRANSLATION_PORT" &
PIDS+=("$!")

(
  cd "$ROOT_DIR/frontend"
  npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
) &
PIDS+=("$!")

wait -n "${PIDS[@]}"
