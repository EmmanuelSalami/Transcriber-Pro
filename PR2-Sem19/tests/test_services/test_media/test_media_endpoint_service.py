"""Unit tests for MediaEndpointService.

Tests cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary value analysis
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.schemas import ErrorResponse, JobStatus, OutputFormat
from app.services.media.media_endpoint_service import (FileUploadResult,
                                                       MediaEndpointService,
                                                       TranscriptionParams,
                                                       UrlUploadResult)


class TestMediaEndpointServiceInit:
    """Test MediaEndpointService initialization."""

    @patch("app.services.media.media_endpoint_service.MediaValidationService")
    @patch("app.services.media.media_endpoint_service.FileStorageService")
    @patch("app.services.media.media_endpoint_service.MediaDownloadService")
    @patch("app.services.media.media_endpoint_service.TranscriptionService")
    @patch("app.services.media.media_endpoint_service.JobManager")
    def test_init_with_default_services(
        self,
        mock_job_manager,
        mock_transcription,
        mock_media_download,
        mock_file_storage,
        mock_validation,
    ):
        """Test initialization with default services."""
        # Act
        service = MediaEndpointService()

        # Assert
        assert service.validation_service is not None
        assert service.file_storage_service is not None
        assert service.media_download_service is not None
        assert service.transcription_service is not None
        assert service.job_manager is not None

    def test_init_with_custom_services(self):
        """Test initialization with custom services."""
        # Arrange
        mock_validation = Mock()
        mock_file_storage = Mock()
        mock_media_download = Mock()
        mock_transcription = Mock()
        mock_job_manager = Mock()

        # Act
        service = MediaEndpointService(
            validation_service=mock_validation,
            file_storage_service=mock_file_storage,
            media_download_service=mock_media_download,
            transcription_service=mock_transcription,
            job_manager=mock_job_manager,
        )

        # Assert
        assert service.validation_service == mock_validation
        assert service.file_storage_service == mock_file_storage
        assert service.media_download_service == mock_media_download
        assert service.transcription_service == mock_transcription
        assert service.job_manager == mock_job_manager


class TestIsLevel3Enabled:
    """Test is_level3_enabled method."""

    def test_is_level3_enabled_true(self):
        """Test that Level 3 is enabled when both queue and S3 are available."""
        # Arrange
        mock_queue = Mock()
        mock_s3 = Mock()
        mock_s3.is_enabled = Mock(return_value=True)

        service = MediaEndpointService(queue_service=mock_queue, s3_storage_service=mock_s3)

        # Act
        result = service.is_level3_enabled()

        # Assert
        assert result is True

    def test_is_level3_enabled_false_no_queue(self):
        """Test that Level 3 is disabled when queue is not available."""
        # Arrange
        mock_s3 = Mock()
        mock_s3.is_enabled = Mock(return_value=True)

        service = MediaEndpointService(queue_service=None, s3_storage_service=mock_s3)

        # Act
        result = service.is_level3_enabled()

        # Assert
        assert result is False

    def test_is_level3_enabled_false_no_s3(self):
        """Test that Level 3 is disabled when S3 is not available."""
        # Arrange
        mock_queue = Mock()
        mock_s3 = Mock()
        mock_s3.is_enabled = Mock(return_value=False)

        service = MediaEndpointService(queue_service=mock_queue, s3_storage_service=mock_s3)

        # Act
        result = service.is_level3_enabled()

        # Assert
        assert result is False


class TestParseFormatParameter:
    """Test parse_format_parameter method."""

    def test_parse_format_parameter_success(self, mock_media_endpoint_service):
        """Test successful format parameter parsing."""
        # Act
        output_format, error = mock_media_endpoint_service.parse_format_parameter("json")

        # Assert
        assert output_format == OutputFormat.JSON
        assert error is None

    def test_parse_format_parameter_lowercase(self, mock_media_endpoint_service):
        """Test format parameter parsing with lowercase."""
        # Act
        output_format, error = mock_media_endpoint_service.parse_format_parameter("JSON")

        # Assert
        assert output_format == OutputFormat.JSON
        assert error is None

    def test_parse_format_parameter_invalid(self, mock_media_endpoint_service):
        """Test format parameter parsing with invalid format."""
        # Act
        output_format, error = mock_media_endpoint_service.parse_format_parameter("invalid")

        # Assert
        assert output_format is None
        assert isinstance(error, ErrorResponse)
        assert error.code == "INVALID_FORMAT"

    def test_parse_format_parameter_empty(self, mock_media_endpoint_service):
        """Test format parameter parsing with empty string (should default to JSON)."""
        # Act
        output_format, error = mock_media_endpoint_service.parse_format_parameter("")

        # Assert
        assert output_format == OutputFormat.JSON
        assert error is None


class TestParseTranscriptionParameters:
    """Test parse_transcription_parameters method."""

    def test_parse_transcription_parameters_success(self, mock_media_endpoint_service):
        """Test successful transcription parameters parsing."""
        # Act
        params, error = mock_media_endpoint_service.parse_transcription_parameters(
            "en", "json", "https://example.com/webhook"
        )

        # Assert
        assert isinstance(params, TranscriptionParams)
        assert params.translate_to == "en"
        assert params.output_format == OutputFormat.JSON
        assert params.webhook_url == "https://example.com/webhook"
        assert error is None

    def test_parse_transcription_parameters_no_translation(self, mock_media_endpoint_service):
        """Test transcription parameters parsing without translation."""
        # Act
        params, error = mock_media_endpoint_service.parse_transcription_parameters(
            None, "json", None
        )

        # Assert
        assert isinstance(params, TranscriptionParams)
        assert params.translate_to is None
        assert params.webhook_url is None
        assert error is None

    def test_parse_transcription_parameters_invalid_format(self, mock_media_endpoint_service):
        """Test transcription parameters parsing with invalid format."""
        # Act
        params, error = mock_media_endpoint_service.parse_transcription_parameters(
            "en", "invalid", None
        )

        # Assert
        assert params is None
        assert isinstance(error, ErrorResponse)
        assert error.code == "INVALID_FORMAT"


class TestValidateUploadedFile:
    """Test validate_uploaded_file method."""

    def test_validate_uploaded_file_success(self, mock_upload_file_mp3):
        """Test successful file validation."""
        # Arrange
        mock_validation = Mock()
        mock_metadata = Mock()
        mock_validation.validate_upload = Mock(return_value=mock_metadata)
        service = MediaEndpointService(validation_service=mock_validation)

        # Act
        metadata, error = service.validate_uploaded_file(mock_upload_file_mp3)

        # Assert
        assert metadata == mock_metadata
        assert error is None
        mock_validation.validate_upload.assert_called_once_with(mock_upload_file_mp3)

    def test_validate_uploaded_file_error(self, mock_upload_file_mp3):
        """Test file validation with error."""
        # Arrange
        mock_validation = Mock()
        mock_validation.validate_upload = Mock(side_effect=ValueError("Invalid file"))
        service = MediaEndpointService(validation_service=mock_validation)

        # Act
        metadata, error = service.validate_uploaded_file(mock_upload_file_mp3)

        # Assert
        assert metadata is None
        assert isinstance(error, ErrorResponse)
        assert error.code == "VALIDATION_ERROR"


class TestValidateRemoteUrl:
    """Test validate_remote_url method."""

    def test_validate_remote_url_success(self, sample_media_url):
        """Test successful remote URL validation."""
        # Arrange
        mock_media_download = Mock()
        mock_media_download.get_media_info = Mock(
            return_value={"content_type": "audio/mpeg", "content_length": 1024 * 1024}
        )
        mock_validation = Mock()
        mock_metadata = Mock()
        mock_validation.validate_remote_url = Mock(return_value=mock_metadata)
        service = MediaEndpointService(
            media_download_service=mock_media_download, validation_service=mock_validation
        )

        # Act
        metadata, error = service.validate_remote_url(sample_media_url)

        # Assert
        assert metadata == mock_metadata
        assert error is None

    def test_validate_remote_url_error(self, sample_media_url):
        """Test remote URL validation with error."""
        # Arrange
        mock_media_download = Mock()
        mock_media_download.get_media_info = Mock(side_effect=ValueError("Invalid URL"))
        service = MediaEndpointService(media_download_service=mock_media_download)

        # Act
        metadata, error = service.validate_remote_url(sample_media_url)

        # Assert
        assert metadata is None
        assert isinstance(error, ErrorResponse)
        assert error.code == "VALIDATION_ERROR"


class TestHandleFileUpload:
    """Test handle_file_upload method."""

    @pytest.mark.asyncio
    async def test_handle_file_upload_success_level2(
        self, mock_upload_file_mp3, sample_job_id, temp_uploads_dir, monkeypatch
    ):
        """Test successful file upload handling (Level 2)."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_endpoint_service.settings.temp_uploads_dir",
            str(temp_uploads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_endpoint_service.settings.max_file_size_mb", 500
        )

        mock_validation = Mock()
        mock_metadata = Mock()
        mock_metadata.media_format = "mp3"
        mock_validation.validate_upload = Mock(return_value=mock_metadata)

        mock_file_storage = Mock()
        mock_file_storage.save_upload = AsyncMock(
            return_value=temp_uploads_dir / f"{sample_job_id}.mp3"
        )

        mock_job_manager = Mock()
        mock_job_manager.create_job = Mock(return_value=(sample_job_id, {"status": "queued"}))
        mock_job_manager.update_job_status = Mock()

        service = MediaEndpointService(
            validation_service=mock_validation,
            file_storage_service=mock_file_storage,
            job_manager=mock_job_manager,
        )

        # Act
        result = await service.handle_file_upload(mock_upload_file_mp3, None, "json", None)

        # Assert
        assert isinstance(result, FileUploadResult)
        assert result.job_id == sample_job_id
        assert result.error is None
        assert result.file_path is not None

    @pytest.mark.asyncio
    async def test_handle_file_upload_validation_error(self, mock_upload_file_invalid_type):
        """Test file upload handling with validation error."""
        # Arrange
        mock_validation = Mock()
        mock_validation.validate_upload = Mock(side_effect=ValueError("Invalid file type"))

        service = MediaEndpointService(validation_service=mock_validation)

        # Act
        result = await service.handle_file_upload(mock_upload_file_invalid_type, None, "json", None)

        # Assert
        assert isinstance(result, FileUploadResult)
        assert result.error is not None
        assert result.error.code == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_handle_file_upload_format_error(self, mock_upload_file_mp3):
        """Test file upload handling with format error."""
        # Arrange
        mock_validation = Mock()
        mock_metadata = Mock()
        mock_validation.validate_upload = Mock(return_value=mock_metadata)

        service = MediaEndpointService(validation_service=mock_validation)

        # Act
        result = await service.handle_file_upload(mock_upload_file_mp3, None, "invalid", None)

        # Assert
        assert isinstance(result, FileUploadResult)
        assert result.error is not None
        assert result.error.code == "INVALID_FORMAT"


