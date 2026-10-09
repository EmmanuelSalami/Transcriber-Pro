"""Fixtures for testing core modules."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from starlette.datastructures import Headers


@pytest.fixture
def mock_settings():
    """Create a mock Settings instance for testing."""
    # Use SimpleNamespace as base to avoid MagicMock auto-creating Mock objects
    # Then wrap with MagicMock only for methods that need to be callable
    settings = SimpleNamespace()

    # Core settings
    settings.api_keys = "test-key-1,test-key-2,test-key-3"
    settings.secret_key = "test-secret-key"
    settings.dev_mode = False
    settings.cors_origins = "https://example.com,https://app.example.com"
    settings.strict_cors_check = False
    settings.observability_enabled = True
    settings.metrics_enabled = True
    # Ensure get_api_keys returns a list, not a Mock
    # CRITICAL: Must use a real function, not a Mock, to avoid "argument of type 'Mock' is not iterable"
    api_keys_list = ["test-key-1", "test-key-2", "test-key-3"]

    # Create a simple function that returns the list
    # This must be a real Python function, not a Mock object
    def get_api_keys():
        return api_keys_list

    # Assign directly to SimpleNamespace - this should work
    settings.get_api_keys = get_api_keys

    # Whisper Model Settings
    settings.whisper_model = "openai/whisper-base"
    settings.whisper_model_path = ""  # Empty string, not None, to avoid Path() issues
    settings.whisper_device = "cpu"
    settings.whisper_compute_type = "float32"

    # Processing Settings
    settings.min_text_length_for_detection = 10
    settings.max_segment_text_length = 10000

    # Whisper Confidence Calculation Thresholds
    settings.whisper_segment_density_optimal_min = 2.0
    settings.whisper_segment_density_optimal_max = 5.0
    settings.whisper_segment_density_max = 10.0
    settings.whisper_gap_score_small = 2.0
    settings.whisper_gap_score_medium = 5.0
    settings.whisper_gap_score_large = 10.0
    settings.whisper_word_length_optimal_min = 3.0
    settings.whisper_word_length_optimal_max = 6.0
    settings.whisper_word_length_short = 2.0
    settings.whisper_word_length_long = 10.0

    # Whisper Confidence Calculation Weights
    settings.whisper_confidence_coverage_weight = 0.4
    settings.whisper_confidence_density_weight = 0.2
    settings.whisper_confidence_text_quality_weight = 0.2
    settings.whisper_confidence_gap_weight = 0.2
    settings.whisper_text_quality_punctuation_weight = 0.5
    settings.whisper_text_quality_capitalization_weight = 0.3
    settings.whisper_text_quality_word_length_weight = 0.2
    settings.whisper_density_penalty_divisor = 20.0
    settings.whisper_density_interpolation_multiplier = 0.5
    settings.whisper_word_length_short_score = 0.5
    settings.whisper_gap_score_very_large = 0.4
    settings.whisper_segment_end_offset = 0.1
    settings.whisper_word_length_long_score = 0.7
    settings.whisper_word_length_medium_score = 0.8
    settings.whisper_gap_score_single_segment = 0.9
    settings.whisper_gap_score_medium_value = 0.8
    settings.whisper_gap_score_large_value = 0.6
    settings.whisper_density_interpolation_factor = 0.1

    return settings


@pytest.fixture
def mock_settings_dev_mode():
    """Create a mock Settings instance with dev mode enabled."""
    settings = MagicMock()
    settings.api_keys = ""
    settings.secret_key = ""
    settings.dev_mode = True
    settings.cors_origins = "*"
    settings.strict_cors_check = False
    # Ensure get_api_keys returns a list, not a Mock
    # Use lambda to ensure it's a real callable, not intercepted by MagicMock
    settings.get_api_keys = lambda: []
    # Configure methods to be callable and trackable
    # These will be patched at the class level in tests
    settings.validate_production_settings = MagicMock()
    settings.is_production = MagicMock(return_value=False)
    settings.get_cors_origins = MagicMock(return_value=["*"])
    return settings


@pytest.fixture
def mock_settings_production():
    """Create a mock Settings instance for production mode."""
    settings = MagicMock()
    settings.api_keys = "prod-key-1,prod-key-2"
    settings.secret_key = "prod-secret-key"
    settings.dev_mode = False
    settings.cors_origins = "https://production.com"
    settings.strict_cors_check = True
    # Ensure get_api_keys returns a list, not a Mock
    # Use lambda to ensure it's a real callable, not intercepted by MagicMock
    settings.get_api_keys = lambda: ["prod-key-1", "prod-key-2"]
    # Configure methods to be callable and trackable
    # These will be patched at the class level in tests
    settings.validate_production_settings = MagicMock()
    settings.is_production = MagicMock(return_value=True)
    settings.get_cors_origins = MagicMock(return_value=["https://production.com"])
    return settings


@pytest.fixture
def mock_http_credentials():
    """Create mock HTTPAuthorizationCredentials for testing."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-api-key")


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object."""
    request = Mock(spec=Request)
    request.method = "GET"
    request.url.path = "/v1/test"
    request.url.query = ""
    request.client = Mock()
    request.client.host = "127.0.0.1"
    request.headers = Headers()
    return request


@pytest.fixture
def mock_response():
    """Create a mock FastAPI Response object."""
    response = Mock()
    response.status_code = 200
    return response


@pytest.fixture
def mock_observability_service():
    """Create a mock ObservabilityService instance."""
    service = Mock()
    service.track_request = Mock()
    return service


@pytest.fixture
def mock_job_manager():
    """Create a mock JobManager instance."""
    manager = Mock()
    manager.recover_orphaned_jobs = Mock(return_value=0)
    manager.create_job = Mock(return_value=("job-id", {"status": "queued"}))
    manager.get_job = Mock(return_value={"status": "completed"})
    return manager


@pytest.fixture
def mock_whisper_service():
    """Create a mock WhisperService instance."""
    service = Mock()
    service.ensure_model_loaded = Mock(return_value=True)
    service.health_check = Mock(return_value={"loaded": True, "ready": True})
    return service


@pytest.fixture
def mock_worker_manager():
    """Create a mock WorkerManager instance."""
    manager = Mock()
    manager.auto_scale_workers = Mock(return_value=5)
    return manager


@pytest.fixture
def mock_queue_service():
    """Create a mock QueueService instance."""
    service = Mock()
    service.get_queue_stats = Mock(return_value={"pending": 5, "processing": 2, "completed": 10})
    return service


@pytest.fixture
def env_vars():
    """Fixture to manage environment variables during tests."""
    original_env = {}

    def _set_env(**kwargs):
        for key, value in kwargs.items():
            original_env[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)

    yield _set_env

    # Restore original environment
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
