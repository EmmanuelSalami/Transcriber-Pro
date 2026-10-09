"""Cost control service for tracking and limiting GPU costs."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.core.config import settings
from app.models.schemas import CostMetrics

logger = logging.getLogger(__name__)


class CostControlService:
    """
    Cost control service for tracking and limiting GPU costs.

    Tracks GPU hours consumed, calculates costs, and enforces budget limits.
    Uses Redis for persistent cost tracking across restarts.

    Attributes:
        _redis_client (Optional[redis.Redis]): Redis client for cost tracking
        _use_redis (bool): Whether Redis is available
        _cost_key_prefix (str): Redis key prefix for cost data

    Example:
        >>> cost_control = CostControlService()
        >>> cost_control.track_job_cost("job-123", 0.5)  # 0.5 GPU hours
        >>> metrics = cost_control.get_cost_metrics()
        >>> if not cost_control.check_budget():
        ...     print("Budget exceeded!")
    """

    def __init__(self) -> None:
        """
        Initialize the cost control service.

        Connects to Redis for persistent cost tracking. Falls back gracefully
        if Redis is unavailable (costs tracked in-memory only). If cost control
        is disabled in settings, the service operates in a no-op mode.

        Returns:
            None: Initializes the service instance

        Raises:
            None: All errors are caught and logged, service falls back to in-memory tracking
        """
        self._use_redis = False
        self._redis_client: Optional[redis.Redis] = None
        self._cost_key_prefix = "cost:"
        self._in_memory_costs: List[Dict[str, Any]] = []

        if not settings.cost_control_enabled:
            logger.info("Cost control is disabled")
            return

        if settings.redis_enabled:
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
                    logger.info(f"CostControlService using Redis URL connection (host={redis_host}:{redis_port}, ssl={ssl})")
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
                logger.info("CostControlService initialized with Redis storage")
            except (RedisConnectionError, RedisError, Exception) as e:
                logger.warning(
                    f"Redis connection failed for cost control, using in-memory tracking: {e}"
                )
                self._redis_client = None
                self._use_redis = False
        else:
            logger.info("CostControlService initialized with in-memory storage (Redis disabled)")

    def track_job_cost(self, job_id: str, gpu_hours: float) -> None:
        """
        Track cost for a completed job.

        Records GPU hours consumed for a job and calculates cost. Stores
        cost data in Redis for persistence.

        Args:
            job_id (str): Job identifier
            gpu_hours (float): GPU hours consumed for this job

        Example:
            >>> cost_control = CostControlService()
            >>> cost_control.track_job_cost("job-123", 0.5)
        """
        if not settings.cost_control_enabled:
            return

        cost = gpu_hours * settings.gpu_cost_per_hour
        timestamp = datetime.now(timezone.utc).isoformat()

        cost_entry = {
            "job_id": job_id,
            "gpu_hours": gpu_hours,
            "cost": cost,
            "timestamp": timestamp,
        }

        if self._use_redis and self._redis_client:
            try:
                ttl_seconds = settings.cost_tracking_window_days * 24 * 3600
                cost_key = f"{self._cost_key_prefix}job:{job_id}"
                self._redis_client.setex(cost_key, ttl_seconds, str(cost_entry))

                total_cost_key = f"{self._cost_key_prefix}total"
                self._redis_client.incrbyfloat(total_cost_key, cost)
                self._redis_client.expire(total_cost_key, ttl_seconds)

                total_hours_key = f"{self._cost_key_prefix}total_hours"
                self._redis_client.incrbyfloat(total_hours_key, gpu_hours)
                self._redis_client.expire(total_hours_key, ttl_seconds)

                logger.debug(
                    f"Tracked cost for job {job_id}: {gpu_hours:.3f} GPU hours = ${cost:.2f}"
                )
            except RedisError as e:
                logger.warning(f"Failed to track cost in Redis for job {job_id}: {e}")
                self._in_memory_costs.append(cost_entry)
        else:
            self._in_memory_costs.append(cost_entry)

    def check_budget(self) -> bool:
        """
        Check if budget limit has been exceeded.

        Compares total accumulated cost against the configured maximum budget.
        Returns False if total cost exceeds max_budget_usd, indicating that
        new jobs should be rejected to prevent cost overruns.

        Returns:
            bool: True if budget is OK (costs are within limit), False if budget exceeded.
                Always returns True if cost control is disabled.

        Example:
            >>> cost_control = CostControlService()
            >>> if not cost_control.check_budget():
            ...     raise TranscriptionError("Budget exceeded")
        """
        if not settings.cost_control_enabled:
            return True  # No budget limit if cost control disabled

        total_cost = self._get_total_cost()
        return total_cost < settings.max_budget_usd

    def get_cost_metrics(self, active_workers: int = 0) -> CostMetrics:
        """
        Get current cost metrics.

        Calculates and returns cost metrics including total cost, GPU hours,
        cost per job, and budget remaining.

        Args:
            active_workers (int): Current number of active workers

        Returns:
            CostMetrics: Cost metrics object

        Example:
            >>> cost_control = CostControlService()
            >>> metrics = cost_control.get_cost_metrics(active_workers=3)
            >>> print(f"Total cost: ${metrics.total_cost:.2f}")
        """
        if not settings.cost_control_enabled:
            return CostMetrics(
                total_gpu_hours=0.0,
                cost_per_job=0.0,
                total_cost=0.0,
                budget_remaining=settings.max_budget_usd,
                jobs_processed=0,
                active_workers=active_workers,
            )

        total_cost = self._get_total_cost()
        total_gpu_hours = self._get_total_gpu_hours()
        jobs_processed = self._get_jobs_processed()

        cost_per_job = total_cost / jobs_processed if jobs_processed > 0 else 0.0
        budget_remaining = max(0.0, settings.max_budget_usd - total_cost)

        if total_cost >= settings.max_budget_usd * settings.budget_alert_threshold:
            logger.warning(
                f"Budget alert: {total_cost:.2f} / {settings.max_budget_usd:.2f} USD "
                f"({total_cost / settings.max_budget_usd * 100:.1f}%)"
            )

        return CostMetrics(
            total_gpu_hours=total_gpu_hours,
            cost_per_job=cost_per_job,
            total_cost=total_cost,
            budget_remaining=budget_remaining,
            jobs_processed=jobs_processed,
            active_workers=active_workers,
        )

    def enforce_idle_timeout(self, worker_id: str, idle_seconds: int) -> bool:
        """
        Check if worker should be terminated due to idle timeout.

        Returns True if worker has been idle longer than the configured
        idle timeout and should be terminated.

        Args:
            worker_id (str): Worker identifier
            idle_seconds (int): Number of seconds worker has been idle

        Returns:
            bool: True if worker should be terminated, False otherwise

        Example:
            >>> cost_control = CostControlService()
            >>> if cost_control.enforce_idle_timeout("worker-123", 600):
            ...     # Terminate worker
            ...     pass
        """
        if not settings.cost_control_enabled:
            return False

        timeout_seconds = settings.worker_idle_timeout_seconds
        return idle_seconds > timeout_seconds

    def _get_total_cost(self) -> float:
        """
        Get total cost from Redis or in-memory storage.

        Retrieves the accumulated total cost from Redis if available,
        otherwise calculates from in-memory cost entries.

        Returns:
            float: Total cost in USD. Returns 0.0 if no costs tracked or on error.

        Note:
            This is a private helper method. Use get_cost_metrics() for public access.
        """
        if self._use_redis and self._redis_client:
            try:
                total_cost_key = f"{self._cost_key_prefix}total"
                total_cost_str = self._redis_client.get(total_cost_key)
                if total_cost_str:
                    return float(cast(str | bytes, total_cost_str))
            except (RedisError, ValueError) as e:
                logger.warning(f"Failed to get total cost from Redis: {e}")

        # Fallback to in-memory calculation
        return float(sum(entry.get("cost", 0.0) for entry in self._in_memory_costs))

    def _get_total_gpu_hours(self) -> float:
        """
        Get total GPU hours from Redis or in-memory storage.

        Retrieves the accumulated total GPU hours from Redis if available,
        otherwise calculates from in-memory cost entries.

        Returns:
            float: Total GPU hours consumed. Returns 0.0 if no jobs tracked or on error.

        Note:
            This is a private helper method. Use get_cost_metrics() for public access.
        """
        if self._use_redis and self._redis_client:
            try:
                total_hours_key = f"{self._cost_key_prefix}total_hours"
                total_hours_str = self._redis_client.get(total_hours_key)
                if total_hours_str:
                    return float(cast(str | bytes, total_hours_str))
            except (RedisError, ValueError) as e:
                logger.warning(f"Failed to get total GPU hours from Redis: {e}")

        # Fallback to in-memory calculation
        return float(sum(entry.get("gpu_hours", 0.0) for entry in self._in_memory_costs))

    def _get_jobs_processed(self) -> int:
        """
        Get total number of jobs processed.

        Counts the number of jobs that have been tracked. Uses Redis key count
        if available, otherwise counts in-memory entries.

        Returns:
            int: Total number of jobs processed. Returns 0 if no jobs tracked or on error.

        Note:
            This is a private helper method. Use get_cost_metrics() for public access.
        """
        if self._use_redis and self._redis_client:
            try:
                cost_keys = cast(
                    list[bytes] | list[str],
                    self._redis_client.keys(f"{self._cost_key_prefix}job:*"),
                )
                return len(cost_keys) if cost_keys else 0
            except RedisError as e:
                logger.warning(f"Failed to count jobs from Redis: {e}")

        return len(self._in_memory_costs)

    def reset_cost_tracking(self) -> None:
        """
        Reset cost tracking (for testing or budget reset).

        Clears all cost data from Redis and in-memory storage. This includes:
        - Individual job cost entries
        - Total cost accumulator
        - Total GPU hours accumulator
        - In-memory cost entries

        Returns:
            None: Clears all cost data in-place

        Note:
            This operation cannot be undone. Use with caution in production.

        Example:
            >>> cost_control = CostControlService()
            >>> cost_control.reset_cost_tracking()
        """
        if self._use_redis and self._redis_client:
            try:
                cost_keys = cast(
                    list[bytes] | list[str], self._redis_client.keys(f"{self._cost_key_prefix}*")
                )
                if cost_keys:
                    self._redis_client.delete(*cost_keys)
                logger.info("Cost tracking reset in Redis")
            except RedisError as e:
                logger.warning(f"Failed to reset cost tracking in Redis: {e}")

        self._in_memory_costs.clear()
        logger.info("Cost tracking reset")
