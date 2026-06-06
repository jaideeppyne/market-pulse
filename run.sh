#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ] || [ requirements.txt -nt .venv/pyvenv.cfg 2>/dev/null ]; then
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  .venv/bin/pip install -r requirements.txt
fi

export PYTHONPATH="$(pwd)"
echo "Starting Market Pulse at http://127.0.0.1:8765"
exec .venv/bin/python -m app.main