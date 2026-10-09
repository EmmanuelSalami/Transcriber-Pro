"""Unit tests for error handlers.

This module tests:
- TranscriptionError handler
- YouTube API error handler
- Rate limit error handler
- Generic exception handler
- Error message sanitization
- Production vs development mode behavior
- Edge cases and error conditions
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from youtube_transcript_api import (CouldNotRetrieveTranscript,
                                    NoTranscriptFound, TranscriptsDisabled,
                                    VideoUnavailable)

from app.core.error_handlers import (_clean_youtube_error_message,
                                     _get_youtube_error_code_and_message,
                                     generic_exception_handler,
                                     rate_limit_error_handler,
                                     register_error_handlers,
                                     transcription_error_handler,
                                     youtube_api_error_handler)
from app.core.exceptions import TranscriptionError


class TestCleanYouTubeErrorMessage:
    """Test suite for _clean_youtube_error_message function."""

    def test_clean_youtube_error_message_happy_path(self):
        """Test: Clean error message with duplicate prefix.

        Verifies that duplicate "Could not retrieve a transcript" prefix
        is removed from error messages.
        """
        error_str = "Could not retrieve a transcript for the video https://youtube.com/watch?v=abc! Error message here"
        result = _clean_youtube_error_message(error_str)
        assert "Could not retrieve a transcript" not in result
        assert "Error message here" in result

    def test_clean_youtube_error_message_no_duplicate(self):
        """Test: Error message without duplicate prefix is unchanged.

        Edge case: If the error doesn't contain the duplicate pattern,
        it should be returned as-is.
        """
        error_str = "Simple error message"
        result = _clean_youtube_error_message(error_str)
        assert result == error_str

    def test_clean_youtube_error_message_with_url(self):
        """Test: URL is removed from error message.

        Verifies that YouTube URLs are removed from error messages.
        """
        error_str = "Could not retrieve a transcript for the video https://youtube.com/watch?v=abc! Actual error"
        result = _clean_youtube_error_message(error_str)
        assert "https://" not in result
        assert "Actual error" in result

    def test_clean_youtube_error_message_empty_string(self):
        """Test: Empty string is handled.

        Edge case: Empty string should be returned as-is.
        """
        result = _clean_youtube_error_message("")
        assert result == ""


class TestGetYouTubeErrorCodeAndMessage:
    """Test suite for _get_youtube_error_code_and_message function."""

    def test_get_youtube_error_ip_blocked(self):
        """Test: IP blocked error is detected correctly.

        Verifies that IP blocking errors are identified and return
        the correct error code and message.
        """
        exc = Mock(spec=CouldNotRetrieveTranscript)
        exc.__class__.__name__ = "IpBlocked"

        with patch("app.core.error_handlers.is_ip_blocked_error", return_value=True):
            code, message = _get_youtube_error_code_and_message(exc)
            assert code == "IP_BLOCKED"
            assert "IP address" in message or "blocking" in message.lower()

    def test_get_youtube_error_transcripts_disabled(self):
        """Test: TranscriptsDisabled exception is handled.

        Verifies that TranscriptsDisabled exceptions return the
        correct error code and message.
        """
        exc = TranscriptsDisabled("video_id")
        code, message = _get_youtube_error_code_and_message(exc)
        assert code == "CAPTIONS_DISABLED"
        assert message == "Captions are disabled for this video"

    def test_get_youtube_error_no_transcript_found(self):
        """Test: NoTranscriptFound exception is handled.

        Verifies that NoTranscriptFound exceptions return the
        correct error code and message.
        """
        exc = NoTranscriptFound("video_id", [], None)
        code, message = _get_youtube_error_code_and_message(exc)
        assert code == "CAPTIONS_NOT_AVAILABLE"
        assert message == "No transcript found for this video"

    def test_get_youtube_error_video_unavailable(self):
        """Test: VideoUnavailable exception is handled.

        Verifies that VideoUnavailable exceptions return the
        correct error code and message.
        """
        exc = VideoUnavailable("video_id")
        code, message = _get_youtube_error_code_and_message(exc)
        assert code == "VIDEO_UNAVAILABLE"
        assert message == "The video is unavailable"

    def test_get_youtube_error_generic_fallback(self):
        """Test: Generic error fallback for unknown exceptions.

        Verifies that unknown exception types fall back to
        generic error handling.
        """
        exc = Mock(spec=CouldNotRetrieveTranscript)
        exc.__class__.__name__ = "UnknownError"
        exc.__str__ = Mock(return_value="Generic error message")

        with patch("app.core.error_handlers.is_ip_blocked_error", return_value=False):
            code, message = _get_youtube_error_code_and_message(exc)
            assert code == "YOUTUBE_API_ERROR"
            assert message == "Generic error message"


class TestTranscriptionErrorHandler:
    """Test suite for transcription_error_handler function."""

    @pytest.mark.asyncio
    async def test_transcription_error_handler_happy_path(self, mock_request):
        """Test: TranscriptionError is handled correctly.

        Verifies that TranscriptionError exceptions are converted
        to proper JSON responses with status 400.
        """
        error = TranscriptionError(
            "Test error message", code="TEST_ERROR", details={"key": "value"}
        )

        response = await transcription_error_handler(mock_request, error)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        content = response.body.decode()
        assert "TEST_ERROR" in content
        assert "Test error message" in content
        assert "key" in content

    @pytest.mark.asyncio
    async def test_transcription_error_handler_with_details(self, mock_request):
        """Test: Error with details includes them in response.

        Verifies that error details are included in the response.
        """
        error = TranscriptionError(
            "Error with details",
            code="DETAILED_ERROR",
            details={"video_id": "abc123", "reason": "test"},
        )

        response = await transcription_error_handler(mock_request, error)
        content = response.body.decode()
        assert "video_id" in content
        assert "abc123" in content

    @pytest.mark.asyncio
    async def test_transcription_error_handler_no_details(self, mock_request):
        """Test: Error without details uses empty dict.

        Edge case: Error without details should still work.
        """
        error = TranscriptionError("Simple error", code="SIMPLE_ERROR")

        response = await transcription_error_handler(mock_request, error)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_transcription_error_handler_production_sanitization(
        self, mock_request, mock_settings_production
    ):
        """Test: Error messages are sanitized in production.

        Verifies that error messages are sanitized when in production mode.
        """
        with patch("app.core.error_handlers.settings", mock_settings_production):
            with patch("app.core.error_handlers.sanitize_error_message") as mock_sanitize:
                mock_sanitize.return_value = "Sanitized message"

                error = TranscriptionError("Sensitive error with /path/to/file")
                await transcription_error_handler(mock_request, error)

                # Verify sanitization was called
                mock_sanitize.assert_called()

    @pytest.mark.asyncio
    async def test_transcription_error_handler_production_sanitizes_details(
        self, mock_request, mock_settings_production
    ):
        """Test: Error details are sanitized in production.

        Verifies that details values are sanitized in production mode.
        """
        with patch("app.core.error_handlers.settings", mock_settings_production):
            with patch("app.core.error_handlers.sanitize_error_message") as mock_sanitize:
                mock_sanitize.return_value = "Sanitized"

                error = TranscriptionError(
                    "Error", details={"path": "/sensitive/path", "number": 42}
                )
                await transcription_error_handler(mock_request, error)

                # Verify sanitization was called for string values
                assert mock_sanitize.call_count >= 1


class TestYouTubeApiErrorHandler:
    """Test suite for youtube_api_error_handler function."""

    @pytest.mark.asyncio
    async def test_youtube_api_error_handler_transcripts_disabled(self, mock_request):
        """Test: TranscriptsDisabled exception is handled.

        Verifies that TranscriptsDisabled exceptions are converted
        to proper JSON responses.
        """
        exc = TranscriptsDisabled("video_id")
        response = await youtube_api_error_handler(mock_request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        content = response.body.decode()
        assert "CAPTIONS_DISABLED" in content

    @pytest.mark.asyncio
    async def test_youtube_api_error_handler_no_transcript(self, mock_request):
        """Test: NoTranscriptFound exception is handled."""
        exc = NoTranscriptFound("video_id", [], None)
        response = await youtube_api_error_handler(mock_request, exc)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = response.body.decode()
        assert "CAPTIONS_NOT_AVAILABLE" in content

    @pytest.mark.asyncio
    async def test_youtube_api_error_handler_video_unavailable(self, mock_request):
        """Test: VideoUnavailable exception is handled."""
        exc = VideoUnavailable("video_id")
        response = await youtube_api_error_handler(mock_request, exc)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = response.body.decode()
        assert "VIDEO_UNAVAILABLE" in content

    @pytest.mark.asyncio
    async def test_youtube_api_error_handler_ip_blocked(self, mock_request):
        """Test: IP blocked error is handled."""
        exc = Mock(spec=CouldNotRetrieveTranscript)

        with patch(
            "app.core.error_handlers._get_youtube_error_code_and_message",
            return_value=("IP_BLOCKED", "IP address blocked"),
        ):
            response = await youtube_api_error_handler(mock_request, exc)

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            content = response.body.decode()
            assert "IP_BLOCKED" in content


class TestRateLimitErrorHandler:
    """Test suite for rate_limit_error_handler function."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_handler_happy_path(self, mock_request):
        """Test: RateLimitExceeded is handled correctly.

        Verifies that rate limit errors return 429 status with
        Retry-After header.
        """
        exc = Mock(spec=RateLimitExceeded)
        exc.detail = "Rate limit exceeded"
        exc.retry_after = 60

        with patch("app.core.error_handlers.settings") as mock_settings:
            mock_settings.rate_limit_default_retry_after = 60

            response = await rate_limit_error_handler(mock_request, exc)

            assert isinstance(response, JSONResponse)
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            assert "Retry-After" in response.headers
            assert response.headers["Retry-After"] == "60"

            content = response.body.decode()
            assert "RATE_LIMIT_EXCEEDED" in content

    @pytest.mark.asyncio
    async def test_rate_limit_error_handler_default_retry_after(self, mock_request):
        """Test: Default retry_after when not provided.

        Edge case: When retry_after is not set, uses default from settings.
        """
        exc = Mock(spec=RateLimitExceeded)
        exc.detail = "Rate limit exceeded"
        # No retry_after attribute

        with patch("app.core.error_handlers.settings") as mock_settings:
            mock_settings.rate_limit_default_retry_after = 120

            response = await rate_limit_error_handler(mock_request, exc)

            assert response.headers["Retry-After"] == "120"
            content = response.body.decode()
            assert "120" in content or "retry_after" in content.lower()

    @pytest.mark.asyncio
    async def test_rate_limit_error_handler_logs_warning(self, mock_request):
        """Test: Rate limit errors are logged.

        Verifies that rate limit errors trigger logging.
        """
        exc = Mock(spec=RateLimitExceeded)
        exc.detail = "Rate limit exceeded"

        with patch("app.core.error_handlers.logger") as mock_logger:
            with patch("app.core.error_handlers.settings") as mock_settings:
                mock_settings.rate_limit_default_retry_after = 60
                await rate_limit_error_handler(mock_request, exc)

                mock_logger.warning.assert_called_once()


