"""Application startup and shutdown logic."""

import asyncio
import logging

from app.core.config import Settings, settings
from app.core.middleware import get_observability_service
from app.services.jobs.job_manager import JobManager
from app.services.jobs.queue_service import QueueService
from app.services.jobs.worker_manager import WorkerManager
from app.services.transcription.whisper_service import WhisperService

logger = logging.getLogger(__name__)


def validate_startup_configuration() -> None:
    """
    Validate production configuration settings at application startup.

    Checks that required production settings (API keys, CORS configuration)
    are properly configured. In production mode, raises ValueError if validation
    fails. In development mode, logs warnings but does not raise.

    Returns:
        None: Function completes successfully if validation passes

    Raises:
        ValueError: If production mode is detected but required settings are missing

    Example:
        Called during application startup:
        ```python
        @app.on_event("startup")
        async def startup():
            validate_startup_configuration()
        ```
    """
    # Always call validate_production_settings (it will skip validation in dev mode internally)
    # Use Settings class directly to allow class-level patching in tests
    try:
        Settings.validate_production_settings(settings)
    except ValueError as e:
        if Settings.is_production(settings):
            logger.error(f"Production configuration validation failed: {e}")
            raise
        # In dev mode, validate_production_settings may still raise, but we just log a warning
        logger.warning(f"Configuration warning (dev mode): {e}")


def log_dev_mode_warnings() -> None:
    """
    Log warnings for development mode configuration issues.

    Checks for insecure configuration in development mode:
    - Missing API keys (allows all requests)
    - CORS set to allow all origins

    Returns:
        None: Logs warnings but does not raise exceptions

    Note:
        This function only logs warnings and does not prevent application startup.
        It is intended to alert developers about insecure configurations.
    """
    if not settings.is_production():
        if not settings.get_api_keys():
            logger.warning(
                "DEV MODE: No API keys configured - allowing all requests (INSECURE). "
                "This should only be used for local development!"
            )
        cors_origins = settings.get_cors_origins()
        if cors_origins == ["*"] or (len(cors_origins) == 1 and cors_origins[0] == "*"):
            logger.warning(
                "DEV MODE: CORS is set to allow all origins (*). "
                "This is not recommended for production!"
            )


def recover_orphaned_jobs() -> None:
    """
    Recover orphaned jobs from previous application run.

    Finds jobs that were in progress when the application was shut down
    and marks them as failed. This prevents jobs from being stuck in
    "processing" state indefinitely.

    Returns:
        None: Logs recovery results but does not return a value

    Note:
        Errors during recovery are logged but do not prevent application startup.
        Orphaned jobs are marked as failed to allow cleanup.
    """
    logger.info("Recovering orphaned jobs from previous run...")
    try:
        job_manager = JobManager()
        recovered_count = job_manager.recover_orphaned_jobs()
        if recovered_count > 0:
            logger.info(f"✓ Recovered {recovered_count} orphaned job(s) (marked as failed)")
        else:
            logger.debug("✓ No orphaned jobs to recover")
    except Exception as e:
        logger.error(
            f"✗ Failed to recover orphaned jobs: {type(e).__name__} - {str(e)}",
            exc_info=True,
        )


def validate_runpod_configuration() -> None:
    """
    Validate Runpod API configuration at startup.

    Checks that Runpod API key and endpoint ID are configured for
    external ASR transcription. Logs status but does not prevent startup.

    Returns:
        None: Logs configuration status

    Note:
        Configuration errors are logged but do not prevent application startup.
        The service will fail gracefully on first transcription request if
        Runpod is not properly configured.
    """
    logger.info("Validating Runpod ASR configuration...")
    try:
        whisper_service = WhisperService()
        if whisper_service._api_key and whisper_service._endpoint_id:
            logger.info("✓ Runpod ASR configured successfully")
            logger.info(f"  - Endpoint ID: {whisper_service._endpoint_id}")
        else:
            logger.warning(
                "⚠ Runpod ASR not fully configured. "
                "Set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID environment variables."
            )
    except Exception as e:
        logger.error(
            f"✗ Error validating Runpod configuration: {type(e).__name__} - {str(e)}.",
            exc_info=True,
        )


