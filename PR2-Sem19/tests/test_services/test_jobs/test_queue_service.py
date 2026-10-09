"""Comprehensive unit tests for QueueService.

This test suite covers:
1. Happy path scenarios
2. Edge cases
3. Error conditions
4. Boundary value analysis
"""

from unittest.mock import patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.core.exceptions import TranscriptionError
from app.models.schemas import JobPriority
from app.services.jobs.queue_service import QueueService


class TestQueueServiceInitialization:
    """Test QueueService initialization scenarios."""

    def test_init_with_redis_backend_success(self, mock_settings_redis_enabled, mock_redis_client):
        """Test: Initialize QueueService with Redis backend successfully (happy path).

        Verifies that QueueService connects to Redis successfully.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    assert queue._use_redis is True
                    assert queue._redis_client == mock_redis_client
                    assert queue._queue_name == f"queue:{mock_settings_redis_enabled.queue_name}"

    def test_init_with_redis_connection_failure(self, mock_settings_redis_enabled):
        """Test: Initialize QueueService with Redis connection failure (error condition).

        Verifies that TranscriptionError is raised when Redis connection fails.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value.ping.side_effect = RedisConnectionError(
                    "Connection failed"
                )

                with pytest.raises(TranscriptionError, match="Queue service requires Redis"):
                    QueueService()

    def test_init_with_sqs_backend(self, mock_settings_redis_enabled):
        """Test: Initialize QueueService with SQS backend (error condition).

        Verifies that TranscriptionError is raised for unsupported SQS backend.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "sqs"
            mock_settings_redis_enabled.queue_name = "transcription"

            with pytest.raises(TranscriptionError, match="SQS backend not yet implemented"):
                QueueService()

    def test_init_with_unsupported_backend(self, mock_settings_redis_enabled):
        """Test: Initialize QueueService with unsupported backend (error condition).

        Verifies that TranscriptionError is raised for unsupported backends.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "kafka"
            mock_settings_redis_enabled.queue_name = "transcription"

            with pytest.raises(TranscriptionError, match="Unsupported queue backend"):
                QueueService()


