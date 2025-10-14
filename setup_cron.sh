#!/bin/bash
#
# Setup cron job for FloodMe worker
# Automatically detects project path and sets up daily scraping

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect project root (script is in scripts/, so go up one level)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo -e "${GREEN}FloodMe Worker Cron Setup${NC}"
echo "================================"
echo "Project root: $PROJECT_ROOT"
echo ""

# Detect Python/uv path
if command -v uv &> /dev/null; then
    UV_CMD="uv"
    echo -e "${GREEN}✓${NC} Found uv package manager"
else
    echo -e "${RED}✗${NC} uv not found. Please install: https://docs.astral.sh/uv/"
    exit 1
fi

# Verify worker.py exists
WORKER_PATH="$PROJECT_ROOT/backend/worker.py"
if [ ! -f "$WORKER_PATH" ]; then
    echo -e "${RED}✗${NC} worker.py not found at: $WORKER_PATH"
    exit 1
fi
echo -e "${GREEN}✓${NC} Found worker.py"

# Create log directory
LOG_DIR="$PROJECT_ROOT/backend/cache/worker_logs"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✓${NC} Created log directory: $LOG_DIR"

# Define cron job
# Run daily at 2 AM, redirect stdout and stderr to log file
CRON_TIME="0 2 * * *"  # 2 AM daily
CRON_LOG="$LOG_DIR/cron_output.log"
CRON_CMD="cd $PROJECT_ROOT && $UV_CMD run python backend/worker.py >> $CRON_LOG 2>&1"
CRON_ENTRY="$CRON_TIME $CRON_CMD"

echo ""
echo "Cron job configuration:"
echo "  Schedule: Daily at 2:00 AM"
echo "  Command: $CRON_CMD"
echo "  Log file: $CRON_LOG"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "backend/worker.py"; then
    echo -e "${YELLOW}⚠${NC}  Cron job already exists. Updating..."
    # Remove existing FloodMe worker cron jobs
    crontab -l 2>/dev/null | grep -v "backend/worker.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo -e "${GREEN}✓${NC} Cron job installed successfully!"
echo ""
echo "To verify installation, run:"
echo "  crontab -l"
echo ""
echo "To view cron output:"
echo "  tail -f $CRON_LOG"
echo ""
echo "To test worker manually:"
echo "  cd $PROJECT_ROOT && uv run python backend/worker.py"
echo ""
echo "To test with specific user:"
echo "  cd $PROJECT_ROOT && uv run python backend/worker.py --user proudlurker"
echo ""
echo -e "${GREEN}Setup complete!${NC}"