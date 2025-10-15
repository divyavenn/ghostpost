#!/bin/bash
#
# Setup cron job for FloodMe worker
# Automatically detects project path and sets up scheduled scraping

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

echo -e "${GREEN}FloodMe Worker Cron Setup${NC}"
echo "================================"

# Verify dependencies
if ! command -v uv &> /dev/null; then
    echo -e "${RED}✗${NC} uv not found. Please install: https://docs.astral.sh/uv/"
    exit 1
fi

WORKER_PATH="$PROJECT_ROOT/backend/worker.py"
if [ ! -f "$WORKER_PATH" ]; then
    echo -e "${RED}✗${NC} worker.py not found at: $WORKER_PATH"
    exit 1
fi

# Create log directory
LOG_DIR="$PROJECT_ROOT/backend/cache/worker_logs"
mkdir -p "$LOG_DIR"

# Define cron job
CRON_TIME="*/10 * * * *"  # Every 10 minutes
CRON_LOG="$LOG_DIR/cron_output.log"
UV_CMD="$(which uv)"
CRON_CMD="cd $PROJECT_ROOT && $UV_CMD run python backend/worker.py >> $CRON_LOG 2>&1"
CRON_ENTRY="$CRON_TIME $CRON_CMD"

# Stop any running worker processes
echo "Stopping existing worker processes..."
pkill -f "backend/worker.py" 2>/dev/null || true

# Stop cron service to ensure clean state
echo "Stopping cron service..."
sudo systemctl stop cron 2>/dev/null || true

# Remove existing cron jobs
echo "Removing existing cron jobs..."
crontab -l 2>/dev/null | grep -v "backend/worker.py" | crontab - 2>/dev/null || true

# Start cron service
echo "Starting cron service..."
sudo systemctl start cron || { echo -e "${RED}✗${NC} Failed to start cron service"; exit 1; }

# Enable cron service to start on boot
sudo systemctl enable cron >/dev/null 2>&1

# Install new cron job
echo "Installing new cron job..."
TEMP_CRONTAB=$(mktemp)
crontab -l 2>/dev/null > "$TEMP_CRONTAB"
echo "$CRON_ENTRY" >> "$TEMP_CRONTAB"
crontab "$TEMP_CRONTAB"
rm "$TEMP_CRONTAB"

echo -e "${GREEN}✓${NC} Setup complete!"
echo ""
echo "Log file: $CRON_LOG"
echo ""
echo "Commands:"
echo "  View logs: tail -f $CRON_LOG"
echo "  Test run: cd $PROJECT_ROOT && uv run python backend/worker.py"
echo "  Check cron: crontab -l"