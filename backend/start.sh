
echo "Setting up backend..."
uv sync
echo "Starting backend on http://localhost:8000..."
uv run uvicorn backend.main:app --reload 