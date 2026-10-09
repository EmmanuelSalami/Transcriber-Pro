# Docker Infrastructure

Complete guide to Docker setup, deployment, and orchestration.

## Table of Contents

- [Docker Overview](#docker-overview)
- [Dockerfiles](#dockerfiles)
- [Docker Compose](#docker-compose)
- [Container Architecture](#container-architecture)
- [Volume Management](#volume-management)
- [Networking](#networking)
- [Environment Configuration](#environment-configuration)
- [Deployment Scenarios](#deployment-scenarios)
- [Troubleshooting](#troubleshooting)

## Docker Overview

The transcription API is containerized using Docker for consistent deployment across environments. Multiple Docker configurations are provided for different use cases.

### Docker Images

- **Standard Image**: CPU-based, suitable for development and low-volume production
- **GPU Image**: CUDA-enabled, for GPU-accelerated transcription

### Docker Compose Files

- **docker-compose.yml**: Standard deployment with all services
- **docker-compose.dev.yml**: Development setup with hot-reload
- **docker-compose.gpu.yml**: GPU-enabled deployment

## Dockerfiles

### Standard Dockerfile

**Location**: `Dockerfile`

**Base Image**: `python:3.11-slim`

**Features**:
- Poetry for dependency management
- FFmpeg for audio processing
- Deno for yt-dlp JavaScript runtime
- Model download on startup
- Health check endpoint

**Key Stages**:

```dockerfile
# 1. Base image with system dependencies
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg curl unzip

# 2. Install Deno (for yt-dlp)
RUN curl -fsSL https://deno.land/install.sh | sh

# 3. Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# 4. Install Python dependencies
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --no-dev

# 5. Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/

# 6. Create directories
RUN mkdir -p /app/models/whisper /app/temp_audio

# 7. Entrypoint script (handles model download)
ENTRYPOINT ["/bin/bash", "/app/scripts/docker-entrypoint.sh"]
```

### GPU Dockerfile

**Location**: `Dockerfile.gpu`

**Base Image**: `nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04`

**Features**:
- CUDA support for GPU acceleration
- CUDA-enabled PyTorch
- GPU model loading
- Same application structure as standard

**Key Differences**:
- CUDA base image
- GPU-specific PyTorch installation
- CUDA environment variables

### Entrypoint Script

**Location**: `scripts/docker-entrypoint.sh`

**Purpose**: Handles model download on container startup

**Logic**:
1. Check if model exists at `WHISPER_MODEL_PATH`
2. If not, download model using `scripts/download_whisper_model.py`
3. Start application

**Benefits**:
- Models persist in Docker volumes
- No re-download on container restart
- Automatic model management

## Docker Compose

### Standard Compose File

**Location**: `docker-compose.yml`

**Services**:

1. **transcription-api**: Main API service
2. **redis**: Job storage and caching
3. **redis-ui**: Redis management interface (optional)
4. **minio**: S3-compatible storage (local testing)
5. **prometheus**: Metrics collection
6. **grafana**: Metrics visualization

### Service Configuration

#### transcription-api

```yaml
transcription-api:
  build:
    context: .
    dockerfile: Dockerfile
  ports:
    - "8000:8000"
  env_file:
    - .env
  volumes:
    - ./logs:/app/logs
    - whisper-models:/app/models/whisper
    - ./temp_audio:/app/temp_audio
    - ./temp_store:/app/temp_store
  depends_on:
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
    interval: 2h
    timeout: 10s
    retries: 3
```

#### redis

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "127.0.0.1:6379:6379"  # Localhost only for security
  volumes:
    - redis-data:/data
  command:
    - redis-server
    - --appendonly
    - yes
    - --requirepass
    - ${REDIS_PASSWORD}
  healthcheck:
    test: ["CMD-SHELL", "redis-cli -a ${REDIS_PASSWORD} ping | grep -q PONG"]
```

#### minio

```yaml
minio:
  image: minio/minio:latest
  ports:
    - "9000:9000"  # API
    - "9001:9001"  # Console
  environment:
    - MINIO_ROOT_USER=${MINIO_ROOT_USER}
    - MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
  volumes:
    - minio-data:/data
  command: server /data --console-address ":9001"
```

### Development Compose File

**Location**: `docker-compose.dev.yml`

**Features**:
- Hot-reload for code changes
- Volume mounts for live code editing
- Development-friendly settings

**Differences**:
- Mounts `./app` for live code changes
- Uses `--reload` flag for uvicorn
- Reduced resource limits

### GPU Compose File

**Location**: `docker-compose.gpu.yml`

**Features**:
- GPU-enabled API service
- CUDA runtime
- GPU resource allocation

**Requirements**:
- NVIDIA Docker runtime
- GPU drivers installed
- `nvidia-docker2` package

**Configuration**:
```yaml
transcription-api:
  build:
    context: .
    dockerfile: Dockerfile.gpu
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

## Container Architecture

### Container Structure

```
transcription-api/
├── /app/                    # Application code
│   ├── app/                 # Main application
│   ├── scripts/             # Utility scripts
│   └── models/              # Whisper models (volume)
├── /app/temp_audio/         # Temporary audio files (volume)
├── /app/temp_store/         # Job results (volume)
└── /app/logs/               # Application logs (volume)
```

### Container Lifecycle

1. **Build**: `docker-compose build`
2. **Start**: `docker-compose up -d`
3. **Entrypoint**: Downloads model if needed
4. **Application**: Starts uvicorn server
5. **Health Check**: Monitors `/health` endpoint
6. **Shutdown**: Graceful shutdown on stop

### Resource Limits

**CPU**: 2.0 cores (limit), 0.5 cores (reservation)

**Memory**: 4GB (limit), 1GB (reservation)

**GPU**: 1 GPU (if GPU compose file)

## Volume Management

### Named Volumes

**whisper-models**: Stores Whisper models
- Persists across container restarts
- Shared between containers
- Prevents re-downloading models

**redis-data**: Redis persistence
- AOF (Append-Only File) enabled
- Data survives container restarts

**minio-data**: MinIO storage
- S3-compatible object storage
- Local testing only

**prometheus-data**: Prometheus metrics
- Time-series data storage
- Retention: 200 hours

**grafana-data**: Grafana configuration
- Dashboards and settings
- User data

### Bind Mounts

**./logs**: Application logs
- Accessible from host
- Useful for log analysis

**./temp_audio**: Temporary audio files
- Cleared on container restart
- Development convenience

**./temp_store**: Job results
- Accessible from host
- Development convenience

### Volume Best Practices

1. **Production**: Use named volumes for persistence
2. **Development**: Use bind mounts for live editing
3. **Models**: Always use named volumes (large files)
4. **Logs**: Bind mount for easy access
5. **Backup**: Regular backups of named volumes

## Networking

### Network Configuration

**Network Name**: `transcription-network`

**Driver**: `bridge`

**Services**:
- All services on same network
- Service names as hostnames
- Internal DNS resolution

### Service Communication

**API → Redis**: `redis:6379`

**API → MinIO**: `minio:9000`

**Prometheus → API**: `transcription-api:8000`

**Grafana → Prometheus**: `prometheus:9090`

### Port Mapping

**Host → Container**:
- `8000:8000` - API
- `6379:6379` - Redis (localhost only)
- `8081:8081` - Redis UI
- `9000:9000` - MinIO API
- `9001:9001` - MinIO Console
- `9090:9090` - Prometheus
- `3000:3000` - Grafana

**Security**: Redis port bound to localhost only

## Environment Configuration

### Environment Variables

Loaded from `.env` file:

```bash
# Copy example
cp env.example .env

# Edit configuration
nano .env
```

### Required Variables

**Production**:
- `API_KEYS`: Comma-separated API keys
- `SECRET_KEY`: Secret key for JWT
- `REDIS_PASSWORD`: Redis password
- `CORS_ORIGINS`: Allowed origins

**Level 3**:
- `RUNPOD_API_KEY`: RunPod API key
- `RUNPOD_TEMPLATE_ID`: Template ID
- `S3_ENABLED`: Enable S3 storage
- `S3_ACCESS_KEY_ID`: S3 access key
- `S3_SECRET_ACCESS_KEY`: S3 secret key

### Environment File Structure

```bash
# API Configuration
API_TITLE=YouTube Transcription API
API_VERSION=v1

# Security
API_KEYS=key1,key2,key3
SECRET_KEY=your-secret-key
CORS_ORIGINS=https://example.com

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your-password

# Whisper
WHISPER_MODEL=openai/whisper-base
WHISPER_DEVICE=cpu

# ... (see env.example for complete list)
```

## Deployment Scenarios

### Local Development

```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose logs -f transcription-api

# Stop services
docker-compose down
```

### Production Deployment

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### GPU Deployment

```bash
# Verify NVIDIA Docker
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Start GPU services
docker-compose -f docker-compose.gpu.yml up -d
```

### Kubernetes Deployment

See [Infrastructure Documentation](../infrastructure/README.md) for Kubernetes deployment.

## Common Operations

### Building Images

```bash
# Build standard image
docker build -t transcription-api:latest .

# Build GPU image
docker build -f Dockerfile.gpu -t transcription-api:gpu .
```

### Starting Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d transcription-api

# Start with logs
docker-compose up
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Stop specific service
docker-compose stop transcription-api
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f transcription-api

# Last 100 lines
docker-compose logs --tail=100 transcription-api
```

### Executing Commands

```bash
# Shell into container
docker-compose exec transcription-api bash

# Run Python script
docker-compose exec transcription-api python scripts/download_whisper_model.py

# Check health
docker-compose exec transcription-api curl http://localhost:8000/health
```

### Updating Services

```bash
# Pull latest images
docker-compose pull

# Rebuild and restart
docker-compose up -d --build

# Restart specific service
docker-compose restart transcription-api
```

## Troubleshooting

### Container Won't Start

**Check logs**:
```bash
docker-compose logs transcription-api
```

**Common issues**:
- Missing environment variables
- Port already in use
- Volume permissions
- Model download failure

### Model Download Issues

**Manual download**:
```bash
docker-compose exec transcription-api python scripts/download_whisper_model.py
```

**Check model location**:
```bash
docker-compose exec transcription-api ls -lh /app/models/whisper
```

### Redis Connection Issues

**Test connection**:
```bash
docker-compose exec redis redis-cli -a ${REDIS_PASSWORD} ping
```

**Check network**:
```bash
docker-compose exec transcription-api ping redis
```

### Volume Issues

**Check volumes**:
```bash
docker volume ls
docker volume inspect transcription_whisper-models
```

**Reset volumes**:
```bash
docker-compose down -v
docker-compose up -d
```

### Resource Issues

**Check resource usage**:
```bash
docker stats
```

**Adjust limits** in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 8G
```

## Best Practices

1. **Use .env file**: Never commit `.env` to version control
2. **Named volumes**: Use for persistent data (models, Redis)
3. **Health checks**: Monitor container health
4. **Resource limits**: Set appropriate CPU/memory limits
5. **Log rotation**: Configure log rotation for production
6. **Backup volumes**: Regular backups of named volumes
7. **Security**: Bind Redis to localhost, use strong passwords
8. **Updates**: Regularly update base images and dependencies

## Next Steps

- Review [Installation Guide](INSTALLATION.md) for setup
- Check [Configuration Guide](CONFIGURATION.md) for settings
- See [Architecture Documentation](architecture.md) for system design
- Read [Infrastructure Documentation](../infrastructure/README.md) for Kubernetes
