"""Job manager for async transcription jobs."""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.models.schemas import JobStatus
from app.utils.serialization import convert_to_camel_case

logger = logging.getLogger(__name__)

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


class JobManager:
    """
    Manages async transcription jobs with Redis persistence (production-ready).

    Storage Strategy:
    - Redis: Stores minimal job metadata (status, progress, resultRef, metadata, timestamps, error)
    - File System: Stores full results in date-based directories: results/YYYY-MM-DD/{job_id}.json
    - Fallback: In-memory storage if Redis unavailable

    Jobs progress through states: QUEUED -> PROCESSING -> COMPLETED/FAILED

    Attributes:
        _redis_client (Optional[redis.Redis]): Redis client if enabled and connected
        _use_redis (bool): Whether to use Redis (enabled in config and connection successful)
        _jobs (Dict[str, dict]): In-memory fallback storage (used if Redis unavailable)
        _redis_key_prefix (str): Prefix for Redis keys (default: "job:")
        _temp_store_dir (Path): Directory for storing full job results

    Example:
        >>> manager = JobManager()
        >>> job_id = manager.create_job(
        ...     "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ...     "dQw4w9WgXcQ",
        ...     None,
        ...     "json",
        ...     False
        ... )
        >>> job = manager.get_job(job_id)
        >>> job["status"] == JobStatus.QUEUED.value
        True
    """

    # Class-level in-memory fallback storage (used when Redis unavailable)
    _jobs: Dict[str, dict] = {}
    _redis_key_prefix: str = settings.redis_key_prefix

    def __init__(self) -> None:
        """Initialize the job manager.

        Attempts to connect to Redis if enabled. Falls back to in-memory storage
        if Redis is disabled or connection fails.
        Creates results directory (and date subdirectories) if they don't exist.

        Raises:
            ValueError: If temp_store_dir setting is not a string.
        """
        self._use_redis: bool = False
        self._redis_client: Optional[redis.Redis] = None
        self._redis_pool: Optional[Any] = None  # type: ignore[type-arg]
        self._job_list_cache: Optional[Dict[str, dict]] = None
        self._job_list_cache_timestamp: Optional[float] = None

        if not isinstance(settings.temp_store_dir, str):
            raise ValueError(
                f"settings.temp_store_dir must be a string, got {type(settings.temp_store_dir).__name__}"
            )
        self._temp_store_dir = Path(settings.temp_store_dir).resolve()
        self._temp_store_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Job results will be stored in: {self._temp_store_dir}")

        self._s3_storage = None
        if settings.s3_enabled:
            try:
                from app.services.media.s3_storage_service import \
                    S3StorageService

                self._s3_storage = S3StorageService()
                if self._s3_storage.is_enabled():
                    logger.info("JobManager initialized with S3 storage for results")
                else:
                    logger.warning("S3 storage requested but not available, using local filesystem")
                    self._s3_storage = None
            except Exception as e:
                logger.warning(f"Failed to initialize S3 storage, using local filesystem: {e}")
                self._s3_storage = None

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
                    logger.info(f"Using Redis URL connection (host={redis_host}:{redis_port}, ssl={ssl})")
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
                pool_info = {
                    "max_connections": pool.max_connections,
                }
                logger.info(
                    f"JobManager initialized with Redis storage "
                    f"(host={settings.redis_host}:{settings.redis_port}, db={settings.redis_db}, "
                    f"max_connections: {pool_info['max_connections']})"
                )
                self._redis_pool = pool
            except (RedisConnectionError, RedisError, Exception) as e:
                logger.warning(
                    f"Redis connection failed, falling back to in-memory storage: {e}. "
                    "Jobs will be lost on restart."
                )
                self._redis_client = None
                self._use_redis = False
        else:
            logger.info("JobManager initialized with in-memory storage (Redis disabled)")

    def recover_orphaned_jobs(self) -> int:
        """
        Recover orphaned jobs that were in PROCESSING state when application stopped.

        On application restart, any jobs that were in "processing" state are considered
        orphaned (the background task was interrupted). This method marks them as "failed"
        with an appropriate error message.

        Returns:
            int: Number of jobs recovered (marked as failed)

        Example:
            >>> manager = JobManager()
            >>> recovered_count = manager.recover_orphaned_jobs()
            >>> print(f"Recovered {recovered_count} orphaned jobs")
        """
        recovered_count = 0
        error_message = "Job was interrupted due to application restart. Please retry the request."

        try:
            all_jobs = self.get_all_jobs()
            for job_id, job in all_jobs.items():
                if job.get("status") == JobStatus.PROCESSING.value:
                    logger.warning(f"Recovering orphaned job {job_id} that was in PROCESSING state")
                    self.fail_job(job_id, error_message)
                    recovered_count += 1

            if recovered_count > 0:
                logger.info(
                    f"Recovery complete: {recovered_count} orphaned job(s) marked as failed"
                )
            else:
                logger.debug("No orphaned jobs found to recover")

        except Exception as e:
            logger.error(f"Error during job recovery: {type(e).__name__} - {str(e)}", exc_info=True)

        return recovered_count

    def get_redis_pool_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get Redis connection pool statistics for monitoring.

        Returns connection pool usage statistics including:
        - created_connections: Number of connections created
        - available_connections: Number of available connections in pool
        - max_connections: Maximum number of connections allowed

        Returns:
            Optional[Dict[str, Any]]: Pool statistics if Redis is enabled, None otherwise.
                Contains max_connections. Other stats are not available via ConnectionPool API.

        Example:
            >>> manager = JobManager()
            >>> stats = manager.get_redis_pool_stats()
            >>> stats["max_connections"]
            50
        """
        if not self._use_redis or not self._redis_pool:
            return None

        return {
            "max_connections": self._redis_pool.max_connections,
            "created_connections": "N/A",  # Not available via ConnectionPool API
            "available_connections": "N/A",  # Not available via ConnectionPool API
            "usage_percent": 0,  # Cannot calculate without connection stats
        }

    def _get_redis_key(self, job_id: str) -> str:
        """
        Get Redis key for a job ID.

        Constructs a Redis key by prepending the configured prefix to the job ID.
        This ensures consistent key naming across all Redis operations.

        Args:
            job_id: Job identifier (UUID).

        Returns:
            str: Redis key string (e.g., "job:123e4567-e89b-12d3-a456-426614174000").
        """
        return f"{self._redis_key_prefix}{job_id}"

    def _get_result_file_path(self, job_id: str) -> Path:
        """
        Get file path for storing full job result.

        Constructs the absolute path to the JSON file where the full job result
        will be stored in a date-based directory structure: results/YYYY-MM-DD/{job_id}.json

        Args:
            job_id: Job identifier (UUID).

        Returns:
            Path: Absolute path to the result file (e.g., "/path/to/results/2024-01-15/{job_id}.json").
        """
        from datetime import date

        date_str = date.today().isoformat()
        date_dir = self._temp_store_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        return Path(date_dir / f"{job_id}.{settings.result_file_extension}")

    def _save_result_to_file(self, job_id: str, result: dict) -> str:
        """
        Save full result to file/S3 and return file path or S3 URI.

        Args:
            job_id: Job identifier
            result: Full result dictionary

        Returns:
            str: S3 URI if S3 enabled, otherwise relative path to result file.

        Raises:
            Exception: If file write operation fails.
        """
        if self._s3_storage and self._s3_storage.is_enabled():
            try:
                s3_uri = self._s3_storage.upload_result(result, job_id)
                logger.info(f"Saved result to S3 for job {job_id}: {s3_uri}")
                return s3_uri
            except Exception as e:
                logger.error(
                    f"Failed to save result to S3 for job {job_id}: {e}, falling back to local"
                )

        file_path = self._get_result_file_path(job_id)
        try:
            result_camel = convert_to_camel_case(result)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result_camel, f, indent=2, default=str, ensure_ascii=False)
            relative_path = file_path.relative_to(self._temp_store_dir)
            return str(relative_path).replace("\\", "/")
        except Exception as e:
            logger.error(f"Error saving result to file for job {job_id}: {e}")
            raise

    def _load_result_from_file(
        self, job_id: str, result_ref: Optional[str] = None
    ) -> Optional[dict]:
        """
        Load full result from S3 or local file.

        Args:
            job_id: Job identifier.
            result_ref: Optional relative path to result file (e.g., "2024-01-15/{job_id}.json").
                If provided, uses this path directly. Otherwise, tries today's date directory.

        Returns:
            Optional[dict]: Full result dictionary if found, None otherwise.
        """
        if self._s3_storage and self._s3_storage.is_enabled():
            try:
                result = self._s3_storage.download_result(job_id)
                if result:
                    logger.debug(f"Loaded result from S3 for job {job_id}")
                    return result
            except Exception as e:
                logger.warning(f"Failed to load result from S3 for job {job_id}: {e}, trying local")

        if result_ref:
            file_path = self._temp_store_dir / result_ref
        else:
            file_path = self._get_result_file_path(job_id)

        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return cast(dict, json.load(f))
            except Exception as e:
                logger.error(f"Error loading result from file for job {job_id}: {e}")
                return None

        if result_ref is None:
            if self._temp_store_dir.exists():
                for date_dir in self._temp_store_dir.iterdir():
                    if (
                        date_dir.is_dir()
                        and len(date_dir.name) == 10
                        and date_dir.name.count("-") == 2
                    ):
                        candidate_path = date_dir / f"{job_id}.{settings.result_file_extension}"
                        if candidate_path.exists():
                            try:
                                with open(candidate_path, "r", encoding="utf-8") as f:
                                    logger.debug(
                                        f"Found result for job {job_id} in date directory {date_dir.name}"
                                    )
                                    return cast(dict, json.load(f))
                            except Exception as e:
                                logger.warning(f"Error loading result from {candidate_path}: {e}")
                                continue

        return None

    def _create_minimal_job_data(
        self,
        job_id: str,
        video_id: str,
        video_url: str,
        translate_to: Optional[str],
        format: str,
        diarise: bool,
        created_at: str,
        webhook_url: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_hash: Optional[str] = None,
    ) -> dict:
        """
        Create minimal job data for Redis storage.

        Creates a dictionary containing only essential fields for Redis storage.
        This minimizes Redis memory usage while maintaining all necessary metadata
        for job tracking and status updates.

        Args:
            job_id: Unique job identifier (UUID).
            video_id: YouTube video ID or media identifier.
            video_url: YouTube video URL or media source URL.
            translate_to: Target language for translation.
            format: Output format ("json", "text", "srt", "vtt").
            diarise: Whether diarization is requested.
            created_at: ISO 8601 timestamp of job creation.
            webhook_url: Optional webhook callback URL.

        Returns:
            dict: Minimal job data dictionary with all essential fields initialized.
                Fields include: status, video_id, video_url, translate_to, format,
                diarise, created_at, completed_at, resultRef, progress, language,
                model, duration, source, error, webhook_url.
        """
        job = {
            "job_id": job_id,
            "status": JobStatus.QUEUED.value,
            "video_id": video_id,
            "video_url": video_url,
            "translate_to": translate_to,
            "format": format,
            "diarise": diarise,
            "created_at": created_at,
            "completed_at": None,
            "resultRef": None,  # Path to result file (results/YYYY-MM-DD/job_id.json)
            "progress": None,  # Optional progress field
            "language": None,  # Detected language (metadata)
            "model": None,  # Model used (metadata, e.g., "whisper-base")
            "duration": None,  # Video duration in seconds (metadata)
            "source": None,  # Source: "youtube_captions" or "asr" (metadata)
            "error": None,  # Error message if failed
            "webhook_url": webhook_url,  # Optional webhook callback URL
        }
        if user_id:
            job["user_id"] = user_id
        if ip_hash:
            job["ip_hash"] = ip_hash
        return job

    def _serialize_job(self, job: dict) -> str:
        """
        Serialize minimal job dictionary to JSON string.

        Converts a job dictionary to a JSON string for storage in Redis.
        Uses default=str to handle non-serializable types (e.g., datetime objects).

        Args:
            job: Job data dictionary to serialize.

        Returns:
            str: JSON string representation of the job data.
        """
        return json.dumps(job, default=str)

    def _deserialize_job(self, job_str: str) -> dict:
        """
        Deserialize JSON string to minimal job dictionary.

        Converts a JSON string (from Redis) back to a job dictionary.
        Uses type casting to satisfy type checkers.

        Args:
            job_str: JSON string representation of job data.

        Returns:
            dict: Job data dictionary.

        Raises:
            json.JSONDecodeError: If the string is not valid JSON.
        """
        return cast(dict, json.loads(job_str))

    def _get_job_from_redis(self, job_id: str) -> Optional[dict]:
        """
        Get minimal job data from Redis.

        Retrieves job metadata from Redis using the job ID. Returns None if
        the job doesn't exist or if Redis is not available.

        Args:
            job_id: Job identifier.

        Returns:
            Optional[dict]: Minimal job data dictionary if found, None otherwise.

        Raises:
            RedisError: If Redis operation fails (logged but not propagated).
        """
        if not self._redis_client:
            return None
        try:
            key = self._get_redis_key(job_id)
            job_str = self._redis_client.get(key)
            if job_str:
                return self._deserialize_job(cast(str, job_str))
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error reading job {job_id} from Redis: {e}")
            return None

    def _set_job_in_redis(self, job_id: str, job: dict, ttl: Optional[int] = None) -> None:
        """
        Store minimal job data in Redis with optional TTL.

        Stores job metadata in Redis. If TTL is provided, the key will expire
        after the specified number of seconds. If TTL is None, the key persists
        indefinitely (until manually deleted).

        Args:
            job_id: Job identifier.
            job: Minimal job data dictionary to store.
            ttl: Time-to-live in seconds. If None, key doesn't expire.

        Raises:
            RedisError: If Redis operation fails (logged but not propagated).
        """
        if not self._redis_client:
            return
        try:
            key = self._get_redis_key(job_id)
            job_str = self._serialize_job(job)
            if ttl:
                self._redis_client.setex(key, ttl, job_str)
            else:
                self._redis_client.set(key, job_str)
        except RedisError as e:
            logger.error(f"Error storing job {job_id} in Redis: {e}")

    def _get_all_jobs_from_redis(self) -> Dict[str, dict]:
        """
        Get all minimal job data from Redis using SCAN instead of KEYS.

        Performance optimization: Uses SCAN cursor-based iteration instead of KEYS
        to avoid blocking Redis and improve performance with large datasets.
        KEYS is O(N) and blocks the server, while SCAN is O(N) but non-blocking.

        Returns:
            Dict[str, dict]: Dictionary of all jobs keyed by job_id. Returns empty
                dictionary if Redis is unavailable or an error occurs.

        Raises:
            RedisError: If Redis operation fails (logged but not propagated, returns empty dict).
        """
        if not self._redis_client:
            return {}
        try:
            pattern = f"{self._redis_key_prefix}*"
            jobs = {}
            cursor = 0

            while True:
                scan_result = self._redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=settings.redis_scan_count,
                )
                cursor, keys = cast(tuple[int, list[str]], scan_result)

                if keys:
                    pipe = self._redis_client.pipeline()
                    for key in keys:
                        pipe.get(key)
                    job_strs = pipe.execute()

                    for key, job_str in zip(keys, job_strs):
                        if job_str:
                            try:
                                job_id = key.replace(self._redis_key_prefix, "")
                                jobs[job_id] = self._deserialize_job(cast(str, job_str))
                            except json.JSONDecodeError as e:
                                logger.warning(f"Error deserializing job {key}: {e}")

                if cursor == 0:
                    break

            return jobs
        except RedisError as e:
            logger.error(f"Error getting all jobs from Redis: {e}")
            return {}

    def create_job(
        self,
        video_url: str,
        video_id: str,
        translate_to: Optional[str],
        format: str,
        diarise: bool,
        webhook_url: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_hash: Optional[str] = None,
    ) -> tuple[str, dict]:
        """
        Create a new async transcription job.

        Generates a unique job ID and stores minimal job metadata in Redis (if enabled)
        or in-memory storage. Job starts in QUEUED status.

        Args:
            video_url: YouTube video URL or media source identifier.
            video_id: YouTube video ID or media identifier.
            translate_to: Target language for translation.
            format: Output format ("json", "text", "srt", "vtt").
            diarise: Whether diarization is requested.
            webhook_url: Optional webhook callback URL for job completion.

        Returns:
            tuple[str, dict]: Tuple of (job_id, job_data) to avoid race conditions.
                job_id: Unique job identifier (UUID).
                job_data: Minimal job data dictionary.

        Example:
            >>> manager = JobManager()
            >>> job_id, job = manager.create_job(
            ...     "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            ...     "dQw4w9WgXcQ",
            ...     None,
            ...     "json",
            ...     False,
            ...     webhook_url="https://example.com/callback"
            ... )
            >>> len(job_id) > 0
            True
            >>> job["status"] == JobStatus.QUEUED.value
            True
        """
        job_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        job = self._create_minimal_job_data(
            job_id, video_id, video_url, translate_to, format, diarise, created_at, webhook_url, user_id, ip_hash
        )

        if self._use_redis:
            self._set_job_in_redis(job_id, job, ttl=settings.job_ttl_seconds)
        else:
            JobManager._jobs[job_id] = job

        self._invalidate_job_list_cache()

        # Track job creation metric
        obs_service = _get_observability_service()
        if obs_service:
            source = "youtube_captions" if "youtube" in video_url.lower() else "media"
            obs_service.track_job("queued", source)

        logger.info(
            f"Created job {job_id} for video {video_id} "
            f"(format: {format}, translate_to: {translate_to}, diarise: {diarise}, "
            f"webhook_url: {'present' if webhook_url else 'none'})"
        )
        return job_id, job

    def get_job(self, job_id: str, include_result: bool = False) -> Optional[dict]:
        """
        Get job status and data.

        Retrieves minimal job information from Redis (if enabled) or in-memory storage.
        Optionally loads full result from file if include_result=True.

        Args:
            job_id: Job identifier.
            include_result: If True, loads full result from file.

        Returns:
            Optional[dict]: Job data dictionary if found, None otherwise.
                If include_result=True and job is completed, includes full result.

        Example:
            >>> manager = JobManager()
            >>> job_id = manager.create_job(url, video_id, None, "json", False)
            >>> job = manager.get_job(job_id)
            >>> job is not None
            True
        """
        if self._use_redis:
            job = self._get_job_from_redis(job_id)
        else:
            job = JobManager._jobs.get(job_id)

        if not job:
            return None

        if include_result:
            if job.get("status") == JobStatus.COMPLETED.value:
                result_ref = job.get("resultRef")
                if result_ref:
                    result = self._load_result_from_file(job_id, result_ref=result_ref)
                    if result:
                        job["result"] = result
                    else:
                        file_path = (
                            self._temp_store_dir / result_ref
                            if result_ref
                            else self._get_result_file_path(job_id)
                        )
                        logger.warning(
                            f"Job {job_id} is completed with resultRef '{result_ref}' "
                            f"but result file not found at {file_path}. "
                            f"File exists: {file_path.exists()}"
                        )
                else:
                    logger.warning(
                        f"Job {job_id} is completed but has no resultRef. "
                        f"This may indicate the result file save failed."
                    )

        return job

    def get_all_jobs(self) -> Dict[str, dict]:
        """
        Get all jobs (minimal data only).

        Retrieves all minimal job data from Redis (if enabled) or in-memory storage.
        Uses caching to reduce Redis load for frequently accessed job lists.

        Returns:
            Dict[str, dict]: Dictionary of all jobs, keyed by job_id.

        Example:
            >>> manager = JobManager()
            >>> job_id = manager.create_job(url, video_id, None, "json", False)
            >>> all_jobs = manager.get_all_jobs()
            >>> len(all_jobs) > 0
            True
        """
        if self._use_redis:
            current_time = time.time()
            cache_ttl = settings.job_list_cache_ttl

            if (
                self._job_list_cache is not None
                and self._job_list_cache_timestamp is not None
                and (current_time - self._job_list_cache_timestamp) < cache_ttl
            ):
                logger.debug("Returning cached job list")
                return self._job_list_cache.copy()

            jobs = self._get_all_jobs_from_redis()
            self._job_list_cache = jobs.copy()
            self._job_list_cache_timestamp = current_time
            return jobs
        else:
            return JobManager._jobs.copy()

    def _invalidate_job_list_cache(self) -> None:
        """
        Invalidate the job list cache.

        Should be called when jobs are created, updated, or deleted
        to ensure cache consistency.
        """
        self._job_list_cache = None
        self._job_list_cache_timestamp = None

    def update_job_status(
        self, job_id: str, status: JobStatus, progress: Optional[float] = None
    ) -> None:
        """
        Update job status and optional progress.

        Updates the status of an existing job. Used to transition jobs
        from QUEUED -> PROCESSING -> COMPLETED/FAILED.

        Args:
            job_id: Job identifier.
            status: New status (QUEUED, PROCESSING, COMPLETED, or FAILED).
            progress: Optional progress value between 0.0 and 1.0.
                If None, progress is not updated.

        Example:
            >>> manager = JobManager()
            >>> job_id = manager.create_job(url, video_id, None, "json", False)
            >>> manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.5)
        """
        job = self.get_job(job_id)
        if not job:
            logger.warning(f"Attempted to update status for non-existent job: {job_id}")
            return

        old_status = job["status"]
        job["status"] = status.value if hasattr(status, "value") else status
        if progress is not None:
            job["progress"] = progress

        if self._use_redis:
            self._set_job_in_redis(job_id, job, ttl=settings.job_ttl_seconds)
        else:
            JobManager._jobs[job_id] = job

        self._invalidate_job_list_cache()

        obs_service = _get_observability_service()
        if obs_service and status == JobStatus.PROCESSING:
            source = job.get("source", "unknown")
            obs_service.track_job("processing", source)

        logger.info(f"Job {job_id} status updated: {old_status} -> {job['status']}")

    def complete_job(
        self,
        job_id: str,
        result: dict,
        language: Optional[str] = None,
        model: Optional[str] = None,
        duration: Optional[float] = None,
        source: Optional[str] = None,
    ) -> None:
        """
        Mark job as completed with result.

        Updates job status to COMPLETED, saves full result to file, and updates
        minimal metadata in Redis. If webhook_url is present in job metadata,
        triggers webhook callback asynchronously.

        Implements transaction semantics: if Redis update fails after file save,
        the file is rolled back (deleted) to maintain consistency.

        Args:
            job_id: Job identifier.
            result: Full transcription result dictionary.
            language: Detected language code (ISO 639-1 format).
            model: Model used (e.g., "whisper-base").
            duration: Video duration in seconds.
            source: Source ("youtube_captions" or "asr").

        Example:
            >>> manager = JobManager()
            >>> job_id = manager.create_job(url, video_id, None, "json", False)
            >>> result = {"transcript": "Hello world", "segments": [...]}
            >>> manager.complete_job(job_id, result, language="en", model="whisper-base")
        """
        job = self.get_job(job_id)
        if not job:
            logger.warning(f"Attempted to complete non-existent job: {job_id}")
            return

        result_ref = None
        try:
            result_ref = self._save_result_to_file(job_id, result)
        except Exception as e:
            logger.error(f"Failed to save result to file for job {job_id}: {e}")
            self.fail_job(job_id, f"Failed to save result: {str(e)}")
            return

        job["status"] = JobStatus.COMPLETED.value
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        job["resultRef"] = result_ref
        if language:
            job["language"] = language
        if model:
            job["model"] = model
        if duration is not None:
            job["duration"] = duration
        if source:
            job["source"] = source

        try:
            if self._use_redis:
                self._set_job_in_redis(job_id, job, ttl=settings.job_ttl_seconds)
            else:
                JobManager._jobs[job_id] = job
        except Exception as e:
            logger.error(f"Failed to update Redis for job {job_id}: {e}. Rolling back file.")
            if result_ref:
                try:
                    result_file_path = self._get_result_file_path(job_id)
                    result_file_path.unlink(missing_ok=True)
                    logger.info(f"Rolled back result file for job {job_id} after Redis failure")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback file for job {job_id}: {rollback_error}")
            self.fail_job(job_id, f"Failed to update job status: {str(e)}")
            return

        logger.info(f"Job {job_id} completed successfully, result saved to {result_ref}")

        obs_service = _get_observability_service()
        if obs_service:
            job_source = source or job.get("source", "unknown")
            # Calculate job duration if created_at is available
            job_duration = None
            if "created_at" in job:
                try:
                    from datetime import datetime as dt

                    created_at = dt.fromisoformat(job["created_at"].replace("Z", "+00:00"))
                    completed_at = dt.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
                    job_duration = (completed_at - created_at).total_seconds()
                except Exception:
                    pass
            obs_service.track_job("completed", job_source, duration_seconds=job_duration)

        webhook_url = job.get("webhook_url")
        if webhook_url:
            logger.info(f"[WEBHOOK] Webhook URL found for job {job_id}: {webhook_url}")

    def fail_job(
        self,
        job_id: str,
        error: str,
        error_code: Optional[str] = None,
        error_details: Optional[dict] = None,
    ) -> None:
        """
        Mark job as failed with error message.

        Updates job status to FAILED and stores the error message, code, and details.

        Args:
            job_id: Job identifier.
            error: Error message describing the failure.
            error_code: Error code for programmatic error handling.
            error_details: Additional error details dictionary.

        Example:
            >>> manager = JobManager()
            >>> job_id = manager.create_job(url, video_id, None, "json", False)
            >>> manager.fail_job(job_id, "Transcription failed: audio file not found")
        """

        job = self.get_job(job_id)
        if not job:
            logger.warning(f"Attempted to fail non-existent job: {job_id}")
            return

        job["status"] = JobStatus.FAILED.value
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        job["error"] = error
        if error_code:
            job["error_code"] = error_code
        if error_details:
            job["error_details"] = error_details

        if self._use_redis:
            self._set_job_in_redis(job_id, job, ttl=settings.job_ttl_seconds)
        else:
            JobManager._jobs[job_id] = job

        # Track job failure metric
        obs_service = _get_observability_service()
        if obs_service:
            job_source = job.get("source", "unknown")
            obs_service.track_job("failed", job_source)

        logger.error(
            f"Job {job_id} failed: {error}" + (f" (code: {error_code})" if error_code else "")
        )

    def store_sync_result_metadata(
        self,
        result_id: str,
        video_id: str,
        video_url: str,
        translate_to: Optional[str],
        format: str,
        diarise: bool,
        result_ref: str,
        language: Optional[str] = None,
        model: Optional[str] = None,
        duration: Optional[float] = None,
        source: Optional[str] = None,
    ) -> None:
        """
        Store metadata for synchronous ASR result in Redis.

        Creates a Redis entry with minimal metadata for sync ASR results.
        This allows all ASR results (sync and async) to be tracked in Redis.

        Args:
            result_id: Unique result identifier (UUID).
            video_id: YouTube video ID.
            video_url: YouTube video URL.
            translate_to: Target language for translation (ISO 639-1).
            format: Output format ("json", "text", "srt", "vtt").
            diarise: Whether diarization was requested.
            result_ref: Path to result file (results/YYYY-MM-DD/{result_id}.json).
            language: Detected language code (ISO 639-1).
            model: Model used (e.g., "whisper-base").
            duration: Video duration in seconds.
            source: Source ("asr").

        Example:
            >>> manager = JobManager()
            >>> manager.store_sync_result_metadata(
            ...     result_id="123e4567-e89b-12d3-a456-426614174000",
            ...     video_id="dQw4w9WgXcQ",
            ...     video_url="https://...",
            ...     translate_to=None,
            ...     format="json",
            ...     diarise=False,
            ...     result_ref="2024-01-15/123e4567-e89b-12d3-a456-426614174000.json",
            ...     language="en",
            ...     model="whisper-base",
            ...     duration=180.5,
            ...     source="asr"
            ... )
        """
        created_at = datetime.now(timezone.utc).isoformat()

        metadata = {
            "job_id": result_id,
            "status": JobStatus.COMPLETED.value,
            "video_id": video_id,
            "video_url": video_url,
            "translate_to": translate_to,
            "format": format,
            "diarise": diarise,
            "created_at": created_at,
            "completed_at": created_at,
            "resultRef": result_ref,
            "progress": 1.0,
            "language": language,
            "model": model,
            "duration": duration,
            "source": source or "asr",
            "error": None,
        }

        if self._use_redis:
            self._set_job_in_redis(result_id, metadata, ttl=settings.job_ttl_seconds)
            logger.info(
                f"Sync ASR result metadata stored in Redis: {result_id} "
                f"(resultRef: {result_ref})"
            )
        else:
            JobManager._jobs[result_id] = metadata
            logger.info(
                f"Sync ASR result metadata stored in-memory: {result_id} (Redis unavailable)"
            )

    def _format_async_result(
        self,
        segments: List,
        language: str,
        confidence: Optional[float],
        job_id: str,
        video_id: str,
        duration: Optional[float],
        format_enum,
        video_url: Optional[str] = None,
    ) -> dict:
        """
        Format transcription result according to requested format.

        Converts transcript segments into the requested output format (JSON, TEXT, SRT, or VTT).
        For JSON format, returns a standardized response with all metadata.
        For other formats, returns a dictionary with "content" and "format" keys.

        Args:
            segments: List of transcript segments (TranscriptSegment objects).
            language: Detected language code (ISO 639-1).
            confidence: Confidence score (0.0-1.0) or None.
            job_id: Job identifier.
            video_id: YouTube video ID.
            duration: Video duration in seconds.
            format_enum: Output format enum value.
            video_url: Optional video URL.

        Returns:
            dict: Formatted result dictionary:
                - For JSON: Full response with transcript, segments, language, confidence, etc.
                - For TEXT/SRT/VTT: Dictionary with "content" (formatted string) and "format" keys.
        """
        from app.models.schemas import OutputFormat
        from app.utils.formatters import (format_as_srt, format_as_text,
                                          format_as_vtt)

        full_transcript = format_as_text(segments)

        if format_enum == OutputFormat.TEXT:
            return {"content": full_transcript, "format": "text"}
        elif format_enum == OutputFormat.SRT:
            return {"content": format_as_srt(segments), "format": "srt"}
        elif format_enum == OutputFormat.VTT:
            return {"content": format_as_vtt(segments), "format": "vtt"}
        else:
            result = {
                "status": "completed",
                "jobId": job_id,
                "source": "asr",
                "language": language,
                "confidence": confidence,
                "transcript": full_transcript,
                "segments": [seg.model_dump() for seg in segments],
                "warnings": [],
            }
            if video_url:
                result["video_url"] = video_url
            return result

    def _process_async_transcription(
        self, job_id: str, job: dict, audio_service, whisper_service
    ) -> None:
        """
        Process async transcription job (download, transcribe, format, save).

        Handles the complete workflow for async transcription:
        1. Updates job status to PROCESSING
        2. Downloads audio from YouTube
        3. Uploads audio to S3 if enabled (for storage and worker access)
        4. Transcribes audio using Whisper (async, in thread pool)
        5. Formats result according to requested format
        6. Saves full result to file/S3
        7. Updates job status to COMPLETED or FAILED
        8. Cleans up audio file

        Args:
            job_id: Job identifier.
            job: Job data dictionary containing video_url, video_id, translate_to, format, etc.
            audio_service: Service instance for downloading audio.
            whisper_service: Service instance for ASR transcription.

        Note:
            This method is called from a background task context. It uses asyncio.run()
            to execute async Whisper transcription since it's called from a sync context.
        """
        import asyncio
        from pathlib import Path

        from app.models.schemas import OutputFormat

        logger.info(f"Starting background processing for job {job_id}")
        self.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)

        audio_path = audio_service.download_audio(job["video_url"], job["video_id"])
        s3_uri = None

        try:
            if self._s3_storage and self._s3_storage.is_enabled():
                try:
                    audio_path_obj = Path(audio_path)
                    extension = audio_path_obj.suffix.lstrip(".") or "wav"
                    logger.info(f"Uploading audio to S3 for job {job_id}...")
                    s3_uri = self._s3_storage.upload_media(audio_path_obj, job_id, extension)
                    logger.info(f"Successfully uploaded audio to S3 for job {job_id}: {s3_uri}")
                except Exception as e:
                    logger.error(
                        f"Failed to upload audio to S3 for job {job_id}: {e}", exc_info=True
                    )

            self.update_job_status(job_id, JobStatus.PROCESSING, progress=0.3)

            async def _transcribe_async():
                return await whisper_service.transcribe_async(
                    audio_path=audio_path,
                    translate_to=job["translate_to"],
                )

            result = asyncio.run(_transcribe_async())

            if isinstance(result, dict) and "code" in result:
                raise TranscriptionError(
                    result["message"],
                    code=result["code"],
                    details=result.get("details", {}),
                )

            segments, language, confidence = result

            self.update_job_status(job_id, JobStatus.PROCESSING, progress=0.8)

            duration = max(seg.end for seg in segments) if segments else None

            model_name = getattr(whisper_service, "_model_id", "whisper-base")
            if hasattr(whisper_service, "model_id"):
                model_name = whisper_service.model_id

            format_enum = OutputFormat(job["format"])
            result = self._format_async_result(
                segments,
                language,
                confidence,
                job_id,
                job["video_id"],
                duration,
                format_enum,
                job.get("video_url"),
            )

            self.complete_job(
                job_id=job_id,
                result=result,
                language=language,
                model=model_name,
                duration=duration,
                source="asr",
            )

            webhook_url = job.get("webhook_url")
            if webhook_url:
                from app.services.infrastructure.webhook_service import \
                    WebhookService

                webhook_service = WebhookService()
                asyncio.run(webhook_service.send_webhook(webhook_url, result, job_id))

        finally:
            audio_service.cleanup_audio(audio_path)

    def schedule_async_transcription(
        self,
        job_id: str,
        audio_service,
        whisper_service,
    ):
        """
        Schedule async transcription as background task.

        Returns a function that can be executed by FastAPI BackgroundTasks.
        The function downloads audio, transcribes it, formats the result,
        saves full result to file, and updates the job status.

        Args:
            job_id: Job identifier.
            audio_service: AudioDownloadService instance.
            whisper_service: WhisperService instance.

        Returns:
            callable: Function to execute as background task.

        Example:
            >>> manager = JobManager()
            >>> job_id = manager.create_job(url, video_id, None, "json", False)
            >>> process_func = manager.schedule_async_transcription(
            ...     job_id, audio_service, whisper_service
            ... )
            >>> # Execute in background task
            >>> background_tasks.add_task(process_func)
        """

        def process_job():
            """Background task for processing async transcription job.

            This function is executed by FastAPI BackgroundTasks.
            It handles the complete transcription workflow:
            1. Download audio
            2. Transcribe with Whisper
            3. Format result
            4. Save full result to file
            5. Update job status
            6. Cleanup audio file

            Raises:
                Exception: If job processing fails, job is marked as failed.
            """
            job = self.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found, cannot process")
                return

            try:
                self._process_async_transcription(job_id, job, audio_service, whisper_service)
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                logger.error(
                    f"Job {job_id} failed: {error_type} - {error_msg}",
                    exc_info=True,
                )
                self.fail_job(job_id, error_msg)

        return process_job
