"""Comprehensive unit tests for TranscriptionService.

This test suite covers:
1. Happy path scenarios
2. Edge cases
3. Error conditions
4. Boundary value analysis
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from youtube_transcript_api import CouldNotRetrieveTranscript

from app.core.exceptions import (CaptionsNotAvailableError,
                                 InvalidVideoURLError, TranscriptionError,
                                 VideoTooLongError)
from app.models.schemas import OutputFormat
from app.services.transcription.transcription_service import \
    TranscriptionService


class TestTranscriptionServiceInitialization:
    """Test TranscriptionService initialization scenarios."""

    def test_init_creates_all_services(self):
        """Test: Initialize TranscriptionService with all required services (happy path).

        Verifies that TranscriptionService initializes all its dependencies:
        - YouTubeCaptionsService
        - AudioDownloadService
        - WhisperService
        - JobManager
        """
        with (
            patch("app.services.transcription.transcription_service.YouTubeCaptionsService"),
            patch("app.services.transcription.transcription_service.AudioDownloadService"),
            patch("app.services.transcription.transcription_service.WhisperService"),
            patch("app.services.transcription.transcription_service.JobManager"),
        ):
            service = TranscriptionService()

            assert service.captions_service is not None
            assert service.audio_service is not None
            assert service.whisper_service is not None
            assert service.job_manager is not None


class TestGetCacheKey:
    """Test _get_cache_key method."""

    def test_get_cache_key_with_translation(self, mock_transcription_service):
        """Test: Generate cache key with translation (happy path).

        Verifies cache key format includes video ID, translation target, and format.
        """
        key = mock_transcription_service._get_cache_key("dQw4w9WgXcQ", "en", OutputFormat.JSON)
        assert key == "dQw4w9WgXcQ:en:json"

    def test_get_cache_key_without_translation(self, mock_transcription_service):
        """Test: Generate cache key without translation (happy path).

        Verifies cache key uses "none" for translation when None is provided.
        """
        key = mock_transcription_service._get_cache_key("dQw4w9WgXcQ", None, OutputFormat.TEXT)
        assert key == "dQw4w9WgXcQ:none:text"

    def test_get_cache_key_different_formats(self, mock_transcription_service):
        """Test: Generate cache keys for different formats (edge case).

        Verifies cache keys are unique for different output formats.
        """
        video_id = "dQw4w9WgXcQ"
        keys = [
            mock_transcription_service._get_cache_key(video_id, None, OutputFormat.JSON),
            mock_transcription_service._get_cache_key(video_id, None, OutputFormat.TEXT),
            mock_transcription_service._get_cache_key(video_id, None, OutputFormat.SRT),
            mock_transcription_service._get_cache_key(video_id, None, OutputFormat.VTT),
        ]
        # All keys should be unique
        assert len(set(keys)) == 4


class TestValidateVideoURL:
    """Test _validate_video_url method."""

    def test_validate_video_url_valid(self, mock_transcription_service, sample_youtube_url):
        """Test: Validate valid YouTube URL (happy path).

        Verifies that valid YouTube URLs pass validation.
        """
        result = mock_transcription_service._validate_video_url(sample_youtube_url)
        assert result == sample_youtube_url.strip()

    def test_validate_video_url_empty_string(self, mock_transcription_service):
        """Test: Validate empty string URL (error condition).

        Verifies that empty strings raise InvalidVideoURLError.
        """
        with pytest.raises(InvalidVideoURLError, match="cannot be empty"):
            mock_transcription_service._validate_video_url("")

    def test_validate_video_url_whitespace_only(self, mock_transcription_service):
        """Test: Validate whitespace-only URL (error condition).

        Verifies that URLs with only whitespace raise InvalidVideoURLError.
        """
        with pytest.raises(InvalidVideoURLError, match="cannot be empty"):
            mock_transcription_service._validate_video_url("   ")

    def test_validate_video_url_not_string(self, mock_transcription_service):
        """Test: Validate non-string URL (error condition).

        Verifies that non-string inputs raise InvalidVideoURLError.
        """
        with pytest.raises(InvalidVideoURLError, match="cannot be empty"):
            mock_transcription_service._validate_video_url(None)

    def test_validate_video_url_too_long(self, mock_transcription_service, mock_settings):
        """Test: Validate URL exceeding max length (boundary value).

        Verifies that URLs exceeding max_url_length raise InvalidVideoURLError.
        """
        with patch("app.services.transcription.transcription_service.settings", mock_settings):
            long_url = "https://www.youtube.com/watch?v=" + "x" * (mock_settings.max_url_length + 1)
            with pytest.raises(InvalidVideoURLError, match="exceeds maximum length"):
                mock_transcription_service._validate_video_url(long_url)

    def test_validate_video_url_invalid_protocol(self, mock_transcription_service):
        """Test: Validate URL with invalid protocol (error condition).

        Verifies that non-HTTP/HTTPS URLs raise InvalidVideoURLError.
        """
        with pytest.raises(InvalidVideoURLError, match="must be a valid HTTP/HTTPS URL"):
            mock_transcription_service._validate_video_url("ftp://youtube.com/watch?v=test")

    def test_validate_video_url_non_youtube_domain(self, mock_transcription_service):
        """Test: Validate URL with non-YouTube domain (error condition).

        Verifies that non-YouTube URLs raise InvalidVideoURLError.
        """
        with pytest.raises(InvalidVideoURLError, match="not a recognized YouTube domain"):
            mock_transcription_service._validate_video_url("https://example.com/video")


class TestExtractAndValidateVideoID:
    """Test _extract_and_validate_video_id method."""

    def test_extract_video_id_valid(
        self, mock_transcription_service, sample_youtube_url, sample_video_id
    ):
        """Test: Extract video ID from valid URL (happy path).

        Verifies that video ID is correctly extracted from valid YouTube URLs.
        """
        with patch(
            "app.services.transcription.transcription_service.extract_video_id"
        ) as mock_extract:
            mock_extract.return_value = sample_video_id
            result = mock_transcription_service._extract_and_validate_video_id(sample_youtube_url)
            assert result == sample_video_id

    def test_extract_video_id_invalid_url(self, mock_transcription_service):
        """Test: Extract video ID from invalid URL (error condition).

        Verifies that invalid URLs raise InvalidVideoURLError.
        """
        with patch(
            "app.services.transcription.transcription_service.extract_video_id"
        ) as mock_extract:
            mock_extract.return_value = None
            with pytest.raises(InvalidVideoURLError):
                mock_transcription_service._extract_and_validate_video_id("https://invalid.com")

    def test_extract_video_id_cached(
        self, mock_transcription_service, sample_youtube_url, sample_video_id
    ):
        """Test: Extract video ID uses cache (edge case).

        Verifies that video ID extraction results are cached.
        """
        # Clear cache first - use module-level cache
        from app.services.transcription.transcription_service import \
            _video_id_cache

        _video_id_cache.clear()
        with patch(
            "app.services.transcription.transcription_service.extract_video_id"
        ) as mock_extract:
            mock_extract.return_value = sample_video_id
            # First call
            result1 = mock_transcription_service._extract_and_validate_video_id(sample_youtube_url)
            # Second call should use cache
            result2 = mock_transcription_service._extract_and_validate_video_id(sample_youtube_url)
            assert result1 == result2 == sample_video_id
            # extract_video_id should only be called once due to caching
            assert mock_extract.call_count == 1


class TestTryCaptionsPath:
    """Test _try_captions_path method."""

    @pytest.mark.asyncio
    async def test_try_captions_path_cache_hit(
        self, mock_transcription_service, sample_video_id, sample_transcript_segments
    ):
        """Test: Try captions path with cache hit (happy path).

        Verifies that cached results are returned without calling captions service.
        """
        _ = mock_transcription_service._get_cache_key(sample_video_id, None, OutputFormat.JSON)
        cached_result = {
            "status": "completed",
            "source": "youtube_captions",
            "transcript": "Hello world",
        }

        with patch(
            "app.services.transcription.transcription_service._captions_cache"
        ) as mock_cache:
            mock_cache.__contains__ = Mock(return_value=True)
            mock_cache.__getitem__ = Mock(return_value=cached_result)

            result = await mock_transcription_service._try_captions_path(
                "https://youtube.com/watch?v=" + sample_video_id,
                sample_video_id,
                None,
                OutputFormat.JSON,
            )
            assert result == cached_result

    @pytest.mark.asyncio
    async def test_try_captions_path_cache_miss(
        self, mock_transcription_service, sample_video_id, sample_transcript_segments, mock_settings
    ):
        """Test: Try captions path with cache miss (happy path).

        Verifies that uncached results are fetched and cached.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        mock_transcription_service.captions_service.fetch_transcript = Mock(
            return_value=(sample_transcript_segments, "en")
        )

        # Ensure cache_warning_threshold is a number, not a Mock
        mock_settings.cache_warning_threshold = 0.8

        # Patch settings first to ensure _log_cache_stats() can access it
        with patch("app.services.transcription.transcription_service.settings", mock_settings):
            with patch(
                "app.services.transcription.transcription_service._captions_cache"
            ) as mock_cache:
                with patch(
                    "app.services.transcription.transcription_service._video_id_cache"
                ) as mock_video_cache:
                    mock_cache.__contains__ = Mock(return_value=False)
                    mock_cache.__setitem__ = Mock()
                    mock_cache.maxsize = 1000
                    # Ensure len() works on the mock cache
                    mock_cache.__len__ = Mock(return_value=0)
                    # Also mock video_id_cache for _log_cache_stats()
                    mock_video_cache.maxsize = 10000
                    mock_video_cache.__len__ = Mock(return_value=0)

                    result = await mock_transcription_service._try_captions_path(
                        video_url, sample_video_id, None, OutputFormat.JSON
                    )

                    assert result["source"] == "youtube_captions"
                    assert result["language"] == "en"
                    mock_cache.__setitem__.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_captions_path_raises_exception(
        self, mock_transcription_service, sample_video_id
    ):
        """Test: Try captions path raises exception (error condition).

        Verifies that exceptions from captions service are propagated.
        """
        # Use side_effect with the exception class to raise it, not return it
        mock_transcription_service.captions_service.fetch_transcript = Mock(
            side_effect=CouldNotRetrieveTranscript("test_video_id")
        )

        with pytest.raises(CouldNotRetrieveTranscript):
            await mock_transcription_service._try_captions_path(
                "https://youtube.com/watch?v=" + sample_video_id,
                sample_video_id,
                None,
                OutputFormat.JSON,
            )


