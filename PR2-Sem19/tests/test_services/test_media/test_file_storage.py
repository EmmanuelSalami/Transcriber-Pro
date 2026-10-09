"""Unit tests for FileStorageService.

Tests cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary value analysis
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import FileTooLargeError, TranscriptionError
from app.services.media.file_storage import FileStorageService


class TestFileStorageServiceInit:
    """Test FileStorageService initialization."""

    def test_init_creates_temp_directory(self, temp_uploads_dir, monkeypatch):
        """Test that initialization creates temp directory if it doesn't exist."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)

        # Act
        service = FileStorageService()

        # Assert
        assert service.temp_dir.exists()
        assert service.temp_dir.is_dir()
        assert service.max_file_size_bytes == 500 * 1024 * 1024

    def test_init_uses_existing_directory(self, temp_uploads_dir, monkeypatch):
        """Test that initialization uses existing directory."""
        # Arrange
        temp_uploads_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)

        # Act
        service = FileStorageService()

        # Assert
        assert service.temp_dir == temp_uploads_dir.resolve()

    def test_init_raises_error_if_path_is_file(self, temp_dir, monkeypatch):
        """Test that initialization raises error if path exists but is a file."""
        # Arrange
        file_path = temp_dir / "not_a_dir"
        file_path.write_text("test")
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(file_path)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            FileStorageService()

        assert "not a directory" in str(exc_info.value).lower()
        assert exc_info.value.code == "STORAGE_ERROR"

    def test_init_raises_error_on_permission_denied(self, temp_uploads_dir, monkeypatch):
        """Test that initialization raises error on permission denied."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)

        with patch.object(Path, "mkdir", side_effect=PermissionError("Permission denied")):
            # Act & Assert
            with pytest.raises(TranscriptionError) as exc_info:
                FileStorageService()

            assert "permission" in str(exc_info.value).lower()
            assert exc_info.value.code == "STORAGE_ERROR"


class TestSaveUpload:
    """Test save_upload method."""

    @pytest.mark.asyncio
    async def test_save_upload_success(
        self, temp_uploads_dir, monkeypatch, mock_upload_file_mp3, sample_job_id
    ):
        """Test successful file upload save."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act
        file_path = await service.save_upload(mock_upload_file_mp3, sample_job_id)

        # Assert
        assert file_path.exists()
        assert file_path.name == f"{sample_job_id}.mp3"
        assert file_path.is_absolute()

    @pytest.mark.asyncio
    async def test_save_upload_with_extension(
        self, temp_uploads_dir, monkeypatch, mock_upload_file_mp3, sample_job_id
    ):
        """Test save upload with explicit extension."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act
        file_path = await service.save_upload(mock_upload_file_mp3, sample_job_id, extension="wav")

        # Assert
        assert file_path.exists()
        assert file_path.name == f"{sample_job_id}.wav"

    @pytest.mark.asyncio
    async def test_save_upload_no_extension_raises_error(
        self, temp_uploads_dir, monkeypatch, mock_upload_file_no_extension, sample_job_id
    ):
        """Test that save upload raises error when extension cannot be determined."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            await service.save_upload(mock_upload_file_no_extension, sample_job_id)

        assert "extension" in str(exc_info.value).lower()
        assert exc_info.value.code == "INVALID_FILE"

    @pytest.mark.asyncio
    async def test_save_upload_file_too_large(
        self, temp_uploads_dir, monkeypatch, mock_upload_file_large, sample_job_id
    ):
        """Test that save upload raises FileTooLargeError for oversized files."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act & Assert
        with pytest.raises(FileTooLargeError) as exc_info:
            await service.save_upload(mock_upload_file_large, sample_job_id)

        assert "exceeds" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_save_upload_overwrites_existing(
        self, temp_uploads_dir, monkeypatch, mock_upload_file_mp3, sample_job_id
    ):
        """Test that save upload overwrites existing file."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Create existing file
        existing_file = service.get_upload_path(sample_job_id, "mp3")
        existing_file.write_bytes(b"old content")

        # Act
        file_path = await service.save_upload(mock_upload_file_mp3, sample_job_id)

        # Assert
        assert file_path.exists()
        assert file_path.read_bytes() != b"old content"

    @pytest.mark.asyncio
    async def test_save_upload_os_error(
        self, temp_uploads_dir, monkeypatch, mock_upload_file_mp3, sample_job_id
    ):
        """Test that OSError during save raises TranscriptionError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        with patch("aiofiles.open", side_effect=OSError("Disk full")):
            # Act & Assert
            with pytest.raises(TranscriptionError) as exc_info:
                await service.save_upload(mock_upload_file_mp3, sample_job_id)

            assert "failed" in str(exc_info.value).lower()
            assert exc_info.value.code == "STORAGE_ERROR"

    @pytest.mark.asyncio
    async def test_save_upload_file_not_written(
        self, temp_uploads_dir, monkeypatch, mock_upload_file_mp3, sample_job_id
    ):
        """Test that missing file after write raises TranscriptionError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        _ = service.get_upload_path(sample_job_id, "mp3")

        async def mock_write(*args, **kwargs):
            # Don't actually write anything
            pass

        with patch("aiofiles.open") as mock_open:
            mock_file = AsyncMock()
            mock_file.write = mock_write
            mock_file.__aenter__ = AsyncMock(return_value=mock_file)
            mock_file.__aexit__ = AsyncMock(return_value=None)
            mock_open.return_value = mock_file

            # Act & Assert
            with pytest.raises(TranscriptionError) as exc_info:
                await service.save_upload(mock_upload_file_mp3, sample_job_id)

            assert "not saved" in str(exc_info.value).lower()
            assert exc_info.value.code == "STORAGE_ERROR"


