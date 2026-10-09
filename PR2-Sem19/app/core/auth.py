"""Authentication and authorization utilities."""

import logging
import os
from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.utils.security import sanitize_for_logging

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
security = HTTPBearer(auto_error=False)


async def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """
    Verify API key from Bearer token in Authorization header.

    Validates the API key provided in the Bearer token against configured valid keys.
    In development mode (no API keys configured), allows all requests with a warning.
    In production mode, raises HTTPException for invalid keys.

    Args:
        credentials (HTTPAuthorizationCredentials): HTTP authorization credentials
            containing the Bearer token (injected via FastAPI Security dependency)

    Returns:
        str: The API key if valid, or a placeholder ("dev_mode_no_key") in development mode

    Raises:
        HTTPException: If API key is invalid in production mode (status 401 Unauthorized)

    Example:
        Used as a FastAPI dependency:
        ```python
        @router.get("/endpoint")
        async def endpoint(api_key: str = Depends(verify_api_key)):
            # api_key is verified here
            pass
        ```
    """
    api_key = credentials.credentials if credentials else None
    if not api_key or not str(api_key).strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    api_key = str(api_key).strip()
    valid_keys = settings.get_api_keys()
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true" or settings.dev_mode

    # 1. Check shared API_KEYS first
    if valid_keys and api_key in valid_keys:
        return api_key

    # 2. Check user-scoped API keys (for Apple Shortcuts, etc.)
    try:
        from app.services.credits.api_key_service import api_key_service

        user_id = await api_key_service.lookup_user_id(api_key)
        if user_id:
            return api_key  # Valid user key
    except Exception as e:
        logger.warning(f"User API key lookup failed: {e}")

    # 3. Dev mode fallback
    if not valid_keys and dev_mode:
        logger.warning(
            "DEV MODE: No API keys configured - allowing all requests (INSECURE). "
            "This should only be used for local development!"
        )
        return api_key if api_key else "dev_mode_no_key"

    if not valid_keys:
        logger.error(
            "SECURITY ERROR: No API keys configured in production mode! "
            "Rejecting all requests. Set DEV_MODE=true for development or configure API_KEYS."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API keys must be configured in production",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key_hash = sanitize_for_logging(api_key)
    logger.warning(f"Invalid API key attempted: hash={api_key_hash}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_user_id_from_request(request: Request) -> Optional[str]:
    """
    Resolve user_id from X-User-Id header or from user API key (Bearer token).
    Returns None if neither is present.
    """
    x_user_id = request.headers.get("X-User-Id", "").strip()
    if x_user_id:
        return x_user_id
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        try:
            from app.services.credits.api_key_service import api_key_service

            return await api_key_service.lookup_user_id(token)
        except Exception:
            pass
    return None


def get_rate_limit_key(api_key: str) -> str:
    """
    Generate rate limit key for an API key.

    Creates a unique rate limit key string for rate limiting purposes.
    This allows rate limiting to be applied per API key rather than per IP address.

    Args:
        api_key (str): The API key to generate a rate limit key for

    Returns:
        str: Rate limit key string in format "api_key:{api_key}"

    Example:
        >>> get_rate_limit_key("my-secret-key")
        'api_key:my-secret-key'
    """
    return f"api_key:{api_key}"
