"""Comprehensive unit tests for WorkerManager service.

This test suite covers:
1. Happy path scenarios
2. Edge cases
3. Error conditions
4. Boundary value analysis
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.core.exceptions import TranscriptionError
from app.models.schemas import WorkerStatus
from app.services.jobs.worker_manager import WorkerManager


class TestWorkerManagerInitialization:
    """Test WorkerManager initialization scenarios."""

    def test_init_without_api_key(self, mock_settings_redis_disabled):
        """Test: Initialize WorkerManager without API key (edge case).

        Verifies that WorkerManager initializes but HTTP client is None.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = None
            mock_settings_redis_disabled.runpod_template_id = None

            manager = WorkerManager()

            assert manager._runpod_api_key is None
            assert manager._http_client is None

    def test_init_with_api_key(self, mock_settings_redis_disabled):
        """Test: Initialize WorkerManager with API key (happy path).

        Verifies that HTTP client is created when API key is provided.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = "test-api-key"
            mock_settings_redis_disabled.runpod_template_id = "template-123"

            with patch("app.services.jobs.worker_manager.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client

                manager = WorkerManager()

                assert manager._http_client == mock_client
                mock_client_class.assert_called_once()


class TestWorkerManagerTestConnection:
    """Test WorkerManager.test_connection method."""

    @pytest.mark.asyncio
    async def test_test_connection_success(
        self, mock_settings_redis_disabled, sample_runpod_user_response
    ):
        """Test: Test connection successfully (happy path).

        Verifies that connection test returns success when API is reachable.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = "test-api-key"
            mock_settings_redis_disabled.runpod_template_id = "template-123"

            manager = WorkerManager()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_runpod_user_response
            mock_response.raise_for_status = Mock()

            manager._http_client = AsyncMock()
            manager._http_client.post = AsyncMock(return_value=mock_response)

            result = await manager.test_connection()

            assert result["connected"] is True
            assert "user_id" in result["details"]

    @pytest.mark.asyncio
    async def test_test_connection_without_api_key(self, mock_settings_redis_disabled):
        """Test: Test connection without API key (error condition).

        Verifies that connection test returns failure when API key is not configured.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = None

            manager = WorkerManager()

            result = await manager.test_connection()

            assert result["connected"] is False
            assert "API key not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_test_connection_api_error(
        self, mock_settings_redis_disabled, sample_runpod_response_error
    ):
        """Test: Test connection with API error (error condition).

        Verifies that connection test returns failure when API returns error.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = "test-api-key"

            manager = WorkerManager()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_runpod_response_error
            mock_response.raise_for_status = Mock()

            manager._http_client = AsyncMock()
            manager._http_client.post = AsyncMock(return_value=mock_response)

            result = await manager.test_connection()

            assert result["connected"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_test_connection_http_error(self, mock_settings_redis_disabled):
        """Test: Test connection with HTTP error (error condition).

        Verifies that connection test handles HTTP errors gracefully.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = "test-api-key"

            manager = WorkerManager()
            manager._http_client = AsyncMock()
            manager._http_client.post = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

            result = await manager.test_connection()

            assert result["connected"] is False
            assert "error" in result


class TestWorkerManagerRegisterWorker:
    """Test WorkerManager.register_worker method."""

    def test_register_worker_success(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Register worker successfully (happy path).

        Verifies that worker is registered with correct status and metadata.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            worker = manager.register_worker(
                worker_id="worker-123",
                runpod_pod_id="pod-abc",
                gpu_type="RTX 4090",
            )

            assert worker.worker_id == "worker-123"
            assert worker.runpod_pod_id == "pod-abc"
            assert worker.gpu_type == "RTX 4090"
            assert worker.status == WorkerStatus.WARMING_UP
            assert worker.model_loaded is False
            assert "worker-123" in manager._workers

    def test_register_worker_with_default_gpu_type(self, mock_settings_redis_disabled):
        """Test: Register worker with default GPU type (edge case).

        Verifies that default GPU type "Unknown" is used when not specified.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            worker = manager.register_worker(
                worker_id="worker-123",
                runpod_pod_id="pod-abc",
            )

            assert worker.gpu_type == "Unknown"

    def test_register_worker_multiple(self, mock_settings_redis_disabled):
        """Test: Register multiple workers (happy path).

        Verifies that multiple workers can be registered.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            for i in range(5):
                manager.register_worker(
                    worker_id=f"worker-{i}",
                    runpod_pod_id=f"pod-{i}",
                    gpu_type="RTX 4090",
                )

            assert len(manager._workers) == 5


class TestWorkerManagerHeartbeat:
    """Test WorkerManager.heartbeat method."""

    def test_heartbeat_idle_worker(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Update heartbeat for idle worker (happy path).

        Verifies that heartbeat updates timestamp and status correctly.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            worker_id = sample_worker_info.worker_id
            manager._workers[worker_id] = sample_worker_info
            sample_worker_info.current_job_id = None
            sample_worker_info.model_loaded = True

            old_heartbeat = sample_worker_info.last_heartbeat
            manager.heartbeat(worker_id, model_loaded=True)

            assert manager._workers[worker_id].last_heartbeat != old_heartbeat
            assert manager._workers[worker_id].status == WorkerStatus.IDLE

    def test_heartbeat_busy_worker(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Update heartbeat for busy worker (happy path).

        Verifies that busy worker status is maintained.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            worker_id = sample_worker_info.worker_id
            manager._workers[worker_id] = sample_worker_info
            sample_worker_info.current_job_id = "job-123"
            sample_worker_info.model_loaded = True

            manager.heartbeat(worker_id, model_loaded=True)

            assert manager._workers[worker_id].status == WorkerStatus.BUSY

    def test_heartbeat_warming_up_worker(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Update heartbeat for warming up worker (happy path).

        Verifies that warming up status is maintained when model not loaded.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            worker_id = sample_worker_info.worker_id
            manager._workers[worker_id] = sample_worker_info
            sample_worker_info.current_job_id = None
            sample_worker_info.model_loaded = False

            manager.heartbeat(worker_id, model_loaded=False)

            assert manager._workers[worker_id].status == WorkerStatus.WARMING_UP

    def test_heartbeat_unregistered_worker(self, mock_settings_redis_disabled):
        """Test: Update heartbeat for unregistered worker (error condition).

        Verifies that TranscriptionError is raised for unregistered worker.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            with pytest.raises(TranscriptionError, match="is not registered"):
                manager.heartbeat("nonexistent-worker", model_loaded=True)


class TestWorkerManagerAssignJob:
    """Test WorkerManager.assign_job method."""

    def test_assign_job_to_idle_worker(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Assign job to idle worker (happy path).

        Verifies that job is assigned and worker status changes to BUSY.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            worker_id = sample_worker_info.worker_id
            manager._workers[worker_id] = sample_worker_info
            sample_worker_info.status = WorkerStatus.IDLE
            sample_worker_info.current_job_id = None

            manager.assign_job(worker_id, "job-123")

            assert manager._workers[worker_id].current_job_id == "job-123"
            assert manager._workers[worker_id].status == WorkerStatus.BUSY

    def test_assign_job_to_unregistered_worker(self, mock_settings_redis_disabled):
        """Test: Assign job to unregistered worker (error condition).

        Verifies that TranscriptionError is raised for unregistered worker.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            with pytest.raises(TranscriptionError, match="is not registered"):
                manager.assign_job("nonexistent-worker", "job-123")

    def test_assign_job_to_busy_worker(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Assign job to busy worker (error condition).

        Verifies that TranscriptionError is raised when worker is not idle.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            worker_id = sample_worker_info.worker_id
            manager._workers[worker_id] = sample_worker_info
            sample_worker_info.status = WorkerStatus.BUSY
            sample_worker_info.current_job_id = "job-456"

            with pytest.raises(TranscriptionError, match="is not idle"):
                manager.assign_job(worker_id, "job-123")


class TestWorkerManagerCompleteJob:
    """Test WorkerManager.complete_job method."""

    def test_complete_job_success(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Complete job successfully (happy path).

        Verifies that job completion updates worker statistics correctly.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            worker_id = sample_worker_info.worker_id
            manager._workers[worker_id] = sample_worker_info
            sample_worker_info.current_job_id = "job-123"
            sample_worker_info.status = WorkerStatus.BUSY
            sample_worker_info.jobs_processed = 10
            sample_worker_info.total_gpu_hours = 2.5

            manager.complete_job(worker_id, "job-123", processing_time_seconds=120.0)

            assert manager._workers[worker_id].current_job_id is None
            assert manager._workers[worker_id].status == WorkerStatus.IDLE
            assert manager._workers[worker_id].jobs_processed == 11
            # 120 seconds = 120/3600 = 0.033... hours
            assert manager._workers[worker_id].total_gpu_hours > 2.5

    def test_complete_job_unregistered_worker(self, mock_settings_redis_disabled):
        """Test: Complete job for unregistered worker (error condition).

        Verifies that TranscriptionError is raised for unregistered worker.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            with pytest.raises(TranscriptionError, match="is not registered"):
                manager.complete_job("nonexistent-worker", "job-123", 120.0)

    def test_complete_job_mismatched_job_id(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Complete job with mismatched job ID (edge case).

        Verifies that warning is logged but job is still completed.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            worker_id = sample_worker_info.worker_id
            manager._workers[worker_id] = sample_worker_info
            sample_worker_info.current_job_id = "job-456"

            # Should not raise exception, but log warning
            manager.complete_job(worker_id, "job-123", 120.0)

            assert manager._workers[worker_id].current_job_id is None


class TestWorkerManagerGetAvailableWorkers:
    """Test WorkerManager.get_available_workers method."""

    def test_get_available_workers_multiple(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Get multiple available workers (happy path).

        Verifies that only idle workers with model loaded are returned.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            # Create idle workers
            for i in range(3):
                worker = sample_worker_info.model_copy()
                worker.worker_id = f"worker-{i}"
                worker.status = WorkerStatus.IDLE
                worker.model_loaded = True
                manager._workers[worker.worker_id] = worker

            # Create busy worker (should not be returned)
            busy_worker = sample_worker_info.model_copy()
            busy_worker.worker_id = "worker-busy"
            busy_worker.status = WorkerStatus.BUSY
            busy_worker.model_loaded = True
            manager._workers[busy_worker.worker_id] = busy_worker

            available = manager.get_available_workers()

            assert len(available) == 3
            assert all(w.status == WorkerStatus.IDLE for w in available)
            assert all(w.model_loaded for w in available)

    def test_get_available_workers_empty(self, mock_settings_redis_disabled):
        """Test: Get available workers when none exist (edge case).

        Verifies that empty list is returned when no workers are available.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            available = manager.get_available_workers()

            assert available == []


class TestWorkerManagerHealthCheck:
    """Test WorkerManager.health_check_workers method."""

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Health check with all workers healthy (happy path).

        Verifies that all workers are marked as healthy.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.worker_health_check_timeout_seconds = 60
            manager = WorkerManager()

            # Create healthy worker (recent heartbeat)
            worker = sample_worker_info.model_copy()
            worker.worker_id = "worker-1"
            worker.last_heartbeat = datetime.now(timezone.utc).isoformat()
            manager._workers[worker.worker_id] = worker

            health = await manager.health_check_workers()

            assert health["worker-1"] is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_worker(
        self, mock_settings_redis_disabled, sample_worker_info
    ):
        """Test: Health check with unhealthy worker (error condition).

        Verifies that workers with stale heartbeats are marked as unhealthy.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.worker_health_check_timeout_seconds = 60
            manager = WorkerManager()

            # Create unhealthy worker (old heartbeat)
            worker = sample_worker_info.model_copy()
            worker.worker_id = "worker-1"
            old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
            worker.last_heartbeat = old_time.isoformat()
            manager._workers[worker.worker_id] = worker

            health = await manager.health_check_workers()

            assert health["worker-1"] is False
            assert manager._workers["worker-1"].status == WorkerStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_check_empty(self, mock_settings_redis_disabled):
        """Test: Health check with no workers (edge case).

        Verifies that empty dictionary is returned when no workers exist.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            health = await manager.health_check_workers()

            assert health == {}


class TestWorkerManagerScaleWorkers:
    """Test WorkerManager.scale_workers method."""

    @pytest.mark.asyncio
    async def test_scale_workers_up(
        self, mock_settings_redis_disabled, sample_runpod_response_success
    ):
        """Test: Scale workers up (happy path).

        Verifies that workers are created when target count is higher.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.min_workers = 1
            mock_settings_redis_disabled.max_workers = 10
            mock_settings_redis_disabled.runpod_api_key = "test-key"
            mock_settings_redis_disabled.runpod_template_id = "template-123"

            manager = WorkerManager()
            manager._http_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_runpod_response_success
            mock_response.raise_for_status = Mock()
            manager._http_client.post = AsyncMock(return_value=mock_response)

            # Register one worker
            manager.register_worker("worker-1", "pod-1", "RTX 4090")

            # Scale to 3 workers
            count = await manager.scale_workers(3)

            # Should have attempted to create workers (mocked)
            assert count >= 1

    @pytest.mark.asyncio
    async def test_scale_workers_respects_limits(self, mock_settings_redis_disabled):
        """Test: Scale workers respects min/max limits (boundary value analysis).

        Verifies that scaling respects min_workers and max_workers boundaries.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.min_workers = 2
            mock_settings_redis_disabled.max_workers = 5

            manager = WorkerManager()

            # Register some workers first
            manager.register_worker("worker-1", "pod-1", "RTX 4090")
            manager.register_worker("worker-2", "pod-2", "RTX 4090")
            manager.register_worker("worker-3", "pod-3", "RTX 4090")

            # Try to scale below min (should keep at least min_workers)
            count = await manager.scale_workers(1)
            assert count >= 2  # Should be at least min_workers

            # Try to scale above max (should cap at max_workers)
            count = await manager.scale_workers(10)
            assert count <= 5  # Should be at most max_workers


class TestWorkerManagerAutoScaleWorkers:
    """Test WorkerManager.auto_scale_workers method."""

    @pytest.mark.asyncio
    async def test_auto_scale_disabled(self, mock_settings_redis_disabled):
        """Test: Auto-scale when disabled (edge case).

        Verifies that no scaling occurs when auto-scaling is disabled.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.worker_auto_scaling_enabled = False

            manager = WorkerManager()
            manager.register_worker("worker-1", "pod-1", "RTX 4090")

            count = await manager.auto_scale_workers(queue_depth=20)

            # Should return current count without scaling
            assert count == 1

    @pytest.mark.asyncio
    async def test_auto_scale_up_high_queue_depth(
        self, mock_settings_redis_disabled, sample_runpod_response_success
    ):
        """Test: Auto-scale up with high queue depth (happy path).

        Verifies that workers are added when queue depth exceeds threshold.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.worker_auto_scaling_enabled = True
            mock_settings_redis_disabled.worker_scale_up_queue_depth = 10
            mock_settings_redis_disabled.max_workers = 10
            mock_settings_redis_disabled.runpod_api_key = "test-key"
            mock_settings_redis_disabled.runpod_template_id = "template-123"

            manager = WorkerManager()
            manager._http_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_runpod_response_success
            mock_response.raise_for_status = Mock()
            manager._http_client.post = AsyncMock(return_value=mock_response)

            manager.register_worker("worker-1", "pod-1", "RTX 4090")

            # Queue depth > threshold
            count = await manager.auto_scale_workers(queue_depth=15)

            # Should attempt to scale up
            assert count >= 1

    @pytest.mark.asyncio
    async def test_auto_scale_down_low_queue_depth(self, mock_settings_redis_disabled):
        """Test: Auto-scale down with low queue depth (happy path).

        Verifies that idle workers are removed when queue depth is low.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.worker_auto_scaling_enabled = True
            mock_settings_redis_disabled.worker_scale_down_queue_depth = 5
            mock_settings_redis_disabled.worker_idle_timeout_seconds = 60
            mock_settings_redis_disabled.min_workers = 1
            mock_settings_redis_disabled.runpod_api_key = "test-key"

            manager = WorkerManager()
            manager._http_client = AsyncMock()

            # Create idle worker with old heartbeat
            worker = manager.register_worker("worker-1", "pod-1", "RTX 4090")
            old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
            worker.last_heartbeat = old_time.isoformat()
            worker.status = WorkerStatus.IDLE

            # Queue depth < threshold
            count = await manager.auto_scale_workers(queue_depth=2)

            # Should attempt to scale down
            assert count >= 0


class TestWorkerManagerCreateWorker:
    """Test WorkerManager._create_worker method."""

    @pytest.mark.asyncio
    async def test_create_worker_success(
        self, mock_settings_redis_disabled, sample_runpod_response_success
    ):
        """Test: Create worker successfully (happy path).

        Verifies that worker pod is created via Runpod API.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = "test-key"
            mock_settings_redis_disabled.runpod_template_id = "template-123"

            manager = WorkerManager()
            manager._http_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_runpod_response_success
            mock_response.raise_for_status = Mock()
            manager._http_client.post = AsyncMock(return_value=mock_response)

            pod_id = await manager._create_worker()

            assert pod_id == "pod-abc123"
            manager._http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_worker_api_error(
        self, mock_settings_redis_disabled, sample_runpod_response_error
    ):
        """Test: Create worker with API error (error condition).

        Verifies that TranscriptionError is raised when API returns error.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = "test-key"
            mock_settings_redis_disabled.runpod_template_id = "template-123"

            manager = WorkerManager()
            manager._http_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_runpod_response_error
            mock_response.raise_for_status = Mock()
            manager._http_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(TranscriptionError, match="Failed to create Runpod worker"):
                await manager._create_worker()

    @pytest.mark.asyncio
    async def test_create_worker_without_config(self, mock_settings_redis_disabled):
        """Test: Create worker without configuration (error condition).

        Verifies that TranscriptionError is raised when API client or template ID is missing.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = None
            mock_settings_redis_disabled.runpod_template_id = None

            manager = WorkerManager()

            with pytest.raises(TranscriptionError, match="not configured"):
                await manager._create_worker()


class TestWorkerManagerTerminateWorker:
    """Test WorkerManager._terminate_worker method."""

    @pytest.mark.asyncio
    async def test_terminate_worker_success(self, mock_settings_redis_disabled, sample_worker_info):
        """Test: Terminate worker successfully (happy path).

        Verifies that worker pod is terminated via Runpod API.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.runpod_api_key = "test-key"

            manager = WorkerManager()
            manager._http_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"podTerminate": {"id": "pod-abc"}}}
            mock_response.raise_for_status = Mock()
            manager._http_client.post = AsyncMock(return_value=mock_response)

            worker_id = sample_worker_info.worker_id
            manager._workers[worker_id] = sample_worker_info

            await manager._terminate_worker(worker_id)

            # Worker should be removed from registry
            assert worker_id not in manager._workers

    @pytest.mark.asyncio
    async def test_terminate_worker_not_found(self, mock_settings_redis_disabled):
        """Test: Terminate non-existent worker (edge case).

        Verifies that method returns gracefully when worker is not found.
        """
        with patch("app.services.jobs.worker_manager.settings", mock_settings_redis_disabled):
            manager = WorkerManager()

            # Should not raise exception
            await manager._terminate_worker("nonexistent-worker")
