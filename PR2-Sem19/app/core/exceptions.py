"""Custom exception classes for the application."""

from typing import Optional


class TranscriptionError(Exception):
    """
    Base exception for transcription-related errors.

    This is the base class for all custom transcription exceptions in the application.
    It provides a structured way to handle errors with error codes and additional details.

    Attributes:
        message (str): Human-readable error message
        code (str): Error code for programmatic error handling
        details (dict): Additional error details for debugging

    Example:
        >>> raise TranscriptionError("Failed to process video", code="PROCESSING_ERROR")
        TranscriptionError: Failed to process video
    """

    def __init__(
        self, message: str, code: str = "TRANSCRIPTION_ERROR", details: Optional[dict] = None
    ):
        """
        Initialize transcription error.

        Args:
            message (str): Human-readable error message
            code (str): Error code for programmatic error handling (default: "TRANSCRIPTION_ERROR")
            details (dict, optional): Additional error details for debugging (default: None)

        Raises:
            None: This is an exception constructor, it raises itself when used
        """
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class CaptionsNotAvailableError(TranscriptionError):
    """
    Raised when YouTube captions are not available for a video.

    This exception is raised when a video does not have captions/subtitles available,
    or when captions cannot be retrieved for any reason.

    Attributes:
        message (str): Error message (default: "Captions not available for this video")
        code (str): Error code (always "CAPTIONS_NOT_AVAILABLE")
        details (dict): Additional error details

    Example:
        >>> raise CaptionsNotAvailableError(
        ...     details={"video_id": "dQw4w9WgXcQ", "reason": "No transcripts found"}
        ... )
    """

    def __init__(
        self, message: str = "Captions not available for this video", details: Optional[dict] = None
    ):
        """
        Initialize captions not available error.

        Args:
            message (str): Error message (default: "Captions not available for this video")
            details (dict, optional): Additional error details (default: None)
        """
        super().__init__(message, code="CAPTIONS_NOT_AVAILABLE", details=details)


class CaptionsDisabledError(TranscriptionError):
    """
    Raised when YouTube captions are disabled for a video.

    This exception is raised when captions exist but are disabled by the video owner
    or YouTube's settings.

    Attributes:
        message (str): Error message (default: "Captions are disabled for this video")
        code (str): Error code (always "CAPTIONS_DISABLED")
        details (dict): Additional error details

    Example:
        >>> raise CaptionsDisabledError(details={"video_id": "dQw4w9WgXcQ"})
    """

    def __init__(
        self, message: str = "Captions are disabled for this video", details: Optional[dict] = None
    ):
        """
        Initialize captions disabled error.

        Args:
            message (str): Error message (default: "Captions are disabled for this video")
            details (dict, optional): Additional error details (default: None)
        """
        super().__init__(message, code="CAPTIONS_DISABLED", details=details)


class VideoNotFoundError(TranscriptionError):
    """
    Raised when a YouTube video is not found or unavailable.

    This exception is raised when the requested video does not exist, has been deleted,
    or is unavailable for other reasons.

    Attributes:
        message (str): Error message (default: "Video not found")
        code (str): Error code (always "VIDEO_NOT_FOUND")
        details (dict): Additional error details

    Example:
        >>> raise VideoNotFoundError(details={"video_id": "invalid_id"})
    """

    def __init__(self, message: str = "Video not found", details: Optional[dict] = None):
        """
        Initialize video not found error.

        Args:
            message (str): Error message (default: "Video not found")
            details (dict, optional): Additional error details (default: None)
        """
        super().__init__(message, code="VIDEO_NOT_FOUND", details=details)


class InvalidVideoURLError(TranscriptionError):
    """
    Raised when a YouTube URL is invalid or cannot be parsed.

    This exception is raised when the provided URL is not a valid YouTube URL,
    or when the video ID cannot be extracted from the URL.

    Attributes:
        message (str): Error message (default: "Invalid YouTube URL")
        code (str): Error code (always "INVALID_VIDEO_URL")
        details (dict): Additional error details

    Example:
        >>> raise InvalidVideoURLError(
        ...     "Invalid YouTube URL format",
        ...     details={"url": "https://invalid-url.com"}
        ... )
    """

    def __init__(self, message: str = "Invalid YouTube URL", details: Optional[dict] = None):
        """
        Initialize invalid video URL error.

        Args:
            message (str): Error message (default: "Invalid YouTube URL")
            details (dict, optional): Additional error details (default: None)
        """
        super().__init__(message, code="INVALID_VIDEO_URL", details=details)


