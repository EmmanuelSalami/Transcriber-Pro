"""Service for validating media files and remote URLs."""

import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError

logger = logging.getLogger(__name__)


@dataclass
class MediaMetadata:
    """
    Metadata about a validated media file.

    Contains information about the media file including its type, format,
    size, and other relevant properties after validation.

    Attributes:
        media_type (str): Type of media ("audio" or "video")
        media_format (str): File format extension (e.g., "mp3", "wav", "mp4")
        file_size (int): File size in bytes
        mime_type (str): Detected MIME type (e.g., "audio/mpeg", "video/mp4")
        original_filename (Optional[str]): Original filename if available (for uploads)
        is_valid (bool): Whether the media passed all validation checks
        duration (Optional[float]): Duration in seconds; used for credit pre-check

    Example:
        >>> metadata = MediaMetadata(
        ...     media_type="audio",
        ...     media_format="mp3",
        ...     file_size=5242880,
        ...     mime_type="audio/mpeg",
        ...     original_filename="song.mp3",
        ...     is_valid=True
        ... )
    """

    media_type: str
    media_format: str
    file_size: int
    mime_type: str
    original_filename: Optional[str] = None
    is_valid: bool = True
    duration: Optional[float] = None  # Duration in seconds (for credit pre-check)


class MediaValidationService:
    """
    Service for validating media files and remote URLs.

    This service provides comprehensive validation for media files including:
    - Content-type validation with MIME type checking
    - File size validation (prevent DOS attacks)
    - Format detection and validation
    - Support for both uploaded files and remote URLs

    The service validates against configured allowed formats and size limits,
    ensuring only supported media types are processed.

    Attributes:
        max_file_size_bytes (int): Maximum allowed file size in bytes
        allowed_audio_formats (set[str]): Set of allowed audio format extensions
        allowed_video_formats (set[str]): Set of allowed video format extensions
        allowed_mime_types (dict[str, str]): Mapping of MIME types to format extensions

    Example:
        >>> service = MediaValidationService()
        >>> metadata = service.validate_upload(upload_file)
        >>> if metadata.is_valid:
        ...     process_media(metadata)
    """

    # Allowed audio formats (loaded from config in __init__)
    ALLOWED_AUDIO_FORMATS: set[str]

    # Allowed video formats (loaded from config in __init__)
    ALLOWED_VIDEO_FORMATS: set[str]

    # MIME type to format mapping
    ALLOWED_MIME_TYPES: dict[str, str] = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/wav": "wav",
        "audio/wave": "wav",
        "audio/x-wav": "wav",
        "audio/x-m4a": "m4a",
        "audio/mp4": "m4a",
        "audio/flac": "flac",
        "audio/x-flac": "flac",
        "audio/ogg": "ogg",
        "audio/vorbis": "ogg",
        "video/mp4": "mp4",
        "video/x-m4v": "mp4",
        "video/x-matroska": "mkv",
        "video/x-msvideo": "avi",
        "video/quicktime": "mov",
        "video/webm": "webm",
    }

    # Pattern-based MIME type inference rules
    # Each entry is a tuple of (patterns, format, requires_media_type)
    # patterns: list of substrings to check in MIME type
    # format: format extension to return
    # requires_media_type: optional media type requirement ("audio" or "video")
    MIME_TYPE_PATTERNS: list[tuple[list[str], str, Optional[str]]] = [
        (["mpeg", "mp3"], "mp3", None),
        (["wav", "wave"], "wav", None),
        (["matroska", "mkv"], "mkv", None),
        (["quicktime", "mov"], "mov", None),
        (["webm"], "webm", None),
        (["m4a", "mp4"], "m4a", "audio"),
        (["m4a", "mp4"], "mp4", "video"),
    ]

    def __init__(self) -> None:
        """
        Initialize the media validation service.

        Loads configuration from settings and sets up validation parameters.
        Creates necessary data structures for format and MIME type validation.

        Returns:
            None: This method does not return a value.
        """
        # Convert MB to bytes for file size validation
        self.max_file_size_bytes = settings.max_file_size_mb * 1024 * 1024

        # Load allowed formats from config
        self.ALLOWED_AUDIO_FORMATS = settings.get_allowed_audio_formats()
        self.ALLOWED_VIDEO_FORMATS = settings.get_allowed_video_formats()

        # Combine all allowed formats for quick lookup
        self.allowed_formats = self.ALLOWED_AUDIO_FORMATS | self.ALLOWED_VIDEO_FORMATS

        logger.info(
            f"[MEDIA] MediaValidationService initialized: "
            f"max_size={settings.max_file_size_mb}MB, "
            f"audio_formats={len(self.ALLOWED_AUDIO_FORMATS)}, "
            f"video_formats={len(self.ALLOWED_VIDEO_FORMATS)}"
        )

    def validate_upload(self, file: UploadFile) -> MediaMetadata:
        """
        Validate an uploaded file.

        Performs comprehensive validation on an uploaded file including:
        - File size check
        - Content-type validation
        - Format detection from filename and MIME type
        - Media type classification (audio/video)

        Args:
            file (UploadFile): FastAPI UploadFile object to validate

        Returns:
            MediaMetadata: Metadata object containing validation results and file information

        Raises:
            FileTooLargeError: If file size exceeds maximum allowed size
            InvalidFileTypeError: If file type is not supported or cannot be determined

        Example:
            >>> service = MediaValidationService()
            >>> metadata = service.validate_upload(upload_file)
            >>> print(f"Media type: {metadata.media_type}, Format: {metadata.media_format}")
        """
        logger.info(f"[MEDIA] Validating upload: filename={file.filename}, size={file.size}")

        # Validate file size
        if file.size is None:
            raise InvalidFileTypeError(
                "File size cannot be determined",
                details={"filename": file.filename},
            )

        if file.size > self.max_file_size_bytes:
            size_mb = file.size / (1024 * 1024)
            max_mb = settings.max_file_size_mb
            raise FileTooLargeError(
                f"File size {size_mb:.2f}MB exceeds maximum of {max_mb}MB",
                details={
                    "filename": file.filename,
                    "file_size": file.size,
                    "max_size": self.max_file_size_bytes,
                },
            )

        # Detect format from filename
        filename = file.filename or ""
        format_from_filename = self._extract_format_from_filename(filename)

        # Detect MIME type from content-type header
        content_type = file.content_type or ""
        mime_type, format_from_mime = self._parse_content_type(content_type)

        # Validate format consistency
        media_format = self._determine_format(format_from_filename, format_from_mime, mime_type)

        if not media_format:
            raise InvalidFileTypeError(
                f"Unsupported file type. Allowed formats: {', '.join(sorted(self.allowed_formats))}",
                details={
                    "filename": filename,
                    "content_type": content_type,
                    "detected_format": format_from_filename,
                    "allowed_formats": list(self.allowed_formats),
                },
            )

        # Determine media type (audio or video)
        media_type = self._classify_media_type(media_format)

        # Final MIME type validation
        if mime_type and mime_type not in self.ALLOWED_MIME_TYPES:
            # If we have a format but MIME type doesn't match, log warning but allow
            # (some clients send incorrect MIME types)
            logger.warning(
                f"[MEDIA] MIME type '{mime_type}' not in allowed list, "
                f"but format '{media_format}' is valid. Proceeding with format-based validation."
            )

        metadata = MediaMetadata(
            media_type=media_type,
            media_format=media_format,
            file_size=file.size,
            mime_type=mime_type or self._get_mime_type_for_format(media_format),
            original_filename=filename,
            is_valid=True,
        )

        logger.info(
            f"[MEDIA] Upload validated: type={media_type}, format={media_format}, "
            f"size={file.size} bytes"
        )

        return metadata

    def validate_remote_url(
        self, url: str, content_type: Optional[str] = None, content_length: Optional[int] = None
    ) -> MediaMetadata:
        """
        Validate a remote media URL.

        Validates remote media URLs by checking:
        - Content-type header (if provided)
        - Content-length header for size validation (if provided)
        - URL extension for format detection

        Note: This method performs basic validation based on headers.
        Full validation should be done after downloading the file.

        Args:
            url (str): Remote media URL to validate
            content_type (Optional[str]): Content-Type header value from HTTP response
            content_length (Optional[int]): Content-Length header value in bytes

        Returns:
            MediaMetadata: Metadata object containing validation results

        Raises:
            FileTooLargeError: If content-length exceeds maximum allowed size
            InvalidFileTypeError: If URL format is not supported

        Example:
            >>> service = MediaValidationService()
            >>> metadata = service.validate_remote_url(
            ...     "https://example.com/audio.mp3",
            ...     content_type="audio/mpeg",
            ...     content_length=5242880
            ... )
        """
        logger.info(f"[MEDIA] Validating remote URL: {url}")

        # Validate file size from Content-Length header if provided
        if content_length is not None:
            if content_length > self.max_file_size_bytes:
                size_mb = content_length / (1024 * 1024)
                max_mb = settings.max_file_size_mb
                raise FileTooLargeError(
                    f"Remote file size {size_mb:.2f}MB exceeds maximum of {max_mb}MB",
                    details={
                        "url": url,
                        "content_length": content_length,
                        "max_size": self.max_file_size_bytes,
                    },
                )

        # Extract format from URL
        format_from_url = self._extract_format_from_url(url)

        # Parse content-type if provided
        mime_type = None
        format_from_mime = None
        if content_type:
            mime_type, format_from_mime = self._parse_content_type(content_type)

        # Determine format
        media_format = self._determine_format(format_from_url, format_from_mime, mime_type)

        if not media_format:
            raise InvalidFileTypeError(
                f"Unsupported file type in URL. Allowed formats: {', '.join(sorted(self.allowed_formats))}",
                details={
                    "url": url,
                    "content_type": content_type,
                    "detected_format": format_from_url,
                    "allowed_formats": list(self.allowed_formats),
                },
            )

        # Classify media type
        media_type = self._classify_media_type(media_format)

        metadata = MediaMetadata(
            media_type=media_type,
            media_format=media_format,
            file_size=content_length or 0,
            mime_type=mime_type or self._get_mime_type_for_format(media_format),
            original_filename=self._extract_filename_from_url(url),
            is_valid=True,
        )

        logger.info(
            f"[MEDIA] Remote URL validated: type={media_type}, format={media_format}, "
            f"size={content_length or 'unknown'} bytes"
        )

        return metadata

    def detect_mime_type(self, file_path: Path) -> str:
        """
        Detect MIME type from a file path.

        Uses Python's mimetypes module to guess the MIME type based on file extension.
        Falls back to format-based detection if mimetypes cannot determine it.

        Args:
            file_path (Path): Path to the file

        Returns:
            str: Detected MIME type (e.g., "audio/mpeg", "video/mp4")

        Example:
            >>> service = MediaValidationService()
            >>> mime_type = service.detect_mime_type(Path("audio.mp3"))
            >>> mime_type
            'audio/mpeg'
        """
        # Try Python's mimetypes module first
        mime_type, _ = mimetypes.guess_type(str(file_path))

        if mime_type:
            # Validate that the detected MIME type is in our allowed list
            if mime_type in self.ALLOWED_MIME_TYPES:
                return mime_type

        # Fallback: determine from format
        format_ext = self._extract_format_from_filename(file_path.name)
        if format_ext:
            return self._get_mime_type_for_format(format_ext)

        # Default fallback
        return "application/octet-stream"

    def validate_file_size(self, size: int) -> bool:
        """
        Validate that a file size is within allowed limits.

        Checks if the provided file size (in bytes) is within the configured
        maximum file size limit.

        Args:
            size (int): File size in bytes

        Returns:
            bool: True if size is valid, False otherwise

        Raises:
            FileTooLargeError: If file size exceeds maximum allowed size

        Example:
            >>> service = MediaValidationService()
            >>> service.validate_file_size(5242880)  # 5MB
            True
            >>> service.validate_file_size(600 * 1024 * 1024)  # 600MB
            Traceback (most recent call last):
            ...
            FileTooLargeError: File size exceeds maximum
        """
        if size > self.max_file_size_bytes:
            size_mb = size / (1024 * 1024)
            max_mb = settings.max_file_size_mb
            raise FileTooLargeError(
                f"File size {size_mb:.2f}MB exceeds maximum of {max_mb}MB",
                details={"file_size": size, "max_size": self.max_file_size_bytes},
            )
        return True

    def _extract_format_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract file format extension from filename.

        Private helper method to extract the file extension (format) from a filename,
        normalizing it to lowercase for comparison.

        Args:
            filename (str): Filename to extract extension from

        Returns:
            Optional[str]: File format extension (lowercase) or None if not found

        Example:
            >>> service = MediaValidationService()
            >>> service._extract_format_from_filename("audio.mp3")
            'mp3'
            >>> service._extract_format_from_filename("VIDEO.MP4")
            'mp4'
        """
        if not filename:
            return None

        # Get extension without the dot
        extension = Path(filename).suffix.lower().lstrip(".")
        return extension if extension else None

    def _extract_format_from_url(self, url: str) -> Optional[str]:
        """
        Extract file format from URL.

        Private helper method to extract the file format from a URL by parsing
        the path component and extracting the extension.

        Args:
            url (str): URL to extract format from

        Returns:
            Optional[str]: File format extension (lowercase) or None if not found

        Example:
            >>> service = MediaValidationService()
            >>> service._extract_format_from_url("https://example.com/audio.mp3")
            'mp3'
        """
        try:
            # Extract path from URL
            from urllib.parse import urlparse

            parsed = urlparse(url)
            path = parsed.path

            # Extract extension from path
            return self._extract_format_from_filename(path)
        except Exception as e:
            logger.warning(f"[MEDIA] Failed to extract format from URL {url}: {e}")
            return None

    def _extract_filename_from_url(self, url: str) -> Optional[str]:
        """
        Extract filename from URL.

        Private helper method to extract the filename from a URL path.

        Args:
            url (str): URL to extract filename from

        Returns:
            Optional[str]: Filename or None if not found

        Example:
            >>> service = MediaValidationService()
            >>> service._extract_filename_from_url("https://example.com/path/audio.mp3")
            'audio.mp3'
        """
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            path = parsed.path
            return Path(path).name if path else None
        except Exception:
            return None

    def _parse_content_type(self, content_type: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse Content-Type header to extract MIME type and format.

        Private helper method that parses a Content-Type header string (which may
        include charset or other parameters) and extracts the base MIME type,
        then maps it to a format extension.

        Args:
            content_type (str): Content-Type header value (e.g., "audio/mpeg; charset=utf-8")

        Returns:
            tuple[Optional[str], Optional[str]]: Tuple of (mime_type, format) or (None, None)

        Example:
            >>> service = MediaValidationService()
            >>> service._parse_content_type("audio/mpeg")
            ('audio/mpeg', 'mp3')
            >>> service._parse_content_type("video/mp4; charset=utf-8")
            ('video/mp4', 'mp4')
        """
        if not content_type:
            return None, None

        # Remove parameters (e.g., "audio/mpeg; charset=utf-8" -> "audio/mpeg")
        mime_type = content_type.split(";")[0].strip().lower()

        # Map MIME type to format
        format_ext = self.ALLOWED_MIME_TYPES.get(mime_type)

        return mime_type, format_ext

    def _determine_format(
        self,
        format_from_filename: Optional[str],
        format_from_mime: Optional[str],
        mime_type: Optional[str],
    ) -> Optional[str]:
        """
        Determine the final format from multiple sources.

        Private helper method that combines format information from filename,
        MIME type, and content-type header to determine the most reliable format.
        Prioritizes format from filename, then MIME type mapping.

        Args:
            format_from_filename (Optional[str]): Format extracted from filename
            format_from_mime (Optional[str]): Format extracted from MIME type mapping
            mime_type (Optional[str]): Raw MIME type string

        Returns:
            Optional[str]: Determined format extension or None if cannot be determined

        Example:
            >>> service = MediaValidationService()
            >>> service._determine_format("mp3", "mp3", "audio/mpeg")
            'mp3'
            >>> service._determine_format(None, "mp4", "video/mp4")
            'mp4'
        """
        # Priority: filename > MIME type mapping > MIME type inference
        if format_from_filename and format_from_filename in self.allowed_formats:
            return format_from_filename

        if format_from_mime and format_from_mime in self.allowed_formats:
            return format_from_mime

        # If we have a MIME type but no mapping, try to infer from MIME type
        if mime_type:
            # Try to extract format from MIME type (e.g., "audio/mpeg" -> "mp3")
            # This is a fallback for MIME types not in our mapping
            inferred_format = self._infer_format_from_mime_type(mime_type)
            if inferred_format and inferred_format in self.allowed_formats:
                return inferred_format

        return None

    def _infer_format_from_mime_type(self, mime_type: str) -> Optional[str]:
        """
        Infer format extension from MIME type when not in mapping.

        Private helper method that attempts to infer a format from a MIME type
        by using Python's mimetypes module or pattern matching.

        Args:
            mime_type (str): MIME type string (e.g., "audio/mpeg")

        Returns:
            Optional[str]: Inferred format extension or None

        Example:
            >>> service = MediaValidationService()
            >>> service._infer_format_from_mime_type("audio/mpeg")
            'mp3'
        """
        # Try mimetypes module
        extensions = mimetypes.guess_all_extensions(mime_type)
        if extensions:
            # Get first extension without dot and check if it's allowed
            for ext in extensions:
                format_ext = ext.lstrip(".")
                if format_ext in self.allowed_formats:
                    return format_ext

        # Pattern matching fallback using structured patterns
        mime_lower = mime_type.lower()
        for patterns, format_ext, required_media_type in self.MIME_TYPE_PATTERNS:
            # Check if any pattern matches
            if any(pattern in mime_lower for pattern in patterns):
                # If media type requirement exists, check it
                if required_media_type is None or required_media_type in mime_lower:
                    if format_ext in self.allowed_formats:
                        return format_ext

        return None

    def _classify_media_type(self, format_ext: str) -> str:
        """
        Classify media type (audio or video) from format extension.

        Private helper method that determines whether a format is audio or video
        based on the format extension.

        Args:
            format_ext (str): Format extension (e.g., "mp3", "mp4")

        Returns:
            str: "audio" or "video"

        Raises:
            ValueError: If format is not recognized as audio or video

        Example:
            >>> service = MediaValidationService()
            >>> service._classify_media_type("mp3")
            'audio'
            >>> service._classify_media_type("mp4")
            'video'
        """
        if format_ext in self.ALLOWED_AUDIO_FORMATS:
            return "audio"
        if format_ext in self.ALLOWED_VIDEO_FORMATS:
            return "video"

        raise ValueError(f"Format '{format_ext}' is not recognized as audio or video")

    def _get_mime_type_for_format(self, format_ext: str) -> str:
        """
        Get MIME type for a format extension.

        Private helper method that returns the standard MIME type for a given
        format extension. Uses reverse lookup of ALLOWED_MIME_TYPES.

        Args:
            format_ext (str): Format extension (e.g., "mp3", "wav")

        Returns:
            str: MIME type string (e.g., "audio/mpeg", "audio/wav")

        Example:
            >>> service = MediaValidationService()
            >>> service._get_mime_type_for_format("mp3")
            'audio/mpeg'
        """
        # Reverse lookup: find MIME type that maps to this format
        for mime_type, mapped_format in self.ALLOWED_MIME_TYPES.items():
            if mapped_format == format_ext:
                return mime_type

        # Fallback: use mimetypes module
        guessed_type, _ = mimetypes.guess_type(f"file.{format_ext}")
        if guessed_type:
            return guessed_type

        # Default fallback
        if format_ext in self.ALLOWED_AUDIO_FORMATS:
            return "audio/octet-stream"
        if format_ext in self.ALLOWED_VIDEO_FORMATS:
            return "video/octet-stream"

        return "application/octet-stream"
