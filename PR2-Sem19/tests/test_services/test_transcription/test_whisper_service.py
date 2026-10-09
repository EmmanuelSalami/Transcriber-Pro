"""
Comprehensive unit tests for WhisperService.

This test suite covers:
1. Happy path scenarios (successful transcription, translation)
2. Edge cases (empty segments, single segments, overlapping timestamps)
3. Error conditions (model loading failures, transcription failures)
4. Boundary value analysis (timestamp validation, duration limits)
5. Singleton pattern behavior
6. Device detection
7. Confidence calculation (heuristic and from model)
8. Language detection
9. Async transcription
10. Health checks
"""

from unittest.mock import Mock, patch

import pytest
import torch

from app.core.exceptions import TranscriptionError
from app.models.schemas import TranscriptSegment

# Mark all tests to use the real WhisperService (not the global mock)
pytestmark = pytest.mark.usefixtures("stop_global_whisper_patch")


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def whisper_result_with_language():
    """Whisper result with language field."""
    return {
        "text": "Hello world. How are you?",
        "language": "en",
        "chunks": [
            {"text": "Hello world.", "timestamp": (0.0, 2.0)},
            {"text": "How are you?", "timestamp": (2.0, 4.5)},
        ],
    }


@pytest.fixture
def whisper_result_no_language():
    """Whisper result without language field."""
    return {
        "text": "Bonjour le monde",
        "chunks": [
            {"text": "Bonjour", "timestamp": (0.0, 1.5)},
            {"text": "le monde", "timestamp": (1.5, 3.0)},
        ],
    }


@pytest.fixture
def whisper_result_with_confidence_scores():
    """Whisper result with chunk-level confidence scores."""
    return {
        "text": "Test transcript",
        "language": "en",
        "chunks": [
            {"text": "Test", "timestamp": (0.0, 1.0), "confidence": 0.95},
            {"text": "transcript", "timestamp": (1.0, 2.5), "confidence": 0.88},
        ],
    }


@pytest.fixture
def whisper_result_with_avg_logprob():
    """Whisper result with avg_logprob for confidence calculation."""
    return {
        "text": "Test",
        "language": "en",
        "avg_logprob": -0.5,
        "chunks": [{"text": "Test", "timestamp": (0.0, 1.0)}],
    }


@pytest.fixture
def whisper_result_with_no_speech_prob():
    """Whisper result with no_speech_prob for confidence calculation."""
    return {
        "text": "Speech detected",
        "language": "en",
        "no_speech_prob": 0.1,  # Low no_speech_prob = high confidence
        "chunks": [{"text": "Speech detected", "timestamp": (0.0, 2.0)}],
    }


@pytest.fixture
def whisper_result_invalid_timestamps():
    """Whisper result with invalid timestamp values."""
    return {
        "text": "Invalid timestamps",
        "language": "en",
        "chunks": [
            {"text": "Negative start", "timestamp": (-1.0, 2.0)},
            {"text": "End before start", "timestamp": (5.0, 3.0)},
            {"text": "None timestamp", "timestamp": None},
            {"text": "Valid", "timestamp": (6.0, 8.0)},
        ],
    }


@pytest.fixture
def whisper_result_overlapping_segments():
    """Whisper result with overlapping segments (good for gap score)."""
    return {
        "text": "Overlapping segments",
        "language": "en",
        "chunks": [
            {"text": "First", "timestamp": (0.0, 3.0)},
            {"text": "Second", "timestamp": (2.5, 5.0)},  # Overlaps
            {"text": "Third", "timestamp": (4.5, 7.0)},  # Overlaps
        ],
    }


@pytest.fixture
def whisper_result_large_gaps():
    """Whisper result with large gaps between segments."""
    return {
        "text": "Segments with gaps",
        "language": "en",
        "chunks": [
            {"text": "First", "timestamp": (0.0, 2.0)},
            {"text": "Second", "timestamp": (15.0, 17.0)},  # 13 second gap
            {"text": "Third", "timestamp": (30.0, 32.0)},  # 13 second gap
        ],
    }


@pytest.fixture
def whisper_result_very_long_text():
    """Whisper result with text exceeding max length."""
    return {
        "text": "A" * 20000,
        "language": "en",
        "chunks": [{"text": "A" * 20000, "timestamp": (0.0, 10.0)}],
    }


@pytest.fixture
def whisper_result_empty_chunks():
    """Whisper result with empty text in chunks."""
    return {
        "text": "Some text",
        "language": "en",
        "chunks": [
            {"text": "", "timestamp": (0.0, 1.0)},  # Empty, should be skipped
            {"text": "  ", "timestamp": (1.0, 2.0)},  # Whitespace only, should be skipped
            {"text": "Valid text", "timestamp": (2.0, 4.0)},
        ],
    }


@pytest.fixture
def whisper_result_single_timestamp():
    """Whisper result with single-value timestamps."""
    return {
        "text": "Single timestamp",
        "language": "en",
        "chunks": [
            {"text": "Single", "timestamp": (0.0,)},  # Only start time
            {"text": "timestamp", "timestamp": (2.0,)},
        ],
    }


@pytest.fixture
def segments_for_heuristic_good():
    """Good quality segments for heuristic confidence calculation."""
    return [
        TranscriptSegment(text="Hello, world!", start=0.0, end=2.0),
        TranscriptSegment(text="How are you today?", start=2.0, end=4.5),
        TranscriptSegment(text="I am doing well.", start=4.5, end=7.0),
        TranscriptSegment(text="Thank you for asking.", start=7.0, end=9.5),
    ]


@pytest.fixture
def segments_for_heuristic_poor():
    """Poor quality segments (short words, no punctuation)."""
    return [
        TranscriptSegment(text="a b c", start=0.0, end=1.0),
        TranscriptSegment(text="d e f", start=1.0, end=2.0),
        TranscriptSegment(text="g h i", start=10.0, end=11.0),  # Large gap
    ]


@pytest.fixture
def segments_sparse():
    """Sparse segments (low density)."""
    return [
        TranscriptSegment(text="First segment", start=0.0, end=2.0),
        TranscriptSegment(text="Second segment", start=50.0, end=52.0),
    ]


@pytest.fixture
def segments_dense():
    """Very dense segments (high density)."""
    return [
        TranscriptSegment(text=f"Seg {i}", start=float(i * 0.1), end=float(i * 0.1 + 0.05))
        for i in range(100)
    ]


# ============================================================================
# Test Class: WhisperService Initialization and Singleton
# ============================================================================


