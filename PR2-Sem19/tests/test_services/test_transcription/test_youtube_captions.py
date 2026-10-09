"""Comprehensive unit tests for YouTubeCaptionsService.

This test suite covers:
1. Happy path scenarios
2. Edge cases
3. Error conditions
4. Boundary value analysis
"""

from unittest.mock import Mock, patch

import pytest
from youtube_transcript_api import (CouldNotRetrieveTranscript,
                                    NoTranscriptFound, TranscriptsDisabled,
                                    VideoUnavailable)

from app.models.schemas import TranscriptSegment
from app.services.transcription.youtube_captions import YouTubeCaptionsService


class TestYouTubeCaptionsServiceInitialization:
    """Test YouTubeCaptionsService initialization scenarios."""

    def test_init_creates_service(self):
        """Test: Initialize YouTubeCaptionsService (happy path).

        Verifies that service initializes successfully.
        """
        service = YouTubeCaptionsService()
        assert service is not None


class TestValidateInput:
    """Test _validate_input method."""

    def test_validate_input_valid(
        self, sample_youtube_url, sample_video_id, boundary_language_codes
    ):
        """Test: Validate valid input (happy path).

        Verifies that valid inputs pass validation.
        """
        service = YouTubeCaptionsService()
        video_url, video_id = service._validate_input(sample_youtube_url, None, None)
        assert video_id == sample_video_id

    def test_validate_input_empty_url(self):
        """Test: Validate empty URL (error condition).

        Verifies that empty URLs raise ValueError.
        """
        service = YouTubeCaptionsService()
        with pytest.raises(ValueError, match="cannot be empty"):
            service._validate_input("", None, None)

    def test_validate_input_whitespace_url(self):
        """Test: Validate whitespace-only URL (error condition).

        Verifies that whitespace-only URLs raise ValueError.
        """
        service = YouTubeCaptionsService()
        with pytest.raises(ValueError, match="cannot be empty"):
            service._validate_input("   ", None, None)

    def test_validate_input_url_too_long(self, mock_settings):
        """Test: Validate URL exceeding max length (boundary value).

        Verifies that URLs exceeding max_url_length raise ValueError.
        """
        service = YouTubeCaptionsService()
        long_url = "https://www.youtube.com/watch?v=" + "x" * (mock_settings.max_url_length + 1)
        with patch("app.services.transcription.youtube_captions.settings", mock_settings):
            with pytest.raises(ValueError, match="too long"):
                service._validate_input(long_url, None, None)

    def test_validate_input_invalid_video_id(self):
        """Test: Validate URL with invalid video ID (error condition).

        Verifies that URLs with invalid video IDs raise ValueError.
        """
        service = YouTubeCaptionsService()
        with patch("app.services.transcription.youtube_captions.extract_video_id") as mock_extract:
            mock_extract.return_value = None
            with pytest.raises(ValueError, match="Invalid YouTube URL"):
                service._validate_input("https://youtube.com/watch?v=invalid", None, None)

    def test_validate_input_invalid_video_id_format(self, mock_settings):
        """Test: Validate video ID with invalid format (error condition).

        Verifies that video IDs with invalid format raise ValueError.
        """
        service = YouTubeCaptionsService()
        with patch("app.services.transcription.youtube_captions.extract_video_id") as mock_extract:
            mock_extract.return_value = "too-short"
            with patch("app.services.transcription.youtube_captions.settings", mock_settings):
                with pytest.raises(ValueError, match="Invalid YouTube video ID format"):
                    service._validate_input("https://youtube.com/watch?v=test", None, None)

    def test_validate_input_too_many_language_codes(self, mock_settings, sample_youtube_url):
        """Test: Validate too many language codes (error condition).

        Verifies that exceeding max_language_codes raises ValueError.
        """
        service = YouTubeCaptionsService()
        # Ensure mock_settings has actual integer value, not Mock object
        mock_settings.max_language_codes = 10
        too_many_codes = ["en"] * (mock_settings.max_language_codes + 1)
        with patch("app.services.transcription.youtube_captions.settings", mock_settings):
            with pytest.raises(ValueError, match="Too many language codes"):
                service._validate_input(sample_youtube_url, too_many_codes, None)

    def test_validate_input_invalid_language_code(self, mock_settings, sample_youtube_url):
        """Test: Validate invalid language code format (error condition).

        Verifies that invalid language codes raise ValueError.
        """
        service = YouTubeCaptionsService()
        # Ensure mock_settings has actual integer values, not Mock objects
        mock_settings.max_language_codes = 10
        mock_settings.min_language_code_length = 2
        mock_settings.max_language_code_length = 10
        with patch("app.services.transcription.youtube_captions.settings", mock_settings):
            with pytest.raises(ValueError, match="Invalid language code format"):
                service._validate_input(sample_youtube_url, ["123"], None)

    def test_validate_input_invalid_translate_to(self, mock_settings, sample_youtube_url):
        """Test: Validate invalid translate_to format (error condition).

        Verifies that invalid translate_to codes raise ValueError.
        """
        service = YouTubeCaptionsService()
        # Ensure mock_settings has actual integer values, not Mock objects
        mock_settings.min_language_code_length = 2
        mock_settings.max_language_code_length = 10
        with patch("app.services.transcription.youtube_captions.settings", mock_settings):
            with pytest.raises(ValueError, match="Invalid translation language code format"):
                service._validate_input(sample_youtube_url, None, "123")


