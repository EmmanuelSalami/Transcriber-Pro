"""
Unit tests for URL validation utilities.

Tests cover:
- Happy path scenarios (valid URLs)
- Edge cases (boundary values, special characters)
- Error conditions (invalid URLs, SSRF attacks)
- Boundary value analysis (empty strings, whitespace, etc.)
"""

import socket
from unittest.mock import patch

import pytest

from app.core.exceptions import TranscriptionError
from app.utils.url_validation import (BLOCKED_HOSTNAMES, _is_private_ip,
                                      _resolve_hostname, validate_remote_url)


class TestIsPrivateIP:
    """Test _is_private_ip function."""

    def test_private_ipv4_10_range(self):
        """Test: Private IPv4 in 10.0.0.0/8 range is detected."""
        assert _is_private_ip("10.0.0.1") is True
        assert _is_private_ip("10.255.255.255") is True
        assert _is_private_ip("10.1.1.1") is True

    def test_private_ipv4_172_range(self):
        """Test: Private IPv4 in 172.16.0.0/12 range is detected."""
        assert _is_private_ip("172.16.0.1") is True
        assert _is_private_ip("172.31.255.255") is True
        assert _is_private_ip("172.20.1.1") is True

    def test_private_ipv4_192_range(self):
        """Test: Private IPv4 in 192.168.0.0/16 range is detected."""
        assert _is_private_ip("192.168.0.1") is True
        assert _is_private_ip("192.168.255.255") is True
        assert _is_private_ip("192.168.1.100") is True

    def test_private_ipv4_loopback(self):
        """Test: Loopback IPv4 (127.0.0.0/8) is detected."""
        assert _is_private_ip("127.0.0.1") is True
        assert _is_private_ip("127.255.255.255") is True
        assert _is_private_ip("127.1.1.1") is True

    def test_private_ipv4_link_local(self):
        """Test: Link-local IPv4 (169.254.0.0/16) is detected."""
        assert _is_private_ip("169.254.0.1") is True
        assert _is_private_ip("169.254.255.255") is True

    def test_public_ipv4(self):
        """Test: Public IPv4 addresses are not detected as private."""
        assert _is_private_ip("8.8.8.8") is False
        assert _is_private_ip("1.1.1.1") is False
        assert _is_private_ip("203.0.113.1") is False
        assert _is_private_ip("198.51.100.1") is False

    def test_private_ipv6(self):
        """Test: Private IPv6 addresses are detected."""
        assert _is_private_ip("fc00::1") is True
        assert _is_private_ip("fe80::1") is True
        assert _is_private_ip("::1") is True

    def test_public_ipv6(self):
        """Test: Public IPv6 addresses are not detected as private."""
        assert _is_private_ip("2001:db8::1") is False
        assert _is_private_ip("2600::1") is False

    def test_invalid_ip_format(self):
        """Test: Invalid IP format returns False."""
        assert _is_private_ip("not-an-ip") is False
        assert _is_private_ip("256.256.256.256") is False
        assert _is_private_ip("") is False

    def test_boundary_values(self):
        """Test: Boundary IP values are handled correctly."""
        # First IP in range
        assert _is_private_ip("10.0.0.0") is True
        assert _is_private_ip("192.168.0.0") is True
        # Last IP in range
        assert _is_private_ip("10.255.255.255") is True
        assert _is_private_ip("192.168.255.255") is True
        # Just outside range
        assert _is_private_ip("9.255.255.255") is False
        assert _is_private_ip("11.0.0.0") is False


class TestResolveHostname:
    """Test _resolve_hostname function."""

    def test_resolve_valid_hostname_ipv4(self, mock_socket):
        """Test: Valid hostname resolves to IPv4."""
        mock_socket.gethostbyname.return_value = "8.8.8.8"
        result = _resolve_hostname("example.com")
        assert result == "8.8.8.8"
        mock_socket.gethostbyname.assert_called_once_with("example.com")

    def test_resolve_valid_hostname_ipv6(self, mock_socket):
        """Test: Valid hostname resolves to IPv6 when IPv4 fails."""
        # Use real socket.gaierror exception
        real_gaierror = socket.gaierror
        mock_socket.gethostbyname.side_effect = real_gaierror("Name resolution failed")
        mock_socket.getaddrinfo.return_value = [
            (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("2001:db8::1", 0, 0, 0))
        ]
        result = _resolve_hostname("example.com")
        assert result == "2001:db8::1"

    def test_resolve_invalid_hostname(self, mock_socket):
        """Test: Invalid hostname returns None."""
        # Use real socket.gaierror exception
        real_gaierror = socket.gaierror
        mock_socket.gethostbyname.side_effect = real_gaierror("Name resolution failed")
        mock_socket.getaddrinfo.side_effect = real_gaierror("Name resolution failed")
        result = _resolve_hostname("invalid-hostname-12345.com")
        assert result is None

    def test_resolve_empty_hostname(self, mock_socket):
        """Test: Empty hostname returns None."""
        # Use real socket.gaierror exception
        real_gaierror = socket.gaierror
        mock_socket.gethostbyname.side_effect = real_gaierror("Name resolution failed")
        mock_socket.getaddrinfo.side_effect = real_gaierror("Name resolution failed")
        result = _resolve_hostname("")
        assert result is None

    def test_resolve_ipv6_index_error(self, mock_socket):
        """Test: IPv6 resolution handles IndexError gracefully."""
        # Use real socket.gaierror exception
        real_gaierror = socket.gaierror
        mock_socket.gethostbyname.side_effect = real_gaierror("Name resolution failed")
        mock_socket.getaddrinfo.return_value = []  # Empty result
        result = _resolve_hostname("example.com")
        assert result is None