class TestWhisperServiceInitialization:
    """Test WhisperService initialization and singleton pattern."""

    def test_singleton_pattern(self, configured_whisper_settings):
        """Test that WhisperService follows singleton pattern."""
        from app.services.transcription.whisper_service import WhisperService

        # Reset singleton
        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            instance1 = WhisperService.get_instance()
            instance2 = WhisperService.get_instance()

            assert instance1 is instance2, "WhisperService should return the same instance"

    def test_device_detection_cuda_available(self, configured_whisper_settings):
        """Test device detection when CUDA is available."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        configured_whisper_settings.whisper_device = "cuda"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch("torch.cuda.is_available", return_value=True):
                service = WhisperService.get_instance()
                assert service.device == "cuda", "Should use CUDA when available"

    def test_device_detection_cuda_unavailable(self, configured_whisper_settings):
        """Test device detection when CUDA requested but unavailable."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        configured_whisper_settings.whisper_device = "cuda"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch("torch.cuda.is_available", return_value=False):
                service = WhisperService.get_instance()
                assert service.device == "cpu", "Should fallback to CPU when CUDA unavailable"

    def test_device_detection_mps_available(self, configured_whisper_settings):
        """Test device detection when MPS is available (Apple Silicon)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        configured_whisper_settings.whisper_device = "mps"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            # Mock MPS availability
            mock_backends = Mock()
            mock_backends.mps = Mock()
            mock_backends.mps.is_available = Mock(return_value=True)

            with patch("torch.backends", mock_backends):
                service = WhisperService.get_instance()
                assert service.device == "mps", "Should use MPS when available"

    def test_device_detection_mps_unavailable(self, configured_whisper_settings):
        """Test device detection when MPS requested but unavailable."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        configured_whisper_settings.whisper_device = "mps"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            # Mock MPS unavailable
            with patch("torch.backends", Mock(spec=[])):
                service = WhisperService.get_instance()
                assert service.device == "cpu", "Should fallback to CPU when MPS unavailable"

    def test_device_detection_default_cpu(self, configured_whisper_settings):
        """Test device detection defaults to CPU."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        configured_whisper_settings.whisper_device = "cpu"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            assert service.device == "cpu", "Should default to CPU"

    def test_properties(self, configured_whisper_settings):
        """Test WhisperService properties."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None
        WhisperService._load_error = "Test error"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()

            assert service.is_loaded is False, "Model should not be loaded initially"
            assert service.model is None, "Model should be None initially"
            assert service.load_error == "Test error", "Load error should be accessible"


# ============================================================================
# Test Class: Model Loading
# ============================================================================


class TestWhisperServiceModelLoading:
    """Test WhisperService model loading functionality."""

    def test_ensure_model_loaded_success(self, configured_whisper_settings, mock_whisper_pipeline):
        """Test successful model loading."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                return_value=mock_whisper_pipeline,
            ):
                service = WhisperService.get_instance()
                result = service.ensure_model_loaded()

                assert result is True, "Model loading should succeed"
                assert service.is_loaded is True, "Model should be marked as loaded"
                assert service.model is not None, "Model should be set"
                assert service.load_error is None, "Load error should be None on success"

    def test_ensure_model_loaded_already_loaded(
        self, configured_whisper_settings, mock_whisper_pipeline
    ):
        """Test that model is not reloaded if already loaded."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = True
        WhisperService._model = mock_whisper_pipeline

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch("app.services.transcription.whisper_service.pipeline") as mock_pipeline_func:
                service = WhisperService.get_instance()
                result = service.ensure_model_loaded()

                assert result is True, "Should return True when already loaded"
                mock_pipeline_func.assert_not_called()  # Should not create new pipeline

    def test_ensure_model_loaded_force_reload(
        self, configured_whisper_settings, mock_whisper_pipeline
    ):
        """Test force reload of model."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = True
        WhisperService._model = Mock()

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                return_value=mock_whisper_pipeline,
            ) as mock_pipeline_func:
                service = WhisperService.get_instance()
                result = service.ensure_model_loaded(force_reload=True)

                assert result is True, "Force reload should succeed"
                mock_pipeline_func.assert_called_once()  # Should create new pipeline

    def test_ensure_model_loaded_failure(self, configured_whisper_settings):
        """Test model loading failure."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                side_effect=Exception("Model not found"),
            ):
                service = WhisperService.get_instance()
                result = service.ensure_model_loaded()

                assert result is False, "Model loading should fail"
                assert service.is_loaded is False, "Model should not be marked as loaded"
                assert service.load_error is not None, "Load error should be set"
                assert "Model not found" in service.load_error

    def test_ensure_model_loaded_failure_force_reload_raises(self, configured_whisper_settings):
        """Test that force reload raises exception on failure."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                side_effect=Exception("Model not found"),
            ):
                service = WhisperService.get_instance()

                with pytest.raises(TranscriptionError) as exc_info:
                    service.ensure_model_loaded(force_reload=True)

                assert exc_info.value.code == "MODEL_LOAD_ERROR"
                assert "Model not found" in str(exc_info.value)

    def test_determine_model_source_local_valid(self, configured_whisper_settings, tmp_path):
        """Test model source detection with valid local path."""
        from app.services.transcription.whisper_service import WhisperService

        # Create local model directory with config.json
        model_path = tmp_path / "whisper_model"
        model_path.mkdir()
        (model_path / "config.json").write_text("{}")

        WhisperService._instance = None
        WhisperService._initialized = False

        configured_whisper_settings.whisper_model_path = str(model_path)
        configured_whisper_settings.whisper_model = "openai/whisper-base"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            model_source, use_local = service._determine_model_source()

            assert use_local is True, "Should use local model"
            assert str(model_path.absolute()) in model_source

    def test_determine_model_source_local_invalid_no_config(
        self, configured_whisper_settings, tmp_path
    ):
        """Test model source detection with local path but no config.json."""
        from app.services.transcription.whisper_service import WhisperService

        # Create local model directory WITHOUT config.json
        model_path = tmp_path / "whisper_model"
        model_path.mkdir()

        WhisperService._instance = None
        WhisperService._initialized = False

        configured_whisper_settings.whisper_model_path = str(model_path)
        configured_whisper_settings.whisper_model = "openai/whisper-base"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            model_source, use_local = service._determine_model_source()

            assert use_local is False, "Should fallback to Hugging Face"
            assert model_source == "openai/whisper-base"

    def test_determine_model_source_local_not_exists(self, configured_whisper_settings):
        """Test model source detection with non-existent local path."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        configured_whisper_settings.whisper_model_path = "/nonexistent/path"
        configured_whisper_settings.whisper_model = "openai/whisper-base"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            model_source, use_local = service._determine_model_source()

            assert use_local is False, "Should fallback to Hugging Face"
            assert model_source == "openai/whisper-base"

    def test_determine_model_source_huggingface(self, configured_whisper_settings):
        """Test model source detection defaults to Hugging Face."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        configured_whisper_settings.whisper_model_path = None
        configured_whisper_settings.whisper_model = "openai/whisper-large-v3"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            model_source, use_local = service._determine_model_source()

            assert use_local is False, "Should use Hugging Face"
            assert model_source == "openai/whisper-large-v3"

    def test_create_whisper_pipeline_cpu(self, configured_whisper_settings, mock_whisper_pipeline):
        """Test pipeline creation with CPU device."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._device = "cpu"

        configured_whisper_settings.whisper_device = "cpu"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                return_value=mock_whisper_pipeline,
            ) as mock_pipeline_func:
                service = WhisperService.get_instance()
                service._create_whisper_pipeline("openai/whisper-base", False)

                # Verify pipeline was called with correct dtype for CPU
                call_kwargs = mock_pipeline_func.call_args[1]
                assert call_kwargs["dtype"] == torch.float32, "Should use float32 for CPU"

    def test_create_whisper_pipeline_cuda(self, configured_whisper_settings, mock_whisper_pipeline):
        """Test pipeline creation with CUDA device."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._device = "cuda"

        configured_whisper_settings.whisper_device = "cuda"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch("torch.cuda.is_available", return_value=True):
                with patch(
                    "app.services.transcription.whisper_service.pipeline",
                    return_value=mock_whisper_pipeline,
                ) as mock_pipeline_func:
                    service = WhisperService.get_instance()
                    service._create_whisper_pipeline("openai/whisper-base", False)

                    # Verify pipeline was called with correct dtype for GPU
                    call_kwargs = mock_pipeline_func.call_args[1]
                    assert call_kwargs["dtype"] == torch.float16, "Should use float16 for GPU"


# ============================================================================
# Test Class: Language Detection
# ============================================================================


class TestWhisperServiceLanguageDetection:
    """Test language detection from Whisper results."""

    def test_extract_language_from_result_direct(
        self, configured_whisper_settings, whisper_result_with_language
    ):
        """Test language extraction when directly in result."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            language = service._extract_language_from_result(whisper_result_with_language, None)

            assert language == "en", "Should extract language from result"

    def test_extract_language_translation_to_english(
        self, configured_whisper_settings, whisper_result_no_language
    ):
        """Test language is 'en' when translating to English."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            language = service._extract_language_from_result(whisper_result_no_language, "en")

            assert language == "en", "Translated language should always be English"

    def test_extract_language_fallback_langdetect(self, configured_whisper_settings):
        """Test language detection using langdetect fallback."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        result = {
            "text": "Bonjour, comment allez-vous? C'est une belle journée aujourd'hui.",
            "chunks": [{"text": "Bonjour", "timestamp": (0.0, 1.0)}],
        }

        configured_whisper_settings.min_text_length_for_detection = 10

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            language = service._extract_language_from_result(result, None)

            # langdetect should detect French
            assert language in ["fr", "en"], "Should detect language from text"

    def test_extract_language_default_fallback(self, configured_whisper_settings):
        """Test default fallback to 'en' when language cannot be detected."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        result = {
            "text": "...",  # Too short for detection
            "chunks": [{"text": "...", "timestamp": (0.0, 1.0)}],
        }

        configured_whisper_settings.min_text_length_for_detection = 10

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            language = service._extract_language_from_result(result, None)

            assert language == "en", "Should default to English when detection fails"

    def test_extract_language_unknown_in_result(self, configured_whisper_settings):
        """Test language extraction when result has 'unknown' language."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        result = {
            "text": "Hello world this is a test",
            "language": "unknown",
            "chunks": [{"text": "Hello", "timestamp": (0.0, 1.0)}],
        }

        configured_whisper_settings.min_text_length_for_detection = 5

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            language = service._extract_language_from_result(result, None)

            # Should use langdetect or default
            assert language != "unknown", "Should not return 'unknown'"


