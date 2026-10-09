# Usage Examples

Practical code examples and integration patterns for the YouTube Transcription API.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Synchronous Transcription](#synchronous-transcription)
- [Asynchronous Jobs](#asynchronous-jobs)
- [Webhooks](#webhooks)
- [Error Handling](#error-handling)
- [Speaker Diarization](#speaker-diarization)
- [Language Translation](#language-translation)
- [Output Formats](#output-formats)
- [Media File Upload](#media-file-upload)
- [Integration Examples](#integration-examples)
- [Complete Example: Full Workflow](#complete-example-full-workflow)

## Basic Usage

### cURL

```bash
# Simple transcription request
curl -X POST "http://localhost:8000/v1/transcriptions/youtube" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "url=https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  -F "format=json"
```

### Python

```python
import requests

API_BASE_URL = "http://localhost:8000/v1"
API_KEY = "YOUR_API_KEY"

def transcribe_youtube(url: str, format: str = "json"):
    """Transcribe a YouTube video."""
    response = requests.post(
        f"{API_BASE_URL}/transcriptions/youtube",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={"url": (None, url), "format": (None, format)}
    )
    response.raise_for_status()
    return response.json()

# Usage
result = transcribe_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(result["transcript"])
```

### JavaScript/Node.js

```javascript
const FormData = require('form-data');
const axios = require('axios');

const API_BASE_URL = 'http://localhost:8000/v1';
const API_KEY = 'YOUR_API_KEY';

async function transcribeYouTube(url, format = 'json') {
  const form = new FormData();
  form.append('url', url);
  form.append('format', format);

  const response = await axios.post(
    `${API_BASE_URL}/transcriptions/youtube`,
    form,
    {
      headers: {
        ...form.getHeaders(),
        'Authorization': `Bearer ${API_KEY}`
      }
    }
  );

  return response.data;
}

// Usage
transcribeYouTube('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
  .then(result => console.log(result.transcript))
  .catch(error => console.error(error));
```

## Synchronous Transcription

**Important**: Synchronous transcription only applies to:
- YouTube videos processed via ASR (when captions unavailable or diarization requested)
- AND video duration is less than 5 minutes

When YouTube captions are available and diarization is not requested, the response is always synchronous regardless of video length (up to 1 hour limit).

For videos 5-60 minutes processed via ASR, or all media file uploads, transcription is asynchronous and returns a job ID.

### Python Example

```python
import requests

def transcribe_sync(url: str):
    """Synchronous transcription for short videos."""
    response = requests.post(
        "http://localhost:8000/v1/transcriptions/youtube",
        headers={"Authorization": "Bearer YOUR_API_KEY"},
        files={"url": (None, url), "format": (None, "json")}
    )
    
    if response.status_code == 200:
        data = response.json()
        # Check if response is synchronous (has transcript) or async (has jobId)
        if "transcript" in data:
            # Synchronous response - transcription completed immediately
            return data
        elif "jobId" in data:
            # Asynchronous response - need to poll for results
            return {"jobId": data["jobId"], "status": data.get("status", "queued")}
    else:
        response.raise_for_status()

# Usage
result = transcribe_sync("https://www.youtube.com/watch?v=SHORT_VIDEO_ID")
if "transcript" in result:
    print(f"Transcript: {result['transcript']}")
    print(f"Language: {result['language']}")
    print(f"Confidence: {result.get('confidence', 'N/A')}")
```

## Asynchronous Jobs

Transcription is processed asynchronously in these cases:
- YouTube videos 5-60 minutes processed via ASR (when captions unavailable or diarization requested)
- All media file uploads (regardless of duration)
- All remote media URLs

You receive a job ID and must poll for results. Jobs progress through states: `queued` → `processing` → `completed` or `failed`.

### Python Example

```python
import requests
import time

API_BASE_URL = "http://localhost:8000/v1"
API_KEY = "YOUR_API_KEY"

def create_transcription_job(url: str):
    """Create an async transcription job."""
    response = requests.post(
        f"{API_BASE_URL}/transcriptions/youtube",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={"url": (None, url), "format": (None, "json")}
    )
    response.raise_for_status()
    return response.json()

def get_job_status(job_id: str, stream: bool = False):
    """Get status of a transcription job.
    
    Args:
        job_id: Job identifier
        stream: If True and result is large (>1MB), streams the response
    """
    params = {"stream": stream} if stream else {}
    response = requests.get(
        f"{API_BASE_URL}/jobs/{job_id}",
        headers={"Authorization": f"Bearer {API_KEY}"},
        params=params
    )
    response.raise_for_status()
    return response.json()

def wait_for_job(job_id: str, poll_interval: int = 5, max_wait: int = 3600):
    """Wait for job to complete, polling periodically."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status = get_job_status(job_id)
        
        if status["status"] == "completed":
            # Result is in the 'result' field for completed jobs
            return status.get("result") or status
        elif status["status"] == "failed":
            error_msg = status.get("error", "Unknown error")
            raise Exception(f"Job failed: {error_msg}")
        elif status["status"] in ["queued", "processing"]:
            print(f"Job {status['status']}, waiting...")
            time.sleep(poll_interval)
        else:
            raise Exception(f"Unknown job status: {status['status']}")
    
    raise TimeoutError("Job did not complete within timeout")

# Usage
job = create_transcription_job("https://www.youtube.com/watch?v=LONG_VIDEO_ID")
job_id = job["jobId"]
print(f"Job created: {job_id}")

try:
    result = wait_for_job(job_id)
    # Handle both direct result and nested result structure
    transcript_data = result.get("result", result) if isinstance(result, dict) else result
    print(f"Transcript: {transcript_data.get('transcript', 'N/A')}")
    print(f"Language: {transcript_data.get('language', 'N/A')}")
    print(f"Confidence: {transcript_data.get('confidence', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")
```

### JavaScript Example

```javascript
async function createTranscriptionJob(url) {
  const form = new FormData();
  form.append('url', url);
  form.append('format', 'json');

  const response = await axios.post(
    `${API_BASE_URL}/transcriptions/youtube`,
    form,
    {
      headers: {
        ...form.getHeaders(),
        'Authorization': `Bearer ${API_KEY}`
      }
    }
  );

  return response.data;
}

async function getJobStatus(jobId) {
  const response = await axios.get(
    `${API_BASE_URL}/jobs/${jobId}`,
    {
      headers: {
        'Authorization': `Bearer ${API_KEY}`
      }
    }
  );

  return response.data;
}

async function waitForJob(jobId, pollInterval = 5000, maxWait = 3600000) {
  const startTime = Date.now();

  while (Date.now() - startTime < maxWait) {
    const status = await getJobStatus(jobId);

    if (status.status === 'completed') {
      return status.result;
    } else if (status.status === 'failed') {
      throw new Error(`Job failed: ${status.error || 'Unknown error'}`);
    } else if (['queued', 'processing'].includes(status.status)) {
      console.log(`Job ${status.status}, waiting...`);
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    } else {
      throw new Error(`Unknown job status: ${status.status}`);
    }
  }

  throw new Error('Job did not complete within timeout');
}

// Usage
const job = await createTranscriptionJob('https://www.youtube.com/watch?v=LONG_VIDEO_ID');
const jobId = job.jobId;
console.log(`Job created: ${jobId}`);

try {
  const result = await waitForJob(jobId);
  console.log(`Transcript: ${result.transcript}`);
} catch (error) {
  console.error(`Error: ${error.message}`);
}
```

## Webhooks

Instead of polling, you can provide a webhook URL to receive results when the job completes.

### Python Example

```python
def create_job_with_webhook(url: str, webhook_url: str):
    """Create transcription job with webhook callback."""
    response = requests.post(
        f"{API_BASE_URL}/transcriptions/youtube",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={
            "url": (None, url),
            "format": (None, "json"),
            "webhookUrl": (None, webhook_url)
        }
    )
    response.raise_for_status()
    return response.json()

# Usage
job = create_job_with_webhook(
    "https://www.youtube.com/watch?v=VIDEO_ID",
    "https://your-server.com/webhook/transcription-complete"
)
print(f"Job created: {job['jobId']}")
```

### Webhook Handler Example (Flask)

```python
from flask import Flask, request, jsonify
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/webhook/transcription-complete', methods=['POST'])
def handle_transcription_webhook():
    """Handle transcription completion webhook.
    
    The API will POST to this endpoint when a job completes.
    Always return 2xx status to acknowledge receipt.
    """
    try:
        data = request.json
        
        if not data:
            logging.warning("Received empty webhook payload")
            return jsonify({"status": "received", "error": "empty payload"}), 200
        
        job_id = data.get("jobId")
        status = data.get("status")
        result = data.get("result")
        
        if status == "completed" and result:
            # Process transcription result
            transcript = result.get("transcript", "")
            language = result.get("language", "unknown")
            confidence = result.get("confidence")
            segments = result.get("segments", [])
            
            # Save to database, send notification, etc.
            logging.info(f"Job {job_id} completed: {len(transcript)} chars, language: {language}")
            
            # Example: Save to database
            # save_transcription_to_db(job_id, transcript, language, segments)
            
            return jsonify({"status": "received", "job_id": job_id}), 200
        elif status == "failed":
            # Handle failed jobs
            error = data.get("error", "Unknown error")
            logging.error(f"Job {job_id} failed: {error}")
            
            # Example: Notify user, log error, etc.
            return jsonify({"status": "received", "job_id": job_id}), 200
        else:
            logging.warning(f"Unexpected webhook payload: {data}")
            return jsonify({"status": "received"}), 200
            
    except Exception as e:
        logging.error(f"Error processing webhook: {e}", exc_info=True)
        # Still return 200 to prevent retries for processing errors
        return jsonify({"status": "received", "error": str(e)}), 200

if __name__ == '__main__':
    # Use HTTPS in production for webhook security
    app.run(port=5000, ssl_context='adhoc' if app.debug else None)
```

**Webhook Best Practices:**
- Always return 2xx status codes to acknowledge receipt (prevents retries)
- Make your endpoint idempotent (safe to call multiple times)
- Respond quickly (< 10 seconds) to avoid timeouts
- Use HTTPS in production
- Validate webhook payload structure
- Log all webhook events for debugging

## Error Handling

### Python Example

```python
import requests
from requests.exceptions import HTTPError, RequestException

def transcribe_with_error_handling(url: str):
    """Transcribe with comprehensive error handling."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/transcriptions/youtube",
            headers={"Authorization": f"Bearer {API_KEY}"},
            files={"url": (None, url), "format": (None, "json")},
            timeout=300  # 5 minute timeout
        )
        
        # Check for HTTP errors
        if response.status_code == 429:
            error_data = response.json()
            retry_after = error_data.get("details", {}).get("retry_after", 60)
            raise Exception(f"Rate limit exceeded. Retry after {retry_after} seconds")
        
        response.raise_for_status()
        return response.json()
        
    except HTTPError as e:
        # Handle API errors
        error_data = e.response.json() if e.response.headers.get('content-type', '').startswith('application/json') else {}
        code = error_data.get("code", "UNKNOWN_ERROR")
        message = error_data.get("message", e.response.text)
        
        if e.response.status_code == 400:
            if code == "VIDEO_NOT_FOUND":
                raise Exception("Video not found on YouTube")
            elif code == "VIDEO_UNAVAILABLE":
                raise Exception("Video is unavailable (deleted, private, etc.)")
            elif code == "CAPTIONS_NOT_AVAILABLE":
                raise Exception("No captions available for this video")
            elif code == "CAPTIONS_DISABLED":
                raise Exception("Captions are disabled for this video")
            elif code == "IP_BLOCKED":
                raise Exception("YouTube is blocking requests from this IP. Try again later.")
            elif code == "VIDEO_TOO_LONG":
                raise Exception("Video exceeds maximum duration (1 hour)")
            elif code == "INVALID_VIDEO_URL":
                raise Exception(f"Invalid YouTube URL: {message}")
            else:
                raise Exception(f"API error ({code}): {message}")
        elif e.response.status_code == 401:
            raise Exception("Authentication failed. Check your API key.")
        elif e.response.status_code == 429:
            retry_after = error_data.get("details", {}).get("retry_after", 60)
            raise Exception(f"Rate limit exceeded. Retry after {retry_after} seconds")
        
        raise Exception(f"API error ({e.response.status_code}): {message}")
        
    except RequestException as e:
        # Handle network errors
        raise Exception(f"Network error: {str(e)}")

# Usage
try:
    result = transcribe_with_error_handling("https://www.youtube.com/watch?v=VIDEO_ID")
    print(f"Success: {result['transcript']}")
except Exception as e:
    print(f"Error: {e}")
```

## Speaker Diarization

Speaker diarization identifies different speakers in the audio. When enabled, it forces ASR processing even if captions are available.

### Python Example

```python
def transcribe_with_diarization(url: str):
    """Transcribe with speaker diarization enabled."""
    response = requests.post(
        f"{API_BASE_URL}/transcriptions/youtube",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={
            "url": (None, url),
            "format": (None, "json"),
            "diarise": (None, "true")  # Enable diarization
        }
    )
    response.raise_for_status()
    return response.json()

# Usage
result = transcribe_with_diarization("https://www.youtube.com/watch?v=VIDEO_ID")
# Note: Diarization forces ASR mode, so may return jobId for longer videos
if "jobId" in result:
    print(f"Job created: {result['jobId']} (poll for results)")
else:
    print(f"Transcript: {result['transcript']}")
    # Segments may include speaker information if available
```

## Language Translation

### Python Example

```python
def transcribe_and_translate(url: str, target_language: str = "en"):
    """Transcribe video and translate to target language."""
    response = requests.post(
        f"{API_BASE_URL}/transcriptions/youtube",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={
            "url": (None, url),
            "format": (None, "json"),
            "translateTo": (None, target_language)
        }
    )
    response.raise_for_status()
    return response.json()

# Usage
# Original language (auto-detected)
result = transcribe_and_translate("https://www.youtube.com/watch?v=VIDEO_ID")
print(f"Original language: {result['language']}")

# Translate to English
result_en = transcribe_and_translate("https://www.youtube.com/watch?v=VIDEO_ID", "en")
print(f"English transcript: {result_en['transcript']}")

# Translate to Spanish
result_es = transcribe_and_translate("https://www.youtube.com/watch?v=VIDEO_ID", "es")
print(f"Spanish transcript: {result_es['transcript']}")
```

## Output Formats

### JSON Format (Default)

```python
result = transcribe_youtube(url, format="json")
# Returns full metadata with segments
print(result["transcript"])
print(result["segments"])
print(result["confidence"])
```

### Text Format

```python
response = requests.post(
    f"{API_BASE_URL}/transcriptions/youtube",
    headers={"Authorization": f"Bearer {API_KEY}"},
    files={"url": (None, url), "format": (None, "text")}
)
response.raise_for_status()

# Text format returns plain text with Content-Disposition header
transcript_text = response.text
print(transcript_text)

# Save to file
with open("transcript.txt", "w", encoding="utf-8") as f:
    f.write(transcript_text)
```

### SRT Format (Subtitles)

```python
response = requests.post(
    f"{API_BASE_URL}/transcriptions/youtube",
    headers={"Authorization": f"Bearer {API_KEY}"},
    files={"url": (None, url), "format": (None, "srt")}
)
response.raise_for_status()

# SRT format returns SubRip subtitle format
srt_content = response.text

# Save to file
with open("subtitles.srt", "w", encoding="utf-8") as f:
    f.write(srt_content)
```

### VTT Format (WebVTT)

```python
response = requests.post(
    f"{API_BASE_URL}/transcriptions/youtube",
    headers={"Authorization": f"Bearer {API_KEY}"},
    files={"url": (None, url), "format": (None, "vtt")}
)
response.raise_for_status()

# VTT format returns WebVTT subtitle format
vtt_content = response.text

# Save to file
with open("subtitles.vtt", "w", encoding="utf-8") as f:
    f.write(vtt_content)
```

### Handling Large Results (Streaming)

For large job results (>1MB), you can use the `stream` parameter to avoid loading the entire response into memory:

```python
def get_large_job_result(job_id: str):
    """Get large job result with streaming."""
    response = requests.get(
        f"{API_BASE_URL}/jobs/{job_id}",
        headers={"Authorization": f"Bearer {API_KEY}"},
        params={"stream": True},
        stream=True  # Enable streaming for response
    )
    response.raise_for_status()
    
    # For streamed responses, save directly to file
    if response.headers.get('content-disposition'):
        filename = response.headers['content-disposition'].split('filename=')[1].strip('"')
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return filename
    else:
        # Normal JSON response
        return response.json()
```

## Media File Upload

**Important**: All media file uploads are processed asynchronously. The endpoint always returns a job ID that you must poll for results.

### Python Example

```python
import os
import requests
import time

def transcribe_uploaded_file(file_path: str):
    """Transcribe an uploaded media file. Returns job ID for polling."""
    with open(file_path, "rb") as f:
        files = {
            "file": (os.path.basename(file_path), f)
        }
        data = {
            "format": "json"
        }
        
        response = requests.post(
            f"{API_BASE_URL}/transcriptions/media",
            headers={"Authorization": f"Bearer {API_KEY}"},
            files=files,
            data=data
        )
        response.raise_for_status()
        return response.json()  # Returns JobResponse with jobId

# Usage - must poll for results
job = transcribe_uploaded_file("audio.mp3")
job_id = job["jobId"]
print(f"Job created: {job_id}")

# Poll for results (see Asynchronous Jobs section for complete example)
status = get_job_status(job_id)
while status["status"] in ["queued", "processing"]:
    time.sleep(5)
    status = get_job_status(job_id)

if status["status"] == "completed":
    result = status.get("result", {})
    print(f"Transcript: {result.get('transcript', 'N/A')}")
```

### Remote URL Example

```python
def transcribe_remote_media(url: str):
    """Transcribe media from remote URL. Returns job ID for polling."""
    response = requests.post(
        f"{API_BASE_URL}/transcriptions/media",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={"url": (None, url), "format": (None, "json")}
    )
    response.raise_for_status()
    return response.json()  # Returns JobResponse with jobId

# Usage - must poll for results
job = transcribe_remote_media("https://cdn.example.com/audio.mp3")
job_id = job["jobId"]
print(f"Job created: {job_id}")

# Poll for results (see Asynchronous Jobs section for complete example)
# ... polling code same as above ...
```

## Integration Examples

### Django Integration

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests

@csrf_exempt
def transcribe_video(request):
    if request.method == 'POST':
        url = request.POST.get('url')
        api_key = request.session.get('api_key')  # Store API key in session
        
        try:
            response = requests.post(
                'http://localhost:8000/v1/transcriptions/youtube',
                headers={'Authorization': f'Bearer {api_key}'},
                files={'url': (None, url), 'format': (None, 'json')},
                timeout=300
            )
            response.raise_for_status()
            return JsonResponse(response.json())
        except requests.exceptions.RequestException as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
```

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException, Form, Header
import httpx

app = FastAPI()

@app.post("/api/transcribe")
async def transcribe(
    url: str = Form(...),
    authorization: str = Header(...)
):
    """Proxy transcription request."""
    api_key = authorization.replace("Bearer ", "")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            "http://localhost:8000/v1/transcriptions/youtube",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"url": (None, url), "format": (None, "json")}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )
        
        return response.json()
```

### React Integration

```javascript
// TranscriptionService.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/v1';
const API_KEY = process.env.REACT_APP_API_KEY;

export const transcribeYouTube = async (url, format = 'json') => {
  const formData = new FormData();
  formData.append('url', url);
  formData.append('format', format);

  try {
    const response = await axios.post(
      `${API_BASE_URL}/transcriptions/youtube`,
      formData,
      {
        headers: {
          'Authorization': `Bearer ${API_KEY}`,
          'Content-Type': 'multipart/form-data'
        }
      }
    );

    return response.data;
  } catch (error) {
    if (error.response) {
      const errorData = error.response.data;
      const errorMessage = errorData.message || errorData.detail || 'Transcription failed';
      const errorCode = errorData.code || 'UNKNOWN_ERROR';
      throw new Error(`${errorCode}: ${errorMessage}`);
    }
    throw error;
  }
};

// Component.jsx
import React, { useState } from 'react';
import { transcribeYouTube } from './TranscriptionService';

function TranscriptionForm() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const data = await transcribeYouTube(url);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="YouTube URL"
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Transcribing...' : 'Transcribe'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
      {result && (
        <div>
          <h3>Transcript:</h3>
          <p>{result.transcript}</p>
        </div>
      )}
    </div>
  );
}
```

## Complete Example: Full Workflow

Here's a complete example that handles both synchronous and asynchronous responses:

```python
import requests
import time
from typing import Dict, Optional

API_BASE_URL = "http://localhost:8000/v1"
API_KEY = "YOUR_API_KEY"

def transcribe_video(url: str, format: str = "json", translate_to: Optional[str] = None, 
                     diarise: bool = False, webhook_url: Optional[str] = None) -> Dict:
    """Transcribe a YouTube video with full feature support.
    
    Args:
        url: YouTube video URL
        format: Output format (json, text, srt, vtt)
        translate_to: Target language code for translation (ISO 639-1)
        diarise: Enable speaker diarization
        webhook_url: Optional webhook callback URL
        
    Returns:
        Transcription result or job information
    """
    files = {
        "url": (None, url),
        "format": (None, format),
    }
    
    if translate_to:
        files["translateTo"] = (None, translate_to)
    if diarise:
        files["diarise"] = (None, "true")
    if webhook_url:
        files["webhookUrl"] = (None, webhook_url)
    
    response = requests.post(
        f"{API_BASE_URL}/transcriptions/youtube",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files=files,
        timeout=300
    )
    response.raise_for_status()
    
    # Handle different response types
    if format == "json":
        return response.json()
    else:
        # Text/SRT/VTT formats return plain text
        return {"content": response.text, "format": format}

def poll_job_until_complete(job_id: str, poll_interval: int = 5, 
                            max_wait: int = 3600) -> Dict:
    """Poll job status until completion."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = requests.get(
            f"{API_BASE_URL}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        response.raise_for_status()
        status = response.json()
        
        if status["status"] == "completed":
            return status.get("result", status)
        elif status["status"] == "failed":
            raise Exception(f"Job failed: {status.get('error', 'Unknown error')}")
        elif status["status"] in ["queued", "processing"]:
            print(f"Job {status['status']}, waiting...")
            time.sleep(poll_interval)
        else:
            raise Exception(f"Unknown job status: {status['status']}")
    
    raise TimeoutError("Job did not complete within timeout")

# Usage example
try:
    # Try synchronous transcription first
    result = transcribe_video(
        "https://www.youtube.com/watch?v=VIDEO_ID",
        format="json",
        translate_to="en"
    )
    
    # Check if we got a job ID (async) or direct result (sync)
    if "jobId" in result:
        print(f"Job created: {result['jobId']}, polling for results...")
        result = poll_job_until_complete(result["jobId"])
    
    # Process result
    print(f"Transcript: {result.get('transcript', 'N/A')[:200]}...")
    print(f"Language: {result.get('language', 'N/A')}")
    print(f"Confidence: {result.get('confidence', 'N/A')}")
    print(f"Segments: {len(result.get('segments', []))}")
    
except requests.exceptions.HTTPError as e:
    error_data = e.response.json() if e.response.headers.get('content-type', '').startswith('application/json') else {}
    print(f"Error: {error_data.get('code', 'UNKNOWN')} - {error_data.get('message', str(e))}")
except Exception as e:
    print(f"Error: {e}")
```

## Next Steps

- Review [API Reference](api-reference.md) for complete endpoint documentation
- Check [Configuration](CONFIGURATION.md) for API settings
- See [Troubleshooting](TROUBLESHOOTING.md) for common issues
- Review [Features Documentation](features.md) for advanced capabilities