def initialize_observability() -> None:
    """
    Initialize observability service to ensure metrics are registered.

    Creates the ObservabilityService singleton instance at startup to
    ensure Prometheus metrics are registered before the first request.
    Only initializes if observability is enabled in settings.

    Returns:
        None: Logs initialization results but does not return a value

    Note:
        Errors during initialization are logged but do not prevent application
        startup. Metrics may not be available if initialization fails.
    """
    if settings.observability_enabled and settings.metrics_enabled:
        try:
            get_observability_service()
            logger.info("✓ ObservabilityService initialized - metrics are ready")
        except Exception as e:
            logger.error(
                f"✗ Failed to initialize ObservabilityService: {type(e).__name__} - {str(e)}",
                exc_info=True,
            )


async def _auto_scaling_loop() -> None:
    """
    Background task for automatic worker scaling based on queue depth.

    Periodically checks queue depth and scales workers up or down based on
    configured thresholds. Runs continuously in the background during application
    lifetime until cancelled.

    The loop:
    - Sleeps for the configured interval between checks
    - Gets current queue depth from QueueService
    - Calls WorkerManager.auto_scale_workers() to adjust worker count
    - Handles errors gracefully without stopping the loop

    Returns:
        None: Runs indefinitely until cancelled

    Raises:
        asyncio.CancelledError: When the task is cancelled during shutdown
            (this is expected and handled gracefully)

    Note:
        This is an internal function that should be started via
        start_auto_scaling_task() which handles configuration checks.
    """
    logger.info("Worker auto-scaling loop started")
    worker_manager = WorkerManager()
    interval = settings.worker_auto_scaling_interval_seconds

    while True:
        try:
            await asyncio.sleep(interval)

            # Get queue depth
            try:
                queue_service = QueueService()
                stats = queue_service.get_queue_stats()
                queue_depth = stats.get("pending", 0)
            except Exception as e:
                logger.warning(f"Failed to get queue stats for auto-scaling: {e}")
                continue

            # Perform auto-scaling
            try:
                worker_count = await worker_manager.auto_scale_workers(queue_depth)
                logger.debug(
                    f"Auto-scaling check: queue_depth={queue_depth}, " f"workers={worker_count}"
                )
            except Exception as e:
                logger.error(f"Error during auto-scaling: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Worker auto-scaling loop cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in auto-scaling loop: {e}", exc_info=True)
            await asyncio.sleep(interval)  # Wait before retrying


async def start_auto_scaling_task() -> asyncio.Task | None:
    """
    Start auto-scaling background task if enabled and configured.

    Checks if auto-scaling is enabled and RunPod credentials are configured.
    If both conditions are met, starts the background auto-scaling loop.
    Otherwise, logs a message and returns None.

    Returns:
        asyncio.Task | None: The auto-scaling task if started successfully,
            None if auto-scaling is disabled or RunPod is not configured

    Example:
        Called during application startup:
        ```python
        @app.on_event("startup")
        async def startup():
            auto_scaling_task = await start_auto_scaling_task()
        ```
    """
    if not settings.worker_auto_scaling_enabled:
        return None

    if settings.runpod_api_key and settings.runpod_template_id:
        logger.info("Starting worker auto-scaling background task...")
        return asyncio.create_task(_auto_scaling_loop())
    else:
        logger.info(
            "Worker auto-scaling is enabled but RunPod is not configured. "
            "Auto-scaling disabled. Set RUNPOD_API_KEY and RUNPOD_TEMPLATE_ID to enable."
        )
        return None


async def shutdown_auto_scaling_task(auto_scaling_task: asyncio.Task | None) -> None:
    """
    Cancel and await auto-scaling background task shutdown.

    Gracefully cancels the auto-scaling background task and waits for it
    to complete cancellation. Handles CancelledError exceptions that are
    expected during task cancellation.

    Args:
        auto_scaling_task (asyncio.Task | None): The auto-scaling task to cancel,
            or None if no task was started

    Returns:
        None: Completes when the task has been cancelled and cleaned up

    Example:
        Called during application shutdown:
        ```python
        @app.on_event("shutdown")
        async def shutdown():
            await shutdown_auto_scaling_task(auto_scaling_task)
        ```
    """
    if auto_scaling_task:
        logger.info("Stopping worker auto-scaling background task...")
        auto_scaling_task.cancel()
        try:
            await auto_scaling_task
        except asyncio.CancelledError:
            pass


# Backward compatibility alias for tests
def preload_whisper_model() -> None:
    """Backward compatibility alias for validate_runpod_configuration()."""
    return validate_runpod_configuration()
