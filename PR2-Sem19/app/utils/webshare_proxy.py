"""WebShare proxy credential fetcher for YouTube transcription.

Uses WEBSHARE_API_KEY to fetch proxy username/password from the WebShare API.
Credentials are cached to avoid API calls on every request.
"""

import logging
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache credentials for 1 hour (3600 seconds)
_CACHE_TTL = 3600
_cached_username: Optional[str] = None
_cached_password: Optional[str] = None
_cache_expires_at: float = 0


def get_webshare_proxy_credentials() -> Optional[tuple[str, str]]:
    """
    Fetch WebShare proxy username and password using the API key.

    Returns (username, password) for use with WebshareProxyConfig or proxy URLs.
    Returns None if WEBSHARE_API_KEY is not set or the API request fails.
    Credentials are cached for 1 hour.
    """
    global _cached_username, _cached_password, _cache_expires_at

    if not settings.webshare_api_key:
        return None

    if _cached_username and _cached_password and time.monotonic() < _cache_expires_at:
        return _cached_username, _cached_password

    try:
        response = httpx.get(
            "https://proxy.webshare.io/api/v2/proxy/list/",
            params={"mode": "backbone", "page": 1, "page_size": 1},
            headers={"Authorization": f"Token {settings.webshare_api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        if not results:
            logger.warning("[WEBSHARE] Proxy list returned no results")
            return None
        proxy = results[0]
        username = proxy.get("username")
        password = proxy.get("password")
        if not username or not password:
            logger.warning("[WEBSHARE] Proxy credentials missing username or password")
            return None
        _cached_username = username
        _cached_password = password
        _cache_expires_at = time.monotonic() + _CACHE_TTL
        logger.info("[WEBSHARE] Fetched proxy credentials successfully")
        return username, password
    except httpx.HTTPStatusError as e:
        logger.error(f"[WEBSHARE] API error: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[WEBSHARE] Failed to fetch proxy credentials: {e}")
        return None


def get_webshare_proxy_url() -> Optional[str]:
    """
    Get a proxy URL suitable for yt-dlp: http://username:password@p.webshare.io:80

    Returns None if credentials are unavailable.
    """
    from urllib.parse import quote

    creds = get_webshare_proxy_credentials()
    if not creds:
        return None
    username, password = creds
    # URL-encode credentials in case they contain special chars (e.g. :, @)
    return f"http://{quote(username, safe='')}:{quote(password, safe='')}@p.webshare.io:80"
