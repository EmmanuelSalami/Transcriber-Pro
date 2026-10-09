"""Unit tests for authentication and authorization utilities.

This module tests:
- API key verification (happy path, edge cases, error conditions)
- Rate limit key generation
- Development mode behavior
- Production mode security
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth import get_rate_limit_key, verify_api_key
from app.core.config import Settings


class TestVerifyApiKey:
    """Test suite for verify_api_key function."""

    def test_verify_api_key_valid_key_happy_path(self, mock_settings):
        """Test: Valid API key should be accepted in production mode.

        Verifies that when a valid API key is provided and the settings
        contain that key, the function returns the API key successfully.
        """
        # Ensure get_api_keys returns a real list
        api_keys_list = ["test-key-1", "test-key-2", "test-key-3"]
        mock_settings.get_api_keys = lambda: api_keys_list

        with patch("app.core.auth.settings", mock_settings):
            with patch("app.core.auth.os.getenv", return_value="false"):
                credentials = HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials="test-key-1"
                )
                result = verify_api_key(credentials)
                assert result == "test-key-1"

    def test_verify_api_key_multiple_valid_keys(self, mock_settings):
        """Test: Any valid key from the list should be accepted.

        Verifies that when multiple API keys are configured, any one
        of them should be accepted.
        """
        # Ensure get_api_keys returns a real list
        api_keys_list = ["test-key-1", "test-key-2", "test-key-3"]
        mock_settings.get_api_keys = lambda: api_keys_list

        with patch("app.core.auth.settings", mock_settings):
            with patch("app.core.auth.os.getenv", return_value="false"):
                # Test first key
                credentials1 = HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials="test-key-1"
                )
                assert verify_api_key(credentials1) == "test-key-1"

                # Test second key
                credentials2 = HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials="test-key-2"
                )
                assert verify_api_key(credentials2) == "test-key-2"

                # Test third key
                credentials3 = HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials="test-key-3"
                )
                assert verify_api_key(credentials3) == "test-key-3"

    def test_verify_api_key_invalid_key_production(self, mock_settings):
        """Test: Invalid API key should raise HTTPException in production.

        Verifies that when an invalid API key is provided in production mode,
        the function raises HTTPException with 401 status.
        """
        # Ensure get_api_keys returns a real list
        api_keys_list = ["test-key-1", "test-key-2", "test-key-3"]
        mock_settings.get_api_keys = lambda: api_keys_list

        with patch("app.core.auth.settings", mock_settings):
            with patch("app.core.auth.os.getenv", return_value="false"):
                credentials = HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials="invalid-key"
                )
                with pytest.raises(HTTPException) as exc_info:
                    verify_api_key(credentials)

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert exc_info.value.detail == "Invalid API key"
                assert "WWW-Authenticate" in exc_info.value.headers
                assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"

    def test_verify_api_key_empty_key_production(self, mock_settings):
        """Test: Empty API key should raise HTTPException in production.

        Edge case: Empty string as API key should be rejected.
        """
        # Ensure get_api_keys returns a real list
        api_keys_list = ["test-key-1", "test-key-2", "test-key-3"]
        mock_settings.get_api_keys = lambda: api_keys_list

        with patch("app.core.auth.settings", mock_settings):
            with patch("app.core.auth.os.getenv", return_value="false"):
                credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
                with pytest.raises(HTTPException) as exc_info:
                    verify_api_key(credentials)

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verify_api_key_no_keys_dev_mode_allows(self, mock_settings_dev_mode):
        """Test: Dev mode allows requests when no API keys configured.

        Verifies that in development mode, when no API keys are configured,
        the function allows the request with a warning.
        """
        with patch("app.core.auth.settings", mock_settings_dev_mode):
            with patch("app.core.auth.os.getenv", return_value="true"):
                credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="any-key")
                result = verify_api_key(credentials)
                assert result == "any-key"

    def test_verify_api_key_no_keys_dev_mode_empty_key(self, mock_settings_dev_mode):
        """Test: Dev mode allows empty key when no API keys configured.

        Edge case: Empty key in dev mode should return placeholder.
        """
        with patch("app.core.auth.settings", mock_settings_dev_mode):
            with patch("app.core.auth.os.getenv", return_value="true"):
                credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
                result = verify_api_key(credentials)
                assert result == "dev_mode_no_key"

    def test_verify_api_key_no_keys_dev_mode_whitespace_key(self, mock_settings_dev_mode):
        """Test: Dev mode handles whitespace-only keys.

        Edge case: Whitespace-only key should be treated as empty.
        """
        with patch("app.core.auth.settings", mock_settings_dev_mode):
            with patch("app.core.auth.os.getenv", return_value="true"):
                credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="   ")
                result = verify_api_key(credentials)
                assert result == "dev_mode_no_key"

    def test_verify_api_key_no_keys_production_raises(self, mock_settings_dev_mode):
        """Test: No API keys in production should raise HTTPException.

        Verifies that when no API keys are configured in production mode,
        the function raises HTTPException.
        """
        # Create settings that are actually in production mode
        prod_settings = Settings(api_keys="", dev_mode=False)

        with patch("app.core.auth.settings", prod_settings):
            with patch("app.core.auth.os.getenv", return_value="false"):
                credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="any-key")
                with pytest.raises(HTTPException) as exc_info:
                    verify_api_key(credentials)

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "API keys must be configured" in exc_info.value.detail

    def test_verify_api_key_case_sensitive(self, mock_settings):
        """Test: API key verification is case-sensitive.

        Boundary case: Verifies that API key matching is case-sensitive.
        """
        # Ensure get_api_keys returns a real list
        api_keys_list = ["test-key-1", "test-key-2", "test-key-3"]
        mock_settings.get_api_keys = lambda: api_keys_list

        with patch("app.core.auth.settings", mock_settings):
            with patch("app.core.auth.os.getenv", return_value="false"):
                credentials = HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials="TEST-KEY-1",  # Different case
                )
                with pytest.raises(HTTPException) as exc_info:
                    verify_api_key(credentials)

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verify_api_key_whitespace_in_key(self, mock_settings):
        """Test: API keys with whitespace are handled correctly.

        Edge case: Keys with leading/trailing whitespace should be stripped
        during comparison (based on get_api_keys implementation).
        """
        # Create settings with keys that have whitespace
        settings_with_whitespace = Settings(
            api_keys="  test-key-1  ,  test-key-2  ", dev_mode=False
        )

        with patch("app.core.auth.settings", settings_with_whitespace):
            with patch("app.core.auth.os.getenv", return_value="false"):
                # Should match after stripping
                credentials = HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials="test-key-1"
                )
                result = verify_api_key(credentials)
                assert result == "test-key-1"

    def test_verify_api_key_dev_mode_env_variable(self, mock_settings):
        """Test: DEV_MODE environment variable takes precedence.

        Verifies that DEV_MODE environment variable overrides settings.dev_mode.
        """
        # Create settings with no API keys but dev_mode=False
        settings_no_keys = Settings(api_keys="", dev_mode=False)

        with patch("app.core.auth.settings", settings_no_keys):
            with patch("app.core.auth.os.getenv", return_value="true"):
                credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="any-key")
                result = verify_api_key(credentials)
                assert result == "any-key"

    def test_verify_api_key_sanitizes_for_logging(self, mock_settings):
        """Test: Invalid API key is sanitized in logs.

        Verifies that when logging invalid API key attempts, the key
        is sanitized to prevent exposure in logs.
        """
        # Ensure get_api_keys returns a real list
        api_keys_list = ["test-key-1", "test-key-2", "test-key-3"]
        mock_settings.get_api_keys = lambda: api_keys_list

        with patch("app.core.auth.settings", mock_settings):
            with patch("app.core.auth.os.getenv", return_value="false"):
                with patch("app.core.auth.sanitize_for_logging") as mock_sanitize:
                    mock_sanitize.return_value = "hashed_key"
                    credentials = HTTPAuthorizationCredentials(
                        scheme="Bearer", credentials="sensitive-api-key"
                    )
                    with pytest.raises(HTTPException):
                        verify_api_key(credentials)

                    # Verify sanitization was called
                    mock_sanitize.assert_called_once()


class TestGetRateLimitKey:
    """Test suite for get_rate_limit_key function."""

    def test_get_rate_limit_key_happy_path(self):
        """Test: Generate rate limit key for valid API key.

        Verifies that the function correctly formats the rate limit key
        with the "api_key:" prefix.
        """
        api_key = "test-api-key-123"
        result = get_rate_limit_key(api_key)
        assert result == "api_key:test-api-key-123"

    def test_get_rate_limit_key_empty_string(self):
        """Test: Handle empty API key string.

        Edge case: Empty string should still generate a valid key format.
        """
        result = get_rate_limit_key("")
        assert result == "api_key:"

    def test_get_rate_limit_key_special_characters(self):
        """Test: Handle API keys with special characters.

        Boundary case: API keys containing special characters should be
        preserved in the rate limit key.
        """
        api_key = "key-with-special-chars-!@#$%"
        result = get_rate_limit_key(api_key)
        assert result == f"api_key:{api_key}"

    def test_get_rate_limit_key_unicode(self):
        """Test: Handle API keys with unicode characters.

        Edge case: Unicode characters in API keys should be preserved.
        """
        api_key = "key-with-unicode-测试"
        result = get_rate_limit_key(api_key)
        assert result == f"api_key:{api_key}"

    def test_get_rate_limit_key_very_long_key(self):
        """Test: Handle very long API keys.

        Boundary case: Very long API keys should be handled correctly.
        """
        api_key = "a" * 1000
        result = get_rate_limit_key(api_key)
        assert result == f"api_key:{api_key}"

    def test_get_rate_limit_key_whitespace(self):
        """Test: Preserve whitespace in API key.

        Edge case: Whitespace in API key should be preserved (not stripped).
        """
        api_key = "  key with spaces  "
        result = get_rate_limit_key(api_key)
        assert result == f"api_key:{api_key}"

    def test_get_rate_limit_key_numeric(self):
        """Test: Handle numeric API keys.

        Edge case: Numeric-only API keys should work correctly.
        """
        api_key = "1234567890"
        result = get_rate_limit_key(api_key)
        assert result == "api_key:1234567890"
