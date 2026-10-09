"""Fixtures for testing model schemas and types."""

import pytest

from app.models.schemas import (CostMetrics, EnhancedJobData, ErrorResponse,
                                JobPriority, JobResponse, JobsListResponse,
                                JobStatus, JobStatusResponse, JobSummary,
                                Language, MediaTranscriptionRequest,
                                OutputFormat, TranscriptionRequest,
                                TranscriptionResponse, TranscriptSegment,
                                WorkerInfo, WorkerStatus)
from app.models.types import ErrorDict


@pytest.fixture
def sample_youtube_url():
    """Sample valid YouTube URL for testing."""
    return "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def sample_media_url():
    """Sample valid media URL for testing."""
    return "https://cdn.example.com/audio.mp3"


@pytest.fixture
def sample_webhook_url():
    """Sample valid webhook URL for testing."""
    return "https://example.com/webhook/callback"


@pytest.fixture
def sample_transcript_segment():
    """Sample transcript segment for testing."""
    return TranscriptSegment(text="Hello world", start=0.0, end=2.5)


@pytest.fixture
def sample_transcript_segments():
    """List of sample transcript segments for testing."""
    return [
        TranscriptSegment(text="Hello", start=0.0, end=1.0),
        TranscriptSegment(text="world", start=1.0, end=2.0),
        TranscriptSegment(text="How are you?", start=2.0, end=4.0),
    ]


@pytest.fixture
def sample_transcription_request(sample_youtube_url):
    """Sample TranscriptionRequest with minimal required fields."""
    return TranscriptionRequest(url=sample_youtube_url)


@pytest.fixture
def sample_transcription_request_full(sample_youtube_url, sample_webhook_url):
    """Sample TranscriptionRequest with all fields."""
    return TranscriptionRequest(
        url=sample_youtube_url,
        translate_to=Language.EN,
        format=OutputFormat.JSON,
        diarise=True,
        webhook_url=sample_webhook_url,
    )


@pytest.fixture
def sample_transcription_response(sample_transcript_segments):
    """Sample TranscriptionResponse for testing."""
    return TranscriptionResponse(
        status="completed",
        jobId=None,
        source="youtube_captions",
        language="en",
        confidence=0.95,
        transcript="Hello world How are you?",
        segments=sample_transcript_segments,
        warnings=[],
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )


@pytest.fixture
def sample_job_response():
    """Sample JobResponse for testing."""
    return JobResponse(
        job_id="123e4567-e89b-12d3-a456-426614174000",
        status=JobStatus.QUEUED,
        created_at="2024-01-01T12:00:00Z",
        video_id="dQw4w9WgXcQ",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )


@pytest.fixture
def sample_job_status_response_completed(sample_transcript_segments):
    """Sample JobStatusResponse for completed job."""
    return JobStatusResponse(
        job_id="123e4567-e89b-12d3-a456-426614174000",
        status=JobStatus.COMPLETED,
        created_at="2024-01-01T12:00:00Z",
        completed_at="2024-01-01T12:05:00Z",
        result={
            "status": "completed",
            "source": "asr",
            "language": "en",
            "transcript": "Hello world",
            "segments": [seg.model_dump() for seg in sample_transcript_segments],
        },
        error=None,
        video_id="dQw4w9WgXcQ",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        source="asr",
        language="en",
        confidence=0.95,
        transcript="Hello world",
        segments=sample_transcript_segments,
        warnings=[],
    )


@pytest.fixture
def sample_job_status_response_failed():
    """Sample JobStatusResponse for failed job."""
    return JobStatusResponse(
        job_id="123e4567-e89b-12d3-a456-426614174000",
        status=JobStatus.FAILED,
        created_at="2024-01-01T12:00:00Z",
        completed_at="2024-01-01T12:05:00Z",
        result=None,
        error="Transcription failed: Model not loaded",
        video_id="dQw4w9WgXcQ",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        source=None,
        language=None,
        confidence=None,
        transcript=None,
        segments=None,
        warnings=None,
    )


@pytest.fixture
def sample_job_summary():
    """Sample JobSummary for testing."""
    return JobSummary(
        job_id="123e4567-e89b-12d3-a456-426614174000",
        status="processing",
    )


@pytest.fixture
def sample_jobs_list_response(sample_job_summary):
    """Sample JobsListResponse for testing."""
    return JobsListResponse(
        jobs=[sample_job_summary],
        total=1,
    )


@pytest.fixture
def sample_error_response():
    """Sample ErrorResponse for testing."""
    return ErrorResponse(
        code="CAPTIONS_NOT_AVAILABLE",
        message="No captions available for this video",
        details={"video_id": "dQw4w9WgXcQ"},
    )


@pytest.fixture
def sample_worker_info():
    """Sample WorkerInfo for testing."""
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
def sample_enhanced_job_data():
    """Sample EnhancedJobData for testing."""
    return EnhancedJobData(
        job_id="job-123",
        priority=JobPriority.NORMAL,
        retry_count=0,
        max_retries=3,
        media_storage_path="s3://bucket/media/job-123.mp3",
        result_storage_path="s3://bucket/results/job-123.json",
        assigned_worker_id="worker-456",
        queue_position=5,
        estimated_processing_time=120.0,
    )


@pytest.fixture
def sample_cost_metrics():
    """Sample CostMetrics for testing."""
    return CostMetrics(
        total_gpu_hours=100.5,
        cost_per_job=0.05,
        total_cost=50.25,
        budget_remaining=49.75,
        jobs_processed=1005,
        active_workers=3,
    )


@pytest.fixture
def sample_media_transcription_request(sample_media_url):
    """Sample MediaTranscriptionRequest with minimal required fields."""
    return MediaTranscriptionRequest(url=sample_media_url)


@pytest.fixture
def sample_media_transcription_request_full(sample_media_url, sample_webhook_url):
    """Sample MediaTranscriptionRequest with all fields."""
    return MediaTranscriptionRequest(
        url=sample_media_url,
        translate_to=Language.ES,
        format=OutputFormat.SRT,
        diarise=False,
        webhook_url=sample_webhook_url,
    )


@pytest.fixture
def sample_error_dict():
    """Sample ErrorDict for testing."""
    return ErrorDict(
        code="TEST_ERROR",
        message="Test error message",
        details={"key": "value"},
    )


@pytest.fixture
def invalid_urls():
    """List of invalid URLs for testing validation."""
    return [
        "not-a-url",
        "ftp://example.com/file.mp3",
        "file:///local/path",
        "",
        "http://",
        "https://",
        "www.youtube.com",  # Missing protocol
    ]


@pytest.fixture
def valid_urls():
    """List of valid URLs for testing."""
    return [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://cdn.example.com/audio.mp3",
        "http://example.com/video.mp4",
        "https://subdomain.example.com/path/to/file.wav?param=value",
    ]


@pytest.fixture
def boundary_timestamps():
    """Boundary timestamp values for testing."""
    return {
        "zero": 0.0,
        "small_positive": 0.001,
        "large_positive": 999999.999,
        "negative": -1.0,
        "very_large": 1e10,
        "nan": float("nan"),
        "inf": float("inf"),
        "negative_inf": float("-inf"),
    }
