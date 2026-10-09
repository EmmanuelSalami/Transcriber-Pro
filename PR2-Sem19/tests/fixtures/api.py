"""Fixtures for testing API endpoints."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, Request, UploadFile
from starlette.datastructures import Headers

from app.models.schemas import (ErrorResponse, OutputFormat, WorkerInfo,
                                WorkerStatus)


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object with Authorization header."""
    request = Mock(spec=Request)
    request.method = "POST"
    request.url.path = "/v1/transcriptions/youtube"
    request.url.query = ""
    request.client = Mock()
    request.client.host = "127.0.0.1"
    request.headers = Headers({"Authorization": "Bearer test-api-key"})
    return request


@pytest.fixture
def mock_request_no_auth():
    """Create a mock FastAPI Request object without Authorization header."""
    request = Mock(spec=Request)
    request.method = "POST"
    request.url.path = "/v1/transcriptions/youtube"
    request.url.query = ""
    request.client = Mock()
    request.client.host = "127.0.0.1"
    request.headers = Headers()
    return request


@pytest.fixture
def mock_background_tasks():
    """Create a mock BackgroundTasks object."""
    tasks = Mock(spec=BackgroundTasks)
    tasks.add_task = Mock()
    return tasks


@pytest.fixture
def mock_upload_file():
    """Create a mock UploadFile for testing file uploads."""
    file = Mock(spec=UploadFile)
    file.filename = "test_audio.mp3"
    file.content_type = "audio/mpeg"
    file.size = 1024 * 1024  # 1MB
    file.read = AsyncMock(return_value=b"fake audio content")
    file.file = Mock()
    file.file.read = AsyncMock(return_value=b"fake audio content")
    return file


@pytest.fixture
def mock_upload_file_large():
    """Create a mock UploadFile with large size for testing."""
    file = Mock(spec=UploadFile)
    file.filename = "large_audio.mp3"
    file.content_type = "audio/mpeg"
    file.size = 600 * 1024 * 1024  # 600MB (exceeds limit)
    file.read = AsyncMock(return_value=b"x" * (600 * 1024 * 1024))
    file.file = Mock()
    file.file.read = AsyncMock(return_value=b"x" * (600 * 1024 * 1024))
    return file


@pytest.fixture
def mock_upload_file_invalid_type():
    """Create a mock UploadFile with invalid file type."""
    file = Mock(spec=UploadFile)
    file.filename = "test_document.pdf"
    file.content_type = "application/pdf"
    file.size = 1024
    file.read = AsyncMock(return_value=b"fake pdf content")
    file.file = Mock()
    file.file.read = AsyncMock(return_value=b"fake pdf content")
    return file


@pytest.fixture
def mock_transcription_service():
    """Create a mock TranscriptionService instance."""
    service = Mock()
    service.transcribe = AsyncMock()
    service.job_manager = Mock()
    service.audio_service = Mock()
    service.whisper_service = Mock()
    return service


@pytest.fixture
def mock_media_endpoint_service():
    """Create a mock MediaEndpointService instance."""
    service = Mock()
    service.handle_file_upload = AsyncMock()
    service.handle_remote_url = AsyncMock()
    service.is_level3_enabled = Mock(return_value=False)
    service.process_level3_job = AsyncMock()
    service.process_media_upload_background = AsyncMock()
    service.process_media_url_background = AsyncMock()
    service.create_job_response = Mock()
    return service


@pytest.fixture
def mock_job_manager():
    """Create a mock JobManager instance."""
    manager = Mock()
    manager.get_job = Mock()
    manager.get_all_jobs = Mock(return_value={})
    manager.update_job_status = Mock()
    manager.schedule_async_transcription = Mock()
    manager.create_job = Mock(return_value=("test-job-id", {"status": "queued"}))
    return manager


@pytest.fixture
def mock_worker_manager():
    """Create a mock WorkerManager instance."""
    manager = Mock()
    manager.register_worker = Mock()
    manager.heartbeat = Mock()
    manager.get_all_workers = Mock(return_value=[])
    manager.get_worker = Mock(return_value=None)
    manager.scale_workers = AsyncMock(return_value=5)
    manager.auto_scale_workers = AsyncMock(return_value=5)
    manager.test_connection = AsyncMock(return_value={"connected": True})
    manager.close = AsyncMock()
    return manager


@pytest.fixture
def mock_queue_service():
    """Create a mock QueueService instance."""
    service = Mock()
    service.get_queue_stats = Mock(return_value={"pending": 0, "processing": 0, "completed": 0})
    return service


@pytest.fixture
def sample_transcription_result_sync():
    """Sample transcription result for synchronous processing."""
    return {
        "status": "completed",
        "jobId": None,
        "source": "youtube_captions",
        "language": "en",
        "confidence": 0.95,
        "transcript": "Hello world",
        "segments": [
            {"text": "Hello", "start": 0.0, "end": 1.0},
            {"text": "world", "start": 1.0, "end": 2.0},
        ],
        "warnings": [],
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }


@pytest.fixture
def sample_transcription_result_async():
    """Sample transcription result for asynchronous processing."""
    job_id = str(uuid4())
    return {
        "status": "queued",
        "jobId": job_id,
        "created_at": "2024-01-01T12:00:00Z",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }


@pytest.fixture
def sample_job_data():
    """Sample job data from JobManager."""
    return {
        "job_id": "test-job-id",
        "status": "processing",
        "created_at": 1704067200.0,
        "completed_at": None,
        "error": None,
        "video_id": "dQw4w9WgXcQ",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }


