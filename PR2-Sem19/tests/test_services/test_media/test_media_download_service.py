"""Unit tests for MediaDownloadService.

Tests cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary value analysis
"""

import os
from unittest.mock import Mock, patch

import httpx
import pytest

from app.core.exceptions import DownloadFailedError, FileTooLargeError
from app.services.media.media_download_service import MediaDownloadService


class TestMediaDownloadServiceInit:
    """Test MediaDownloadService initialization."""

    def test_init_creates_temp_directory(self, temp_downloads_dir, monkeypatch):
        """Test that initialization creates temp directory if it doesn't exist."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )

        # Act
        service = MediaDownloadService()

        # Assert
        assert service.temp_dir.exists()
        assert service.temp_dir.is_dir()
        assert service.max_file_size_bytes == 500 * 1024 * 1024
        assert service.download_timeout == 30

    def test_init_custom_parameters(self, temp_downloads_dir):
        """Test initialization with custom parameters."""
        # Act
        service = MediaDownloadService(
            temp_dir=str(temp_downloads_dir),
            max_file_size_bytes=100 * 1024 * 1024,
            download_timeout=60,
        )

        # Assert
        assert service.temp_dir == temp_downloads_dir.resolve()
        assert service.max_file_size_bytes == 100 * 1024 * 1024
        assert service.download_timeout == 60

    def test_init_raises_error_if_path_is_file(self, temp_dir, monkeypatch):
        """Test that initialization raises error if path exists but is a file."""
        # Arrange
        file_path = temp_dir / "not_a_dir"
        file_path.write_text("test")
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir", str(file_path)
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )

        # Act & Assert
        with pytest.raises(DownloadFailedError) as exc_info:
            MediaDownloadService()

        assert "not a directory" in str(exc_info.value).lower()


class TestGetMediaInfo:
    """Test get_media_info method."""

    def test_get_media_info_success(
        self, temp_downloads_dir, monkeypatch, sample_media_url, mock_httpx_client
    ):
        """Test successful media info retrieval."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "audio/mpeg",
            "content-length": "1048576",  # 1MB
        }
        mock_response.text = ""

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.head = Mock(return_value=mock_response)
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            info = service.get_media_info(sample_media_url)

            # Assert
            assert info["content_type"] == "audio/mpeg"
            assert info["content_length"] == 1048576
            assert info["status_code"] == 200

    def test_get_media_info_content_type_with_charset(
        self, temp_downloads_dir, monkeypatch, sample_media_url
    ):
        """Test that content-type with charset is parsed correctly."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "audio/mpeg; charset=utf-8",
            "content-length": "1048576",
        }
        mock_response.text = ""

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.head = Mock(return_value=mock_response)
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            info = service.get_media_info(sample_media_url)

            # Assert
            assert info["content_type"] == "audio/mpeg"  # Charset should be removed

    def test_get_media_info_no_content_length(
        self, temp_downloads_dir, monkeypatch, sample_media_url
    ):
        """Test media info retrieval when content-length is not provided."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.text = ""

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.head = Mock(return_value=mock_response)
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            info = service.get_media_info(sample_media_url)

            # Assert
            assert info["content_length"] is None

    def test_get_media_info_file_too_large(self, temp_downloads_dir, monkeypatch, sample_media_url):
        """Test that file too large raises FileTooLargeError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "audio/mpeg",
            "content-length": str(600 * 1024 * 1024),  # 600MB
        }
        mock_response.text = ""

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.head = Mock(return_value=mock_response)
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(FileTooLargeError) as exc_info:
                service.get_media_info(sample_media_url)

            assert "exceeds" in str(exc_info.value).lower()

    def test_get_media_info_http_error(self, temp_downloads_dir, monkeypatch, sample_media_url):
        """Test that HTTP error status raises DownloadFailedError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.head = Mock(return_value=mock_response)
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(DownloadFailedError) as exc_info:
                service.get_media_info(sample_media_url)

            assert (
                "status" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()
            )

    def test_get_media_info_timeout(self, temp_downloads_dir, monkeypatch, sample_media_url):
        """Test that timeout raises DownloadFailedError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.head = Mock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(DownloadFailedError) as exc_info:
                service.get_media_info(sample_media_url)

            assert "timeout" in str(exc_info.value).lower()


class TestDownloadMedia:
    """Test download_media method."""

    def test_download_media_success(
        self, temp_downloads_dir, monkeypatch, sample_media_url, sample_job_id
    ):
        """Test successful media download."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.default_file_extension", "mp3"
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.download_chunk_size", 8192
        )
        service = MediaDownloadService()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "audio/mpeg",
            "content-length": "1024",
        }
        mock_response.iter_bytes = Mock(return_value=iter([b"chunk1", b"chunk2", b"chunk3"]))
        mock_response.text = ""

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_stream = Mock()
            mock_stream.__enter__ = Mock(return_value=mock_response)
            mock_stream.__exit__ = Mock(return_value=None)
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act
            file_path = service.download_media(sample_media_url, sample_job_id)

            # Assert
            assert os.path.exists(file_path)
            assert file_path.endswith(f"{sample_job_id}.mp3")

    def test_download_media_file_too_large_during_download(
        self, temp_downloads_dir, monkeypatch, sample_media_url, sample_job_id
    ):
        """Test that file too large during download raises FileTooLargeError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.default_file_extension", "mp3"
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.download_chunk_size", 8192
        )
        service = MediaDownloadService()

        # Create a large chunk that exceeds limit
        large_chunk = b"x" * (600 * 1024 * 1024)  # 600MB

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.iter_bytes = Mock(return_value=iter([large_chunk]))
        mock_response.text = ""

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_stream = Mock()
            mock_stream.__enter__ = Mock(return_value=mock_response)
            mock_stream.__exit__ = Mock(return_value=None)
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(FileTooLargeError) as exc_info:
                service.download_media(sample_media_url, sample_job_id)

            assert "exceeds" in str(exc_info.value).lower()

    def test_download_media_http_error(
        self, temp_downloads_dir, monkeypatch, sample_media_url, sample_job_id
    ):
        """Test that HTTP error raises DownloadFailedError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.default_file_extension", "mp3"
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.download_chunk_size", 8192
        )
        service = MediaDownloadService()

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_stream = Mock()
            mock_stream.__enter__ = Mock(return_value=mock_response)
            mock_stream.__exit__ = Mock(return_value=None)
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(DownloadFailedError) as exc_info:
                service.download_media(sample_media_url, sample_job_id)

            assert "failed" in str(exc_info.value).lower()

    def test_download_media_timeout(
        self, temp_downloads_dir, monkeypatch, sample_media_url, sample_job_id
    ):
        """Test that timeout raises DownloadFailedError and cleans up."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.default_file_extension", "mp3"
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.download_chunk_size", 8192
        )
        service = MediaDownloadService()

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.stream = Mock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(DownloadFailedError) as exc_info:
                service.download_media(sample_media_url, sample_job_id)

            assert "timeout" in str(exc_info.value).lower()

    def test_download_media_empty_file(
        self, temp_downloads_dir, monkeypatch, sample_media_url, sample_job_id
    ):
        """Test that empty file raises DownloadFailedError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.default_file_extension", "mp3"
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.download_chunk_size", 8192
        )
        service = MediaDownloadService()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.iter_bytes = Mock(return_value=iter([]))  # Empty
        mock_response.text = ""

        with patch("app.services.media.media_download_service.httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_stream = Mock()
            mock_stream.__enter__ = Mock(return_value=mock_response)
            mock_stream.__exit__ = Mock(return_value=None)
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(DownloadFailedError) as exc_info:
                service.download_media(sample_media_url, sample_job_id)

            assert "empty" in str(exc_info.value).lower()


class TestCleanupMedia:
    """Test cleanup_media method."""

    def test_cleanup_media_success(self, temp_downloads_dir, monkeypatch, sample_audio_file):
        """Test successful media file cleanup."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()
        file_path = str(sample_audio_file)

        # Ensure file exists
        assert os.path.exists(file_path)

        # Act
        service.cleanup_media(file_path)

        # Assert
        assert not os.path.exists(file_path)

    def test_cleanup_media_file_not_exists(self, temp_downloads_dir, monkeypatch):
        """Test cleanup when file doesn't exist (should not raise)."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()
        non_existent_path = str(temp_downloads_dir / "nonexistent.mp3")

        # Act & Assert (should not raise)
        service.cleanup_media(non_existent_path)

    def test_cleanup_media_os_error(self, temp_downloads_dir, monkeypatch, sample_audio_file):
        """Test cleanup handles OSError gracefully."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()
        file_path = str(sample_audio_file)

        with patch("os.remove", side_effect=OSError("File in use")):
            # Act & Assert (should not raise, just log warning)
            service.cleanup_media(file_path)


class TestExtractExtensionFromUrl:
    """Test _extract_extension_from_url method."""

    def test_extract_extension_success(self, temp_downloads_dir, monkeypatch):
        """Test successful extension extraction from URL."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()

        # Act
        extension = service._extract_extension_from_url("https://example.com/audio.mp3")

        # Assert
        assert extension == "mp3"

    def test_extract_extension_with_query_params(self, temp_downloads_dir, monkeypatch):
        """Test extension extraction from URL with query parameters."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()

        # Act
        extension = service._extract_extension_from_url(
            "https://example.com/audio.mp3?token=abc123"
        )

        # Assert
        assert extension == "mp3"

    def test_extract_extension_no_extension(self, temp_downloads_dir, monkeypatch):
        """Test extension extraction from URL without extension."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.temp_downloads_dir",
            str(temp_downloads_dir),
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.max_file_size_mb", 500
        )
        monkeypatch.setattr(
            "app.services.media.media_download_service.settings.media_download_timeout_seconds", 30
        )
        service = MediaDownloadService()

        # Act
        extension = service._extract_extension_from_url("https://example.com/audio")

        # Assert
        assert extension is None
