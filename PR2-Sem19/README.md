# Transcriber API

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/badge/linter-ruff-yellow.svg)](https://github.com/astral-sh/ruff)

A production-ready FastAPI service for transcribing YouTube videos and media files with automatic speech recognition (ASR) capabilities. Features an intelligent two-path transcription strategy that automatically selects the optimal method based on video availability and requirements.

**Key Highlights:**

- **Fast Path**: Uses existing YouTube captions when available (milliseconds response time)
- **Smart Fallback**: Automatically switches to Whisper ASR when captions unavailable
- **Scalable**: Supports synchronous (< 5 min) and asynchronous (5-60 min) processing
- **Production-Ready**: Includes auto-scaling, monitoring, and cost control

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage Examples](#usage-examples)
- [Documentation](#documentation)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

### Core Capabilities

- **YouTube Video Transcription** - Extract transcripts from YouTube videos using captions or ASR
- **Media File Support** - Upload and transcribe audio/video files (mp3, wav, m4a, mp4, mkv, etc.)
- **Multi-language Support** - Automatic language detection and translation to 100+ languages (ISO 639-1)
- **Multiple Output Formats** - JSON (with metadata), Text (plain), SRT, VTT subtitle formats
- **Interactive API Documentation** - Auto-generated OpenAPI docs at `/docs` (Swagger UI) and `/redoc` (ReDoc). See [API Reference](docs/api-reference.md) for details.

### Production Features

- **Async Processing** - Background job processing for videos 5-60 minutes (returns job ID for polling)
- **Auto-scaling** - Automatic GPU worker scaling based on queue depth (Level 3)
- **Observability** - Prometheus metrics at `/v1/metrics`, structured logging, Grafana dashboards
- **Health Monitoring** - Health check endpoints at `/` and `/health` for load balancers
- **Security** - API key authentication (Bearer token), rate limiting (60 req/min default), CORS protection
- **Storage** - [Redis](docs/installation.md#step-5-start-redis-required-for-job-management) for job persistence (see [Configuration](docs/configuration.md#redis-configuration)), S3-compatible storage for media files (Level 3)
- **Webhooks** - Optional callback URLs for async job completion notifications

## Architecture

### Two-Path Transcription Strategy

The service implements an intelligent **two-path transcription strategy** that automatically selects the optimal method:

- **Path A (Fast-path)**: Uses existing YouTube captions when available

  - **Response time**: Milliseconds (no processing needed)
  - **Cost**: Free (no GPU required)
  - **When used**: Captions available and no diarization requested
  - **Fallback**: Automatically switches to Path B if captions unavailable

- **Path B (ASR Fallback)**: Uses OpenAI Whisper model for automatic speech recognition
  - **Response time**: Seconds to minutes (depends on video length)
  - **Cost**: GPU compute (if using GPU workers)
  - **When used**:
    - Captions unavailable or disabled
    - Speaker diarization requested (`diarise=true`)
    - Translation to non-English languages (Whisper limitation: only translates to English)

### Processing Modes

Based on video duration, the API automatically selects the processing mode:

- **Synchronous** (< 5 minutes): Returns transcription result immediately
- **Asynchronous** (5-60 minutes): Returns job ID, poll `/v1/jobs/{job_id}` for results
- **Rejected** (> 60 minutes): Returns `VIDEO_TOO_LONG` error (configurable via `MAX_VIDEO_DURATION_SECONDS`)

### Architecture Levels

The service is designed with three progressive levels of functionality:

- **Level 1 (Basic)**: YouTube captions extraction, synchronous processing, in-memory job storage
- **Level 2 (Advanced)**: ASR fallback, media uploads, speaker diarization, webhooks, [Redis persistence](docs/installation.md#step-5-start-redis-required-for-job-management)
- **Level 3 (Production)**: GPU workers, auto-scaling, S3 storage, observability, cost control

## Quick Start

### Prerequisites

- **Docker and Docker Compose** (recommended) or **Python 3.11+** (for local development)
- **Redis** (required for job persistence; included in Docker Compose)

### Docker Setup (Recommended)

```bash
# 1. Clone the repository
git clone <repository-url>
cd transcription

# 2. Configure environment
cp env.example .env

# 3. Generate API keys and secret key
python scripts/generate_api_key.py
python scripts/generate_secret_key.py

# 4. Edit .env file - add generated keys:
# API_KEYS=your-generated-api-key-here
# SECRET_KEY=your-generated-secret-key-here
# REDIS_PASSWORD=your-secure-password-here

# 5. Start all services (API, Redis, MinIO, Prometheus, Grafana)
docker-compose up -d

# 6. View logs
docker-compose logs -f transcription-api

# 7. Check health
curl http://localhost:8000/health
```

**Access Points:**

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **Redis UI**: http://localhost:8081 (default: `admin/admin`)
- **MinIO Console**: http://localhost:9001 (default: `minioadmin/minioadmin`)
- **Grafana**: http://localhost:3000 (default: `admin/admin`)

### Quick Test

```bash
# Replace YOUR_API_KEY with your actual API key from .env

# Test health endpoint
curl http://localhost:8000/health

# Test YouTube transcription
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  -F "format=json"
```

> **Note**: In development mode, API keys are optional. In production, API keys are required. See [Installation Guide](docs/INSTALLATION.md) for detailed setup instructions.

## Installation

### Docker (Recommended)

See [Quick Start](#quick-start) above for Docker setup commands. For detailed instructions, see [Installation Guide - Docker Setup](docs/installation.md#docker-setup).

### Local Development

```bash
# 1. Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# 2. Install dependencies
poetry install
poetry shell

# 3. Configure environment
cp env.example .env
python scripts/generate_api_key.py
python scripts/generate_secret_key.py
# Edit .env with generated keys

# 4. Download Whisper model
python scripts/download_whisper_model.py

# 5. Start Redis (required)
# Option A: Using Docker
docker run -d --name transcription-redis -p 6379:6379 \
  -e REDIS_PASSWORD=dev-redis-password-change-me \
  redis:7-alpine redis-server --appendonly yes --requirepass dev-redis-password-change-me

# Option B: Local installation
# macOS: brew install redis && brew services start redis
# Ubuntu: sudo apt-get install redis-server && sudo systemctl start redis-server

# 6. Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

For detailed local development setup, see [Installation Guide - Local Development](docs/installation.md#local-development-setup).

### Production Deployment

For production deployment instructions, see [Installation Guide - Production Deployment](docs/installation.md#production-deployment).

## Usage Examples

### Basic Transcription

```bash
# YouTube video (synchronous)
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=VIDEO_ID" \
  -F "format=json"

# Media file upload
curl -X POST "http://localhost:8000/v1/transcriptions/media" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@audio.mp3" \
  -F "format=srt"
```

### Async Job Processing

```bash
# Submit job (for videos > 5 minutes)
JOB_RESPONSE=$(curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=LONG_VIDEO_ID" \
  -F "format=json")

# Extract job ID and poll for results
JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')
curl -X GET "http://localhost:8000/v1/jobs/$JOB_ID" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

For comprehensive examples in Python, JavaScript, and cURL, see [Usage Examples](docs/usage-examples.md).

## Documentation

**📚 All detailed documentation is in the [`docs/`](docs/) folder.** Start with the [Documentation Overview](docs/OVERVIEW.md) for navigation.

### Quick Links

| Document                                       | Description                                             |
| ---------------------------------------------- | ------------------------------------------------------- |
| **[Installation Guide](docs/INSTALLATION.md)** | Complete setup instructions (local, Docker, production) |
| **[API Reference](docs/api-reference.md)**     | Detailed API endpoint documentation                     |
| **[Usage Examples](docs/usage-examples.md)**   | Code examples (Python, JavaScript, cURL)                |
| **[Configuration](docs/CONFIGURATION.md)**     | All environment variables and settings                  |
| **[Architecture](docs/architecture.md)**       | System design and architecture details                  |
| **[Features](docs/features.md)**               | Feature descriptions and implementation                 |
| **[Docker Infrastructure](docs/docker.md)**    | Docker setup and orchestration                          |
| **[Troubleshooting](docs/TROUBLESHOOTING.md)** | Common issues and solutions                             |
| **[FAQ](docs/FAQ.md)**                         | Frequently asked questions                              |

### Additional Resources

- **[Infrastructure Documentation](infrastructure/README.md)** - Kubernetes, Terraform, monitoring setup
- **[Test Documentation](tests/README.md)** - Testing guide, test coverage, and test examples

## Project Structure

```
transcription/
├── app/                    # Main application code
│   ├── api/               # API endpoints and routing
│   │   └── v1/
│   │       ├── endpoints/ # Route handlers
│   │       └── router.py
│   ├── core/              # Core functionality
│   │   ├── auth.py        # Authentication & rate limiting
│   │   ├── config.py      # Configuration management
│   │   ├── error_handlers.py
│   │   ├── middleware.py
│   │   └── startup.py
│   ├── models/            # Data models
│   │   ├── schemas.py     # Pydantic schemas
│   │   └── types.py
│   ├── services/          # Business logic services
│   │   ├── jobs/         # Job management and queue
│   │   ├── media/        # Media handling and storage
│   │   ├── transcription/ # Transcription services
│   │   └── infrastructure/ # Infrastructure services
│   └── utils/            # Utility functions
├── docs/                  # Documentation
├── infrastructure/        # Infrastructure as code
│   ├── kubernetes/       # K8s manifests
│   ├── terraform/        # Terraform configurations
│   ├── prometheus/       # Prometheus config
│   └── grafana/          # Grafana dashboards
├── tests/                # Test suite
├── workers/              # GPU worker implementation
├── scripts/              # Utility scripts
│   ├── generate_api_key.py
│   ├── generate_secret_key.py
│   └── download_whisper_model.py
├── docker-compose.yml    # Docker Compose configuration
├── docker-compose.dev.yml # Development Docker Compose
├── docker-compose.gpu.yml # GPU-enabled Docker Compose
├── Dockerfile            # Standard Docker image
├── Dockerfile.gpu        # GPU-enabled Docker image
├── env.example           # Environment variables template
├── pyproject.toml        # Poetry dependencies
├── LICENSE               # MIT License
└── CONTRIBUTING.md       # Contribution guidelines
```

## API Endpoints

### Core Endpoints

- `GET /` - API information and status
- `GET /health` - Detailed health check (model, [Redis](docs/configuration.md#redis-configuration) status)
- `POST /v1/transcriptions/youtube` - Transcribe YouTube video
- `POST /v1/transcriptions/media` - Transcribe uploaded media file or remote URL
- `GET /v1/jobs` - List all transcription jobs
- `GET /v1/jobs/{job_id}` - Get job status and result
- `DELETE /v1/jobs/{job_id}` - Delete job and results

### Monitoring Endpoints

- `GET /v1/metrics` - Prometheus metrics (no authentication)
- `GET /docs` - Interactive API documentation (Swagger UI) - Access at `http://localhost:8000/docs` when running locally
- `GET /redoc` - Alternative API documentation (ReDoc) - Access at `http://localhost:8000/redoc` when running locally

### Worker Management (Level 3)

- `POST /v1/workers/register` - Register GPU worker
- `POST /v1/workers/{worker_id}/heartbeat` - Worker heartbeat
- `GET /v1/workers` - List all workers
- `GET /v1/workers/{worker_id}` - Get worker information

For complete API reference, see [API Reference](docs/api-reference.md).

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- Development setup
- Code style and guidelines
- Testing requirements
- Pull request process
- Issue reporting

Quick start: Fork and clone the repository, set up development environment with Poetry, and run tests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:

- **Issues**: [GitHub Issues](https://github.com/your-username/transcription/issues)
- **Documentation**: See [`docs/`](docs/) directory
- **Infrastructure Docs**: See [`infrastructure/README.md`](infrastructure/README.md)
- **Test Docs**: See [`tests/README.md`](tests/README.md)

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework
- [OpenAI Whisper](https://github.com/openai/whisper) - State-of-the-art speech recognition
- [Hugging Face Transformers](https://huggingface.co/transformers/) - Model loading and inference
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) - YouTube captions extraction
