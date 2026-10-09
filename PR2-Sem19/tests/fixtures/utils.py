"""Fixtures for testing utility functions."""

from unittest.mock import Mock, patch

import pytest

from app.models.schemas import TranscriptSegment


@pytest.fixture
def sample_urls():
    """Sample URLs for testing URL validation."""
    return {
        "valid_https": "https://example.com/file.mp3",
        "valid_http": "http://example.com/file.mp3",
        "valid_with_path": "https://subdomain.example.com/path/to/file.wav?param=value",
        "invalid_no_scheme": "example.com/file.mp3",
        "invalid_ftp": "ftp://example.com/file.mp3",
        "invalid_file": "file:///local/path",
        "empty": "",
        "whitespace": "   ",
        "localhost": "http://localhost/file.mp3",
        "private_ipv4": "http://192.168.1.1/file.mp3",
        "private_ipv4_10": "http://10.0.0.1/file.mp3",
        "private_ipv4_172": "http://172.16.0.1/file.mp3",
        "loopback": "http://127.0.0.1/file.mp3",
        "link_local": "http://169.254.0.1/file.mp3",
    }


@pytest.fixture
def sample_youtube_urls():
    """Sample YouTube URLs for testing YouTube utilities."""
    return {
        "standard_watch": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "standard_watch_with_params": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s",
        "short_url": "https://youtu.be/dQw4w9WgXcQ",
        "short_url_with_params": "https://youtu.be/dQw4w9WgXcQ?t=30",
        "embed_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "embed_url_with_params": "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1",
        "v_url": "https://www.youtube.com/v/dQw4w9WgXcQ",
        "mobile_url": "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "invalid_no_video_id": "https://www.youtube.com/watch",
        "invalid_wrong_domain": "https://example.com/watch?v=dQw4w9WgXcQ",
        "invalid_short_id": "https://www.youtube.com/watch?v=short",
        "invalid_long_id": "https://www.youtube.com/watch?v=dQw4w9WgXcQextra",
        "empty": "",
        "none": None,
    }


@pytest.fixture
def sample_video_ids():
    """Sample video IDs for testing."""
    return {
        "valid": "dQw4w9WgXcQ",
        "valid_with_underscore": "dQw4w9WgX_Q",
        "valid_with_hyphen": "dQw4w9WgX-Q",
        "short": "short",
        "long": "dQw4w9WgXcQextra",
        "empty": "",
        "none": None,
    }


@pytest.fixture
def sample_transcript_segments():
    """Sample transcript segments for testing formatters."""
    return [
        TranscriptSegment(text="Hello", start=0.0, end=1.0),
        TranscriptSegment(text="world", start=1.0, end=2.0),
        TranscriptSegment(text="How are you?", start=2.0, end=4.0),
    ]


@pytest.fixture
def sample_transcript_segments_empty():
    """Empty transcript segments list."""
    return []


@pytest.fixture
def sample_transcript_segments_with_empty_text():
    """Transcript segments with some empty text."""
    return [
        TranscriptSegment(text="Hello", start=0.0, end=1.0),
        TranscriptSegment(text="", start=1.0, end=2.0),
        TranscriptSegment(text="   ", start=2.0, end=3.0),
        TranscriptSegment(text="world", start=3.0, end=4.0),
    ]


@pytest.fixture
def sample_timestamps():
    """Sample timestamps for testing formatters."""
    return {
        "zero": 0.0,
        "small": 0.001,
        "one_second": 1.0,
        "one_minute": 60.0,
        "one_hour": 3600.0,
        "with_milliseconds": 125.5,
        "with_precise_milliseconds": 3661.123,
        "negative": -1.0,
        "very_large": 999999.999,
        "nan": float("nan"),
        "inf": float("inf"),
        "negative_inf": float("-inf"),
    }


@pytest.fixture
def sample_data_for_serialization():
    """Sample data structures for testing serialization."""
    return {
        "simple_dict": {"job_id": "123", "created_at": "2024-01-01"},
        "nested_dict": {
            "job_id": "123",
            "result": {"video_id": "abc", "created_at": "2024-01-01"},
        },
        "list_of_dicts": [
            {"job_id": "123", "created_at": "2024-01-01"},
            {"job_id": "456", "created_at": "2024-01-02"},
        ],
        "mixed_structure": {
            "job_id": "123",
            "segments": [
                {"text": "Hello", "start": 0.0},
                {"text": "world", "start": 1.0},
            ],
            "metadata": {"created_at": "2024-01-01", "video_id": "abc"},
        },
        "primitive_string": "hello",
        "primitive_int": 123,
        "primitive_float": 45.67,
        "primitive_bool": True,
        "primitive_none": None,
        "empty_dict": {},
        "empty_list": [],
    }


@pytest.fixture
def sample_sensitive_strings():
    """Sample sensitive strings for testing security utilities."""
    return {
        "api_key": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
        "short_string": "abc",
        "empty": "",
        "none": None,
        "long_string": "a" * 100,
        "unicode_string": "测试字符串",
    }


@pytest.fixture
def sample_error_messages():
    """Sample error messages for testing error sanitization."""
    return {
        "with_file_path": "Error in /app/models/whisper.py: Model not loaded",
        "with_api_key": "Error: API key abc12345678901234567890 is invalid",
        "with_windows_path": "Error in C:\\Users\\test\\file.py: File not found",
        "with_unix_path": "Error in /home/user/project/src/main.py: Import failed",
        "with_multiple_paths": "Error in /app/models/whisper.py: Failed to load from /tmp/model.bin",
        "simple": "Simple error message",
        "empty": "",
        "none": None,
    }


@pytest.fixture
def sample_exceptions():
    """Sample exceptions for testing error detection."""
    return {
        "ip_blocked_exception": Exception("IP address blocked by YouTube"),
        "ip_blocked_upper": Exception("IP ADDRESS BLOCKED BY YOUTUBE"),
        "ip_blocked_lower": Exception("ip address blocked by youtube"),
        "request_blocked": Exception("RequestBlocked: Too many requests"),
        "ip_blocked_type": type("IpBlockedError", (Exception,), {}),
        "cloud_provider": Exception("Cloud provider IP blocked"),
        "normal_exception": Exception("Video not found"),
        "value_error": ValueError("Invalid input"),
        "key_error": KeyError("key"),
    }


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    mock = Mock()
    mock.youtube_video_id_length = 11
    mock.max_url_length = 2048
    return mock


@pytest.fixture
def mock_socket():
    """Mock socket module for testing URL resolution."""
    import socket as real_socket

    with patch("app.utils.url_validation.socket") as mock:
        # Preserve real exception classes and constants
        mock.gaierror = real_socket.gaierror
        mock.AF_INET6 = real_socket.AF_INET6
        mock.SOCK_STREAM = real_socket.SOCK_STREAM
        yield mock


@pytest.fixture
def mock_ipaddress():
    """Mock ipaddress module for testing."""
    with patch("app.utils.url_validation.ipaddress") as mock:
        yield mock
