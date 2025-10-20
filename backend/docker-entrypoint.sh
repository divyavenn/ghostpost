#!/bin/bash
set -e

echo "🚀 Starting virtual display and VNC services..."

# Clean up any existing X lock files
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 2>/dev/null || true

# Start Xvfb (virtual display) in background
Xvfb :99 -screen 0 1280x720x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
export DISPLAY=:99

# Verify Xvfb started successfully
sleep 2
if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "❌ ERROR: Xvfb failed to start"
    exit 1
fi
echo "✅ Xvfb started (PID: $XVFB_PID)"

# Start x11vnc (VNC server) in background
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &
X11VNC_PID=$!

# Verify x11vnc started
sleep 2
if ! kill -0 $X11VNC_PID 2>/dev/null; then
    echo "❌ ERROR: x11vnc failed to start"
    exit 1
fi
echo "✅ x11vnc started (PID: $X11VNC_PID)"

# Start noVNC (web-based VNC client) in background
cd /opt/novnc && ./utils/novnc_proxy --vnc localhost:5900 --listen 6080 &
NOVNC_PID=$!

# Verify noVNC started
sleep 2
if ! kill -0 $NOVNC_PID 2>/dev/null; then
    echo "❌ ERROR: noVNC failed to start"
    exit 1
fi
echo "✅ noVNC started (PID: $NOVNC_PID)"
echo ""
echo "🌐 Access OAuth browser at: http://localhost:6080/vnc.html"
echo "   (Replace localhost with your server IP in production)"
echo ""

# Start the main application
echo "🚀 Starting FastAPI backend..."
exec "$@"
