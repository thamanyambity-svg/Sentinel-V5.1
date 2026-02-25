# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
# build-essential for compiling some python libs
# libpq-dev for psycopg2 (Postgres)
# git if needed for dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY bot/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Environment variables
ENV TIMEOUT=300

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 health_check.py || exit 1

# Default command
CMD ["python3", "bot/main_v5.py"]