class TestCleanupUpload:
    """Test cleanup_upload method."""

    def test_cleanup_upload_success(self, temp_uploads_dir, monkeypatch, sample_audio_file):
        """Test successful file cleanup."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()
        file_path = sample_audio_file

        # Ensure file exists
        assert file_path.exists()

        # Act
        service.cleanup_upload(file_path)

        # Assert
        assert not file_path.exists()

    def test_cleanup_upload_string_path(self, temp_uploads_dir, monkeypatch, sample_audio_file):
        """Test cleanup with string path."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()
        file_path = str(sample_audio_file)

        # Act & Assert (should not raise)
        service.cleanup_upload(file_path)

    def test_cleanup_upload_file_not_exists(self, temp_uploads_dir, monkeypatch):
        """Test cleanup when file doesn't exist (should not raise)."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()
        non_existent_path = temp_uploads_dir / "nonexistent.mp3"

        # Act & Assert (should not raise)
        service.cleanup_upload(non_existent_path)

    def test_cleanup_upload_permission_error(
        self, temp_uploads_dir, monkeypatch, sample_audio_file
    ):
        """Test cleanup handles permission errors gracefully."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        with patch.object(Path, "unlink", side_effect=PermissionError("Permission denied")):
            # Act & Assert (should not raise, just log warning)
            service.cleanup_upload(sample_audio_file)

    def test_cleanup_upload_os_error(self, temp_uploads_dir, monkeypatch, sample_audio_file):
        """Test cleanup handles OSError gracefully."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        with patch.object(Path, "unlink", side_effect=OSError("File in use")):
            # Act & Assert (should not raise, just log warning)
            service.cleanup_upload(sample_audio_file)


class TestGetUploadPath:
    """Test get_upload_path method."""

    def test_get_upload_path_success(self, temp_uploads_dir, monkeypatch, sample_job_id):
        """Test successful path generation."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act
        file_path = service.get_upload_path(sample_job_id, "mp3")

        # Assert
        assert file_path.name == f"{sample_job_id}.mp3"
        assert file_path.parent == service.temp_dir

    def test_get_upload_path_sanitizes_job_id(self, temp_uploads_dir, monkeypatch):
        """Test that job_id is sanitized to prevent path traversal."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()
        unsafe_job_id = "../../etc/passwd"

        # Act
        file_path = service.get_upload_path(unsafe_job_id, "mp3")

        # Assert
        assert ".." not in str(file_path)
        assert "../etc/passwd" not in str(file_path)  # Check that path traversal is prevented
        assert file_path.name == "etcpasswd.mp3"  # Sanitized job_id should be "etcpasswd"
        assert file_path.parent == service.temp_dir

    def test_get_upload_path_sanitizes_extension(
        self, temp_uploads_dir, monkeypatch, sample_job_id
    ):
        """Test that extension is sanitized."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act
        file_path = service.get_upload_path(sample_job_id, ".MP3")

        # Assert
        assert file_path.name == f"{sample_job_id}.mp3"  # Lowercase, no leading dot

    def test_get_upload_path_invalid_job_id(self, temp_uploads_dir, monkeypatch):
        """Test that invalid job_id raises TranscriptionError."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()
        invalid_job_id = ""

        # Act & Assert
        with pytest.raises(TranscriptionError) as exc_info:
            service.get_upload_path(invalid_job_id, "mp3")

        assert "invalid" in str(exc_info.value).lower()
        assert exc_info.value.code == "INVALID_JOB_ID"

    def test_get_upload_path_special_characters(self, temp_uploads_dir, monkeypatch):
        """Test that special characters in job_id are removed."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()
        job_id_with_special = "job@#$%^&*()123"

        # Act
        file_path = service.get_upload_path(job_id_with_special, "mp3")

        # Assert
        assert "@" not in file_path.name
        assert "#" not in file_path.name
        assert file_path.name.startswith("job")


class TestExtractExtensionFromFilename:
    """Test _extract_extension_from_filename method."""

    def test_extract_extension_success(self, temp_uploads_dir, monkeypatch):
        """Test successful extension extraction."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act
        extension = service._extract_extension_from_filename("test.mp3")

        # Assert
        assert extension == "mp3"

    def test_extract_extension_uppercase(self, temp_uploads_dir, monkeypatch):
        """Test extension extraction from uppercase filename."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act
        extension = service._extract_extension_from_filename("TEST.MP3")

        # Assert
        assert extension == "mp3"

    def test_extract_extension_no_extension(self, temp_uploads_dir, monkeypatch):
        """Test extension extraction from filename without extension."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act
        extension = service._extract_extension_from_filename("test")

        # Assert
        assert extension is None

    def test_extract_extension_empty_filename(self, temp_uploads_dir, monkeypatch):
        """Test extension extraction from empty filename."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act
        extension = service._extract_extension_from_filename("")

        # Assert
        assert extension is None

    def test_extract_extension_multiple_dots(self, temp_uploads_dir, monkeypatch):
        """Test extension extraction from filename with multiple dots."""
        # Arrange
        monkeypatch.setattr(
            "app.services.media.file_storage.settings.temp_uploads_dir", str(temp_uploads_dir)
        )
        monkeypatch.setattr("app.services.media.file_storage.settings.max_file_size_mb", 500)
        service = FileStorageService()

        # Act
        extension = service._extract_extension_from_filename("test.file.tar.gz")

        # Assert
        assert extension == "gz"  # Should get the last extension
