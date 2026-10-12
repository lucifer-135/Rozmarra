#!/usr/bin/env bash
# This script starts the Rozmarra API and the doctor dashboard on macOS and Linux.
# Please run scripts/setup.sh once before you run this script:
#   bash scripts/run_demo.sh
# The dashboard then opens at http://localhost:5173. Press Ctrl+C to stop both.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting the Rozmarra API at http://127.0.0.1:8000 ..."
cd "$root/backend"
uv run rozmarra serve &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true; echo "The Rozmarra API and the dashboard have stopped."' EXIT

echo "Starting the dashboard at http://localhost:5173 ..."
cd "$root/frontend"
npm run dev