class TestListTranscripts:
    """Test _list_transcripts method."""

    def test_list_transcripts_success(
        self,
        mock_youtube_transcript_api,
        sample_video_id,
        mock_transcript_list,
        mock_transcript_list_iter,
    ):
        """Test: List transcripts successfully (happy path).

        Verifies that transcript listing works correctly.
        """
        service = YouTubeCaptionsService()
        mock_youtube_transcript_api.list = Mock(return_value=mock_transcript_list)
        mock_transcript_list.__iter__ = Mock(return_value=iter(mock_transcript_list_iter))

        transcript_list, transcript_list_iter = service._list_transcripts(
            mock_youtube_transcript_api, sample_video_id
        )

        assert transcript_list == mock_transcript_list
        assert len(transcript_list_iter) == len(mock_transcript_list_iter)

    def test_list_transcripts_connection_error(self, mock_youtube_transcript_api, sample_video_id):
        """Test: List transcripts with connection error (error condition).

        Verifies that connection errors raise CouldNotRetrieveTranscript.
        """
        service = YouTubeCaptionsService()
        mock_youtube_transcript_api.list = Mock(
            side_effect=CouldNotRetrieveTranscript("Connection failed")
        )

        with pytest.raises(CouldNotRetrieveTranscript):
            service._list_transcripts(mock_youtube_transcript_api, sample_video_id)


class TestGetBaseLanguageCode:
    """Test _get_base_language_code method."""

    def test_get_base_language_code_simple(self):
        """Test: Get base language code from simple code (happy path).

        Verifies that simple language codes return themselves.
        """
        service = YouTubeCaptionsService()
        assert service._get_base_language_code("en") == "en"

    def test_get_base_language_code_with_region(self):
        """Test: Get base language code from code with region (happy path).

        Verifies that codes with regions return base language.
        """
        service = YouTubeCaptionsService()
        assert service._get_base_language_code("en-US") == "en"
        assert service._get_base_language_code("es-MX") == "es"

    def test_get_base_language_code_with_underscore(self):
        """Test: Get base language code with underscore (edge case).

        Verifies that codes with underscores are handled correctly.
        """
        service = YouTubeCaptionsService()
        assert service._get_base_language_code("en_GB") == "en"


class TestIsSameBaseLanguage:
    """Test _is_same_base_language method."""

    def test_is_same_base_language_true(self):
        """Test: Check same base language returns True (happy path).

        Verifies that codes with same base language return True.
        """
        service = YouTubeCaptionsService()
        assert service._is_same_base_language("en", "en-US") is True
        assert service._is_same_base_language("es", "es-MX") is True

    def test_is_same_base_language_false(self):
        """Test: Check different base languages returns False (happy path).

        Verifies that codes with different base languages return False.
        """
        service = YouTubeCaptionsService()
        assert service._is_same_base_language("en", "es") is False
        assert service._is_same_base_language("en-US", "es-MX") is False


