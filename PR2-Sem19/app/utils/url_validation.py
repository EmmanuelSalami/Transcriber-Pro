"""URL validation utilities for SSRF protection."""

import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

from app.core.exceptions import TranscriptionError

logger = logging.getLogger(__name__)

# Private IP ranges to block (RFC 1918, RFC 4193, etc.)
PRIVATE_IPV4_RANGES = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("127.0.0.0/8"),  # Loopback
    ipaddress.IPv4Network("169.254.0.0/16"),  # Link-local
]

PRIVATE_IPV6_RANGES = [
    ipaddress.IPv6Network("fc00::/7"),  # Unique local address
    ipaddress.IPv6Network("fe80::/10"),  # Link-local
    ipaddress.IPv6Network("::1/128"),  # Loopback
]

# Blocked hostnames
BLOCKED_HOSTNAMES = ["localhost", "127.0.0.1", "::1", "0.0.0.0"]


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is in a private/internal range.

    Args:
        ip_str: IP address string (IPv4 or IPv6).

    Returns:
        bool: True if IP is private/internal, False otherwise.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        if isinstance(ip, ipaddress.IPv4Address):
            return any(ip in network for network in PRIVATE_IPV4_RANGES)
        elif isinstance(ip, ipaddress.IPv6Address):
            return any(ip in network for network in PRIVATE_IPV6_RANGES)
    except ValueError:
        return False
    return False


def _resolve_hostname(hostname: str) -> Optional[str]:
    """Resolve hostname to IP address.

    Attempts to resolve the hostname to an IP address, trying IPv4 first,
    then IPv6 if IPv4 resolution fails.

    Args:
        hostname: Hostname to resolve.

    Returns:
        Optional[str]: IP address if resolved, None otherwise.
    """
    try:
        ip = socket.gethostbyname(hostname)
        return ip
    except socket.gaierror:
        try:
            result = socket.getaddrinfo(hostname, None, socket.AF_INET6)
            if result:
                ip_address = result[0][4][0]
                return str(ip_address)
        except (socket.gaierror, IndexError):
            pass
    return None


def validate_remote_url(url: str, allow_private: bool = False) -> None:
    """Validate remote URL to prevent SSRF attacks.

    Validates that the URL:
    - Uses HTTP or HTTPS scheme only
    - Does not point to private/internal IP addresses
    - Does not use blocked hostnames (localhost, etc.)
    - Has a valid hostname

    Args:
        url: URL to validate.
        allow_private: If True, allows private IPs (for testing only). Default: False.

    Raises:
        TranscriptionError: If URL is invalid or points to private/internal resources.
            - code: "INVALID_URL" for invalid URL format
            - code: "SSRF_BLOCKED" for blocked private/internal resources

    Example:
        >>> validate_remote_url("https://example.com/file.mp3")
        >>> # No exception raised
        >>> validate_remote_url("http://192.168.1.1/file.mp3")
        TranscriptionError: SSRF blocked: Private IP ranges not allowed
    """
    if not url or not isinstance(url, str):
        raise TranscriptionError(
            "URL cannot be empty",
            code="INVALID_URL",
            details={"url": str(url) if url else "empty"},
        )

    url = url.strip()
    if not url:
        raise TranscriptionError(
            "URL cannot be empty or whitespace only",
            code="INVALID_URL",
            details={"url": "whitespace"},
        )

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise TranscriptionError(
            f"Invalid URL format: {str(e)}",
            code="INVALID_URL",
            details={"url": url, "error": str(e)},
        )

    if parsed.scheme not in ["http", "https"]:
        raise TranscriptionError(
            f"Only HTTP/HTTPS URLs are allowed, got: {parsed.scheme}",
            code="INVALID_URL",
            details={"url": url, "scheme": parsed.scheme},
        )

    hostname = parsed.hostname
    if not hostname:
        raise TranscriptionError(
            "URL must have a valid hostname",
            code="INVALID_URL",
            details={"url": url},
        )

    hostname_lower = hostname.lower()

    if allow_private:
        return

    if hostname_lower in BLOCKED_HOSTNAMES:
        raise TranscriptionError(
            "SSRF blocked: Localhost and internal hostnames are not allowed",
            code="SSRF_BLOCKED",
            details={"url": url, "hostname": hostname},
        )

    try:
        ip = ipaddress.ip_address(hostname)
        if _is_private_ip(str(ip)):
            raise TranscriptionError(
                "SSRF blocked: Private IP ranges not allowed",
                code="SSRF_BLOCKED",
                details={"url": url, "ip": str(ip)},
            )
    except ValueError:
        resolved_ip = _resolve_hostname(hostname)
        if resolved_ip and _is_private_ip(resolved_ip):
            raise TranscriptionError(
                f"SSRF blocked: Hostname resolves to private IP address: {resolved_ip}",
                code="SSRF_BLOCKED",
                details={"url": url, "hostname": hostname, "resolved_ip": resolved_ip},
            )