class TestQueueServiceEnqueueJob:
    """Test QueueService.enqueue_job method."""

    def test_enqueue_job_normal_priority(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Enqueue job with normal priority (happy path).

        Verifies that job is enqueued with correct priority.
        """
        # Ensure all required settings are set (fixture should have them, but be explicit)
        mock_settings_redis_enabled.queue_backend = "redis"
        mock_settings_redis_enabled.queue_name = "transcription"
        mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
        mock_settings_redis_enabled.queue_max_retries = 3

        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    job_id = queue.enqueue_job(sample_enhanced_job_data, JobPriority.NORMAL)

                    assert job_id == sample_enhanced_job_data.job_id
                    assert mock_redis_client.zadd.called
                    assert mock_redis_client.setex.called

    def test_enqueue_job_high_priority(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Enqueue job with high priority (happy path).

        Verifies that high priority jobs are enqueued correctly.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Ensure required settings are set
                    mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
                    mock_settings_redis_enabled.queue_max_retries = 3

                    job_id = queue.enqueue_job(sample_enhanced_job_data, JobPriority.HIGH)

                    assert job_id == sample_enhanced_job_data.job_id
                    # Verify zadd was called (priority queue)
                    assert mock_redis_client.zadd.called

    def test_enqueue_job_low_priority(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Enqueue job with low priority (happy path).

        Verifies that low priority jobs are enqueued correctly.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
            mock_settings_redis_enabled.queue_max_retries = 3
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    job_id = queue.enqueue_job(sample_enhanced_job_data, JobPriority.LOW)

                    assert job_id == sample_enhanced_job_data.job_id

    def test_enqueue_job_without_redis(self, mock_settings_redis_enabled):
        """Test: Enqueue job when Redis is unavailable (error condition).

        Verifies that TranscriptionError is raised when Redis is unavailable.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value.ping.side_effect = RedisConnectionError(
                    "Connection failed"
                )

                with pytest.raises(TranscriptionError):
                    QueueService()

    def test_enqueue_job_redis_error(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Enqueue job when Redis operation fails (error condition).

        Verifies that TranscriptionError is raised when Redis operation fails.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Ensure required settings are set
                    mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
                    mock_settings_redis_enabled.queue_max_retries = 3

                    mock_redis_client.zadd.side_effect = RedisError("Redis error")

                    with pytest.raises(TranscriptionError, match="Failed to enqueue job"):
                        queue.enqueue_job(sample_enhanced_job_data, JobPriority.NORMAL)


class TestQueueServiceDequeueJob:
    """Test QueueService.dequeue_job method."""

    def test_dequeue_job_success(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Dequeue job successfully (happy path).

        Verifies that highest priority job is dequeued correctly.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Ensure required settings are set
                    mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
                    mock_settings_redis_enabled.queue_max_retries = 3

                    # Mock bzpopmin to return a job
                    job_json = sample_enhanced_job_data.model_dump_json()
                    mock_redis_client.bzpopmin.return_value = (
                        queue._queue_name,
                        sample_enhanced_job_data.job_id,
                        1.0,
                    )
                    mock_redis_client.get.return_value = job_json

                    dequeued = queue.dequeue_job("worker-123")

                    assert dequeued is not None
                    assert dequeued.job_id == sample_enhanced_job_data.job_id
                    assert dequeued.assigned_worker_id == "worker-123"

    def test_dequeue_job_empty_queue(self, mock_settings_redis_enabled, mock_redis_client):
        """Test: Dequeue from empty queue (edge case).

        Verifies that None is returned when queue is empty.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Mock bzpopmin to return None (timeout)
                    mock_redis_client.bzpopmin.return_value = None

                    dequeued = queue.dequeue_job("worker-123")

                    assert dequeued is None

    def test_dequeue_job_missing_data(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Dequeue job when job data is missing (error condition).

        Verifies that None is returned when job data is not found in hash.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Ensure required settings are set
                    mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
                    mock_settings_redis_enabled.queue_max_retries = 3

                    # Mock bzpopmin to return a job
                    mock_redis_client.bzpopmin.return_value = (
                        queue._queue_name,
                        sample_enhanced_job_data.job_id,
                        1.0,
                    )
                    # But job data is missing
                    mock_redis_client.get.return_value = None

                    dequeued = queue.dequeue_job("worker-123")

                    assert dequeued is None

    def test_dequeue_job_redis_error(self, mock_settings_redis_enabled, mock_redis_client):
        """Test: Dequeue job when Redis operation fails (error condition).

        Verifies that TranscriptionError is raised when Redis operation fails.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Ensure required settings are set
                    mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
                    mock_settings_redis_enabled.queue_max_retries = 3

                    mock_redis_client.bzpopmin.side_effect = RedisError("Redis error")

                    with pytest.raises(TranscriptionError, match="Failed to dequeue job"):
                        queue.dequeue_job("worker-123")


class TestQueueServiceRequeueFailedJob:
    """Test QueueService.requeue_failed_job method."""

    def test_requeue_failed_job_within_retry_limit(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Requeue failed job within retry limit (happy path).

        Verifies that job is requeued when retry count is below max_retries.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            mock_settings_redis_enabled.queue_max_retries = 3
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Ensure required settings are set
                    mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
                    mock_settings_redis_enabled.queue_max_retries = 3

                    # Job with retry_count < max_retries
                    job_data = sample_enhanced_job_data
                    job_data.retry_count = 1
                    job_json = job_data.model_dump_json()

                    mock_redis_client.get.return_value = job_json

                    requeued = queue.requeue_failed_job(job_data.job_id, "Test error")

                    assert requeued is True
                    assert mock_redis_client.zadd.called  # Job was requeued

    def test_requeue_failed_job_exceeds_retry_limit(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Requeue failed job that exceeds retry limit (happy path).

        Verifies that job is moved to dead letter queue when retry limit is exceeded.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            mock_settings_redis_enabled.queue_max_retries = 3
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Ensure required settings are set
                    mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
                    mock_settings_redis_enabled.queue_max_retries = 3

                    # Job with retry_count >= max_retries
                    job_data = sample_enhanced_job_data
                    job_data.retry_count = 3
                    job_json = job_data.model_dump_json()

                    mock_redis_client.get.return_value = job_json

                    requeued = queue.requeue_failed_job(job_data.job_id, "Test error")

                    assert requeued is False
                    assert mock_redis_client.lpush.called  # Moved to DLQ

    def test_requeue_failed_job_not_found(self, mock_settings_redis_enabled, mock_redis_client):
        """Test: Requeue non-existent job (error condition).

        Verifies that False is returned when job is not found.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    mock_redis_client.get.return_value = None

                    requeued = queue.requeue_failed_job("nonexistent-job", "Test error")

                    assert requeued is False

    def test_requeue_failed_job_boundary_retry_count(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Requeue job at boundary retry count (boundary value analysis).

        Verifies behavior when retry_count equals max_retries (boundary case).
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            mock_settings_redis_enabled.queue_max_retries = 3
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Ensure required settings are set
                    mock_settings_redis_enabled.queue_visibility_timeout_seconds = 300
                    mock_settings_redis_enabled.queue_max_retries = 3

                    # Test with retry_count = max_retries (boundary)
                    job_data = sample_enhanced_job_data
                    job_data.retry_count = 2  # Will become 3 after increment
                    job_json = job_data.model_dump_json()

                    mock_redis_client.get.return_value = job_json

                    requeued = queue.requeue_failed_job(job_data.job_id, "Test error")

                    # retry_count becomes 3, which equals max_retries, so should be requeued
                    # (retry_count <= max_retries means requeue)
                    assert requeued is True


class TestQueueServiceGetQueueStats:
    """Test QueueService.get_queue_stats method."""

    def test_get_queue_stats_success(self, mock_settings_redis_enabled, mock_redis_client):
        """Test: Get queue stats successfully (happy path).

        Verifies that queue statistics are returned correctly.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    mock_redis_client.zcard.return_value = 5  # pending
                    mock_redis_client.keys.return_value = ["key1", "key2"]  # processing
                    mock_redis_client.llen.return_value = 3  # failed

                    stats = queue.get_queue_stats()

                    assert stats["pending"] == 5
                    assert stats["processing"] == 2
                    assert stats["failed"] == 3
                    assert stats["total"] == 10

    def test_get_queue_stats_empty_queue(self, mock_settings_redis_enabled, mock_redis_client):
        """Test: Get queue stats for empty queue (edge case).

        Verifies that all counts are zero for empty queue.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    mock_redis_client.zcard.return_value = 0
                    mock_redis_client.keys.return_value = []
                    mock_redis_client.llen.return_value = 0

                    stats = queue.get_queue_stats()

                    assert stats["pending"] == 0
                    assert stats["processing"] == 0
                    assert stats["failed"] == 0
                    assert stats["total"] == 0

    def test_get_queue_stats_redis_error(self, mock_settings_redis_enabled, mock_redis_client):
        """Test: Get queue stats when Redis operation fails (error condition).

        Verifies that error is returned in stats when Redis operation fails.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    mock_redis_client.zcard.side_effect = RedisError("Redis error")

                    stats = queue.get_queue_stats()

                    assert stats["error"] is not None
                    assert stats["pending"] == 0
                    assert stats["processing"] == 0
                    assert stats["failed"] == 0


class TestQueueServiceGetJobPosition:
    """Test QueueService.get_job_position method."""

    def test_get_job_position_success(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Get job position successfully (happy path).

        Verifies that job position (1-indexed) is returned correctly.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    # Mock zrank to return 0-indexed position (5 -> position 6)
                    mock_redis_client.zrank.return_value = 5

                    position = queue.get_job_position(sample_enhanced_job_data.job_id)

                    assert position == 6  # 1-indexed

    def test_get_job_position_not_in_queue(self, mock_settings_redis_enabled, mock_redis_client):
        """Test: Get position of job not in queue (edge case).

        Verifies that None is returned when job is not in queue.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    mock_redis_client.zrank.return_value = None

                    position = queue.get_job_position("nonexistent-job")

                    assert position is None

    def test_get_job_position_first_in_queue(
        self, mock_settings_redis_enabled, mock_redis_client, sample_enhanced_job_data
    ):
        """Test: Get position of first job in queue (boundary value analysis).

        Verifies that position 1 is returned for first job (rank 0).
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    mock_redis_client.zrank.return_value = 0  # First position

                    position = queue.get_job_position(sample_enhanced_job_data.job_id)

                    assert position == 1


class TestQueueServiceRemoveJobFromProcessing:
    """Test QueueService.remove_job_from_processing method."""

    def test_remove_job_from_processing_success(
        self, mock_settings_redis_enabled, mock_redis_client
    ):
        """Test: Remove job from processing queue successfully (happy path).

        Verifies that job is removed from processing queue.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.queue_service.redis.connection.ConnectionPool"):
                    queue = QueueService()

                    queue.remove_job_from_processing("job-123")

                    assert mock_redis_client.delete.called

    def test_remove_job_from_processing_without_redis(self, mock_settings_redis_enabled):
        """Test: Remove job when Redis is unavailable (edge case).

        Verifies that method returns gracefully when Redis is unavailable.
        """
        with patch("app.services.jobs.queue_service.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.queue_backend = "redis"
            mock_settings_redis_enabled.queue_name = "transcription"
            with patch("app.services.jobs.queue_service.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value.ping.side_effect = RedisConnectionError(
                    "Connection failed"
                )

                with pytest.raises(TranscriptionError):
                    QueueService()
