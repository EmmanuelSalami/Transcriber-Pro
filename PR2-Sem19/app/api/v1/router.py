"""API v1 router configuration.

This module configures the main API router for version 1 of the transcription API.
It aggregates all endpoint routers and sets up routing prefixes and tags for
OpenAPI documentation.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import credits, jobs, media, metrics, workers, youtube

api_router = APIRouter()
"""Main API router for v1 endpoints.

This router aggregates all v1 endpoint routers with appropriate prefixes and tags.
All routes are registered under this router and exposed through the main application.
"""

api_router.include_router(
    youtube.router,
    prefix="/transcriptions",
    tags=["transcriptions"],
)
api_router.include_router(
    media.router,
    prefix="/transcriptions",
    tags=["transcriptions"],
)
api_router.include_router(
    credits.router,
    prefix="",
    tags=["credits"],
)
api_router.include_router(
    jobs.router,
    prefix="/jobs",
    tags=["jobs"],
)
api_router.include_router(
    metrics.router,
    tags=["monitoring"],
)
api_router.include_router(
    workers.router,
    prefix="/workers",
    tags=["workers"],
)
