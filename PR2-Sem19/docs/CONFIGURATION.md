# Configuration Guide

Complete reference for all configuration options available in the YouTube Transcription API.

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Environment Variables](#environment-variables)
- [API Configuration](#api-configuration)
- [Security Settings](#security-settings)
- [Whisper Model Configuration](#whisper-model-configuration)
- [Redis Configuration](#redis-configuration)
- [Storage Configuration](#storage-configuration)
- [Queue Configuration](#queue-configuration)
- [Worker Configuration](#worker-configuration)
- [Observability Configuration](#observability-configuration)
- [Advanced Settings](#advanced-settings)

## Configuration Overview

Configuration is managed through environment variables, loaded from a `.env` file or system environment. The application uses Pydantic Settings (BaseSettings) for type-safe configuration management with automatic validation.

### Configuration Loading Order

1. Environment variables from system (highest priority)
2. Variables from `.env` file in project root
3. Default values defined in code (lowest priority)

### Configuration File Location

The application looks for `.env` file in the project root directory. In Docker, the `.env` file should be mounted or environment variables should be set in Docker Compose.

### Configuration File

Copy `env.example` to `.env` and customize:

```bash
cp env.example .env
# Edit .env with your settings
```

**Note**: The `.env` file is automatically loaded by Pydantic Settings. No additional configuration needed. Environment variables take precedence over `.env` file values.

### Configuration Validation

The application validates configuration on startup:
- Production mode requires API keys and restricted CORS
- Development mode allows relaxed security (with warnings)
- Missing required settings raise errors in production

## Environment Variables

### API Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `API_TITLE` | string | `YouTube Transcription API` | API title for OpenAPI docs |
| `API_VERSION` | string | `v1` | API version string |
| `API_PREFIX` | string | `/v1` | API URL prefix |

### Security & Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `API_KEYS` | string | `""` | **REQUIRED (production)**: Comma-separated list of valid API keys. Multiple keys separated by commas. |
| `SECRET_KEY` | string | `""` | **REQUIRED (production)**: Secret key for JWT token signing (32+ chars recommended). Generate with: `python scripts/generate_secret_key.py` |
| `CORS_ORIGINS` | string | `*` | Comma-separated list of allowed CORS origins. Use `*` for all (dev only, not recommended for production). Examples: `https://example.com,https://app.example.com` |
| `STRICT_CORS_CHECK` | boolean | `false` | If `true`, raise error if CORS is `*` in production. Helps enforce security in production deployments. |
| `DEV_MODE` | boolean | `false` | Enable development mode (allows requests without API keys). Set via `DEV_MODE` environment variable. Not recommended for production. |
| `RATE_LIMIT_PER_MINUTE` | integer | `60` | Default rate limit per API key per minute. Rate limiting is enforced per API key (or IP address in dev mode). |

**Security Best Practices:**
- **API Keys**: Generate strong API keys using `python scripts/generate_api_key.py` or `make api-key`
- **Secret Key**: Generate secret key using `python scripts/generate_secret_key.py` (32+ characters recommended)
- **CORS**: In production, set specific CORS origins: `CORS_ORIGINS=https://example.com,https://app.example.com`. Never use `*` in production.
- **Environment Files**: Never commit `.env` file to version control. Use `.env.example` as a template.
- **Redis Password**: Always set a strong password in production: `REDIS_PASSWORD=<strong-password>`
- **S3 Credentials**: Store S3 credentials securely (use secrets management in production)
- **Rate Limiting**: Adjust `RATE_LIMIT_PER_MINUTE` based on your usage patterns and server capacity

## Whisper Model Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WHISPER_MODEL` | string | `openai/whisper-base` | Hugging Face Whisper model ID. Options: `openai/whisper-base`, `openai/whisper-small`, `openai/whisper-medium`, `openai/whisper-large-v3` |
| `WHISPER_MODEL_PATH` | string | `""` | Local path to pre-downloaded model. If set, loads from path instead of downloading |
| `WHISPER_DEVICE` | string | `cpu` | Compute device: `cpu`, `cuda` (GPU), `mps` (Mac Metal) |
| `WHISPER_COMPUTE_TYPE` | string | `float32` | Precision: `float32` (CPU), `float16` (GPU), `int8` (quantized) |

**Model Selection Guide:**
- `openai/whisper-base`: Fastest, lower accuracy (149M parameters). Good for quick transcriptions, less accurate for complex audio.
- `openai/whisper-small`: Balanced speed/accuracy (244M parameters). Recommended for most use cases.
- `openai/whisper-medium`: Better accuracy, slower (769M parameters). Good for high-quality requirements.
- `openai/whisper-large-v3`: Best accuracy, slowest (1550M parameters). Use for highest quality requirements, requires significant GPU memory.

**Model Path Configuration:**
- If `WHISPER_MODEL_PATH` is set, the model is loaded from the local path instead of downloading from Hugging Face.
- For Docker: Use `/app/models/whisper` (container path) - models are stored in Docker volumes.
- For local development: Use `./models/whisper` or any local path.
- If `WHISPER_MODEL_PATH` is empty, the model specified in `WHISPER_MODEL` is downloaded from Hugging Face on first use.

**Device Configuration:**
- `cpu`: Works everywhere, slower processing. No GPU required. Use `float32` compute type.
- `cuda`: Requires NVIDIA GPU with CUDA support, 10x+ faster. Use `float16` compute type for best performance.
- `mps`: Apple Silicon (M1/M2/M3), faster than CPU. Use `float32` compute type.

**Compute Type Selection:**
- `float32`: Full precision, works on all devices. Slower but most accurate.
- `float16`: Half precision, requires GPU (CUDA). Faster, slightly less accurate. Recommended for GPU.
- `int8`: Quantized, requires GPU. Fastest but lower accuracy. Use for speed-critical applications.

## Processing Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ASYNC_THRESHOLD_SECONDS` | integer | `300` | Videos longer than this (5 min) trigger async processing |
| `MAX_VIDEO_DURATION_SECONDS` | integer | `3600` | Maximum video duration (1 hour). Longer videos rejected |
| `YT_DLP_TIMEOUT` | integer | `300` | yt-dlp download timeout in seconds (5 minutes) |
| `TEMP_AUDIO_DIR` | string | `./temp_audio` | Directory for temporary audio files |
| `TEMP_STORE_DIR` | string | `./results` | Directory for storing full job results (JSON files). Results organized by date: `results/YYYY-MM-DD/{job_id}.json` |
| `JOB_TTL_SECONDS` | integer | `3600` | Job results time-to-live (1 hour). Completed job results are kept for this duration before cleanup. |
| `MEDIA_DOWNLOAD_TIMEOUT_SECONDS` | integer | `300` | Timeout for media download requests in seconds (5 minutes). Applies to remote media URL downloads. |

## Redis Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_ENABLED` | boolean | `true` | Enable Redis for persistent job storage |
| `REDIS_HOST` | string | `localhost` | Redis server hostname |
| `REDIS_PORT` | integer | `6379` | Redis server port |
| `REDIS_DB` | integer | `0` | Redis database number |
| `REDIS_PASSWORD` | string | `""` | Redis password (empty string for no password). **Recommended**: Set a strong password in production. |
| `REDIS_SOCKET_TIMEOUT` | float | `5.0` | Redis socket timeout in seconds |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | float | `5.0` | Redis connection timeout in seconds |
| `REDIS_POOL_MAX_CONNECTIONS` | integer | `50` | Maximum connections in Redis pool |
| `REDIS_SCAN_COUNT` | integer | `500` | Keys to scan per iteration in SCAN operations |
| `JOB_LIST_CACHE_TTL` | integer | `10` | Time-to-live for job list cache in seconds |
| `REDIS_KEY_PREFIX` | string | `job:` | Prefix for Redis keys |

**Redis Best Practices:**
- Always set a password in production
- Use connection pooling (configured automatically)
- Monitor connection pool usage via health endpoint
- Use Redis persistence (AOF enabled in Docker Compose)

## Storage Configuration

### S3 Storage (Level 3)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `S3_ENABLED` | boolean | `false` | Enable S3-compatible storage |
| `S3_BUCKET_NAME` | string | `""` | **REQUIRED if S3_ENABLED**: S3 bucket name |
| `S3_REGION` | string | `us-east-1` | S3 region |
| `S3_ACCESS_KEY_ID` | string | `""` | **REQUIRED if S3_ENABLED**: S3 access key ID |
| `S3_SECRET_ACCESS_KEY` | string | `""` | **REQUIRED if S3_ENABLED**: S3 secret access key |
| `S3_ENDPOINT_URL` | string | `""` | S3 endpoint URL (empty for AWS S3, set for MinIO/R2) |
| `S3_MEDIA_PREFIX` | string | `media/` | S3 prefix for uploaded media files |
| `S3_RESULTS_PREFIX` | string | `results/` | S3 prefix for transcription results |
| `S3_MULTIPART_THRESHOLD_MB` | integer | `100` | File size threshold for multipart uploads (MB) |
| `S3_MULTIPART_CHUNK_SIZE_MB` | integer | `10` | Chunk size for multipart uploads (MB) |

**S3 Configuration Examples:**

```bash
# AWS S3
S3_ENABLED=true
S3_BUCKET_NAME=my-transcription-bucket
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
S3_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
S3_ENDPOINT_URL=  # Leave empty for AWS

# MinIO (local testing)
S3_ENABLED=true
S3_BUCKET_NAME=transcription-storage
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin

# Cloudflare R2
S3_ENABLED=true
S3_BUCKET_NAME=my-bucket
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=your-r2-access-key
S3_SECRET_ACCESS_KEY=your-r2-secret-key
```

### File Storage

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_FILE_SIZE_MB` | integer | `500` | Maximum file size for uploads (MB) |
| `ALLOWED_AUDIO_FORMATS` | string | `mp3,wav,m4a,flac,ogg` | Comma-separated allowed audio formats |
| `ALLOWED_VIDEO_FORMATS` | string | `mp4,mkv,avi,mov,webm` | Comma-separated allowed video formats |
| `DEFAULT_FILE_EXTENSION` | string | `mp4` | Default extension when cannot be determined |
| `TEMP_UPLOADS_DIR` | string | `./temp_uploads` | Directory for uploaded files |
| `TEMP_DOWNLOADS_DIR` | string | `./temp_downloads` | Directory for downloaded remote files. Cleaned up after processing. |
| `DOWNLOAD_CHUNK_SIZE` | integer | `8192` | Chunk size in bytes for streaming downloads (8KB). Used for streaming large job results. |
| `RESULT_FILE_EXTENSION` | string | `json` | File extension for result files stored on disk. |

## Queue Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `QUEUE_BACKEND` | string | `redis` | Queue backend: `redis` (Redis Queue) or `sqs` (AWS SQS). Currently only `redis` is fully implemented. |
| `QUEUE_NAME` | string | `transcription_jobs` | Queue name for job processing |
| `QUEUE_MAX_RETRIES` | integer | `3` | Maximum retry attempts for failed jobs |
| `QUEUE_RETRY_DELAY_SECONDS` | integer | `60` | Initial delay before retrying failed job |
| `QUEUE_VISIBILITY_TIMEOUT_SECONDS` | integer | `300` | Visibility timeout for jobs in queue (5 minutes) |
| `QUEUE_MAX_JOB_TIME_SECONDS` | integer | `3600` | Maximum time a job can run before considered failed (1 hour) |

## Worker Configuration (Level 3)

### RunPod Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RUNPOD_API_KEY` | string | `""` | **REQUIRED for GPU workers**: RunPod API key |
| `RUNPOD_TEMPLATE_ID` | string | `""` | **REQUIRED for GPU workers**: RunPod template ID |
| `RUNPOD_API_URL` | string | `https://api.runpod.io/graphql` | RunPod GraphQL API URL |

### Worker Scaling

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_WORKERS` | integer | `5` | Maximum number of concurrent GPU workers |
| `MIN_WORKERS` | integer | `0` | Minimum number of GPU workers to keep running |
| `WORKER_IDLE_TIMEOUT_SECONDS` | integer | `300` | Idle timeout before shutting down worker (5 minutes) |
| `WORKER_HEARTBEAT_INTERVAL_SECONDS` | integer | `30` | Interval for worker heartbeat checks |
| `WORKER_HEALTH_CHECK_TIMEOUT_SECONDS` | integer | `120` | Timeout before marking worker as unhealthy |
| `WORKER_WARMUP_TIME_SECONDS` | integer | `60` | Time for worker to warm up (load model) |

### Auto-scaling

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WORKER_AUTO_SCALING_ENABLED` | boolean | `true` | Enable automatic worker scaling based on queue depth. When enabled, workers are automatically created/terminated based on job queue depth. |
| `WORKER_SCALE_UP_QUEUE_DEPTH` | integer | `10` | Queue depth threshold to trigger scale-up (add worker). When pending jobs exceed this, a new worker is created (up to `MAX_WORKERS`). |
| `WORKER_SCALE_DOWN_QUEUE_DEPTH` | integer | `2` | Queue depth threshold to trigger scale-down (remove worker). When pending jobs fall below this, idle workers are terminated (down to `MIN_WORKERS`). |
| `WORKER_AUTO_SCALING_INTERVAL_SECONDS` | integer | `60` | Interval in seconds for auto-scaling checks. The system checks queue depth and scales workers at this interval. |
| `AUTO_SCALING_ENABLED` | boolean | `true` | Enable automatic worker scaling (alias for `WORKER_AUTO_SCALING_ENABLED`). |
| `SCALE_UP_THRESHOLD` | integer | `10` | Queue depth threshold to trigger scale-up (alias for `WORKER_SCALE_UP_QUEUE_DEPTH`). |
| `SCALE_DOWN_THRESHOLD` | integer | `2` | Queue depth threshold to trigger scale-down (alias for `WORKER_SCALE_DOWN_QUEUE_DEPTH`). |
| `SCALE_COOLDOWN_SECONDS` | integer | `300` | Cooldown period in seconds between scaling operations (5 minutes). Prevents rapid scaling up/down. |

## Observability Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OBSERVABILITY_ENABLED` | boolean | `true` | Enable structured logging and metrics |
| `LOG_FORMAT` | string | `json` | Log format: `json` (structured) or `text` |
| `LOG_LEVEL` | string | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `METRICS_ENABLED` | boolean | `true` | Enable Prometheus metrics collection |
| `METRICS_PORT` | integer | `9090` | Port for Prometheus metrics endpoint. Note: Metrics are exposed on the main API port at `/v1/metrics`, not on a separate port. This setting may be used for future metrics server separation. |
| `TRACING_ENABLED` | boolean | `false` | Enable distributed tracing (OpenTelemetry) |
| `TRACING_ENDPOINT` | string | `""` | OpenTelemetry collector endpoint URL |

## Webhook Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WEBHOOK_TIMEOUT_SECONDS` | integer | `10` | Timeout for webhook callback requests |
| `WEBHOOK_MAX_RETRIES` | integer | `3` | Maximum retry attempts for failed webhooks |
| `WEBHOOK_RETRY_BACKOFF_BASE` | float | `1.0` | Base delay for exponential backoff (seconds) |
| `WEBHOOK_CONNECT_TIMEOUT` | float | `5.0` | Connection timeout for webhook requests |
| `WEBHOOK_WRITE_TIMEOUT` | float | `5.0` | Write timeout for webhook requests |
| `WEBHOOK_POOL_TIMEOUT` | float | `5.0` | Connection pool timeout |
| `WEBHOOK_USER_AGENT` | string | `TranscriptionService/1.0` | User-Agent string for webhook requests |

## Cache Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CACHE_MAX_SIZE` | integer | `1000` | Maximum entries in captions cache. When reached, oldest entries are evicted (LRU). |
| `CACHE_TTL_SECONDS` | integer | `300` | Time-to-live for captions cache (5 minutes). Cached captions expire after this duration. |
| `VIDEO_ID_CACHE_MAX_SIZE` | integer | `5000` | Maximum entries in video ID cache. Used to cache video metadata lookups. |
| `VIDEO_ID_CACHE_TTL_SECONDS` | integer | `3600` | Time-to-live for video ID cache (1 hour). Cached video IDs expire after this duration. |
| `CACHE_WARNING_THRESHOLD` | float | `0.8` | Cache size warning threshold (0.0-1.0). Warns when cache reaches this percentage of max size (default: 80%). |
| `JOB_LIST_CACHE_TTL` | integer | `10` | Time-to-live for job list cache in seconds. Caches job list results to reduce Redis load. |

## Cost Control Configuration (Level 3)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `COST_CONTROL_ENABLED` | boolean | `true` | Enable cost control features |
| `MAX_BUDGET_USD` | float | `100.0` | Maximum budget in USD before rejecting jobs |
| `GPU_COST_PER_HOUR` | float | `0.50` | Cost per GPU hour in USD |
| `COST_TRACKING_WINDOW_DAYS` | integer | `30` | Number of days to track costs |
| `BUDGET_ALERT_THRESHOLD` | float | `0.8` | Alert threshold as fraction of max_budget (0.0-1.0) |

## Advanced Settings

### Language Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PREFERRED_LANGUAGES` | string | `en,es,fr,de,it,pt,ru` | Preferred languages for YouTube captions (ISO 639-1) |
| `COMMON_LANGUAGES` | string | `en,es,fr,de,it,pt,ru,ja,ko,zh-Hans,zh-Hant` | Common languages for fallback |
| `YOUTUBE_API_TIMEOUT` | integer | `30` | Timeout for YouTube Transcript API requests |

### Validation Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_URL_LENGTH` | integer | `2048` | Maximum URL length in characters. Applies to video URLs, media URLs, and webhook URLs. |
| `MAX_URL_QUERY_LENGTH` | integer | `2000` | Maximum length of URL query parameters in characters. |
| `MAX_LANGUAGE_CODES` | integer | `10` | Maximum number of language codes in a single request. |
| `MIN_LANGUAGE_CODE_LENGTH` | integer | `2` | Minimum length for language codes (ISO 639-1 standard). |
| `MAX_LANGUAGE_CODE_LENGTH` | integer | `5` | Maximum length for language codes (supports variants like `zh-Hans`). |
| `YOUTUBE_VIDEO_ID_LENGTH` | integer | `11` | YouTube video ID length (YouTube standard is exactly 11 characters). |
| `MAX_TRANSLATE_TO_LENGTH` | integer | `10` | Maximum length for `translateTo` form field (ISO 639-1 codes are 2-3 chars, allows buffer). |
| `MAX_FORMAT_LENGTH` | integer | `10` | Maximum length for `format` form field (format names are short). |
| `MAX_DIARISE_LENGTH` | integer | `5` | Maximum length for `diarise` form field (`"true"` or `"false"`). |
| `MAX_FILE_EXTENSION_LENGTH` | integer | `10` | Maximum length of file extension in characters. |
| `MAX_SEGMENT_TEXT_LENGTH` | integer | `10000` | Maximum text length per transcript segment in bytes. |
| `MIN_TEXT_LENGTH_FOR_DETECTION` | integer | `10` | Minimum text length in characters required for language detection. |
| `MAX_LANGUAGES_DISPLAY` | integer | `10` | Maximum number of languages to display in logs/errors before truncating. |

### Whisper Confidence Calculation

These settings control how confidence scores are calculated for ASR transcriptions. Confidence scores range from 0.0 to 1.0 and are based on multiple factors.

**Segment Density Settings:**
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WHISPER_SEGMENT_DENSITY_OPTIMAL_MIN` | float | `2.0` | Minimum optimal segment density (segments per second) for confidence calculation. |
| `WHISPER_SEGMENT_DENSITY_OPTIMAL_MAX` | float | `5.0` | Maximum optimal segment density (segments per second) for confidence calculation. |
| `WHISPER_SEGMENT_DENSITY_MAX` | float | `10.0` | Maximum segment density before confidence penalty is applied. |
| `WHISPER_DENSITY_PENALTY_DIVISOR` | float | `20.0` | Divisor for density penalty calculation when density exceeds max. |
| `WHISPER_DENSITY_INTERPOLATION_MULTIPLIER` | float | `0.5` | Multiplier for density interpolation when density is below optimal min. |
| `WHISPER_DENSITY_INTERPOLATION_FACTOR` | float | `0.1` | Factor for density interpolation when density is between optimal_max and max. |

**Gap Score Settings:**
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WHISPER_GAP_SCORE_SMALL` | float | `2.0` | Small gap threshold in seconds for gap score calculation. |
| `WHISPER_GAP_SCORE_MEDIUM` | float | `5.0` | Medium gap threshold in seconds for gap score calculation. |
| `WHISPER_GAP_SCORE_LARGE` | float | `10.0` | Large gap threshold in seconds for gap score calculation. |
| `WHISPER_GAP_SCORE_SINGLE_SEGMENT` | float | `0.9` | Gap score for single segment (can't assess gaps). |
| `WHISPER_GAP_SCORE_MEDIUM_VALUE` | float | `0.8` | Gap score for medium gaps (between small and medium threshold). |
| `WHISPER_GAP_SCORE_LARGE_VALUE` | float | `0.6` | Gap score for large gaps (between medium and large threshold). |
| `WHISPER_GAP_SCORE_VERY_LARGE` | float | `0.4` | Gap score for very large gaps (above large threshold). |

**Word Length Settings:**
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WHISPER_WORD_LENGTH_OPTIMAL_MIN` | float | `3.0` | Minimum optimal word length for confidence calculation. |
| `WHISPER_WORD_LENGTH_OPTIMAL_MAX` | float | `6.0` | Maximum optimal word length for confidence calculation. |
| `WHISPER_WORD_LENGTH_SHORT` | float | `2.0` | Short word length threshold for confidence calculation. |
| `WHISPER_WORD_LENGTH_LONG` | float | `10.0` | Long word length threshold for confidence calculation. |
| `WHISPER_WORD_LENGTH_SHORT_SCORE` | float | `0.5` | Confidence score for short words (below short threshold). |
| `WHISPER_WORD_LENGTH_MEDIUM_SCORE` | float | `0.8` | Confidence score for medium word length (between short and optimal). |
| `WHISPER_WORD_LENGTH_LONG_SCORE` | float | `0.7` | Confidence score for long words (above long threshold). |

**Confidence Weights:**
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WHISPER_CONFIDENCE_COVERAGE_WEIGHT` | float | `0.4` | Weight for coverage ratio in confidence calculation (40%). |
| `WHISPER_CONFIDENCE_DENSITY_WEIGHT` | float | `0.2` | Weight for density score in confidence calculation (20%). |
| `WHISPER_CONFIDENCE_TEXT_QUALITY_WEIGHT` | float | `0.2` | Weight for text quality metrics in confidence calculation (20%). |
| `WHISPER_CONFIDENCE_GAP_WEIGHT` | float | `0.2` | Weight for gap score in confidence calculation (20%). |

**Text Quality Weights:**
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WHISPER_TEXT_QUALITY_PUNCTUATION_WEIGHT` | float | `0.5` | Weight for punctuation ratio within text quality (50%). |
| `WHISPER_TEXT_QUALITY_CAPITALIZATION_WEIGHT` | float | `0.3` | Weight for capitalization ratio within text quality (30%). |
| `WHISPER_TEXT_QUALITY_WORD_LENGTH_WEIGHT` | float | `0.2` | Weight for word length score within text quality (20%). |

**Other Settings:**
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WHISPER_SEGMENT_END_OFFSET` | float | `0.1` | Offset in seconds to add to segment start when end is invalid. |
| `LOG_RESULT_SAMPLE_LENGTH` | integer | `500` | Maximum length of result sample to log for debugging (characters). |

## Configuration Examples

### Development Setup

```bash
# .env for local development
API_KEYS=dev-key-123
SECRET_KEY=dev-secret-key-change-in-production
CORS_ORIGINS=*
DEV_MODE=true
REDIS_ENABLED=true
REDIS_PASSWORD=dev-redis-password
WHISPER_DEVICE=cpu
WHISPER_MODEL=openai/whisper-base
```

### Production Setup

```bash
# .env for production
API_KEYS=prod-key-1,prod-key-2,prod-key-3
SECRET_KEY=<32+ character secret key>
CORS_ORIGINS=https://api.example.com,https://app.example.com
DEV_MODE=false
REDIS_ENABLED=true
REDIS_PASSWORD=<strong-password>
S3_ENABLED=true
S3_BUCKET_NAME=transcription-prod
S3_ACCESS_KEY_ID=<aws-access-key>
S3_SECRET_ACCESS_KEY=<aws-secret-key>
WHISPER_DEVICE=cuda
WHISPER_MODEL=openai/whisper-medium
OBSERVABILITY_ENABLED=true
METRICS_ENABLED=true
LOG_FORMAT=json
LOG_LEVEL=INFO
```

### GPU-Enabled Setup

```bash
# .env for GPU workers
# ... (all production settings above) ...
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
RUNPOD_API_KEY=<runpod-api-key>
RUNPOD_TEMPLATE_ID=<template-id>
WORKER_AUTO_SCALING_ENABLED=true
MAX_WORKERS=10
COST_CONTROL_ENABLED=true
MAX_BUDGET_USD=500.0
```

## Configuration Validation

The application validates configuration on startup:

1. **Production Mode Detection**: Production mode is enabled when:
   - `DEV_MODE` environment variable is not `"true"` (case-insensitive)
   - AND `API_KEYS` are configured (non-empty)
   
   If either condition is false, development mode is enabled.

2. **Production Mode Validation**: When in production mode:
   - API keys must be configured (non-empty `API_KEYS`)
   - If `STRICT_CORS_CHECK=true`, CORS origins must be restricted (not `*`)
   - Validation errors raise `ValueError` exceptions on startup

3. **Security Warnings**: Development mode logs warnings for:
   - Missing API keys
   - CORS set to `*` (all origins allowed)
   - Missing secret key

4. **Configuration Methods**: The Settings class provides helper methods:
   - `get_api_keys()`: Parses comma-separated API keys into a list
   - `get_cors_origins()`: Parses and validates CORS origins
   - `get_allowed_audio_formats()`: Parses allowed audio formats
   - `get_allowed_video_formats()`: Parses allowed video formats
   - `get_preferred_languages()`: Parses preferred language codes
   - `get_common_languages()`: Parses common language codes
   - `is_production()`: Checks if running in production mode
   - `validate_production_settings()`: Validates production configuration

## Environment-Specific Configuration

### Docker

In Docker, environment variables are loaded from `.env` file or Docker Compose environment section. Volume mounts handle model storage and temporary files.

### Kubernetes

Use ConfigMaps and Secrets for configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: transcription-config
data:
  API_VERSION: "v1"
  REDIS_HOST: "redis-service"
  # ... other non-sensitive config
---
apiVersion: v1
kind: Secret
metadata:
  name: transcription-secrets
type: Opaque
stringData:
  API_KEYS: "key1,key2"
  SECRET_KEY: "secret-key"
  REDIS_PASSWORD: "redis-password"
```

See [Infrastructure Documentation](../infrastructure/README.md) for Kubernetes setup.

## Configuration Tips

### Performance Tuning

1. **Whisper Model**: Use `whisper-small` or `whisper-medium` for balanced performance. `whisper-large-v3` requires significant GPU memory.
2. **Device**: Use `cuda` with `float16` for best GPU performance. Use `cpu` only if GPU unavailable.
3. **Redis Pool**: Increase `REDIS_POOL_MAX_CONNECTIONS` if you have high concurrent request volume.
4. **Cache**: Increase `CACHE_MAX_SIZE` if you frequently transcribe the same videos.
5. **Rate Limiting**: Adjust `RATE_LIMIT_PER_MINUTE` based on your server capacity and usage patterns.

### Production Checklist

- [ ] Set `API_KEYS` with strong, unique keys
- [ ] Set `SECRET_KEY` (32+ characters)
- [ ] Configure `CORS_ORIGINS` with specific domains (not `*`)
- [ ] Set `DEV_MODE=false` or unset `DEV_MODE` environment variable
- [ ] Configure `REDIS_PASSWORD` with strong password
- [ ] Enable `S3_ENABLED=true` if using Level 3 features
- [ ] Set `OBSERVABILITY_ENABLED=true` and `METRICS_ENABLED=true` for monitoring
- [ ] Configure `LOG_FORMAT=json` for structured logging
- [ ] Set appropriate `MAX_WORKERS` and `MIN_WORKERS` for your workload
- [ ] Enable `COST_CONTROL_ENABLED=true` and set `MAX_BUDGET_USD` for GPU workers

## Next Steps

- Review [API Reference](api-reference.md) for endpoint usage
- Check [Usage Examples](usage-examples.md) for integration patterns
- See [Troubleshooting](TROUBLESHOOTING.md) for configuration issues
- Review [Architecture Documentation](architecture.md) for system design details