class TestGenericExceptionHandler:
    """Test suite for generic_exception_handler function."""

    @pytest.mark.asyncio
    async def test_generic_exception_handler_happy_path(self, mock_request):
        """Test: Generic exception is handled correctly.

        Verifies that unhandled exceptions return 500 status with
        generic error message.
        """
        exc = ValueError("Something went wrong")

        with patch("app.core.error_handlers.settings") as mock_settings:
            mock_settings.is_production.return_value = False

            response = await generic_exception_handler(mock_request, exc)

            assert isinstance(response, JSONResponse)
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

            content = response.body.decode()
            assert "INTERNAL_SERVER_ERROR" in content
            assert "internal server error" in content.lower()

    @pytest.mark.asyncio
    async def test_generic_exception_handler_production_sanitization(
        self, mock_request, mock_settings_production
    ):
        """Test: Error messages are sanitized in production.

        Verifies that error messages are sanitized in production mode.
        """
        exc = ValueError("Error with /sensitive/path")

        with patch("app.core.error_handlers.settings", mock_settings_production):
            with patch("app.core.error_handlers.sanitize_error_message") as mock_sanitize:
                mock_sanitize.return_value = "Sanitized error"

                await generic_exception_handler(mock_request, exc)

                # Verify sanitization was called
                mock_sanitize.assert_called()

    @pytest.mark.asyncio
    async def test_generic_exception_handler_includes_error_type(self, mock_request):
        """Test: Error type is included in response details.

        Verifies that the exception class name is included in details.
        """
        exc = KeyError("missing key")

        with patch("app.core.error_handlers.settings") as mock_settings:
            mock_settings.is_production.return_value = False

            response = await generic_exception_handler(mock_request, exc)

            content = response.body.decode()
            assert "KeyError" in content or "error_type" in content.lower()

    @pytest.mark.asyncio
    async def test_generic_exception_handler_logs_exception(self, mock_request):
        """Test: Exceptions are logged with traceback.

        Verifies that exceptions trigger logging with full traceback.
        """
        exc = RuntimeError("Runtime error")

        with patch("app.core.error_handlers.logger") as mock_logger:
            with patch("app.core.error_handlers.settings") as mock_settings:
                mock_settings.is_production.return_value = False
                await generic_exception_handler(mock_request, exc)

                mock_logger.exception.assert_called_once()


