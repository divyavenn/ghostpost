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
    `docker ps` # to find the container id
    `docker logs <container_id>`

## Docker Compose Services

- **Frontend**: React/Vite app served by Nginx on port 80
- **Backend**: FastAPI app on port 8000 (internal)
- **Cache-init**: Sets up proper permissions for cache directories

## Environment Setup for Docker

1) Create environment files:

    `cp backend/.env.example backend/.env`
    `cp frontend/.env.example frontend/.env`

2) Configure your environment variables in both `.env` files

3) Build and start:

    `docker compose up --build -d`

## Production Deployment with Systemd

For production environments, you can run Docker Compose as a systemd service:

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

3) Enable and start the service:

    `sudo systemctl daemon-reload`
    `sudo systemctl enable ghostposter-app`
    `sudo systemctl start ghostposter-app`

4) Check service status:

    `sudo systemctl status ghostposter-app`

5) View logs:

    `sudo journalctl -u ghostposter-app -f`

## Pushing Updates and Redeploying

### From Dev Machine

1) Push your code changes to main

      `git push origin main`

### On Server

2) SSH into the server

      `ssh username@your-server-ip`

3) Navigate to the project directory

      `cd /path/to/your/project`

4) Pull the latest changes and rebuild

      `git pull`
      `docker compose down`
      `docker compose up --build -d`

5) Verify services are running

      `docker compose ps`
      `docker compose logs -f`

## Accessing the Application

- **Frontend**: http://your-server-ip:80 (port 80)
- **Backend API**: http://your-server-ip/api/

## Debugging

### Docker Compose Debugging
- View all logs: `docker compose logs -f`
- View backend logs: `docker compose logs -f backend`
- View frontend logs: `docker compose logs -f frontend`
- Check service status: `docker compose ps`

### Common Issues

1) **Port conflicts**: Ensure ports 80 and 8000 are not in use
2) **Permission issues**: Check that Docker has proper permissions
3) **Environment variables**: Verify `.env` files are properly configured
4) **Build failures**: Check Docker logs for specific error messages