class TestPathACaptions:
    """Test _path_a_captions method."""

    def test_path_a_captions_json_format(
        self, mock_transcription_service, sample_video_id, sample_transcript_segments
    ):
        """Test: Path A captions with JSON format (happy path).

        Verifies that captions are returned in JSON format with all metadata.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        mock_transcription_service.captions_service.fetch_transcript = Mock(
            return_value=(sample_transcript_segments, "en")
        )

        result = mock_transcription_service._path_a_captions(
            video_url, sample_video_id, None, OutputFormat.JSON
        )

        assert result["status"] == "completed"
        assert result["source"] == "youtube_captions"
        assert result["language"] == "en"
        assert result["transcript"] == "Hello world How are you?"
        assert len(result["segments"]) == 3

    def test_path_a_captions_text_format(
        self, mock_transcription_service, sample_video_id, sample_transcript_segments
    ):
        """Test: Path A captions with TEXT format (happy path).

        Verifies that captions are returned in plain text format.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        mock_transcription_service.captions_service.fetch_transcript = Mock(
            return_value=(sample_transcript_segments, "en")
        )

        result = mock_transcription_service._path_a_captions(
            video_url, sample_video_id, None, OutputFormat.TEXT
        )

        assert result["format"] == "text"
        assert "content" in result
        assert "Hello world How are you?" in result["content"]

    def test_path_a_captions_srt_format(
        self, mock_transcription_service, sample_video_id, sample_transcript_segments
    ):
        """Test: Path A captions with SRT format (happy path).

        Verifies that captions are returned in SRT subtitle format.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        mock_transcription_service.captions_service.fetch_transcript = Mock(
            return_value=(sample_transcript_segments, "en")
        )

        result = mock_transcription_service._path_a_captions(
            video_url, sample_video_id, None, OutputFormat.SRT
        )

        assert result["format"] == "srt"
        assert "content" in result
        assert "1\n" in result["content"]  # SRT format starts with sequence number

    def test_path_a_captions_vtt_format(
        self, mock_transcription_service, sample_video_id, sample_transcript_segments
    ):
        """Test: Path A captions with VTT format (happy path).

        Verifies that captions are returned in VTT subtitle format.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        mock_transcription_service.captions_service.fetch_transcript = Mock(
            return_value=(sample_transcript_segments, "en")
        )

        result = mock_transcription_service._path_a_captions(
            video_url, sample_video_id, None, OutputFormat.VTT
        )

        assert result["format"] == "vtt"
        assert "content" in result
        assert "WEBVTT" in result["content"]  # VTT format starts with WEBVTT header

    def test_path_a_captions_empty_segments(
        self, mock_transcription_service, sample_video_id, sample_transcript_segments_empty
    ):
        """Test: Path A captions with empty segments (error condition).

        Verifies that empty segments raise CaptionsNotAvailableError.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        mock_transcription_service.captions_service.fetch_transcript = Mock(
            return_value=(sample_transcript_segments_empty, "en")
        )

        with pytest.raises(CaptionsNotAvailableError, match="No transcript segments found"):
            mock_transcription_service._path_a_captions(
                video_url, sample_video_id, None, OutputFormat.JSON
            )

    def test_path_a_captions_with_translation(
        self, mock_transcription_service, sample_video_id, sample_transcript_segments
    ):
        """Test: Path A captions with translation (happy path).

        Verifies that translation parameter is passed to captions service.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        mock_transcription_service.captions_service.fetch_transcript = Mock(
            return_value=(sample_transcript_segments, "es")
        )

        result = mock_transcription_service._path_a_captions(
            video_url, sample_video_id, "es", OutputFormat.JSON
        )

        assert result["language"] == "es"
        mock_transcription_service.captions_service.fetch_transcript.assert_called_once_with(
            video_url, translate_to="es"
        )


