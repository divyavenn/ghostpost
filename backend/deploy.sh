#!/bin/bash

# Production deployment script for Playwright backend

set -e

echo "🚀 Starting deployment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Build the Docker image
echo "📦 Building Docker image..."
docker build -t floodme-backend:latest .

# Stop existing container if running
echo "🛑 Stopping existing container..."
docker-compose down || true

# Start the new container
echo "▶️ Starting new container..."
docker-compose up -d

# Wait for health check
echo "⏳ Waiting for service to be healthy..."
timeout=60
counter=0
while [ $counter -lt $timeout ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Service is healthy!"
        break
    fi
    sleep 2
    counter=$((counter + 2))
done

if [ $counter -ge $timeout ]; then
    echo "❌ Service failed to become healthy within $timeout seconds"
    docker-compose logs
    exit 1
fi

echo "🎉 Deployment completed successfully!"
echo "📊 Service is running at http://localhost:8000"