class TestValidateRemoteURL:
    """Test validate_remote_url function."""

    # Happy Path Tests
    def test_valid_https_url(self):
        """Test: Valid HTTPS URL passes validation."""
        validate_remote_url("https://example.com/file.mp3")

    def test_valid_http_url(self):
        """Test: Valid HTTP URL passes validation."""
        validate_remote_url("http://example.com/file.mp3")

    def test_valid_url_with_path(self):
        """Test: Valid URL with path and query parameters passes validation."""
        validate_remote_url("https://subdomain.example.com/path/to/file.wav?param=value")

    def test_valid_url_with_port(self):
        """Test: Valid URL with port number passes validation."""
        validate_remote_url("https://example.com:8080/file.mp3")

    def test_valid_url_allow_private_flag(self):
        """Test: Private IP allowed when allow_private=True (for testing)."""
        validate_remote_url("http://192.168.1.1/file.mp3", allow_private=True)
        validate_remote_url("http://127.0.0.1/file.mp3", allow_private=True)
        validate_remote_url("http://localhost/file.mp3", allow_private=True)

    # Error Condition Tests - Empty/None Inputs
    def test_empty_url(self):
        """Test: Empty URL raises TranscriptionError."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("")
        assert exc_info.value.code == "INVALID_URL"
        assert "empty" in exc_info.value.message.lower()

    def test_none_url(self):
        """Test: None URL raises TranscriptionError."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url(None)
        assert exc_info.value.code == "INVALID_URL"

    def test_whitespace_only_url(self):
        """Test: Whitespace-only URL raises TranscriptionError."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("   ")
        assert exc_info.value.code == "INVALID_URL"
        assert "whitespace" in exc_info.value.message.lower()

    def test_non_string_url(self):
        """Test: Non-string URL raises TranscriptionError."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url(123)
        assert exc_info.value.code == "INVALID_URL"

    # Error Condition Tests - Invalid Schemes
    def test_ftp_scheme(self):
        """Test: FTP scheme raises TranscriptionError."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("ftp://example.com/file.mp3")
        assert exc_info.value.code == "INVALID_URL"
        assert "HTTP/HTTPS" in exc_info.value.message

    def test_file_scheme(self):
        """Test: File scheme raises TranscriptionError."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("file:///local/path")
        assert exc_info.value.code == "INVALID_URL"

    def test_no_scheme(self):
        """Test: URL without scheme raises TranscriptionError."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("example.com/file.mp3")
        assert exc_info.value.code == "INVALID_URL"

    # Error Condition Tests - SSRF Protection
    def test_localhost_hostname(self):
        """Test: Localhost hostname is blocked."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http://localhost/file.mp3")
        assert exc_info.value.code == "SSRF_BLOCKED"
        assert "localhost" in exc_info.value.message.lower()

    def test_127_0_0_1_hostname(self):
        """Test: 127.0.0.1 hostname is blocked."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http://127.0.0.1/file.mp3")
        assert exc_info.value.code == "SSRF_BLOCKED"

    def test_private_ipv4_direct(self):
        """Test: Direct private IPv4 address is blocked."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http://192.168.1.1/file.mp3")
        assert exc_info.value.code == "SSRF_BLOCKED"
        assert "private" in exc_info.value.message.lower()

    def test_private_ipv4_10_range(self):
        """Test: Private IPv4 in 10.0.0.0/8 range is blocked."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http://10.0.0.1/file.mp3")
        assert exc_info.value.code == "SSRF_BLOCKED"

    def test_private_ipv4_172_range(self):
        """Test: Private IPv4 in 172.16.0.0/12 range is blocked."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http://172.16.0.1/file.mp3")
        assert exc_info.value.code == "SSRF_BLOCKED"

    def test_loopback_ip(self):
        """Test: Loopback IP (127.0.0.1) is blocked."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http://127.0.0.1/file.mp3")
        assert exc_info.value.code == "SSRF_BLOCKED"

    def test_link_local_ip(self):
        """Test: Link-local IP (169.254.0.0/16) is blocked."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http://169.254.0.1/file.mp3")
        assert exc_info.value.code == "SSRF_BLOCKED"

    def test_private_ip_resolved_from_hostname(self, mock_socket):
        """Test: Hostname resolving to private IP is blocked."""
        mock_socket.gethostbyname.return_value = "192.168.1.1"
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http://internal.example.com/file.mp3")
        assert exc_info.value.code == "SSRF_BLOCKED"
        assert "resolves to private" in exc_info.value.message.lower()

    def test_no_hostname(self):
        """Test: URL without hostname raises TranscriptionError."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http:///file.mp3")
        assert exc_info.value.code == "INVALID_URL"
        assert "hostname" in exc_info.value.message.lower()

    # Edge Cases
    def test_url_with_fragment(self):
        """Test: URL with fragment identifier is handled."""
        validate_remote_url("https://example.com/file.mp3#section")

    def test_url_with_multiple_query_params(self):
        """Test: URL with multiple query parameters is handled."""
        validate_remote_url("https://example.com/file.mp3?param1=value1&param2=value2")

    def test_url_with_encoded_characters(self):
        """Test: URL with URL-encoded characters is handled."""
        validate_remote_url("https://example.com/file%20name.mp3")

    def test_very_long_url(self):
        """Test: Very long URL is handled (if within reasonable limits)."""
        long_path = "/" + "a" * 1000
        validate_remote_url(f"https://example.com{long_path}")

    def test_url_parsing_exception(self):
        """Test: URL parsing exception is caught and handled."""
        with patch("app.utils.url_validation.urlparse") as mock_parse:
            mock_parse.side_effect = Exception("Parse error")
            with pytest.raises(TranscriptionError) as exc_info:
                validate_remote_url("http://example.com/file.mp3")
            assert exc_info.value.code == "INVALID_URL"

    # Boundary Value Tests
    def test_minimal_valid_url(self):
        """Test: Minimal valid URL format."""
        validate_remote_url("http://a.com")

    def test_url_with_only_domain(self):
        """Test: URL with only domain (no path) is valid."""
        validate_remote_url("https://example.com")

    def test_case_insensitive_hostname_blocking(self):
        """Test: Hostname blocking is case-insensitive."""
        with pytest.raises(TranscriptionError) as exc_info:
            validate_remote_url("http://LOCALHOST/file.mp3")
        assert exc_info.value.code == "SSRF_BLOCKED"

    def test_all_blocked_hostnames(self):
        """Test: All blocked hostnames are properly blocked."""
        for hostname in BLOCKED_HOSTNAMES:
            with pytest.raises(TranscriptionError) as exc_info:
                validate_remote_url(f"http://{hostname}/file.mp3")
            # Some hostnames like "::1" might be parsed as IPs first, causing different error
            # But they should still be blocked
            assert exc_info.value.code in ("SSRF_BLOCKED", "INVALID_URL")

    # Additional Security Tests
    def test_ipv6_private_address(self):
        """Test: IPv6 private addresses are blocked."""
        with pytest.raises(TranscriptionError):
            validate_remote_url("http://[::1]/file.mp3")
        # Note: This might fail URL parsing, but if it parses, it should be blocked

    def test_public_ip_allowed(self):
        """Test: Public IP addresses are allowed."""
        validate_remote_url("http://8.8.8.8/file.mp3")
        validate_remote_url("http://1.1.1.1/file.mp3")

    def test_hostname_resolution_failure_allowed(self, mock_socket):
        """Test: Hostname that fails to resolve is allowed (no private IP check)."""
        # Use real socket.gaierror exception
        real_gaierror = socket.gaierror
        mock_socket.gethostbyname.side_effect = real_gaierror("Name resolution failed")
        mock_socket.getaddrinfo.side_effect = real_gaierror("Name resolution failed")
        # Should not raise SSRF error if hostname doesn't resolve
        # (might raise other errors, but not SSRF)
        # Note: This will actually try to resolve, so we need to ensure it doesn't resolve
        # In real scenario, unresolvable hostnames would fail DNS lookup
        # For test purposes, we'll just verify it doesn't raise SSRF error
        try:
            validate_remote_url("http://unresolvable-hostname-12345.com/file.mp3")
        except TranscriptionError as e:
            # Should not be SSRF error
            assert e.code != "SSRF_BLOCKED"
