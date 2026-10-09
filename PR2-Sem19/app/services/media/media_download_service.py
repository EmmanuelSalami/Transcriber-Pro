"""Service for downloading remote media files from HTTP/HTTPS URLs."""

import logging
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.exceptions import DownloadFailedError, FileTooLargeError
from app.utils.url_validation import validate_remote_url

logger = logging.getLogger(__name__)


class MediaDownloadService:
    """
    Service for downloading remote media files from HTTP/HTTPS URLs.

    This service handles downloading media files (audio/video) from remote URLs including:
    - Direct media URLs (e.g., https://cdn.example.com/audio.mp3)
    - S3/R2 signed URLs
    - Any HTTP/HTTPS accessible media file

    It provides methods to:
    - Get media information (size, content-type) via HEAD request
    - Download media files with progress tracking
    - Clean up temporary downloaded files after processing

    The service downloads files to a temporary directory and validates file size
    before and during download to prevent DOS attacks.

    Attributes:
        temp_dir (Path): Directory where temporary downloaded files are stored
        max_file_size_bytes (int): Maximum allowed file size in bytes
        download_timeout (int): Timeout for download requests in seconds

    Example:
        >>> service = MediaDownloadService()
        >>> media_info = service.get_media_info("https://example.com/audio.mp3")
        >>> file_path = service.download_media("https://example.com/audio.mp3", "job-123")
        >>> service.cleanup_media(file_path)
    """

    def __init__(
        self,
        temp_dir: Optional[str] = None,
        max_file_size_bytes: Optional[int] = None,
        download_timeout: Optional[int] = None,
    ) -> None:
        """
        Initialize the media download service.

        Creates the temporary directory for storing downloaded media files
        if it doesn't already exist. Configures file size limits and timeout settings.

        Args:
            temp_dir (Optional[str]): Custom temporary directory path.
                If None, uses settings.temp_downloads_dir (default: None)
            max_file_size_bytes (Optional[int]): Maximum file size in bytes.
                If None, uses settings.max_file_size_mb converted to bytes (default: None)
            download_timeout (Optional[int]): Timeout for download requests in seconds.
                If None, uses settings.media_download_timeout_seconds (default: None)

        Returns:
            None: This method does not return a value.

        Example:
            >>> service = MediaDownloadService()
            >>> service.temp_dir.exists()
            True
        """
        self.temp_dir = Path(temp_dir or settings.temp_downloads_dir).resolve()

        if self.temp_dir.exists() and not self.temp_dir.is_dir():
            from app.core.exceptions import DownloadFailedError

            raise DownloadFailedError(
                f"Temp downloads directory path exists but is not a directory: {self.temp_dir}",
                details={"temp_dir": str(self.temp_dir)},
            )

        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.max_file_size_bytes = max_file_size_bytes or (settings.max_file_size_mb * 1024 * 1024)
        self.download_timeout = download_timeout or settings.media_download_timeout_seconds

        logger.info(
            f"[MEDIA] MediaDownloadService initialized: "
            f"temp_dir={self.temp_dir}, "
            f"max_size={self.max_file_size_bytes / (1024 * 1024):.1f}MB, "
            f"timeout={self.download_timeout}s"
        )

    def get_media_info(self, url: str) -> dict[str, Any]:
        """
        Get media file information via HEAD request without downloading.

        Performs a HEAD request to retrieve metadata about the remote media file
        including content-type, content-length, and other headers. This allows
        validation before downloading the full file.

        Args:
            url (str): Remote media URL

        Returns:
            dict: Dictionary containing media information:
                - content_type (str): MIME type from Content-Type header
                - content_length (Optional[int]): File size in bytes from Content-Length header
                - headers (dict): All response headers
                - status_code (int): HTTP status code

        Raises:
            DownloadFailedError: If HEAD request fails, URL is unreachable,
                or server returns an error status code
            TranscriptionError: If URL validation fails (SSRF protection)

        Example:
            >>> service = MediaDownloadService()
            >>> info = service.get_media_info("https://example.com/audio.mp3")
            >>> info["content_type"]
            'audio/mpeg'
            >>> info["content_length"]
            5242880
        """
        validate_remote_url(url)

        logger.info(f"[MEDIA] Getting media info for URL: {url}")

        try:
            with httpx.Client(timeout=self.download_timeout, follow_redirects=True) as client:
                response = client.head(url)

                if response.status_code >= 400:
                    raise DownloadFailedError(
                        f"HEAD request failed with status {response.status_code}",
                        details={
                            "url": url,
                            "status_code": response.status_code,
                            "response_text": response.text[:200] if response.text else None,
                        },
                    )

                content_type = response.headers.get("content-type", "")
                if ";" in content_type:
                    content_type = content_type.split(";")[0].strip()

                content_length = response.headers.get("content-length")
                content_length_int = int(content_length) if content_length else None

                if content_length_int and content_length_int > self.max_file_size_bytes:
                    size_mb = content_length_int / (1024 * 1024)
                    max_mb = self.max_file_size_bytes / (1024 * 1024)
                    raise FileTooLargeError(
                        f"Remote file size {size_mb:.2f}MB exceeds maximum of {max_mb:.2f}MB",
                        details={
                            "url": url,
                            "content_length": content_length_int,
                            "max_size": self.max_file_size_bytes,
                        },
                    )

                info = {
                    "content_type": content_type,
                    "content_length": content_length_int,
                    "headers": dict(response.headers),
                    "status_code": response.status_code,
                }

                logger.info(
                    f"[MEDIA] Media info retrieved: type={content_type}, "
                    f"size={content_length_int or 'unknown'} bytes"
                )

                return info

        except httpx.TimeoutException as e:
            error_msg = f"Timeout while getting media info: {str(e)}"
            logger.error(f"[MEDIA] {error_msg}")
            raise DownloadFailedError(
                error_msg,
                details={"url": url, "timeout": self.download_timeout, "error": str(e)},
            )
        except httpx.RequestError as e:
            error_msg = f"Request error while getting media info: {str(e)}"
            logger.error(f"[MEDIA] {error_msg}")
            raise DownloadFailedError(
                error_msg,
                details={"url": url, "error": str(e), "error_type": type(e).__name__},
            )
        except FileTooLargeError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting media info: {str(e)}"
            error_type = type(e).__name__
            logger.error(f"[MEDIA] {error_msg} ({error_type})")
            raise DownloadFailedError(
                error_msg,
                details={"url": url, "error": str(e), "error_type": error_type},
            )

    def _ensure_temp_directory(self) -> None:
        """
        Ensure temporary directory exists and is valid.

        Creates the temporary directory if it doesn't exist and validates
        that it's actually a directory.

        Raises:
            DownloadFailedError: If directory creation fails or path is invalid
        """
        try:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            if not self.temp_dir.is_dir():
                raise DownloadFailedError(
                    f"Temp directory path exists but is not a directory: {self.temp_dir}",
                    details={"temp_dir": str(self.temp_dir)},
                )
        except PermissionError as e:
            logger.error(f"[MEDIA] Permission denied creating temp directory: {self.temp_dir}")
            raise DownloadFailedError(
                f"Permission denied creating temp directory: {str(e)}",
                details={"temp_dir": str(self.temp_dir), "error": str(e)},
            )
        except OSError as e:
            logger.error(f"[MEDIA] Failed to create temp directory: {self.temp_dir} - {str(e)}")
            raise DownloadFailedError(
                f"Failed to create temp directory: {str(e)}",
                details={"temp_dir": str(self.temp_dir), "error": str(e)},
            )

    def _determine_output_path(self, url: str, job_id: str) -> Path:
        """
        Determine output file path for downloaded media.

        Extracts file extension from URL or uses default, then generates
        a safe filename using the job_id.

        Args:
            url (str): Remote media URL
            job_id (str): Job identifier used for filename generation

        Returns:
            Path: Path object for the output file
        """
        file_extension = self._extract_extension_from_url(url)
        if not file_extension:
            file_extension = settings.default_file_extension
            logger.warning(
                f"[MEDIA] Could not determine file extension from URL, using default: {file_extension}"
            )

        safe_filename = f"{job_id}.{file_extension}"
        return self.temp_dir / safe_filename

    def _validate_response_headers(self, response: httpx.Response, url: str, job_id: str) -> None:
        """
        Validate HTTP response headers before downloading.

        Checks response status code and content-length header to ensure
        the download can proceed safely.

        Args:
            response (httpx.Response): HTTP response object
            url (str): Remote media URL
            job_id (str): Job identifier

        Raises:
            DownloadFailedError: If response status indicates failure
            FileTooLargeError: If content-length exceeds maximum allowed size
        """
        if response.status_code >= 400:
            raise DownloadFailedError(
                f"Download failed with status {response.status_code}",
                details={
                    "url": url,
                    "job_id": job_id,
                    "status_code": response.status_code,
                    "response_text": response.text[:200] if hasattr(response, "text") else None,
                },
            )

        content_length = response.headers.get("content-length")
        if content_length:
            content_length_int = int(content_length)
            if content_length_int > self.max_file_size_bytes:
                size_mb = content_length_int / (1024 * 1024)
                max_mb = self.max_file_size_bytes / (1024 * 1024)
                raise FileTooLargeError(
                    f"Remote file size {size_mb:.2f}MB exceeds maximum of {max_mb:.2f}MB",
                    details={
                        "url": url,
                        "job_id": job_id,
                        "content_length": content_length_int,
                        "max_size": self.max_file_size_bytes,
                    },
                )

    def _write_file_chunks(
        self, response: httpx.Response, output_path: Path, url: str, job_id: str
    ) -> int:
        """
        Write response chunks to file with size monitoring.

        Downloads file in chunks, monitoring size to prevent DOS attacks.
        Ensures data is flushed and synced to disk.

        Args:
            response (httpx.Response): Streaming HTTP response
            output_path (Path): Path where file should be written
            url (str): Remote media URL
            job_id (str): Job identifier

        Returns:
            int: Number of bytes downloaded

        Raises:
            FileTooLargeError: If downloaded file exceeds maximum allowed size
        """
        downloaded_bytes = 0
        chunk_size = settings.download_chunk_size

        abs_output_path = output_path.resolve()

        logger.debug(f"[MEDIA] Writing file to: {abs_output_path}")

        with open(abs_output_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size):
                downloaded_bytes += len(chunk)

                if downloaded_bytes > self.max_file_size_bytes:
                    try:
                        if abs_output_path.exists():
                            os.remove(abs_output_path)
                    except OSError:
                        pass

                    size_mb = downloaded_bytes / (1024 * 1024)
                    max_mb = self.max_file_size_bytes / (1024 * 1024)
                    raise FileTooLargeError(
                        f"Downloaded file size {size_mb:.2f}MB exceeds maximum of {max_mb:.2f}MB",
                        details={
                            "url": url,
                            "job_id": job_id,
                            "downloaded_bytes": downloaded_bytes,
                            "max_size": self.max_file_size_bytes,
                        },
                    )

                f.write(chunk)

            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError as e:
                logger.warning(f"[MEDIA] Could not sync file to disk: {e}")

        if not abs_output_path.exists():
            logger.error(
                f"[MEDIA] File not found immediately after write: {abs_output_path}. "
                f"Downloaded {downloaded_bytes} bytes. "
                f"Parent exists: {abs_output_path.parent.exists()}"
            )
            raise DownloadFailedError(
                f"File not found after writing: {abs_output_path}",
                details={
                    "url": url,
                    "job_id": job_id,
                    "output_path": str(abs_output_path),
                    "downloaded_bytes": downloaded_bytes,
                },
            )

        actual_size = abs_output_path.stat().st_size
        if actual_size != downloaded_bytes:
            logger.warning(
                f"[MEDIA] File size mismatch: expected {downloaded_bytes} bytes, "
                f"got {actual_size} bytes"
            )

        logger.debug(
            f"[MEDIA] File written successfully: {abs_output_path} " f"({actual_size} bytes)"
        )

        return downloaded_bytes

    def _verify_downloaded_file(self, output_path: Path, url: str, job_id: str) -> int:
        """
        Verify downloaded file exists and is valid.

        Checks that the file exists, is not empty, and doesn't exceed
        maximum size limits. Uses absolute path to avoid path resolution issues.

        Args:
            output_path (Path): Path to downloaded file
            url (str): Remote media URL
            job_id (str): Job identifier

        Returns:
            int: File size in bytes

        Raises:
            DownloadFailedError: If file doesn't exist or is empty
            FileTooLargeError: If file exceeds maximum allowed size
        """
        abs_output_path = output_path.resolve()

        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            if abs_output_path.exists():
                break

            if attempt < max_retries - 1:
                import time

                time.sleep(retry_delay)
                logger.debug(f"[MEDIA] File not found on attempt {attempt + 1}, retrying...")

        if not abs_output_path.exists():
            logger.error(
                f"[MEDIA] File not found after download: {abs_output_path}. "
                f"Parent directory exists: {abs_output_path.parent.exists()}, "
                f"Parent is directory: {abs_output_path.parent.is_dir() if abs_output_path.parent.exists() else 'N/A'}, "
                f"Temp dir: {self.temp_dir}, "
                f"Temp dir exists: {self.temp_dir.exists()}, "
                f"Temp dir resolved: {self.temp_dir.resolve()}"
            )
            # Check if file exists with different case or similar name
            if abs_output_path.parent.exists():
                try:
                    existing_files = list(abs_output_path.parent.glob(f"{job_id}.*"))
                    if existing_files:
                        logger.error(
                            f"[MEDIA] Found similar files: {[str(f) for f in existing_files]}"
                        )
                    # Also list all files in the directory for debugging
                    all_files = list(abs_output_path.parent.glob("*"))
                    logger.error(
                        f"[MEDIA] All files in temp directory: {[str(f) for f in all_files[:10]]}"
                    )
                except Exception as e:
                    logger.error(f"[MEDIA] Error checking for similar files: {e}")

            raise DownloadFailedError(
                f"Downloaded file not found at expected path: {abs_output_path}",
                details={
                    "url": url,
                    "job_id": job_id,
                    "expected_path": str(abs_output_path),
                    "temp_dir": str(self.temp_dir),
                    "temp_dir_resolved": str(self.temp_dir.resolve()),
                    "temp_dir_exists": self.temp_dir.exists(),
                },
            )

        actual_size = abs_output_path.stat().st_size
        if actual_size == 0:
            logger.warning(f"[MEDIA] Downloaded file is empty: {abs_output_path}")
            raise DownloadFailedError(
                f"Downloaded file is empty: {abs_output_path}",
                details={
                    "url": url,
                    "job_id": job_id,
                    "file_path": str(abs_output_path),
                },
            )

        if actual_size > self.max_file_size_bytes:
            try:
                os.remove(abs_output_path)
            except OSError:
                pass

            size_mb = actual_size / (1024 * 1024)
            max_mb = self.max_file_size_bytes / (1024 * 1024)
            raise FileTooLargeError(
                f"Downloaded file size {size_mb:.2f}MB exceeds maximum of {max_mb:.2f}MB",
                details={
                    "url": url,
                    "job_id": job_id,
                    "file_size": actual_size,
                    "max_size": self.max_file_size_bytes,
                },
            )

        return actual_size

    def download_media(self, url: str, job_id: str) -> str:
        """
        Download media file from remote URL.

        Downloads the media file from the provided URL and saves it to a temporary
        directory with a filename based on the job_id. Validates file size during
        download to prevent DOS attacks.

        Args:
            url (str): Remote media URL to download
            job_id (str): Job identifier used for filename generation

        Returns:
            str: Absolute path to the downloaded media file

        Raises:
            DownloadFailedError: If download fails, file is too large,
                or file cannot be saved
            FileTooLargeError: If downloaded file exceeds maximum allowed size
            TranscriptionError: If URL validation fails (SSRF protection)

        Example:
            >>> service = MediaDownloadService()
            >>> file_path = service.download_media(
            ...     "https://example.com/audio.mp3",
            ...     "job-123"
            ... )
            >>> os.path.exists(file_path)
            True
        """
        validate_remote_url(url)

        logger.info(f"[MEDIA] Downloading media from URL: {url} (job_id: {job_id})")

        self._ensure_temp_directory()

        output_path = self._determine_output_path(url, job_id)

        try:
            abs_output_path = output_path.resolve()

            with httpx.Client(timeout=self.download_timeout, follow_redirects=True) as client:
                with client.stream("GET", url) as response:
                    self._validate_response_headers(response, url, job_id)

                    self._write_file_chunks(response, abs_output_path, url, job_id)

            actual_size = self._verify_downloaded_file(abs_output_path, url, job_id)

            file_path = str(abs_output_path)
            logger.info(
                f"[MEDIA] Media downloaded successfully: {file_path} "
                f"({actual_size / (1024 * 1024):.2f}MB)"
            )

            return file_path

        except (FileTooLargeError, DownloadFailedError):
            raise
        except httpx.TimeoutException as e:
            try:
                abs_output_path = output_path.resolve()
                if abs_output_path.exists():
                    os.remove(abs_output_path)
            except OSError:
                pass

            error_msg = f"Timeout while downloading media: {str(e)}"
            logger.error(f"[MEDIA] {error_msg}")
            raise DownloadFailedError(
                error_msg,
                details={
                    "url": url,
                    "job_id": job_id,
                    "timeout": self.download_timeout,
                    "error": str(e),
                },
            )
        except httpx.RequestError as e:
            try:
                abs_output_path = output_path.resolve()
                if abs_output_path.exists():
                    os.remove(abs_output_path)
            except OSError:
                pass

            error_msg = f"Request error while downloading media: {str(e)}"
            logger.error(f"[MEDIA] {error_msg}")
            raise DownloadFailedError(
                error_msg,
                details={
                    "url": url,
                    "job_id": job_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
        except OSError as e:
            try:
                abs_output_path = output_path.resolve()
                if abs_output_path.exists():
                    os.remove(abs_output_path)
            except OSError:
                pass

            error_msg = f"Filesystem error while downloading media: {str(e)}"
            logger.error(f"[MEDIA] {error_msg}")
            raise DownloadFailedError(
                error_msg,
                details={
                    "url": url,
                    "job_id": job_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
        except Exception as e:
            try:
                abs_output_path = output_path.resolve()
                if abs_output_path.exists():
                    os.remove(abs_output_path)
            except OSError:
                pass

            error_msg = f"Unexpected error downloading media: {str(e)}"
            error_type = type(e).__name__
            logger.error(f"[MEDIA] {error_msg} ({error_type})")
            raise DownloadFailedError(
                error_msg,
                details={
                    "url": url,
                    "job_id": job_id,
                    "error": str(e),
                    "error_type": error_type,
                },
            )

    def cleanup_media(self, file_path: str) -> None:
        """
        Delete temporary downloaded media file.

        Safely removes the media file from the filesystem.
        Logs warnings if cleanup fails but doesn't raise exceptions
        (cleanup failures are not critical).

        Args:
            file_path (str): Path to the media file to delete

        Returns:
            None: This method does not return a value. Cleanup failures are logged
                but do not raise exceptions.

        Example:
            >>> service = MediaDownloadService()
            >>> file_path = service.download_media(url, "job-123")
            >>> service.cleanup_media(file_path)
            >>> os.path.exists(file_path)
            False
        """
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"[MEDIA] Cleaned up media file: {file_path}")
            else:
                logger.debug(f"[MEDIA] Media file does not exist, skipping cleanup: {file_path}")
        except OSError as e:
            logger.warning(
                f"[MEDIA] Failed to cleanup media file {file_path}: {type(e).__name__} - {str(e)}"
            )
        except Exception as e:
            error_type = type(e).__name__
            logger.warning(
                f"[MEDIA] Unexpected error during media cleanup for {file_path}: "
                f"{error_type} - {str(e)}"
            )

    def _extract_extension_from_url(self, url: str) -> Optional[str]:
        """
        Extract file extension from URL.

        Parses the URL to extract the file extension from the path component.
        Handles URLs with query parameters and fragments.

        Args:
            url (str): Remote media URL

        Returns:
            Optional[str]: File extension without leading dot (e.g., "mp3", "mp4"),
                or None if extension cannot be determined

        Example:
            >>> service = MediaDownloadService()
            >>> service._extract_extension_from_url("https://example.com/audio.mp3")
            'mp3'
            >>> service._extract_extension_from_url("https://example.com/video.mp4?token=abc")
            'mp4'
        """
        try:
            parsed = urlparse(url)
            path = parsed.path

            if "." in path:
                extension = path.rsplit(".", 1)[-1].lower()
                if "?" in extension:
                    extension = extension.split("?")[0]
                if "#" in extension:
                    extension = extension.split("#")[0]

                if (
                    extension
                    and extension.isalnum()
                    and len(extension) <= settings.max_file_extension_length
                ):
                    return extension

            return None
        except Exception as e:
            logger.warning(f"[MEDIA] Failed to extract extension from URL {url}: {str(e)}")
            return None
