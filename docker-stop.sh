#!/bin/bash

# FloodMe Docker Stop Script
# Stops and optionally removes Docker containers

echo "🛑 Stopping FloodMe containers..."
docker compose down

echo ""
echo "✅ Containers stopped"
echo ""
echo "💡 To also remove volumes (cache data), run:"
echo "   docker compose down -v"
