#!/bin/bash
# Production Browser Setup with noVNC
# Run this on your production server to enable remote browser access

set -e

echo "🚀 Setting up remote browser access for FloodMe OAuth..."
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script needs sudo privileges to install packages"
    echo "Please run: sudo bash setup-production-browser.sh"
    exit 1
fi

# Install required packages
echo "📦 Installing required packages..."
apt-get update -qq
apt-get install -y \
    xvfb \
    x11vnc \
    git \
    python3-numpy \
    websockify

# Create directory for noVNC
NOVNC_DIR="/opt/novnc"
echo ""
echo "📥 Installing noVNC..."

if [ -d "$NOVNC_DIR" ]; then
    echo "noVNC already exists, updating..."
    cd $NOVNC_DIR && git pull
else
    git clone https://github.com/novnc/noVNC.git $NOVNC_DIR
fi

# Clone websockify if needed
if [ ! -d "$NOVNC_DIR/utils/websockify" ]; then
    git clone https://github.com/novnc/websockify $NOVNC_DIR/utils/websockify
fi

# Create systemd service for Xvfb
echo ""
echo "⚙️  Creating Xvfb service..."
cat > /etc/systemd/system/xvfb.service <<'EOF'
[Unit]
Description=X Virtual Frame Buffer Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :99 -screen 0 1280x720x24 -ac +extension GLX +render -noreset
Restart=always
RestartSec=3
Environment=DISPLAY=:99

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for x11vnc
echo "⚙️  Creating x11vnc service..."
cat > /etc/systemd/system/x11vnc.service <<'EOF'
[Unit]
Description=x11vnc VNC Server
After=xvfb.service
Requires=xvfb.service

[Service]
Type=simple
ExecStart=/usr/bin/x11vnc -display :99 -forever -shared -rfbport 5900
Restart=always
RestartSec=3
Environment=DISPLAY=:99

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for noVNC
echo "⚙️  Creating noVNC service..."
cat > /etc/systemd/system/novnc.service <<'EOF'
[Unit]
Description=noVNC Web VNC Client
After=x11vnc.service
Requires=x11vnc.service

[Service]
Type=simple
WorkingDirectory=/opt/novnc
ExecStart=/opt/novnc/utils/novnc_proxy --vnc localhost:5900 --listen 6080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start services
echo ""
echo "🔄 Starting services..."
systemctl daemon-reload
systemctl enable xvfb x11vnc novnc
systemctl restart xvfb
sleep 2
systemctl restart x11vnc
sleep 2
systemctl restart novnc

# Check status
echo ""
echo "✅ Checking service status..."
systemctl is-active --quiet xvfb && echo "  ✓ Xvfb: Running" || echo "  ✗ Xvfb: Failed"
systemctl is-active --quiet x11vnc && echo "  ✓ x11vnc: Running" || echo "  ✗ x11vnc: Failed"
systemctl is-active --quiet novnc && echo "  ✓ noVNC: Running" || echo "  ✗ noVNC: Failed"

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "🎉 Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📱 Access the remote browser from ANY device:"
echo ""
echo "   Open your web browser and go to:"
echo "   http://$SERVER_IP:6080/vnc.html"
echo ""
echo "   Or if you set up a domain:"
echo "   http://your-domain.com:6080/vnc.html"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔒 Security Notes:"
echo "  - Port 6080 is now open (consider adding password protection)"
echo "  - To add password: edit /etc/systemd/system/x11vnc.service"
echo "  - Add '-passwd yourpassword' to ExecStart line"
echo ""
echo "🔥 Firewall Setup (if using ufw):"
echo "  sudo ufw allow 6080/tcp"
echo "  sudo ufw allow 8000/tcp  # For backend API"
echo ""
echo "📝 Service Management:"
echo "  View logs:     sudo journalctl -u novnc -f"
echo "  Restart:       sudo systemctl restart xvfb x11vnc novnc"
echo "  Stop:          sudo systemctl stop xvfb x11vnc novnc"
echo ""
