"""Fixtures for testing job services (JobManager, QueueService, WorkerManager)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import pytest
from redis import Redis

from app.models.schemas import (EnhancedJobData, JobPriority, JobStatus,
                                WorkerInfo, WorkerStatus)


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing."""
    mock_client = MagicMock(spec=Redis)
    mock_client.ping = Mock(return_value=True)
    mock_client.get = Mock(return_value=None)
    mock_client.set = Mock(return_value=True)
    mock_client.setex = Mock(return_value=True)
    mock_client.delete = Mock(return_value=1)
    mock_client.zadd = Mock(return_value=1)
    mock_client.zcard = Mock(return_value=0)
    mock_client.zrank = Mock(return_value=None)
    mock_client.bzpopmin = Mock(return_value=None)
    mock_client.scan = Mock(return_value=(0, []))
    mock_client.keys = Mock(return_value=[])
    mock_client.llen = Mock(return_value=0)
    mock_client.lpush = Mock(return_value=1)
    mock_client.pipeline = Mock(return_value=Mock(execute=Mock(return_value=[])))
    return mock_client


@pytest.fixture
def mock_redis_connection_pool():
    """Create a mock Redis connection pool."""
    mock_pool = Mock()
    mock_pool.max_connections = 50
    return mock_pool


@pytest.fixture
def mock_settings_redis_disabled():
    """Mock settings with Redis disabled."""
    settings = MagicMock()
    settings.redis_enabled = False
    settings.redis_host = "localhost"
    settings.redis_port = 6379
    settings.redis_db = 0
    settings.redis_password = None
    settings.redis_socket_timeout = 5.0
    settings.redis_socket_connect_timeout = 5.0
    settings.redis_pool_max_connections = 50
    settings.redis_key_prefix = "job:"
    settings.redis_scan_count = 100
    settings.temp_store_dir = "/tmp/test_temp_store"
    settings.job_ttl_seconds = 3600
    settings.job_list_cache_ttl = 60
    settings.result_file_extension = "json"
    settings.s3_enabled = False
    settings.queue_backend = "redis"
    settings.queue_name = "transcription"
    settings.queue_visibility_timeout_seconds = 300
    settings.queue_max_retries = 3
    settings.runpod_api_key = None
    settings.runpod_template_id = None
    settings.runpod_api_url = "https://api.runpod.io/graphql"
    settings.worker_health_check_timeout_seconds = 60
    settings.worker_auto_scaling_enabled = False
    settings.worker_scale_up_queue_depth = 10
    settings.worker_scale_down_queue_depth = 5
    settings.worker_idle_timeout_seconds = 300
    settings.min_workers = 1
    settings.max_workers = 10
    # Add any other settings attributes that might be accessed
    settings.api_keys = ""
    settings.secret_key = ""
    settings.dev_mode = False
    settings.s3_enabled = False  # Ensure this is set
    return settings


@pytest.fixture
def mock_settings_redis_enabled(mock_settings_redis_disabled):
    """Mock settings with Redis enabled."""
    settings = mock_settings_redis_disabled
    settings.redis_enabled = True
    return settings


@pytest.fixture
def mock_s3_storage():
    """Create a mock S3 storage service."""
    mock_storage = Mock()
    mock_storage.is_enabled = Mock(return_value=True)
    mock_storage.upload_result = Mock(return_value="s3://bucket/results/job-123.json")
    mock_storage.upload_media = Mock(return_value="s3://bucket/media/job-123.mp3")
    mock_storage.download_result = Mock(return_value={"transcript": "test"})
    return mock_storage


@pytest.fixture
def sample_job_data():
    """Sample minimal job data dictionary."""
    return {
        "job_id": "123e4567-e89b-12d3-a456-426614174000",
        "status": JobStatus.QUEUED.value,
        "video_id": "dQw4w9WgXcQ",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "translate_to": None,
        "format": "json",
        "diarise": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "resultRef": None,
        "progress": None,
        "language": None,
        "model": None,
        "duration": None,
        "source": None,
        "error": None,
        "webhook_url": None,
    }