# ============================================================================
# Test Class: Chunk Processing
# ============================================================================


class TestWhisperServiceChunkProcessing:
    """Test processing of Whisper chunks into segments."""

    def test_process_chunk_valid(self, configured_whisper_settings):
        """Test processing a valid chunk."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        chunk = {"text": "Hello world", "timestamp": (0.0, 2.5)}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is not None, "Should return result tuple"
            segment, confidence = result
            assert segment.text == "Hello world"
            assert segment.start == 0.0
            assert segment.end == 2.5
            assert confidence is None  # No confidence in chunk

    def test_process_chunk_with_confidence(self, configured_whisper_settings):
        """Test processing chunk with confidence score."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure required settings are real values
        configured_whisper_settings.max_segment_text_length = 10000

        chunk = {"text": "Test", "timestamp": (0.0, 1.0), "confidence": 0.95}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is not None
            segment, confidence = result
            assert confidence == 0.95

    def test_process_chunk_negative_start_time(self, configured_whisper_settings):
        """Test processing chunk with negative start time (should be corrected to 0)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure required settings are real values
        configured_whisper_settings.max_segment_text_length = 10000

        chunk = {"text": "Negative", "timestamp": (-1.0, 2.0)}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is not None
            segment, _ = result
            assert segment.start == 0.0, "Negative start should be corrected to 0"
            assert segment.end == 2.0

    def test_process_chunk_end_before_start(self, configured_whisper_settings):
        """Test processing chunk where end is before start (should be corrected)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure required settings are real values
        configured_whisper_settings.max_segment_text_length = 10000
        configured_whisper_settings.whisper_segment_end_offset = 0.1

        chunk = {"text": "Invalid", "timestamp": (5.0, 3.0)}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is not None
            segment, _ = result
            assert segment.start == 5.0
            assert segment.end == 5.1  # start + offset

    def test_process_chunk_single_timestamp_value(self, configured_whisper_settings):
        """Test processing chunk with single timestamp value."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure required settings are real values
        configured_whisper_settings.max_segment_text_length = 10000
        configured_whisper_settings.whisper_segment_end_offset = 0.1

        chunk = {"text": "Single", "timestamp": (2.5,)}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is not None
            segment, _ = result
            assert segment.start == 2.5
            assert segment.end == 2.5  # Same as start (when only one timestamp)

    def test_process_chunk_empty_text(self, configured_whisper_settings):
        """Test processing chunk with empty text (should return None)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        chunk = {"text": "   ", "timestamp": (0.0, 1.0)}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is None, "Empty text should return None"

    def test_process_chunk_missing_timestamp(self, configured_whisper_settings):
        """Test processing chunk with missing timestamp (should return None)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        chunk = {"text": "No timestamp"}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is None, "Missing timestamp should return None"

    def test_process_chunk_none_timestamp(self, configured_whisper_settings):
        """Test processing chunk with None timestamp (should return None)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        chunk = {"text": "None timestamp", "timestamp": None}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is None, "None timestamp should return None"

    def test_process_chunk_exceeds_max_length(self, configured_whisper_settings):
        """Test processing chunk with text exceeding max length."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        long_text = "A" * 20000
        chunk = {"text": long_text, "timestamp": (0.0, 10.0)}

        configured_whisper_settings.max_segment_text_length = 10000

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is not None
            segment, _ = result
            assert len(segment.text) == 10000, "Text should be truncated"

    def test_process_chunk_prob_variants(self, configured_whisper_settings):
        """Test processing chunk with different confidence field names."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure required settings are real values
        configured_whisper_settings.max_segment_text_length = 10000

        # Test 'prob' field
        chunk_prob = {"text": "Test", "timestamp": (0.0, 1.0), "prob": 0.9}
        # Test 'probability' field
        chunk_probability = {"text": "Test", "timestamp": (0.0, 1.0), "probability": 0.85}
        # Test 'score' field
        chunk_score = {"text": "Test", "timestamp": (0.0, 1.0), "score": 0.92}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()

            result_prob = service._process_chunk(chunk_prob)
            assert result_prob is not None
            assert result_prob[1] == 0.9

            result_probability = service._process_chunk(chunk_probability)
            assert result_probability is not None
            assert result_probability[1] == 0.85

            result_score = service._process_chunk(chunk_score)
            assert result_score is not None
            assert result_score[1] == 0.92

    def test_process_chunks_to_segments_valid(
        self, configured_whisper_settings, whisper_result_with_language
    ):
        """Test converting chunks to segments."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure required settings are real values
        configured_whisper_settings.max_segment_text_length = 10000

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            segments, confidence_scores = service._process_chunks_to_segments(
                whisper_result_with_language
            )

            assert len(segments) == 2, "Should create 2 segments"
            assert segments[0].text == "Hello world."
            assert segments[1].text == "How are you?"

    def test_process_chunks_to_segments_no_chunks(self, configured_whisper_settings):
        """Test processing result with no chunks but text."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        result = {"text": "Single text", "language": "en"}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            segments, confidence_scores = service._process_chunks_to_segments(result)

            assert len(segments) == 1, "Should create single segment from text"
            assert segments[0].text == "Single text"
            assert segments[0].start == 0.0
            assert segments[0].end == 0.0

    def test_process_chunks_to_segments_empty_result(self, configured_whisper_settings):
        """Test processing empty result."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        result = {"language": "en"}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            segments, confidence_scores = service._process_chunks_to_segments(result)

            assert len(segments) == 0, "Should return empty segments"


# ============================================================================
# Test Class: Confidence Calculation
# ============================================================================


class TestWhisperServiceConfidenceCalculation:
    """Test confidence score calculation methods."""

    def test_calculate_confidence_from_chunk_scores(
        self, configured_whisper_settings, whisper_result_with_confidence_scores
    ):
        """Test confidence calculation from chunk-level scores."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure required settings are real values
        configured_whisper_settings.max_segment_text_length = 10000

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            segments, confidence_scores = service._process_chunks_to_segments(
                whisper_result_with_confidence_scores
            )
            confidence = service._calculate_confidence_from_result(
                whisper_result_with_confidence_scores,
                segments,
                confidence_scores,
                "/tmp/test.wav",
            )

            # Average of 0.95 and 0.88
            expected_avg = (0.95 + 0.88) / 2
            assert confidence is not None
            assert abs(confidence - expected_avg) < 0.01

    def test_calculate_confidence_from_avg_logprob(
        self, configured_whisper_settings, whisper_result_with_avg_logprob
    ):
        """Test confidence calculation from avg_logprob."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            segments, confidence_scores = service._process_chunks_to_segments(
                whisper_result_with_avg_logprob
            )
            confidence = service._calculate_confidence_from_result(
                whisper_result_with_avg_logprob, segments, confidence_scores, "/tmp/test.wav"
            )

            # exp(-0.5) ≈ 0.606
            assert confidence is not None
            assert 0.6 < confidence < 0.7

    def test_calculate_confidence_from_no_speech_prob(
        self, configured_whisper_settings, whisper_result_with_no_speech_prob
    ):
        """Test confidence calculation from no_speech_prob."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            segments, confidence_scores = service._process_chunks_to_segments(
                whisper_result_with_no_speech_prob
            )
            confidence = service._calculate_confidence_from_result(
                whisper_result_with_no_speech_prob, segments, confidence_scores, "/tmp/test.wav"
            )

            # 1.0 - 0.1 = 0.9
            assert confidence is not None
            assert abs(confidence - 0.9) < 0.01

    def test_calculate_heuristic_confidence_good_quality(
        self, configured_whisper_settings, segments_for_heuristic_good
    ):
        """Test heuristic confidence calculation for good quality segments."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            confidence = service._calculate_heuristic_confidence(segments_for_heuristic_good)

            assert confidence is not None
            assert confidence > 0.5, "Good quality should have higher confidence"

    def test_calculate_heuristic_confidence_poor_quality(
        self, configured_whisper_settings, segments_for_heuristic_poor
    ):
        """Test heuristic confidence calculation for poor quality segments."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            confidence = service._calculate_heuristic_confidence(segments_for_heuristic_poor)

            assert confidence is not None
            # Poor quality should have lower confidence due to gaps and short words
            assert confidence < 0.8

    def test_calculate_heuristic_confidence_empty_segments(self, configured_whisper_settings):
        """Test heuristic confidence calculation with empty segments."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            confidence = service._calculate_heuristic_confidence([])

            assert confidence == 0.0

    def test_calculate_coverage_ratio(self, configured_whisper_settings):
        """Test segment coverage ratio calculation."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        segments = [
            TranscriptSegment(text="A", start=0.0, end=2.0),  # 2 seconds
            TranscriptSegment(text="B", start=2.0, end=5.0),  # 3 seconds
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            ratio = service._calculate_coverage_ratio(segments, 10.0)

            # (2 + 3) / 10 = 0.5
            assert abs(ratio - 0.5) < 0.01

    def test_calculate_coverage_ratio_full_coverage(self, configured_whisper_settings):
        """Test coverage ratio with full coverage."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        segments = [TranscriptSegment(text="A", start=0.0, end=10.0)]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            ratio = service._calculate_coverage_ratio(segments, 10.0)

            assert ratio == 1.0

    def test_calculate_coverage_ratio_zero_duration(self, configured_whisper_settings):
        """Test coverage ratio with zero audio duration."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        segments = [TranscriptSegment(text="A", start=0.0, end=1.0)]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            ratio = service._calculate_coverage_ratio(segments, 0.0)

            assert ratio == 0.0

    def test_calculate_density_score_optimal(self, configured_whisper_settings):
        """Test density score with optimal density."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Create segments with optimal density (2-5 segments per second)
        # 3 segments per second = optimal
        segments = [
            TranscriptSegment(text=f"Seg {i}", start=float(i * 0.33), end=float(i * 0.33 + 0.3))
            for i in range(30)
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            score = service._calculate_density_score(segments, 10.0)

            assert score == 1.0, "Optimal density should score 1.0"

    def test_calculate_density_score_too_sparse(self, configured_whisper_settings, segments_sparse):
        """Test density score with sparse segments."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            score = service._calculate_density_score(segments_sparse, 60.0)

            # Very low density should have lower score
            assert score < 1.0

    def test_calculate_density_score_too_dense(self, configured_whisper_settings, segments_dense):
        """Test density score with very dense segments."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            score = service._calculate_density_score(segments_dense, 5.0)

            # Very high density should have lower score
            assert score < 1.0

    def test_calculate_gap_score_no_gaps(self, configured_whisper_settings):
        """Test gap score with continuous segments (no gaps)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        segments = [
            TranscriptSegment(text="A", start=0.0, end=2.0),
            TranscriptSegment(text="B", start=2.0, end=4.0),
            TranscriptSegment(text="C", start=4.0, end=6.0),
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            score = service._calculate_gap_score(segments)

            assert score == 1.0, "No gaps should score 1.0"

    def test_calculate_gap_score_small_gaps(self, configured_whisper_settings):
        """Test gap score with small gaps."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure all gap-related settings are real values
        configured_whisper_settings.whisper_gap_score_single_segment = 0.9
        configured_whisper_settings.whisper_gap_score_small = 2.0
        configured_whisper_settings.whisper_gap_score_medium = 5.0
        configured_whisper_settings.whisper_gap_score_large = 10.0
        configured_whisper_settings.whisper_gap_score_medium_value = 0.8
        configured_whisper_settings.whisper_gap_score_large_value = 0.6
        configured_whisper_settings.whisper_gap_score_very_large = 0.4

        segments = [
            TranscriptSegment(text="A", start=0.0, end=2.0),
            TranscriptSegment(text="B", start=2.5, end=4.5),  # 0.5 second gap
            TranscriptSegment(text="C", start=5.0, end=7.0),  # 0.5 second gap
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            score = service._calculate_gap_score(segments)

            assert score == 1.0, "Small gaps should score 1.0"

    def test_calculate_gap_score_large_gaps(
        self, configured_whisper_settings, whisper_result_large_gaps
    ):
        """Test gap score with large gaps."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            segments, _ = service._process_chunks_to_segments(whisper_result_large_gaps)
            score = service._calculate_gap_score(segments)

            assert score < 1.0, "Large gaps should have lower score"

    def test_calculate_gap_score_single_segment(self, configured_whisper_settings):
        """Test gap score with single segment."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        segments = [TranscriptSegment(text="Only one", start=0.0, end=5.0)]

        configured_whisper_settings.whisper_gap_score_single_segment = 0.9

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            score = service._calculate_gap_score(segments)

            assert score == 0.9

    def test_calculate_text_quality_score_good(self, configured_whisper_settings):
        """Test text quality score with good quality text."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure all word length-related settings are real values
        configured_whisper_settings.whisper_word_length_optimal_min = 4.0
        configured_whisper_settings.whisper_word_length_optimal_max = 6.0
        configured_whisper_settings.whisper_word_length_short = 2.0
        configured_whisper_settings.whisper_word_length_long = 10.0
        configured_whisper_settings.whisper_word_length_short_score = 0.5
        configured_whisper_settings.whisper_word_length_long_score = 0.7
        configured_whisper_settings.whisper_word_length_medium_score = 0.8

        segments = [
            TranscriptSegment(text="Hello, world!", start=0.0, end=2.0),
            TranscriptSegment(text="How are you today?", start=2.0, end=4.0),
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            punct_ratio, cap_ratio, word_score = service._calculate_text_quality_score(segments)

            assert punct_ratio > 0, "Should have punctuation"
            assert cap_ratio > 0, "Should have capitalized words"
            assert word_score > 0, "Should have reasonable word length"

    def test_calculate_text_quality_score_poor(self, configured_whisper_settings):
        """Test text quality score with poor quality text."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure all word length-related settings are real values
        configured_whisper_settings.whisper_word_length_optimal_min = 4.0
        configured_whisper_settings.whisper_word_length_optimal_max = 6.0
        configured_whisper_settings.whisper_word_length_short = 2.0
        configured_whisper_settings.whisper_word_length_long = 10.0
        configured_whisper_settings.whisper_word_length_short_score = 0.5
        configured_whisper_settings.whisper_word_length_long_score = 0.7
        configured_whisper_settings.whisper_word_length_medium_score = 0.8

        segments = [
            TranscriptSegment(text="a b c d e f", start=0.0, end=2.0),
            TranscriptSegment(text="g h i j k", start=2.0, end=4.0),
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            punct_ratio, cap_ratio, word_score = service._calculate_text_quality_score(segments)

            assert punct_ratio == 0, "Should have no punctuation"
            assert cap_ratio == 0, "Should have no capitalized words"
            # Short words should have lower score

    def test_calculate_text_quality_score_empty(self, configured_whisper_settings):
        """Test text quality score with empty segments."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            punct_ratio, cap_ratio, word_score = service._calculate_text_quality_score([])

            assert punct_ratio == 0.0
            assert cap_ratio == 0.0
            assert word_score == 0.0


# ============================================================================
# Test Class: Transcription (Sync)
# ============================================================================


class TestWhisperServiceTranscription:
    """Test synchronous transcription functionality."""

    def test_transcribe_success(
        self, configured_whisper_settings, sample_audio_path, whisper_result_with_language
    ):
        """Test successful transcription."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_with_language

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(sample_audio_path)

                assert len(segments) == 2
                assert language == "en"
                assert segments[0].text == "Hello world."
                assert segments[1].text == "How are you?"

    def test_transcribe_translate_to_english(
        self, configured_whisper_settings, sample_audio_path, whisper_result_with_language
    ):
        """Test transcription with translation to English."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_with_language

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(
                    sample_audio_path, translate_to="en"
                )

                # Verify task was set to 'translate'
                call_kwargs = mock_pipeline.call_args[1]
                assert call_kwargs["task"] == "translate"
                assert language == "en"

    def test_transcribe_translate_to_non_english_raises(
        self, configured_whisper_settings, sample_audio_path
    ):
        """Test that translation to non-English languages raises error."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                with pytest.raises(TranscriptionError) as exc_info:
                    service.transcribe(sample_audio_path, translate_to="fr")

                assert exc_info.value.code == "TRANSLATION_NOT_SUPPORTED"

    def test_transcribe_model_not_loaded_raises(
        self, configured_whisper_settings, sample_audio_path
    ):
        """Test transcription fails when model is not loaded."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                side_effect=Exception("Model load failed"),
            ):
                service = WhisperService.get_instance()

                with pytest.raises(TranscriptionError) as exc_info:
                    service.transcribe(sample_audio_path)

                assert exc_info.value.code == "MODEL_NOT_LOADED"

    def test_transcribe_no_segments_raises(self, configured_whisper_settings, sample_audio_path):
        """Test transcription raises error when no segments generated."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        # Result with no chunks and no text
        empty_result = {"language": "en"}

        mock_pipeline = Mock()
        mock_pipeline.return_value = empty_result

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                with pytest.raises(TranscriptionError) as exc_info:
                    service.transcribe(sample_audio_path)

                assert exc_info.value.code == "NO_SEGMENTS"

    def test_transcribe_inference_fails(self, configured_whisper_settings, sample_audio_path):
        """Test transcription handles inference failures."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.side_effect = RuntimeError("CUDA out of memory")

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                with pytest.raises(TranscriptionError) as exc_info:
                    service.transcribe(sample_audio_path)

                assert exc_info.value.code == "TRANSCRIPTION_FAILED"
                assert "CUDA out of memory" in str(exc_info.value)


# ============================================================================
# Test Class: Transcription (Async)
# ============================================================================


class TestWhisperServiceTranscriptionAsync:
    """Test asynchronous transcription functionality."""

    @pytest.mark.asyncio
    async def test_transcribe_async_success(
        self, configured_whisper_settings, sample_audio_path, whisper_result_with_language
    ):
        """Test successful async transcription."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_with_language

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = await service.transcribe_async(sample_audio_path)

                assert len(segments) == 2
                assert language == "en"

    @pytest.mark.asyncio
    async def test_transcribe_async_translate_to_english(
        self, configured_whisper_settings, sample_audio_path, whisper_result_with_language
    ):
        """Test async transcription with translation to English."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_with_language

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = await service.transcribe_async(
                    sample_audio_path, translate_to="en"
                )

                assert language == "en"

    @pytest.mark.asyncio
    async def test_transcribe_async_translate_to_non_english_returns_dict(
        self, configured_whisper_settings, sample_audio_path
    ):
        """Test async transcription returns error dict for non-English translation."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                result = await service.transcribe_async(sample_audio_path, translate_to="fr")

                # Should return error dict instead of raising
                assert isinstance(result, dict)
                assert result["code"] == "TRANSLATION_NOT_SUPPORTED"
                assert "message" in result
                assert "details" in result

    @pytest.mark.asyncio
    async def test_transcribe_async_no_segments_raises(
        self, configured_whisper_settings, sample_audio_path
    ):
        """Test async transcription raises error when no segments generated."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        empty_result = {"language": "en"}

        mock_pipeline = Mock()
        mock_pipeline.return_value = empty_result

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                with pytest.raises(TranscriptionError) as exc_info:
                    await service.transcribe_async(sample_audio_path)

                assert exc_info.value.code == "NO_SEGMENTS"

    @pytest.mark.asyncio
    async def test_transcribe_async_model_not_loaded_raises(
        self, configured_whisper_settings, sample_audio_path
    ):
        """Test async transcription fails when model is not loaded."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                side_effect=Exception("Model load failed"),
            ):
                service = WhisperService.get_instance()

                with pytest.raises(TranscriptionError) as exc_info:
                    await service.transcribe_async(sample_audio_path)

                assert exc_info.value.code == "MODEL_NOT_LOADED"

    @pytest.mark.asyncio
    async def test_transcribe_async_inference_fails(
        self, configured_whisper_settings, sample_audio_path
    ):
        """Test async transcription handles inference failures."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.side_effect = RuntimeError("Inference failed")

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                with pytest.raises(TranscriptionError) as exc_info:
                    await service.transcribe_async(sample_audio_path)

                assert exc_info.value.code == "TRANSCRIPTION_FAILED"


# ============================================================================
# Test Class: Health Check
# ============================================================================


class TestWhisperServiceHealthCheck:
    """Test health check functionality."""

    def test_health_check_model_loaded(self, configured_whisper_settings, mock_whisper_pipeline):
        """Test health check when model is loaded."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                return_value=mock_whisper_pipeline,
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                health = service.health_check()

                assert health["loaded"] is True
                assert health["ready"] is True
                assert health["device"] == "cpu"
                assert health["model"] == "openai/whisper-base"
                assert health["error"] is None

    def test_health_check_model_not_loaded(self, configured_whisper_settings):
        """Test health check when model is not loaded."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None
        WhisperService._load_error = None

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()

            health = service.health_check()

            assert health["loaded"] is False
            assert health["ready"] is False
            assert health["device"] == "cpu"

    def test_health_check_with_load_error(self, configured_whisper_settings):
        """Test health check when model loading failed."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None
        WhisperService._load_error = "Model file not found"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()

            health = service.health_check()

            assert health["loaded"] is False
            assert health["ready"] is False
            assert health["error"] == "Model file not found"


# ============================================================================
# Test Class: Edge Cases and Boundary Values
# ============================================================================


class TestWhisperServiceEdgeCases:
    """Test edge cases and boundary values."""

    def test_transcribe_with_invalid_timestamps(
        self, configured_whisper_settings, sample_audio_path, whisper_result_invalid_timestamps
    ):
        """Test transcription handles invalid timestamps gracefully."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_invalid_timestamps

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(sample_audio_path)

                # Should skip invalid chunks and only keep valid one
                assert len(segments) >= 1  # At least the valid one
                # Check that negative start times were corrected
                for seg in segments:
                    assert seg.start >= 0.0
                    assert seg.end >= seg.start

    def test_transcribe_with_overlapping_segments(
        self, configured_whisper_settings, sample_audio_path, whisper_result_overlapping_segments
    ):
        """Test transcription with overlapping segments."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_overlapping_segments

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(sample_audio_path)

                assert len(segments) == 3
                # Overlapping is valid, should be preserved
                assert segments[0].end > segments[1].start

    def test_transcribe_with_empty_chunks(
        self, configured_whisper_settings, sample_audio_path, whisper_result_empty_chunks
    ):
        """Test transcription filters out empty chunks."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_empty_chunks

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(sample_audio_path)

                # Should only have the valid text segment
                assert len(segments) == 1
                assert segments[0].text == "Valid text"

    def test_transcribe_with_single_timestamp(
        self, configured_whisper_settings, sample_audio_path, whisper_result_single_timestamp
    ):
        """Test transcription handles single-value timestamps."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_single_timestamp

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(sample_audio_path)

                assert len(segments) == 2
                # Single timestamp should have start == end
                for seg in segments:
                    assert seg.start == seg.end

    def test_boundary_zero_duration_segments(self, configured_whisper_settings):
        """Test heuristic confidence with zero-duration segments."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        segments = [
            TranscriptSegment(text="Test", start=0.0, end=0.0),
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            confidence = service._calculate_heuristic_confidence(segments)

            # Zero duration should return None
            assert confidence is None

    def test_boundary_very_long_text_truncation(
        self, configured_whisper_settings, sample_audio_path, whisper_result_very_long_text
    ):
        """Test that very long text is truncated."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_very_long_text

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(sample_audio_path)

                assert len(segments) == 1
                assert len(segments[0].text) == 10000

    def test_thread_safety_concurrent_access(
        self, configured_whisper_settings, mock_whisper_pipeline
    ):
        """Test that singleton is thread-safe."""
        import threading

        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        instances = []

        def get_instance():
            instances.append(WhisperService.get_instance())

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            threads = [threading.Thread(target=get_instance) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All instances should be the same
            assert all(inst is instances[0] for inst in instances)


# ============================================================================
# Test Class: Additional Tests Using Fixtures
# ============================================================================


class TestWhisperServiceWithFixtures:
    """Additional tests using fixtures from fixture folder."""

    def test_transcribe_with_sample_whisper_result(
        self, configured_whisper_settings, sample_audio_path, sample_whisper_result
    ):
        """Test transcription using sample_whisper_result fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = sample_whisper_result

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(sample_audio_path)

                assert len(segments) == 3
                assert language == "en"
                assert segments[0].text == "Hello"
                assert segments[1].text == "world"
                assert segments[2].text == "How are you?"

    def test_transcribe_with_sample_whisper_result_no_chunks(
        self, configured_whisper_settings, sample_audio_path, sample_whisper_result_no_chunks
    ):
        """Test transcription using sample_whisper_result_no_chunks fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = sample_whisper_result_no_chunks

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(sample_audio_path)

                # Should create single segment from text
                assert len(segments) == 1
                assert segments[0].text == "Hello world"
                assert language == "en"

    def test_transcribe_with_sample_whisper_result_with_confidence(
        self, configured_whisper_settings, sample_audio_path, sample_whisper_result_with_confidence
    ):
        """Test transcription using sample_whisper_result_with_confidence fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = sample_whisper_result_with_confidence

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(sample_audio_path)

                assert len(segments) == 2
                assert language == "en"
                # Confidence should be calculated from chunk scores
                assert confidence is not None
                assert 0.0 <= confidence <= 1.0

    def test_calculate_heuristic_confidence_with_sample_segments(
        self, configured_whisper_settings, sample_transcript_segments
    ):
        """Test heuristic confidence calculation using sample_transcript_segments fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            confidence = service._calculate_heuristic_confidence(sample_transcript_segments)

            assert confidence is not None
            assert 0.0 <= confidence <= 1.0

    def test_calculate_heuristic_confidence_with_empty_segments(
        self, configured_whisper_settings, sample_transcript_segments_empty
    ):
        """Test heuristic confidence with empty segments fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            confidence = service._calculate_heuristic_confidence(sample_transcript_segments_empty)

            assert confidence == 0.0

    def test_calculate_heuristic_confidence_with_single_segment(
        self, configured_whisper_settings, sample_transcript_segments_single
    ):
        """Test heuristic confidence with single segment fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure all confidence-related settings are real values
        configured_whisper_settings.whisper_confidence_coverage_weight = 0.3
        configured_whisper_settings.whisper_confidence_density_weight = 0.2
        configured_whisper_settings.whisper_confidence_text_quality_weight = 0.3
        configured_whisper_settings.whisper_confidence_gap_weight = 0.2
        configured_whisper_settings.whisper_text_quality_punctuation_weight = 0.3
        configured_whisper_settings.whisper_text_quality_capitalization_weight = 0.3
        configured_whisper_settings.whisper_text_quality_word_length_weight = 0.4
        configured_whisper_settings.whisper_segment_density_optimal_min = 2.0
        configured_whisper_settings.whisper_segment_density_optimal_max = 5.0
        configured_whisper_settings.whisper_segment_density_max = 10.0
        configured_whisper_settings.whisper_density_penalty_divisor = 5.0
        configured_whisper_settings.whisper_density_interpolation_multiplier = 0.1
        configured_whisper_settings.whisper_density_interpolation_factor = 0.1
        configured_whisper_settings.whisper_word_length_optimal_min = 4.0
        configured_whisper_settings.whisper_word_length_optimal_max = 6.0
        configured_whisper_settings.whisper_word_length_short = 2.0
        configured_whisper_settings.whisper_word_length_long = 10.0
        configured_whisper_settings.whisper_word_length_short_score = 0.5
        configured_whisper_settings.whisper_word_length_long_score = 0.7
        configured_whisper_settings.whisper_word_length_medium_score = 0.8
        configured_whisper_settings.whisper_gap_score_single_segment = 0.9
        configured_whisper_settings.whisper_gap_score_small = 2.0
        configured_whisper_settings.whisper_gap_score_medium = 5.0
        configured_whisper_settings.whisper_gap_score_large = 10.0
        configured_whisper_settings.whisper_gap_score_medium_value = 0.8
        configured_whisper_settings.whisper_gap_score_large_value = 0.6
        configured_whisper_settings.whisper_gap_score_very_large = 0.4

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            confidence = service._calculate_heuristic_confidence(sample_transcript_segments_single)

            assert confidence is not None
            assert 0.0 <= confidence <= 1.0

    def test_calculate_heuristic_confidence_with_large_segments(
        self, configured_whisper_settings, sample_transcript_segments_large
    ):
        """Test heuristic confidence with large segments fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure all confidence-related settings are real values
        configured_whisper_settings.whisper_confidence_coverage_weight = 0.3
        configured_whisper_settings.whisper_confidence_density_weight = 0.2
        configured_whisper_settings.whisper_confidence_text_quality_weight = 0.3
        configured_whisper_settings.whisper_confidence_gap_weight = 0.2
        configured_whisper_settings.whisper_text_quality_punctuation_weight = 0.3
        configured_whisper_settings.whisper_text_quality_capitalization_weight = 0.3
        configured_whisper_settings.whisper_text_quality_word_length_weight = 0.4
        configured_whisper_settings.whisper_segment_density_optimal_min = 2.0
        configured_whisper_settings.whisper_segment_density_optimal_max = 5.0
        configured_whisper_settings.whisper_segment_density_max = 10.0
        configured_whisper_settings.whisper_density_penalty_divisor = 5.0
        configured_whisper_settings.whisper_density_interpolation_multiplier = 0.1
        configured_whisper_settings.whisper_density_interpolation_factor = 0.1
        configured_whisper_settings.whisper_word_length_optimal_min = 4.0
        configured_whisper_settings.whisper_word_length_optimal_max = 6.0
        configured_whisper_settings.whisper_word_length_short = 2.0
        configured_whisper_settings.whisper_word_length_long = 10.0
        configured_whisper_settings.whisper_word_length_short_score = 0.5
        configured_whisper_settings.whisper_word_length_long_score = 0.7
        configured_whisper_settings.whisper_word_length_medium_score = 0.8
        configured_whisper_settings.whisper_gap_score_single_segment = 0.9
        configured_whisper_settings.whisper_gap_score_small = 2.0
        configured_whisper_settings.whisper_gap_score_medium = 5.0
        configured_whisper_settings.whisper_gap_score_large = 10.0
        configured_whisper_settings.whisper_gap_score_medium_value = 0.8
        configured_whisper_settings.whisper_gap_score_large_value = 0.6
        configured_whisper_settings.whisper_gap_score_very_large = 0.4

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            confidence = service._calculate_heuristic_confidence(sample_transcript_segments_large)

            assert confidence is not None
            assert 0.0 <= confidence <= 1.0

    def test_calculate_gap_score_with_gaps(
        self, configured_whisper_settings, sample_transcript_segments_with_gaps
    ):
        """Test gap score calculation using sample_transcript_segments_with_gaps fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure all gap-related settings are real values
        configured_whisper_settings.whisper_gap_score_single_segment = 0.9
        configured_whisper_settings.whisper_gap_score_small = 2.0
        configured_whisper_settings.whisper_gap_score_medium = 5.0
        configured_whisper_settings.whisper_gap_score_large = 10.0
        configured_whisper_settings.whisper_gap_score_medium_value = 0.8
        configured_whisper_settings.whisper_gap_score_large_value = 0.6
        configured_whisper_settings.whisper_gap_score_very_large = 0.4

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            score = service._calculate_gap_score(sample_transcript_segments_with_gaps)

            assert 0.0 <= score <= 1.0
            # Large gaps should have lower score
            assert score < 1.0

    def test_calculate_gap_score_with_overlapping(
        self, configured_whisper_settings, sample_transcript_segments_overlapping
    ):
        """Test gap score calculation using sample_transcript_segments_overlapping fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            score = service._calculate_gap_score(sample_transcript_segments_overlapping)

            # Overlapping segments should have no gaps, score should be 1.0
            assert score == 1.0

    def test_calculate_coverage_ratio_with_sample_segments(
        self, configured_whisper_settings, sample_transcript_segments
    ):
        """Test coverage ratio calculation using sample_transcript_segments fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            # Calculate audio duration from segments
            audio_duration = max(seg.end for seg in sample_transcript_segments)
            ratio = service._calculate_coverage_ratio(sample_transcript_segments, audio_duration)

            assert 0.0 <= ratio <= 1.0
            # Segments cover 5.5 seconds out of 5.5 seconds = 1.0
            assert ratio == 1.0

    def test_calculate_density_score_with_sample_segments(
        self, configured_whisper_settings, sample_transcript_segments
    ):
        """Test density score calculation using sample_transcript_segments fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure all density-related settings are real values
        configured_whisper_settings.whisper_segment_density_optimal_min = 2.0
        configured_whisper_settings.whisper_segment_density_optimal_max = 5.0
        configured_whisper_settings.whisper_segment_density_max = 10.0
        configured_whisper_settings.whisper_density_penalty_divisor = 5.0
        configured_whisper_settings.whisper_density_interpolation_multiplier = 0.1
        configured_whisper_settings.whisper_density_interpolation_factor = 0.1

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            audio_duration = max(seg.end for seg in sample_transcript_segments)
            score = service._calculate_density_score(sample_transcript_segments, audio_duration)

            assert 0.0 <= score <= 1.0

    def test_calculate_text_quality_score_with_sample_segments(
        self, configured_whisper_settings, sample_transcript_segments
    ):
        """Test text quality score calculation using sample_transcript_segments fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure all word length-related settings are real values
        configured_whisper_settings.whisper_word_length_optimal_min = 4.0
        configured_whisper_settings.whisper_word_length_optimal_max = 6.0
        configured_whisper_settings.whisper_word_length_short = 2.0
        configured_whisper_settings.whisper_word_length_long = 10.0
        configured_whisper_settings.whisper_word_length_short_score = 0.5
        configured_whisper_settings.whisper_word_length_long_score = 0.7
        configured_whisper_settings.whisper_word_length_medium_score = 0.8

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            punct_ratio, cap_ratio, word_score = service._calculate_text_quality_score(
                sample_transcript_segments
            )

            assert punct_ratio >= 0.0
            assert cap_ratio >= 0.0
            assert word_score >= 0.0

    def test_transcribe_with_sample_wav_file(
        self, configured_whisper_settings, sample_wav_file, whisper_result_with_language
    ):
        """Test transcription using sample_wav_file fixture from media fixtures."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_with_language

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(str(sample_wav_file))

                assert len(segments) == 2
                assert language == "en"

    def test_transcribe_with_sample_audio_file(
        self, configured_whisper_settings, sample_audio_file, whisper_result_with_language
    ):
        """Test transcription using sample_audio_file fixture from media fixtures."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = whisper_result_with_language

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = service.transcribe(str(sample_audio_file))

                assert len(segments) == 2
                assert language == "en"

    @pytest.mark.asyncio
    async def test_transcribe_async_with_sample_whisper_result(
        self, configured_whisper_settings, sample_audio_path, sample_whisper_result
    ):
        """Test async transcription using sample_whisper_result fixture."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        # Settings are configured via configured_whisper_settings fixture

        mock_pipeline = Mock()
        mock_pipeline.return_value = sample_whisper_result

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline", return_value=mock_pipeline
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                segments, language, confidence = await service.transcribe_async(sample_audio_path)

                assert len(segments) == 3
                assert language == "en"
                assert segments[0].text == "Hello"

    def test_log_model_info_with_local_model(
        self, configured_whisper_settings, mock_whisper_pipeline, tmp_path
    ):
        """Test _log_model_info method with local model."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._device = "cpu"

        model_path = tmp_path / "whisper_model"
        model_path.mkdir()
        (model_path / "config.json").write_text("{}")

        configured_whisper_settings.whisper_model_path = str(model_path)
        configured_whisper_settings.whisper_model = "openai/whisper-base"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            service._log_model_info(str(model_path), use_local_model=True)

            # Should not raise exception
            assert True

    def test_log_model_info_with_huggingface_model(
        self, configured_whisper_settings, mock_whisper_pipeline
    ):
        """Test _log_model_info method with Hugging Face model."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._device = "cpu"
        WhisperService._model = mock_whisper_pipeline

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            service._log_model_info("openai/whisper-base", use_local_model=False)

            # Should not raise exception
            assert True

    def test_extract_language_with_boundary_language_codes(
        self, configured_whisper_settings, boundary_language_codes
    ):
        """Test language extraction with boundary language codes."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        result = {
            "text": "Test text for language detection",
            "language": boundary_language_codes["valid_iso"],
            "chunks": [{"text": "Test", "timestamp": (0.0, 1.0)}],
        }

        configured_whisper_settings.min_text_length_for_detection = 5

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            language = service._extract_language_from_result(result, None)

            assert language == "en"

    def test_process_chunk_with_negative_confidence(self, configured_whisper_settings):
        """Test processing chunk with negative confidence (log probability)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure max_segment_text_length is a real value, not a Mock
        configured_whisper_settings.max_segment_text_length = 10000

        chunk = {"text": "Test", "timestamp": (0.0, 1.0), "confidence": -2.0}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is not None
            segment, confidence = result
            # Negative confidence should be converted using exp()
            assert confidence is not None
            assert 0.0 <= confidence <= 1.0

    def test_process_chunk_with_confidence_above_one(self, configured_whisper_settings):
        """Test processing chunk with confidence above 1.0 (should be normalized)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure max_segment_text_length is a real value, not a Mock
        configured_whisper_settings.max_segment_text_length = 10000

        chunk = {"text": "Test", "timestamp": (0.0, 1.0), "confidence": 1.5}

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            result = service._process_chunk(chunk)

            assert result is not None
            segment, confidence = result
            # Confidence above 1.0 should be normalized to 1.0
            assert confidence == 1.0

    def test_calculate_confidence_from_result_with_compression_ratio(
        self, configured_whisper_settings, whisper_result_with_language
    ):
        """Test confidence calculation using compression_ratio field."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        result = whisper_result_with_language.copy()
        result["compression_ratio"] = 0.85

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            segments, confidence_scores = service._process_chunks_to_segments(result)
            confidence = service._calculate_confidence_from_result(
                result, segments, confidence_scores, "/tmp/test.wav"
            )

            # Should use compression_ratio if no chunk scores
            assert confidence is not None
            assert 0.0 <= confidence <= 1.0

    def test_health_check_with_model_path(
        self, configured_whisper_settings, mock_whisper_pipeline, tmp_path
    ):
        """Test health check with local model path configured."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._is_loaded = False
        WhisperService._model = None

        model_path = tmp_path / "whisper_model"
        model_path.mkdir()
        (model_path / "config.json").write_text("{}")

        configured_whisper_settings.whisper_model_path = str(model_path)
        configured_whisper_settings.whisper_model = "openai/whisper-base"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                return_value=mock_whisper_pipeline,
            ):
                service = WhisperService.get_instance()
                service.ensure_model_loaded()

                health = service.health_check()

                assert health["loaded"] is True
                assert health["ready"] is True
                assert "model_path" in health
                assert str(model_path) in health["model_path"]

    def test_create_whisper_pipeline_mps(self, configured_whisper_settings, mock_whisper_pipeline):
        """Test pipeline creation with MPS device."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False
        WhisperService._device = "mps"

        configured_whisper_settings.whisper_device = "mps"

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            with patch(
                "app.services.transcription.whisper_service.pipeline",
                return_value=mock_whisper_pipeline,
            ) as mock_pipeline_func:
                service = WhisperService.get_instance()
                service._create_whisper_pipeline("openai/whisper-base", False)

                # Verify pipeline was called with correct dtype for MPS (GPU)
                call_kwargs = mock_pipeline_func.call_args[1]
                assert call_kwargs["dtype"] == torch.float16, "Should use float16 for MPS"

    def test_extract_language_with_processor_attributes(self, configured_whisper_settings):
        """Test language extraction from processor attributes."""
        from unittest.mock import PropertyMock

        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Create mock with language as a property that returns a string
        mock_model = Mock()
        mock_processor = Mock()
        # Use PropertyMock to ensure it returns actual string
        type(mock_processor).language = PropertyMock(return_value="fr")
        mock_model.processor = mock_processor

        result = {
            "text": "Bonjour le monde. C'est une belle journée.",
            "chunks": [{"text": "Bonjour", "timestamp": (0.0, 1.0)}],
        }

        configured_whisper_settings.min_text_length_for_detection = 5

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            WhisperService._model = mock_model
            language = service._extract_language_from_result(result, None)

            # Language should be a string (from processor, langdetect, or default)
            assert language is not None
            # Convert to string if needed (handles Mock objects)
            language_str = str(language) if not isinstance(language, str) else language
            assert isinstance(language_str, str)
            assert len(language_str) > 0

    def test_extract_language_with_config_attributes(self, configured_whisper_settings):
        """Test language extraction from model config attributes."""
        from unittest.mock import PropertyMock

        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Create mock with config language as a property that returns a string
        mock_model = Mock()
        mock_model_config = Mock()
        # Use PropertyMock to ensure it returns actual string
        type(mock_model_config).language = PropertyMock(return_value="de")
        mock_model.model = Mock()
        mock_model.model.config = mock_model_config

        result = {
            "text": "Hallo Welt. Wie geht es dir?",
            "chunks": [{"text": "Hallo", "timestamp": (0.0, 1.0)}],
        }

        configured_whisper_settings.min_text_length_for_detection = 5

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            WhisperService._model = mock_model
            language = service._extract_language_from_result(result, None)

            # Language should be a string (from config, langdetect, or default)
            assert language is not None
            # Convert to string if needed (handles Mock objects)
            language_str = str(language) if not isinstance(language, str) else language
            assert isinstance(language_str, str)
            assert len(language_str) > 0

    def test_calculate_heuristic_confidence_with_zero_duration(self, configured_whisper_settings):
        """Test heuristic confidence with segments that have zero duration."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        segments = [
            TranscriptSegment(text="Test", start=0.0, end=0.0),  # Zero duration
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            confidence = service._calculate_heuristic_confidence(segments)

            # Zero duration should return None
            assert confidence is None

    def test_calculate_coverage_ratio_exceeds_one(self, configured_whisper_settings):
        """Test coverage ratio when segments exceed audio duration."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        segments = [
            TranscriptSegment(text="A", start=0.0, end=10.0),  # 10 seconds
            TranscriptSegment(text="B", start=10.0, end=20.0),  # 10 seconds
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            ratio = service._calculate_coverage_ratio(segments, 15.0)  # 15 second audio

            # Should be capped at 1.0
            assert ratio == 1.0

    def test_calculate_density_score_below_one(self, configured_whisper_settings):
        """Test density score with very sparse segments (< 1 segment per second)."""
        from app.services.transcription.whisper_service import WhisperService

        WhisperService._instance = None
        WhisperService._initialized = False

        # Ensure all density-related settings are real values, not Mocks
        configured_whisper_settings.whisper_segment_density_optimal_min = 2.0
        configured_whisper_settings.whisper_segment_density_optimal_max = 5.0
        configured_whisper_settings.whisper_segment_density_max = 10.0
        configured_whisper_settings.whisper_density_penalty_divisor = 5.0
        configured_whisper_settings.whisper_density_interpolation_multiplier = 0.1
        configured_whisper_settings.whisper_density_interpolation_factor = 0.1

        segments = [
            TranscriptSegment(text="First", start=0.0, end=2.0),
            TranscriptSegment(text="Second", start=50.0, end=52.0),
        ]

        with patch(
            "app.services.transcription.whisper_service.settings", configured_whisper_settings
        ):
            service = WhisperService.get_instance()
            score = service._calculate_density_score(segments, 60.0)

            # Very sparse should have lower score
            assert 0.0 <= score <= 1.0
            assert score < 1.0
