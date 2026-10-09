"""Fixtures for testing infrastructure services."""

from unittest.mock import Mock

import pytest
import redis
from prometheus_client import Counter, Gauge, Histogram

from app.core.config import Settings


@pytest.fixture
def mock_settings_observability_enabled():
    """Create mock Settings with observability enabled."""
    settings = Mock(spec=Settings)
    settings.observability_enabled = True
    settings.metrics_enabled = True
    settings.tracing_enabled = False
    settings.log_format = "json"
    return settings


@pytest.fixture
def mock_settings_observability_disabled():
    """Create mock Settings with observability disabled."""
    settings = Mock(spec=Settings)
    settings.observability_enabled = False
    settings.metrics_enabled = False
    settings.tracing_enabled = False
    settings.log_format = "text"
    return settings


@pytest.fixture
def mock_settings_metrics_only():
    """Create mock Settings with metrics enabled but tracing disabled."""
    settings = Mock(spec=Settings)
    settings.observability_enabled = True
    settings.metrics_enabled = True
    settings.tracing_enabled = False
    settings.log_format = "text"
    return settings


@pytest.fixture
def mock_prometheus_metrics():
    """Create mock Prometheus metrics objects."""
    return {
        "request_counter": Mock(spec=Counter),
        "request_duration": Mock(spec=Histogram),
        "job_counter": Mock(spec=Counter),
        "job_duration": Mock(spec=Histogram),
        "queue_depth": Mock(spec=Gauge),
        "worker_count": Mock(spec=Gauge),
    }


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = Mock(spec=redis.Redis)
    client.ping = Mock(return_value=True)
    client.setex = Mock()
    client.incrbyfloat = Mock()
    client.expire = Mock()
    client.get = Mock(return_value=None)
    client.keys = Mock(return_value=[])
    client.delete = Mock(return_value=1)
    return client


@pytest.fixture
def mock_redis_connection_pool():
    """Create a mock Redis connection pool."""
    pool = Mock(spec=redis.connection.ConnectionPool)
    return pool


@pytest.fixture
def mock_settings_cost_control_enabled():
    """Create mock Settings with cost control enabled."""
    settings = Mock(spec=Settings)
    settings.cost_control_enabled = True
    settings.redis_enabled = True
    settings.redis_host = "localhost"
    settings.redis_port = 6379
    settings.redis_db = 0
    settings.redis_password = ""
    settings.redis_socket_timeout = 5.0
    settings.redis_socket_connect_timeout = 5.0
    settings.redis_pool_max_connections = 50
    settings.gpu_cost_per_hour = 0.50
    settings.max_budget_usd = 100.0
    settings.cost_tracking_window_days = 30
    settings.budget_alert_threshold = 0.8
    settings.worker_idle_timeout_seconds = 600
    return settings


@pytest.fixture
def mock_settings_cost_control_disabled():
    """Create mock Settings with cost control disabled."""
    settings = Mock(spec=Settings)
    settings.cost_control_enabled = False
    settings.redis_enabled = False
    settings.max_budget_usd = 100.0  # Still need this for get_cost_metrics
    return settings


@pytest.fixture
def mock_settings_redis_enabled():
    """Create mock Settings with Redis enabled."""
    settings = Mock(spec=Settings)
    settings.redis_enabled = True
    settings.redis_host = "localhost"
    settings.redis_port = 6379
    settings.redis_db = 0
    settings.redis_password = ""
    settings.redis_socket_timeout = 5.0
    settings.redis_socket_connect_timeout = 5.0
    settings.redis_pool_max_connections = 50
    return settings


@pytest.fixture
def mock_settings_webhook():
    """Create mock Settings for webhook service."""
    settings = Mock(spec=Settings)
    settings.webhook_timeout_seconds = 10
    settings.webhook_max_retries = 3
    settings.webhook_retry_backoff_base = 1.0
    settings.webhook_connect_timeout = 5.0
    settings.webhook_write_timeout = 5.0
    settings.webhook_pool_timeout = 5.0
    settings.webhook_user_agent = "TranscriptionService/1.0"
    return settings


@pytest.fixture
def sample_webhook_result():
    """Sample webhook result payload."""
    return {
        "status": "completed",
        "source": "asr",
        "language": "en",
        "transcript": "Hello world",
        "segments": [
            {"text": "Hello", "start": 0.0, "end": 1.0},
            {"text": "world", "start": 1.0, "end": 2.0},
        ],
    }


