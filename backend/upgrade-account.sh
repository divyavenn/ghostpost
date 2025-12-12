#!/bin/bash

# Usage: ./upgrade-account.sh <username> <account_type> [model]
#
# Examples:
#   ./upgrade-account.sh NeelSardana premium paul-graham-1
#   ./upgrade-account.sh ABhargava2000 premium nakul-1
#   ./upgrade-account.sh someuser paid
#   ./upgrade-account.sh someuser trial

set -e

# Default to production URL (nginx adds /api prefix)
# For local development, use: API_BASE_URL="http://localhost:8000" ./upgrade-account.sh ...
API_BASE_URL="${API_BASE_URL:-https://x.ghostposter.app/api}"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <username> <account_type> [model]"
    echo ""
    echo "Account types: trial, paid, premium"
    echo "Note: 'premium' requires a model name"
    echo ""
    echo "Examples:"
    echo "  $0 NeelSardana premium paul-graham-1"
    echo "  $0 someuser paid"
    echo ""
    echo "Environment variables:"
    echo "  API_BASE_URL - Override the API URL"
    echo "    Production: https://x.ghostposter.app/api (default)"
    echo "    Local:      http://localhost:8000"
    exit 1
fi

USERNAME="$1"
ACCOUNT_TYPE="$2"
MODEL="$3"

# Validate account type
if [[ ! "$ACCOUNT_TYPE" =~ ^(trial|paid|premium)$ ]]; then
    echo "Error: Invalid account type '$ACCOUNT_TYPE'. Must be: trial, paid, or premium"
    exit 1
fi

# Premium requires a model
if [ "$ACCOUNT_TYPE" = "premium" ] && [ -z "$MODEL" ]; then
    echo "Error: Premium accounts require a model name"
    echo "Usage: $0 $USERNAME premium <model-name>"
    exit 1
fi

# Build the JSON payload
if [ -n "$MODEL" ]; then
    PAYLOAD="{\"account_type\": \"$ACCOUNT_TYPE\", \"model\": \"$MODEL\"}"
else
    PAYLOAD="{\"account_type\": \"$ACCOUNT_TYPE\"}"
fi

echo "Upgrading $USERNAME to $ACCOUNT_TYPE..."
if [ -n "$MODEL" ]; then
    echo "Model: $MODEL"
fi
echo "API: $API_BASE_URL"
echo ""

# Make the API call
RESPONSE=$(curl -s -X PUT "$API_BASE_URL/account/$USERNAME/account-type" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

# Check for errors
if echo "$RESPONSE" | grep -q '"error"'; then
    echo "Error: $RESPONSE"
    exit 1
elif echo "$RESPONSE" | grep -q '"detail"'; then
    echo "Error: $RESPONSE"
    exit 1
else
    echo "Success!"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
fi
