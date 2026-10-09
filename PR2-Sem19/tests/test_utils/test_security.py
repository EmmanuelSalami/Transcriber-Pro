"""
Unit tests for security utilities.

Tests cover:
- Happy path scenarios (valid inputs)
- Edge cases (empty strings, special characters)
- Error conditions (invalid inputs)
- Boundary value analysis (length limits, unicode)
"""

import os
from unittest.mock import patch

from app.utils.security import (is_dev_mode, sanitize_error_message,
                                sanitize_for_logging)


class TestSanitizeForLogging:
    """Test sanitize_for_logging function."""

    def test_valid_string_default_length(self):
        """Test: Valid string returns 8-character hash by default."""
        result = sanitize_for_logging("my-secret-api-key")
        assert isinstance(result, str)
        assert len(result) == 8
        assert result != "my-secret-api-key"  # Should be hashed

    def test_valid_string_custom_length(self):
        """Test: Valid string returns hash with custom length."""
        result = sanitize_for_logging("my-secret-api-key", max_chars=16)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_valid_string_short_length(self):
        """Test: Valid string returns hash with short length."""
        result = sanitize_for_logging("my-secret-api-key", max_chars=4)
        assert isinstance(result, str)
        assert len(result) == 4

    def test_deterministic_hashing(self):
        """Test: Same input produces same hash (deterministic)."""
        input_str = "my-secret-api-key"
        result1 = sanitize_for_logging(input_str)
        result2 = sanitize_for_logging(input_str)
        assert result1 == result2

    def test_different_inputs_different_hashes(self):
        """Test: Different inputs produce different hashes."""
        result1 = sanitize_for_logging("key1")
        result2 = sanitize_for_logging("key2")
        assert result1 != result2

    def test_empty_string(self):
        """Test: Empty string returns 'none'."""
        assert sanitize_for_logging("") == "none"

    def test_none_input(self):
        """Test: None input returns 'none'."""
        assert sanitize_for_logging(None) == "none"

    def test_non_string_input(self):
        """Test: Non-string input returns 'none'."""
        assert sanitize_for_logging(123) == "none"
        assert sanitize_for_logging([]) == "none"
        assert sanitize_for_logging({}) == "none"

    def test_short_string(self):
        """Test: Short string still produces hash."""
        result = sanitize_for_logging("abc")
        assert isinstance(result, str)
        assert len(result) == 8

    def test_long_string(self):
        """Test: Long string produces hash."""
        long_string = "a" * 1000
        result = sanitize_for_logging(long_string)
        assert isinstance(result, str)
        assert len(result) == 8

    def test_unicode_string(self):
        """Test: Unicode string produces hash."""
        result = sanitize_for_logging("测试字符串")
        assert isinstance(result, str)
        assert len(result) == 8

    def test_special_characters(self):
        """Test: String with special characters produces hash."""
        result = sanitize_for_logging("key!@#$%^&*()")
        assert isinstance(result, str)
        assert len(result) == 8

    def test_zero_length(self):
        """Test: Zero max_chars returns empty string."""
        result = sanitize_for_logging("test", max_chars=0)
        assert result == ""

    def test_very_long_hash_length(self):
        """Test: Very long max_chars returns full hash."""
        result = sanitize_for_logging("test", max_chars=100)
        # SHA-256 produces 64 hex characters
        assert len(result) == 64

    def test_whitespace_string(self):
        """Test: Whitespace-only string produces hash."""
        result = sanitize_for_logging("   ")
        assert isinstance(result, str)
        assert len(result) == 8
        assert result != "none"  # Whitespace is not empty

    def test_newline_in_string(self):
        """Test: String with newlines produces hash."""
        result = sanitize_for_logging("key\nwith\nnewlines")
        assert isinstance(result, str)
        assert len(result) == 8


