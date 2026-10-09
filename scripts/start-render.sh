#!/bin/bash
set -e
# Render Python runtime may run from /opt/render/project/ while repo is in src/
# Ensure we're in the repo root (where package.json and PR2-Sem19 live)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
# Start backend on 8000 (internal)
(cd PR2-Sem19 && uvicorn app.main:app --host 0.0.0.0 --port 8000) &
# Start frontend on $PORT (Render's port) - we're already in repo root
exec npm start
