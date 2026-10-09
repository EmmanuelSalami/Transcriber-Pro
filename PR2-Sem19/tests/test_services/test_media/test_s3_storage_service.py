"""Unit tests for S3StorageService.

Tests cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary value analysis
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.core.exceptions import TranscriptionError
from app.services.media.s3_storage_service import S3StorageService


class TestS3StorageServiceInit:
    """Test S3StorageService initialization."""

    def test_init_disabled(self, monkeypatch):
        """Test initialization when S3 is disabled."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", False)

        # Act
        service = S3StorageService()

        # Assert
        assert service.is_enabled() is False
        assert service._s3_client is None

    def test_init_enabled_success(self, monkeypatch, mock_s3_client):
        """Test successful initialization when S3 is enabled."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_region", "us-east-1")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_media_prefix", "media"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_results_prefix", "results"
        )

        with patch("app.services.media.s3_storage_service.boto3") as mock_boto3:
            mock_boto3.client = Mock(return_value=mock_s3_client)
            mock_s3_client.head_bucket = Mock()

            # Act
            service = S3StorageService()

            # Assert
            assert service.is_enabled() is True

    def test_init_missing_bucket_name(self, monkeypatch):
        """Test initialization raises error when bucket name is missing."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_bucket_name", "")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            S3StorageService()

        assert "bucket name" in str(exc_info.value).lower()
        assert exc_info.value.code == "CONFIG_ERROR"

    def test_init_missing_credentials(self, monkeypatch):
        """Test initialization raises error when credentials are missing."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_access_key_id", "")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", ""
        )

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            S3StorageService()

        assert "access key" in str(exc_info.value).lower()
        assert exc_info.value.code == "CONFIG_ERROR"


class TestIsEnabled:
    """Test is_enabled method."""

    def test_is_enabled_true(self, monkeypatch, mock_s3_client):
        """Test is_enabled returns True when S3 is enabled."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_region", "us-east-1")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_media_prefix", "media"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_results_prefix", "results"
        )

        with patch("app.services.media.s3_storage_service.boto3") as mock_boto3:
            mock_boto3.client = Mock(return_value=mock_s3_client)
            mock_s3_client.head_bucket = Mock()

            service = S3StorageService()

            # Act
            result = service.is_enabled()

            # Assert
            assert result is True

    def test_is_enabled_false(self, monkeypatch):
        """Test is_enabled returns False when S3 is disabled."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", False)

        service = S3StorageService()

        # Act
        result = service.is_enabled()

        # Assert
        assert result is False


class TestUploadMedia:
    """Test upload_media method."""

    def test_upload_media_success(
        self, sample_audio_file, sample_job_id, monkeypatch, mock_s3_client
    ):
        """Test successful media upload."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_region", "us-east-1")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_media_prefix", "media"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_results_prefix", "results"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_multipart_threshold_mb", 100
        )

        with patch("app.services.media.s3_storage_service.boto3") as mock_boto3:
            mock_boto3.client = Mock(return_value=mock_s3_client)
            mock_s3_client.head_bucket = Mock()
            mock_s3_client.upload_fileobj = Mock()

            service = S3StorageService()

            # Act
            s3_uri = service.upload_media(sample_audio_file, sample_job_id, "mp3")

            # Assert
            assert s3_uri.startswith("s3://")
            assert "test-bucket" in s3_uri
            mock_s3_client.upload_fileobj.assert_called_once()

    def test_upload_media_not_enabled(self, sample_audio_file, sample_job_id, monkeypatch):
        """Test upload_media raises error when S3 is not enabled."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", False)

        service = S3StorageService()

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            service.upload_media(sample_audio_file, sample_job_id, "mp3")

        assert "not enabled" in str(exc_info.value).lower()
        assert exc_info.value.code == "S3_ERROR"

    def test_upload_media_file_not_found(self, sample_job_id, monkeypatch, mock_s3_client):
        """Test upload_media raises error when file doesn't exist."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_region", "us-east-1")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_media_prefix", "media"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_results_prefix", "results"
        )

        with patch("app.services.media.s3_storage_service.boto3") as mock_boto3:
            mock_boto3.client = Mock(return_value=mock_s3_client)
            mock_s3_client.head_bucket = Mock()

            service = S3StorageService()
            non_existent_file = Path("/nonexistent/file.mp3")

            # Act & Assert
            with pytest.raises(TranscriptionError) as exc_info:
                service.upload_media(non_existent_file, sample_job_id, "mp3")

            assert "not found" in str(exc_info.value).lower()
            assert exc_info.value.code == "FILE_NOT_FOUND"