class TestFindDirectTranscript:
    """Test _find_direct_transcript method."""

    def test_find_direct_transcript_exact_match(
        self, mock_transcript_list, mock_transcript, sample_fetched_transcript
    ):
        """Test: Find direct transcript with exact match (happy path).

        Verifies that exact language matches are found.
        """
        service = YouTubeCaptionsService()
        mock_transcript_list.find_transcript = Mock(return_value=mock_transcript)
        mock_transcript.fetch = Mock(return_value=sample_fetched_transcript)

        success, fetched, language = service._find_direct_transcript(
            mock_transcript_list, "en", [mock_transcript]
        )

        assert success is True
        assert fetched == sample_fetched_transcript
        assert language == "en"

    def test_find_direct_transcript_variant_match(
        self, mock_transcript_list, mock_transcript, sample_fetched_transcript
    ):
        """Test: Find direct transcript with variant match (happy path).

        Verifies that language variants are matched correctly.
        """
        service = YouTubeCaptionsService()
        variant_transcript = Mock()
        variant_transcript.language_code = "en-GB"
        variant_transcript.language = "English (UK)"

        mock_transcript_list.find_transcript = Mock(
            side_effect=[NoTranscriptFound("test", None, None), variant_transcript]
        )
        variant_transcript.fetch = Mock(return_value=sample_fetched_transcript)

        success, fetched, language = service._find_direct_transcript(
            mock_transcript_list, "en", [variant_transcript]
        )

        assert success is True
        assert language == "en-GB"

    def test_find_direct_transcript_not_found(self, mock_transcript_list):
        """Test: Find direct transcript not found (error condition).

        Verifies that missing transcripts return False.
        """
        service = YouTubeCaptionsService()
        mock_transcript_list.find_transcript = Mock(
            side_effect=NoTranscriptFound("test", None, None)
        )

        success, fetched, language = service._find_direct_transcript(mock_transcript_list, "en", [])

        assert success is False
        assert fetched is None
        assert language is None


class TestCanTranslate:
    """Test _can_translate method."""

    def test_can_translate_success(self, mock_transcript):
        """Test: Check translation capability successfully (happy path).

        Verifies that translatable transcripts return True.
        """
        service = YouTubeCaptionsService()
        mock_transcript.language_code = "es"
        mock_transcript.is_translatable = True
        mock_transcript.translation_languages = [Mock(language_code="en")]

        can_translate, error = service._can_translate(mock_transcript, "en")

        assert can_translate is True
        assert error is None

    def test_can_translate_same_base_language(self, mock_transcript):
        """Test: Check translation with same base language (edge case).

        Verifies that same base languages don't need translation.
        """
        service = YouTubeCaptionsService()
        mock_transcript.language_code = "en"

        can_translate, error = service._can_translate(mock_transcript, "en-US")

        assert can_translate is False
        assert "same base language" in error

    def test_can_translate_not_translatable(self, mock_transcript):
        """Test: Check translation with non-translatable transcript (error condition).

        Verifies that non-translatable transcripts return False.
        """
        service = YouTubeCaptionsService()
        mock_transcript.language_code = "es"
        mock_transcript.is_translatable = False

        can_translate, error = service._can_translate(mock_transcript, "en")

        assert can_translate is False
        assert "not translatable" in error

    def test_can_translate_target_not_available(self, mock_transcript):
        """Test: Check translation with unavailable target language (error condition).

        Verifies that unavailable target languages return False.
        """
        service = YouTubeCaptionsService()
        mock_transcript.language_code = "es"
        mock_transcript.is_translatable = True
        mock_transcript.translation_languages = [Mock(language_code="fr")]

        can_translate, error = service._can_translate(mock_transcript, "en")

        assert can_translate is False
        assert "not available" in error


class TestTryTranslateTranscript:
    """Test _try_translate_transcript method."""

    def test_try_translate_transcript_success(self, mock_transcript, sample_fetched_transcript):
        """Test: Translate transcript successfully (happy path).

        Verifies that translation works correctly.
        """
        service = YouTubeCaptionsService()
        mock_transcript.language_code = "es"
        translated_transcript = Mock()
        translated_transcript.fetch = Mock(return_value=sample_fetched_transcript)
        mock_transcript.translate = Mock(return_value=translated_transcript)

        success, fetched, language, error = service._try_translate_transcript(mock_transcript, "en")

        assert success is True
        assert fetched == sample_fetched_transcript
        assert language == "en"
        assert error is None

    def test_try_translate_transcript_failure(self, mock_transcript):
        """Test: Translate transcript fails (error condition).

        Verifies that translation failures are handled correctly.
        """
        service = YouTubeCaptionsService()
        mock_transcript.language_code = "es"
        mock_transcript.translate = Mock(
            side_effect=CouldNotRetrieveTranscript("Translation failed")
        )

        success, fetched, language, error = service._try_translate_transcript(mock_transcript, "en")

        assert success is False
        assert fetched is None
        assert language is None
        assert error is not None


