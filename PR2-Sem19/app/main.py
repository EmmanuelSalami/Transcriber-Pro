"""FastAPI application main entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.auth import limiter
from app.core.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.middleware import MetricsMiddleware
from app.core.startup import (initialize_observability, log_dev_mode_warnings,
                              recover_orphaned_jobs,
                              shutdown_auto_scaling_task,
                              start_auto_scaling_task,
                              validate_runpod_configuration,
                              validate_startup_configuration)
from app.services.jobs.job_manager import JobManager
from app.services.transcription.whisper_service import WhisperService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager for FastAPI.

    Handles startup and shutdown events for the application lifecycle.
    Performs security checks and logging during startup, and cleanup during shutdown.

    Args:
        app: FastAPI application instance

    Yields:
        None: Control is yielded to the application runtime

    Example:
        This is automatically used by FastAPI when the app is created with
        `lifespan=lifespan` parameter. No manual invocation needed.
    """
    logger.info("Starting YouTube Transcription API...")
    logger.info(f"API Version: {settings.api_version}")

    # Startup sequence
    validate_startup_configuration()
    log_dev_mode_warnings()
    recover_orphaned_jobs()
    validate_runpod_configuration()
    initialize_observability()
    auto_scaling_task = await start_auto_scaling_task()

    yield

    # Shutdown sequence
    await shutdown_auto_scaling_task(auto_scaling_task)
    logger.info("Shutting down YouTube Transcription API...")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-User-Id"],
)

# Add metrics middleware for Prometheus tracking (if enabled)
if settings.observability_enabled and settings.metrics_enabled:
    app.add_middleware(MetricsMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

register_error_handlers(app)

app.include_router(api_router, prefix=f"/{settings.api_version}")


@app.get("/", tags=["health"])
async def root():
    """
    Root endpoint for API health check and information.

    Provides basic API metadata including name, version, and status.
    This endpoint does not require authentication.

    Returns:
        dict: Dictionary containing:
            - name (str): API title
            - version (str): API version
            - status (str): Current API status ("running")

    Example:
        >>> GET /
        {
            "name": "YouTube Transcription API",
            "version": "v1",
            "status": "running"
        }
    """
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "status": "running",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.

    Checks API health, model readiness status, and Redis connection pool health.
    This endpoint does not require authentication.

    Returns:
        dict: Dictionary containing:
            - status (str): Overall health status ("healthy" or "degraded")
            - api (str): API status ("running")
            - whisper (dict): Whisper model health status:
                - loaded (bool): Whether model is loaded
                - device (str): Compute device
                - ready (bool): Whether model is ready for requests
            - redis (dict, optional): Redis connection pool health:
                - connected (bool): Whether Redis is connected
                - pool_stats (dict): Connection pool statistics

    Example:
        >>> GET /health
        {
            "status": "healthy",
            "api": "running",
            "whisper": {
                "loaded": true,
                "device": "cpu",
                "ready": true
            },
            "redis": {
                "connected": true,
                "pool_stats": {
                    "created_connections": 5,
                    "available_connections": 45,
                    "max_connections": 50,
                    "usage_percent": 10.0
                }
            }
        }
    """
    whisper_service = WhisperService.get_instance()
    whisper_health = whisper_service.health_check()

    redis_health = None
    try:
        job_manager = JobManager()
        if job_manager._use_redis:
            if job_manager._redis_client:
                job_manager._redis_client.ping()
                pool_stats = job_manager.get_redis_pool_stats()
                redis_health = {
                    "connected": True,
                    "pool_stats": pool_stats,
                }
            else:
                redis_health = {"connected": False}
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        redis_health = {"connected": False, "error": str(e)}

    overall_status = "healthy" if whisper_health["ready"] else "degraded"

    response = {
        "status": overall_status,
        "api": "running",
        "whisper": whisper_health,
    }

    if redis_health:
        response["redis"] = redis_health

    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
