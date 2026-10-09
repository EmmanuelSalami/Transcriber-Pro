"""Unit tests for MediaValidationService.

Tests cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary value analysis
"""

from unittest.mock import Mock, patch

import pytest

from app.core.config import Settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError
from app.services.media.media_validation import (MediaMetadata,
                                                 MediaValidationService)


class TestMediaValidationServiceInit:
    """Test MediaValidationService initialization."""

    def test_init_loads_configuration(self, monkeypatch):
        """Test that initialization loads configuration correctly."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            # Act
            service = MediaValidationService()

            # Assert
            assert service.max_file_size_bytes == 500 * 1024 * 1024
            assert "mp3" in service.ALLOWED_AUDIO_FORMATS
            assert "mp4" in service.ALLOWED_VIDEO_FORMATS


class TestValidateUpload:
    """Test validate_upload method."""

    def test_validate_upload_success_mp3(self, mock_upload_file_mp3, monkeypatch):
        """Test successful validation of MP3 upload."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

            # Act
            metadata = service.validate_upload(mock_upload_file_mp3)

            # Assert
            assert isinstance(metadata, MediaMetadata)
            assert metadata.media_type == "audio"
            assert metadata.media_format == "mp3"
            assert metadata.file_size == 1024 * 1024
            assert metadata.is_valid is True

    def test_validate_upload_success_wav(self, mock_upload_file_wav, monkeypatch):
        """Test successful validation of WAV upload."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        metadata = service.validate_upload(mock_upload_file_wav)

        # Assert
        assert metadata.media_type == "audio"
        assert metadata.media_format == "wav"

    def test_validate_upload_success_mp4(self, mock_upload_file_mp4, monkeypatch):
        """Test successful validation of MP4 upload."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        metadata = service.validate_upload(mock_upload_file_mp4)

        # Assert
        assert metadata.media_type == "video"
        assert metadata.media_format == "mp4"

    def test_validate_upload_file_too_large(self, mock_upload_file_large, monkeypatch):
        """Test that oversized file raises FileTooLargeError."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act & Assert
        with pytest.raises(FileTooLargeError) as exc_info:
            service.validate_upload(mock_upload_file_large)

        assert "exceeds" in str(exc_info.value).lower()

    def test_validate_upload_no_size(self, monkeypatch):
        """Test that file with None size raises InvalidFileTypeError."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        mock_file = Mock()
        mock_file.filename = "test.mp3"
        mock_file.content_type = "audio/mpeg"
        mock_file.size = None

        # Act & Assert
        with pytest.raises(InvalidFileTypeError) as exc_info:
            service.validate_upload(mock_file)

        assert "size" in str(exc_info.value).lower()

    def test_validate_upload_invalid_file_type(self, mock_upload_file_invalid_type, monkeypatch):
        """Test that invalid file type raises InvalidFileTypeError."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act & Assert
        with pytest.raises(InvalidFileTypeError) as exc_info:
            service.validate_upload(mock_upload_file_invalid_type)

        assert (
            "unsupported" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
        )

    def test_validate_upload_no_extension_but_valid_mime(self, monkeypatch):
        """Test validation when filename has no extension but MIME type is valid."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        mock_file = Mock()
        mock_file.filename = "test_file"
        mock_file.content_type = "audio/mpeg"
        mock_file.size = 1024 * 1024

        # Act
        metadata = service.validate_upload(mock_file)

        # Assert
        assert metadata.media_format == "mp3"  # Should infer from MIME type

    def test_validate_upload_boundary_size_exact_limit(self, monkeypatch):
        """Test validation with file size exactly at the limit."""
        # Arrange
        max_size_mb = 500
        max_size_bytes = max_size_mb * 1024 * 1024
        monkeypatch.setattr(
            "app.services.media.media_validation.settings.max_file_size_mb", max_size_mb
        )
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        mock_file = Mock()
        mock_file.filename = "test.mp3"
        mock_file.content_type = "audio/mpeg"
        mock_file.size = max_size_bytes

        # Act
        metadata = service.validate_upload(mock_file)

        # Assert
        assert metadata.is_valid is True

    def test_validate_upload_boundary_size_one_byte_over(self, monkeypatch):
        """Test validation with file size one byte over the limit."""
        # Arrange
        max_size_mb = 500
        max_size_bytes = max_size_mb * 1024 * 1024
        monkeypatch.setattr(
            "app.services.media.media_validation.settings.max_file_size_mb", max_size_mb
        )
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        mock_file = Mock()
        mock_file.filename = "test.mp3"
        mock_file.content_type = "audio/mpeg"
        mock_file.size = max_size_bytes + 1

        # Act & Assert
        with pytest.raises(FileTooLargeError):
            service.validate_upload(mock_file)


