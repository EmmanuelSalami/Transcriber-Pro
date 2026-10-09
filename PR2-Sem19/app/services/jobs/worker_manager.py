"""Worker manager for Runpod GPU workers."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, cast

import httpx

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.models.schemas import WorkerInfo, WorkerStatus

logger = logging.getLogger(__name__)

# Lazy import for observability service
_observability_service = None


def _get_observability_service():
    """Get or create observability service instance.

    Returns:
        Optional[ObservabilityService]: Observability service instance if available,
            None otherwise.
    """
    global _observability_service
    if _observability_service is None:
        try:
            from app.services.infrastructure.observability_service import \
                ObservabilityService

            _observability_service = ObservabilityService()
        except Exception as e:
            logger.debug(f"Observability service not available: {e}")
            _observability_service = None
    return _observability_service


def _update_worker_metrics(worker_manager_instance):
    """Update worker count metrics.

    Args:
        worker_manager_instance: WorkerManager instance to get worker data from.
    """
    obs_service = _get_observability_service()
    if obs_service:
        try:
            status_counts = {}
            for worker in worker_manager_instance._workers.values():
                status = (
                    worker.status.value if hasattr(worker.status, "value") else str(worker.status)
                )
                status_counts[status] = status_counts.get(status, 0) + 1

            for status, count in status_counts.items():
                obs_service.update_worker_count(status, count)

            all_statuses = ["idle", "busy", "warming_up", "unhealthy"]
            for status in all_statuses:
                if status not in status_counts:
                    obs_service.update_worker_count(status, 0)
        except Exception as e:
            logger.debug(f"Failed to update worker metrics: {e}")


class WorkerManager:
    """
    Manager for Runpod GPU workers.

    Handles worker registration, health checks, scaling, and lifecycle management.
    Integrates with Runpod API to create, manage, and terminate GPU worker pods.

    Attributes:
        _workers (Dict[str, WorkerInfo]): Dictionary of registered workers keyed by worker_id
        _runpod_api_key (str): Runpod API key
        _runpod_template_id (str): Runpod template ID
        _runpod_api_url (str): Runpod GraphQL API URL
        _http_client (httpx.AsyncClient): HTTP client for Runpod API calls

    Example:
        >>> manager = WorkerManager()
        >>> worker = manager.register_worker("worker-123", "pod-abc", "RTX 4090")
        >>> available = manager.get_available_workers()
        >>> manager.scale_workers(target_count=3)
    """

    def __init__(self) -> None:
        """
        Initialize the worker manager.

        Sets up HTTP client for Runpod API and validates configuration.

        Raises:
            TranscriptionError: If Runpod configuration is invalid
        """
        self._workers: Dict[str, WorkerInfo] = {}
        self._runpod_api_key = settings.runpod_api_key
        self._runpod_template_id = settings.runpod_template_id
        self._runpod_api_url = settings.runpod_api_url
        self._http_client: Optional[httpx.AsyncClient] = None

        # Validate configuration
        if not self._runpod_api_key:
            logger.warning(
                "Runpod API key not configured. Worker management will be limited. "
                "Set RUNPOD_API_KEY environment variable."
            )

        if not self._runpod_template_id:
            logger.warning(
                "Runpod template ID not configured. Worker creation will fail. "
                "Set RUNPOD_TEMPLATE_ID environment variable."
            )

        # Create HTTP client for Runpod API
        if self._runpod_api_key:
            self._http_client = httpx.AsyncClient(
                base_url=self._runpod_api_url,
                headers={"Authorization": f"Bearer {self._runpod_api_key}"},
                timeout=30.0,
            )
            logger.info("WorkerManager initialized with Runpod API client")

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()

    async def test_connection(self) -> dict:
        """
        Test connection to Runpod API.

        Performs a simple GraphQL query to verify the API key and connection
        are working correctly.

        Returns:
            dict: Connection test result with status and details

        Example:
            >>> manager = WorkerManager()
            >>> result = await manager.test_connection()
            >>> result["connected"]
            True
        """
        if not self._runpod_api_key:
            return {
                "connected": False,
                "error": "Runpod API key not configured",
                "details": {
                    "api_key_set": False,
                    "template_id_set": bool(self._runpod_template_id),
                    "api_url": self._runpod_api_url,
                },
            }

        if not self._http_client:
            return {
                "connected": False,
                "error": "HTTP client not initialized",
                "details": {
                    "api_key_set": True,
                    "template_id_set": bool(self._runpod_template_id),
                    "api_url": self._runpod_api_url,
                },
            }

        # Simple GraphQL query to test connection
        # Query for user info - a lightweight test query
        query = """
        query {
            myself {
                id
                username
            }
        }
        """

        try:
            response = await self._http_client.post(
                "",
                json={"query": query},
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                return {
                    "connected": False,
                    "error": f"Runpod API returned error: {error_msg}",
                    "details": {
                        "api_key_set": True,
                        "template_id_set": bool(self._runpod_template_id),
                        "api_url": self._runpod_api_url,
                        "response_status": response.status_code,
                        "errors": data["errors"],
                    },
                }

            # Check if we got valid user data
            user_data = data.get("data", {}).get("myself")
            if user_data:
                return {
                    "connected": True,
                    "message": "Successfully connected to Runpod API",
                    "details": {
                        "api_key_set": True,
                        "template_id_set": bool(self._runpod_template_id),
                        "api_url": self._runpod_api_url,
                        "user_id": user_data.get("id"),
                        "username": user_data.get("username"),
                    },
                }
            else:
                return {
                    "connected": False,
                    "error": "Runpod API returned unexpected response",
                    "details": {
                        "api_key_set": True,
                        "template_id_set": bool(self._runpod_template_id),
                        "api_url": self._runpod_api_url,
                        "response": data,
                    },
                }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error testing Runpod connection: {e}")
            return {
                "connected": False,
                "error": f"Failed to connect to Runpod API: {str(e)}",
                "details": {
                    "api_key_set": True,
                    "template_id_set": bool(self._runpod_template_id),
                    "api_url": self._runpod_api_url,
                    "error_type": type(e).__name__,
                },
            }
        except Exception as e:
            logger.error(f"Unexpected error testing Runpod connection: {e}")
            return {
                "connected": False,
                "error": f"Unexpected error: {str(e)}",
                "details": {
                    "api_key_set": True,
                    "template_id_set": bool(self._runpod_template_id),
                    "api_url": self._runpod_api_url,
                    "error_type": type(e).__name__,
                },
            }

    def register_worker(
        self, worker_id: str, runpod_pod_id: str, gpu_type: str = "Unknown"
    ) -> WorkerInfo:
        """
        Register a new worker.

        Registers a worker that has started up and is ready to accept jobs.
        Workers call this method when they start up to register themselves.

        Args:
            worker_id: Unique worker identifier.
            runpod_pod_id: Runpod pod ID for this worker.
            gpu_type: GPU type (e.g., "RTX 4090", "A100"). Default: "Unknown".

        Returns:
            WorkerInfo: Worker information object.

        Example:
            >>> manager = WorkerManager()
            >>> worker = manager.register_worker("worker-123", "pod-abc", "RTX 4090")
            >>> worker.status
            <WorkerStatus.WARMING_UP: 'warming_up'>
        """
        worker_info = WorkerInfo(
            worker_id=worker_id,
            status=WorkerStatus.WARMING_UP,
            runpod_pod_id=runpod_pod_id,
            gpu_type=gpu_type,
            current_job_id=None,
            last_heartbeat=datetime.now(timezone.utc).isoformat(),
            model_loaded=False,
            jobs_processed=0,
            total_gpu_hours=0.0,
        )

        self._workers[worker_id] = worker_info

        # Update worker metrics
        _update_worker_metrics(self)

        logger.info(f"Registered worker {worker_id} (pod: {runpod_pod_id}, GPU: {gpu_type})")
        return worker_info

    def heartbeat(self, worker_id: str, model_loaded: bool = True) -> None:
        """
        Update worker heartbeat.

        Workers call this method periodically to indicate they are alive.
        Updates the last heartbeat timestamp and model loaded status.

        Args:
            worker_id: Unique worker identifier.
            model_loaded: Whether the model is loaded and ready. Default: True.

        Raises:
            TranscriptionError: If worker is not registered.

        Example:
            >>> manager = WorkerManager()
            >>> manager.heartbeat("worker-123", model_loaded=True)
        """
        if worker_id not in self._workers:
            raise TranscriptionError(
                f"Worker {worker_id} is not registered",
                code="WORKER_ERROR",
                details={"worker_id": worker_id},
            )

        worker = self._workers[worker_id]
        worker.last_heartbeat = datetime.now(timezone.utc).isoformat()
        worker.model_loaded = model_loaded

        if worker.current_job_id:
            worker.status = WorkerStatus.BUSY
        elif model_loaded:
            worker.status = WorkerStatus.IDLE
        else:
            worker.status = WorkerStatus.WARMING_UP

        _update_worker_metrics(self)

        logger.debug(f"Worker {worker_id} heartbeat updated (model_loaded: {model_loaded})")

    def assign_job(self, worker_id: str, job_id: str) -> None:
        """
        Assign a job to a worker.

        Marks a worker as busy and assigns a job to it.

        Args:
            worker_id: Unique worker identifier.
            job_id: Job identifier to assign.

        Raises:
            TranscriptionError: If worker is not registered or not available.

        Example:
            >>> manager = WorkerManager()
            >>> manager.assign_job("worker-123", "job-456")
        """
        if worker_id not in self._workers:
            raise TranscriptionError(
                f"Worker {worker_id} is not registered",
                code="WORKER_ERROR",
                details={"worker_id": worker_id},
            )

        worker = self._workers[worker_id]
        if worker.status != WorkerStatus.IDLE:
            raise TranscriptionError(
                f"Worker {worker_id} is not idle (status: {worker.status.value})",
                code="WORKER_ERROR",
                details={"worker_id": worker_id, "status": worker.status.value},
            )

        worker.current_job_id = job_id
        worker.status = WorkerStatus.BUSY

        _update_worker_metrics(self)

        logger.info(f"Assigned job {job_id} to worker {worker_id}")

    def complete_job(self, worker_id: str, job_id: str, processing_time_seconds: float) -> None:
        """
        Mark a job as completed by a worker.

        Updates worker statistics and marks worker as idle.

        Args:
            worker_id: Unique worker identifier.
            job_id: Job identifier that was completed.
            processing_time_seconds: Time taken to process the job in seconds.

        Raises:
            TranscriptionError: If worker is not registered or job doesn't match.

        Example:
            >>> manager = WorkerManager()
            >>> manager.complete_job("worker-123", "job-456", 120.5)
        """
        if worker_id not in self._workers:
            raise TranscriptionError(
                f"Worker {worker_id} is not registered",
                code="WORKER_ERROR",
                details={"worker_id": worker_id},
            )

        worker = self._workers[worker_id]
        if worker.current_job_id != job_id:
            logger.warning(
                f"Job {job_id} completion doesn't match worker's current job {worker.current_job_id}"
            )

        worker.current_job_id = None
        worker.status = WorkerStatus.IDLE
        worker.jobs_processed += 1
        worker.total_gpu_hours += processing_time_seconds / 3600.0

        _update_worker_metrics(self)

        logger.info(
            f"Worker {worker_id} completed job {job_id} "
            f"(processing time: {processing_time_seconds:.2f}s, "
            f"total jobs: {worker.jobs_processed})"
        )

    def get_available_workers(self) -> List[WorkerInfo]:
        """
        Get list of available (idle) workers.

        Returns workers that are idle and ready to accept jobs.

        Returns:
            List[WorkerInfo]: List of available worker information objects

        Example:
            >>> manager = WorkerManager()
            >>> available = manager.get_available_workers()
            >>> len(available)
            3
        """
        return [
            worker
            for worker in self._workers.values()
            if worker.status == WorkerStatus.IDLE and worker.model_loaded
        ]

    def get_all_workers(self) -> List[WorkerInfo]:
        """
        Get list of all registered workers.

        Returns:
            List[WorkerInfo]: List of all worker information objects

        Example:
            >>> manager = WorkerManager()
            >>> all_workers = manager.get_all_workers()
        """
        return list(self._workers.values())

    def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """
        Get worker information by ID.

        Args:
            worker_id: Unique worker identifier.

        Returns:
            Optional[WorkerInfo]: Worker information if found, None otherwise.

        Example:
            >>> manager = WorkerManager()
            >>> worker = manager.get_worker("worker-123")
        """
        return self._workers.get(worker_id)

    async def health_check_workers(self) -> Dict[str, bool]:
        """
        Perform health check on all workers.

        Checks if workers have sent heartbeats recently. Marks workers as
        unhealthy if they haven't sent a heartbeat within the timeout period.

        Returns:
            Dict[str, bool]: Dictionary mapping worker_id to health status (True = healthy)

        Example:
            >>> manager = WorkerManager()
            >>> health = await manager.health_check_workers()
            >>> all_healthy = all(health.values())
        """
        health_status: Dict[str, bool] = {}
        timeout_seconds = settings.worker_health_check_timeout_seconds
        current_time = datetime.now(timezone.utc)

        for worker_id, worker in self._workers.items():
            try:
                last_heartbeat = datetime.fromisoformat(
                    worker.last_heartbeat.replace("Z", "+00:00")
                )
                time_since_heartbeat = (current_time - last_heartbeat).total_seconds()

                if time_since_heartbeat > timeout_seconds:
                    worker.status = WorkerStatus.UNHEALTHY
                    health_status[worker_id] = False
                    logger.warning(
                        f"Worker {worker_id} is unhealthy "
                        f"(no heartbeat for {time_since_heartbeat:.0f}s)"
                    )
                else:
                    health_status[worker_id] = True
            except Exception as e:
                logger.error(f"Error checking health for worker {worker_id}: {e}")
                worker.status = WorkerStatus.UNHEALTHY
                health_status[worker_id] = False

        return health_status

    async def scale_workers(self, target_count: int) -> int:
        """
        Scale workers to target count.

        Creates or terminates workers to reach the target count. Respects
        min_workers and max_workers limits.

        Args:
            target_count: Target number of workers.

        Returns:
            int: Number of workers after scaling.

        Raises:
            TranscriptionError: If scaling fails.

        Example:
            >>> manager = WorkerManager()
            >>> current_count = await manager.scale_workers(target_count=5)
            >>> print(f"Scaled to {current_count} workers")
        """
        # Enforce limits
        target_count = max(settings.min_workers, min(target_count, settings.max_workers))

        healthy_count = sum(1 for w in self._workers.values() if w.status != WorkerStatus.UNHEALTHY)

        if target_count > healthy_count:
            needed = target_count - healthy_count
            logger.info(f"Scaling up: need {needed} more workers (current: {healthy_count})")
            for _ in range(needed):
                try:
                    await self._create_worker()
                except Exception as e:
                    logger.error(f"Failed to create worker: {e}")
                    break

        elif target_count < healthy_count:
            excess = healthy_count - target_count
            logger.info(f"Scaling down: removing {excess} workers (current: {healthy_count})")
            idle_workers = [
                w
                for w in self._workers.values()
                if w.status == WorkerStatus.IDLE and w.current_job_id is None
            ]
            for worker in idle_workers[:excess]:
                try:
                    await self._terminate_worker(worker.worker_id)
                except Exception as e:
                    logger.error(f"Failed to terminate worker {worker.worker_id}: {e}")

        return len([w for w in self._workers.values() if w.status != WorkerStatus.UNHEALTHY])

    async def auto_scale_workers(self, queue_depth: int) -> int:
        """
        Automatically scale workers based on queue depth.

        Implements auto-scaling strategy:
        - Queue depth > scale_up_threshold → Add worker (up to max_workers)
        - Queue depth < scale_down_threshold AND worker idle > idle_timeout → Remove worker

        Args:
            queue_depth: Current queue depth (pending jobs).

        Returns:
            int: Number of workers after auto-scaling.

        Example:
            >>> manager = WorkerManager()
            >>> current_count = await manager.auto_scale_workers(queue_depth=15)
            >>> print(f"Auto-scaled to {current_count} workers")
        """
        if not settings.worker_auto_scaling_enabled:
            return len([w for w in self._workers.values() if w.status != WorkerStatus.UNHEALTHY])

        healthy_workers = [w for w in self._workers.values() if w.status != WorkerStatus.UNHEALTHY]
        healthy_count = len(healthy_workers)
        idle_workers = [
            w for w in healthy_workers if w.status == WorkerStatus.IDLE and w.current_job_id is None
        ]

        if queue_depth > settings.worker_scale_up_queue_depth:
            if healthy_count < settings.max_workers:
                target_count = min(healthy_count + 1, settings.max_workers)
                logger.info(
                    f"Auto-scaling UP: queue_depth={queue_depth} > threshold={settings.worker_scale_up_queue_depth}, "
                    f"scaling to {target_count} workers"
                )
                return await self.scale_workers(target_count)

        elif queue_depth < settings.worker_scale_down_queue_depth:
            if healthy_count > settings.min_workers and idle_workers:
                from datetime import datetime, timezone

                current_time = datetime.now(timezone.utc)
                idle_timeout_seconds = settings.worker_idle_timeout_seconds

                workers_to_remove = []
                for worker in idle_workers:
                    try:
                        last_heartbeat = datetime.fromisoformat(
                            worker.last_heartbeat.replace("Z", "+00:00")
                        )
                        idle_seconds = (current_time - last_heartbeat).total_seconds()

                        if idle_seconds >= idle_timeout_seconds:
                            workers_to_remove.append(worker)
                    except Exception as e:
                        logger.warning(
                            f"Error checking idle time for worker {worker.worker_id}: {e}"
                        )

                if workers_to_remove:
                    # Remove one worker at a time
                    worker_to_remove = workers_to_remove[0]
                    target_count = max(healthy_count - 1, settings.min_workers)
                    logger.info(
                        f"Auto-scaling DOWN: queue_depth={queue_depth} < threshold={settings.worker_scale_down_queue_depth}, "
                        f"worker {worker_to_remove.worker_id} idle > {idle_timeout_seconds}s, "
                        f"scaling to {target_count} workers"
                    )
                    try:
                        await self._terminate_worker(worker_to_remove.worker_id)
                    except Exception as e:
                        logger.error(
                            f"Failed to terminate worker {worker_to_remove.worker_id}: {e}"
                        )

        return len([w for w in self._workers.values() if w.status != WorkerStatus.UNHEALTHY])

    async def _create_worker(self) -> str:
        """
        Create a new Runpod worker pod.

        Private method to create a worker pod via Runpod API.

        Returns:
            str: Runpod pod ID of the created worker.

        Raises:
            TranscriptionError: If worker creation fails.
        """
        if not self._http_client or not self._runpod_template_id:
            raise TranscriptionError(
                "Runpod API client or template ID not configured",
                code="WORKER_ERROR",
                details={"template_id": self._runpod_template_id},
            )

        mutation = """
        mutation {
            podFindAndDeploy(
                input: {
                    templateId: "%s"
                    cloudType: ALL
                    gpuCount: 1
                }
            ) {
                id
                name
                imageName
                env
                machineId
                machine {
                    podHostId
                }
            }
        }
        """ % (self._runpod_template_id)

        try:
            response = await self._http_client.post(
                "",
                json={"query": mutation},
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                raise TranscriptionError(
                    f"Failed to create Runpod worker: {error_msg}",
                    code="WORKER_ERROR",
                    details={"errors": data["errors"]},
                )

            pod_id = data.get("data", {}).get("podFindAndDeploy", {}).get("id")
            if not pod_id:
                raise TranscriptionError(
                    "Runpod API returned no pod ID",
                    code="WORKER_ERROR",
                    details={"response": data},
                )

            logger.info(f"Created Runpod worker pod: {pod_id}")
            return cast(str, pod_id)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error creating Runpod worker: {e}")
            raise TranscriptionError(
                f"Failed to create Runpod worker: {str(e)}",
                code="WORKER_ERROR",
                details={"error": str(e)},
            )

    async def _terminate_worker(self, worker_id: str) -> None:
        """
        Terminate a Runpod worker pod.

        Private method to terminate a worker pod via Runpod API.

        Args:
            worker_id: Worker identifier.

        Raises:
            TranscriptionError: If worker termination fails.
        """
        worker = self._workers.get(worker_id)
        if not worker:
            logger.warning(f"Worker {worker_id} not found for termination")
            return

        if not self._http_client:
            raise TranscriptionError(
                "Runpod API client not configured",
                code="WORKER_ERROR",
            )

        mutation = """
        mutation {
            podTerminate(input: { podId: "%s" }) {
                id
            }
        }
        """ % (worker.runpod_pod_id)

        try:
            response = await self._http_client.post(
                "",
                json={"query": mutation},
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                logger.warning(f"Failed to terminate Runpod worker {worker_id}: {error_msg}")
            else:
                del self._workers[worker_id]
                _update_worker_metrics(self)
                logger.info(f"Terminated Runpod worker {worker_id} (pod: {worker.runpod_pod_id})")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error terminating Runpod worker {worker_id}: {e}")
            if worker_id in self._workers:
                del self._workers[worker_id]
                _update_worker_metrics(self)
