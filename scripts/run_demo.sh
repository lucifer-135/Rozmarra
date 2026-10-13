#!/usr/bin/env bash
# This script starts the Rozmarra API and the doctor dashboard on macOS and Linux.
# Please run scripts/setup.sh once before you run this script:
#   bash scripts/run_demo.sh
# The dashboard then opens at http://localhost:5173. Press Ctrl+C to stop both.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -d "$root/frontend/node_modules" ]; then
  echo "The dashboard packages are missing. Please run scripts/setup.sh first." >&2
  exit 1
fi

echo "Starting the Rozmarra API at http://127.0.0.1:8000 ..."
cd "$root/backend"
uv run rozmarra serve &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true; echo "The Rozmarra API and the dashboard have stopped."' EXIT

# The dashboard starts only when the API answers, so that the first screen has its data.
for _ in $(seq 1 90); do
  if ! kill -0 "$api_pid" 2>/dev/null; then
    echo "The Rozmarra API stopped. Please read the messages above." >&2
    exit 1
  fi
  if curl -fs http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "The Rozmarra API is running."
    break
  fi
  sleep 1
done

echo "Starting the dashboard at http://localhost:5173 ..."
cd "$root/frontend"
npm run dev -- --open
