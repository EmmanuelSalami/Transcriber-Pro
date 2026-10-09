"""FastAPI middleware for request tracking and observability."""

import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings
from app.services.infrastructure.observability_service import \
    ObservabilityService

logger = logging.getLogger(__name__)

_observability_service: Optional[ObservabilityService] = None


def get_observability_service() -> ObservabilityService:
    """
    Get or create the observability service instance.

    Implements singleton pattern to ensure only one ObservabilityService
    instance exists throughout the application lifecycle.

    Returns:
        ObservabilityService: Singleton observability service instance

    Example:
        >>> service = get_observability_service()
        >>> service2 = get_observability_service()
        >>> service is service2  # Same instance
        True
    """
    global _observability_service
    if _observability_service is None:
        _observability_service = ObservabilityService()
    return _observability_service


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API requests for Prometheus metrics.

    Automatically tracks:
    - Request count by method, endpoint, and status code
    - Request duration by method and endpoint

    Only tracks requests if metrics are enabled in settings.
    Skips tracking for the /metrics endpoint itself to avoid recursion.

    Attributes:
        _metrics_enabled (bool): Whether metrics tracking is enabled
        _obs_service (Optional[ObservabilityService]): Observability service instance
    """

    def __init__(self, app: ASGIApp) -> None:
        """
        Initialize metrics middleware.

        Args:
            app (ASGIApp): ASGI application instance

        Returns:
            None: Initializes the middleware instance
        """
        super().__init__(app)
        self._metrics_enabled = settings.observability_enabled and settings.metrics_enabled
        self._obs_service: Optional[ObservabilityService] = (
            get_observability_service() if self._metrics_enabled else None
        )
        if self._metrics_enabled:
            logger.info("MetricsMiddleware initialized - request tracking enabled")
        else:
            logger.debug("MetricsMiddleware initialized - metrics disabled")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and track metrics.

        Measures request duration and tracks metrics for successful requests
        and exceptions. Handles exceptions by tracking them as 500 errors
        before re-raising.

        Args:
            request (Request): FastAPI request object
            call_next (Callable): Next middleware/route handler in the chain

        Returns:
            Response: HTTP response from the application

        Raises:
            Exception: Re-raises any exception that occurs during request processing
                after tracking it as a 500 error
        """
        # Skip tracking if metrics disabled
        if not self._metrics_enabled or self._obs_service is None:
            response = await call_next(request)
            return response  # type: ignore[no-any-return]

        # Skip tracking for metrics endpoint itself (avoid recursion)
        if request.url.path.endswith("/metrics"):
            response = await call_next(request)
            return response  # type: ignore[no-any-return]

        # Track request start time
        start_time = time.time()

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Track 500 errors
            status_code = 500
            duration = time.time() - start_time
            self._track_request(request, status_code, duration)
            raise

        # Calculate duration
        duration = time.time() - start_time

        # Track the request
        self._track_request(request, status_code, duration)

        return response  # type: ignore[no-any-return]

    def _track_request(self, request: Request, status_code: int, duration_seconds: float) -> None:
        """
        Track a request using observability service.

        Extracts request method and endpoint path, then records metrics.
        Silently handles any errors in metrics tracking to prevent breaking
        the request flow.

        Args:
            request (Request): FastAPI request object
            status_code (int): HTTP status code of the response
            duration_seconds (float): Request processing duration in seconds

        Returns:
            None: Records metrics in-place, does not return a value

        Note:
            Errors during metrics tracking are logged but do not affect
            the request processing flow.
        """
        if self._obs_service is None:
            return

        try:
            method = request.method
            # Normalize endpoint path (remove query params, use path template if available)
            endpoint = request.url.path

            # Track the request
            self._obs_service.track_request(method, endpoint, status_code, duration_seconds)
        except Exception as e:
            # Don't let metrics tracking break the request
            logger.debug(f"Failed to track request metrics: {e}", exc_info=True)
