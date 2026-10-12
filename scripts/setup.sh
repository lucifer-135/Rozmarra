#!/usr/bin/env bash
# This script sets up Rozmarra on macOS and Linux.
# Please run it from the repository folder with this command:
#   bash scripts/setup.sh
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for tool in uv node npm; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "The tool '$tool' is not installed. Please see the README for the installation steps." >&2
    exit 1
  fi
done

echo "Installing the backend packages with uv ..."
(cd "$root/backend" && uv sync)

echo "Installing the dashboard packages with npm ..."
(cd "$root/frontend" && npm ci)

echo "Rozmarra is set up. Please run scripts/run_demo.sh to start the demo."