class TestSanitizeErrorMessage:
    """Test sanitize_error_message function."""

    def test_simple_error_message(self):
        """Test: Simple error message without sensitive data returns unchanged."""
        error = "Simple error message"
        result = sanitize_error_message(error)
        assert result == "Simple error message"

    def test_error_with_file_path(self):
        """Test: Error with file path redacts the path."""
        error = "Error in /app/models/whisper.py: Model not loaded"
        result = sanitize_error_message(error)
        assert "[REDACTED]" in result
        assert "/app/models/whisper.py" not in result

    def test_error_with_multiple_file_paths(self):
        """Test: Error with multiple file paths redacts all paths."""
        error = "Error in /app/models/whisper.py: Failed to load from /tmp/model.bin"
        result = sanitize_error_message(error)
        assert error.count("/") > result.count("/")  # Paths should be redacted

    def test_error_with_api_key(self):
        """Test: Error with long alphanumeric string (potential API key) is redacted."""
        error = "Error: API key abc12345678901234567890 is invalid"
        result = sanitize_error_message(error)
        assert "[REDACTED]" in result
        assert "abc12345678901234567890" not in result

    def test_error_with_windows_path(self):
        """Test: Error with Windows path is redacted."""
        error = "Error in C:\\Users\\test\\file.py: File not found"
        result = sanitize_error_message(error)
        assert "[REDACTED]" in result
        assert "C:\\Users\\test\\file.py" not in result

    def test_error_with_unix_path(self):
        """Test: Error with Unix path is redacted."""
        error = "Error in /home/user/project/src/main.py: Import failed"
        result = sanitize_error_message(error)
        assert "[REDACTED]" in result
        assert "/home/user/project/src/main.py" not in result

    def test_error_with_json_file(self):
        """Test: Error with .json file path is redacted."""
        error = "Error loading /app/config.json: Parse error"
        result = sanitize_error_message(error)
        assert "[REDACTED]" in result

    def test_error_with_log_file(self):
        """Test: Error with .log file path is redacted."""
        error = "Error writing to /var/log/app.log: Permission denied"
        result = sanitize_error_message(error)
        assert "[REDACTED]" in result

    def test_error_with_txt_file(self):
        """Test: Error with .txt file path is redacted."""
        error = "Error reading /tmp/data.txt: File not found"
        result = sanitize_error_message(error)
        assert "[REDACTED]" in result

    def test_error_with_py_file(self):
        """Test: Error with .py file path is redacted."""
        error = "Error in /app/main.py: Import error"
        result = sanitize_error_message(error)
        assert "[REDACTED]" in result

    def test_empty_error_message(self):
        """Test: Empty error message returns empty string."""
        assert sanitize_error_message("") == ""

    def test_none_error_message(self):
        """Test: None error message returns None."""
        assert sanitize_error_message(None) is None

    def test_error_with_short_alphanumeric(self):
        """Test: Short alphanumeric strings (not API keys) are not redacted."""
        error = "Error: ID abc123 is invalid"
        result = sanitize_error_message(error)
        # Short strings (< 20 chars) should not be redacted
        assert "abc123" in result or "[REDACTED]" not in result

    def test_error_with_exactly_20_chars(self):
        """Test: Exactly 20-character string may or may not be redacted."""
        error = "Error: Key abc1234567890123456 is invalid"
        result = sanitize_error_message(error)
        # 20 chars might be redacted (>= 20 in regex)
        assert isinstance(result, str)

    def test_error_with_mixed_content(self):
        """Test: Error with mixed sensitive and non-sensitive content."""
        error = "Error in /app/models/whisper.py: API key abc12345678901234567890 failed"
        result = sanitize_error_message(error)
        assert "[REDACTED]" in result
        assert "/app/models/whisper.py" not in result
        assert "abc12345678901234567890" not in result

    def test_error_with_multiple_long_strings(self):
        """Test: Error with multiple long alphanumeric strings."""
        error = "Key1 abc12345678901234567890 and Key2 def09876543210987654321 failed"
        result = sanitize_error_message(error)
        assert "abc12345678901234567890" not in result
        assert "def09876543210987654321" not in result

    def test_error_with_unicode(self):
        """Test: Error with unicode characters is handled."""
        error = "错误在 /app/models/whisper.py: 模型未加载"
        result = sanitize_error_message(error)
        assert isinstance(result, str)
        # Path should still be redacted
        assert "/app/models/whisper.py" not in result or "[REDACTED]" in result

    def test_error_with_special_characters(self):
        """Test: Error with special characters is handled."""
        error = "Error in /app/file.py: Key !@#$%^&*() failed"
        result = sanitize_error_message(error)
        assert isinstance(result, str)

    def test_error_with_newlines(self):
        """Test: Error with newlines is handled."""
        error = "Error in /app/file.py:\nLine 1\nLine 2"
        result = sanitize_error_message(error)
        assert isinstance(result, str)
        assert "[REDACTED]" in result


class TestIsDevMode:
    """Test is_dev_mode function."""

    def test_dev_mode_true(self):
        """Test: DEV_MODE=true returns True."""
        with patch.dict(os.environ, {"DEV_MODE": "true"}):
            assert is_dev_mode() is True

    def test_dev_mode_uppercase_true(self):
        """Test: DEV_MODE=TRUE returns True (case insensitive)."""
        with patch.dict(os.environ, {"DEV_MODE": "TRUE"}):
            assert is_dev_mode() is True

    def test_dev_mode_mixed_case_true(self):
        """Test: DEV_MODE=True returns True (case insensitive)."""
        with patch.dict(os.environ, {"DEV_MODE": "True"}):
            assert is_dev_mode() is True

    def test_dev_mode_false(self):
        """Test: DEV_MODE=false returns False."""
        with patch.dict(os.environ, {"DEV_MODE": "false"}):
            assert is_dev_mode() is False

    def test_dev_mode_not_set(self):
        """Test: DEV_MODE not set returns False."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove DEV_MODE if it exists
            os.environ.pop("DEV_MODE", None)
            assert is_dev_mode() is False

    def test_dev_mode_empty_string(self):
        """Test: DEV_MODE='' returns False."""
        with patch.dict(os.environ, {"DEV_MODE": ""}):
            assert is_dev_mode() is False

    def test_dev_mode_other_value(self):
        """Test: DEV_MODE with other value returns False."""
        with patch.dict(os.environ, {"DEV_MODE": "yes"}):
            assert is_dev_mode() is False

    def test_dev_mode_whitespace(self):
        """Test: DEV_MODE with whitespace returns False."""
        with patch.dict(os.environ, {"DEV_MODE": " true "}):
            # Whitespace should make it not equal to "true"
            assert is_dev_mode() is False

    def test_dev_mode_one(self):
        """Test: DEV_MODE=1 returns False (must be exactly 'true')."""
        with patch.dict(os.environ, {"DEV_MODE": "1"}):
            assert is_dev_mode() is False

    def test_dev_mode_yes(self):
        """Test: DEV_MODE=yes returns False (must be exactly 'true')."""
        with patch.dict(os.environ, {"DEV_MODE": "yes"}):
            assert is_dev_mode() is False
