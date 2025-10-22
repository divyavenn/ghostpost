#!/bin/bash
set -e

echo "🚀 Starting FastAPI backend with Browserbase integration..."
echo ""
echo "📝 OAuth: Uses Browserbase cloud browser (live debugger URL)"
echo "📝 Scraping: Uses local headless Playwright (Xvfb virtual display)"
echo ""

# Clean up any existing X lock files
rm -f /tmp/.X99-lock 2>/dev/null || true
mkdir -p /tmp/.X11-unix 2>/dev/null || true
rm -f /tmp/.X11-unix/X99 2>/dev/null || true

# Start Xvfb (virtual display) for local scraping in background
Xvfb :99 -screen 0 1280x720x24 -ac +extension GLX +render -noreset -nolisten tcp &
XVFB_PID=$!
export DISPLAY=:99

# Verify Xvfb started successfully
sleep 2
if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "❌ ERROR: Xvfb failed to start for local scraping"
    exit 1
fi
echo "✅ Xvfb started for local scraping (PID: $XVFB_PID)"

# Set up signal handling for graceful shutdown
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $XVFB_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# Start the main application
exec "$@"
