# Frequently Asked Questions (FAQ)

Common questions about the YouTube Transcription API, based on the actual implementation.

## Table of Contents

- [General Questions](#general-questions)
- [API Usage](#api-usage)
- [Configuration](#configuration)
- [Performance](#performance)
- [Features](#features)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Costs & Billing](#costs--billing)

## General Questions

### What is the YouTube Transcription API?

The YouTube Transcription API is a production-ready FastAPI service that provides transcription capabilities for YouTube videos and media files. It uses a two-path strategy:

- **Path A (Fast-path)**: Uses existing YouTube captions when available (milliseconds, no GPU needed)
- **Path B (ASR Fallback)**: Uses OpenAI Whisper model when captions unavailable (seconds to minutes, may require GPU)

The API automatically chooses the best path based on availability and request parameters.

### What are the main features?

- **YouTube video transcription** with automatic path selection
- **Media file upload and transcription** (audio/video files)
- **Multi-language support** (100+ languages via ISO 639-1)
- **Automatic language detection**
- **Translation to target languages** (Path A supports all languages, Path B only English)
- **Multiple output formats** (JSON, Text, SRT, VTT)
- **Speaker diarization** (forces Path B, ASR processing)
- **Async job processing** for videos 5-60 minutes
- **GPU worker auto-scaling** (Level 3)
- **Webhook callbacks** for async job completion
- **Prometheus metrics** and observability
- **Cost control** and budget limits (Level 3)

### What are the architecture levels?

- **Level 1 (Basic)**: YouTube captions extraction, synchronous processing, in-memory storage
- **Level 2 (Advanced)**: ASR fallback, media uploads, speaker diarization, webhooks, Redis storage
- **Level 3 (Production)**: GPU workers, auto-scaling, S3 storage, observability, cost control, queue management

### Is this free to use?

The API itself is open source (MIT License). However, you'll need to provide:

- **Compute resources**: CPU/GPU for ASR processing
- **Storage**: Redis (for job metadata), S3 or file system (for results)
- **Infrastructure costs**: If using cloud services (AWS, RunPod, etc.)

**GPU workers on RunPod** incur costs based on usage (typically $0.20-$2.00 per GPU hour depending on GPU type).

## API Usage

### How do I get an API key?

Generate one or more API keys using the provided script:

```bash
# Generate a single API key
python scripts/generate_api_key.py

# Generate multiple keys
python scripts/generate_api_key.py 3

# Or use the make command
make api-key
```

The script outputs URL-safe tokens (not hex-encoded). Add them to your `.env` file:

```bash
# Single key
API_KEYS=your-generated-key-here

# Multiple keys (comma-separated)
API_KEYS=key1,key2,key3
```

**Important**: In production, always configure API keys. In development, you can set `DEV_MODE=true` to allow requests without API keys (not recommended for production).

### How do I authenticate requests?

Include the API key in the `Authorization` header as a Bearer token:

```http
Authorization: Bearer YOUR_API_KEY
```

**Example with curl**:

```bash
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=VIDEO_ID"
```

**Example with Python**:

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_API_KEY"
}

response = requests.post(
    "http://localhost:8000/v1/transcriptions/youtube",
    headers=headers,
    files={"url": (None, "https://www.youtube.com/watch?v=VIDEO_ID")}
)
```

### What happens if I don't provide an API key?

- **Development mode** (`DEV_MODE=true`): Requests are allowed but logged with warnings
- **Production mode** (`DEV_MODE=false` or not set): Requests are rejected with `401 Unauthorized`

### What video formats are supported?

**YouTube Videos**: Any YouTube video URL is supported:
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
- Other YouTube URL formats

**Media Uploads**: Supported formats include:
- **Audio**: `mp3`, `wav`, `m4a`, `flac`, `ogg`
- **Video**: `mp4`, `mkv`, `avi`, `mov`, `webm`

Formats are configurable via `ALLOWED_AUDIO_FORMATS` and `ALLOWED_VIDEO_FORMATS` environment variables.

### What is the maximum video duration?

**Default**: 1 hour (3600 seconds). Videos longer than this are rejected with `VIDEO_TOO_LONG` error.

**Configurable**: Set `MAX_VIDEO_DURATION_SECONDS` in your `.env` file:

```bash
# Allow 2-hour videos (not recommended for production)
MAX_VIDEO_DURATION_SECONDS=7200
```

**Processing modes**:
- **< 5 minutes**: Synchronous processing (returns result immediately)
- **5-60 minutes**: Asynchronous processing (returns job ID for polling)
- **> 60 minutes**: Rejected (configurable limit)

### How long does transcription take?

Processing time depends on the path used and video length:

**Path A (YouTube Captions)**:
- **Typical**: 100-500ms (near-instant)
- **With translation**: 200-1000ms
- **Cached**: < 50ms

**Path B (ASR with Whisper)**:
- **Short videos (< 5 min, CPU)**: 30-120 seconds
- **Short videos (< 5 min, GPU)**: 5-20 seconds
- **Medium videos (5-30 min, CPU)**: 5-30 minutes
- **Medium videos (5-30 min, GPU)**: 1-5 minutes
- **Long videos (30-60 min, GPU)**: 5-15 minutes

**Factors affecting speed**:
- Model size (base < small < medium < large-v3)
- Compute device (GPU 10x+ faster than CPU)
- Video length (linear scaling)
- System resources (CPU, memory, disk I/O)

**Note**: These are estimates. Actual times vary based on hardware and video content.

### What languages are supported?

The API supports **100+ languages** for transcription and translation. Common languages include:

- **Major languages**: English, Spanish, French, German, Italian, Portuguese, Russian
- **Asian languages**: Japanese, Korean, Chinese (Simplified/Traditional), Hindi, Thai, Vietnamese
- **Middle Eastern**: Arabic, Hebrew, Turkish, Persian
- **European**: Polish, Dutch, Swedish, Norwegian, Danish, Finnish, Czech, Hungarian, Romanian, Ukrainian
- **And many more**: See the `Language` enum in the codebase for the complete list

**Translation support**:
- **Path A (Captions)**: Can translate to any language supported by YouTube's translation API
- **Path B (ASR)**: Can only translate to English (Whisper limitation)

### Can I translate transcripts?

Yes! Use the `translateTo` parameter:

```bash
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=VIDEO_ID" \
  -F "translateTo=en"
```

**Important limitations**:
- **Path A (Captions)**: Supports translation to any language available in YouTube's translation API
- **Path B (ASR)**: Only supports translation to English (`translateTo=en`). Other languages will return `TRANSLATION_NOT_SUPPORTED` error

The API automatically tries Path A first, which supports broader translation capabilities.

### What output formats are available?

- **JSON** (default): Full metadata with segments, timings, confidence scores, language, source
- **Text**: Plain text transcript only (no timestamps)
- **SRT**: SubRip subtitle format (`.srt` files)
- **VTT**: WebVTT subtitle format (`.vtt` files)

**Example request**:

```bash
# JSON format (default)
curl ... -F "format=json"

# Plain text
curl ... -F "format=text"

# SRT subtitles
curl ... -F "format=srt"

# VTT subtitles
curl ... -F "format=vtt"
```

### How do I handle async jobs?

**YouTube Endpoint**: For videos 5-60 minutes, the API returns a job ID instead of the result immediately.

**Media Endpoint**: All requests return a job ID (always asynchronous).

1. **Submit transcription request**:
   ```bash
   # YouTube endpoint
   curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -F "url=https://www.youtube.com/watch?v=VIDEO_ID"
   
   # Media endpoint (file upload)
   curl -X POST "http://localhost:8000/v1/transcriptions/media" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -F "file=@audio.mp3"
   ```

2. **Receive job ID in response**:
   ```json
   {
     "jobId": "123e4567-e89b-12d3-a456-426614174000",
     "status": "processing",
     "createdAt": "2024-01-15T10:30:00Z",
     "videoId": "dQw4w9WgXcQ"
   }
   ```
   
   **Note**: Media endpoint returns status `"processing"` (not `"queued"`) because file handling happens before returning the job ID.

3. **Poll job status**:
   ```bash
   curl -X GET "http://localhost:8000/v1/jobs/{job_id}" \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

4. **Retrieve result when status is "completed"**:
   ```json
   {
     "job_id": "...",
     "status": "completed",
     "result": {
       "transcript": "...",
       "segments": [...],
       "language": "en",
       "confidence": 0.95
     }
   }
   ```

**Or use webhooks** to receive results automatically (see below).

### What are webhooks?

Webhooks allow you to receive transcription results automatically when jobs complete. Provide a `webhookUrl` parameter:

```bash
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=VIDEO_ID" \
  -F "webhookUrl=https://your-server.com/webhook"
```

**When the job completes**, the API will:
1. POST the full transcription result to your webhook URL
2. Retry up to 3 times if the request fails (with exponential backoff)
3. Include timeout protection (default: 10 seconds)
4. Validate the URL (SSRF protection)

**Webhook payload**:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "transcript": "...",
  "segments": [...],
  "language": "en",
  "confidence": 0.95,
  "source": "asr"
}
```

## Configuration

### Do I need Redis?

**Recommended for production**: Yes. Redis is used for:
- Job metadata storage (status, timestamps, video IDs)
- Fast job lookups and status updates
- Queue management (Level 3)
- Cost tracking (Level 3)

**Without Redis**: Jobs are stored in-memory only and **lost on restart** (not recommended for production).

**Configuration**:
```bash
REDIS_ENABLED=true
REDIS_HOST=localhost  # or redis (Docker)
REDIS_PORT=6379
REDIS_PASSWORD=your-secure-password
```

**Docker Compose**: Redis is included in `docker-compose.yml` and `docker-compose.dev.yml`.

### Do I need S3 storage?

**Optional but recommended for production**. S3 storage is used for:
- Storing uploaded media files
- Storing transcription results (long-term persistence)
- Enabling GPU worker access to media files (Level 3)

**Without S3**: Results are stored in the local file system (`./results` by default).

**Configuration**:
```bash
S3_ENABLED=true
S3_BUCKET_NAME=transcription-storage
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
# For AWS S3, leave S3_ENDPOINT_URL empty
# For S3-compatible (MinIO, Cloudflare R2), set endpoint:
S3_ENDPOINT_URL=http://minio:9000  # MinIO (Docker)
```

**Local Development**: Use MinIO (included in Docker Compose):
```bash
# Access MinIO Console: http://localhost:9001
# Create bucket: Use MinIO console to create bucket named S3_BUCKET_NAME
```

### What Whisper model should I use?

Choose based on your accuracy vs speed requirements:

| Model | Parameters | Speed | Accuracy | Use Case |
|-------|-----------|-------|----------|----------|
| `whisper-base` | 149M | Fastest | Lower | Development, low-volume production |
| `whisper-small` | 244M | Fast | Good | Production (recommended) |
| `whisper-medium` | 769M | Medium | Better | High-accuracy requirements |
| `whisper-large-v3` | 1550M | Slowest | Best | Maximum quality, research |

**Configuration**:
```bash
WHISPER_MODEL=openai/whisper-base  # or small, medium, large-v3
```

**Memory requirements**:
- `whisper-base`: ~1GB GPU memory
- `whisper-small`: ~2GB GPU memory
- `whisper-medium`: ~5GB GPU memory
- `whisper-large-v3`: ~10GB GPU memory

### Do I need a GPU?

**Not required**, but **highly recommended for production**:

- **CPU**: Works fine for development and low-volume production (10x+ slower than GPU)
- **GPU**: Recommended for production (10x+ faster, better throughput)

**Configuration**:
```bash
# CPU (default)
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=float32

# GPU (NVIDIA)
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

# Apple Silicon (Mac)
WHISPER_DEVICE=mps
WHISPER_COMPUTE_TYPE=float16
```

**Performance comparison** (approximate):
- **5-minute video, CPU**: 60-120 seconds
- **5-minute video, GPU**: 5-15 seconds
- **30-minute video, CPU**: 15-30 minutes
- **30-minute video, GPU**: 2-5 minutes

### How do I configure GPU workers?

GPU workers (Level 3) enable distributed processing and auto-scaling:

1. **Get RunPod API key**: https://www.runpod.io/console/user/settings

2. **Create RunPod template**:
   - Build your worker Docker image
   - Create a template in RunPod console
   - Note the template ID

3. **Configure in `.env`**:
   ```bash
   RUNPOD_API_KEY=your-runpod-api-key
   RUNPOD_TEMPLATE_ID=your-template-id
   WORKER_AUTO_SCALING_ENABLED=true
   MAX_WORKERS=5
   MIN_WORKERS=0
   WORKER_SCALE_UP_QUEUE_DEPTH=10
   WORKER_SCALE_DOWN_QUEUE_DEPTH=2
   ```

4. **Test connection**:
   ```bash
   python scripts/test_runpod_connection.py
   # Or via API: GET /v1/workers/test-connection
   ```

**Auto-scaling behavior**:
- **Scale up**: When queue depth > `WORKER_SCALE_UP_QUEUE_DEPTH` (default: 10)
- **Scale down**: When queue depth < `WORKER_SCALE_DOWN_QUEUE_DEPTH` (default: 2) and worker idle > `WORKER_IDLE_TIMEOUT_SECONDS` (default: 300s)

## Performance

### How can I improve transcription speed?

1. **Use GPU**:**
   ```bash
   WHISPER_DEVICE=cuda
   WHISPER_COMPUTE_TYPE=float16
   ```

2. **Use smaller model**:
   ```bash
   WHISPER_MODEL=openai/whisper-base  # Fastest
   ```

3. **Enable caching** (Path A only):
   ```bash
   CACHE_MAX_SIZE=5000  # Increase cache size
   CACHE_TTL_SECONDS=600  # Increase cache TTL
   ```

4. **Use Path A (captions)** when available (much faster than ASR)

5. **Use GPU workers** (Level 3) for parallel processing

6. **Pre-load model** at startup (enabled by default):
   ```python
   # Already enabled in app/core/startup.py
   ```

### How much memory do I need?

**System memory**:
- **Minimum**: 4GB
- **Recommended**: 8GB+
- **Production**: 16GB+

**GPU memory** (if using GPU):
- **whisper-base**: 1-2GB
- **whisper-small**: 2-4GB
- **whisper-medium**: 5-8GB
- **whisper-large-v3**: 10GB+

**Redis memory**:
- **Minimal**: ~100MB for job metadata
- **Production**: 1-2GB depending on job volume

**Disk space**:
- **Model storage**: 1-10GB depending on model
- **Temporary audio**: ~100MB per video (cleaned up after processing)
- **Results storage**: Varies by volume (organized by date for cleanup)

### How do I monitor performance?

**Prometheus metrics**:
```bash
curl http://localhost:8000/v1/metrics
```

**Health endpoint**:
```bash
curl http://localhost:8000/health
```

**Grafana dashboards** (Level 3):
- Pre-configured dashboards in `infrastructure/grafana/dashboards/`
- Access at `http://localhost:3000` (Docker Compose)

**Application logs**:
- **Structured JSON logs** (if `LOG_FORMAT=json`): Parseable, searchable
- **Text logs** (if `LOG_FORMAT=text`): Human-readable

**Key metrics to monitor**:
- Request rate and latency
- Job queue depth
- Worker count and status
- GPU utilization
- Error rates
- Cache hit rates

## Features

### What is speaker diarization?

Speaker diarization identifies different speakers in audio. Enable with `diarise=true`:

```bash
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=VIDEO_ID" \
  -F "diarise=true"
```

**Important notes**:
- **Forces Path B (ASR)**: Diarization requires ASR processing, so Path A is skipped
- **Takes longer**: ASR processing is slower than captions
- **Level 1 requirement**: `diarise=true` triggers ASR mode (implemented)
- **Level 2 feature**: Actual speaker identification/labeling in segments (not yet fully implemented)

### How does the two-path strategy work?

The API automatically chooses the best path:

**Path A (Fast-path)**:
- Uses existing YouTube captions
- **Speed**: Milliseconds (100-500ms typical)
- **GPU**: Not required
- **Translation**: Supports all languages
- **When used**: Captions available and `diarise=false`

**Path B (ASR Fallback)**:
- Uses Whisper model for speech recognition
- **Speed**: Seconds to minutes (depends on video length and device)
- **GPU**: Recommended for production
- **Translation**: Only to English
- **When used**: Captions unavailable, `diarise=true`, or translation to non-English requested

**Decision flow (YouTube endpoint only)**:
1. Check if `diarise=true` → If yes, skip Path A and use Path B directly
2. If `diarise=false`, try Path A (captions) → If successful, return result
3. If Path A fails → Fall back to Path B

**Media endpoint** (`/v1/transcriptions/media`):
- Always uses Path B (ASR) - no captions path available
- All media files (uploaded or remote URL) go through Whisper ASR
- Processing is always asynchronous (returns job ID for polling)

### What is auto-scaling?

Auto-scaling automatically creates and destroys GPU workers based on queue depth:

**Scale up**:
- When queue depth > `WORKER_SCALE_UP_QUEUE_DEPTH` (default: 10)
- Creates new worker (up to `MAX_WORKERS`)

**Scale down**:
- When queue depth < `WORKER_SCALE_DOWN_QUEUE_DEPTH` (default: 2)
- AND worker idle > `WORKER_IDLE_TIMEOUT_SECONDS` (default: 300s)
- Terminates idle worker (down to `MIN_WORKERS`)

**Configuration**:
```bash
WORKER_AUTO_SCALING_ENABLED=true
WORKER_SCALE_UP_QUEUE_DEPTH=10
WORKER_SCALE_DOWN_QUEUE_DEPTH=2
WORKER_IDLE_TIMEOUT_SECONDS=300
MAX_WORKERS=5
MIN_WORKERS=0
```

**Check interval**: Every `WORKER_AUTO_SCALING_INTERVAL_SECONDS` (default: 60s)

### How does cost control work?

Cost control (Level 3) tracks GPU usage and enforces budget limits:

**Features**:
- Tracks GPU hours consumed per job
- Calculates costs based on `GPU_COST_PER_HOUR` (default: $0.50/hour)
- Rejects new jobs when budget exceeded
- Alerts when approaching budget threshold (default: 80% of max)

**Configuration**:
```bash
COST_CONTROL_ENABLED=true
MAX_BUDGET_USD=100.0
GPU_COST_PER_HOUR=0.50
BUDGET_ALERT_THRESHOLD=0.8  # Alert at 80% of budget
COST_TRACKING_WINDOW_DAYS=30  # Track costs for 30 days
```

**Cost calculation**:
```
cost = gpu_hours * GPU_COST_PER_HOUR
```

**Budget enforcement**:
- If `current_cost >= MAX_BUDGET_USD`: New jobs rejected
- If `current_cost >= MAX_BUDGET_USD * BUDGET_ALERT_THRESHOLD`: Alerts logged

## Deployment

### Can I deploy without Docker?

Yes! The API can run directly with Python:

```bash
# Install dependencies
poetry install

# Set environment variables
export API_KEYS=your-api-key
export REDIS_ENABLED=true
export REDIS_HOST=localhost

# Run the API
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**However**, Docker is **recommended for production** for:
- Consistency across environments
- Easy dependency management
- Isolated execution
- Easy scaling

### How do I deploy to production?

1. **Configure production settings** in `.env`:
   ```bash
   API_KEYS=your-secure-api-keys
   DEV_MODE=false
   REDIS_ENABLED=true
   REDIS_PASSWORD=strong-password
   S3_ENABLED=true
   S3_BUCKET_NAME=your-bucket
   ```

2. **Set up infrastructure**:
   - Redis (external or managed service)
   - S3 storage (AWS S3, Cloudflare R2, etc.)
   - GPU workers (if using Level 3)

3. **Deploy with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Or deploy with Kubernetes**:
   - Use manifests in `infrastructure/kubernetes/`
   - See [Infrastructure Documentation](../infrastructure/README.md)

5. **Configure monitoring**:
   - Prometheus (metrics collection)
   - Grafana (visualization)
   - Application logs (structured JSON)

6. **Set up GPU workers** (if needed):
   - Configure RunPod API key and template ID
   - Enable auto-scaling

See [Installation Guide](INSTALLATION.md) and [Infrastructure Documentation](../infrastructure/README.md) for details.

### Can I use Kubernetes?

Yes! Kubernetes manifests are provided in `infrastructure/kubernetes/`:

- `api-deployment.yaml`: API server deployment
- `hpa.yaml`: Horizontal Pod Autoscaler

See [Infrastructure Documentation](../infrastructure/README.md) for details.

### How do I scale horizontally?

**API instances**:
- Deploy multiple API instances behind a load balancer
- All instances share the same Redis and S3 storage
- Stateless design allows easy horizontal scaling

**Workers** (Level 3):
- Use auto-scaling workers (managed by RunPod)
- Workers automatically scale based on queue depth

**Redis**:
- Use Redis Cluster for high availability
- Or use managed Redis service (AWS ElastiCache, etc.)

**Storage**:
- Use S3-compatible storage (scales automatically)
- Or use distributed file system

## Troubleshooting

### Why is my transcription slow?

**Check these factors**:

1. **Compute device**:
   ```bash
   # Check if using CPU (slower) vs GPU (faster)
   curl http://localhost:8000/health
   # Look for "whisper.device": "cpu" or "cuda"
   ```

2. **Model size**:
   ```bash
   # Larger models are slower
   # Check WHISPER_MODEL in .env
   ```

3. **Video length**: Longer videos take proportionally longer

4. **System resources**:
   ```bash
   # CPU usage
   top
   
   # Memory usage
   free -h
   
   # Disk I/O
   iostat
   ```

5. **Path used**: Path A (captions) is much faster than Path B (ASR)

**Solutions**:
- Use GPU instead of CPU
- Use smaller model (whisper-base instead of whisper-large-v3)
- Ensure Path A is used when possible (captions available)
- Check system resources (CPU, memory, disk)

### Why are jobs failing?

**Check these**:

1. **Application logs**:
   ```bash
   docker-compose logs transcription-api
   # Or: tail -f logs/app.log
   ```

2. **Job status**:
   ```bash
   curl -X GET "http://localhost:8000/v1/jobs/{job_id}" \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

3. **Health endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```

4. **Enable debug logging**:
   ```bash
   LOG_LEVEL=DEBUG
   ```

**Common failure reasons**:
- Video too long (> 1 hour)
- Video unavailable or private
- Audio download failed
- Whisper model not loaded
- Insufficient memory
- Redis connection failed

### Why can't I connect to Redis?

**Check these**:

1. **Redis is running**:
   ```bash
   docker ps | grep redis
   # Or: redis-cli ping
   ```

2. **Redis password** in `.env`:
   ```bash
   REDIS_PASSWORD=your-password
   ```

3. **Network connectivity**:
   ```bash
   # From API container
   docker exec -it transcription-api ping redis
   ```

4. **Redis host/port**:
   ```bash
   REDIS_HOST=redis  # Docker service name
   REDIS_PORT=6379
   ```

5. **Redis enabled**:
   ```bash
   REDIS_ENABLED=true
   ```

**Solutions**:
- Verify Redis is running: `docker-compose ps`
- Check Redis logs: `docker-compose logs redis`
- Test connection: `redis-cli -h localhost -p 6379 -a your-password ping`

### Why are workers not scaling?

**Check these**:

1. **Auto-scaling enabled**:
   ```bash
   WORKER_AUTO_SCALING_ENABLED=true
   ```

2. **RunPod configuration**:
   ```bash
   RUNPOD_API_KEY=your-key
   RUNPOD_TEMPLATE_ID=your-template-id
   ```

3. **Queue depth**:
   ```bash
   # Check queue stats
   curl http://localhost:8000/v1/queue/stats \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

4. **Worker limits**:
   ```bash
   MAX_WORKERS=5
   MIN_WORKERS=0
   ```

5. **Worker logs** in RunPod console

**Solutions**:
- Test RunPod connection: `python scripts/test_runpod_connection.py`
- Check queue depth exceeds threshold
- Verify worker template is correct
- Check RunPod account has credits

### How do I debug issues?

1. **Enable debug logging**:
   ```bash
   LOG_LEVEL=DEBUG
   LOG_FORMAT=json  # Structured logs for easier parsing
   ```

2. **Check application logs**:
   ```bash
   docker-compose logs -f transcription-api
   ```

3. **Check health endpoint**:
   ```bash
   curl http://localhost:8000/health | jq
   ```

4. **Check metrics**:
   ```bash
   curl http://localhost:8000/v1/metrics
   ```

5. **Review configuration**:
   ```bash
   # Verify .env settings
   cat .env
   ```

6. **Test individual components**:
   ```bash
   # Test Redis connection
   redis-cli -h localhost -p 6379 ping
   
   # Test RunPod connection
   python scripts/test_runpod_connection.py
   
   # Test S3 connection
   # Check S3 logs in MinIO console or AWS CloudWatch
   ```

## Costs & Billing

### How much does it cost to run?

**API Server** (self-hosted):
- Infrastructure costs (CPU, memory, disk)
- No per-request charges

**GPU Workers** (RunPod):
- **Cost per GPU hour**: $0.20-$2.00 depending on GPU type
- **Typical usage**: 0.1-0.5 GPU hours per 30-minute video
- **Example**: 100 videos (30 min each) = ~50 GPU hours = $10-$100

**Storage** (S3):
- **Storage cost**: ~$0.023 per GB/month (AWS S3)
- **Transfer cost**: ~$0.09 per GB (outbound)
- **Typical usage**: Minimal (results are small JSON files)

**Redis**:
- **Managed service**: $10-$100/month depending on size
- **Self-hosted**: Infrastructure costs only

### How do I control costs?

1. **Enable cost control** (Level 3):
   ```bash
   COST_CONTROL_ENABLED=true
   MAX_BUDGET_USD=100.0
   GPU_COST_PER_HOUR=0.50
   ```

2. **Set worker limits**:
   ```bash
   MAX_WORKERS=3  # Limit concurrent workers
   MIN_WORKERS=0  # Scale to zero when idle
   ```

3. **Configure auto-scaling**:
   ```bash
   WORKER_IDLE_TIMEOUT_SECONDS=300  # Terminate idle workers quickly
   WORKER_SCALE_DOWN_QUEUE_DEPTH=2  # Scale down aggressively
   ```

4. **Use Path A (captions)** when possible (no GPU cost)

5. **Monitor costs**:
   ```bash
   # Check cost metrics
   curl http://localhost:8000/v1/metrics | grep cost
   ```

### What happens when budget is exceeded?

When `current_cost >= MAX_BUDGET_USD`:
- **New jobs are rejected** with `BUDGET_EXCEEDED` error
- **Existing jobs continue** processing
- **Alerts are logged** when approaching threshold (80% by default)

**To resume**:
- Increase `MAX_BUDGET_USD`
- Or wait for cost tracking window to reset (default: 30 days)

## Next Steps

- Read [Installation Guide](INSTALLATION.md) for setup
- Review [API Reference](api-reference.md) for endpoints
- Check [Features Documentation](features.md) for implementation details
- See [Configuration Guide](CONFIGURATION.md) for all settings
- Review [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues
- Explore [Architecture Documentation](architecture.md) for system design
