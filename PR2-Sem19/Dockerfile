# ============================================
# Standard Dockerfile
# ============================================

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Add poetry to PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install deno (JavaScript runtime for yt-dlp)
RUN curl -fsSL https://deno.land/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install Python dependencies
RUN poetry install --no-root --no-dev --no-interaction --no-ansi

# Update yt-dlp to latest version to avoid YouTube blocking
# YouTube frequently changes their API, so we need the latest yt-dlp
RUN poetry run pip install --upgrade yt-dlp || pip install --upgrade yt-dlp

# Copy application code
COPY app/ ./app/

# Copy scripts including entrypoint and download script
COPY scripts/ ./scripts/

# Create models directory for mounting pre-downloaded Whisper models
# This allows mounting models as volumes to avoid downloading on each container start
RUN mkdir -p /app/models/whisper && chmod 755 /app/models/whisper
# Also create internal models directory for read-only volume fallback
RUN mkdir -p /app/.models/whisper && chmod 755 /app/.models/whisper

# Create temp_audio directory for audio downloads
RUN mkdir -p /app/temp_audio && chmod 777 /app/temp_audio

# Make entrypoint script executable
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=7200s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint to handle model downloading
# Use bash explicitly to ensure script execution
ENTRYPOINT ["/bin/bash", "/app/scripts/docker-entrypoint.sh"]

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
