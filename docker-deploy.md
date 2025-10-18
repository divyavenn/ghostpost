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

    `docker compose up --build -d`

3) Stop all services

    `docker compose down`

4) View logs
   ```bash
    docker ps # to find the container id
    docker logs <container_id>
   ```

## Docker Compose Services

- **Frontend**: React/Vite app served by Nginx on port 80
- **Backend**: FastAPI app on port 8000 (internal)
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

## Pushing Updates and Redeploying

### From Dev Machine

1) Push your code changes to main, or merge your branch into main:

      `git push origin main`

### On Server

2) SSH into the server

      `ssh root@45.63.85.26`

3) Navigate to the project directory

      `cd projects/ghostposter`

4) Pull the latest changes and rebuild
    ```bash
      git fetch
      git pull # assuming you are on main since that should be our default hosted branch
      docker compose down
      docker compose up --build -d
    ```

## Accessing the Application

- **Frontend**: https://x.ghostposter.app
- **Backend API**: https://x.ghostposter.app/api/

  If for whatever reason the cloudflare tunnel is down, use this
 - **Frontend**: http://45.63.85.26:80 (port 80)
- **Backend API**: http://45.63.85.26:80/api/

### Common Issues

1) **Port conflicts**: Ensure ports 80 and 8000 are not in use
2) **Permission issues**: Check that Docker has proper permissions
3) **Environment variables**: Verify `.env` files are properly configured
4) **Build failures**: Check Docker logs for specific error messages