class TestDownloadMedia:
    """Test download_media method."""

    def test_download_media_success(
        self, temp_dir, sample_s3_uri, sample_job_id, monkeypatch, mock_s3_client
    ):
        """Test successful media download."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_region", "us-east-1")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_media_prefix", "media"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_results_prefix", "results"
        )

        with patch("app.services.media.s3_storage_service.boto3") as mock_boto3:
            mock_boto3.client = Mock(return_value=mock_s3_client)
            mock_s3_client.head_bucket = Mock()
            mock_s3_client.download_file = Mock()

            service = S3StorageService()
            local_path = temp_dir / "downloaded.mp3"

            # Act
            result_path = service.download_media(sample_s3_uri, local_path)

            # Assert
            assert result_path == local_path
            mock_s3_client.download_file.assert_called_once()

    def test_download_media_not_enabled(self, temp_dir, sample_s3_uri, monkeypatch):
        """Test download_media raises error when S3 is not enabled."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", False)

        service = S3StorageService()
        local_path = temp_dir / "downloaded.mp3"

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            service.download_media(sample_s3_uri, local_path)

        assert "not enabled" in str(exc_info.value).lower()
        assert exc_info.value.code == "S3_ERROR"


class TestUploadResult:
    """Test upload_result method."""

    def test_upload_result_success(self, sample_job_id, monkeypatch, mock_s3_client):
        """Test successful result upload."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_region", "us-east-1")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_media_prefix", "media"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_results_prefix", "results"
        )

        with patch("app.services.media.s3_storage_service.boto3") as mock_boto3:
            mock_boto3.client = Mock(return_value=mock_s3_client)
            mock_s3_client.head_bucket = Mock()
            mock_s3_client.put_object = Mock()

            service = S3StorageService()
            result = {"transcript": "Hello world", "segments": []}

            # Act
            s3_uri = service.upload_result(result, sample_job_id)

            # Assert
            assert s3_uri.startswith("s3://")
            assert "test-bucket" in s3_uri
            mock_s3_client.put_object.assert_called_once()

    def test_upload_result_not_enabled(self, sample_job_id, monkeypatch):
        """Test upload_result raises error when S3 is not enabled."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", False)

        service = S3StorageService()
        result = {"transcript": "Hello world"}

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            service.upload_result(result, sample_job_id)

        assert "not enabled" in str(exc_info.value).lower()
        assert exc_info.value.code == "S3_ERROR"


class TestDownloadResult:
    """Test download_result method."""

    def test_download_result_success(self, sample_job_id, monkeypatch, mock_s3_client):
        """Test successful result download."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_region", "us-east-1")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_media_prefix", "media"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_results_prefix", "results"
        )

        result_data = {"transcript": "Hello world", "segments": []}
        result_json = json.dumps(result_data)

        mock_response = Mock()
        mock_response.read = Mock(return_value=result_json.encode("utf-8"))
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)

        mock_get_object = Mock(return_value={"Body": mock_response})

        with patch("app.services.media.s3_storage_service.boto3") as mock_boto3:
            mock_boto3.client = Mock(return_value=mock_s3_client)
            mock_s3_client.head_bucket = Mock()
            mock_s3_client.get_object = mock_get_object

            service = S3StorageService()

            # Act
            result = service.download_result(sample_job_id)

            # Assert
            assert result == result_data
            mock_get_object.assert_called_once()

    def test_download_result_not_found(self, sample_job_id, monkeypatch, mock_s3_client):
        """Test download_result returns None when result is not found."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_region", "us-east-1")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_media_prefix", "media"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_results_prefix", "results"
        )

        from botocore.exceptions import ClientError

        mock_error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

        with patch("app.services.media.s3_storage_service.boto3") as mock_boto3:
            mock_boto3.client = Mock(return_value=mock_s3_client)
            mock_s3_client.head_bucket = Mock()
            mock_s3_client.get_object = Mock(side_effect=mock_error)

            service = S3StorageService()

            # Act
            result = service.download_result(sample_job_id)

            # Assert
            assert result is None

    def test_download_result_not_enabled(self, sample_job_id, monkeypatch):
        """Test download_result raises error when S3 is not enabled."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", False)

        service = S3StorageService()

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            service.download_result(sample_job_id)

        assert "not enabled" in str(exc_info.value).lower()
        assert exc_info.value.code == "S3_ERROR"


class TestCleanupJobFiles:
    """Test cleanup_job_files method."""

    def test_cleanup_job_files_success(self, sample_job_id, monkeypatch, mock_s3_client):
        """Test successful job files cleanup."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", True)
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_bucket_name", "test-bucket"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_access_key_id", "test-key"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_secret_access_key", "test-secret"
        )
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_region", "us-east-1")
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_media_prefix", "media"
        )
        monkeypatch.setattr(
            "app.services.media.s3_storage_service.settings.s3_results_prefix", "results"
        )

        with patch("app.services.media.s3_storage_service.boto3") as mock_boto3:
            mock_boto3.client = Mock(return_value=mock_s3_client)
            mock_s3_client.head_bucket = Mock()
            mock_s3_client.delete_object = Mock()

            service = S3StorageService()

            # Act
            service.cleanup_job_files(sample_job_id, "mp3")

            # Assert
            assert mock_s3_client.delete_object.call_count >= 1  # At least media or result deleted

    def test_cleanup_job_files_not_enabled(self, sample_job_id, monkeypatch):
        """Test cleanup_job_files does nothing when S3 is not enabled."""
        # Arrange
        monkeypatch.setattr("app.services.media.s3_storage_service.settings.s3_enabled", False)

        service = S3StorageService()

        # Act & Assert (should not raise)
        service.cleanup_job_files(sample_job_id, "mp3")
