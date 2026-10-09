"""Fixtures for testing transcription services."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from youtube_transcript_api import (CouldNotRetrieveTranscript,
                                    NoTranscriptFound, TranscriptsDisabled,
                                    VideoUnavailable)

from app.core.exceptions import CaptionsNotAvailableError, TranscriptionError
from app.models.schemas import OutputFormat, TranscriptSegment


@pytest.fixture
def sample_video_id():
    """Sample YouTube video ID for testing."""
    return "dQw4w9WgXcQ"


@pytest.fixture
def sample_youtube_url(sample_video_id):
    """Sample YouTube URL for testing."""
    return f"https://www.youtube.com/watch?v={sample_video_id}"


@pytest.fixture
def sample_youtube_urls():
    """List of valid YouTube URLs in various formats."""
    return [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube-nocookie.com/watch?v=dQw4w9WgXcQ",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ]


@pytest.fixture
def invalid_youtube_urls():
    """List of invalid YouTube URLs for testing."""
    return [
        "not-a-url",
        "https://example.com/video",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
        "",
        "https://www.youtube.com",
        "https://www.youtube.com/watch",
    ]


@pytest.fixture
def sample_transcript_segments():
    """Sample transcript segments for testing."""
    return [
        TranscriptSegment(text="Hello", start=0.0, end=1.5),
        TranscriptSegment(text="world", start=1.5, end=3.0),
        TranscriptSegment(text="How are you?", start=3.0, end=5.5),
    ]


@pytest.fixture
def sample_transcript_segments_empty():
    """Empty list of transcript segments."""
    return []


@pytest.fixture
def sample_transcript_segments_single():
    """Single transcript segment."""
    return [TranscriptSegment(text="Hello world", start=0.0, end=2.0)]


@pytest.fixture
def sample_transcript_segments_large():
    """Large list of transcript segments for testing."""
    return [
        TranscriptSegment(text=f"Segment {i}", start=float(i), end=float(i + 1)) for i in range(100)
    ]


@pytest.fixture
def sample_transcript_segments_with_gaps():
    """Transcript segments with gaps between them."""
    return [
        TranscriptSegment(text="First", start=0.0, end=2.0),
        TranscriptSegment(text="Second", start=5.0, end=7.0),  # 3 second gap
        TranscriptSegment(text="Third", start=10.0, end=12.0),  # 3 second gap
    ]


@pytest.fixture
def sample_transcript_segments_overlapping():
    """Transcript segments with overlapping timestamps."""
    return [
        TranscriptSegment(text="First", start=0.0, end=3.0),
        TranscriptSegment(text="Second", start=2.0, end=5.0),  # Overlaps with first
        TranscriptSegment(text="Third", start=4.0, end=7.0),  # Overlaps with second
    ]


@pytest.fixture
def sample_fetched_transcript():
    """Sample fetched transcript from YouTube API (list of dicts)."""
    return [
        {"text": "Hello", "start": 0.0, "duration": 1.5},
        {"text": "world", "start": 1.5, "duration": 1.5},
        {"text": "How are you?", "start": 3.0, "duration": 2.5},
    ]


@pytest.fixture
def sample_fetched_transcript_empty():
    """Empty fetched transcript."""
    return []


@pytest.fixture
def mock_youtube_transcript_api():
    """Mock YouTubeTranscriptApi instance."""
    mock_api = Mock()
    mock_api.list = Mock()
    return mock_api


@pytest.fixture
def mock_transcript_list():
    """Mock transcript list object."""
    mock_list = Mock()
    mock_list.find_transcript = Mock()
    mock_list.find_manually_created_transcript = Mock()
    return mock_list


@pytest.fixture
def mock_transcript():
    """Mock transcript object."""
    mock_transcript = Mock()
    mock_transcript.language = "English"
    mock_transcript.language_code = "en"
    mock_transcript.is_generated = False
    mock_transcript.is_translatable = True
    mock_transcript.translation_languages = []
    mock_transcript.fetch = Mock()
    mock_transcript.translate = Mock()
    return mock_transcript


@pytest.fixture
def mock_transcript_list_iter(mock_transcript):
    """Mock transcript list iterator."""
    return [mock_transcript]


@pytest.fixture
def mock_captions_service():
    """Mock YouTubeCaptionsService."""
    mock_service = Mock()
    mock_service.fetch_transcript = Mock()
    return mock_service


@pytest.fixture
def mock_audio_download_service():
    """Mock AudioDownloadService."""
    mock_service = Mock()
    mock_service.download_audio = Mock(return_value="/tmp/test_audio.wav")
    mock_service.cleanup_audio = Mock()
    mock_service.get_video_duration = Mock(return_value=180.0)  # 3 minutes
    return mock_service


@pytest.fixture
def mock_whisper_service():
    """Mock WhisperService."""
    mock_service = Mock()
    mock_service.transcribe_async = Mock()
    mock_service.transcribe = Mock()
    mock_service.ensure_model_loaded = Mock(return_value=True)
    mock_service.health_check = Mock(
        return_value={
            "loaded": True,
            "device": "cpu",
            "ready": True,
        }
    )
    mock_service.model_id = "whisper-base"
    mock_service._model_id = "whisper-base"
    return mock_service


@pytest.fixture
def mock_job_manager():
    """Mock JobManager."""
    mock_manager = Mock()
    mock_manager.create_job = Mock(return_value=("test-job-id", {"status": "queued"}))
    mock_manager.get_job = Mock(return_value={"status": "queued"})
    mock_manager._save_result_to_file = Mock(return_value="temp_store/test-result.json")
    mock_manager.store_sync_result_metadata = Mock()
    mock_manager._s3_storage = Mock()
    mock_manager._s3_storage.is_enabled = Mock(return_value=False)
    return mock_manager


@pytest.fixture
def mock_transcription_service(
    mock_captions_service,
    mock_audio_download_service,
    mock_whisper_service,
    mock_job_manager,
):
    """Mock TranscriptionService with all dependencies."""
    from app.services.transcription.transcription_service import \
        TranscriptionService

    service = TranscriptionService()
    service.captions_service = mock_captions_service
    service.audio_service = mock_audio_download_service
    service.whisper_service = mock_whisper_service
    service.job_manager = mock_job_manager
    return service


@pytest.fixture
def sample_whisper_result():
    """Sample Whisper model result dictionary."""
    return {
        "text": "Hello world How are you?",
        "language": "en",
        "chunks": [
            {"text": "Hello", "timestamp": (0.0, 1.5)},
            {"text": "world", "timestamp": (1.5, 3.0)},
            {"text": "How are you?", "timestamp": (3.0, 5.5)},
        ],
    }


@pytest.fixture
def sample_whisper_result_no_chunks():
    """Sample Whisper result without chunks."""
    return {
        "text": "Hello world",
        "language": "en",
    }


@pytest.fixture
def sample_whisper_result_with_confidence():
    """Sample Whisper result with confidence scores."""
    return {
        "text": "Hello world",
        "language": "en",
        "chunks": [
            {"text": "Hello", "timestamp": (0.0, 1.5), "confidence": 0.95},
            {"text": "world", "timestamp": (1.5, 3.0), "confidence": 0.92},
        ],
        "avg_logprob": -0.5,
    }


@pytest.fixture
def boundary_durations():
    """Boundary video duration values for testing."""
    return {
        "zero": 0.0,
        "very_short": 0.1,
        "short": 60.0,  # 1 minute
        "sync_threshold": 300.0,  # 5 minutes (sync/async boundary)
        "sync_threshold_minus_one": 299.0,
        "sync_threshold_plus_one": 301.0,
        "medium": 1800.0,  # 30 minutes
        "max_duration": 3600.0,  # 1 hour (max allowed)
        "max_duration_plus_one": 3601.0,  # Exceeds max
        "very_long": 7200.0,  # 2 hours
    }


@pytest.fixture
def boundary_language_codes():
    """Boundary language code values for testing."""
    return {
        "min_length": "a",
        "max_length": "abcdefghijklmnopqrstuvwxyz",
        "valid_iso": "en",
        "valid_iso_with_region": "en-US",
        "invalid_too_short": "",
        "invalid_too_long": "a" * 100,
        "invalid_numeric": "123",
        "invalid_special_chars": "en@#$",
    }


@pytest.fixture
def sample_output_formats():
    """All output formats for testing."""
    return [
        OutputFormat.JSON,
        OutputFormat.TEXT,
        OutputFormat.SRT,
        OutputFormat.VTT,
    ]


@pytest.fixture
def mock_settings():
    """Mock settings for transcription services."""
    from types import SimpleNamespace

    settings = SimpleNamespace()
    settings.cache_max_size = 1000
    settings.cache_ttl_seconds = 300
    settings.cache_warning_threshold = 0.8
    settings.video_id_cache_max_size = 10000
    settings.video_id_cache_ttl_seconds = 86400
    settings.max_url_length = 2048
    settings.max_url_query_length = 1024
    settings.async_threshold_seconds = 300.0  # 5 minutes
    settings.max_video_duration_seconds = 3600.0  # 1 hour
    settings.youtube_video_id_length = 11
    settings.max_language_codes = 10
    settings.min_language_code_length = 2
    settings.max_language_code_length = 10
    settings.max_segment_text_length = 10000
    settings.get_preferred_languages = Mock(return_value=["en", "es", "fr"])
    settings.get_common_languages = Mock(return_value=["en", "es", "fr", "de", "it"])
    settings.max_languages_display = 10
    settings.whisper_model = "openai/whisper-base"
    settings.whisper_model_path = None
    settings.whisper_device = "cpu"
    settings.whisper_segment_end_offset = 0.1
    settings.whisper_segment_density_optimal_min = 2.0
    settings.whisper_segment_density_optimal_max = 5.0
    settings.whisper_segment_density_max = 10.0
    settings.whisper_density_penalty_divisor = 5.0
    settings.whisper_density_interpolation_multiplier = 0.1
    settings.whisper_density_interpolation_factor = 0.1
    settings.whisper_word_length_optimal_min = 4.0
    settings.whisper_word_length_optimal_max = 6.0
    settings.whisper_word_length_short = 2.0
    settings.whisper_word_length_long = 10.0
    settings.whisper_word_length_short_score = 0.5
    settings.whisper_word_length_long_score = 0.7
    settings.whisper_word_length_medium_score = 0.8
    settings.whisper_gap_score_single_segment = 0.9
    settings.whisper_gap_score_small = 2.0
    settings.whisper_gap_score_medium = 5.0
    settings.whisper_gap_score_large = 10.0
    settings.whisper_gap_score_medium_value = 0.8
    settings.whisper_gap_score_large_value = 0.6
    settings.whisper_gap_score_very_large = 0.4
    settings.whisper_confidence_coverage_weight = 0.3
    settings.whisper_confidence_density_weight = 0.2
    settings.whisper_confidence_text_quality_weight = 0.3
    settings.whisper_confidence_gap_weight = 0.2
    settings.whisper_text_quality_punctuation_weight = 0.3
    settings.whisper_text_quality_capitalization_weight = 0.3
    settings.whisper_text_quality_word_length_weight = 0.4
    settings.log_result_sample_length = 200
    settings.min_text_length_for_detection = 10
    settings.result_file_extension = "json"
    return settings


@pytest.fixture
def configured_whisper_settings(mock_settings):
    """
    Configure mock_settings with all required whisper-related settings.

    This fixture ensures all whisper settings are set to real values (not Mocks)
    to prevent TypeError when comparing with numeric values in WhisperService.
    Use this fixture in tests that need all whisper settings properly configured.
    """
    # Model settings
    mock_settings.whisper_model_path = None
    mock_settings.whisper_model = getattr(mock_settings, "whisper_model", "openai/whisper-base")
    mock_settings.whisper_device = getattr(mock_settings, "whisper_device", "cpu")

    # Segment settings
    mock_settings.max_segment_text_length = 10000
    mock_settings.whisper_segment_end_offset = 0.1
    mock_settings.min_text_length_for_detection = 10

    # Density-related settings
    mock_settings.whisper_segment_density_optimal_min = 2.0
    mock_settings.whisper_segment_density_optimal_max = 5.0
    mock_settings.whisper_segment_density_max = 10.0
    mock_settings.whisper_density_penalty_divisor = 5.0
    mock_settings.whisper_density_interpolation_multiplier = 0.1
    mock_settings.whisper_density_interpolation_factor = 0.1

    # Word length settings
    mock_settings.whisper_word_length_optimal_min = 4.0
    mock_settings.whisper_word_length_optimal_max = 6.0
    mock_settings.whisper_word_length_short = 2.0
    mock_settings.whisper_word_length_long = 10.0
    mock_settings.whisper_word_length_short_score = 0.5
    mock_settings.whisper_word_length_long_score = 0.7
    mock_settings.whisper_word_length_medium_score = 0.8

    # Gap score settings
    mock_settings.whisper_gap_score_single_segment = 0.9
    mock_settings.whisper_gap_score_small = 2.0
    mock_settings.whisper_gap_score_medium = 5.0
    mock_settings.whisper_gap_score_large = 10.0
    mock_settings.whisper_gap_score_medium_value = 0.8
    mock_settings.whisper_gap_score_large_value = 0.6
    mock_settings.whisper_gap_score_very_large = 0.4

    # Confidence calculation weights
    mock_settings.whisper_confidence_coverage_weight = 0.3
    mock_settings.whisper_confidence_density_weight = 0.2
    mock_settings.whisper_confidence_text_quality_weight = 0.3
    mock_settings.whisper_confidence_gap_weight = 0.2

    # Text quality weights
    mock_settings.whisper_text_quality_punctuation_weight = 0.3
    mock_settings.whisper_text_quality_capitalization_weight = 0.3
    mock_settings.whisper_text_quality_word_length_weight = 0.4

    return mock_settings


@pytest.fixture
def sample_audio_path(tmp_path):
    """Sample audio file path for testing."""
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_bytes(b"fake audio content")
    return str(audio_file)


@pytest.fixture
def sample_media_file_path(tmp_path):
    """Sample media file path for testing."""
    media_file = tmp_path / "test_media.mp3"
    media_file.write_bytes(b"fake media content")
    return Path(media_file)


@pytest.fixture
def error_scenarios():
    """Common error scenarios for testing."""
    return {
        "captions_not_available": CaptionsNotAvailableError(
            "No captions available", details={"video_id": "test"}
        ),
        "could_not_retrieve": CouldNotRetrieveTranscript(
            "Could not retrieve transcript", video_id="test"
        ),
        "transcripts_disabled": TranscriptsDisabled("test", None),
        "video_unavailable": VideoUnavailable("test"),
        "no_transcript_found": NoTranscriptFound("test", None, None),
        "transcription_error": TranscriptionError("Transcription failed", code="TEST_ERROR"),
    }


@pytest.fixture
def mock_whisper_pipeline():
    """Mock Whisper pipeline (transformers pipeline)."""
    mock_pipeline = Mock()
    mock_pipeline.return_value = {
        "text": "Hello world",
        "language": "en",
        "chunks": [
            {"text": "Hello", "timestamp": (0.0, 1.5)},
            {"text": "world", "timestamp": (1.5, 3.0)},
        ],
    }
    return mock_pipeline


@pytest.fixture(autouse=False)
def stop_global_whisper_patch(monkeypatch):
    """Stop global WhisperService patch for tests that need the real service.

    This fixture stops the global patches that mock WhisperService in conftest.py,
    allowing tests to use the real WhisperService implementation.

    Note: This fixture is NOT autouse by default. Use it explicitly in test files
    that need the real WhisperService:

        pytestmark = pytest.mark.usefixtures("stop_global_whisper_patch")
    """
    import sys
    from unittest.mock import patch

    # Stop the global patches that mock WhisperService
    stopped_patches = []
    try:
        from tests.conftest import _patches

        for key in ["whisper1", "whisper2"]:
            if key in _patches:
                try:
                    _patches[key].stop()
                    stopped_patches.append(key)
                except Exception:
                    pass
    except (ImportError, AttributeError):
        pass

    # Remove the module from sys.modules to force reload
    if "app.services.transcription.whisper_service" in sys.modules:
        del sys.modules["app.services.transcription.whisper_service"]

    # Now import the real WhisperService
    from app.services.transcription.whisper_service import WhisperService

    # Reset WhisperService singleton state before each test
    WhisperService._instance = None
    WhisperService._initialized = False
    WhisperService._is_loaded = False
    WhisperService._model = None
    WhisperService._load_error = None

    # Patch the pipeline creation to avoid loading real models
    with patch("app.services.transcription.whisper_service.pipeline") as mock_pipeline_func:
        # Configure mock pipeline
        mock_pipeline = Mock()
        mock_pipeline.return_value = {
            "text": "Hello world",
            "language": "en",
            "chunks": [
                {"text": "Hello", "timestamp": (0.0, 1.5)},
                {"text": "world", "timestamp": (1.5, 3.0)},
            ],
        }
        mock_pipeline_func.return_value = mock_pipeline

        yield

    # Cleanup: remove the module again to allow fresh import next time
    if "app.services.transcription.whisper_service" in sys.modules:
        del sys.modules["app.services.transcription.whisper_service"]

    # Restart the patches after the test
    for key in stopped_patches:
        try:
            from tests.conftest import _patches

            _patches[key].start()
        except Exception:
            pass
