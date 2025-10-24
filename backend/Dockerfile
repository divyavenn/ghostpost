# Use Python 3.11 slim base image (Debian Bookworm - stable)
FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Prevent Python from writing .pyc files and buffer output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies - Xvfb for local scraping, basic utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Virtual display for local scraping (headless Playwright)
    xvfb \
    # Basic utilities
    curl \
    wget \
    ca-certificates \
    # Cleanup to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager for Python
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    # Copy uv binary to system-wide location so appuser can access it
    cp /root/.local/bin/uv /usr/local/bin/uv && \
    chmod +x /usr/local/bin/uv
ENV PATH="/usr/local/bin:${PATH}"

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY backend ./backend
COPY docker-entrypoint.sh ./


RUN uv lock
# Install Python dependencies using uv
RUN uv sync --frozen

# Install Playwright system dependencies first (as root before switching to appuser)
RUN uv run playwright install-deps chromium

# Create cache directory with proper permissions
RUN mkdir -p /app/cache && \
    chmod 755 /app/cache

# Make entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Create a non-root user for running the application
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Install Playwright browsers (Chromium for browser automation) as appuser
# This ensures browsers are in /home/appuser/.cache where Playwright expects them
RUN uv run playwright install chromium

# Expose port
# 8000: Backend API
EXPOSE 8000

# Health check for the backend API
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command to start the FastAPI application
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
