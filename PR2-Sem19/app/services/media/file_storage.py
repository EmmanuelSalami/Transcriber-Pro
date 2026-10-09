"""Service for handling uploaded file persistence and cleanup."""

import logging
import re
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileTooLargeError, TranscriptionError

logger = logging.getLogger(__name__)


class FileStorageService:
    """
    Service for handling uploaded file persistence and cleanup.

    This service provides methods to:
    - Save uploaded files to temporary storage
    - Generate safe file paths for uploads
    - Clean up temporary files after processing
    - Manage the upload directory structure

    Files are stored in a temporary directory (configured via settings)
    with filenames based on job IDs to ensure uniqueness and prevent conflicts.
    The service handles async file operations and provides safe cleanup
    that logs warnings but doesn't raise exceptions on failures.

    Attributes:
        temp_dir (Path): Directory where uploaded files are stored
        max_file_size_bytes (int): Maximum allowed file size in bytes

    Example:
        >>> service = FileStorageService()
        >>> file_path = await service.save_upload(upload_file, "job-123")
        >>> # Process file...
        >>> service.cleanup_upload(file_path)
    """

    def __init__(self) -> None:
        """
        Initialize the file storage service.

        Creates the temporary directory for storing uploaded files
        if it doesn't already exist. Loads configuration from settings
        including the upload directory path and maximum file size.

        Returns:
            None: This method does not return a value.

        Raises:
            TranscriptionError: If the temp directory cannot be created
                or is not accessible

        Example:
            >>> service = FileStorageService()
            >>> service.temp_dir.exists()
            True
        """
        self.temp_dir = Path(settings.temp_uploads_dir).resolve()
        self.max_file_size_bytes = settings.max_file_size_mb * 1024 * 1024

        try:
            # Check if path exists and is a file (not a directory)
            if self.temp_dir.exists() and not self.temp_dir.is_dir():
                raise TranscriptionError(
                    f"Temp uploads directory path exists but is not a directory: {self.temp_dir}",
                    code="STORAGE_ERROR",
                    details={"temp_dir": str(self.temp_dir)},
                )

            # Create directory if it doesn't exist
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # Verify directory is accessible
            if not self.temp_dir.is_dir():
                raise TranscriptionError(
                    f"Temp uploads directory path exists but is not a directory: {self.temp_dir}",
                    code="STORAGE_ERROR",
                    details={"temp_dir": str(self.temp_dir)},
                )

            logger.info(
                f"[FILE_STORAGE] FileStorageService initialized with temp directory: {self.temp_dir}"
            )

        except PermissionError as e:
            logger.error(
                f"[FILE_STORAGE] Permission denied creating temp directory: {self.temp_dir}"
            )
            raise TranscriptionError(
                f"Permission denied creating temp uploads directory: {str(e)}",
                code="STORAGE_ERROR",
                details={"temp_dir": str(self.temp_dir), "error": str(e)},
            )
        except OSError as e:
            logger.error(
                f"[FILE_STORAGE] Failed to create temp directory: {self.temp_dir} - {str(e)}"
            )
            raise TranscriptionError(
                f"Failed to create temp uploads directory: {str(e)}",
                code="STORAGE_ERROR",
                details={"temp_dir": str(self.temp_dir), "error": str(e)},
            )

    async def save_upload(
        self, file: UploadFile, job_id: str, extension: Optional[str] = None
    ) -> Path:
        """
        Save an uploaded file to temporary storage.

        Saves the uploaded file to the temporary uploads directory with a filename
        based on the job ID. The file extension is determined from the original
        filename or can be explicitly provided.

        Args:
            file (UploadFile): FastAPI UploadFile object to save
            job_id (str): Unique job identifier for the file
            extension (Optional[str]): File extension to use (e.g., "mp3", "wav").
                If not provided, extracted from the original filename.

        Returns:
            Path: Absolute path to the saved file

        Raises:
            TranscriptionError: If file cannot be saved, directory is not accessible,
                or file operation fails

        Example:
            >>> service = FileStorageService()
            >>> file_path = await service.save_upload(upload_file, "job-123", "mp3")
            >>> file_path.exists()
            True
            >>> file_path.name
            'job-123.mp3'
        """
        # Ensure temp directory exists (safety check)
        try:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            logger.error(f"[FILE_STORAGE] Cannot access temp directory: {self.temp_dir}")
            raise TranscriptionError(
                f"Cannot access temp uploads directory: {str(e)}",
                code="STORAGE_ERROR",
                details={"temp_dir": str(self.temp_dir), "error": str(e)},
            )

        # Determine file extension
        if extension is None:
            extension = self._extract_extension_from_filename(file.filename or "")
            if not extension:
                raise TranscriptionError(
                    "Cannot determine file extension from filename",
                    code="INVALID_FILE",
                    details={"filename": file.filename},
                )

        # Get safe file path
        file_path = self.get_upload_path(job_id, extension)

        # Check if file already exists (shouldn't happen with unique job IDs, but safety check)
        if file_path.exists():
            logger.warning(f"[FILE_STORAGE] File already exists, will overwrite: {file_path}")
            # Remove existing file to avoid conflicts
            try:
                file_path.unlink()
            except OSError as e:
                logger.warning(f"[FILE_STORAGE] Failed to remove existing file {file_path}: {e}")

        try:
            # Read file content and write to disk
            logger.info(
                f"[FILE_STORAGE] Saving upload: job_id={job_id}, "
                f"filename={file.filename}, extension={extension}, "
                f"size={file.size} bytes"
            )

            # Read file content
            content = await file.read()

            # Verify file size after reading (safety check)
            if len(content) > self.max_file_size_bytes:
                size_mb = len(content) / (1024 * 1024)
                max_mb = settings.max_file_size_mb
                raise FileTooLargeError(
                    f"File size {size_mb:.2f}MB exceeds maximum of {max_mb}MB",
                    details={
                        "job_id": job_id,
                        "file_size": len(content),
                        "max_size": self.max_file_size_bytes,
                    },
                )

            # Write file to disk using async I/O to avoid blocking event loop
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)

            # Verify file was written successfully
            if not file_path.exists():
                raise TranscriptionError(
                    f"File was not saved successfully: {file_path}",
                    code="STORAGE_ERROR",
                    details={"job_id": job_id, "file_path": str(file_path)},
                )

            # Verify file size matches
            actual_size = file_path.stat().st_size
            if actual_size != len(content):
                logger.warning(
                    f"[FILE_STORAGE] File size mismatch: expected {len(content)} bytes, "
                    f"got {actual_size} bytes"
                )

            logger.info(
                f"[FILE_STORAGE] Upload saved successfully: {file_path} " f"({actual_size} bytes)"
            )

            # Return absolute path for Docker compatibility
            return file_path.resolve()

        except FileTooLargeError:
            # Re-raise FileTooLargeError as-is (don't wrap in TranscriptionError)
            raise
        except OSError as e:
            error_msg = str(e)
            logger.error(f"[FILE_STORAGE] Failed to save upload for job {job_id}: {error_msg}")
            # Clean up partial file if it exists
            if file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass  # Ignore cleanup errors

            raise TranscriptionError(
                f"Failed to save uploaded file: {error_msg}",
                code="STORAGE_ERROR",
                details={"job_id": job_id, "file_path": str(file_path), "error": error_msg},
            )
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            logger.error(
                f"[FILE_STORAGE] Unexpected error saving upload for job {job_id}: "
                f"{error_type} - {error_msg}"
            )
            # Clean up partial file if it exists
            if file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass  # Ignore cleanup errors

            raise TranscriptionError(
                f"Unexpected error saving uploaded file: {error_msg}",
                code="STORAGE_ERROR",
                details={
                    "job_id": job_id,
                    "file_path": str(file_path),
                    "error": error_msg,
                    "error_type": error_type,
                },
            )

    def cleanup_upload(self, file_path: Path) -> None:
        """
        Delete an uploaded file from temporary storage.

        Safely removes the file from the filesystem. This method is designed
        to be non-critical - it logs warnings if cleanup fails but doesn't
        raise exceptions (cleanup failures are not critical for the application).

        Args:
            file_path (Path): Path to the file to delete. Can be a string or Path object.

        Returns:
            None: This method does not return a value. Cleanup failures are logged
                but do not raise exceptions.

        Example:
            >>> service = FileStorageService()
            >>> file_path = await service.save_upload(upload_file, "job-123")
            >>> service.cleanup_upload(file_path)
            >>> file_path.exists()
            False
        """
        # Convert to Path if string provided
        if isinstance(file_path, str):
            file_path = Path(file_path)

        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"[FILE_STORAGE] Cleaned up upload file: {file_path}")
            else:
                logger.debug(
                    f"[FILE_STORAGE] Upload file does not exist, skipping cleanup: {file_path}"
                )
        except PermissionError as e:
            logger.warning(
                f"[FILE_STORAGE] Permission denied cleaning up upload file {file_path}: {e}"
            )
        except OSError as e:
            # OSError includes FileNotFoundError, etc.
            logger.warning(
                f"[FILE_STORAGE] Failed to cleanup upload file {file_path}: "
                f"{type(e).__name__} - {str(e)}"
            )
        except Exception as e:
            error_type = type(e).__name__
            logger.warning(
                f"[FILE_STORAGE] Unexpected error during upload cleanup for {file_path}: "
                f"{error_type} - {str(e)}"
            )

    def get_upload_path(self, job_id: str, extension: str) -> Path:
        """
        Get the file path for an uploaded file based on job ID and extension.

        Generates a safe file path in the temporary uploads directory using
        the job ID as the base filename and the provided extension. The job ID
        is sanitized to ensure filesystem compatibility.

        Args:
            job_id (str): Unique job identifier
            extension (str): File extension (e.g., "mp3", "wav", "mp4").
                Should not include the leading dot.

        Returns:
            Path: Path object pointing to the file location

        Example:
            >>> service = FileStorageService()
            >>> path = service.get_upload_path("job-123", "mp3")
            >>> path.name
            'job-123.mp3'
            >>> path.parent == service.temp_dir
            True
        """
        # Sanitize job_id to prevent path traversal attacks
        # Remove all characters except alphanumeric, hyphens, and underscores
        safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", job_id)
        if not safe_job_id:
            raise TranscriptionError(
                "Invalid job_id: job_id must contain at least one alphanumeric character",
                code="INVALID_JOB_ID",
                details={"job_id": job_id},
            )

        # Sanitize extension (remove leading dot if present, lowercase)
        safe_extension = extension.lstrip(".").lower()

        # Construct file path
        filename = f"{safe_job_id}.{safe_extension}"
        file_path = self.temp_dir / filename

        return file_path

    def _extract_extension_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract file extension from filename.

        Private helper method to extract the file extension from a filename,
        normalizing it to lowercase and removing the leading dot.

        Args:
            filename (str): Filename to extract extension from

        Returns:
            Optional[str]: File extension (lowercase, without dot) or None if not found

        Example:
            >>> service = FileStorageService()
            >>> service._extract_extension_from_filename("audio.mp3")
            'mp3'
            >>> service._extract_extension_from_filename("VIDEO.MP4")
            'mp4'
            >>> service._extract_extension_from_filename("noextension")
            None
        """
        if not filename:
            return None

        # Get extension without the dot
        extension = Path(filename).suffix.lower().lstrip(".")
        return extension if extension else None

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to ensure filesystem compatibility.

        Private helper method that removes or replaces characters that are
        not safe for use in filenames across different operating systems.
        This ensures that job IDs with special characters don't cause
        filesystem errors.

        Args:
            filename (str): Original filename or identifier to sanitize

        Returns:
            str: Sanitized filename safe for filesystem use

        Example:
            >>> service = FileStorageService()
            >>> service._sanitize_filename("job-123")
            'job-123'
            >>> service._sanitize_filename("job/123")
            'job_123'
            >>> service._sanitize_filename("job:123")
            'job_123'
        """
        if not filename:
            return "file"

        # Replace unsafe characters with underscore
        # Unsafe characters: / \ : * ? " < > |
        unsafe_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        sanitized = filename

        for char in unsafe_chars:
            sanitized = sanitized.replace(char, "_")

        # Remove leading/trailing dots and spaces (Windows doesn't allow these)
        sanitized = sanitized.strip(". ")

        # Ensure we have a valid filename
        if not sanitized:
            sanitized = "file"

        # Limit length to prevent filesystem issues (most filesystems support 255 chars)
        if len(sanitized) > 200:
            sanitized = sanitized[:200]

        return sanitized
