#!/bin/bash

# Run the FastAPI backend server
# Usage: ./run-backend.sh

cd "$(dirname "$0")/backend"
echo "Starting backend server with scheduler (24-hour interval)..."
echo "Working directory: $(pwd)"
echo ""
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
