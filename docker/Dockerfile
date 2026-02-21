# Radio Monitor 1.0 - Dockerfile
# Multi-stage build for optimized image size

# Stage 1: Builder
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies to /usr/local
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Metadata
LABEL maintainer="Radio Monitor"
LABEL description="Automatically discovers music from radio stations"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RADIO_MONITOR_DB_PATH=/app/data/radio_songs.db \
    RADIO_MONITOR_SETTINGS_PATH=/app/data/radio_monitor_settings.json \
    TZ=America/Chicago

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*
# Chrome for Selenium removed in v1.1.0 (WTMX station no longer supported)

# Copy Python dependencies from builder
COPY --from=builder /install /usr/local

# Set working directory to /app/data (so wizard creates files in mounted volume)
WORKDIR /app/data

# Create app directories
RUN mkdir -p /app/radio_monitor /app/templates /app/prompts

# Copy application code (to /app, not /app/data)
COPY radio_monitor/ /app/radio_monitor/
COPY templates/ /app/templates/
COPY prompts/ /app/prompts/

# Add /app to Python path so imports work
ENV PYTHONPATH=/app:$PYTHONPATH

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash radio && \
    chown -R radio:radio /app

# Switch to non-root user
USER radio

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

# Run application
CMD ["python", "-m", "radio_monitor.cli", "--gui"]