@pytest.fixture
def sample_webhook_result_large():
    """Sample large webhook result payload for testing."""
    return {
        "status": "completed",
        "source": "asr",
        "language": "en",
        "transcript": "A" * 10000,  # Large transcript
        "segments": [
            {"text": "A" * 100, "start": float(i), "end": float(i + 1)} for i in range(100)
        ],
    }


@pytest.fixture
def valid_webhook_urls():
    """List of valid webhook URLs for testing."""
    return [
        "https://example.com/webhook",
        "https://api.example.com/v1/callback",
        "http://test.example.com/webhook",
        "https://subdomain.example.com/path/to/webhook?param=value",
    ]


@pytest.fixture
def invalid_webhook_urls():
    """List of invalid/unsafe webhook URLs for SSRF testing."""
    return [
        "http://localhost:8080/webhook",
        "http://127.0.0.1/webhook",
        "http://192.168.1.1/webhook",
        "http://10.0.0.1/webhook",
        "http://172.16.0.1/webhook",
        "file:///etc/passwd",
        "ftp://example.com/webhook",
        "not-a-url",
        "",
    ]


@pytest.fixture
def mock_httpx_client_success():
    """Mock httpx.AsyncClient that returns successful response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()

    mock_client = Mock()
    mock_client.__aenter__ = Mock(return_value=mock_client)
    mock_client.__aexit__ = Mock(return_value=None)
    mock_client.post = Mock(return_value=mock_response)

    return mock_client


@pytest.fixture
def mock_httpx_client_timeout():
    """Mock httpx.AsyncClient that raises TimeoutException."""
    import httpx

    mock_client = Mock()
    mock_client.__aenter__ = Mock(return_value=mock_client)
    mock_client.__aexit__ = Mock(return_value=None)
    mock_client.post = Mock(side_effect=httpx.TimeoutException("Request timed out"))

    return mock_client


@pytest.fixture
def mock_httpx_client_connection_error():
    """Mock httpx.AsyncClient that raises ConnectError."""
    import httpx

    mock_client = Mock()
    mock_client.__aenter__ = Mock(return_value=mock_client)
    mock_client.__aexit__ = Mock(return_value=None)
    mock_client.post = Mock(side_effect=httpx.ConnectError("Connection failed"))

    return mock_client


@pytest.fixture
def mock_httpx_client_http_error():
    """Mock httpx.AsyncClient that raises HTTPStatusError."""
    import httpx

    mock_response = Mock()
    mock_response.status_code = 500

    mock_client = Mock()
    mock_client.__aenter__ = Mock(return_value=mock_client)
    mock_client.__aexit__ = Mock(return_value=None)
    mock_client.post = Mock(
        side_effect=httpx.HTTPStatusError("Server error", request=Mock(), response=mock_response)
    )

    return mock_client


@pytest.fixture
def mock_httpx_client_4xx_error():
    """Mock httpx.AsyncClient that raises 4xx HTTPStatusError."""
    import httpx

    mock_response = Mock()
    mock_response.status_code = 400

    mock_client = Mock()
    mock_client.__aenter__ = Mock(return_value=mock_client)
    mock_client.__aexit__ = Mock(return_value=None)
    mock_client.post = Mock(
        side_effect=httpx.HTTPStatusError("Bad request", request=Mock(), response=mock_response)
    )

    return mock_client


@pytest.fixture
def cost_entry_sample():
    """Sample cost entry for testing."""
    return {
        "job_id": "job-123",
        "gpu_hours": 0.5,
        "cost": 0.25,
        "timestamp": "2024-01-01T12:00:00Z",
    }


@pytest.fixture
def cost_entries_multiple():
    """Multiple cost entries for testing."""
    return [
        {"job_id": "job-1", "gpu_hours": 0.5, "cost": 0.25, "timestamp": "2024-01-01T12:00:00Z"},
        {"job_id": "job-2", "gpu_hours": 1.0, "cost": 0.50, "timestamp": "2024-01-01T13:00:00Z"},
        {"job_id": "job-3", "gpu_hours": 0.25, "cost": 0.125, "timestamp": "2024-01-01T14:00:00Z"},
    ]
