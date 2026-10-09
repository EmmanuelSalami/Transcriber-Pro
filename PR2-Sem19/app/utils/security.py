"""Security utilities for safe logging and sanitization."""

import hashlib
import logging
import os
import re

logger = logging.getLogger(__name__)


def sanitize_for_logging(value: str, max_chars: int = 8) -> str:
    """Create a safe hash for logging sensitive values like API keys.

    Uses SHA-256 to create a deterministic hash that can be used for
    logging and tracking without exposing the actual value.

    Args:
        value: Sensitive value to hash (e.g., API key).
        max_chars: Number of characters to return from hash. Default: 8.

    Returns:
        str: First max_chars characters of SHA-256 hash, or "none" if value is empty.

    Example:
        >>> sanitize_for_logging("my-secret-api-key")
        'a1b2c3d4'
        >>> sanitize_for_logging("")
        'none'
    """
    if not value or not isinstance(value, str):
        return "none"
    return hashlib.sha256(value.encode()).hexdigest()[:max_chars]


def sanitize_error_message(error: str) -> str:
    """Remove sensitive information from error messages.

    Sanitizes error messages to prevent leaking:
    - File paths
    - Potential API keys or tokens
    - Internal system details

    Args:
        error: Error message to sanitize.

    Returns:
        str: Sanitized error message.

    Example:
        >>> sanitize_error_message("Error in /app/models/whisper: API key abc123...")
        'Error in [REDACTED]: API key [REDACTED]'
    """
    if not error:
        return error

    error = re.sub(r"/[\w/]+\.(py|json|log|txt)", "[REDACTED]", error)
    error = re.sub(r"\b[A-Za-z0-9]{20,}\b", "[REDACTED]", error)
    error = re.sub(r"[A-Z]:\\[\\\w\s]+", "[REDACTED]", error)
    error = re.sub(r"/[\w\s/]+", "[REDACTED]", error)

    return error


def is_dev_mode() -> bool:
    """Check if running in development mode.

    Development mode is enabled by setting DEV_MODE environment variable to "true".
    This allows more permissive security settings for local development.

    Returns:
        bool: True if DEV_MODE is set to "true", False otherwise.

    Example:
        >>> import os
        >>> os.environ["DEV_MODE"] = "true"
        >>> is_dev_mode()
        True
    """
    return os.getenv("DEV_MODE", "false").lower() == "true"
