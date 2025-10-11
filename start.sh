#!/bin/bash

# Install backend dependencies
echo "Setting up backend..."
uv sync

# Install frontend dependencies
echo "Setting up frontend..."
cd frontend && npm install && cd ..

# Start backend in background
echo "Starting backend on http://localhost:8000..."
uv run uvicorn backend.main:app --reload &
BACKEND_PID=$!

# Start frontend in background
echo "Starting frontend on http://localhost:5173..."
cd frontend && npm run dev &
FRONTEND_PID=$!

# Wait for both processes
echo "Both servers are running. Press Ctrl+C to stop both."
wait $BACKEND_PID $FRONTEND_PID
