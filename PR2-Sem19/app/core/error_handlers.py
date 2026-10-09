"""Error handlers for FastAPI application."""

import logging
from typing import Tuple

from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from youtube_transcript_api import (CouldNotRetrieveTranscript,
                                    NoTranscriptFound, TranscriptsDisabled,
                                    VideoUnavailable)

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.models.schemas import ErrorResponse
from app.utils.error_detection import is_ip_blocked_error
from app.utils.security import sanitize_error_message

logger = logging.getLogger(__name__)


def _clean_youtube_error_message(error_str: str) -> str:
    """
    Clean up duplicate error messages from YouTube API.

    Extracts the actual error message from YouTube API error strings,
    removing redundant prefixes and URLs that may be duplicated in
    the error message.

    Args:
        error_str (str): Raw error string from YouTube API

    Returns:
        str: Cleaned error message with redundant parts removed

    Example:
        >>> _clean_youtube_error_message(
        ...     "Could not retrieve a transcript for the video https://youtube.com/watch?v=abc! No transcript found"
        ... )
        'No transcript found'
    """
    if "Could not retrieve a transcript for the video" in error_str:
        parts = error_str.split("Could not retrieve a transcript for the video")
        if len(parts) > 1:
            message = parts[-1].strip()
            if message.startswith("https://"):
                message = message.split("!", 1)[-1].strip() if "!" in message else message
            return message
    return error_str


_YOUTUBE_TYPE_HANDLERS: dict[type[CouldNotRetrieveTranscript], Tuple[str, str]] = {
    TranscriptsDisabled: ("CAPTIONS_DISABLED", "Captions are disabled for this video"),
    NoTranscriptFound: ("CAPTIONS_NOT_AVAILABLE", "No transcript found for this video"),
    VideoUnavailable: ("VIDEO_UNAVAILABLE", "The video is unavailable"),
}


def _get_youtube_error_code_and_message(exc: CouldNotRetrieveTranscript) -> Tuple[str, str]:
    """
    Get error code and message for YouTube API exception using strategy pattern.

    Uses a mapping-based approach for cleaner error handling logic:
    1. Check function-based conditions first (e.g., IP blocking)
    2. Check type-based handlers from _YOUTUBE_TYPE_HANDLERS mapping
    3. Fall back to generic error handler with cleaned message

    Args:
        exc (CouldNotRetrieveTranscript): YouTube API exception instance
            (or subclasses: TranscriptsDisabled, NoTranscriptFound, VideoUnavailable)

    Returns:
        Tuple[str, str]: (error_code, error_message) tuple where:
            - error_code: Machine-readable error code (e.g., "IP_BLOCKED", "CAPTIONS_DISABLED")
            - error_message: Human-readable error message

    Example:
        >>> exc = TranscriptsDisabled("video_id", "en")
        >>> _get_youtube_error_code_and_message(exc)
        ('CAPTIONS_DISABLED', 'Captions are disabled for this video')
    """
    if is_ip_blocked_error(exc):
        return (
            "IP_BLOCKED",
            (
                "YouTube is blocking requests from this IP address. "
                "This is usually due to too many requests or requests from a cloud provider IP. "
                "Please try again later or use a different network."
            ),
        )

    exc_type = type(exc)
    if exc_type in _YOUTUBE_TYPE_HANDLERS:
        return _YOUTUBE_TYPE_HANDLERS[exc_type]

    error_str = str(exc)
    message = _clean_youtube_error_message(error_str)
    return ("YOUTUBE_API_ERROR", message)


async def transcription_error_handler(_request: Request, exc: TranscriptionError) -> JSONResponse:
    """
    Handle custom transcription errors.

    Global exception handler for TranscriptionError and its subclasses.
    Converts transcription errors into standardized JSON error responses
    with appropriate HTTP status codes. Sanitizes error messages and details
    in production mode to prevent information leakage.

    Args:
        _request (Request): FastAPI request object (unused but required by FastAPI)
        exc (TranscriptionError): TranscriptionError exception instance

    Returns:
        JSONResponse: JSON error response with status 400 (Bad Request) containing:
            - code: Error code from exception
            - message: Error message from exception (sanitized in production)
            - details: Additional error details from exception (sanitized in production)
    """
    error_message = exc.message
    error_details = exc.details.copy() if exc.details else {}

    if settings.is_production():
        error_message = sanitize_error_message(error_message)
        for key, value in error_details.items():
            if isinstance(value, str):
                error_details[key] = sanitize_error_message(value)

    logger.error(f"Transcription error: {exc.code} - {error_message}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            code=exc.code, message=error_message, details=error_details
        ).model_dump(),
    )