class TestRegisterErrorHandlers:
    """Test suite for register_error_handlers function."""

    def test_register_error_handlers_registers_all_handlers(self):
        """Test: All error handlers are registered.

        Verifies that register_error_handlers registers all four
        error handler types.
        """
        mock_app = Mock()

        register_error_handlers(mock_app)

        # Verify all handlers were registered
        assert mock_app.add_exception_handler.call_count == 4

        # Check that TranscriptionError handler was registered
        calls = [call[0][0] for call in mock_app.add_exception_handler.call_args_list]
        assert TranscriptionError in calls
        assert CouldNotRetrieveTranscript in calls
        assert RateLimitExceeded in calls
        assert Exception in calls

    def test_register_error_handlers_correct_order(self):
        """Test: Handlers are registered in correct order.

        Verifies that specific handlers are registered before generic ones.
        """
        mock_app = Mock()

        register_error_handlers(mock_app)

        # Get the exception types in registration order
        exception_types = [call[0][0] for call in mock_app.add_exception_handler.call_args_list]

        # Generic Exception handler should be last
        assert exception_types[-1] is Exception


class TestErrorHandlersEdgeCases:
    """Test suite for edge cases in error handlers."""

    @pytest.mark.asyncio
    async def test_transcription_error_handler_empty_message(self, mock_request):
        """Test: Error with empty message is handled.

        Edge case: Empty message should still work.
        """
        error = TranscriptionError("", code="EMPTY_ERROR")
        response = await transcription_error_handler(mock_request, error)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_transcription_error_handler_unicode_message(self, mock_request):
        """Test: Error with unicode message is handled.

        Edge case: Unicode characters in error message.
        """
        error = TranscriptionError("错误消息", code="UNICODE_ERROR")
        response = await transcription_error_handler(mock_request, error)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_rate_limit_error_handler_no_client_host(self):
        """Test: Rate limit handler handles missing client host.

        Edge case: Request without client host should still work.
        """
        request = Mock(spec=Request)
        request.client = None

        exc = Mock(spec=RateLimitExceeded)
        exc.detail = "Rate limit exceeded"

        with patch("app.core.error_handlers.settings") as mock_settings:
            mock_settings.rate_limit_default_retry_after = 60
            response = await rate_limit_error_handler(request, exc)
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