class TestConvertSegments:
    """Test _convert_segments method."""

    def test_convert_segments_success(self, sample_fetched_transcript, sample_video_id):
        """Test: Convert segments successfully (happy path).

        Verifies that fetched transcript is converted to TranscriptSegment objects.
        """
        service = YouTubeCaptionsService()

        # Create mock snippet objects
        class MockSnippet:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration

        mock_snippets = [
            MockSnippet("Hello", 0.0, 1.5),
            MockSnippet("world", 1.5, 1.5),
            MockSnippet("How are you?", 3.0, 2.5),
        ]

        segments = service._convert_segments(mock_snippets, sample_video_id)

        assert len(segments) == 3
        assert all(isinstance(seg, TranscriptSegment) for seg in segments)
        assert segments[0].text == "Hello"
        assert segments[0].start == 0.0
        assert segments[0].end == 1.5

    def test_convert_segments_empty_text(self, sample_video_id):
        """Test: Convert segments with empty text (edge case).

        Verifies that segments with empty text are filtered out.
        """
        service = YouTubeCaptionsService()

        class MockSnippet:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration

        mock_snippets = [
            MockSnippet("", 0.0, 1.0),  # Empty text
            MockSnippet("Hello", 1.0, 1.0),
        ]

        segments = service._convert_segments(mock_snippets, sample_video_id)

        assert len(segments) == 1
        assert segments[0].text == "Hello"

    def test_convert_segments_invalid_timestamps(self, sample_video_id):
        """Test: Convert segments with invalid timestamps (error condition).

        Verifies that segments with invalid timestamps are filtered out.
        """
        service = YouTubeCaptionsService()

        class MockSnippet:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration

        mock_snippets = [
            MockSnippet("Hello", -1.0, 1.0),  # Negative start
            MockSnippet("world", 1.0, 0.0),  # Zero duration
        ]

        segments = service._convert_segments(mock_snippets, sample_video_id)

        # Invalid segments should be filtered out
        assert len(segments) == 0

    def test_convert_segments_text_too_long(self, sample_video_id, mock_settings):
        """Test: Convert segments with text exceeding max length (boundary value).

        Verifies that long text is truncated.
        """
        service = YouTubeCaptionsService()

        class MockSnippet:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration

        # Ensure mock_settings has actual integer value, not Mock object
        mock_settings.max_segment_text_length = 10000
        long_text = "x" * (mock_settings.max_segment_text_length + 100)
        mock_snippets = [MockSnippet(long_text, 0.0, 1.0)]

        with patch("app.services.transcription.youtube_captions.settings", mock_settings):
            segments = service._convert_segments(mock_snippets, sample_video_id)

            assert len(segments) == 1
            assert len(segments[0].text) == mock_settings.max_segment_text_length


