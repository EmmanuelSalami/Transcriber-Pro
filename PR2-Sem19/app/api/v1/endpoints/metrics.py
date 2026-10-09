"""Prometheus metrics endpoint for observability."""

import logging

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import settings
from app.core.middleware import get_observability_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="Prometheus Metrics",
    description="""
    Expose Prometheus metrics for monitoring and observability.
    
    This endpoint returns metrics in Prometheus text format, which can be
    scraped by Prometheus for monitoring. Metrics include:
    - API request counts and durations
    - Job processing metrics
    - Queue depth and worker status
    - Custom application metrics
    
    This endpoint does not require authentication and is intended for
    monitoring systems like Prometheus.
    
    Returns:
        Response: Prometheus metrics in text format (Content-Type: text/plain)
    
    Example:
        >>> GET /v1/metrics
        # HELP api_requests_total Total number of API requests
        # TYPE api_requests_total counter
        api_requests_total{endpoint="/v1/transcriptions/youtube",method="POST",status="200"} 42.0
        ...
    """,
    tags=["monitoring"],
)
async def get_metrics() -> Response:
    """Get Prometheus metrics.

    Returns metrics in Prometheus text format. If metrics are disabled
    in configuration, returns an empty response.

    Returns:
        Response: Prometheus metrics in text format (Content-Type: text/plain).
            Returns empty response if metrics are disabled in configuration.

    Raises:
        Response: 500 if error occurs while generating metrics (error message
            included in response body).
    """
    if not settings.metrics_enabled:
        logger.debug("Metrics endpoint called but metrics are disabled")
        return Response(
            content="# Metrics are disabled\n",
            media_type=CONTENT_TYPE_LATEST,
            status_code=status.HTTP_200_OK,
        )

    try:
        if settings.observability_enabled:
            get_observability_service()

        metrics_data = generate_latest()
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST,
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}", exc_info=True)
        return Response(
            content=f"# Error generating metrics: {str(e)}\n",
            media_type=CONTENT_TYPE_LATEST,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
