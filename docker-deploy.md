# Docker Deployment Guide

This guide covers deploying the application using Docker Compose for both development and production environments.

## Prerequisites

Before starting, ensure you have:
- Docker and Docker Compose installed
- Git installed
- Access to your server via SSH

## Quick Start with Docker Compose

1) Navigate to the project directory

    `cd /path/to/your/project`

2) Build and start all services

    `./docker-run.sh`

3) Access the services:
   - **Frontend**: http://localhost:80
   - **Backend API**: http://localhost:8000
   - **noVNC (Browser View)**: http://localhost:6080/vnc.html

4) Stop all services

    `docker compose down`

5) View logs
   ```bash
    # View all logs
    docker compose logs -f

    # View specific service logs
    docker compose logs -f backend
    docker compose logs -f frontend
   ```

## Docker Compose Services

- **Frontend**: React/Vite app served by Nginx on port 80
- **Backend**: FastAPI app on port 8000, including:
  - Virtual display (Xvfb) for headless browser automation
  - Playwright with Chromium for browser automation
- **Cache-init**: Sets up proper permissions for cache directories

## Environment Setup for Docker

1) Create environment files:
    ```bash
    cp backend/.env.example backend/.env
    cp frontend/.env.example frontend/.env.production # TODO: change this to env in a future commit just for convenience
    ```

2) Configure your environment variables in both `.env` files

3) Build and start:

    `docker compose up --build -d`

## Production Deployment with Systemd

For production environments, you can run Docker Compose as a systemd service. Skip steps 1, 2 & 3 if you are using the existing ghostposter vultr instance since this is already setup:

1) Create systemd service file:

    `sudo vim /etc/systemd/system/ghostposter-app.service`

2) Add the following content:

```
[Unit]
Description=GhostPoster App - Docker Compose Service
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
Group=root
WorkingDirectory=/root/projects/ghostposter # modify this to your working directory
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=600
TimeoutStopSec=300
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

3) Enable the service:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable ghostposter-app
    
    ```
4) Start the service
   `sudo systemctl start ghostposter-app`

6) Check service status:

    `sudo systemctl status ghostposter-app`

7) View logs:

    `sudo journalctl -u ghostposter-app -f`

8) Periodically clear old images to free up space on the device:
   
   `docker system prune`

The cloudflare tunnel is already set up to point to port 80 (default port). This means when the systemctl service is up and running, it will automatically be accessible from the URL x.ghostposter.app


## Using noVNC for Browser Automation

The backend container includes a web-based VNC client (noVNC) that allows you to view and interact with the headless browser during OAuth flows or debugging.

**Access noVNC**: http://localhost:6080/vnc.html (or use your server IP in production)

This is particularly useful for:
- Debugging OAuth login flows
- Monitoring browser automation tasks
- Troubleshooting browser-related issues

The browser runs in a virtual display (Xvfb) which works on any server, even those without a GUI.

## Automated Deployment with redeploy.sh

The `redeploy.sh` script automates the deployment process:

1) Commits cache files (except user_info.json)
2) Fetches and rebases latest code from GitHub
3) Rebuilds and restarts Docker containers
4) Shows deployment status

**Usage:**
```bash
./redeploy.sh
```

The script includes automatic checks for:
- Docker installation
- Docker Compose availability
- Container status after deployment

### Common Issues

1) **Port conflicts**: Ensure ports 80, 8000, 5900, and 6080 are not in use
2) **Permission issues**: Check that Docker has proper permissions
3) **Environment variables**: Verify `.env` files are properly configured
4) **Build failures**: Check Docker logs for specific error messages
5) **Docker not found**: Install Docker before running redeploy.sh


## Prequisites
2. **Important: Set for production:**
   ```bash
   HEADLESS_BROWSER=true
   BACKEND_URL=http://your-server-ip:8000  # Replace with your actual server IP or domain
   ```

3. Update Twitter Developer Portal**

   Before deploying, add your production callback URL to Twitter:

   ```bash
   # Run this helper to see your callback URL
   ./check-callback-url.sh

4. Then:
   1. Go to https://developer.x.com/en/portal/dashboard
   2. Select your app → "User authentication settings" → "Edit"
   3. Add callback URL: `http://your-server-ip:8000/auth/callback`
   4. Save changes

   **The URL must EXACTLY match your `BACKEND_URL` + `/auth/callback`**