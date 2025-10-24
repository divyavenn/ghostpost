#!/bin/bash

# FloodMe Docker Runner
# This script builds and runs the FloodMe application in Docker containers

set -e  # Exit on error

echo "🐳 FloodMe Docker Runner"
echo "======================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "Please start Docker Desktop and wait for it to fully launch."
    echo "Then run this script again."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check for .env file
if [ ! -f "backend/.env" ]; then
    echo "⚠️  Warning: backend/.env file not found!"
    echo "Please create backend/.env with your environment variables."
    echo "You can copy from backend/.env.example"
    exit 1
fi

echo "✅ Environment file found"
echo ""

echo "Shut down any running instances"
docker compose down 

# Build and start containers
echo "🏗️  Clear cache and rebuild Docker images"

docker compose build --no-cache

echo ""
echo "🚀 Starting containers..."
docker compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

echo ""
echo "📊 Container status:"
docker compose ps

echo ""
echo "✅ Docker containers are running!"
echo ""
echo "📍 Services available at:"
echo "   Frontend:  http://localhost"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "📝 Useful commands:"
echo "   View logs:        docker compose logs -f"
echo "   View backend logs: docker compose logs -f backend"
echo "   Stop containers:  docker compose down"
echo "   Restart:          docker compose restart"
echo ""
echo "🎉 FloodMe is ready!"
