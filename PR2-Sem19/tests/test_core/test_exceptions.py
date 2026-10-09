"""Unit tests for custom exception classes.

This module tests:
- TranscriptionError base class
- All exception subclasses
- Exception initialization
- Error code and message handling
- Details dictionary handling
- Edge cases and boundary conditions
"""

import pytest

from app.core.exceptions import (CaptionsDisabledError,
                                 CaptionsNotAvailableError,
                                 DownloadFailedError, FileTooLargeError,
                                 InvalidFileTypeError, InvalidVideoURLError,
                                 TranscriptionError, TranscriptionTimeoutError,
                                 VideoNotFoundError, VideoTooLongError)


class TestTranscriptionError:
    """Test suite for TranscriptionError base class."""

    def test_transcription_error_basic_initialization(self):
        """Test: Basic exception initialization with message.

        Verifies that TranscriptionError can be initialized with
        just a message.
        """
        error = TranscriptionError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.code == "TRANSCRIPTION_ERROR"
        assert error.details == {}

    def test_transcription_error_with_code(self):
        """Test: Exception initialization with custom code.

        Verifies that a custom error code can be provided.
        """
        error = TranscriptionError("Test error", code="CUSTOM_ERROR")
        assert error.message == "Test error"
        assert error.code == "CUSTOM_ERROR"
        assert error.details == {}

    def test_transcription_error_with_details(self):
        """Test: Exception initialization with details dictionary.

        Verifies that additional details can be provided.
        """
        details = {"video_id": "abc123", "reason": "test"}
        error = TranscriptionError("Test error", details=details)
        assert error.message == "Test error"
        assert error.details == details

    def test_transcription_error_with_all_parameters(self):
        """Test: Exception initialization with all parameters.

        Verifies that message, code, and details can all be provided.
        """
        details = {"key": "value"}
        error = TranscriptionError("Test error", code="CUSTOM_CODE", details=details)
        assert error.message == "Test error"
        assert error.code == "CUSTOM_CODE"
        assert error.details == details

    def test_transcription_error_details_none_defaults_to_empty_dict(self):
        """Test: None details defaults to empty dictionary.

        Edge case: When details is None, it should default to {}.
        """
        error = TranscriptionError("Test error", details=None)
        assert error.details == {}

    def test_transcription_error_inherits_from_exception(self):
        """Test: TranscriptionError inherits from Exception.

        Verifies that TranscriptionError is a proper Exception subclass.
        """
        error = TranscriptionError("Test error")
        assert isinstance(error, Exception)
        assert isinstance(error, TranscriptionError)

    def test_transcription_error_can_be_raised(self):
        """Test: TranscriptionError can be raised and caught.

        Verifies that the exception can be raised and caught properly.
        """
        with pytest.raises(TranscriptionError) as exc_info:
            raise TranscriptionError("Test error")

        assert exc_info.value.message == "Test error"
        assert exc_info.value.code == "TRANSCRIPTION_ERROR"


class TestCaptionsNotAvailableError:
    """Test suite for CaptionsNotAvailableError."""

    def test_captions_not_available_error_default_message(self):
        """Test: Default message when none provided.

        Verifies that the default message is used when not specified.
        """
        error = CaptionsNotAvailableError()
        assert error.message == "Captions not available for this video"
        assert error.code == "CAPTIONS_NOT_AVAILABLE"
        assert error.details == {}

    def test_captions_not_available_error_custom_message(self):
        """Test: Custom message can be provided.

        Verifies that a custom message can override the default.
        """
        error = CaptionsNotAvailableError("Custom message")
        assert error.message == "Custom message"
        assert error.code == "CAPTIONS_NOT_AVAILABLE"

    def test_captions_not_available_error_with_details(self):
        """Test: Details can be provided.

        Verifies that additional details can be included.
        """
        details = {"video_id": "dQw4w9WgXcQ", "reason": "No transcripts found"}
        error = CaptionsNotAvailableError(details=details)
        assert error.details == details
        assert error.code == "CAPTIONS_NOT_AVAILABLE"

    def test_captions_not_available_error_inherits_from_transcription_error(self):
        """Test: CaptionsNotAvailableError inherits from TranscriptionError.

        Verifies proper inheritance hierarchy.
        """
        error = CaptionsNotAvailableError()
        assert isinstance(error, TranscriptionError)
        assert isinstance(error, CaptionsNotAvailableError)


