#!/bin/bash
# Test Twitter OAuth credentials

set -e

echo "🔍 Testing Twitter OAuth Credentials..."
echo ""

# Load .env
if [ ! -f "backend/.env" ]; then
    echo "❌ backend/.env not found"
    exit 1
fi

source backend/.env

echo "📋 Current credentials in .env:"
echo "   CLIENT_ID: ${TWITTER_CLIENT_ID:0:20}..."
echo "   CLIENT_SECRET: ${TWITTER_CLIENT_SECRET:0:20}..."
echo "   BACKEND_URL: $BACKEND_URL"
echo ""

# Test if credentials are valid by calling Twitter API
echo "🧪 Testing credentials against Twitter API..."
echo ""

# Get authorization URL (this validates client_id)
AUTH_URL="https://twitter.com/i/oauth2/authorize"
PARAMS="?client_id=$TWITTER_CLIENT_ID&redirect_uri=${BACKEND_URL}/auth/callback&response_type=code&scope=tweet.read%20tweet.write%20users.read&code_challenge=test&code_challenge_method=S256&state=test"

FULL_URL="${AUTH_URL}${PARAMS}"

echo "📡 Testing authorization URL..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$FULL_URL")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Credentials are VALID - Twitter accepted the client_id"
    echo ""
    echo "   Your Twitter app is properly configured for OAuth 2.0"
    echo ""
elif [ "$HTTP_CODE" = "400" ]; then
    echo "❌ Credentials are INVALID - Twitter rejected the request"
    echo ""
    echo "   HTTP 400 Bad Request - Possible issues:"
    echo "   1. Client ID is wrong or from a different app"
    echo "   2. OAuth 2.0 not enabled on this app"
    echo "   3. App doesn't have correct permissions"
    echo "   4. Callback URL not registered in Twitter portal"
    echo ""
    echo "   Check Twitter Developer Portal:"
    echo "   - Go to your app settings"
    echo "   - Verify OAuth 2.0 is enabled"
    echo "   - Verify callback URL: ${BACKEND_URL}/auth/callback"
    echo ""
else
    echo "⚠️  Unexpected HTTP code: $HTTP_CODE"
    echo "   This might indicate a network issue or Twitter API problem"
    echo ""
fi

echo "🔗 Full authorization URL (for manual testing):"
echo "$FULL_URL"
echo ""
echo "💡 Tip: Open this URL in a browser to see the exact error from Twitter"