@pytest.fixture
def sample_job_data_completed():
    """Sample completed job data."""
    return {
        "job_id": "test-job-id",
        "status": "completed",
        "created_at": 1704067200.0,
        "completed_at": 1704067300.0,
        "error": None,
        "video_id": "dQw4w9WgXcQ",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "result": {
            "status": "completed",
            "source": "asr",
            "language": "en",
            "transcript": "Hello world",
            "segments": [
                {"text": "Hello", "start": 0.0, "end": 1.0},
                {"text": "world", "start": 1.0, "end": 2.0},
            ],
        },
    }


@pytest.fixture
def sample_file_upload_result():
    """Sample result from handle_file_upload."""
    return Mock(
        error=None,
        job_id="test-job-id",
        file_path="/tmp/test_audio.mp3",
        job={"status": "queued", "job_id": "test-job-id"},
        video_id=None,
        metadata={"filename": "test_audio.mp3", "size": 1024 * 1024},
        params={"format": OutputFormat.JSON, "translate_to": None},
    )


@pytest.fixture
def sample_url_upload_result():
    """Sample result from handle_remote_url."""
    return Mock(
        error=None,
        job_id="test-job-id",
        file_path=None,
        url="https://cdn.example.com/audio.mp3",
        job={"status": "queued", "job_id": "test-job-id"},
        video_id=None,
        metadata={"url": "https://cdn.example.com/audio.mp3"},
        params={"format": OutputFormat.JSON, "translate_to": None},
    )


@pytest.fixture
def sample_worker():
    """Sample WorkerInfo object."""
    return WorkerInfo(
        worker_id="worker-123",
        status=WorkerStatus.IDLE,
        runpod_pod_id="pod-abc",
        gpu_type="RTX 4090",
        current_job_id=None,
        last_heartbeat="2024-01-01T12:00:00Z",
        model_loaded=True,
        jobs_processed=10,
        total_gpu_hours=2.5,
    )


@pytest.fixture
def sample_worker_warming_up():
    """Sample WorkerInfo object in warming up state."""
    return WorkerInfo(
        worker_id="worker-456",
        status=WorkerStatus.WARMING_UP,
        runpod_pod_id="pod-def",
        gpu_type="A100",
        current_job_id=None,
        last_heartbeat="2024-01-01T12:00:00Z",
        model_loaded=False,
        jobs_processed=0,
        total_gpu_hours=0.0,
    )


@pytest.fixture
def sample_worker_processing():
    """Sample WorkerInfo object processing a job."""
    return WorkerInfo(
        worker_id="worker-789",
        status=WorkerStatus.BUSY,
        runpod_pod_id="pod-ghi",
        gpu_type="RTX 4090",
        current_job_id="job-123",
        last_heartbeat="2024-01-01T12:00:00Z",
        model_loaded=True,
        jobs_processed=5,
        total_gpu_hours=1.2,
    )


@pytest.fixture
def valid_youtube_urls():
    """List of valid YouTube URLs for testing."""
    return [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
    ]


@pytest.fixture
def invalid_youtube_urls():
    """List of invalid YouTube URLs for testing."""
    return [
        "not-a-url",
        "https://example.com/video",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com",
        "",
        "https://vimeo.com/123456",
    ]


@pytest.fixture
def valid_media_urls():
    """List of valid media URLs for testing."""
    return [
        "https://cdn.example.com/audio.mp3",
        "http://example.com/video.mp4",
        "https://s3.amazonaws.com/bucket/file.wav?X-Amz-Signature=abc123",
        "https://storage.googleapis.com/bucket/audio.m4a",
    ]


@pytest.fixture
def invalid_media_urls():
    """List of invalid media URLs for testing."""
    return [
        "not-a-url",
        "ftp://example.com/file.mp3",
        "file:///local/path/audio.mp3",
        "",
        "javascript:alert('xss')",
    ]


@pytest.fixture
def valid_output_formats():
    """List of valid output formats."""
    return ["json", "text", "srt", "vtt"]


@pytest.fixture
def invalid_output_formats():
    """List of invalid output formats."""
    return ["xml", "csv", "pdf", "html", ""]


@pytest.fixture
def valid_language_codes():
    """List of valid language codes (ISO 639-1)."""
    return ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]


@pytest.fixture
def invalid_language_codes():
    """List of invalid language codes."""
    return ["xx", "invalid", "123", "en-US", "english", ""]


@pytest.fixture
def boundary_url_lengths():
    """Boundary values for URL length testing."""
    return {
        "min": "https://youtu.be/a",
        "max_valid": "https://www.youtube.com/watch?v=" + "a" * 100,
        "too_long": "https://www.youtube.com/watch?v=" + "a" * 10000,
    }


@pytest.fixture
def boundary_file_sizes():
    """Boundary values for file size testing."""
    return {
        "zero": 0,
        "small": 1024,  # 1KB
        "medium": 10 * 1024 * 1024,  # 10MB
        "large": 100 * 1024 * 1024,  # 100MB
        "max_allowed": 500 * 1024 * 1024,  # 500MB
        "too_large": 600 * 1024 * 1024,  # 600MB (exceeds limit)
    }


@pytest.fixture
def sample_error_response():
    """Sample ErrorResponse for testing."""
    return ErrorResponse(
        code="TEST_ERROR",
        message="Test error message",
        details={"key": "value"},
    )


@pytest.fixture
def sample_large_result():
    """Sample large transcription result for streaming tests."""
    # Create a result that exceeds 1MB when serialized
    large_segments = [
        {"text": f"Segment {i} " * 100, "start": float(i), "end": float(i + 1)} for i in range(1000)
    ]
    return {
        "status": "completed",
        "jobId": None,
        "source": "asr",
        "language": "en",
        "confidence": 0.95,
        "transcript": " ".join([seg["text"] for seg in large_segments]),
        "segments": large_segments,
        "warnings": [],
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
