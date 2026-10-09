"""Unit tests for AudioDownloadService.

Tests cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary value analysis
"""

import os
from unittest.mock import Mock, patch

import pytest
import yt_dlp

from app.core.exceptions import InvalidVideoURLError, TranscriptionError
from app.services.media.audio_download_service import AudioDownloadService


class TestAudioDownloadServiceInit:
    """Test AudioDownloadService initialization."""

    def test_init_creates_temp_directory(self, temp_audio_dir, monkeypatch):
        """Test that initialization creates temp directory if it doesn't exist."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )

        # Act
        service = AudioDownloadService()

        # Assert
        assert service.temp_dir.exists()
        assert service.temp_dir.is_dir()

    def test_init_uses_existing_directory(self, temp_audio_dir, monkeypatch):
        """Test that initialization uses existing directory."""
        # Arrange
        temp_audio_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )

        # Act
        service = AudioDownloadService()

        # Assert
        assert service.temp_dir == temp_audio_dir.resolve()

    def test_init_raises_error_if_path_is_file(self, temp_dir, monkeypatch):
        """Test that initialization raises error if path exists but is a file."""
        # Arrange
        file_path = temp_dir / "not_a_dir"
        file_path.write_text("test")
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(file_path)
        )

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            AudioDownloadService()

        assert "not a directory" in str(exc_info.value).lower()
        assert exc_info.value.code == "STORAGE_ERROR"


class TestGetVideoDuration:
    """Test get_video_duration method."""

    def test_get_video_duration_success(self, temp_audio_dir, monkeypatch, sample_video_url):
        """Test successful video duration retrieval."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        mock_info = {"duration": 180.5, "id": "test123", "title": "Test Video"}

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(return_value=mock_info)
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act
            duration = service.get_video_duration(sample_video_url)

            # Assert
            assert duration == 180.5
            mock_ydl.extract_info.assert_called_once_with(sample_video_url, download=False)

    def test_get_video_duration_zero_duration(self, temp_audio_dir, monkeypatch, sample_video_url):
        """Test that zero duration raises InvalidVideoURLError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        mock_info = {"duration": 0}

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(return_value=mock_info)
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act & Assert
            with pytest.raises(InvalidVideoURLError) as exc_info:
                service.get_video_duration(sample_video_url)

            assert "duration" in str(exc_info.value).lower()

    def test_get_video_duration_none_duration(self, temp_audio_dir, monkeypatch, sample_video_url):
        """Test that None duration raises InvalidVideoURLError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        mock_info = {"duration": None}

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(return_value=mock_info)
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act & Assert
            with pytest.raises(InvalidVideoURLError) as exc_info:
                service.get_video_duration(sample_video_url)

            assert "duration" in str(exc_info.value).lower()

    def test_get_video_duration_negative_duration(
        self, temp_audio_dir, monkeypatch, sample_video_url
    ):
        """Test that negative duration raises InvalidVideoURLError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        mock_info = {"duration": -10}

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(return_value=mock_info)
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act & Assert
            with pytest.raises(InvalidVideoURLError) as exc_info:
                service.get_video_duration(sample_video_url)

            assert "duration" in str(exc_info.value).lower()

    def test_get_video_duration_download_error(self, temp_audio_dir, monkeypatch, sample_video_url):
        """Test that yt-dlp DownloadError raises InvalidVideoURLError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(
                side_effect=yt_dlp.utils.DownloadError("Video unavailable")
            )
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act & Assert
            with pytest.raises(InvalidVideoURLError) as exc_info:
                service.get_video_duration(sample_video_url)

            assert (
                "unavailable" in str(exc_info.value).lower()
                or "failed" in str(exc_info.value).lower()
            )

    def test_get_video_duration_generic_exception(
        self, temp_audio_dir, monkeypatch, sample_video_url
    ):
        """Test that generic exceptions raise InvalidVideoURLError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(side_effect=ValueError("Unexpected error"))
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act & Assert
            with pytest.raises(InvalidVideoURLError) as exc_info:
                service.get_video_duration(sample_video_url)

            assert "failed" in str(exc_info.value).lower()


class TestDownloadAudio:
    """Test download_audio method."""

    def test_download_audio_success(
        self, temp_audio_dir, monkeypatch, sample_video_url, sample_job_id
    ):
        """Test successful audio download."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        # Create expected output file
        expected_file = temp_audio_dir / f"{sample_job_id}.wav"
        expected_file.write_bytes(b"fake audio content")

        mock_info = {"id": sample_job_id, "duration": 180.0}

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(return_value=mock_info)
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act
            audio_path = service.download_audio(sample_video_url, sample_job_id)

            # Assert
            assert audio_path == str(expected_file.resolve())
            mock_ydl.extract_info.assert_called_once_with(sample_video_url, download=True)

    def test_download_audio_file_not_found_fallback(
        self, temp_audio_dir, monkeypatch, sample_video_url, sample_job_id
    ):
        """Test that download handles file not found and searches for actual file."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        # Create a different file that yt-dlp might have created
        actual_file = temp_audio_dir / "different_name.wav"
        actual_file.write_bytes(b"fake audio content")

        mock_info = {"id": sample_job_id, "duration": 180.0}

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(return_value=mock_info)
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act
            audio_path = service.download_audio(sample_video_url, sample_job_id)

            # Assert
            assert audio_path == str(actual_file.resolve())

    def test_download_audio_no_files_found(
        self, temp_audio_dir, monkeypatch, sample_video_url, sample_job_id
    ):
        """Test that download raises error when no files are found."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        mock_info = {"id": sample_job_id, "duration": 180.0}

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(return_value=mock_info)
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act & Assert
            with pytest.raises(InvalidVideoURLError) as exc_info:
                service.download_audio(sample_video_url, sample_job_id)

            assert "not found" in str(exc_info.value).lower()

    def test_download_audio_permission_error(
        self, temp_audio_dir, monkeypatch, sample_video_url, sample_job_id
    ):
        """Test that permission errors raise InvalidVideoURLError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        # Patch Path.mkdir at the class level
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")):
            # Act & Assert
            with pytest.raises(InvalidVideoURLError) as exc_info:
                service.download_audio(sample_video_url, sample_job_id)

            assert (
                "permission" in str(exc_info.value).lower()
                or "failed" in str(exc_info.value).lower()
            )

    def test_download_audio_os_error(
        self, temp_audio_dir, monkeypatch, sample_video_url, sample_job_id
    ):
        """Test that OSError raises InvalidVideoURLError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        # Patch Path.mkdir at the class level
        with patch("pathlib.Path.mkdir", side_effect=OSError("Disk full")):
            # Act & Assert
            with pytest.raises(InvalidVideoURLError) as exc_info:
                service.download_audio(sample_video_url, sample_job_id)

            assert "failed" in str(exc_info.value).lower()

    def test_download_audio_download_exception(
        self, temp_audio_dir, monkeypatch, sample_video_url, sample_job_id
    ):
        """Test that download exceptions raise InvalidVideoURLError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        with patch("app.services.media.audio_download_service.yt_dlp.YoutubeDL") as mock_ydl_class:
            mock_ydl = Mock()
            mock_ydl.extract_info = Mock(side_effect=Exception("Download failed"))
            mock_ydl.__enter__ = Mock(return_value=mock_ydl)
            mock_ydl.__exit__ = Mock(return_value=None)
            mock_ydl_class.return_value = mock_ydl

            # Act & Assert
            with pytest.raises(InvalidVideoURLError) as exc_info:
                service.download_audio(sample_video_url, sample_job_id)

            assert "failed" in str(exc_info.value).lower()


class TestCleanupAudio:
    """Test cleanup_audio method."""

    def test_cleanup_audio_success(self, temp_audio_dir, monkeypatch, sample_audio_file):
        """Test successful audio file cleanup."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()
        audio_path = str(sample_audio_file)

        # Ensure file exists
        assert os.path.exists(audio_path)

        # Act
        service.cleanup_audio(audio_path)

        # Assert
        assert not os.path.exists(audio_path)

    def test_cleanup_audio_file_not_exists(self, temp_audio_dir, monkeypatch):
        """Test cleanup when file doesn't exist (should not raise)."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()
        non_existent_path = str(temp_audio_dir / "nonexistent.wav")

        # Act & Assert (should not raise)
        service.cleanup_audio(non_existent_path)

    def test_cleanup_audio_none_path(self, temp_audio_dir, monkeypatch):
        """Test cleanup with None path (should not raise)."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()

        # Act & Assert (should not raise)
        service.cleanup_audio("")

    def test_cleanup_audio_permission_error(self, temp_audio_dir, monkeypatch, sample_audio_file):
        """Test cleanup handles permission errors gracefully."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()
        audio_path = str(sample_audio_file)

        with patch("os.remove", side_effect=PermissionError("Permission denied")):
            # Act & Assert (should not raise, just log warning)
            service.cleanup_audio(audio_path)

    def test_cleanup_audio_os_error(self, temp_audio_dir, monkeypatch, sample_audio_file):
        """Test cleanup handles OSError gracefully."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()
        audio_path = str(sample_audio_file)

        with patch("os.remove", side_effect=OSError("File in use")):
            # Act & Assert (should not raise, just log warning)
            service.cleanup_audio(audio_path)

    def test_cleanup_audio_generic_exception(self, temp_audio_dir, monkeypatch, sample_audio_file):
        """Test cleanup handles generic exceptions gracefully."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.audio_download_service.settings.temp_audio_dir", str(temp_audio_dir)
        )
        service = AudioDownloadService()
        audio_path = str(sample_audio_file)

        with patch("os.remove", side_effect=ValueError("Unexpected error")):
            # Act & Assert (should not raise, just log warning)
            service.cleanup_audio(audio_path)
