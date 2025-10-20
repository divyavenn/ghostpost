#!/bin/bash
echo "🔧 Setting up backend..."
uv sync

echo ""
echo "⚠️  Note: Auto-reload only works for Python files (.py)"
echo "   If you change .env, restart this script manually (Ctrl+C then ./start.sh)"
echo ""
echo "🚀 Starting backend on http://localhost:8000..."
echo "   Press Ctrl+C to stop"
echo ""

uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 