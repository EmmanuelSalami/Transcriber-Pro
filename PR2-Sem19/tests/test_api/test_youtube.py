"""
Comprehensive unit tests for YouTube transcription endpoint.

This module tests the /transcriptions/youtube endpoint covering:
- Happy path scenarios (sync and async processing)
- Edge cases (boundary values, optional parameters)
- Error conditions (invalid inputs, service errors)
- Rate limiting and authentication
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse, Response

from app.api.v1.endpoints.youtube import (get_rate_limit_key_from_request,
                                          transcribe_youtube)
from app.core.exceptions import TranscriptionError
from app.models.schemas import JobResponse, TranscriptionResponse


class TestGetRateLimitKeyFromRequest:
    """Tests for get_rate_limit_key_from_request helper function."""

    def test_get_rate_limit_key_with_bearer_token(self, mock_request):
        """Test: Extract API key from Bearer token in Authorization header."""
        # Arrange
        mock_request.headers = {"Authorization": "Bearer test-api-key-123"}

        # Act
        with patch("app.api.v1.endpoints.youtube.get_rate_limit_key") as mock_get_key:
            mock_get_key.return_value = "api_key:test-api-key-123"
            result = get_rate_limit_key_from_request(mock_request)

        # Assert
        assert result == "api_key:test-api-key-123"
        mock_get_key.assert_called_once_with("test-api-key-123")

    def test_get_rate_limit_key_no_auth_in_production(self, mock_request_no_auth):
        """Test: Raise HTTPException in production when no API key provided."""
        # Arrange
        mock_request_no_auth.headers = {}

        # Act & Assert
        with patch("app.api.v1.endpoints.youtube.settings") as mock_settings:
            mock_settings.is_production.return_value = True
            with pytest.raises(HTTPException) as exc_info:
                get_rate_limit_key_from_request(mock_request_no_auth)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "API key required" in exc_info.value.detail

    def test_get_rate_limit_key_no_auth_in_dev(self, mock_request_no_auth):
        """Test: Fall back to IP address in development mode."""
        # Arrange
        mock_request_no_auth.headers = {}

        # Act
        with patch("app.api.v1.endpoints.youtube.settings") as mock_settings:
            with patch("app.api.v1.endpoints.youtube.get_remote_address") as mock_get_ip:
                mock_settings.is_production.return_value = False
                mock_get_ip.return_value = "127.0.0.1"
                result = get_rate_limit_key_from_request(mock_request_no_auth)

        # Assert
        assert result == "127.0.0.1"
        mock_get_ip.assert_called_once_with(mock_request_no_auth)

    def test_get_rate_limit_key_malformed_header(self, mock_request):
        """Test: Handle malformed Authorization header gracefully."""
        # Arrange
        mock_request.headers = {"Authorization": "InvalidFormat test-key"}

        # Act & Assert
        with patch("app.api.v1.endpoints.youtube.settings") as mock_settings:
            mock_settings.is_production.return_value = True
            with pytest.raises(HTTPException) as exc_info:
                get_rate_limit_key_from_request(mock_request)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestTranscribeYouTube:
    """Tests for transcribe_youtube endpoint."""

    @pytest.mark.asyncio
    async def test_transcribe_youtube_sync_json_success(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Happy path - Synchronous processing with JSON format returns TranscriptionResponse."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        format_str = "json"
        translate_to = None
        diarise = "false"
        webhook_url = None

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

            # Act
            result = await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=translate_to,
                format=format_str,
                diarise=diarise,
                webhookUrl=webhook_url,
            )

        # Assert
        assert isinstance(result, TranscriptionResponse)
        assert result.status == "completed"
        assert result.source == "youtube_captions"
        assert result.language == "en"
        mock_service.transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_youtube_sync_text_success(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Happy path - Synchronous processing with TEXT format returns Response with text content."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        format_str = "text"
        sample_transcription_result_sync["content"] = "Hello world"

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

            # Act
            result = await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=None,
                format=format_str,
                diarise="false",
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        assert result.media_type == "text/plain"
        assert b"Hello world" in result.body
        assert 'filename="transcription.txt"' in result.headers.get("Content-Disposition", "")

    @pytest.mark.asyncio
    async def test_transcribe_youtube_sync_srt_success(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Happy path - Synchronous processing with SRT format returns Response with SRT content."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        format_str = "srt"
        sample_transcription_result_sync["content"] = "1\n00:00:00,000 --> 00:00:01,000\nHello\n"

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

            # Act
            result = await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=None,
                format=format_str,
                diarise="false",
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        assert result.media_type == "text/srt"
        assert 'filename="transcription.srt"' in result.headers.get("Content-Disposition", "")

    @pytest.mark.asyncio
    async def test_transcribe_youtube_sync_vtt_success(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Happy path - Synchronous processing with VTT format returns Response with VTT content."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        format_str = "vtt"
        sample_transcription_result_sync["content"] = (
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n"
        )

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

            # Act
            result = await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=None,
                format=format_str,
                diarise="false",
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        assert result.media_type == "text/vtt"
        assert 'filename="transcription.vtt"' in result.headers.get("Content-Disposition", "")

    @pytest.mark.asyncio
    async def test_transcribe_youtube_async_success(
        self,
        mock_request,
        mock_background_tasks,
        sample_transcription_result_async,
        mock_job_manager,
    ):
        """Test: Happy path - Asynchronous processing returns JobResponse."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        format_str = "json"

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_async)
            mock_service.job_manager = mock_job_manager
            mock_service.job_manager.update_job_status = Mock()
            mock_service.job_manager.schedule_async_transcription = Mock(return_value=AsyncMock())
            mock_service.job_manager.get_job = Mock(
                return_value={
                    "status": "processing",
                    "job_id": sample_transcription_result_async["jobId"],
                    "video_url": url,
                }
            )

            # Act
            result = await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=None,
                format=format_str,
                diarise="false",
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, JobResponse)
        assert result.job_id == sample_transcription_result_async["jobId"]
        assert result.status == "processing"
        mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_youtube_with_translation(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Happy path - Transcription with translation parameter."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        translate_to = "es"

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

            # Act
            result = await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=translate_to,
                format="json",
                diarise="false",
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, TranscriptionResponse)
        call_args = mock_service.transcribe.call_args
        assert call_args.kwargs["translate_to"] == translate_to

    @pytest.mark.asyncio
    async def test_transcribe_youtube_with_diarization(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Happy path - Transcription with diarization enabled."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        diarise = "true"

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

            # Act
            result = await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=None,
                format="json",
                diarise=diarise,
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, TranscriptionResponse)
        call_args = mock_service.transcribe.call_args
        assert call_args.kwargs["diarise"] is True

    @pytest.mark.asyncio
    async def test_transcribe_youtube_with_webhook(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Happy path - Transcription with webhook URL."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        webhook_url = "https://example.com/webhook"

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

            # Act
            result = await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=None,
                format="json",
                diarise="false",
                webhookUrl=webhook_url,
            )

        # Assert
        assert isinstance(result, TranscriptionResponse)
        call_args = mock_service.transcribe.call_args
        assert call_args.kwargs["webhook_url"] == webhook_url

    @pytest.mark.asyncio
    async def test_transcribe_youtube_invalid_format(self, mock_request, mock_background_tasks):
        """Test: Error condition - Invalid format parameter returns ErrorResponse."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        format_str = "invalid_format"

        # Act
        result = await transcribe_youtube(
            request=mock_request,
            background_tasks=mock_background_tasks,
            api_key="test-api-key",
            url=url,
            translateTo=None,
            format=format_str,
            diarise="false",
            webhookUrl=None,
        )

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST
        content = json.loads(result.body)
        assert content["code"] == "INVALID_FORMAT"

    @pytest.mark.asyncio
    async def test_transcribe_youtube_service_error(self, mock_request, mock_background_tasks):
        """Test: Error condition - TranscriptionService raises TranscriptionError."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(
                side_effect=TranscriptionError("Video not found", code="VIDEO_NOT_FOUND")
            )

            # Act & Assert
            with pytest.raises(TranscriptionError) as exc_info:
                await transcribe_youtube(
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    api_key="test-api-key",
                    url=url,
                    translateTo=None,
                    format="json",
                    diarise="false",
                    webhookUrl=None,
                )

            assert exc_info.value.code == "VIDEO_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_transcribe_youtube_empty_url(self, mock_request, mock_background_tasks):
        """Test: Edge case - Empty URL string raises InvalidVideoURLError."""
        # Arrange
        url = ""

        # Act & Assert
        from app.core.exceptions import InvalidVideoURLError

        with pytest.raises(InvalidVideoURLError) as exc_info:
            await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=None,
                format="json",
                diarise="false",
                webhookUrl=None,
            )

        assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_transcribe_youtube_very_long_url(
        self, mock_request, mock_background_tasks, boundary_url_lengths
    ):
        """Test: Edge case - Very long URL (boundary value)."""
        # Arrange
        url = boundary_url_lengths["too_long"]

        # Act & Assert
        # FastAPI should validate max_length, but if it passes, service should handle it
        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(
                side_effect=TranscriptionError("URL too long", code="INVALID_URL")
            )

            with pytest.raises(TranscriptionError):
                await transcribe_youtube(
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    api_key="test-api-key",
                    url=url,
                    translateTo=None,
                    format="json",
                    diarise="false",
                    webhookUrl=None,
                )

    @pytest.mark.asyncio
    async def test_transcribe_youtube_diarise_case_insensitive(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Edge case - Diarise parameter is case-insensitive."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        for diarise_value in ["True", "TRUE", "true", "False", "FALSE", "false"]:
            with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
                mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

                # Act
                await transcribe_youtube(
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    api_key="test-api-key",
                    url=url,
                    translateTo=None,
                    format="json",
                    diarise=diarise_value,
                    webhookUrl=None,
                )

                # Assert
                call_args = mock_service.transcribe.call_args
                expected_bool = diarise_value.lower() == "true"
                assert call_args.kwargs["diarise"] == expected_bool

    @pytest.mark.asyncio
    async def test_transcribe_youtube_format_case_insensitive(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Edge case - Format parameter is case-insensitive."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        sample_transcription_result_sync["content"] = "Hello world"

        for format_value in ["JSON", "Json", "json", "TEXT", "Text", "text"]:
            with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
                mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

                # Act
                result = await transcribe_youtube(
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    api_key="test-api-key",
                    url=url,
                    translateTo=None,
                    format=format_value,
                    diarise="false",
                    webhookUrl=None,
                )

                # Assert
                assert result is not None

    @pytest.mark.asyncio
    async def test_transcribe_youtube_none_optional_params(
        self, mock_request, mock_background_tasks, sample_transcription_result_sync
    ):
        """Test: Edge case - All optional parameters are None."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_sync)

            # Act
            result = await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=None,
                format="json",
                diarise="false",
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, TranscriptionResponse)
        call_args = mock_service.transcribe.call_args
        assert call_args.kwargs["translate_to"] is None
        assert call_args.kwargs["webhook_url"] is None

    @pytest.mark.asyncio
    async def test_transcribe_youtube_async_job_status_update(
        self,
        mock_request,
        mock_background_tasks,
        sample_transcription_result_async,
        mock_job_manager,
    ):
        """Test: Async job status is updated to PROCESSING immediately."""
        # Arrange
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        job_id = sample_transcription_result_async["jobId"]

        with patch("app.api.v1.endpoints.youtube.transcription_service") as mock_service:
            mock_service.transcribe = AsyncMock(return_value=sample_transcription_result_async)
            mock_service.job_manager = mock_job_manager
            mock_service.job_manager.update_job_status = Mock()
            mock_service.job_manager.schedule_async_transcription = Mock(return_value=AsyncMock())
            mock_service.job_manager.get_job = Mock(
                return_value={
                    "status": "processing",
                    "job_id": job_id,
                    "video_url": url,
                }
            )

            # Act
            await transcribe_youtube(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                url=url,
                translateTo=None,
                format="json",
                diarise="false",
                webhookUrl=None,
            )

        # Assert
        from app.models.schemas import JobStatus

        mock_service.job_manager.update_job_status.assert_called_once_with(
            job_id, JobStatus.PROCESSING, progress=0.0
        )
