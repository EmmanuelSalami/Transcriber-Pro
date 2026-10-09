"""Queue service for managing transcription jobs with Redis Queue or SQS."""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, cast

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.models.schemas import EnhancedJobData, JobPriority

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


def _update_queue_depth_metric(queue_service_instance):
    """Update queue depth metric.

    Args:
        queue_service_instance: QueueService instance to get stats from.
    """
    obs_service = _get_observability_service()
    if obs_service:
        try:
            stats = queue_service_instance.get_queue_stats()
            depth = stats.get("pending", 0)
            obs_service.update_queue_depth(depth)
        except Exception as e:
            logger.debug(f"Failed to update queue depth metric: {e}")


class QueueService:
    """
    Queue service for managing transcription jobs with Redis Queue.

    Provides a unified interface for enqueueing, dequeuing, and managing jobs
    in a distributed queue system. Supports job prioritization, retries, and
    dead letter queue for failed jobs.

    Attributes:
        _redis_client (Optional[redis.Redis]): Redis client for queue operations
        _queue_name (str): Name of the queue
        _dead_letter_queue_name (str): Name of the dead letter queue
        _use_redis (bool): Whether Redis is available

    Example:
        >>> queue = QueueService()
        >>> job_data = EnhancedJobData(job_id="job-123", priority=JobPriority.NORMAL)
        >>> queue.enqueue_job(job_data, JobPriority.NORMAL)
        'job-123'
        >>> dequeued = queue.dequeue_job("worker-456")
        >>> dequeued.job_id
        'job-123'
    """

    def __init__(self) -> None:
        """
        Initialize the queue service.

        Connects to Redis and sets up queue names. Falls back gracefully
        if Redis is unavailable (logs warning but doesn't raise exception).

        Raises:
            TranscriptionError: If queue backend is not supported or Redis connection fails critically
        """
        self._queue_name = f"queue:{settings.queue_name}"
        self._dead_letter_queue_name = f"queue:{settings.queue_name}:dlq"
        self._processing_queue_name = f"queue:{settings.queue_name}:processing"
        self._use_redis = False
        self._redis_client: Optional[redis.Redis] = None

        if settings.queue_backend == "redis":
            try:
                from redis.connection import ConnectionPool

                # Check if redis_url is provided (Upstash format)
                if settings.redis_url:
                    # Parse redis_url like rediss://default:password@host:port
                    import urllib.parse
                    parsed = urllib.parse.urlparse(settings.redis_url)
                    redis_host = parsed.hostname or settings.redis_host
                    redis_port = parsed.port or settings.redis_port
                    redis_password = parsed.password
                    # Use SSL for rediss:// URLs
                    ssl = parsed.scheme == 'rediss'
                    
                    pool = ConnectionPool(
                        host=redis_host,
                        port=redis_port,
                        password=redis_password,
                        socket_timeout=settings.redis_socket_timeout,
                        socket_connect_timeout=settings.redis_socket_connect_timeout,
                        max_connections=settings.redis_pool_max_connections,
                        decode_responses=True,
                        connection_class=redis.SSLConnection if ssl else redis.Connection,
                    )
                    logger.info(f"QueueService using Redis URL connection (host={redis_host}:{redis_port}, ssl={ssl})")
                else:
                    # Use individual config values
                    redis_password = None
                    if settings.redis_password:
                        password_stripped = settings.redis_password.strip()
                        redis_password = password_stripped if password_stripped else None

                    pool = ConnectionPool(
                        host=settings.redis_host,
                        port=settings.redis_port,
                        db=settings.redis_db,
                        password=redis_password,
                        socket_timeout=settings.redis_socket_timeout,
                        socket_connect_timeout=settings.redis_socket_connect_timeout,
                        max_connections=settings.redis_pool_max_connections,
                        decode_responses=True,
                    )
                self._redis_client = redis.Redis(connection_pool=pool)
                self._redis_client.ping()
                self._use_redis = True
                logger.info(
                    f"QueueService initialized with Redis Queue "
                    f"(host={settings.redis_host}:{settings.redis_port}, queue={self._queue_name})"
                )
            except (RedisConnectionError, RedisError, Exception) as e:
                logger.error(
                    f"Failed to connect to Redis for queue service: {e}. "
                    "Queue operations will fail. Please check Redis configuration."
                )
                self._redis_client = None
                self._use_redis = False
                raise TranscriptionError(
                    f"Queue service requires Redis connection: {str(e)}",
                    code="QUEUE_ERROR",
                    details={"error": str(e)},
                )
        elif settings.queue_backend == "sqs":
            # TODO: Implement SQS backend
            raise TranscriptionError(
                "SQS backend not yet implemented. Please use 'redis' backend.",
                code="QUEUE_ERROR",
                details={"backend": settings.queue_backend},
            )
        else:
            raise TranscriptionError(
                f"Unsupported queue backend: {settings.queue_backend}. "
                "Supported backends: 'redis', 'sqs'",
                code="QUEUE_ERROR",
                details={"backend": settings.queue_backend},
            )

    def enqueue_job(
        self, job_data: EnhancedJobData, priority: JobPriority = JobPriority.NORMAL
    ) -> str:
        """
        Enqueue a job in the processing queue.

        Adds a job to the queue with the specified priority. Higher priority
        jobs are processed before lower priority jobs.

        Args:
            job_data: Enhanced job data with all metadata.
            priority: Job priority (low, normal, high). Default: NORMAL.

        Returns:
            str: Job ID that was enqueued.

        Raises:
            TranscriptionError: If queue operation fails.

        Example:
            >>> queue = QueueService()
            >>> job_data = EnhancedJobData(job_id="job-123", priority=JobPriority.HIGH)
            >>> queue.enqueue_job(job_data, JobPriority.HIGH)
            'job-123'
        """
        if not self._use_redis or not self._redis_client:
            raise TranscriptionError(
                "Queue service not available: Redis connection failed",
                code="QUEUE_ERROR",
                details={"queue_name": self._queue_name},
            )

        try:
            job_data.priority = priority

            job_json = job_data.model_dump_json()

            priority_score = {"low": 0, "normal": 1, "high": 2}.get(priority.value, 1)
            timestamp = time.time()
            score = priority_score * 1000000 + timestamp

            self._redis_client.zadd(self._queue_name, {job_data.job_id: score})

            job_hash_key = f"queue:job:{job_data.job_id}"
            self._redis_client.setex(
                job_hash_key, settings.queue_visibility_timeout_seconds * 2, job_json
            )

            logger.info(
                f"Enqueued job {job_data.job_id} with priority {priority.value} "
                f"(queue: {self._queue_name})"
            )

            _update_queue_depth_metric(self)

            return job_data.job_id

        except RedisError as e:
            logger.error(f"Failed to enqueue job {job_data.job_id}: {e}")
            raise TranscriptionError(
                f"Failed to enqueue job: {str(e)}",
                code="QUEUE_ERROR",
                details={"job_id": job_data.job_id, "error": str(e)},
            )

    def dequeue_job(self, worker_id: str) -> Optional[EnhancedJobData]:
        """
        Dequeue a job from the queue for processing.

        Retrieves the highest priority job from the queue and moves it to
        the processing queue. Returns None if no jobs are available.

        Args:
            worker_id: ID of the worker requesting a job.

        Returns:
            Optional[EnhancedJobData]: Job data if available, None if queue is empty.

        Raises:
            TranscriptionError: If queue operation fails.

        Example:
            >>> queue = QueueService()
            >>> job = queue.dequeue_job("worker-456")
            >>> if job:
            ...     print(f"Processing job {job.job_id}")
        """
        if not self._use_redis or not self._redis_client:
            raise TranscriptionError(
                "Queue service not available: Redis connection failed",
                code="QUEUE_ERROR",
                details={"queue_name": self._queue_name},
            )

        try:
            result = self._redis_client.bzpopmin(self._queue_name, timeout=1)

            if not result:
                return None

            queue_name, job_id, score = cast(tuple[str, str, float], result)

            job_hash_key = f"queue:job:{job_id}"
            job_json = self._redis_client.get(job_hash_key)

            if not job_json:
                logger.warning(f"Job {job_id} found in queue but data not found in hash")
                return None

            job_dict = json.loads(cast(str, job_json))
            job_data = EnhancedJobData(**job_dict)
            job_data.assigned_worker_id = worker_id

            processing_key = f"{self._processing_queue_name}:{job_id}"
            self._redis_client.setex(
                processing_key, settings.queue_visibility_timeout_seconds, cast(str, job_json)
            )

            logger.info(f"Dequeued job {job_id} for worker {worker_id}")

            _update_queue_depth_metric(self)

            return job_data

        except RedisError as e:
            logger.error(f"Failed to dequeue job: {e}")
            raise TranscriptionError(
                f"Failed to dequeue job: {str(e)}",
                code="QUEUE_ERROR",
                details={"worker_id": worker_id, "error": str(e)},
            )

    def requeue_failed_job(
        self, job_id: str, error: str, max_retries: Optional[int] = None
    ) -> bool:
        """
        Requeue a failed job for retry or move to dead letter queue.

        If retry count is below max_retries, requeues the job with incremented
        retry count. Otherwise, moves the job to the dead letter queue.

        Args:
            job_id: ID of the failed job.
            error: Error message describing the failure.
            max_retries: Maximum retries (uses config default if None).

        Returns:
            bool: True if job was requeued, False if moved to DLQ.

        Raises:
            TranscriptionError: If queue operation fails.

        Example:
            >>> queue = QueueService()
            >>> requeued = queue.requeue_failed_job("job-123", "Transcription failed")
            >>> if requeued:
            ...     print("Job requeued for retry")
            ... else:
            ...     print("Job moved to dead letter queue")
        """
        if not self._use_redis or not self._redis_client:
            raise TranscriptionError(
                "Queue service not available: Redis connection failed",
                code="QUEUE_ERROR",
                details={"queue_name": self._queue_name},
            )

        try:
            processing_key = f"{self._processing_queue_name}:{job_id}"
            job_json = self._redis_client.get(processing_key)

            if not job_json:
                job_hash_key = f"queue:job:{job_id}"
                job_json = self._redis_client.get(job_hash_key)

            if not job_json:
                logger.warning(f"Job {job_id} not found for requeue")
                return False

            job_dict = json.loads(cast(str, job_json))
            job_data = EnhancedJobData(**job_dict)

            max_retries_value = max_retries or settings.queue_max_retries
            job_data.retry_count += 1

            if job_data.retry_count <= max_retries_value:
                priority = (
                    JobPriority.LOW if job_data.priority == JobPriority.LOW else JobPriority.NORMAL
                )
                logger.info(
                    f"Requeuing job {job_id} (retry {job_data.retry_count}/{max_retries_value})"
                )
                self.enqueue_job(job_data, priority)
                self._redis_client.delete(processing_key)
                return True
            else:
                dlq_entry = {
                    "job_id": job_id,
                    "job_data": job_dict,
                    "error": error,
                    "retry_count": job_data.retry_count,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                }
                self._redis_client.lpush(self._dead_letter_queue_name, json.dumps(dlq_entry))
                self._redis_client.delete(processing_key)
                logger.warning(
                    f"Job {job_id} moved to dead letter queue after {job_data.retry_count} retries"
                )
                return False

        except RedisError as e:
            logger.error(f"Failed to requeue job {job_id}: {e}")
            raise TranscriptionError(
                f"Failed to requeue job: {str(e)}",
                code="QUEUE_ERROR",
                details={"job_id": job_id, "error": str(e)},
            )

    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics for monitoring.

        Returns counts of pending, processing, and failed jobs.

        Returns:
            Dict[str, Any]: Dictionary with queue statistics:
                - pending (int): Number of jobs waiting in queue.
                - processing (int): Number of jobs currently being processed.
                - failed (int): Number of jobs in dead letter queue.
                - total (int): Total jobs across all queues.
                - error (str, optional): Error message if stats retrieval failed.

        Example:
            >>> queue = QueueService()
            >>> stats = queue.get_queue_stats()
            >>> print(f"Pending: {stats['pending']}, Processing: {stats['processing']}")
        """
        if not self._use_redis or not self._redis_client:
            return {
                "pending": 0,
                "processing": 0,
                "failed": 0,
                "total": 0,
                "error": "Queue service not available",
            }

        try:
            pending = cast(int, self._redis_client.zcard(self._queue_name))

            processing_keys = cast(
                list[str], self._redis_client.keys(f"{self._processing_queue_name}:*")
            )
            processing = len(processing_keys) if processing_keys else 0

            failed = cast(int, self._redis_client.llen(self._dead_letter_queue_name))

            total = pending + processing + failed

            return {
                "pending": pending,
                "processing": processing,
                "failed": failed,
                "total": total,
            }

        except RedisError as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {
                "pending": 0,
                "processing": 0,
                "failed": 0,
                "total": 0,
                "error": str(e),
            }

    def remove_job_from_processing(self, job_id: str) -> None:
        """
        Remove a job from the processing queue.

        Called when a job completes successfully or fails permanently.
        Cleans up the job from the processing queue.

        Args:
            job_id: ID of the job to remove.
        """
        if not self._use_redis or not self._redis_client:
            return

        try:
            processing_key = f"{self._processing_queue_name}:{job_id}"
            job_hash_key = f"queue:job:{job_id}"
            self._redis_client.delete(processing_key, job_hash_key)
            logger.debug(f"Removed job {job_id} from processing queue")
        except RedisError as e:
            logger.warning(f"Failed to remove job {job_id} from processing queue: {e}")

    def get_job_position(self, job_id: str) -> Optional[int]:
        """
        Get the position of a job in the queue.

        Returns the position (1-indexed) of the job in the queue, or None
        if the job is not in the queue.

        Args:
            job_id: ID of the job.

        Returns:
            Optional[int]: Position in queue (1-indexed) or None if not found.

        Example:
            >>> queue = QueueService()
            >>> position = queue.get_job_position("job-123")
            >>> if position:
            ...     print(f"Job is at position {position} in queue")
        """
        if not self._use_redis or not self._redis_client:
            return None

        try:
            rank = self._redis_client.zrank(self._queue_name, job_id)
            if rank is not None:
                return cast(int, rank) + 1
            return None
        except RedisError as e:
            logger.warning(f"Failed to get position for job {job_id}: {e}")
            return None
