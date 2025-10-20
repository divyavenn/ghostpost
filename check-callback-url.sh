#!/bin/bash
# Helper script to verify callback URL configuration

set -e

echo "🔍 Checking OAuth Callback URL Configuration..."
echo ""

# Check if .env exists
if [ ! -f "backend/.env" ]; then
    echo "❌ backend/.env not found"
    echo "   Run: cd backend && cp .env.example .env"
    exit 1
fi

# Read BACKEND_URL from .env
BACKEND_URL=$(grep "^BACKEND_URL" backend/.env | cut -d'=' -f2 | tr -d "'" | tr -d '"')

if [ -z "$BACKEND_URL" ]; then
    echo "❌ BACKEND_URL not set in backend/.env"
    exit 1
fi

CALLBACK_URL="${BACKEND_URL}/auth/callback"

echo "✅ Configuration found:"
echo "   BACKEND_URL: $BACKEND_URL"
echo "   Callback URL: $CALLBACK_URL"
echo ""

echo "📋 Add this callback URL to Twitter Developer Portal:"
echo ""
echo "   1. Go to: https://developer.x.com/en/portal/dashboard"
echo "   2. Select your app → 'User authentication settings' → 'Edit'"
echo "   3. Add this URL to 'Callback URI / Redirect URL':"
echo ""
echo "      $CALLBACK_URL"
echo ""
echo "   4. Make sure it EXACTLY matches (including http/https and port)"
echo ""
echo "⚠️  IMPORTANT: Use /auth/callback (NOT /api/auth/callback)"
echo "   Frontend uses /api prefix, but Twitter redirects directly to backend"
echo ""

# Check if we're using localhost (development)
if [[ "$BACKEND_URL" == *"localhost"* ]] || [[ "$BACKEND_URL" == *"127.0.0.1"* ]]; then
    echo "ℹ️  You're using localhost (development mode)"
    echo "   For production, update BACKEND_URL to your server IP or domain"
    echo ""
fi

# Check if we're using IP address
if [[ "$BACKEND_URL" =~ ^http://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+$ ]]; then
    IP=$(echo $BACKEND_URL | sed -E 's|http://([0-9.]+):.*|\1|')
    echo "ℹ️  You're using IP address: $IP"
    echo "   This is fine for production, but consider using a domain name"
    echo ""
fi

# Test if backend is running
echo "🧪 Testing backend connectivity..."
if curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL" | grep -q "200\|404"; then
    echo "✅ Backend is reachable at $BACKEND_URL"
else
    echo "⚠️  Backend not reachable at $BACKEND_URL"
    echo "   Make sure backend is running: docker-compose up -d"
fi

echo ""
echo "Done! 🎉"