class TestPathBASR:
    """Test _path_b_asr method."""

    @pytest.mark.asyncio
    async def test_path_b_asr_sync_processing(
        self, mock_transcription_service, sample_video_id, boundary_durations
    ):
        """Test: Path B ASR with synchronous processing (happy path).

        Verifies that videos shorter than async threshold are processed synchronously.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        duration = boundary_durations["short"]  # 1 minute

        mock_transcription_service.audio_service.get_video_duration = Mock(return_value=duration)
        mock_transcription_service._asr_sync = AsyncMock(
            return_value={"status": "completed", "source": "asr"}
        )

        result = await mock_transcription_service._path_b_asr(
            video_url, sample_video_id, None, OutputFormat.JSON, False, None
        )

        assert result["status"] == "completed"
        assert result["source"] == "asr"
        mock_transcription_service._asr_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_path_b_asr_async_processing(
        self, mock_transcription_service, sample_video_id, boundary_durations
    ):
        """Test: Path B ASR with asynchronous processing (happy path).

        Verifies that videos longer than async threshold are processed asynchronously.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        duration = boundary_durations["medium"]  # 30 minutes

        mock_transcription_service.audio_service.get_video_duration = Mock(return_value=duration)
        mock_transcription_service._asr_async = Mock(
            return_value={"status": "queued", "jobId": "test-job-id"}
        )

        result = await mock_transcription_service._path_b_asr(
            video_url, sample_video_id, None, OutputFormat.JSON, False, None
        )

        assert result["status"] == "queued"
        assert "jobId" in result
        mock_transcription_service._asr_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_path_b_asr_video_too_long(
        self, mock_transcription_service, sample_video_id, boundary_durations
    ):
        """Test: Path B ASR with video exceeding max duration (error condition).

        Verifies that videos longer than max duration raise VideoTooLongError.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        duration = boundary_durations["max_duration_plus_one"]  # Exceeds 1 hour

        mock_transcription_service.audio_service.get_video_duration = Mock(return_value=duration)

        with pytest.raises(VideoTooLongError, match="Video too long"):
            await mock_transcription_service._path_b_asr(
                video_url, sample_video_id, None, OutputFormat.JSON, False, None
            )

    @pytest.mark.asyncio
    async def test_path_b_asr_boundary_sync_threshold(
        self, mock_transcription_service, sample_video_id, boundary_durations
    ):
        """Test: Path B ASR at sync/async boundary (boundary value).

        Verifies behavior at the exact sync/async threshold.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id

        # Test just below threshold (should be sync)
        duration_below = boundary_durations["sync_threshold_minus_one"]
        mock_transcription_service.audio_service.get_video_duration = Mock(
            return_value=duration_below
        )
        mock_transcription_service._asr_sync = AsyncMock(return_value={"status": "completed"})

        await mock_transcription_service._path_b_asr(
            video_url, sample_video_id, None, OutputFormat.JSON, False, None
        )
        mock_transcription_service._asr_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_path_b_asr_zero_duration(
        self, mock_transcription_service, sample_video_id, boundary_durations
    ):
        """Test: Path B ASR with zero duration (edge case).

        Verifies handling of videos with zero duration.
        """
        video_url = "https://youtube.com/watch?v=" + sample_video_id
        duration = boundary_durations["zero"]

        mock_transcription_service.audio_service.get_video_duration = Mock(return_value=duration)
        mock_transcription_service._asr_sync = AsyncMock(return_value={"status": "completed"})

        result = await mock_transcription_service._path_b_asr(
            video_url, sample_video_id, None, OutputFormat.JSON, False, None
        )
        assert result["status"] == "completed"