class TestCaptionsDisabledError:
    """Test suite for CaptionsDisabledError."""

    def test_captions_disabled_error_default_message(self):
        """Test: Default message when none provided."""
        error = CaptionsDisabledError()
        assert error.message == "Captions are disabled for this video"
        assert error.code == "CAPTIONS_DISABLED"

    def test_captions_disabled_error_custom_message(self):
        """Test: Custom message can be provided."""
        error = CaptionsDisabledError("Custom disabled message")
        assert error.message == "Custom disabled message"
        assert error.code == "CAPTIONS_DISABLED"

    def test_captions_disabled_error_with_details(self):
        """Test: Details can be provided."""
        details = {"video_id": "dQw4w9WgXcQ"}
        error = CaptionsDisabledError(details=details)
        assert error.details == details


class TestVideoNotFoundError:
    """Test suite for VideoNotFoundError."""

    def test_video_not_found_error_default_message(self):
        """Test: Default message when none provided."""
        error = VideoNotFoundError()
        assert error.message == "Video not found"
        assert error.code == "VIDEO_NOT_FOUND"

    def test_video_not_found_error_custom_message(self):
        """Test: Custom message can be provided."""
        error = VideoNotFoundError("Video does not exist")
        assert error.message == "Video does not exist"
        assert error.code == "VIDEO_NOT_FOUND"

    def test_video_not_found_error_with_details(self):
        """Test: Details can be provided."""
        details = {"video_id": "invalid_id"}
        error = VideoNotFoundError(details=details)
        assert error.details == details


class TestInvalidVideoURLError:
    """Test suite for InvalidVideoURLError."""

    def test_invalid_video_url_error_default_message(self):
        """Test: Default message when none provided."""
        error = InvalidVideoURLError()
        assert error.message == "Invalid YouTube URL"
        assert error.code == "INVALID_VIDEO_URL"

    def test_invalid_video_url_error_custom_message(self):
        """Test: Custom message can be provided."""
        error = InvalidVideoURLError("URL format is invalid")
        assert error.message == "URL format is invalid"
        assert error.code == "INVALID_VIDEO_URL"

    def test_invalid_video_url_error_with_details(self):
        """Test: Details can be provided."""
        details = {"url": "https://invalid-url.com"}
        error = InvalidVideoURLError(details=details)
        assert error.details == details


class TestTranscriptionTimeoutError:
    """Test suite for TranscriptionTimeoutError."""

    def test_transcription_timeout_error_default_message(self):
        """Test: Default message when none provided."""
        error = TranscriptionTimeoutError()
        assert error.message == "Transcription timeout"
        assert error.code == "TRANSCRIPTION_TIMEOUT"

    def test_transcription_timeout_error_custom_message(self):
        """Test: Custom message can be provided."""
        error = TranscriptionTimeoutError("Operation timed out after 30s")
        assert error.message == "Operation timed out after 30s"
        assert error.code == "TRANSCRIPTION_TIMEOUT"

    def test_transcription_timeout_error_with_details(self):
        """Test: Details can be provided."""
        details = {"video_id": "dQw4w9WgXcQ", "timeout_seconds": 30}
        error = TranscriptionTimeoutError(details=details)
        assert error.details == details


class TestVideoTooLongError:
    """Test suite for VideoTooLongError."""

    def test_video_too_long_error_default_message(self):
        """Test: Default message when none provided."""
        error = VideoTooLongError()
        assert error.message == "Video too long"
        assert error.code == "VIDEO_TOO_LONG"

    def test_video_too_long_error_custom_message(self):
        """Test: Custom message can be provided."""
        error = VideoTooLongError("Video exceeds maximum duration of 1 hour")
        assert error.message == "Video exceeds maximum duration of 1 hour"
        assert error.code == "VIDEO_TOO_LONG"

    def test_video_too_long_error_with_details(self):
        """Test: Details can be provided."""
        details = {"video_id": "dQw4w9WgXcQ", "duration": 4000}
        error = VideoTooLongError(details=details)
        assert error.details == details


class TestInvalidFileTypeError:
    """Test suite for InvalidFileTypeError."""

    def test_invalid_file_type_error_default_message(self):
        """Test: Default message when none provided."""
        error = InvalidFileTypeError()
        assert error.message == "Invalid file type"
        assert error.code == "INVALID_FILE_TYPE"

    def test_invalid_file_type_error_custom_message(self):
        """Test: Custom message can be provided."""
        error = InvalidFileTypeError("File type 'exe' is not supported")
        assert error.message == "File type 'exe' is not supported"
        assert error.code == "INVALID_FILE_TYPE"

    def test_invalid_file_type_error_with_details(self):
        """Test: Details can be provided."""
        details = {"filename": "file.exe", "allowed_formats": ["mp3", "wav", "mp4"]}
        error = InvalidFileTypeError(details=details)
        assert error.details == details


