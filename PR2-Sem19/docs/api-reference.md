# API Reference

Complete reference for all API endpoints in the YouTube Transcription API.

## Table of Contents

- [Authentication](#authentication)
- [Base URL](#base-url)
- [Endpoints](#endpoints)
  - [Health & Status](#health--status)
  - [Transcription Endpoints](#transcription-endpoints)
  - [Job Management](#job-management)
  - [Worker Management](#worker-management)
  - [Monitoring](#monitoring)
- [Request/Response Formats](#requestresponse-formats)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

## Authentication

All API endpoints (except health checks and metrics) require authentication using Bearer token authentication.

### Authentication Header

```http
Authorization: Bearer YOUR_API_KEY
```

### Development Mode

In development mode (`DEV_MODE=true`), API keys are optional. Requests without authentication are allowed but logged with warnings.

### Generating API Keys

```bash
# Generate a new API key
python scripts/generate_api_key.py

# Or use make command
make api-key
```

## Base URL

- **Local Development**: `http://localhost:8000`
- **Production**: `https://api.yourdomain.com`

All endpoints are prefixed with `/v1` (configurable via `API_VERSION`).

## Endpoints

### Health & Status

#### GET `/`

Root endpoint for API information.

**Authentication**: Not required

**Response**:

```json
{
  "name": "YouTube Transcription API",
  "version": "v1",
  "status": "running"
}
```

#### GET `/health`

Health check endpoint for monitoring and load balancers.

**Authentication**: Not required

**Response**:

```json
{
  "status": "healthy",
  "api": "running",
  "whisper": {
    "loaded": true,
    "device": "cpu",
    "ready": true
  },
  "redis": {
    "connected": true,
    "pool_stats": {
      "created_connections": 5,
      "available_connections": 45,
      "max_connections": 50,
      "usage_percent": 10.0
    }
  }
}
```

**Status Codes**:

- `200 OK`: Service is healthy
- `503 Service Unavailable`: Service is degraded (model not ready, Redis disconnected)

### Transcription Endpoints

The API provides two transcription endpoints with different flows:

1. **YouTube Endpoint** (`/v1/transcriptions/youtube`): Uses two-path strategy (captions fast-path with ASR fallback)
2. **Media Endpoint** (`/v1/transcriptions/media`): Always uses ASR, processes all requests asynchronously

#### POST `/v1/transcriptions/youtube`

Transcribe a YouTube video using two-path strategy.

**Authentication**: Required

**Content-Type**: `multipart/form-data`

**Request Parameters**:

| Parameter     | Type   | Required | Description                                                                                                                                        |
| ------------- | ------ | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `url`         | string | Yes      | YouTube video URL (e.g., `https://www.youtube.com/watch?v=dQw4w9WgXcQ`). Maximum length: 2048 characters.                                          |
| `translateTo` | string | No       | Target language code for translation (ISO 639-1, e.g., `en`, `es`, `fr`). Maximum length: 10 characters.                                           |
| `format`      | string | No       | Output format: `json` (default), `text`, `srt`, `vtt`. Case-insensitive.                                                                           |
| `diarise`     | string | No       | Enable speaker diarization: `"true"` or `"false"` (default: `"false"`). String value, not boolean. Forces ASR mode even if captions are available. |
| `webhookUrl`  | string | No       | Optional webhook callback URL for async jobs. Maximum length: 2048 characters.                                                                     |

**Processing Modes**:

- **Synchronous** (videos < 5 minutes): Returns transcription result immediately. Only applies to YouTube videos processed via ASR (when captions unavailable or diarization requested).
- **Asynchronous** (videos 5-60 minutes): Returns job ID for polling. Applies to all ASR-processed videos in this duration range.
- **Rejected** (videos > 60 minutes): Returns `VIDEO_TOO_LONG` error (413 status code).

**Note**: When YouTube captions are available and diarization is not requested, the response is always synchronous regardless of video length (up to 1 hour limit).

**Two-Path Strategy**:

- **Path A (Captions)**: Fast-path using existing YouTube captions (no GPU needed). Used when `diarise=false` and captions are available.
- **Path B (ASR)**: Whisper ASR fallback. Used when `diarise=true`, captions unavailable, or translation requested.

**Response (Synchronous - JSON format)**:

```json
{
  "status": "completed",
  "jobId": null,
  "source": "youtube_captions",
  "language": "en",
  "confidence": 0.95,
  "transcript": "Full transcript text here...",
  "segments": [
    {
      "text": "Segment text",
      "start": 0.0,
      "end": 2.5
    }
  ],
  "warnings": [],
  "videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response (Asynchronous)**:

```json
{
  "jobId": "123e4567-e89b-12d3-a456-426614174000",
  "status": "queued",
  "createdAt": "2024-01-01T12:00:00Z",
  "videoId": "dQw4w9WgXcQ",
  "videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response (Text/SRT/VTT format)**: Returns plain text content with appropriate `Content-Type` header and `Content-Disposition` header for file download:

- `Content-Type`: `text/plain` (text), `text/srt` (srt), or `text/vtt` (vtt)
- `Content-Disposition`: `attachment; filename="transcription.{ext}"`

**Status Codes**:

- `200 OK`: Request successful
- `400 Bad Request`: Invalid URL, parameters, or transcription error (see error codes)
- `401 Unauthorized`: Missing or invalid API key
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Internal server error

**Example**:

```bash
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  -F "format=json" \
  -F "translateTo=en"
```

#### POST `/v1/transcriptions/media`

Transcribe a media file (upload or remote URL).

**Authentication**: Required

**Content-Type**: `multipart/form-data`

**Request Parameters**:

| Parameter     | Type   | Required | Description                                                                                                                                          |
| ------------- | ------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `file`        | file   | No\*     | Upload media file. Supported formats: `mp3`, `wav`, `m4a`, `flac`, `ogg` (audio) or `mp4`, `mkv`, `avi`, `mov`, `webm` (video). Maximum size: 500MB. |
| `url`         | string | No\*     | Remote media URL (HTTP/HTTPS, not YouTube). Can be direct file URL or S3/R2 signed URL. Maximum length: 2048 characters.                             |
| `translateTo` | string | No       | Target language code for translation (ISO 639-1). Maximum length: 10 characters.                                                                     |
| `format`      | string | No       | Output format: `json` (default), `text`, `srt`, `vtt`. Case-insensitive.                                                                             |
| `webhookUrl`  | string | No       | Optional webhook callback URL. Maximum length: 2048 characters.                                                                                      |

\*Either `file` or `url` must be provided (not both).

**Important Notes**:

- **Always uses ASR (Path B)**: The media endpoint always uses Whisper ASR for transcription. There is no captions path (Path A) available for uploaded media files or remote URLs, unlike the YouTube endpoint which can use existing captions.
- **Asynchronous processing**: All media transcription requests are processed asynchronously. The endpoint always returns a `JobResponse` with a `jobId` for polling, regardless of file size or duration.

**Response**:

```json
{
  "jobId": "123e4567-e89b-12d3-a456-426614174000",
  "status": "queued",
  "createdAt": "2024-01-01T12:00:00Z",
  "videoId": null,
  "videoUrl": null
}
```

**Status Codes**:

- `200 OK`: Job created successfully
- `400 Bad Request`: Invalid file, URL, or parameters (see error codes)
- `401 Unauthorized`: Missing or invalid API key
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Internal server error

**Example (File Upload)**:

```bash
curl -X POST "http://localhost:8000/v1/transcriptions/media" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@audio.mp3" \
  -F "format=json"
```

**Example (Remote URL)**:

```bash
curl -X POST "http://localhost:8000/v1/transcriptions/media" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://cdn.example.com/audio.mp3" \
  -F "format=srt"
```

### Job Management

#### GET `/v1/jobs`

List all transcription jobs.

**Authentication**: Required

**Response**:

```json
{
  "jobs": [
    {
      "jobId": "123e4567-e89b-12d3-a456-426614174000",
      "status": "completed"
    },
    {
      "jobId": "223e4567-e89b-12d3-a456-426614174001",
      "status": "processing"
    }
  ],
  "total": 2
}
```

**Status Codes**:

- `200 OK`: Request successful
- `401 Unauthorized`: Missing or invalid API key

#### GET `/v1/jobs/{job_id}`

Get status and result of a specific job.

**Authentication**: Required

**Path Parameters**:

- `job_id` (string): Job identifier

**Response**:

```json
{
  "jobId": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "createdAt": "2024-01-01T12:00:00Z",
  "completedAt": "2024-01-01T12:05:00Z",
  "result": {
    "status": "completed",
    "source": "asr",
    "language": "en",
    "confidence": 0.92,
    "transcript": "Full transcript...",
    "segments": [...]
  },
  "videoId": "dQw4w9WgXcQ",
  "videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "source": "asr",
  "language": "en",
  "confidence": 0.92,
  "transcript": "Full transcript...",
  "segments": [...]
}
```

**Status Codes**:

- `200 OK`: Request successful
- `404 Not Found`: Job not found
- `401 Unauthorized`: Missing or invalid API key

**Query Parameters**:

- `stream` (boolean, optional): If `true` and result is large (>1MB), streams the response instead of loading into memory. Default: `false`.

**Response Notes**:

- For completed jobs, the `result` field contains the full transcription result.
- For large results (>1MB) with `stream=true`, the response is streamed as a JSON file download.
- Job status values: `queued`, `processing`, `completed`, `failed`.

**Example**:

```bash
# Get job status (default)
curl -X GET "http://localhost:8000/v1/jobs/123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Stream large result
curl -X GET "http://localhost:8000/v1/jobs/123e4567-e89b-12d3-a456-426614174000?stream=true" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Worker Management (Level 3)

#### POST `/v1/workers/register`

Register a GPU worker with the API.

**Authentication**: Not required (called by workers)

**Query Parameters**:

- `worker_id` (string, required): Unique worker identifier
- `runpod_pod_id` (string, required): RunPod pod ID
- `gpu_type` (string, optional): GPU type (e.g., "RTX 4090", "A100")

**Response**:

```json
{
  "message": "Worker registered successfully",
  "worker_id": "worker-123",
  "status": "warming_up"
}
```

#### POST `/v1/workers/{worker_id}/heartbeat`

Send heartbeat from worker to API.

**Authentication**: Not required (called by workers)

**Path Parameters**:

- `worker_id` (string, required): Worker identifier

**Query Parameters**:

- `model_loaded` (boolean, optional): Whether the Whisper model is loaded and ready. Default: `true`.

**Response**:

```json
{
  "message": "Heartbeat received",
  "worker_id": "worker-123",
  "model_loaded": true
}
```

**Note**: Workers should call this endpoint periodically (every 30 seconds by default) to indicate they are alive. The API uses heartbeats to track worker health and availability.

#### GET `/v1/workers`

List all registered workers.

**Authentication**: Required

**Response**:

```json
[
  {
    "workerId": "worker-123",
    "status": "idle",
    "runpodPodId": "pod-abc",
    "gpuType": "RTX 4090",
    "currentJobId": null,
    "lastHeartbeat": "2024-01-01T12:00:00Z",
    "modelLoaded": true,
    "jobsProcessed": 10,
    "totalGpuHours": 2.5
  }
]
```

**Note**: Returns an array of `WorkerInfo` objects, not an object with a `workers` field.

#### GET `/v1/workers/{worker_id}`

Get information about a specific worker.

**Authentication**: Required

**Path Parameters**:

- `worker_id` (string): Worker identifier

**Response**: Same format as worker object in list endpoint.

**Status Codes**:

- `200 OK`: Request successful
- `404 Not Found`: Worker not found
- `401 Unauthorized`: Missing or invalid API key

#### POST `/v1/workers/scale`

Manually scale workers to a target count or trigger auto-scaling.

**Authentication**: Required

**Query Parameters**:

- `target_count` (integer, optional): Target number of workers. If not provided, uses auto-scaling based on queue depth.

**Response**:

```json
{
  "message": "Scaled workers to 3",
  "worker_count": 3,
  "target_count": 3
}
```

OR (if auto-scaling):

```json
{
  "message": "Auto-scaled workers based on queue depth",
  "worker_count": 2,
  "queue_depth": 15
}
```

**Status Codes**:

- `200 OK`: Scaling operation successful
- `400 Bad Request`: Invalid scaling parameters
- `401 Unauthorized`: Missing or invalid API key
- `500 Internal Server Error`: Scaling operation failed

**Note**: Scaling respects `MIN_WORKERS` and `MAX_WORKERS` configuration limits.

#### POST `/v1/workers/test-connection`

Test RunPod API connection.

**Authentication**: Required

**Response**:

```json
{
  "connected": true,
  "message": "Successfully connected to Runpod API",
  "details": {
    "api_key_set": true,
    "template_id_set": true,
    "api_url": "https://api.runpod.io/graphql",
    "user_id": "abc123",
    "username": "user@example.com"
  }
}
```

**Status Codes**:

- `200 OK`: Connection test completed (may return `connected: false` if test fails)
- `401 Unauthorized`: Missing or invalid API key

### Monitoring

#### GET `/v1/metrics`

Prometheus metrics endpoint.

**Authentication**: Not required

**Content-Type**: `text/plain`

**Response**: Prometheus metrics in text format.

**Example**:

```bash
curl http://localhost:8000/v1/metrics
```

## Request/Response Formats

### Output Formats

#### JSON (Default)

Full transcription with metadata:

```json
{
  "status": "completed",
  "source": "youtube_captions",
  "language": "en",
  "confidence": 0.95,
  "transcript": "Full text...",
  "segments": [
    {
      "text": "Segment text",
      "start": 0.0,
      "end": 2.5
    }
  ]
}
```

#### Text

Plain text transcript only:

```
Full transcript text here...
```

#### SRT (SubRip)

Subtitle format:

```
1
00:00:00,000 --> 00:00:02,500
Segment text

2
00:00:02,500 --> 00:00:05,000
Next segment
```

#### VTT (WebVTT)

Web video text tracks:

```
WEBVTT

00:00:00.000 --> 00:00:02.500
Segment text

00:00:02.500 --> 00:00:05.000
Next segment
```

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "additional": "context"
  }
}
```

### Error Codes

| Code                     | HTTP Status | Description                                                 |
| ------------------------ | ----------- | ----------------------------------------------------------- |
| `INVALID_VIDEO_URL`      | 400         | Invalid YouTube URL format                                  |
| `VIDEO_NOT_FOUND`        | 400         | Video not found on YouTube                                  |
| `VIDEO_UNAVAILABLE`      | 400         | Video is unavailable (deleted, private, etc.)               |
| `CAPTIONS_NOT_AVAILABLE` | 400         | No captions available for video                             |
| `CAPTIONS_DISABLED`      | 400         | Captions are disabled for this video                        |
| `IP_BLOCKED`             | 400         | YouTube is blocking requests from this IP address           |
| `YOUTUBE_API_ERROR`      | 400         | Generic YouTube API error                                   |
| `VIDEO_TOO_LONG`         | 400         | Video exceeds maximum duration (1 hour)                     |
| `INVALID_API_KEY`        | 401         | Missing or invalid API key                                  |
| `RATE_LIMIT_EXCEEDED`    | 429         | Rate limit exceeded                                         |
| `TRANSCRIPTION_ERROR`    | 400         | Error during transcription                                  |
| `TRANSCRIPTION_TIMEOUT`  | 400         | Transcription operation timed out                           |
| `JOB_NOT_FOUND`          | 404         | Job not found                                               |
| `INVALID_FILE_TYPE`      | 400         | Unsupported file format                                     |
| `INVALID_FORMAT`         | 400         | Invalid output format parameter                             |
| `FILE_TOO_LARGE`         | 400         | File exceeds maximum size (500MB)                           |
| `DOWNLOAD_FAILED`        | 400         | Failed to download remote media file                        |
| `INVALID_INPUT`          | 400         | Invalid input parameters (e.g., both file and url provided) |
| `MISSING_INPUT`          | 400         | Missing required input (neither file nor url provided)      |
| `INTERNAL_SERVER_ERROR`  | 500         | Internal server error                                       |

### Error Examples

**Invalid URL**:

```json
{
  "code": "INVALID_VIDEO_URL",
  "message": "Invalid YouTube URL format",
  "details": {
    "url": "https://example.com/video"
  }
}
```

**Rate Limit Exceeded**:

```json
{
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded: 60 per 1 minute",
  "details": {
    "retry_after": 60
  }
}
```

**Note**: The response includes a `Retry-After` header indicating seconds until the limit resets.

**IP Blocked (YouTube)**:

```json
{
  "code": "IP_BLOCKED",
  "message": "YouTube is blocking requests from this IP address. This is usually due to too many requests or requests from a cloud provider IP. Please try again later or use a different network.",
  "details": {}
}
```

**Captions Disabled**:

```json
{
  "code": "CAPTIONS_DISABLED",
  "message": "Captions are disabled for this video",
  "details": {}
}
```

**Invalid Input (Media Endpoint)**:

```json
{
  "code": "INVALID_INPUT",
  "message": "Cannot provide both 'file' and 'url' parameters. Please provide either a file upload OR a remote URL, not both.",
  "details": {
    "provided": "both",
    "required": "one_of",
    "options": ["file", "url"]
  }
}
```

## Rate Limiting

Rate limiting is enforced per API key (or IP address in development mode).

### Default Limits

- **Default**: 60 requests per minute per API key
- **Configurable**: Set via `RATE_LIMIT_PER_MINUTE` environment variable

### Rate Limit Headers

Responses include rate limit information:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1640995200
```

### Rate Limit Exceeded

When rate limit is exceeded:

- **Status Code**: `429 Too Many Requests`
- **Response**: Error with `RATE_LIMIT_EXCEEDED` code
- **Retry-After Header**: Seconds until limit resets

## Webhooks

For async jobs, you can provide a `webhookUrl` parameter. When the job completes, the API will POST the transcription result to your URL.

### Webhook Payload

The webhook payload is sent as JSON in the request body:

```json
{
  "jobId": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "result": {
    "status": "completed",
    "source": "asr",
    "language": "en",
    "confidence": 0.92,
    "transcript": "Full transcript text...",
    "segments": [
      {
        "text": "Segment text",
        "start": 0.0,
        "end": 2.5
      }
    ],
    "warnings": []
  }
}
```

### Webhook Request Details

- **Method**: POST
- **Content-Type**: `application/json`
- **User-Agent**: `TranscriptionService/1.0` (configurable via `WEBHOOK_USER_AGENT`)
- **Timeout**: 10 seconds (configurable via `WEBHOOK_TIMEOUT_SECONDS`)
- **Connection Timeout**: 5 seconds (configurable via `WEBHOOK_CONNECT_TIMEOUT`)

### Webhook Retry Logic

- **Max Retries**: 3 (configurable via `WEBHOOK_MAX_RETRIES`)
- **Retry Strategy**: Exponential backoff with base delay of 1 second (configurable via `WEBHOOK_RETRY_BACKOFF_BASE`)
- **Timeout**: 10 seconds (configurable via `WEBHOOK_TIMEOUT_SECONDS`)
- **SSRF Protection**: Webhook URLs are validated to prevent Server-Side Request Forgery attacks

### Webhook Best Practices

1. **Idempotency**: Your webhook endpoint should be idempotent (safe to call multiple times)
2. **Response Handling**: Return a 2xx status code to acknowledge receipt. The API will retry on non-2xx responses.
3. **Timeout**: Ensure your endpoint responds within the timeout window (default 10 seconds)
4. **Security**: Use HTTPS for webhook URLs and validate the request source if needed

## Next Steps

- See [Usage Examples](usage-examples.md) for integration patterns
- Review [Configuration](CONFIGURATION.md) for API settings
- Check [Troubleshooting](TROUBLESHOOTING.md) for common issues