class TestFormatASRResult:
    """Test _format_asr_result method."""

    def test_format_asr_result_json(self, mock_transcription_service, sample_transcript_segments):
        """Test: Format ASR result as JSON (happy path).

        Verifies that ASR results are formatted correctly in JSON format.
        """
        result = mock_transcription_service._format_asr_result(
            sample_transcript_segments, "en", 0.95, OutputFormat.JSON
        )

        assert result["status"] == "completed"
        assert result["source"] == "asr"
        assert result["language"] == "en"
        assert result["confidence"] == 0.95
        assert result["transcript"] == "Hello world How are you?"
        assert len(result["segments"]) == 3

    def test_format_asr_result_text(self, mock_transcription_service, sample_transcript_segments):
        """Test: Format ASR result as TEXT (happy path).

        Verifies that ASR results are formatted correctly in plain text format.
        """
        result = mock_transcription_service._format_asr_result(
            sample_transcript_segments, "en", 0.95, OutputFormat.TEXT
        )

        assert result["format"] == "text"
        assert "content" in result
        assert "Hello world How are you?" in result["content"]

    def test_format_asr_result_no_confidence(
        self, mock_transcription_service, sample_transcript_segments
    ):
        """Test: Format ASR result without confidence (edge case).

        Verifies that results without confidence scores are handled correctly.
        """
        result = mock_transcription_service._format_asr_result(
            sample_transcript_segments, "en", None, OutputFormat.JSON
        )

        assert result["confidence"] is None
        assert result["language"] == "en"

    def test_format_asr_result_empty_segments(
        self, mock_transcription_service, sample_transcript_segments_empty
    ):
        """Test: Format ASR result with empty segments (edge case).

        Verifies that empty segments are handled correctly.
        """
        result = mock_transcription_service._format_asr_result(
            sample_transcript_segments_empty, "en", 0.95, OutputFormat.JSON
        )

        assert result["transcript"] == ""
        assert result["segments"] == []