class TestFileTooLargeError:
    """Test suite for FileTooLargeError."""

    def test_file_too_large_error_default_message(self):
        """Test: Default message when none provided."""
        error = FileTooLargeError()
        assert error.message == "File too large"
        assert error.code == "FILE_TOO_LARGE"

    def test_file_too_large_error_custom_message(self):
        """Test: Custom message can be provided."""
        error = FileTooLargeError("File size 600MB exceeds maximum of 500MB")
        assert error.message == "File size 600MB exceeds maximum of 500MB"
        assert error.code == "FILE_TOO_LARGE"

    def test_file_too_large_error_with_details(self):
        """Test: Details can be provided."""
        details = {"file_size": 629145600, "max_size": 524288000}
        error = FileTooLargeError(details=details)
        assert error.details == details


class TestDownloadFailedError:
    """Test suite for DownloadFailedError."""

    def test_download_failed_error_default_message(self):
        """Test: Default message when none provided."""
        error = DownloadFailedError()
        assert error.message == "Download failed"
        assert error.code == "DOWNLOAD_FAILED"

    def test_download_failed_error_custom_message(self):
        """Test: Custom message can be provided."""
        error = DownloadFailedError("Failed to download media from URL")
        assert error.message == "Failed to download media from URL"
        assert error.code == "DOWNLOAD_FAILED"

    def test_download_failed_error_with_details(self):
        """Test: Details can be provided."""
        details = {"url": "https://example.com/media.mp4", "status_code": 404}
        error = DownloadFailedError(details=details)
        assert error.details == details


class TestExceptionEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_exception_with_empty_message(self):
        """Test: Exception with empty message string.

        Edge case: Empty string message should be accepted.
        """
        error = TranscriptionError("")
        assert error.message == ""
        assert str(error) == ""

    def test_exception_with_very_long_message(self):
        """Test: Exception with very long message.

        Boundary case: Very long message should be accepted.
        """
        long_message = "A" * 10000
        error = TranscriptionError(long_message)
        assert error.message == long_message
        assert len(error.message) == 10000

    def test_exception_with_unicode_message(self):
        """Test: Exception with unicode characters in message.

        Edge case: Unicode characters should be preserved.
        """
        unicode_message = "错误消息: 测试"
        error = TranscriptionError(unicode_message)
        assert error.message == unicode_message

    def test_exception_with_empty_details(self):
        """Test: Exception with empty details dictionary.

        Edge case: Empty dict should be accepted.
        """
        error = TranscriptionError("Test", details={})
        assert error.details == {}

    def test_exception_with_large_details(self):
        """Test: Exception with large details dictionary.

        Boundary case: Large details dict should be accepted.
        """
        large_details = {f"key_{i}": f"value_{i}" for i in range(1000)}
        error = TranscriptionError("Test", details=large_details)
        assert len(error.details) == 1000

    def test_exception_with_nested_details(self):
        """Test: Exception with nested structures in details.

        Edge case: Nested dicts and lists in details should work.
        """
        nested_details = {"outer": {"inner": ["list", "of", "items"], "number": 42}}
        error = TranscriptionError("Test", details=nested_details)
        assert error.details == nested_details
        assert error.details["outer"]["inner"] == ["list", "of", "items"]

    def test_exception_details_are_assigned(self):
        """Test: Details dictionary is assigned to exception.

        Note: The current implementation assigns the dict directly,
        so modifications to the original will affect the exception.
        This test verifies the actual behavior.
        """
        original_details = {"key": "value"}
        error = TranscriptionError("Test", details=original_details)
        original_details["key"] = "modified"
        # Current implementation assigns directly, so it will be modified
        assert error.details["key"] == "modified"

    def test_all_exception_codes_are_unique(self):
        """Test: All exception classes have unique error codes.

        Verifies that no two exception classes share the same code.
        """
        exception_classes = [
            CaptionsNotAvailableError,
            CaptionsDisabledError,
            VideoNotFoundError,
            InvalidVideoURLError,
            TranscriptionTimeoutError,
            VideoTooLongError,
            InvalidFileTypeError,
            FileTooLargeError,
            DownloadFailedError,
        ]

        codes = []
        for exc_class in exception_classes:
            error = exc_class()
            assert error.code not in codes, f"Duplicate code: {error.code}"
            codes.append(error.code)