class TestFetchTranscript:
    """Test fetch_transcript method (main entry point)."""

    def test_fetch_transcript_original_success(
        self, sample_youtube_url, sample_video_id, sample_transcript_segments
    ):
        """Test: Fetch original transcript successfully (happy path).

        Verifies that original transcripts are fetched correctly.
        """
        service = YouTubeCaptionsService()

        # Create mock fetched transcript (list of snippet-like objects)
        class MockSnippet:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration

        mock_fetched = [
            MockSnippet("Hello", 0.0, 1.5),
            MockSnippet("world", 1.5, 1.5),
            MockSnippet("How are you?", 3.0, 2.5),
        ]

        with (
            patch.object(
                service, "_validate_input", return_value=(sample_youtube_url, sample_video_id)
            ),
            patch("app.services.transcription.youtube_captions.YouTubeTranscriptApi"),
            patch.object(service, "_fetch_original_transcript") as mock_fetch,
        ):
            mock_fetch.return_value = (mock_fetched, "en")

            with patch.object(service, "_convert_segments") as mock_convert:
                mock_convert.return_value = sample_transcript_segments

                segments, language = service.fetch_transcript(sample_youtube_url)

                assert len(segments) == 3
                assert language == "en"

    def test_fetch_transcript_with_translation(
        self, sample_youtube_url, sample_video_id, sample_transcript_segments
    ):
        """Test: Fetch translated transcript successfully (happy path).

        Verifies that translated transcripts are fetched correctly.
        """
        service = YouTubeCaptionsService()

        # Create mock fetched transcript
        class MockSnippet:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration

        mock_fetched = [
            MockSnippet("Hola", 0.0, 1.5),
            MockSnippet("mundo", 1.5, 1.5),
        ]

        with (
            patch.object(
                service, "_validate_input", return_value=(sample_youtube_url, sample_video_id)
            ),
            patch.object(service, "_fetch_translated_transcript") as mock_fetch,
            patch.object(service, "_convert_segments") as mock_convert,
        ):
            mock_fetch.return_value = (mock_fetched, "es")
            mock_convert.return_value = sample_transcript_segments

            segments, language = service.fetch_transcript(sample_youtube_url, translate_to="es")

            assert language == "es"
            mock_fetch.assert_called_once()

    def test_fetch_transcript_transcripts_disabled(self, sample_youtube_url, sample_video_id):
        """Test: Fetch transcript with transcripts disabled (error condition).

        Verifies that TranscriptsDisabled exception is raised.
        """
        service = YouTubeCaptionsService()

        with (
            patch.object(
                service, "_validate_input", return_value=(sample_youtube_url, sample_video_id)
            ),
            patch(
                "app.services.transcription.youtube_captions.YouTubeTranscriptApi"
            ) as mock_api_class,
        ):
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.list = Mock(side_effect=TranscriptsDisabled("test"))

            with pytest.raises(TranscriptsDisabled):
                service.fetch_transcript(sample_youtube_url)

    def test_fetch_transcript_video_unavailable(self, sample_youtube_url, sample_video_id):
        """Test: Fetch transcript with video unavailable (error condition).

        Verifies that VideoUnavailable exception is raised.
        """
        service = YouTubeCaptionsService()

        with (
            patch.object(
                service, "_validate_input", return_value=(sample_youtube_url, sample_video_id)
            ),
            patch(
                "app.services.transcription.youtube_captions.YouTubeTranscriptApi"
            ) as mock_api_class,
        ):
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.list = Mock(side_effect=VideoUnavailable("test"))

            with pytest.raises(VideoUnavailable):
                service.fetch_transcript(sample_youtube_url)

    def test_fetch_transcript_empty_segments(self, sample_youtube_url, sample_video_id):
        """Test: Fetch transcript with empty segments (error condition).

        Verifies that empty segments raise CouldNotRetrieveTranscript.
        """
        service = YouTubeCaptionsService()

        # Create mock fetched transcript
        class MockSnippet:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration

        mock_fetched = [MockSnippet("Hello", 0.0, 1.5)]

        with (
            patch.object(
                service, "_validate_input", return_value=(sample_youtube_url, sample_video_id)
            ),
            patch("app.services.transcription.youtube_captions.YouTubeTranscriptApi"),
            patch.object(service, "_fetch_original_transcript") as mock_fetch,
            patch.object(service, "_convert_segments") as mock_convert,
        ):
            mock_fetch.return_value = (mock_fetched, "en")
            mock_convert.return_value = []  # Empty segments

            with pytest.raises(
                CouldNotRetrieveTranscript, match="Could not retrieve valid transcript segments"
            ):
                service.fetch_transcript(sample_youtube_url)


class TestIsTranscriptAvailable:
    """Test is_transcript_available method."""

    def test_is_transcript_available_true(
        self, sample_youtube_url, sample_video_id, mock_transcript_list_iter
    ):
        """Test: Check transcript availability returns True (happy path).

        Verifies that available transcripts return True.
        """
        service = YouTubeCaptionsService()

        with (
            patch("app.services.transcription.youtube_captions.extract_video_id") as mock_extract,
            patch(
                "app.services.transcription.youtube_captions.YouTubeTranscriptApi"
            ) as mock_api_class,
        ):
            mock_extract.return_value = sample_video_id
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.list = Mock(return_value=mock_transcript_list_iter)

            result = service.is_transcript_available(sample_youtube_url)
            assert result is True

    def test_is_transcript_available_false(self, sample_youtube_url):
        """Test: Check transcript availability returns False (error condition).

        Verifies that unavailable transcripts return False.
        """
        service = YouTubeCaptionsService()

        with (
            patch("app.services.transcription.youtube_captions.extract_video_id") as mock_extract,
            patch(
                "app.services.transcription.youtube_captions.YouTubeTranscriptApi"
            ) as mock_api_class,
        ):
            mock_extract.return_value = None
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.list = Mock(side_effect=Exception("Error"))

            result = service.is_transcript_available(sample_youtube_url)
            assert result is False

    def test_is_transcript_available_empty_url(self):
        """Test: Check transcript availability with empty URL (edge case).

        Verifies that empty URLs return False.
        """
        service = YouTubeCaptionsService()
        assert service.is_transcript_available("") is False