class TestTranscribe:
    """Test transcribe method (main entry point)."""

    @pytest.mark.asyncio
    async def test_transcribe_path_a_success(
        self,
        mock_transcription_service,
        sample_youtube_url,
        sample_video_id,
        sample_transcript_segments,
    ):
        """Test: Transcribe using Path A (captions) successfully (happy path).

        Verifies that transcription uses captions path when available.
        """
        mock_transcription_service._extract_and_validate_video_id = Mock(
            return_value=sample_video_id
        )
        mock_transcription_service._try_captions_path = AsyncMock(
            return_value={"status": "completed", "source": "youtube_captions"}
        )

        result = await mock_transcription_service.transcribe(
            sample_youtube_url, None, OutputFormat.JSON, False, None
        )

        assert result["source"] == "youtube_captions"
        mock_transcription_service._try_captions_path.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_path_b_fallback(
        self, mock_transcription_service, sample_youtube_url, sample_video_id
    ):
        """Test: Transcribe falls back to Path B when captions unavailable (happy path).

        Verifies that transcription falls back to ASR when captions fail.
        """
        mock_transcription_service._extract_and_validate_video_id = Mock(
            return_value=sample_video_id
        )
        # Use side_effect with the exception to raise it, not return it
        mock_transcription_service._try_captions_path = AsyncMock(
            side_effect=CouldNotRetrieveTranscript("test_video_id")
        )
        mock_transcription_service._path_b_asr = AsyncMock(
            return_value={"status": "completed", "source": "asr"}
        )

        result = await mock_transcription_service.transcribe(
            sample_youtube_url, None, OutputFormat.JSON, False, None
        )

        assert result["source"] == "asr"
        mock_transcription_service._path_b_asr.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_with_diarization(
        self, mock_transcription_service, sample_youtube_url, sample_video_id
    ):
        """Test: Transcribe with diarization forces Path B (happy path).

        Verifies that diarization request forces ASR path.
        """
        mock_transcription_service._extract_and_validate_video_id = Mock(
            return_value=sample_video_id
        )
        mock_transcription_service._try_captions_path = AsyncMock()
        mock_transcription_service._path_b_asr = AsyncMock(
            return_value={"status": "completed", "source": "asr"}
        )

        result = await mock_transcription_service.transcribe(
            sample_youtube_url, None, OutputFormat.JSON, True, None
        )

        assert result["source"] == "asr"
        mock_transcription_service._try_captions_path.assert_not_called()
        mock_transcription_service._path_b_asr.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_invalid_url(self, mock_transcription_service):
        """Test: Transcribe with invalid URL (error condition).

        Verifies that invalid URLs raise InvalidVideoURLError.
        """
        mock_transcription_service._extract_and_validate_video_id = Mock(
            side_effect=InvalidVideoURLError("Invalid URL")
        )

        with pytest.raises(InvalidVideoURLError):
            await mock_transcription_service.transcribe(
                "invalid-url", None, OutputFormat.JSON, False, None
            )

    @pytest.mark.asyncio
    async def test_transcribe_with_translation(
        self,
        mock_transcription_service,
        sample_youtube_url,
        sample_video_id,
        sample_transcript_segments,
    ):
        """Test: Transcribe with translation (happy path).

        Verifies that translation parameter is passed through correctly.
        """
        mock_transcription_service._extract_and_validate_video_id = Mock(
            return_value=sample_video_id
        )
        mock_transcription_service._try_captions_path = AsyncMock(
            return_value={"status": "completed", "source": "youtube_captions", "language": "es"}
        )

        result = await mock_transcription_service.transcribe(
            sample_youtube_url, "es", OutputFormat.JSON, False, None
        )

        assert result["language"] == "es"
        call_args = mock_transcription_service._try_captions_path.call_args
        assert call_args[0][2] == "es"  # translate_to parameter

    @pytest.mark.asyncio
    async def test_transcribe_with_webhook(
        self, mock_transcription_service, sample_youtube_url, sample_video_id
    ):
        """Test: Transcribe with webhook URL (happy path).

        Verifies that webhook URL is passed to async processing.
        """
        webhook_url = "https://example.com/webhook"
        mock_transcription_service._extract_and_validate_video_id = Mock(
            return_value=sample_video_id
        )
        mock_transcription_service._path_b_asr = AsyncMock(
            return_value={"status": "queued", "jobId": "test-job-id"}
        )

        await mock_transcription_service.transcribe(
            sample_youtube_url, None, OutputFormat.JSON, True, webhook_url
        )

        call_args = mock_transcription_service._path_b_asr.call_args
        assert call_args[0][5] == webhook_url  # webhook_url parameter


