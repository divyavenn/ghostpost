# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    procps \
    libxss1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf-2.0-0 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrender1 \
    libxtst6 \
    libnss3 \
    libcups2 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Create user and group
RUN groupadd -g 1000 ayush && useradd -u 1000 -g ayush -m ayush

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml ./
# Copy uv.lock if it exists, otherwise create it
COPY uv.lock* ./

# Install dependencies using uv (will create uv.lock if it doesn't exist)
RUN uv sync --no-dev

# Copy application code
COPY . .

# create backend directory to match import statements in main.py, Need to verify if this follows best practices
RUN mkdir -p backend
RUN mv *.py backend/

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# Create the directory
RUN mkdir -p /opt/playwright

# Install browsers (they'll go to the path specified by the env var)
RUN uv run playwright install --with-deps chromium

# Make it accessible to all users
RUN chmod -R 755 /opt/playwright
ENV PYTHONPATH=/app
# ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
# Use a directory that's NOT mounted as a volume
ENV UV_CACHE_DIR=/tmp/uv-cache

# # Create cache directory with proper permissions
# RUN mkdir -p /app/.cache/uv && chmod 777 /app/.cache/uv

# RUN chmod -R 755 /app

# Expose port
EXPOSE 8000

# Run the application using uv
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]