class TestHandleRemoteUrl:
    """Test handle_remote_url method."""

    @pytest.mark.asyncio
    async def test_handle_remote_url_success(self, sample_media_url, sample_job_id):
        """Test successful remote URL handling."""
        # Arrange
        mock_media_download = Mock()
        mock_media_download.get_media_info = Mock(
            return_value={"content_type": "audio/mpeg", "content_length": 1024 * 1024}
        )
        mock_validation = Mock()
        mock_metadata = Mock()
        mock_validation.validate_remote_url = Mock(return_value=mock_metadata)

        mock_job_manager = Mock()
        mock_job_manager.create_job = Mock(return_value=(sample_job_id, {"status": "queued"}))
        mock_job_manager.update_job_status = Mock()

        service = MediaEndpointService(
            media_download_service=mock_media_download,
            validation_service=mock_validation,
            job_manager=mock_job_manager,
        )

        # Act
        result = await service.handle_remote_url(sample_media_url, None, "json", None)

        # Assert
        assert isinstance(result, UrlUploadResult)
        assert result.job_id == sample_job_id
        assert result.error is None
        assert result.url == sample_media_url

    @pytest.mark.asyncio
    async def test_handle_remote_url_validation_error(self, sample_media_url):
        """Test remote URL handling with validation error."""
        # Arrange
        mock_media_download = Mock()
        mock_media_download.get_media_info = Mock(side_effect=ValueError("Invalid URL"))

        service = MediaEndpointService(media_download_service=mock_media_download)

        # Act
        result = await service.handle_remote_url(sample_media_url, None, "json", None)

        # Assert
        assert isinstance(result, UrlUploadResult)
        assert result.error is not None
        assert result.error.code == "VALIDATION_ERROR"


class TestCreateJobResponse:
    """Test create_job_response method."""

    def test_create_job_response_success(self, sample_job_id):
        """Test successful job response creation."""
        # Arrange
        mock_job_manager = Mock()
        mock_job_manager.get_job = Mock(
            return_value={"status": JobStatus.PROCESSING, "created_at": "2024-01-01T12:00:00Z"}
        )

        service = MediaEndpointService(job_manager=mock_job_manager)

        job = {"status": JobStatus.QUEUED, "created_at": "2024-01-01T12:00:00Z"}
        video_id = "test-video-123"

        # Act
        response = service.create_job_response(sample_job_id, job, video_id)

        # Assert
        assert response.job_id == sample_job_id
        assert response.video_id == video_id
        assert response.status == JobStatus.PROCESSING  # Should use updated status