class TestTranscribeMedia:
    """Test transcribe_media method."""

    @pytest.mark.asyncio
    async def test_transcribe_media_success(
        self, mock_transcription_service, sample_media_file_path, sample_transcript_segments
    ):
        """Test: Transcribe media file successfully (happy path).

        Verifies that media files are transcribed correctly.
        """
        mock_transcription_service.whisper_service.transcribe_async = AsyncMock(
            return_value=(sample_transcript_segments, "en", 0.95)
        )
        mock_transcription_service.whisper_service.model_id = "whisper-base"

        result = await mock_transcription_service.transcribe_media(
            sample_media_file_path, None, OutputFormat.JSON, False
        )

        assert result["source"] == "asr"
        assert result["language"] == "en"
        assert result["confidence"] == 0.95
        assert "duration" in result
        assert "model" in result

    @pytest.mark.asyncio
    async def test_transcribe_media_with_translation(
        self, mock_transcription_service, sample_media_file_path, sample_transcript_segments
    ):
        """Test: Transcribe media file with translation (happy path).

        Verifies that translation parameter is passed to Whisper service.
        """
        mock_transcription_service.whisper_service.transcribe_async = AsyncMock(
            return_value=(sample_transcript_segments, "en", 0.95)
        )
        mock_transcription_service.whisper_service.model_id = "whisper-base"

        await mock_transcription_service.transcribe_media(
            sample_media_file_path, "en", OutputFormat.JSON, False
        )

        call_args = mock_transcription_service.whisper_service.transcribe_async.call_args
        assert call_args[1]["translate_to"] == "en"

    @pytest.mark.asyncio
    async def test_transcribe_media_error_response(
        self, mock_transcription_service, sample_media_file_path
    ):
        """Test: Transcribe media file with error response (error condition).

        Verifies that error dictionaries from Whisper service raise TranscriptionError.
        """
        error_dict = {
            "code": "TRANSLATION_NOT_SUPPORTED",
            "message": "Translation not available",
            "details": {},
        }
        mock_transcription_service.whisper_service.transcribe_async = AsyncMock(
            return_value=error_dict
        )

        with pytest.raises(TranscriptionError, match="Translation not available"):
            await mock_transcription_service.transcribe_media(
                sample_media_file_path, None, OutputFormat.JSON, False
            )

    @pytest.mark.asyncio
    async def test_transcribe_media_different_formats(
        self,
        mock_transcription_service,
        sample_media_file_path,
        sample_transcript_segments,
        sample_output_formats,
    ):
        """Test: Transcribe media file with different output formats (happy path).

        Verifies that all output formats are handled correctly.
        """
        mock_transcription_service.whisper_service.transcribe_async = AsyncMock(
            return_value=(sample_transcript_segments, "en", 0.95)
        )
        mock_transcription_service.whisper_service.model_id = "whisper-base"

        for format in sample_output_formats:
            result = await mock_transcription_service.transcribe_media(
                sample_media_file_path, None, format, False
            )
            if format == OutputFormat.JSON:
                assert "transcript" in result
            else:
                assert "content" in result
                assert "format" in result
