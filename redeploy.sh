#!/bin/bash
set -e

echo "🔄 Starting deployment process..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ ERROR: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ ERROR: Docker Compose is not available. Please install Docker Compose plugin."
    exit 1
fi

echo "📦 Committing cache files (except user_info.json)..."
# Commit cache files EXCEPT user_info.json
git add backend/cache/*.jsonl backend/cache/*.json 2>/dev/null || true
git restore --staged backend/cache/user_info.json 2>/dev/null || true
git commit -m "Update cache from server" || true

# Discard changes to user_info.json so dev version wins
git restore backend/cache/user_info.json 2>/dev/null || true

echo "⬇️  Fetching latest code..."
# Fetch latest code
git fetch origin

echo "🔀 Rebasing local commits..."
# Rebase local commits on top of remote
git rebase origin/main

echo "🛑 Stopping existing containers..."
# Stop existing containers
docker compose down

echo "🏗️  Building and starting containers..."
# Build and start containers in detached mode

docker compose up --build --no-cache -d

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Container status:"
docker compose ps
echo ""
echo "🌐 Access points:"
echo "   - Backend API: http://localhost:8000"
echo "   - noVNC (Browser): http://localhost:6080/vnc.html"
echo ""
echo "📝 View logs with: docker compose logs -f"