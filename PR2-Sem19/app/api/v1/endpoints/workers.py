"""Worker management endpoints for RunPod GPU workers."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.core.exceptions import TranscriptionError
from app.models.schemas import WorkerInfo
from app.services.jobs.queue_service import QueueService
from app.services.jobs.worker_manager import WorkerManager

logger = logging.getLogger(__name__)

router = APIRouter()


def get_worker_manager() -> WorkerManager:
    """Get worker manager instance.

    Creates a new WorkerManager instance. Since WorkerManager uses class-level storage
    (_workers), all instances share the same worker data.

    Returns:
        WorkerManager: Worker manager instance that shares class-level storage
            with other instances.
    """
    return WorkerManager()


def get_queue_service() -> QueueService:
    """Get queue service instance.

    Returns:
        QueueService: Queue service instance for managing job queues.
    """
    return QueueService()


@router.post(
    "/register",
    status_code=status.HTTP_200_OK,
    summary="Register Worker",
    description="""
    Register a new GPU worker with the API.

    Workers call this endpoint when they start up to register themselves
    with the API. The worker will be marked as warming up until it sends
    a heartbeat indicating the model is loaded.

    **Request Parameters**:
    - `worker_id` (query): Unique worker identifier
    - `runpod_pod_id` (query): RunPod pod ID for this worker
    - `gpu_type` (query): GPU type (e.g., "RTX 4090", "A100")

    **Response**:
    - 200 OK: Worker registered successfully
    """,
)
async def register_worker(
    worker_id: str = Query(..., description="Unique worker identifier"),
    runpod_pod_id: str = Query(..., description="RunPod pod ID"),
    gpu_type: str = Query(default="Unknown", description="GPU type"),
) -> dict:
    """Register a new GPU worker.

    Workers call this endpoint when they start up to register themselves
    with the API. The worker will be marked as warming up until it sends
    a heartbeat indicating the model is loaded.

    Args:
        worker_id: Unique worker identifier.
        runpod_pod_id: RunPod pod ID for this worker.
        gpu_type: GPU type (e.g., "RTX 4090", "A100").

    Returns:
        dict: Registration confirmation containing message, worker_id, and status.

    Raises:
        HTTPException: 400 if registration fails, 500 for unexpected errors.
    """
    try:
        manager = get_worker_manager()
        worker = manager.register_worker(worker_id, runpod_pod_id, gpu_type)
        logger.info(f"Worker {worker_id} registered successfully")
        return {
            "message": "Worker registered successfully",
            "worker_id": worker.worker_id,
            "status": worker.status.value,
        }
    except TranscriptionError as e:
        logger.error(f"Failed to register worker {worker_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error registering worker {worker_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register worker: {str(e)}",
        )


@router.post(
    "/{worker_id}/heartbeat",
    status_code=status.HTTP_200_OK,
    summary="Worker Heartbeat",
    description="""
    Update worker heartbeat.

    Workers call this endpoint periodically (every 30 seconds by default)
    to indicate they are alive and ready to accept jobs. The heartbeat also
    indicates whether the model is loaded.

    **Path Parameters**:
    - `worker_id` (path): Unique worker identifier

    **Query Parameters**:
    - `model_loaded` (query, bool): Whether the Whisper model is loaded and ready

    **Response**:
    - 200 OK: Heartbeat received successfully
    """,
)
async def worker_heartbeat(
    worker_id: str,
    model_loaded: bool = Query(default=True, description="Whether model is loaded"),
) -> dict:
    """Update worker heartbeat.

    Workers call this endpoint periodically (every 30 seconds by default)
    to indicate they are alive and ready to accept jobs. The heartbeat also
    indicates whether the model is loaded.

    Args:
        worker_id: Unique worker identifier.
        model_loaded: Whether the Whisper model is loaded and ready.

    Returns:
        dict: Heartbeat confirmation containing message, worker_id, and model_loaded status.

    Raises:
        HTTPException: 404 if worker not found, 400 if heartbeat fails,
            500 for unexpected errors.
    """
    try:
        manager = get_worker_manager()
        manager.heartbeat(worker_id, model_loaded)
        logger.debug(f"Heartbeat received from worker {worker_id} (model_loaded: {model_loaded})")
        return {
            "message": "Heartbeat received",
            "worker_id": worker_id,
            "model_loaded": model_loaded,
        }
    except TranscriptionError as e:
        logger.warning(f"Failed to update heartbeat for worker {worker_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error updating heartbeat for worker {worker_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update heartbeat: {str(e)}",
        )


@router.get(
    "",
    response_model=List[WorkerInfo],
    status_code=status.HTTP_200_OK,
    summary="List Workers",
    description="""
    Get list of all registered workers.

    Returns information about all GPU workers that are registered with
    the API, including their status, current job, and health information.

    **Response**:
    - List of WorkerInfo objects with worker details

    **Usage**:
    Use this endpoint to monitor worker status and health.
    """,
)
async def list_workers() -> List[WorkerInfo]:
    """List all registered workers.

    Returns information about all GPU workers that are registered with
    the API, including their status, current job, and health information.

    Returns:
        List[WorkerInfo]: List of all registered workers with their details.
    """
    manager = get_worker_manager()
    workers = manager.get_all_workers()
    logger.info(f"List workers requested: {len(workers)} workers found")
    return workers


@router.get(
    "/{worker_id}",
    response_model=WorkerInfo,
    status_code=status.HTTP_200_OK,
    summary="Get Worker Info",
    description="""
    Get information about a specific worker.

    **Path Parameters**:
    - `worker_id` (path): Unique worker identifier

    **Response**:
    - WorkerInfo object with worker details

    **Raises**:
    - 404: Worker not found
    """,
)
async def get_worker(worker_id: str) -> WorkerInfo:
    """Get information about a specific worker.

    Args:
        worker_id: Unique worker identifier.

    Returns:
        WorkerInfo: Worker information including status, current job, and health details.

    Raises:
        HTTPException: 404 if worker not found.
    """
    manager = get_worker_manager()
    worker = manager.get_worker(worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker not found: {worker_id}",
        )
    return worker


@router.post(
    "/scale",
    status_code=status.HTTP_200_OK,
    summary="Scale Workers",
    description="""
    Manually scale workers to a target count.

    Creates or terminates workers to reach the target count.
    Respects MIN_WORKERS and MAX_WORKERS limits.

    **Request Body** (JSON):
    - `target_count` (int, optional): Target number of workers. If not provided, uses auto-scaling based on queue depth.

    **Response**:
    - Current worker count after scaling

    **Usage**:
    Use this endpoint to manually start workers or scale to a specific count.
    """,
)
async def scale_workers(
    target_count: Optional[int] = Query(
        None, description="Target number of workers (optional, uses auto-scaling if not provided)"
    ),
) -> dict:
    """Manually scale workers to a target count.

    Creates or terminates workers to reach the target count.
    Respects MIN_WORKERS and MAX_WORKERS limits.

    Args:
        target_count: Target number of workers. If None, uses auto-scaling
            based on queue depth.

    Returns:
        dict: Scaling result with current worker count, message, and optionally
            target_count or queue_depth.

    Raises:
        HTTPException: 400 if scaling fails, 500 for unexpected errors.
    """
    try:
        manager = get_worker_manager()
        queue_service = get_queue_service()

        if target_count is not None:
            worker_count = await manager.scale_workers(target_count)
            return {
                "message": f"Scaled workers to {worker_count}",
                "worker_count": worker_count,
                "target_count": target_count,
            }
        else:
            stats = queue_service.get_queue_stats()
            queue_depth = stats.get("pending", 0)
            worker_count = await manager.auto_scale_workers(queue_depth)
            return {
                "message": "Auto-scaled workers based on queue depth",
                "worker_count": worker_count,
                "queue_depth": queue_depth,
            }
    except TranscriptionError as e:
        logger.error(f"Failed to scale workers: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error scaling workers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scale workers: {str(e)}",
        )


@router.get(
    "/test-connection",
    status_code=status.HTTP_200_OK,
    summary="Test RunPod Connection",
    description="""
    Test connection to RunPod API.

    Verifies that the RunPod API key and configuration are correct
    by making a test query to the RunPod GraphQL API.

    **Response**:
    - Connection test result with status and details

    **Usage**:
    Use this endpoint to verify RunPod configuration before deploying workers.
    """,
)
async def test_runpod_connection() -> dict:
    """Test connection to RunPod API.

    Verifies that the RunPod API key and configuration are correct
    by making a test query to the RunPod GraphQL API.

    Returns:
        dict: Connection test result containing:
            - connected (bool): Whether connection was successful
            - message (str): Status message
            - details (dict): Connection details including API key status,
              template ID status, API URL, user ID, and username
            - error (str, optional): Error message if connection failed

    Example:
        >>> {
        ...     "connected": true,
        ...     "message": "Successfully connected to Runpod API",
        ...     "details": {
        ...         "api_key_set": true,
        ...         "template_id_set": true,
        ...         "api_url": "https://api.runpod.io/graphql",
        ...         "user_id": "abc123",
        ...         "username": "user@example.com"
        ...     }
        ... }
    """
    manager = get_worker_manager()
    try:
        result = await manager.test_connection()
        return result
    except Exception as e:
        logger.error(f"Error testing RunPod connection: {e}")
        return {
            "connected": False,
            "error": f"Failed to test connection: {str(e)}",
            "details": {},
        }
    finally:
        await manager.close()
