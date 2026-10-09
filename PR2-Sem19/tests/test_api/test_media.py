"""
Comprehensive unit tests for Media transcription endpoint.

This module tests the /transcriptions/media endpoint covering:
- Happy path scenarios (file upload and URL processing)
- Edge cases (boundary values, optional parameters)
- Error conditions (invalid inputs, service errors)
- Validation (file type, size, URL format)
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import status
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.media import (get_rate_limit_key_from_request,
                                        transcribe_media)
from app.models.schemas import (ErrorResponse, JobResponse, JobStatus,
                                OutputFormat)


class TestGetRateLimitKeyFromRequestMedia:
    """Tests for get_rate_limit_key_from_request helper function in media endpoint."""

    def test_get_rate_limit_key_with_bearer_token(self, mock_request):
        """Test: Extract API key from Bearer token in Authorization header."""
        # Arrange
        mock_request.headers = {"Authorization": "Bearer test-api-key-123"}

        # Act
        with patch("app.api.v1.endpoints.media.get_rate_limit_key") as mock_get_key:
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
        with patch("app.api.v1.endpoints.media.settings") as mock_settings:
            mock_settings.is_production.return_value = True
            with pytest.raises(Exception) as exc_info:
                get_rate_limit_key_from_request(mock_request_no_auth)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestTranscribeMedia:
    """Tests for transcribe_media endpoint."""

    @pytest.mark.asyncio
    async def test_transcribe_media_file_upload_success(
        self, mock_request, mock_background_tasks, mock_upload_file, sample_file_upload_result
    ):
        """Test: Happy path - File upload returns JobResponse."""
        # Arrange
        translate_to = None
        format_str = "json"
        webhook_url = None

        with patch("app.api.v1.endpoints.media.media_endpoint_service") as mock_service:
            mock_service.handle_file_upload = AsyncMock(return_value=sample_file_upload_result)
            mock_service.is_level3_enabled = Mock(return_value=False)
            mock_service.create_job_response = Mock(
                return_value=JobResponse(
                    job_id="test-job-id",
                    status=JobStatus.QUEUED,
                    created_at="2024-01-01T12:00:00Z",
                    video_id="test-video-id",
                )
            )

            # Act
            result = await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=mock_upload_file,
                url=None,
                translateTo=translate_to,
                format=format_str,
                webhookUrl=webhook_url,
            )

        # Assert
        assert isinstance(result, JobResponse)
        assert result.job_id == "test-job-id"
        mock_service.handle_file_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_media_url_success(
        self, mock_request, mock_background_tasks, sample_url_upload_result
    ):
        """Test: Happy path - Remote URL processing returns JobResponse."""
        # Arrange
        url = "https://cdn.example.com/audio.mp3"
        translate_to = None
        format_str = "json"
        webhook_url = None

        with patch("app.api.v1.endpoints.media.media_endpoint_service") as mock_service:
            mock_service.handle_remote_url = AsyncMock(return_value=sample_url_upload_result)
            mock_service.is_level3_enabled = Mock(return_value=False)
            mock_service.create_job_response = Mock(
                return_value=JobResponse(
                    job_id="test-job-id",
                    status=JobStatus.QUEUED,
                    created_at="2024-01-01T12:00:00Z",
                    video_id="test-video-id",
                )
            )

            # Act
            result = await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=None,
                url=url,
                translateTo=translate_to,
                format=format_str,
                webhookUrl=webhook_url,
            )

        # Assert
        assert isinstance(result, JobResponse)
        assert result.job_id == "test-job-id"
        mock_service.handle_remote_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_media_both_file_and_url_provided(
        self, mock_request, mock_background_tasks, mock_upload_file
    ):
        """Test: Error condition - Both file and URL provided returns ErrorResponse."""
        # Arrange
        url = "https://cdn.example.com/audio.mp3"

        # Act
        result = await transcribe_media(
            request=mock_request,
            background_tasks=mock_background_tasks,
            api_key="test-api-key",
            file=mock_upload_file,
            url=url,
            translateTo=None,
            format="json",
            webhookUrl=None,
        )

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST
        content = json.loads(result.body)
        assert content["code"] == "INVALID_INPUT"
        assert "both" in content["message"].lower()

    @pytest.mark.asyncio
    async def test_transcribe_media_neither_file_nor_url_provided(
        self, mock_request, mock_background_tasks
    ):
        """Test: Error condition - Neither file nor URL provided returns ErrorResponse."""
        # Act
        result = await transcribe_media(
            request=mock_request,
            background_tasks=mock_background_tasks,
            api_key="test-api-key",
            file=None,
            url=None,
            translateTo=None,
            format="json",
            webhookUrl=None,
        )

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST
        content = json.loads(result.body)
        assert content["code"] == "MISSING_INPUT"

    @pytest.mark.asyncio
    async def test_transcribe_media_file_upload_with_translation(
        self, mock_request, mock_background_tasks, mock_upload_file, sample_file_upload_result
    ):
        """Test: Happy path - File upload with translation parameter."""
        # Arrange
        translate_to = "es"

        with patch("app.api.v1.endpoints.media.media_endpoint_service") as mock_service:
            mock_service.handle_file_upload = AsyncMock(return_value=sample_file_upload_result)
            mock_service.is_level3_enabled = Mock(return_value=False)
            mock_service.create_job_response = Mock(
                return_value=JobResponse(
                    job_id="test-job-id",
                    status=JobStatus.QUEUED,
                    created_at="2024-01-01T12:00:00Z",
                    video_id="test-video-id",
                )
            )

            # Act
            await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=mock_upload_file,
                url=None,
                translateTo=translate_to,
                format="json",
                webhookUrl=None,
            )

        # Assert
        call_args = mock_service.handle_file_upload.call_args
        assert call_args[0][1] == translate_to  # translateTo is second positional arg

    @pytest.mark.asyncio
    async def test_transcribe_media_file_upload_with_webhook(
        self, mock_request, mock_background_tasks, mock_upload_file, sample_file_upload_result
    ):
        """Test: Happy path - File upload with webhook URL."""
        # Arrange
        webhook_url = "https://example.com/webhook"

        with patch("app.api.v1.endpoints.media.media_endpoint_service") as mock_service:
            mock_service.handle_file_upload = AsyncMock(return_value=sample_file_upload_result)
            mock_service.is_level3_enabled = Mock(return_value=False)
            mock_service.create_job_response = Mock(
                return_value=JobResponse(
                    job_id="test-job-id",
                    status=JobStatus.QUEUED,
                    created_at="2024-01-01T12:00:00Z",
                    video_id="test-video-id",
                )
            )

            # Act
            await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=mock_upload_file,
                url=None,
                translateTo=None,
                format="json",
                webhookUrl=webhook_url,
            )

        # Assert
        call_args = mock_service.handle_file_upload.call_args
        assert call_args[0][3] == webhook_url  # webhookUrl is fourth positional arg

    @pytest.mark.asyncio
    async def test_transcribe_media_file_upload_with_different_formats(
        self, mock_request, mock_background_tasks, mock_upload_file, sample_file_upload_result
    ):
        """Test: Happy path - File upload with different output formats."""
        # Arrange
        formats = ["json", "text", "srt", "vtt"]

        for format_str in formats:
            with patch("app.api.v1.endpoints.media.media_endpoint_service") as mock_service:
                mock_service.handle_file_upload = AsyncMock(return_value=sample_file_upload_result)
                mock_service.is_level3_enabled = Mock(return_value=False)
                mock_service.create_job_response = Mock(
                    return_value=JobResponse(
                        job_id="test-job-id",
                        status=JobStatus.QUEUED,
                        created_at="2024-01-01T12:00:00Z",
                        video_id="test-video-id",
                    )
                )

                # Act
                result = await transcribe_media(
                    request=mock_request,
                    background_tasks=mock_background_tasks,
                    api_key="test-api-key",
                    file=mock_upload_file,
                    url=None,
                    translateTo=None,
                    format=format_str,
                    webhookUrl=None,
                )

                # Assert
                assert isinstance(result, JobResponse)

    @pytest.mark.asyncio
    async def test_transcribe_media_file_upload_service_error(
        self, mock_request, mock_background_tasks, mock_upload_file
    ):
        """Test: Error condition - MediaEndpointService returns error."""
        # Arrange
        error_result = Mock()
        error_result.error = ErrorResponse(
            code="VALIDATION_ERROR", message="Invalid file type", details={}
        )
        error_result.job_id = None

        with patch("app.api.v1.endpoints.media.media_endpoint_service") as mock_service:
            mock_service.handle_file_upload = AsyncMock(return_value=error_result)

            # Act
            result = await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=mock_upload_file,
                url=None,
                translateTo=None,
                format="json",
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST
        content = json.loads(result.body)
        assert content["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_transcribe_media_url_service_error(self, mock_request, mock_background_tasks):
        """Test: Error condition - MediaEndpointService returns error for URL."""
        # Arrange
        url = "https://cdn.example.com/audio.mp3"
        error_result = Mock()
        error_result.error = ErrorResponse(
            code="INVALID_URL", message="Invalid URL format", details={}
        )
        error_result.job_id = None

        with patch("app.api.v1.endpoints.media.media_endpoint_service") as mock_service:
            mock_service.handle_remote_url = AsyncMock(return_value=error_result)

            # Act
            result = await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=None,
                url=url,
                translateTo=None,
                format="json",
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, JSONResponse)
        # Service errors can return 400 or 500 depending on error type
        assert result.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        content = json.loads(result.body)
        assert content["code"] == "INVALID_URL"

    @pytest.mark.asyncio
    async def test_transcribe_media_file_upload_level3_enabled(
        self, mock_request, mock_background_tasks, mock_upload_file, sample_file_upload_result
    ):
        """Test: Happy path - File upload with Level 3 (queue) enabled."""

        # Arrange
        # Use a simple object to ensure attributes are real values, not Mocks
        class FileResult:
            def __init__(self):
                self.error = None
                self.job_id = "test-job-id"
                self.file_path = "/tmp/test_audio.mp3"  # Must be truthy for level3
                self.params = None  # Must be None to avoid level2 branch
                self.job = {"status": "queued", "job_id": "test-job-id"}
                self.video_id = None
                self.metadata = {"filename": "test_audio.mp3", "size": 1024 * 1024}

        file_result = FileResult()

        # Import the module to patch the service instance directly
        import app.api.v1.endpoints.media as media_module

        original_service = media_module.media_endpoint_service

        try:
            mock_service = Mock()
            mock_service.handle_file_upload = AsyncMock(return_value=file_result)
            mock_service.is_level3_enabled = Mock(return_value=True)
            mock_process_level3_job = AsyncMock()
            mock_service.process_level3_job = mock_process_level3_job
            mock_service.create_job_response = Mock(
                return_value=JobResponse(
                    job_id="test-job-id",
                    status=JobStatus.QUEUED,
                    created_at="2024-01-01T12:00:00Z",
                    video_id="test-video-id",
                )
            )
            media_module.media_endpoint_service = mock_service

            # Act
            result = await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=mock_upload_file,
                url=None,
                translateTo=None,
                format="json",
                webhookUrl=None,
            )

            # Assert
            assert isinstance(result, JobResponse)
            # Verify is_level3_enabled was called (this confirms the condition was checked)
            mock_service.is_level3_enabled.assert_called()
            # Verify background task was added with process_level3_job
            mock_background_tasks.add_task.assert_called_once()
            # Verify the function passed to add_task is process_level3_job
            call_args = mock_background_tasks.add_task.call_args
            assert call_args[0][0] == mock_process_level3_job
            assert call_args[0][1] == "test-job-id"
            assert call_args[0][2] == "/tmp/test_audio.mp3"
        finally:
            # Restore original service
            media_module.media_endpoint_service = original_service

    @pytest.mark.asyncio
    async def test_transcribe_media_url_level3_enabled(
        self, mock_request, mock_background_tasks, sample_url_upload_result
    ):
        """Test: Happy path - URL processing with Level 3 (queue) enabled."""
        # Arrange
        url = "https://cdn.example.com/audio.mp3"

        # Create a simple object to ensure attributes are real values, not Mocks
        class UrlResult:
            def __init__(self):
                self.error = None
                self.job_id = "test-job-id"
                self.file_path = "/tmp/downloaded_audio.mp3"  # Must be truthy for level3
                self.url = None  # Must be None to avoid level2 branch
                self.params = None  # Must be None to avoid level2 branch
                self.job = {"status": "queued", "job_id": "test-job-id"}
                self.video_id = None
                self.metadata = {"url": "https://cdn.example.com/audio.mp3"}

        url_result = UrlResult()

        # Import the module to patch the service instance directly
        import app.api.v1.endpoints.media as media_module

        original_service = media_module.media_endpoint_service

        try:
            mock_service = Mock()
            mock_service.handle_remote_url = AsyncMock(return_value=url_result)
            mock_service.is_level3_enabled = Mock(return_value=True)
            mock_process_level3_job = AsyncMock()
            mock_service.process_level3_job = mock_process_level3_job
            mock_service.create_job_response = Mock(
                return_value=JobResponse(
                    job_id="test-job-id",
                    status=JobStatus.QUEUED,
                    created_at="2024-01-01T12:00:00Z",
                    video_id="test-video-id",
                )
            )
            media_module.media_endpoint_service = mock_service

            # Act
            result = await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=None,
                url=url,
                translateTo=None,
                format="json",
                webhookUrl=None,
            )

            # Assert
            assert isinstance(result, JobResponse)
            # Verify is_level3_enabled was called (this confirms the condition was checked)
            mock_service.is_level3_enabled.assert_called()
            # Verify background task was added with process_level3_job
            mock_background_tasks.add_task.assert_called_once()
            # Verify the function passed to add_task is process_level3_job
            call_args = mock_background_tasks.add_task.call_args
            assert call_args[0][0] == mock_process_level3_job
            assert call_args[0][1] == "test-job-id"
            assert call_args[0][2] == "/tmp/downloaded_audio.mp3"
        finally:
            # Restore original service
            media_module.media_endpoint_service = original_service

    @pytest.mark.asyncio
    async def test_transcribe_media_file_upload_level2_background(
        self, mock_request, mock_background_tasks, mock_upload_file, sample_file_upload_result
    ):
        """Test: Happy path - File upload with Level 2 background processing."""

        # Arrange
        # Create a simple object to ensure attributes are real values, not Mocks
        class FileResult:
            def __init__(self):
                self.error = None
                self.job_id = "test-job-id"
                self.file_path = "/tmp/test_audio.mp3"  # Must be truthy
                self.params = {
                    "format": OutputFormat.JSON,
                    "translate_to": None,
                }  # Must be not None for level2
                self.job = {"status": "queued", "job_id": "test-job-id"}
                self.video_id = None
                self.metadata = {"filename": "test_audio.mp3", "size": 1024 * 1024}

        file_result = FileResult()

        # Import the module to patch the service instance directly
        import app.api.v1.endpoints.media as media_module

        original_service = media_module.media_endpoint_service

        try:
            mock_service = Mock()
            mock_service.handle_file_upload = AsyncMock(return_value=file_result)
            mock_service.is_level3_enabled = Mock(return_value=False)  # Level 3 disabled
            mock_process_media_upload_background = AsyncMock()
            mock_service.process_media_upload_background = mock_process_media_upload_background
            mock_service.create_job_response = Mock(
                return_value=JobResponse(
                    job_id="test-job-id",
                    status=JobStatus.QUEUED,
                    created_at="2024-01-01T12:00:00Z",
                    video_id="test-video-id",
                )
            )
            media_module.media_endpoint_service = mock_service

            # Act
            result = await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=mock_upload_file,
                url=None,
                translateTo=None,
                format="json",
                webhookUrl=None,
            )

            # Assert
            assert isinstance(result, JobResponse)
            # Verify is_level3_enabled was called (should return False for level2)
            mock_service.is_level3_enabled.assert_called()
            # Verify background task was added with process_media_upload_background
            mock_background_tasks.add_task.assert_called_once()
            # Verify the function passed to add_task is process_media_upload_background
            call_args = mock_background_tasks.add_task.call_args
            assert call_args[0][0] == mock_process_media_upload_background
            assert call_args[0][1] == "test-job-id"
            assert call_args[0][2] == "/tmp/test_audio.mp3"
            assert call_args[0][3] == file_result.metadata
            assert call_args[0][4] == file_result.params
        finally:
            # Restore original service
            media_module.media_endpoint_service = original_service

    @pytest.mark.asyncio
    async def test_transcribe_media_url_level2_background(
        self, mock_request, mock_background_tasks, sample_url_upload_result
    ):
        """Test: Happy path - URL processing with Level 2 background processing."""
        # Arrange
        url = "https://cdn.example.com/audio.mp3"

        # Create a simple object to ensure attributes are real values, not Mocks
        class UrlResult:
            def __init__(self, url):
                self.error = None
                self.job_id = "test-job-id"
                self.file_path = None  # Must be None/falsy for level2 URL path
                self.url = url  # Must be truthy for level2
                self.params = {
                    "format": OutputFormat.JSON,
                    "translate_to": None,
                }  # Must be not None for level2
                self.job = {"status": "queued", "job_id": "test-job-id"}
                self.video_id = None
                self.metadata = {"url": url}

        url_result = UrlResult(url)

        # Import the module to patch the service instance directly
        import app.api.v1.endpoints.media as media_module

        original_service = media_module.media_endpoint_service

        try:
            mock_service = Mock()
            mock_service.handle_remote_url = AsyncMock(return_value=url_result)
            mock_service.is_level3_enabled = Mock(return_value=False)  # Level 3 disabled
            mock_process_media_url_background = AsyncMock()
            mock_service.process_media_url_background = mock_process_media_url_background
            mock_service.create_job_response = Mock(
                return_value=JobResponse(
                    job_id="test-job-id",
                    status=JobStatus.QUEUED,
                    created_at="2024-01-01T12:00:00Z",
                    video_id="test-video-id",
                )
            )
            media_module.media_endpoint_service = mock_service

            # Act
            result = await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=None,
                url=url,
                translateTo=None,
                format="json",
                webhookUrl=None,
            )

            # Assert
            assert isinstance(result, JobResponse)
            # Verify is_level3_enabled was called (should return False for level2)
            mock_service.is_level3_enabled.assert_called()
            # Verify background task was added with process_media_url_background
            mock_background_tasks.add_task.assert_called_once()
            # Verify the function passed to add_task is process_media_url_background
            call_args = mock_background_tasks.add_task.call_args
            assert call_args[0][0] == mock_process_media_url_background
            assert call_args[0][1] == "test-job-id"
            assert call_args[0][2] == url
            assert call_args[0][3] == url_result.metadata
            assert call_args[0][4] == url_result.params
        finally:
            # Restore original service
            media_module.media_endpoint_service = original_service

    @pytest.mark.asyncio
    async def test_transcribe_media_empty_url_string(self, mock_request, mock_background_tasks):
        """Test: Edge case - Empty URL string treated as None."""
        # Arrange
        url = ""

        # Act
        result = await transcribe_media(
            request=mock_request,
            background_tasks=mock_background_tasks,
            api_key="test-api-key",
            file=None,
            url=url,
            translateTo=None,
            format="json",
            webhookUrl=None,
        )

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST
        content = json.loads(result.body)
        assert content["code"] == "MISSING_INPUT"

    @pytest.mark.asyncio
    async def test_transcribe_media_whitespace_url_string(
        self, mock_request, mock_background_tasks
    ):
        """Test: Edge case - Whitespace-only URL string treated as None."""
        # Arrange
        url = "   "

        # Act
        result = await transcribe_media(
            request=mock_request,
            background_tasks=mock_background_tasks,
            api_key="test-api-key",
            file=None,
            url=url,
            translateTo=None,
            format="json",
            webhookUrl=None,
        )

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST
        content = json.loads(result.body)
        assert content["code"] == "MISSING_INPUT"

    @pytest.mark.asyncio
    async def test_transcribe_media_file_with_no_filename(
        self, mock_request, mock_background_tasks
    ):
        """Test: Edge case - File upload with no filename."""
        # Arrange
        file_no_name = Mock()
        file_no_name.filename = None
        file_no_name.size = 1024

        # Act
        result = await transcribe_media(
            request=mock_request,
            background_tasks=mock_background_tasks,
            api_key="test-api-key",
            file=file_no_name,
            url=None,
            translateTo=None,
            format="json",
            webhookUrl=None,
        )

        # Assert
        # Should be treated as no file provided
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_transcribe_media_internal_server_error(
        self, mock_request, mock_background_tasks, mock_upload_file
    ):
        """Test: Error condition - Internal server error from service."""
        # Arrange
        error_result = Mock()
        error_result.error = ErrorResponse(
            code="INTERNAL_ERROR", message="Internal error", details={}
        )
        error_result.job_id = None

        with patch("app.api.v1.endpoints.media.media_endpoint_service") as mock_service:
            mock_service.handle_file_upload = AsyncMock(return_value=error_result)

            # Act
            result = await transcribe_media(
                request=mock_request,
                background_tasks=mock_background_tasks,
                api_key="test-api-key",
                file=mock_upload_file,
                url=None,
                translateTo=None,
                format="json",
                webhookUrl=None,
            )

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        content = json.loads(result.body)
        assert content["code"] == "INTERNAL_ERROR"
