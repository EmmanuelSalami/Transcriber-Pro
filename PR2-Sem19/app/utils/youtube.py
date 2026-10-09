"""YouTube URL parsing and video ID extraction utilities."""

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse


def _validate_video_id(video_id: str) -> bool:
    """Validate that a video ID is exactly 11 characters (YouTube standard).

    YouTube video IDs are always exactly 11 alphanumeric characters (with
    possible hyphens and underscores). This function validates that the
    extracted ID matches this format.

    Args:
        video_id: Video ID to validate (can be None or empty).

    Returns:
        bool: True if video ID is exactly 11 characters, False otherwise.
            Returns False if video_id is None or empty.

    Example:
        >>> _validate_video_id("dQw4w9WgXcQ")
        True
        >>> _validate_video_id("short")
        False
        >>> _validate_video_id("")
        False
        >>> _validate_video_id(None)
        False
    """
    from app.core.config import settings

    return video_id is not None and len(video_id) == settings.youtube_video_id_length


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats.

    Supports multiple YouTube URL formats including standard watch URLs,
    short URLs (youtu.be), embed URLs, and direct video URLs. Validates
    that the extracted ID is exactly 11 characters (YouTube standard).

    Supported formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID

    Args:
        url: YouTube video URL (will be sanitized and validated).

    Returns:
        Optional[str]: Video ID if found and valid (11 characters), None otherwise.

    Example:
        >>> extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> extract_video_id("invalid-url")
        None
    """
    if not url or not isinstance(url, str):
        return None

    url = url.strip()
    from app.core.config import settings

    if len(url) > settings.max_url_length:
        return None

    try:
        parsed = urlparse(url)
    except Exception:
        return None

    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        video_id = parsed.path.lstrip("/")
        if video_id and _validate_video_id(video_id):
            return video_id

    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if "/embed/" in parsed.path:
            video_id = parsed.path.split("/embed/")[-1]
            video_id = video_id.split("?")[0]
            if _validate_video_id(video_id):
                return video_id
        if "/v/" in parsed.path:
            video_id = parsed.path.split("/v/")[-1]
            video_id = video_id.split("?")[0]
            if _validate_video_id(video_id):
                return video_id

        query_params = parse_qs(parsed.query)
        if "v" in query_params:
            video_id = query_params["v"][0]
            if _validate_video_id(video_id):
                return video_id

    from app.core.config import settings

    video_id_length = settings.youtube_video_id_length
    patterns = [
        rf"(?:v=|\/)([0-9A-Za-z_-]{{{video_id_length}}})(?:[?&#]|$)",
        rf"(?:embed\/)([0-9A-Za-z_-]{{{video_id_length}}})(?:[?&#]|$)",
        rf"(?:youtu\.be\/)([0-9A-Za-z_-]{{{video_id_length}}})(?:[?&#]|$)",
    ]

    for pattern in patterns:
        try:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                if video_id and len(video_id) == video_id_length:
                    return video_id
        except Exception:
            continue

    return None


def is_valid_youtube_url(url: str) -> bool:
    """Check if the URL is a valid YouTube URL.

    Validates that the provided URL is a valid YouTube URL by attempting
    to extract a video ID from it. If a valid video ID can be extracted,
    the URL is considered valid.

    Args:
        url: URL to validate.

    Returns:
        bool: True if valid YouTube URL (can extract video ID), False otherwise.

    Example:
        >>> is_valid_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        True
        >>> is_valid_youtube_url("https://youtu.be/dQw4w9WgXcQ")
        True
        >>> is_valid_youtube_url("https://example.com")
        False
    """
    return extract_video_id(url) is not None