async def youtube_api_error_handler(
    _request: Request, exc: CouldNotRetrieveTranscript
) -> JSONResponse:
    """
    Handle YouTube Transcript API errors.

    Global exception handler for YouTube Transcript API exceptions.
    Detects specific error types (IP blocking, disabled captions, unavailable video, etc.)
    and provides user-friendly error messages with appropriate error codes.

    Uses strategy pattern for cleaner error handling logic.

    Args:
        _request (Request): FastAPI request object (unused but required by FastAPI)
        exc (CouldNotRetrieveTranscript): YouTube Transcript API exception instance
            (or subclasses: TranscriptsDisabled, NoTranscriptFound, VideoUnavailable)

    Returns:
        JSONResponse: JSON error response with status 400 (Bad Request) containing:
            - code: Specific error code (IP_BLOCKED, CAPTIONS_DISABLED, etc.)
            - message: Human-readable error message
            - details: Empty dict (details not provided for YouTube API errors)
    """
    code, message = _get_youtube_error_code_and_message(exc)
    logger.error(f"YouTube API error: {code} - {message}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(code=code, message=message, details={}).model_dump(),
    )


async def rate_limit_error_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Handle rate limit exceeded errors.

    Global exception handler for rate limiting errors. Returns appropriate
    HTTP 429 status code with Retry-After header indicating when the client
    can retry the request.

    Args:
        request (Request): FastAPI request object (used to get client host for logging)
        exc (RateLimitExceeded): RateLimitExceeded exception instance

    Returns:
        JSONResponse: JSON error response with status 429 (Too Many Requests) containing:
            - code: "RATE_LIMIT_EXCEEDED"
            - message: Rate limit error message
            - details: Dictionary with "retry_after" key indicating seconds to wait
        Also includes "Retry-After" header with retry time in seconds.
    """
    client_host = request.client.host if request.client else "unknown"
    logger.warning(f"Rate limit exceeded for {client_host}")
    retry_after = getattr(exc, "retry_after", settings.rate_limit_default_retry_after)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=ErrorResponse(
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded: {exc.detail}",
            details={"retry_after": retry_after},
        ).model_dump(),
        headers={"Retry-After": str(retry_after)},
    )


async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """
    Handle generic unhandled exceptions.

    Catch-all exception handler for any exceptions not handled by specific handlers.
    Logs the full exception traceback and returns a generic 500 error response
    to avoid exposing internal error details to clients.

    Args:
        _request (Request): FastAPI request object (unused but required by FastAPI)
        exc (Exception): Any unhandled exception instance

    Returns:
        JSONResponse: JSON error response with status 500 (Internal Server Error) containing:
            - code: "INTERNAL_SERVER_ERROR"
            - message: Generic error message ("An internal server error occurred")
            - details: Dictionary with "error_type" key containing exception class name
    """
    error_str = str(exc)
    if settings.is_production():
        error_str = sanitize_error_message(error_str)

    logger.exception(f"Unhandled exception: {type(exc).__name__} - {error_str}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            code="INTERNAL_SERVER_ERROR",
            message="An internal server error occurred",
            details={"error_type": type(exc).__name__},
        ).model_dump(),
    )


def register_error_handlers(app) -> None:
    """
    Register all error handlers with the FastAPI application.

    Registers global exception handlers for:
    - TranscriptionError and subclasses
    - YouTube Transcript API exceptions
    - Rate limiting exceptions
    - Generic unhandled exceptions

    Args:
        app (FastAPI): FastAPI application instance to register handlers with

    Returns:
        None: Function modifies the app in place

    Example:
        Called during application startup:
        ```python
        app = FastAPI()
        register_error_handlers(app)
        ```
    """
    app.add_exception_handler(TranscriptionError, transcription_error_handler)
    app.add_exception_handler(CouldNotRetrieveTranscript, youtube_api_error_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
