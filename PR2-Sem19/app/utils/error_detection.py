"""Utilities for detecting specific error types from exceptions."""


def is_ip_blocked_error(exception: Exception) -> bool:
    """Check if an exception indicates IP blocking by YouTube.

    Analyzes exception type and message to determine if the error is related
    to IP blocking by YouTube's API. This is useful for providing specific
    error messages to users when their IP has been blocked.

    Args:
        exception: The exception to check (any exception type).

    Returns:
        bool: True if the exception indicates IP blocking, False otherwise.

    Example:
        >>> exc = Exception("IP address blocked by YouTube")
        >>> is_ip_blocked_error(exc)
        True
        >>> exc = Exception("Video not found")
        >>> is_ip_blocked_error(exc)
        False
    """
    error_type = type(exception).__name__
    error_str = str(exception)
    error_lower = error_str.lower()
    error_upper = error_str.upper()

    return (
        "IpBlocked" in error_type
        or "RequestBlocked" in error_type
        or ("IP" in error_upper and "BLOCKED" in error_upper)
        or ("ip address" in error_lower and "blocked" in error_lower)
        or "cloud provider" in error_lower
    )
