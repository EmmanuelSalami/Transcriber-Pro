# Installation Guide

This comprehensive guide covers installation and setup of the YouTube Transcription API for different deployment scenarios, from local development to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Installation Methods](#installation-methods)
  - [Local Development Setup](#local-development-setup)
  - [Docker Setup](#docker-setup)
  - [Production Deployment](#production-deployment)
- [Post-Installation Configuration](#post-installation-configuration)
- [Verification and Testing](#verification-and-testing)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

## Prerequisites

### System Requirements

**Minimum Requirements:**

- **Python**: 3.11 or higher (for local development)
- **Docker**: 20.10+ and Docker Compose 2.0+ (for containerized deployment)
- **Memory**: Minimum 4GB RAM (8GB+ recommended for ASR processing)
- **Storage**: At least 5GB free space for models and temporary files
- **Network**: Internet connection for downloading models and YouTube videos

**Recommended for Production:**

- **Memory**: 8GB+ RAM for optimal ASR performance
- **Storage**: 10GB+ for models, temporary files, and logs
- **CPU**: Multi-core processor (4+ cores recommended)
- **GPU**: NVIDIA GPU with CUDA support for faster ASR processing (optional but recommended)

### Software Dependencies

**Required:**

- **Poetry**: Python dependency manager (auto-installed in Docker)
- **Redis**: Job storage and queue management (included in Docker Compose)
- **FFmpeg**: Audio/video processing (included in Docker image)

**Optional:**

- **MinIO**: S3-compatible storage for local testing (included in Docker Compose)
- **Prometheus**: Metrics collection (included in Docker Compose)
- **Grafana**: Metrics visualization (included in Docker Compose)

## Architecture Overview

### System Architecture

The YouTube Transcription API consists of several interconnected services:

```mermaid
graph TB
    Client[Client Application] -->|HTTP/HTTPS| API[Transcription API<br/>FastAPI]
    API -->|Job Storage| Redis[(Redis<br/>Job Queue)]
    API -->|Media Storage| S3[S3/MinIO<br/>Object Storage]
    API -->|ASR Processing| Whisper[Whisper Model<br/>ASR Engine]
    API -->|Metrics| Prometheus[Prometheus<br/>Metrics]
    Prometheus -->|Visualization| Grafana[Grafana<br/>Dashboards]

    subgraph "Optional GPU Workers"
        Worker1[GPU Worker 1]
        Worker2[GPU Worker 2]
        WorkerN[GPU Worker N]
    end

    API -->|Queue Jobs| Worker1
    API -->|Queue Jobs| Worker2
    API -->|Queue Jobs| WorkerN

    style API fill:#4CAF50,stroke:#388E3C,stroke-width:2px,color:#fff
    style Redis fill:#F44336,stroke:#D32F2F,stroke-width:2px,color:#fff
    style S3 fill:#FF9800,stroke:#F57C00,stroke-width:2px,color:#fff
    style Whisper fill:#9C27B0,stroke:#7B1FA2,stroke-width:2px,color:#fff
```

### Service Components

| Service               | Purpose                               | Port       | Required |
| --------------------- | ------------------------------------- | ---------- | -------- |
| **Transcription API** | Main FastAPI application              | 8000       | Yes      |
| **Redis**             | Job storage and queue management      | 6379       | Yes      |
| **MinIO**             | S3-compatible storage (local testing) | 9000, 9001 | Optional |
| **Prometheus**        | Metrics collection                    | 9090       | Optional |
| **Grafana**           | Metrics visualization                 | 3000       | Optional |
| **Redis UI**          | Redis management interface            | 8081       | Optional |

## Installation Methods

## Local Development Setup

This method is ideal for development, testing, and debugging. It requires manual setup of dependencies but provides the most control and fastest iteration.

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone <repository-url>
cd transcription

# Verify repository structure
ls -la
```

**Expected directory structure:**

```
transcription/
├── app/              # Application code
├── scripts/          # Utility scripts
├── tests/            # Test suite
├── docs/             # Documentation
├── env.example       # Environment template
├── pyproject.toml    # Poetry dependencies
└── docker-compose.yml # Docker configuration
```

### Step 2: Install Python Dependencies

The project uses **Poetry** for dependency management, which ensures consistent environments across different systems.

```bash
# Install Poetry if not already installed
# macOS/Linux:
curl -sSL https://install.python-poetry.org | python3 -

# Windows (PowerShell):
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Verify Poetry installation
poetry --version

# Install project dependencies (this may take several minutes)
poetry install

# Activate the virtual environment
poetry shell

# Verify installation
python --version  # Should show Python 3.11+
poetry show       # Lists all installed packages
```

**What this does:**

- Creates an isolated virtual environment
- Installs all Python dependencies from `pyproject.toml`
- Includes development dependencies (pytest, black, ruff, etc.)

**Troubleshooting:**

- If Poetry installation fails, ensure Python 3.11+ is installed: `python3 --version`
- If `poetry install` fails, try: `poetry install --no-root` then `poetry install`

### Step 3: Configure Environment

Environment configuration is critical for the application to function correctly.

```bash
# Copy the example environment file
cp env.example .env

# Generate API keys (required for authentication)
python scripts/generate_api_key.py

# Generate secret key (required for production)
python scripts/generate_secret_key.py
```

**Edit `.env` file with the generated values:**

```bash
# Minimum required configuration for local development
API_KEYS=your-generated-api-key-here
SECRET_KEY=your-generated-secret-key-here

# Redis configuration (required for job management)
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=dev-redis-password-change-me

# Whisper model configuration
WHISPER_MODEL=openai/whisper-base
WHISPER_DEVICE=cpu  # Use 'cuda' if you have GPU support

# Temporary directories (create these if they don't exist)
TEMP_AUDIO_DIR=./temp_audio
TEMP_STORE_DIR=./temp_store
```

**Important Configuration Notes:**

- **API_KEYS**: Comma-separated list of valid API keys. Clients must send `Authorization: Bearer <API_KEY>` header
- **REDIS_PASSWORD**: Must match the password used when starting Redis (see Step 4)
- **TEMP_AUDIO_DIR** and **TEMP_STORE_DIR**: Directories must exist and be writable

**Create required directories:**

```bash
mkdir -p temp_audio temp_store logs
chmod 755 temp_audio temp_store logs
```

### Step 4: Download Whisper Model

The Whisper model is required for ASR (Automatic Speech Recognition) fallback when YouTube captions are unavailable.

```bash
# Download default model (whisper-base, ~150MB)
python scripts/download_whisper_model.py

# Or specify a different model
# Options: openai/whisper-base, openai/whisper-small, openai/whisper-medium, openai/whisper-large-v3
WHISPER_MODEL=openai/whisper-small python scripts/download_whisper_model.py
```

**Model Size Reference:**
| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| `whisper-base` | ~150MB | Fast | Good | Development, testing |
| `whisper-small` | ~500MB | Medium | Better | Production (balanced) |
| `whisper-medium` | ~1.5GB | Slow | Excellent | High accuracy needed |
| `whisper-large-v3` | ~3GB | Very Slow | Best | Maximum accuracy |

**What this does:**

- Downloads the Whisper model from Hugging Face
- Saves model files to `./models/whisper/` (or specified directory)
- Model files include: `config.json`, `tokenizer.json`, `model.safetensors`, etc.

**Troubleshooting:**

- If download fails, check internet connection and Hugging Face access
- Ensure sufficient disk space (models range from 150MB to 3GB)
- If using a proxy, configure it: `export HTTP_PROXY=your-proxy-url`

### Step 5: Start Redis (Required for Job Management)

Redis is required for persistent job storage and queue management. The application will not start without Redis.

**Option A: Using Docker (Recommended for Development)**

```bash
# Start Redis container
docker run -d \
  --name transcription-redis \
  -p 6379:6379 \
  -e REDIS_PASSWORD=dev-redis-password-change-me \
  redis:7-alpine \
  redis-server --appendonly yes --requirepass dev-redis-password-change-me

# Verify Redis is running
docker ps | grep redis

# Test Redis connection
docker exec -it transcription-redis redis-cli -a dev-redis-password-change-me ping
# Should return: PONG
```

**Option B: Local Installation**

```bash
# macOS (using Homebrew)
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Configure Redis password (edit /etc/redis/redis.conf)
# Add: requirepass dev-redis-password-change-me
# Restart: sudo systemctl restart redis-server

# Test connection
redis-cli -a dev-redis-password-change-me ping
```

**Important:** The `REDIS_PASSWORD` in your `.env` file must match the password used when starting Redis.

### Step 6: Run the Application

Start the FastAPI application in development mode with auto-reload enabled.

```bash
# Ensure you're in the poetry shell
poetry shell

# Start the application with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Poetry directly
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**What you should see:**

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Access Points:**

- **API Base URL**: http://localhost:8000
- **Interactive API Docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative API Docs (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Metrics Endpoint**: http://localhost:8000/v1/metrics

## Docker Setup

Docker setup is the recommended method for most users as it handles all dependencies automatically and ensures consistent environments.

### Docker Compose Services Architecture

```mermaid
graph LR
    subgraph "Docker Compose Stack"
        API[transcription-api<br/>:8000]
        Redis[(Redis<br/>:6379)]
        MinIO[MinIO<br/>:9000/:9001]
        Prom[Prometheus<br/>:9090]
        Graf[Grafana<br/>:3000]
        RedisUI[Redis UI<br/>:8081]
    end

    API -->|Job Storage| Redis
    API -->|Media Storage| MinIO
    API -->|Metrics| Prom
    Prom -->|Visualization| Graf
    RedisUI -->|Management| Redis

    style API fill:#4CAF50,stroke:#388E3C,stroke-width:2px,color:#fff
    style Redis fill:#F44336,stroke:#D32F2F,stroke-width:2px,color:#fff
    style MinIO fill:#FF9800,stroke:#F57C00,stroke-width:2px,color:#fff
```

### Step 1: Configure Environment

```bash
# Copy the example environment file
cp env.example .env

# Generate secure API keys
python scripts/generate_api_key.py

# Generate secret key
python scripts/generate_secret_key.py
```

**Edit `.env` file - Minimum Required Configuration:**

```bash
# Security (REQUIRED)
API_KEYS=your-generated-api-key-1,your-generated-api-key-2
SECRET_KEY=your-generated-secret-key-here

# Redis (REQUIRED - must be set, cannot be empty)
REDIS_PASSWORD=your-secure-redis-password-here

# Whisper Model (optional - defaults to whisper-base)
WHISPER_MODEL=openai/whisper-base

# S3/MinIO Configuration (optional - for Level 3 features)
S3_ENABLED=true
S3_BUCKET_NAME=transcription-storage
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_ENDPOINT_URL=http://minio:9000
```

**Important Notes:**

- **REDIS_PASSWORD**: Cannot be empty. Docker Compose will fail if not set. Use a strong password in production.
- **API_KEYS**: Multiple keys can be comma-separated for different clients/environments
- **S3 Configuration**: MinIO is included in Docker Compose for local testing. For production, configure real S3 credentials.

### Step 2: Choose Docker Compose File

The project provides different Docker Compose configurations:

| File                     | Purpose                     | Use Case              |
| ------------------------ | --------------------------- | --------------------- |
| `docker-compose.yml`     | Production configuration    | Production deployment |
| `docker-compose.dev.yml` | Development with hot-reload | Local development     |
| `docker-compose.gpu.yml` | GPU-enabled configuration   | GPU processing        |

**For Development:**

```bash
# Use development compose file (includes hot-reload)
docker-compose -f docker-compose.dev.yml up -d
```

**For Production:**

```bash
# Use production compose file
docker-compose -f docker-compose.yml up -d
```

**For GPU Support:**

```bash
# Use GPU-enabled compose file
docker-compose -f docker-compose.gpu.yml up -d
```

### Step 3: Start Services

```bash
# Start all services in detached mode
docker-compose up -d

# View logs from all services
docker-compose logs -f

# View logs from specific service
docker-compose logs -f transcription-api

# Check service status
docker-compose ps
```

**What Happens During Startup:**

1. **Docker builds the API image** (first time only, ~5-10 minutes)
2. **Services start in order:**

   - Redis starts first (required dependency)
   - MinIO starts (S3-compatible storage)
   - Prometheus and Grafana start (monitoring)
   - API starts last (depends on Redis)

3. **Model Download (Automatic):**
   - On first start, the `docker-entrypoint.sh` script runs
   - Checks if Whisper model exists at `/app/models/whisper`
   - If not found, automatically downloads the model from Hugging Face
   - Model is stored in Docker volume `whisper-models` (persists across restarts)
   - **First startup may take 5-15 minutes** depending on model size and internet speed

**Expected Output:**

```
Creating network "transcription-network" ...
Creating volume "transcription_whisper-models" ...
Creating volume "transcription_redis-data" ...
Creating transcription-redis ... done
Creating transcription-minio ... done
Creating transcription-prometheus ... done
Creating transcription-grafana ... done
Creating transcription-api ... done
```

### Step 4: Verify Services Are Running

```bash
# Check all containers are running
docker-compose ps

# Expected output:
# NAME                    STATUS          PORTS
# transcription-api       Up 2 minutes    0.0.0.0:8000->8000/tcp
# transcription-redis     Up 2 minutes    127.0.0.1:6379->6379/tcp
# transcription-minio     Up 2 minutes    0.0.0.0:9000->9000/tcp, 0.0.0.0:9001->9001/tcp
# transcription-prometheus Up 2 minutes  0.0.0.0:9090->9090/tcp
# transcription-grafana   Up 2 minutes    0.0.0.0:3000->3000/tcp

# Check API health
curl http://localhost:8000/health

# Check Redis connection
docker exec transcription-redis redis-cli -a $REDIS_PASSWORD ping

# Check MinIO
curl http://localhost:9000/minio/health/live
```

### Step 5: Access Services

Once all services are running, access them at:

| Service           | URL                          | Credentials                                             | Purpose                       |
| ----------------- | ---------------------------- | ------------------------------------------------------- | ----------------------------- |
| **API**           | http://localhost:8000        | API Key (Bearer token)                                  | Main API endpoint             |
| **API Docs**      | http://localhost:8000/docs   | None                                                    | Interactive API documentation |
| **ReDoc**         | http://localhost:8000/redoc  | None                                                    | Alternative API documentation |
| **Health Check**  | http://localhost:8000/health | None                                                    | Service health status         |
| **Redis UI**      | http://localhost:8081        | From `.env` (REDIS_UI_USER/REDIS_UI_PASSWORD)           | Redis management interface    |
| **MinIO Console** | http://localhost:9001        | From `.env` (MINIO_ROOT_USER/MINIO_ROOT_PASSWORD)       | S3 storage management         |
| **Prometheus**    | http://localhost:9090        | None                                                    | Metrics collection            |
| **Grafana**       | http://localhost:3000        | From `.env` (GRAFANA_ADMIN_USER/GRAFANA_ADMIN_PASSWORD) | Metrics visualization         |

**First-Time MinIO Setup:**

1. Access MinIO Console at http://localhost:9001
2. Login with credentials from `.env` (default: minioadmin/minioadmin)
3. Create a bucket named `transcription-storage` (or match `S3_BUCKET_NAME` in `.env`)
4. Configure bucket policies if needed

## Production Deployment

Production deployment requires additional security, monitoring, and scalability considerations.

### Step 1: Environment Configuration

**Critical Production Settings:**

```bash
# Security (REQUIRED - Never use defaults in production!)
API_KEYS=production-key-1,production-key-2,production-key-3
SECRET_KEY=your-very-secure-32-character-minimum-secret-key
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
DEV_MODE=false

# Redis (REQUIRED)
REDIS_ENABLED=true
REDIS_PASSWORD=strong-production-password-minimum-32-characters
REDIS_HOST=redis  # Use service name in Docker, or external Redis hostname

# S3 Storage (REQUIRED for Level 3)
S3_ENABLED=true
S3_BUCKET_NAME=your-production-bucket-name
S3_ACCESS_KEY_ID=your-aws-access-key-id
S3_SECRET_ACCESS_KEY=your-aws-secret-access-key
S3_ENDPOINT_URL=  # Empty for AWS S3, or your S3-compatible endpoint
S3_REGION=us-east-1

# Observability (Recommended)
OBSERVABILITY_ENABLED=true
METRICS_ENABLED=true
LOG_FORMAT=json
LOG_LEVEL=INFO

# Whisper Configuration
WHISPER_MODEL=openai/whisper-small  # or whisper-medium for better accuracy
WHISPER_DEVICE=cuda  # Use GPU if available
WHISPER_COMPUTE_TYPE=float16  # Use float16 for GPU

# Processing Limits
MAX_VIDEO_DURATION_SECONDS=3600  # 1 hour max
ASYNC_THRESHOLD_SECONDS=300  # 5 minutes - switch to async
```

**Security Checklist:**

- [ ] Generate strong, unique API keys (use `scripts/generate_api_key.py`)
- [ ] Generate strong secret key (use `scripts/generate_secret_key.py`)
- [ ] Set `CORS_ORIGINS` to specific domains (never use `*` in production)
- [ ] Set `DEV_MODE=false`
- [ ] Use strong Redis password (32+ characters recommended)
- [ ] Use production-grade S3 credentials (not MinIO defaults)
- [ ] Enable observability and monitoring
- [ ] Review and adjust rate limits based on expected load

### Step 2: Docker Compose Production

```bash
# Use production compose file
docker-compose -f docker-compose.yml up -d

# Or with GPU support
docker-compose -f docker-compose.gpu.yml up -d

# View logs
docker-compose logs -f transcription-api

# Check service health
docker-compose ps
```

**Production Considerations:**

- Remove port exposures for Redis (already configured in `docker-compose.yml` to bind to localhost only)
- Use external Redis instance for high availability
- Use external S3 (AWS S3, Cloudflare R2, etc.) instead of MinIO
- Configure resource limits in `docker-compose.yml` (already included)
- Set up log rotation and retention
- Configure backup strategies for Redis and S3

### Step 3: Kubernetes Deployment (Optional)

For Kubernetes deployment, see the [Infrastructure Documentation](../infrastructure/README.md).

**Kubernetes Resources:**

- Deployment manifests: `infrastructure/kubernetes/api-deployment.yaml`
- Horizontal Pod Autoscaler: `infrastructure/kubernetes/hpa.yaml`
- Service and Ingress configurations

### Step 4: Model Pre-loading

For faster startup and to avoid download delays, pre-download Whisper models to persistent volumes:

```bash
# Download model to persistent volume (one-time setup)
docker run --rm \
  -v whisper-models:/app/models/whisper \
  -e WHISPER_MODEL=openai/whisper-small \
  transcription-api:latest \
  python scripts/download_whisper_model.py openai/whisper-small /app/models/whisper

# Verify model is downloaded
docker run --rm \
  -v whisper-models:/app/models/whisper \
  transcription-api:latest \
  ls -lh /app/models/whisper
```

**Benefits:**

- Faster container startup (no model download delay)
- Consistent model versions across deployments
- Reduced bandwidth usage
- Better for CI/CD pipelines

## Post-Installation Configuration

### 1. Generate and Configure API Keys

API keys are required for authentication. Generate them securely:

```bash
# Generate a single API key
python scripts/generate_api_key.py

# Generate multiple API keys (for different clients/environments)
python scripts/generate_api_key.py 3

# Output example:
# Generated API Keys (add these to your .env file):
# ============================================================
# API_KEY_1=abc123xyz...
# API_KEY_2=def456uvw...
# API_KEY_3=ghi789rst...
# ============================================================
#
# Add to .env file:
# API_KEYS=abc123xyz...,def456uvw...,ghi789rst...
```

**Add to `.env`:**

```bash
API_KEYS=your-generated-key-1,your-generated-key-2
```

**Usage in API Requests:**

```bash
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer your-generated-key-1" \
  -F "url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### 2. Configure S3 Storage (Level 3)

**For MinIO (Local Testing):**

1. Access MinIO Console: http://localhost:9001
2. Login with credentials from `.env` (default: `minioadmin`/`minioadmin`)
3. Create bucket:
   - Click "Create Bucket"
   - Name: `transcription-storage` (or match `S3_BUCKET_NAME` in `.env`)
   - Region: `us-east-1` (or match `S3_REGION`)
   - Click "Create Bucket"
4. Configure access policy if needed (default: private)

**For AWS S3 (Production):**

1. Create S3 bucket in AWS Console
2. Configure IAM user with S3 access permissions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject",
           "s3:DeleteObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::your-bucket-name/*",
           "arn:aws:s3:::your-bucket-name"
         ]
       }
     ]
   }
   ```
3. Generate access key and secret key
4. Update `.env`:
   ```bash
   S3_ENABLED=true
   S3_BUCKET_NAME=your-aws-bucket-name
   S3_ACCESS_KEY_ID=your-aws-access-key-id
   S3_SECRET_ACCESS_KEY=your-aws-secret-access-key
   S3_ENDPOINT_URL=  # Leave empty for AWS S3
   S3_REGION=us-east-1
   ```

### 3. Configure GPU Workers (Level 3 - Optional)

For automatic GPU worker scaling using RunPod:

1. **Get RunPod API Key:**

   - Sign up at https://www.runpod.io
   - Navigate to: https://www.runpod.io/console/user/settings
   - Copy your API key

2. **Create RunPod Template:**

   - Go to RunPod Console → Templates
   - Create new template with your worker Docker image
   - Note the Template ID

3. **Configure in `.env`:**

   ```bash
   RUNPOD_API_KEY=your-runpod-api-key
   RUNPOD_TEMPLATE_ID=your-template-id
   WORKER_AUTO_SCALING_ENABLED=true
   MAX_WORKERS=5
   MIN_WORKERS=0
   WORKER_SCALE_UP_QUEUE_DEPTH=10
   WORKER_SCALE_DOWN_QUEUE_DEPTH=2
   ```

4. **Test Connection:**

   ```bash
   # Using script
   python scripts/test_runpod_connection.py

   # Or via API (requires API key)
   curl -X GET "http://localhost:8000/v1/workers/test-connection" \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

### 4. Configure Monitoring

**Prometheus:**

- Already configured in Docker Compose
- Access at: http://localhost:9090
- Metrics endpoint: http://localhost:8000/v1/metrics

**Grafana:**

1. Access Grafana: http://localhost:3000
2. Login with credentials from `.env` (default: `admin`/`admin`)
3. Import dashboards:
   - Go to Dashboards → Import
   - Upload `infrastructure/grafana/dashboards/transcription-api.json`
   - Or use dashboard ID if available
4. Configure data source (Prometheus should be auto-configured)

**Key Metrics to Monitor:**

- Request rate and latency
- Job queue depth
- Worker status and count
- Error rates
- Model download/load times
- Redis connection health
- S3 storage usage

## Verification and Testing

### 1. Health Check

```bash
# Basic health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"v1","timestamp":"2024-01-01T00:00:00Z"}

# Detailed health check (includes service status)
curl http://localhost:8000/health?detailed=true
```

### 2. Test API Endpoint

```bash
# Replace YOUR_API_KEY with your actual API key from .env

# Test YouTube transcription (synchronous - short video)
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  -F "format=json"

# Test with different format
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  -F "format=srt"

# Test async job (for longer videos)
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=LONG_VIDEO_ID" \
  -F "format=json"
```

### 3. Verify Services

```bash
# Check all Docker containers are running
docker-compose ps

# Check API logs for errors
docker-compose logs transcription-api | grep -i error

# Check Redis connection
docker exec transcription-redis redis-cli -a $REDIS_PASSWORD ping

# Check MinIO health
curl http://localhost:9000/minio/health/live

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets
```

### 4. Test Job Processing

```bash
# Submit a job
JOB_RESPONSE=$(curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  -F "format=json")

# Extract job ID (if async)
JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')

# Poll job status
curl -X GET "http://localhost:8000/v1/jobs/$JOB_ID" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Model Download Fails

**Symptoms:**

- Container logs show "Failed to download model"
- Application starts but ASR requests fail

**Solutions:**

```bash
# Check internet connection
curl https://huggingface.co

# Verify disk space (models are 150MB-3GB)
df -h

# Manually download model
docker exec -it transcription-api python scripts/download_whisper_model.py

# Check Hugging Face access
docker exec -it transcription-api curl https://huggingface.co
```

#### 2. Redis Connection Errors

**Symptoms:**

- Logs show "Redis connection failed"
- Jobs are not being stored

**Solutions:**

```bash
# Verify Redis is running
docker ps | grep redis

# Check Redis password matches .env
docker exec transcription-redis redis-cli -a $REDIS_PASSWORD ping

# Test connection from API container
docker exec transcription-api redis-cli -h redis -p 6379 -a $REDIS_PASSWORD ping

# Check Redis logs
docker-compose logs redis
```

#### 3. Port Already in Use

**Symptoms:**

- Docker Compose fails with "port already in use"
- Cannot access services

**Solutions:**

```bash
# Find what's using the port
lsof -i :8000  # For API
lsof -i :6379  # For Redis

# Stop conflicting service or change port in docker-compose.yml
# For API port, edit docker-compose.yml:
# ports:
#   - "8001:8000"  # Use different host port
```

#### 4. Permission Errors

**Symptoms:**

- "Permission denied" errors in logs
- Cannot write to temp directories

**Solutions:**

```bash
# Fix directory permissions (local development)
chmod 777 temp_audio temp_store logs

# Check Docker volume permissions
docker volume inspect transcription_whisper-models

# Recreate volumes if needed
docker-compose down -v
docker-compose up -d
```

#### 5. API Key Authentication Fails

**Symptoms:**

- "401 Unauthorized" errors
- "Invalid API key" messages

**Solutions:**

```bash
# Verify API key in .env
cat .env | grep API_KEYS

# Check API key format (should be comma-separated, no spaces)
# Correct: API_KEYS=key1,key2,key3
# Wrong:   API_KEYS=key1, key2, key3

# Regenerate API keys
python scripts/generate_api_key.py

# Restart services after changing .env
docker-compose restart transcription-api
```

#### 6. Services Not Starting

**Symptoms:**

- Containers exit immediately
- `docker-compose ps` shows "Exited" status

**Solutions:**

```bash
# Check logs for errors
docker-compose logs transcription-api

# Verify .env file exists and is valid
cat .env

# Check for required environment variables
docker-compose config

# Verify Docker and Docker Compose versions
docker --version
docker-compose --version
```

#### 7. Model Not Found After Restart

**Symptoms:**

- Model downloads on every restart
- Slow startup times

**Solutions:**

```bash
# Verify Docker volume exists
docker volume ls | grep whisper

# Check volume contents
docker run --rm -v whisper-models:/models alpine ls -la /models

# Pre-download model to volume (see Production Deployment section)
```

### Getting Help

If you encounter issues not covered here:

1. **Check Logs:**

   ```bash
   docker-compose logs -f transcription-api
   ```

2. **Review Documentation:**

   - [Troubleshooting Guide](TROUBLESHOOTING.md)
   - [Configuration Guide](CONFIGURATION.md)
   - [FAQ](FAQ.md)

3. **Verify Configuration:**

   ```bash
   # Validate .env file
   docker-compose config
   ```

4. **Check Service Health:**
   ```bash
   curl http://localhost:8000/health?detailed=true
   ```

## Next Steps

After successful installation:

1. **Read the Documentation:**

   - [API Reference](api-reference.md) - Complete endpoint documentation
   - [Configuration Guide](CONFIGURATION.md) - All configuration options
   - [Usage Examples](usage-examples.md) - Integration examples
   - [Architecture Documentation](architecture.md) - System design details

2. **Explore Features:**

   - Test different transcription formats (JSON, SRT, VTT, Text)
   - Try speaker diarization (`diarise=true`)
   - Test translation features
   - Explore async job processing

3. **Set Up Monitoring:**

   - Configure Grafana dashboards
   - Set up alerting rules
   - Monitor API metrics

4. **Production Readiness:**

   - Review security settings
   - Set up backup strategies
   - Configure log rotation
   - Plan scaling strategy

5. **Development:**
   - Explore the test suite
   - Check out the codebase structure

---

**Need Help?** Check the [FAQ](FAQ.md) or [Troubleshooting Guide](TROUBLESHOOTING.md) for common questions and solutions.
