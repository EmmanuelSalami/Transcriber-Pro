# Troubleshooting Guide

Common issues and solutions for the YouTube Transcription API.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Configuration Issues](#configuration-issues)
- [API Errors](#api-errors)
- [Performance Issues](#performance-issues)
- [Storage Issues](#storage-issues)
- [Worker Issues](#worker-issues)
- [Network Issues](#network-issues)

## Installation Issues

### Model Download Fails

**Symptoms**:
- Error: "Failed to download Whisper model"
- Container fails to start
- Model files missing

**Solutions**:

1. **Check Internet Connection**:
   ```bash
   curl -I https://huggingface.co
   ```

2. **Verify Disk Space**:
   ```bash
   df -h
   # Models require 1-3GB depending on size
   ```

3. **Manual Model Download**:
   ```bash
   python scripts/download_whisper_model.py
   ```

4. **Use Pre-downloaded Model**:
   ```bash
   # Download model to local directory
   WHISPER_MODEL_PATH=./models/whisper python scripts/download_whisper_model.py
   
   # Set in .env
   WHISPER_MODEL_PATH=./models/whisper
   ```

5. **Docker Volume Mount**:
   ```yaml
   volumes:
     - ./models/whisper:/app/models/whisper
   ```

### Poetry Installation Fails

**Symptoms**:
- `poetry: command not found`
- Poetry installation errors

**Solutions**:

1. **Install Poetry**:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Add to PATH**:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

3. **Verify Installation**:
   ```bash
   poetry --version
   ```

### Python Version Issues

**Symptoms**:
- `Python 3.11+ required`
- Import errors

**Solutions**:

1. **Check Python Version**:
   ```bash
   python3 --version
   # Should be 3.11 or higher
   ```

2. **Use pyenv** (if needed):
   ```bash
   pyenv install 3.11.0
   pyenv local 3.11.0
   ```

## Configuration Issues

### API Keys Not Working

**Symptoms**:
- `401 Unauthorized` errors
- "Invalid API key" messages

**Solutions**:

1. **Verify API Key Format**:
   ```bash
   # Check .env file
   cat .env | grep API_KEYS
   # Should be: API_KEYS=key1,key2,key3
   ```

2. **Check Authorization Header**:
   ```bash
   # Correct format
   Authorization: Bearer YOUR_API_KEY
   ```

3. **Regenerate API Key**:
   ```bash
   python scripts/generate_api_key.py
   ```

4. **Check Development Mode**:
   ```bash
   # If DEV_MODE=true, API keys are optional
   # In production, API keys are required
   ```

### Redis Connection Errors

**Symptoms**:
- `Redis connection failed`
- Jobs not persisting
- `Connection refused` errors

**Solutions**:

1. **Check Redis is Running**:
   ```bash
   # Docker
   docker ps | grep redis
   
   # Local
   redis-cli ping
   ```

2. **Verify Redis Password**:
   ```bash
   # Check .env
   cat .env | grep REDIS_PASSWORD
   
   # Test connection
   redis-cli -a YOUR_PASSWORD ping
   ```

3. **Check Redis Host/Port**:
   ```bash
   # Docker: Use service name
   REDIS_HOST=redis
   REDIS_PORT=6379
   
   # Local: Use localhost
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```

4. **Check Network**:
   ```bash
   # From API container
   docker exec transcription-api ping redis
   ```

5. **Redis Connection Pool**:
   ```bash
   # Check health endpoint
   curl http://localhost:8000/health | jq .redis
   # Returns pool statistics:
   # {
   #   "connected": true,
   #   "pool_stats": {
   #     "max_connections": 50,
   #     "created_connections": "N/A",
   #     "available_connections": "N/A",
   #     "usage_percent": 0
   #   }
   # }
   ```

### CORS Errors

**Symptoms**:
- `CORS policy` errors in browser
- Requests blocked by browser

**Solutions**:

1. **Check CORS Configuration**:
   ```bash
   # In .env
   CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
   ```

2. **Development Mode**:
   ```bash
   # Allow all origins (dev only)
   CORS_ORIGINS=*
   DEV_MODE=true
   ```

3. **Verify Origin**:
   ```bash
   # Check request origin matches CORS_ORIGINS
   # Browser console shows actual origin
   ```

## API Errors

### Video Not Found

**Symptoms**:
- `404 Video not found`
- `VIDEO_NOT_FOUND` error

**Solutions**:

1. **Verify URL Format**:
   ```bash
   # Correct formats:
   https://www.youtube.com/watch?v=VIDEO_ID
   https://youtu.be/VIDEO_ID
   ```

2. **Check Video Availability**:
   ```bash
   # Test in browser
   curl -I "https://www.youtube.com/watch?v=VIDEO_ID"
   ```

3. **Video May Be Private/Deleted**:
   - Private videos require authentication
   - Deleted videos cannot be transcribed

### Captions Not Available

**Symptoms**:
- `404 Captions not available` or `CAPTIONS_NOT_AVAILABLE` error
- API automatically falls back to ASR (Path B)
- Response includes `"source": "asr"` instead of `"source": "youtube_captions"`

**Solutions**:

1. **Understanding Two-Path Strategy** (YouTube endpoint only):
   - **Path A (Captions)**: Fast, no GPU needed, preferred
   - **Path B (ASR)**: Automatic fallback when captions unavailable
   - If `diarise=true`: Skips Path A and goes directly to Path B
   - If `diarise=false`: The API tries Path A first, then falls back to Path B if captions unavailable
   - No action needed - fallback is automatic
   - **Note**: Media endpoint (`/v1/transcriptions/media`) always uses Path B (ASR) - no captions path available

2. **Why Captions May Fail**:
   - Video has no captions/transcripts
   - Captions are disabled for the video
   - Video is private/age-restricted (captions may be blocked)
   - Translation requested but not available in captions

3. **Check Caption Languages**:
   ```bash
   # The API tries preferred languages first
   # Default: en,es,fr,de,it,pt,ru
   PREFERRED_LANGUAGES=en,es,fr,de,it,pt,ru
   
   # Common languages as fallback
   # Default: en,es,fr,de,it,pt,ru,ja,ko,zh-Hans,zh-Hant
   COMMON_LANGUAGES=en,es,fr,de,it,pt,ru,ja,ko,zh-Hans,zh-Hant
   ```

4. **Force ASR (Skip Captions)**:
   ```bash
   # Force ASR by requesting diarization
   # This skips Path A entirely and goes directly to Path B
   curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -F "url=https://youtube.com/watch?v=VIDEO_ID" \
     -F "diarise=true"
   ```
   
   **Note**: For media endpoint, ASR is always used (no need to force it).

5. **Check Logs**:
   ```bash
   # Look for log messages:
   # "[CAPTIONS] Path A failed for {video_id}: {error}"
   # "[ASR] Falling back to Whisper ASR (Path B)"
   docker-compose logs transcription-api | grep -i "captions\|asr"
   ```

### Rate Limit Exceeded

**Symptoms**:
- `429 Too Many Requests`
- `RATE_LIMIT_EXCEEDED` error

**Solutions**:

1. **Check Rate Limit**:
   ```bash
   # Default: 60 requests/minute
   # Check RATE_LIMIT_PER_MINUTE in .env
   ```

2. **Implement Retry Logic**:
   ```python
   import time
   import requests
   from requests.exceptions import HTTPError

   def transcribe_with_retry(url, api_key, max_retries=3):
       headers = {"Authorization": f"Bearer {api_key}"}
       for attempt in range(max_retries):
           try:
               response = requests.post(
                   "http://localhost:8000/v1/transcriptions/youtube",
                   headers=headers,
                   data={"url": url}
               )
               response.raise_for_status()
               return response.json()
           except HTTPError as e:
               if e.response.status_code == 429:
                   # Default retry-after is 60 seconds (configurable)
                   retry_after = int(e.response.headers.get('Retry-After', 60))
                   if attempt < max_retries - 1:
                       print(f"Rate limited. Retrying after {retry_after}s...")
                       time.sleep(retry_after)
                       continue
               raise
   ```

3. **Use Multiple API Keys**:
   ```bash
   # Rotate between multiple keys
   API_KEYS=key1,key2,key3
   ```

### Video Too Long

**Symptoms**:
- `400 Bad Request` or `413 Payload Too Large`
- `VIDEO_TOO_LONG` error code
- Error message: "Video too long: {duration}s. Maximum allowed duration is {max}s"

**Solutions**:

1. **Check Video Duration**:
   ```bash
   # Maximum: 1 hour (3600 seconds) by default
   # Check MAX_VIDEO_DURATION_SECONDS in .env
   # Default: 3600 seconds (1 hour)
   ```

2. **Understanding Duration Limits**:
   - Videos < 5 minutes: Synchronous processing (returns immediately)
   - Videos 5 minutes - 1 hour: Asynchronous processing (returns job ID)
   - Videos > 1 hour: Rejected with `VIDEO_TOO_LONG` error
   - Thresholds: `ASYNC_THRESHOLD_SECONDS` (default: 300) and `MAX_VIDEO_DURATION_SECONDS` (default: 3600)

3. **Use Async Processing for Long Videos**:
   ```python
   # For videos 5-60 minutes, the API automatically uses async processing
   # Response includes job_id for polling:
   response = requests.post(
       "http://localhost:8000/v1/transcriptions/youtube",
       headers={"Authorization": f"Bearer {api_key}"},
       data={"url": "https://youtube.com/watch?v=VIDEO_ID"}
   )
   job = response.json()
   job_id = job["jobId"]
   
   # Poll job status
   while True:
       status = requests.get(
           f"http://localhost:8000/v1/jobs/{job_id}",
           headers={"Authorization": f"Bearer {api_key}"}
       ).json()
       if status["status"] == "completed":
           break
       time.sleep(5)
   ```

4. **Increase Limit** (if needed):
   ```bash
   # In .env (not recommended for production)
   # Consider resource constraints and costs
   MAX_VIDEO_DURATION_SECONDS=7200  # 2 hours
   ```

## Performance Issues

### Slow Transcription

**Symptoms**:
- Transcription takes too long
- Timeout errors
- Requests hanging

**Solutions**:

1. **Use GPU (Recommended for Production)**:
   ```bash
   # In .env
   WHISPER_DEVICE=cuda  # For NVIDIA GPUs
   # or
   WHISPER_DEVICE=mps   # For Apple Silicon (M1/M2)
   WHISPER_COMPUTE_TYPE=float16  # GPU: float16, CPU: float32
   ```
   **Note**: GPU provides 10-50x speedup for ASR transcription

2. **Use Smaller Model**:
   ```bash
   # Models (speed vs accuracy trade-off):
   WHISPER_MODEL=openai/whisper-base      # Fastest, ~149M params
   WHISPER_MODEL=openai/whisper-small    # Balanced, ~244M params
   WHISPER_MODEL=openai/whisper-medium   # Slower, ~769M params
   WHISPER_MODEL=openai/whisper-large-v3 # Slowest, ~1550M params (best accuracy)
   ```

3. **Check System Resources**:
   ```bash
   # CPU usage
   top
   htop  # Better visualization
   
   # Memory usage
   free -h
   
   # Disk I/O
   iostat -x 1
   
   # GPU usage (if using CUDA)
   nvidia-smi
   watch -n 1 nvidia-smi
   ```

4. **Optimize Cache**:
   ```bash
   # Increase captions cache (Path A results only)
   CACHE_MAX_SIZE=5000  # Default: 1000
   CACHE_TTL_SECONDS=600  # Default: 300 (5 minutes)
   
   # Video ID cache (separate cache)
   VIDEO_ID_CACHE_MAX_SIZE=10000  # Default: 5000
   VIDEO_ID_CACHE_TTL_SECONDS=7200  # Default: 3600 (1 hour)
   ```

5. **Check Video Duration**:
   ```bash
   # Long videos (>5 min) use async processing
   # Check if job is being processed asynchronously
   # Short videos (<5 min) should be fast with GPU
   ```

6. **Check Network for Downloads**:
   ```bash
   # Slow YouTube downloads affect transcription time
   # Check yt-dlp download speed
   YT_DLP_TIMEOUT=600  # Increase if needed (default: 300)
   ```

7. **Monitor Logs**:
   ```bash
   # Check for bottlenecks
   docker-compose logs transcription-api | grep -i "duration\|time\|slow"
   ```

### High Memory Usage

**Symptoms**:
- Out of memory errors
- Container killed

**Solutions**:

1. **Use Smaller Model**:
   ```bash
   WHISPER_MODEL=openai/whisper-base  # 149M params
   # Instead of whisper-large-v3 (1550M params)
   ```

2. **Limit Concurrent Requests**:
   ```bash
   # Use rate limiting
   RATE_LIMIT_PER_MINUTE=30
   ```

3. **Increase Container Memory**:
   ```yaml
   # docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 8G
   ```

### Model Loading Takes Too Long

**Symptoms**:
- Slow application startup
- First transcription request very slow
- Startup logs show "Whisper model not loaded at startup"

**Solutions**:

1. **Preload Model on Startup** (Enabled by Default):
   ```bash
   # Check startup logs:
   docker-compose logs transcription-api | grep -i "whisper\|model"
   # Should see: "✓ Whisper model loaded successfully at startup"
   # If not: "⚠ Whisper model not loaded at startup"
   ```
   **Note**: Model preloading happens automatically during application startup. If it fails, the model will load lazily on first request.

2. **Use Pre-downloaded Model** (Faster Startup):
   ```bash
   # Download model manually first
   python scripts/download_whisper_model.py
   
   # Then set path in .env
   WHISPER_MODEL_PATH=./models/whisper  # Local path
   # or in Docker:
   WHISPER_MODEL_PATH=/app/models/whisper  # Container path
   ```
   **Benefits**: 
   - Faster startup (no download during startup)
   - Works offline
   - Consistent model version

3. **Check Model Download**:
   ```bash
   # Verify model files exist
   ls -lh models/whisper/
   # Should see: config.json, tokenizer.json, model.safetensors, etc.
   
   # Check model size
   du -sh models/whisper/
   # whisper-base: ~300MB
   # whisper-small: ~500MB
   # whisper-medium: ~1.5GB
   # whisper-large-v3: ~3GB
   ```

4. **Warm Up Model** (Optional):
   ```bash
   # Send a test request after startup to ensure model is ready
   # This is only needed if preloading failed
   curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -F "url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Short video
   ```

5. **Check Health Endpoint**:
   ```bash
   # Verify model is loaded
   curl http://localhost:8000/health | jq .whisper
   # Should show: {"loaded": true, "device": "cpu|cuda|mps", "ready": true}
   ```

6. **GPU Model Loading**:
   ```bash
   # GPU models load faster than CPU
   # If using GPU, ensure CUDA is available:
   WHISPER_DEVICE=cuda
   # Check: nvidia-smi shows GPU available
   ```

## Storage Issues

### S3 Connection Errors

**Symptoms**:
- `S3 connection failed` or `S3_ERROR` in logs
- Files not uploading to S3
- Fallback to local file system

**Solutions**:

1. **Verify S3 Configuration**:
   ```bash
   # Check .env - all required for S3
   S3_ENABLED=true  # Must be true
   S3_BUCKET_NAME=your-bucket  # Required if S3_ENABLED=true
   S3_ACCESS_KEY_ID=your-key  # Required if S3_ENABLED=true
   S3_SECRET_ACCESS_KEY=your-secret  # Required if S3_ENABLED=true
   S3_REGION=us-east-1  # Default: us-east-1
   
   # For S3-compatible services (MinIO, Cloudflare R2, etc.)
   S3_ENDPOINT_URL=http://minio:9000  # Optional, empty for AWS S3
   ```

2. **Check S3 Initialization**:
   ```bash
   # Check startup logs
   docker-compose logs transcription-api | grep -i "s3"
   # Should see: "S3StorageService initialized successfully"
   # Or error: "Failed to initialize S3 storage"
   ```

3. **Test S3 Connection**:
   ```python
   import boto3
   from botocore.exceptions import ClientError
   
   try:
       s3 = boto3.client(
           's3',
           endpoint_url='http://minio:9000',  # or None for AWS
           aws_access_key_id='your-key',
           aws_secret_access_key='your-secret',
           region_name='us-east-1'
       )
       # Test connection
       s3.list_buckets()
       print("S3 connection successful")
       
       # Test bucket access
       s3.head_bucket(Bucket='your-bucket')
       print("Bucket accessible")
   except ClientError as e:
       print(f"S3 error: {e}")
   ```

4. **Check Bucket Exists**:
   ```bash
   # MinIO console: http://localhost:9001
   # Login and create bucket if missing
   
   # Or via CLI
   mc mb minio/your-bucket
   
   # For AWS S3
   aws s3 ls s3://your-bucket
   ```

5. **Verify Permissions**:
   ```bash
   # S3 user needs read/write permissions
   # AWS: Check IAM policies
   # MinIO: Check bucket policies in console
   # Cloudflare R2: Check API token permissions
   ```

6. **Check Network Connectivity** (Docker):
   ```bash
   # From API container to MinIO
   docker exec transcription-api ping -c 3 minio
   
   # Check DNS resolution
   docker exec transcription-api nslookup minio
   ```

7. **Verify boto3 Installation**:
   ```bash
   # boto3 is required for S3
   docker exec transcription-api python -c "import boto3; print(boto3.__version__)"
   # If missing: pip install boto3
   ```

8. **Check Fallback Behavior**:
   ```bash
   # If S3 fails, system falls back to local file system
   # Check logs for: "Failed to initialize S3 storage, using local filesystem"
   # Results will still be stored, just locally instead of S3
   ```

### File Upload Fails

**Symptoms**:
- `413 Payload Too Large`
- Upload timeout
- `FILE_TOO_LARGE` error

**Solutions**:

1. **Check File Size Limit**:
   ```bash
   # Default: 500MB
   MAX_FILE_SIZE_MB=500
   
   # Increase if needed (not recommended for production)
   MAX_FILE_SIZE_MB=1000  # 1GB
   ```
   **Note**: Large files increase processing time and resource usage.

2. **Check Allowed Formats**:
   ```bash
   # Audio formats
   ALLOWED_AUDIO_FORMATS=mp3,wav,m4a,flac,ogg
   
   # Video formats
   ALLOWED_VIDEO_FORMATS=mp4,mkv,avi,mov,webm
   ```

3. **Use Multipart Upload** (S3):
   ```bash
   # Automatically used for files > threshold
   S3_MULTIPART_THRESHOLD_MB=100  # Default: 100MB
   S3_MULTIPART_CHUNK_SIZE_MB=10  # Default: 10MB per chunk
   ```

4. **Increase Timeout**:
   ```bash
   # For large file uploads
   MEDIA_DOWNLOAD_TIMEOUT_SECONDS=600  # Default: 300 (5 minutes)
   
   # For webhook callbacks (if uploading results)
   WEBHOOK_TIMEOUT_SECONDS=10  # Default: 10 seconds
   ```

5. **Check Disk Space**:
   ```bash
   # Ensure enough space for temporary files
   df -h
   # Check temp_uploads_dir and temp_downloads_dir
   ```

6. **Check Network**:
   ```bash
   # Slow network affects upload time
   # Check upload speed
   # Consider using S3 for large files
   ```

## Job Issues

### Jobs Stuck in Processing

**Symptoms**:
- Jobs remain in "processing" status indefinitely
- Jobs not completing
- No error messages

**Solutions**:

1. **Check Background Tasks**:
   ```bash
   # Background tasks process async jobs
   # Check if background task is running
   docker-compose logs transcription-api | grep -i "background\|processing"
   ```

2. **Recover Orphaned Jobs**:
   ```bash
   # On application restart, orphaned jobs are automatically recovered
   # Check startup logs:
   docker-compose logs transcription-api | grep -i "orphaned\|recover"
   # Should see: "Recovered X orphaned job(s) (marked as failed)"
   ```

3. **Check Job Status**:
   ```bash
   # Get job details
   curl http://localhost:8000/v1/jobs/{job_id} \
     -H "Authorization: Bearer YOUR_API_KEY"
   
   # Check if job has error
   # Look for "error" field in response
   ```

4. **Manual Job Recovery**:
   ```bash
   # Orphaned jobs are automatically marked as failed on restart
   # To manually check, restart the application
   docker-compose restart transcription-api
   ```

5. **Check Queue**:
   ```bash
   # If using Level 3 with QueueService
   # Check queue stats
   curl http://localhost:8000/v1/metrics | jq .queue
   ```

### Jobs Not Found

**Symptoms**:
- `404 Job not found`
- Job ID exists but can't retrieve

**Solutions**:

1. **Check Job TTL**:
   ```bash
   # Jobs expire after TTL (default: 1 hour)
   JOB_TTL_SECONDS=3600  # Default: 3600 (1 hour)
   
   # Increase if needed
   JOB_TTL_SECONDS=7200  # 2 hours
   ```

2. **Check Redis Connection**:
   ```bash
   # If Redis is down, jobs stored in-memory are lost on restart
   # Check Redis is running
   docker-compose ps redis
   curl http://localhost:8000/health | jq .redis
   ```

3. **Check Result File**:
   ```bash
   # Full results stored in file system/S3
   # Check if result file exists
   ls -la results/YYYY-MM-DD/{job_id}.json
   
   # Or in S3
   # Check S3 bucket for result file
   ```

4. **Job List Cache**:
   ```bash
   # Job list is cached (default: 10 seconds)
   # Wait a moment and retry
   # Or check individual job by ID
   ```

## Worker Issues

### Workers Not Registering

**Symptoms**:
- No workers in `/v1/workers`
- Jobs stuck in queue

**Solutions**:

1. **Check RunPod Configuration**:
   ```bash
   RUNPOD_API_KEY=your-key
   RUNPOD_TEMPLATE_ID=your-template-id
   ```

2. **Test RunPod Connection**:
   ```bash
   python scripts/test_runpod_connection.py
   ```

3. **Check Worker Logs**:
   ```bash
   # In RunPod console
   # Check worker startup logs
   ```

4. **Verify Worker Endpoint**:
   ```bash
   # Worker must be able to reach API
   # Check network connectivity
   ```

### Workers Unhealthy

**Symptoms**:
- Workers marked as `unhealthy`
- No heartbeat received

**Solutions**:

1. **Check Heartbeat Interval**:
   ```bash
   WORKER_HEARTBEAT_INTERVAL_SECONDS=30
   WORKER_HEALTH_CHECK_TIMEOUT_SECONDS=120
   ```

2. **Verify Worker is Running**:
   ```bash
   # Check RunPod console
   # Worker pod should be running
   ```

3. **Check Network**:
   ```bash
   # Worker must be able to reach API
   # Test from worker: curl http://api-url/health
   ```

### Auto-scaling Not Working

**Symptoms**:
- Queue depth high but no workers created
- Workers not scaling up/down automatically
- Jobs stuck in queue

**Solutions**:

1. **Check Auto-scaling Enabled**:
   ```bash
   # In .env
   WORKER_AUTO_SCALING_ENABLED=true  # Default: true
   ```
   **Note**: Auto-scaling requires RunPod configuration. Check startup logs:
   ```bash
   docker-compose logs transcription-api | grep -i "auto-scaling"
   # Should see: "Starting worker auto-scaling background task..."
   # Or: "Worker auto-scaling is enabled but RunPod is not configured"
   ```

2. **Verify RunPod Configuration**:
   ```bash
   # Required for auto-scaling
   RUNPOD_API_KEY=your-api-key
   RUNPOD_TEMPLATE_ID=your-template-id
   
   # Test connection
   python scripts/test_runpod_connection.py
   ```

3. **Verify Thresholds**:
   ```bash
   # Scale up when queue depth exceeds this
   WORKER_SCALE_UP_QUEUE_DEPTH=10  # Default: 10
   
   # Scale down when queue depth below this
   WORKER_SCALE_DOWN_QUEUE_DEPTH=2  # Default: 2
   
   # Idle timeout before scaling down
   WORKER_IDLE_TIMEOUT_SECONDS=300  # Default: 300 (5 minutes)
   ```

4. **Check Scaling Interval**:
   ```bash
   # How often to check queue and scale
   WORKER_AUTO_SCALING_INTERVAL_SECONDS=60  # Default: 60 seconds
   ```
   **Note**: Auto-scaling runs as a background task that checks every 60 seconds.

5. **Check Worker Limits**:
   ```bash
   MAX_WORKERS=5  # Default: 5
   MIN_WORKERS=0  # Default: 0
   ```
   **Note**: Auto-scaling respects these limits. If at max_workers, no new workers will be created.

6. **Check Queue Service**:
   ```bash
   # Auto-scaling requires QueueService to be working
   # Check queue stats endpoint
   curl http://localhost:8000/v1/metrics | jq .queue
   # or check QueueService is initialized
   docker-compose logs transcription-api | grep -i "QueueService"
   ```

7. **Monitor Auto-scaling**:
   ```bash
   # Check logs for auto-scaling decisions
   docker-compose logs transcription-api | grep -i "auto-scaling\|scale"
   # Look for:
   # "Auto-scaling UP: queue_depth=X > threshold=10"
   # "Auto-scaling DOWN: queue_depth=X < threshold=2"
   ```

8. **Manual Scaling** (If Auto-scaling Fails):
   ```bash
   # Manually scale workers via API
   curl -X POST "http://localhost:8000/v1/workers/scale?target_count=3" \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

## Network Issues

### Timeout Errors

**Symptoms**:
- Request timeouts
- Connection errors

**Solutions**:

1. **Increase Timeouts**:
   ```bash
   YT_DLP_TIMEOUT=600  # 10 minutes
   MEDIA_DOWNLOAD_TIMEOUT_SECONDS=600
   ```

2. **Check Network Connectivity**:
   ```bash
   # From container
   docker exec transcription-api ping google.com
   ```

3. **Use DNS**:
   ```yaml
   # docker-compose.yml
   dns:
     - 8.8.8.8
     - 8.8.4.4
   ```

### YouTube Blocking

**Symptoms**:
- `yt-dlp` errors
- Video download fails

**Solutions**:

1. **Update yt-dlp**:
   ```bash
   poetry run pip install --upgrade yt-dlp
   ```

2. **Check YouTube Changes**:
   ```bash
   # YouTube frequently changes API
   # Keep yt-dlp updated
   ```

3. **Use Alternative Methods**:
   ```bash
   # If captions available, use Path A
   # ASR fallback doesn't require yt-dlp
   ```

## Getting Help

If you're still experiencing issues:

1. **Check Logs**:
   ```bash
   docker-compose logs transcription-api
   ```

2. **Enable Debug Logging**:
   ```bash
   LOG_LEVEL=DEBUG
   ```

3. **Check Health Endpoint**:
   ```bash
   curl http://localhost:8000/health
   # Returns:
   # {
   #   "status": "healthy" | "degraded",
   #   "api": "running",
   #   "whisper": {
   #     "loaded": true/false,
   #     "device": "cpu" | "cuda" | "mps",
   #     "ready": true/false
   #   },
   #   "redis": {
   #     "connected": true/false,
   #     "pool_stats": {...}
   #   }
   # }
   ```

4. **Review Documentation**:
   - [Configuration Guide](CONFIGURATION.md)
   - [API Reference](api-reference.md)
   - [Architecture](architecture.md)

5. **Open an Issue**:
   - Include error messages
   - Include relevant logs
   - Include configuration (sanitized)

## Quick Reference

### Common Configuration Values

```bash
# API Configuration
API_KEYS=key1,key2,key3  # Required in production
DEV_MODE=false  # Set to true for development (disables auth)

# Redis
REDIS_ENABLED=true
REDIS_HOST=localhost  # or 'redis' in Docker
REDIS_PORT=6379
REDIS_PASSWORD=  # Optional

# Whisper Model
WHISPER_MODEL=openai/whisper-base
WHISPER_DEVICE=cpu  # or 'cuda' for GPU
WHISPER_COMPUTE_TYPE=float32  # or 'float16' for GPU

# Video Limits
ASYNC_THRESHOLD_SECONDS=300  # 5 minutes
MAX_VIDEO_DURATION_SECONDS=3600  # 1 hour

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# CORS
CORS_ORIGINS=https://yourdomain.com  # or '*' for dev

# S3 (Level 3)
S3_ENABLED=false  # Set to true to enable
S3_BUCKET_NAME=your-bucket
S3_ACCESS_KEY_ID=your-key
S3_SECRET_ACCESS_KEY=your-secret

# Workers (Level 3)
WORKER_AUTO_SCALING_ENABLED=true
RUNPOD_API_KEY=your-key
RUNPOD_TEMPLATE_ID=your-template-id
MAX_WORKERS=5
```

### Diagnostic Checklist

When troubleshooting, check in this order:

1. ✅ **Health Endpoint**: `curl http://localhost:8000/health`
2. ✅ **Logs**: `docker-compose logs transcription-api`
3. ✅ **Configuration**: Verify `.env` file settings
4. ✅ **Network**: Check connectivity between services
5. ✅ **Resources**: Check CPU, memory, disk space
6. ✅ **Dependencies**: Redis, S3, RunPod (if used)

## Next Steps

- Review [Configuration Guide](CONFIGURATION.md) for all settings
- Check [API Reference](api-reference.md) for endpoint details and examples
- See [FAQ](FAQ.md) for common questions
- Review [Architecture](architecture.md) for system design understanding
