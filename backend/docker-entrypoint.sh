#!/bin/bash
set -e

echo "🚀 Starting virtual display and VNC services..."

# Clean up any existing X lock files (only if we have permission)
rm -f /tmp/.X99-lock 2>/dev/null || true
mkdir -p /tmp/.X11-unix 2>/dev/null || true
rm -f /tmp/.X11-unix/X99 2>/dev/null || true

# Start Xvfb (virtual display) in background
# Using -nolisten tcp for security, -ac to disable access control for headless operation
Xvfb :99 -screen 0 1280x720x24 -ac +extension GLX +render -noreset -nolisten tcp &
XVFB_PID=$!
export DISPLAY=:99

# Verify Xvfb started successfully
sleep 2
if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "❌ ERROR: Xvfb failed to start"
    echo "   Check if running as root or with proper permissions"
    exit 1
fi
echo "✅ Xvfb started (PID: $XVFB_PID)"

# Start x11vnc (VNC server) in background
# -nopw: no password (for internal use only)
# -forever: keep accepting connections after client disconnects
# -shared: allow multiple VNC connections
# -rfbport: VNC server port
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw -quiet &
X11VNC_PID=$!

# Verify x11vnc started
sleep 2
if ! kill -0 $X11VNC_PID 2>/dev/null; then
    echo "❌ ERROR: x11vnc failed to start"
    echo "   Xvfb may not be ready or display :99 is not accessible"
    exit 1
fi
echo "✅ x11vnc started (PID: $X11VNC_PID)"

# Start noVNC (web-based VNC client) in background
# noVNC provides a web-based VNC client accessible via browser
cd /opt/novnc && ./utils/novnc_proxy --vnc localhost:5900 --listen 6080 &
NOVNC_PID=$!

# Verify noVNC started
sleep 2
if ! kill -0 $NOVNC_PID 2>/dev/null; then
    echo "❌ ERROR: noVNC failed to start"
    echo "   VNC server may not be ready on port 5900"
    exit 1
fi
echo "✅ noVNC started (PID: $NOVNC_PID)"
echo ""
echo "🌐 Access OAuth browser at: http://localhost:6080/vnc.html"
echo "   (Replace localhost with your server IP in production)"
echo ""

# Set up signal handling to gracefully shutdown all services
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $NOVNC_PID $X11VNC_PID $XVFB_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# Start the main application
echo "🚀 Starting FastAPI backend..."
exec "$@"