class TestValidateRemoteUrl:
    """Test validate_remote_url method."""

    def test_validate_remote_url_success(self, sample_media_url, monkeypatch):
        """Test successful remote URL validation."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        metadata = service.validate_remote_url(
            sample_media_url, content_type="audio/mpeg", content_length=1024 * 1024
        )

        # Assert
        assert isinstance(metadata, MediaMetadata)
        assert metadata.media_type == "audio"
        assert metadata.media_format == "mp3"
        assert metadata.is_valid is True

    def test_validate_remote_url_file_too_large(self, sample_media_url, monkeypatch):
        """Test that oversized remote file raises FileTooLargeError."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act & Assert
        with pytest.raises(FileTooLargeError) as exc_info:
            service.validate_remote_url(
                sample_media_url, content_type="audio/mpeg", content_length=600 * 1024 * 1024
            )

        assert "exceeds" in str(exc_info.value).lower()

    def test_validate_remote_url_no_content_length(self, sample_media_url, monkeypatch):
        """Test remote URL validation without content-length."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        metadata = service.validate_remote_url(
            sample_media_url, content_type="audio/mpeg", content_length=None
        )

        # Assert
        assert metadata.file_size == 0
        assert metadata.is_valid is True

    def test_validate_remote_url_invalid_format(self, monkeypatch):
        """Test that invalid format in URL raises InvalidFileTypeError."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        invalid_url = "https://example.com/file.exe"

        # Act & Assert
        with pytest.raises(InvalidFileTypeError) as exc_info:
            service.validate_remote_url(invalid_url)

        assert (
            "unsupported" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
        )

    def test_validate_remote_url_format_from_content_type(self, monkeypatch):
        """Test that format is inferred from content-type when URL has no extension."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        url_without_extension = "https://example.com/audio"

        # Act
        metadata = service.validate_remote_url(
            url_without_extension, content_type="audio/mpeg", content_length=1024 * 1024
        )

        # Assert
        assert metadata.media_format == "mp3"  # Should infer from content-type


class TestValidateFileSize:
    """Test validate_file_size method."""

    def test_validate_file_size_success(self, monkeypatch):
        """Test successful file size validation."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        result = service.validate_file_size(100 * 1024 * 1024)  # 100MB

        # Assert
        assert result is True

    def test_validate_file_size_too_large(self, monkeypatch):
        """Test that oversized file raises FileTooLargeError."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act & Assert
        with pytest.raises(FileTooLargeError) as exc_info:
            service.validate_file_size(600 * 1024 * 1024)  # 600MB

        assert "exceeds" in str(exc_info.value).lower()

    def test_validate_file_size_boundary_exact_limit(self, monkeypatch):
        """Test file size validation at exact limit."""
        # Arrange
        max_size_mb = 500
        max_size_bytes = max_size_mb * 1024 * 1024
        monkeypatch.setattr(
            "app.services.media.media_validation.settings.max_file_size_mb", max_size_mb
        )
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        result = service.validate_file_size(max_size_bytes)

        # Assert
        assert result is True

    def test_validate_file_size_boundary_one_byte_over(self, monkeypatch):
        """Test file size validation one byte over limit."""
        # Arrange
        max_size_mb = 500
        max_size_bytes = max_size_mb * 1024 * 1024
        monkeypatch.setattr(
            "app.services.media.media_validation.settings.max_file_size_mb", max_size_mb
        )
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act & Assert
        with pytest.raises(FileTooLargeError):
            service.validate_file_size(max_size_bytes + 1)


class TestDetectMimeType:
    """Test detect_mime_type method."""

    def test_detect_mime_type_from_extension(self, monkeypatch):
        """Test MIME type detection from file extension."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        from pathlib import Path

        # Act
        mime_type = service.detect_mime_type(Path("test.mp3"))

        # Assert
        assert mime_type == "audio/mpeg"

    def test_detect_mime_type_fallback(self, monkeypatch):
        """Test MIME type detection fallback."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        from pathlib import Path

        # Act
        mime_type = service.detect_mime_type(Path("test.unknown"))

        # Assert
        assert mime_type in ["application/octet-stream", "audio/octet-stream", "video/octet-stream"]


class TestHelperMethods:
    """Test private helper methods."""

    def test_extract_format_from_filename(self, monkeypatch):
        """Test format extraction from filename."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        format_ext = service._extract_format_from_filename("test.mp3")

        # Assert
        assert format_ext == "mp3"

    def test_extract_format_from_url(self, monkeypatch):
        """Test format extraction from URL."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        format_ext = service._extract_format_from_url("https://example.com/audio.mp3")

        # Assert
        assert format_ext == "mp3"

    def test_classify_media_type_audio(self, monkeypatch):
        """Test media type classification for audio."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        media_type = service._classify_media_type("mp3")

        # Assert
        assert media_type == "audio"

    def test_classify_media_type_video(self, monkeypatch):
        """Test media type classification for video."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act
        media_type = service._classify_media_type("mp4")

        # Assert
        assert media_type == "video"

    def test_classify_media_type_invalid(self, monkeypatch):
        """Test media type classification raises ValueError for invalid format."""
        # Arrange
        monkeypatch.setattr("app.services.media.media_validation.settings.max_file_size_mb", 500)
        with (
            patch.object(Settings, "get_allowed_audio_formats", return_value={"mp3", "wav", "m4a"}),
            patch.object(Settings, "get_allowed_video_formats", return_value={"mp4", "mkv"}),
        ):
            service = MediaValidationService()

        # Act & Assert
        with pytest.raises(ValueError):
            service._classify_media_type("invalid")