@pytest.fixture
def sample_job_data_processing(sample_job_data):
    """Sample job data in PROCESSING status."""
    job = sample_job_data.copy()
    job["status"] = JobStatus.PROCESSING.value
    job["progress"] = 0.5
    return job


@pytest.fixture
def sample_job_data_completed(sample_job_data):
    """Sample job data in COMPLETED status."""
    job = sample_job_data.copy()
    job["status"] = JobStatus.COMPLETED.value
    job["completed_at"] = datetime.now(timezone.utc).isoformat()
    job["resultRef"] = "2024-01-15/123e4567-e89b-12d3-a456-426614174000.json"
    job["language"] = "en"
    job["model"] = "whisper-base"
    job["duration"] = 180.5
    job["source"] = "asr"
    job["progress"] = 1.0
    return job


@pytest.fixture
def sample_job_data_failed(sample_job_data):
    """Sample job data in FAILED status."""
    job = sample_job_data.copy()
    job["status"] = JobStatus.FAILED.value
    job["completed_at"] = datetime.now(timezone.utc).isoformat()
    job["error"] = "Transcription failed: Model not loaded"
    return job


@pytest.fixture
def sample_enhanced_job_data():
    """Sample EnhancedJobData for queue testing."""
    return EnhancedJobData(
        job_id="job-123",
        priority=JobPriority.NORMAL,
        retry_count=0,
        max_retries=3,
        media_storage_path="s3://bucket/media/job-123.mp3",
        result_storage_path="s3://bucket/results/job-123.json",
        assigned_worker_id=None,
        queue_position=5,
        estimated_processing_time=120.0,
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
        last_heartbeat=datetime.now(timezone.utc).isoformat(),
        model_loaded=True,
        jobs_processed=10,
        total_gpu_hours=2.5,
    )


@pytest.fixture
def sample_transcription_result():
    """Sample transcription result dictionary."""
    return {
        "status": "completed",
        "jobId": "123e4567-e89b-12d3-a456-426614174000",
        "source": "asr",
        "language": "en",
        "confidence": 0.95,
        "transcript": "Hello world",
        "segments": [
            {"text": "Hello", "start": 0.0, "end": 1.0},
            {"text": "world", "start": 1.0, "end": 2.0},
        ],
        "warnings": [],
    }


@pytest.fixture
def temp_store_dir(tmp_path):
    """Create a temporary directory for storing job results."""
    store_dir = tmp_path / "temp_store"
    store_dir.mkdir()
    return store_dir


@pytest.fixture
def mock_observability_service():
    """Create a mock ObservabilityService."""
    mock_service = Mock()
    mock_service.track_job = Mock()
    mock_service.update_queue_depth = Mock()
    mock_service.update_worker_count = Mock()
    return mock_service


@pytest.fixture
def mock_audio_service():
    """Create a mock AudioDownloadService."""
    mock_service = Mock()
    mock_service.download_audio = Mock(return_value="/tmp/audio.wav")
    mock_service.cleanup_audio = Mock()
    return mock_service


@pytest.fixture
def mock_whisper_service():
    """Create a mock WhisperService."""
    mock_service = Mock()
    mock_service.transcribe_async = Mock()
    mock_service.model_id = "whisper-base"
    return mock_service


@pytest.fixture
def mock_http_client():
    """Create a mock httpx.AsyncClient for Runpod API."""
    mock_client = Mock()
    mock_client.post = Mock()
    mock_client.aclose = Mock()
    return mock_client


@pytest.fixture
def sample_runpod_response_success():
    """Sample successful Runpod API response."""
    return {
        "data": {
            "podFindAndDeploy": {
                "id": "pod-abc123",
                "name": "transcription-worker",
                "imageName": "transcription:latest",
                "env": [],
                "machineId": "machine-123",
                "machine": {"podHostId": "host-123"},
            }
        }
    }


@pytest.fixture
def sample_runpod_response_error():
    """Sample error Runpod API response."""
    return {"errors": [{"message": "Template not found", "extensions": {"code": "NOT_FOUND"}}]}


@pytest.fixture
def sample_runpod_user_response():
    """Sample Runpod user query response."""
    return {
        "data": {
            "myself": {
                "id": "user-123",
                "username": "testuser",
            }
        }
    }