class TranscriptionTimeoutError(TranscriptionError):
    """
    Raised when a transcription operation times out.

    This exception is raised when a transcription request takes too long to complete
    and exceeds the configured timeout limit.

    Attributes:
        message (str): Error message (default: "Transcription timeout")
        code (str): Error code (always "TRANSCRIPTION_TIMEOUT")
        details (dict): Additional error details

    Example:
        >>> raise TranscriptionTimeoutError(
        ...     details={"video_id": "dQw4w9WgXcQ", "timeout_seconds": 30}
        ... )
    """

    def __init__(self, message: str = "Transcription timeout", details: Optional[dict] = None):
        """
        Initialize transcription timeout error.

        Args:
            message (str): Error message (default: "Transcription timeout")
            details (dict, optional): Additional error details (default: None)
        """
        super().__init__(message, code="TRANSCRIPTION_TIMEOUT", details=details)


class VideoTooLongError(TranscriptionError):
    """
    Raised when a video exceeds the maximum allowed duration for processing.

    This exception is raised when a video is longer than the maximum allowed duration
    (e.g., more than 1 hour) and cannot be processed even asynchronously.

    Attributes:
        message (str): Error message (default: "Video too long")
        code (str): Error code (always "VIDEO_TOO_LONG")
        details (dict): Additional error details

    Example:
        >>> raise VideoTooLongError(
        ...     "Video exceeds maximum duration of 1 hour",
        ...     details={"video_id": "dQw4w9WgXcQ", "duration": 4000}
        ... )
    """

    def __init__(self, message: str = "Video too long", details: Optional[dict] = None):
        """
        Initialize video too long error.

        Args:
            message (str): Error message (default: "Video too long")
            details (dict, optional): Additional error details (default: None)
        """
        super().__init__(message, code="VIDEO_TOO_LONG", details=details)


class InvalidFileTypeError(TranscriptionError):
    """
    Raised when an uploaded file or remote media has an unsupported file type.

    This exception is raised when the file format is not in the list of allowed
    audio or video formats, or when the MIME type cannot be validated.

    Attributes:
        message (str): Error message (default: "Invalid file type")
        code (str): Error code (always "INVALID_FILE_TYPE")
        details (dict): Additional error details

    Example:
        >>> raise InvalidFileTypeError(
        ...     "File type 'exe' is not supported",
        ...     details={"filename": "file.exe", "allowed_formats": ["mp3", "wav", "mp4"]}
        ... )
    """

    def __init__(self, message: str = "Invalid file type", details: Optional[dict] = None):
        """
        Initialize invalid file type error.

        Args:
            message (str): Error message (default: "Invalid file type")
            details (dict, optional): Additional error details (default: None)
        """
        super().__init__(message, code="INVALID_FILE_TYPE", details=details)


class FileTooLargeError(TranscriptionError):
    """
    Raised when an uploaded file or remote media exceeds the maximum allowed size.

    This exception is raised when the file size exceeds the configured maximum
    (e.g., 500MB) to prevent DOS attacks and resource exhaustion.

    Attributes:
        message (str): Error message (default: "File too large")
        code (str): Error code (always "FILE_TOO_LARGE")
        details (dict): Additional error details

    Example:
        >>> raise FileTooLargeError(
        ...     "File size 600MB exceeds maximum of 500MB",
        ...     details={"file_size": 629145600, "max_size": 524288000}
        ... )
    """

    def __init__(self, message: str = "File too large", details: Optional[dict] = None):
        """
        Initialize file too large error.

        Args:
            message (str): Error message (default: "File too large")
            details (dict, optional): Additional error details (default: None)
        """
        super().__init__(message, code="FILE_TOO_LARGE", details=details)


class DownloadFailedError(TranscriptionError):
    """
    Raised when downloading remote media fails.

    This exception is raised when a remote media URL cannot be downloaded,
    the download times out, or the remote server returns an error.

    Attributes:
        message (str): Error message (default: "Download failed")
        code (str): Error code (always "DOWNLOAD_FAILED")
        details (dict): Additional error details

    Example:
        >>> raise DownloadFailedError(
        ...     "Failed to download media from URL",
        ...     details={"url": "https://example.com/media.mp4", "status_code": 404}
        ... )
    """

    def __init__(self, message: str = "Download failed", details: Optional[dict] = None):
        """
        Initialize download failed error.

        Args:
            message (str): Error message (default: "Download failed")
            details (dict, optional): Additional error details (default: None)
        """
        super().__init__(message, code="DOWNLOAD_FAILED", details=details)
