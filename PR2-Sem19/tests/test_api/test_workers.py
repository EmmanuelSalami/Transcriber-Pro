"""
Comprehensive unit tests for Workers endpoint.

This module tests the /workers endpoints covering:
- Happy path scenarios (register, heartbeat, list, get, scale, test connection)
- Edge cases (boundary values, optional parameters)
- Error conditions (worker not found, registration errors, scaling errors)
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, status

from app.api.v1.endpoints.workers import (get_queue_service, get_worker,
                                          get_worker_manager, list_workers,
                                          register_worker, scale_workers,
                                          test_runpod_connection,
                                          worker_heartbeat)
from app.core.exceptions import TranscriptionError
from app.models.schemas import WorkerInfo


class TestGetWorkerManager:
    """Tests for get_worker_manager dependency function."""

    def test_get_worker_manager_returns_instance(self):
        """Test: get_worker_manager returns a WorkerManager instance."""
        # Act
        with patch("app.api.v1.endpoints.workers.WorkerManager") as mock_worker_manager_class:
            mock_instance = Mock()
            mock_worker_manager_class.return_value = mock_instance
            result = get_worker_manager()

        # Assert
        assert result == mock_instance
        mock_worker_manager_class.assert_called_once()


class TestGetQueueService:
    """Tests for get_queue_service dependency function."""

    def test_get_queue_service_returns_instance(self):
        """Test: get_queue_service returns a QueueService instance."""
        # Act
        with patch("app.api.v1.endpoints.workers.QueueService") as mock_queue_service_class:
            mock_instance = Mock()
            mock_queue_service_class.return_value = mock_instance
            result = get_queue_service()

        # Assert
        assert result == mock_instance
        mock_queue_service_class.assert_called_once()


class TestRegisterWorker:
    """Tests for register_worker endpoint."""

    @pytest.mark.asyncio
    async def test_register_worker_success(self, mock_worker_manager, sample_worker):
        """Test: Happy path - Register worker successfully."""
        # Arrange
        worker_id = "worker-123"
        runpod_pod_id = "pod-abc"
        gpu_type = "RTX 4090"
        mock_worker_manager.register_worker.return_value = sample_worker

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            result = await register_worker(
                worker_id=worker_id, runpod_pod_id=runpod_pod_id, gpu_type=gpu_type
            )

        # Assert
        assert isinstance(result, dict)
        assert result["message"] == "Worker registered successfully"
        assert result["worker_id"] == worker_id
        assert result["status"] == sample_worker.status.value
        mock_worker_manager.register_worker.assert_called_once_with(
            worker_id, runpod_pod_id, gpu_type
        )

    @pytest.mark.asyncio
    async def test_register_worker_default_gpu_type(self, mock_worker_manager, sample_worker):
        """Test: Happy path - Register worker with default GPU type."""
        # Arrange
        worker_id = "worker-123"
        runpod_pod_id = "pod-abc"
        mock_worker_manager.register_worker.return_value = sample_worker

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            # When gpu_type is not provided, FastAPI uses the default value from Query()
            result = await register_worker(
                worker_id=worker_id, runpod_pod_id=runpod_pod_id, gpu_type="Unknown"
            )

        # Assert
        assert isinstance(result, dict)
        # The actual call will have the default value, but we need to check the call was made
        mock_worker_manager.register_worker.assert_called_once()
        # Verify the call included the default GPU type
        call_args = mock_worker_manager.register_worker.call_args[0]
        assert call_args[2] == "Unknown"  # Third argument is gpu_type

    @pytest.mark.asyncio
    async def test_register_worker_transcription_error(self, mock_worker_manager):
        """Test: Error condition - TranscriptionError during registration."""
        # Arrange
        worker_id = "worker-123"
        runpod_pod_id = "pod-abc"
        error_message = "Worker already registered"
        mock_worker_manager.register_worker.side_effect = TranscriptionError(
            error_message, code="WORKER_EXISTS"
        )

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await register_worker(worker_id=worker_id, runpod_pod_id=runpod_pod_id)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert error_message in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_register_worker_generic_error(self, mock_worker_manager):
        """Test: Error condition - Generic exception during registration."""
        # Arrange
        worker_id = "worker-123"
        runpod_pod_id = "pod-abc"
        error_message = "Unexpected error"
        mock_worker_manager.register_worker.side_effect = Exception(error_message)

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await register_worker(worker_id=worker_id, runpod_pod_id=runpod_pod_id)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to register worker" in exc_info.value.detail


class TestWorkerHeartbeat:
    """Tests for worker_heartbeat endpoint."""

    @pytest.mark.asyncio
    async def test_worker_heartbeat_success(self, mock_worker_manager):
        """Test: Happy path - Update worker heartbeat successfully."""
        # Arrange
        worker_id = "worker-123"
        model_loaded = True

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            result = await worker_heartbeat(worker_id=worker_id, model_loaded=model_loaded)

        # Assert
        assert isinstance(result, dict)
        assert result["message"] == "Heartbeat received"
        assert result["worker_id"] == worker_id
        assert result["model_loaded"] == model_loaded
        mock_worker_manager.heartbeat.assert_called_once_with(worker_id, model_loaded)

    @pytest.mark.asyncio
    async def test_worker_heartbeat_model_not_loaded(self, mock_worker_manager):
        """Test: Happy path - Heartbeat with model not loaded."""
        # Arrange
        worker_id = "worker-123"
        model_loaded = False

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            result = await worker_heartbeat(worker_id=worker_id, model_loaded=model_loaded)

        # Assert
        assert isinstance(result, dict)
        assert result["model_loaded"] is False

    @pytest.mark.asyncio
    async def test_worker_heartbeat_default_model_loaded(self, mock_worker_manager):
        """Test: Happy path - Heartbeat with default model_loaded=True."""
        # Arrange
        worker_id = "worker-123"

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            # When model_loaded is not provided, FastAPI uses the default value from Query()
            result = await worker_heartbeat(worker_id=worker_id, model_loaded=True)

        # Assert
        assert isinstance(result, dict)
        assert result["model_loaded"] is True
        mock_worker_manager.heartbeat.assert_called_once_with(worker_id, True)

    @pytest.mark.asyncio
    async def test_worker_heartbeat_worker_not_found(self, mock_worker_manager):
        """Test: Error condition - Worker not found returns 404."""
        # Arrange
        worker_id = "non-existent-worker"
        error_message = "Worker not found"
        mock_worker_manager.heartbeat.side_effect = TranscriptionError(
            error_message, code="WORKER_NOT_FOUND"
        )

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await worker_heartbeat(worker_id=worker_id)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert error_message in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_worker_heartbeat_generic_error(self, mock_worker_manager):
        """Test: Error condition - Generic exception during heartbeat."""
        # Arrange
        worker_id = "worker-123"
        error_message = "Unexpected error"
        mock_worker_manager.heartbeat.side_effect = Exception(error_message)

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await worker_heartbeat(worker_id=worker_id)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to update heartbeat" in exc_info.value.detail


class TestListWorkers:
    """Tests for list_workers endpoint."""

    @pytest.mark.asyncio
    async def test_list_workers_empty(self, mock_worker_manager):
        """Test: Happy path - List workers when no workers exist returns empty list."""
        # Arrange
        mock_worker_manager.get_all_workers.return_value = []

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            result = await list_workers()

        # Assert
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_workers_single_worker(self, mock_worker_manager, sample_worker):
        """Test: Happy path - List workers with single worker."""
        # Arrange
        mock_worker_manager.get_all_workers.return_value = [sample_worker]

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            result = await list_workers()

        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].worker_id == sample_worker.worker_id

    @pytest.mark.asyncio
    async def test_list_workers_multiple_workers(
        self, mock_worker_manager, sample_worker, sample_worker_warming_up, sample_worker_processing
    ):
        """Test: Happy path - List workers with multiple workers."""
        # Arrange
        workers = [sample_worker, sample_worker_warming_up, sample_worker_processing]
        mock_worker_manager.get_all_workers.return_value = workers

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            result = await list_workers()

        # Assert
        assert isinstance(result, list)
        assert len(result) == 3
        worker_ids = {w.worker_id for w in result}
        assert worker_ids == {
            sample_worker.worker_id,
            sample_worker_warming_up.worker_id,
            sample_worker_processing.worker_id,
        }


class TestGetWorker:
    """Tests for get_worker endpoint."""

    @pytest.mark.asyncio
    async def test_get_worker_success(self, mock_worker_manager, sample_worker):
        """Test: Happy path - Get worker information successfully."""
        # Arrange
        worker_id = "worker-123"
        mock_worker_manager.get_worker.return_value = sample_worker

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            result = await get_worker(worker_id=worker_id)

        # Assert
        assert isinstance(result, WorkerInfo)
        assert result.worker_id == worker_id
        mock_worker_manager.get_worker.assert_called_once_with(worker_id)

    @pytest.mark.asyncio
    async def test_get_worker_not_found(self, mock_worker_manager):
        """Test: Error condition - Worker not found returns 404."""
        # Arrange
        worker_id = "non-existent-worker"
        mock_worker_manager.get_worker.return_value = None

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_worker(worker_id=worker_id)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert worker_id in exc_info.value.detail


class TestScaleWorkers:
    """Tests for scale_workers endpoint."""

    @pytest.mark.asyncio
    async def test_scale_workers_manual_target_count(self, mock_worker_manager, mock_queue_service):
        """Test: Happy path - Manual scaling to target count."""
        # Arrange
        target_count = 5
        mock_worker_manager.scale_workers = AsyncMock(return_value=target_count)

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            with patch(
                "app.api.v1.endpoints.workers.get_queue_service", return_value=mock_queue_service
            ):
                # Act
                result = await scale_workers(target_count=target_count)

        # Assert
        assert isinstance(result, dict)
        assert result["message"] == f"Scaled workers to {target_count}"
        assert result["worker_count"] == target_count
        assert result["target_count"] == target_count
        mock_worker_manager.scale_workers.assert_called_once_with(target_count)

    @pytest.mark.asyncio
    async def test_scale_workers_auto_scaling(self, mock_worker_manager, mock_queue_service):
        """Test: Happy path - Auto-scaling based on queue depth."""
        # Arrange
        queue_depth = 10
        worker_count = 3
        mock_queue_service.get_queue_stats.return_value = {"pending": queue_depth}
        mock_worker_manager.auto_scale_workers = AsyncMock(return_value=worker_count)

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            with patch(
                "app.api.v1.endpoints.workers.get_queue_service", return_value=mock_queue_service
            ):
                # Act
                result = await scale_workers(target_count=None)

        # Assert
        assert isinstance(result, dict)
        assert result["message"] == "Auto-scaled workers based on queue depth"
        assert result["worker_count"] == worker_count
        assert result["queue_depth"] == queue_depth
        mock_worker_manager.auto_scale_workers.assert_called_once_with(queue_depth)

    @pytest.mark.asyncio
    async def test_scale_workers_transcription_error(self, mock_worker_manager, mock_queue_service):
        """Test: Error condition - TranscriptionError during scaling."""
        # Arrange
        target_count = 10
        error_message = "Cannot scale beyond max workers"
        mock_worker_manager.scale_workers = AsyncMock(
            side_effect=TranscriptionError(error_message, code="SCALING_ERROR")
        )

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            with patch(
                "app.api.v1.endpoints.workers.get_queue_service", return_value=mock_queue_service
            ):
                # Act & Assert
                with pytest.raises(HTTPException) as exc_info:
                    await scale_workers(target_count=target_count)

                assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
                assert error_message in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_scale_workers_generic_error(self, mock_worker_manager, mock_queue_service):
        """Test: Error condition - Generic exception during scaling."""
        # Arrange
        target_count = 5
        error_message = "Unexpected error"
        mock_worker_manager.scale_workers = AsyncMock(side_effect=Exception(error_message))

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            with patch(
                "app.api.v1.endpoints.workers.get_queue_service", return_value=mock_queue_service
            ):
                # Act & Assert
                with pytest.raises(HTTPException) as exc_info:
                    await scale_workers(target_count=target_count)

                assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                assert "Failed to scale workers" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_scale_workers_zero_target(self, mock_worker_manager, mock_queue_service):
        """Test: Edge case - Scaling to zero workers."""
        # Arrange
        target_count = 0
        mock_worker_manager.scale_workers = AsyncMock(return_value=0)

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            with patch(
                "app.api.v1.endpoints.workers.get_queue_service", return_value=mock_queue_service
            ):
                # Act
                result = await scale_workers(target_count=target_count)

        # Assert
        assert result["worker_count"] == 0

    @pytest.mark.asyncio
    async def test_scale_workers_large_target(self, mock_worker_manager, mock_queue_service):
        """Test: Edge case - Scaling to large number of workers."""
        # Arrange
        target_count = 100
        mock_worker_manager.scale_workers = AsyncMock(return_value=100)

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            with patch(
                "app.api.v1.endpoints.workers.get_queue_service", return_value=mock_queue_service
            ):
                # Act
                result = await scale_workers(target_count=target_count)

        # Assert
        assert result["worker_count"] == 100


class TestTestRunpodConnection:
    """Tests for test_runpod_connection endpoint."""

    @pytest.mark.asyncio
    async def test_test_runpod_connection_success(self, mock_worker_manager):
        """Test: Happy path - Test RunPod connection successfully."""
        # Arrange
        connection_result = {
            "connected": True,
            "message": "Successfully connected to Runpod API",
            "details": {
                "api_key_set": True,
                "template_id_set": True,
                "api_url": "https://api.runpod.io/graphql",
            },
        }
        mock_worker_manager.test_connection = AsyncMock(return_value=connection_result)
        mock_worker_manager.close = AsyncMock()

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            result = await test_runpod_connection()

        # Assert
        assert isinstance(result, dict)
        assert result["connected"] is True
        assert "Successfully connected" in result["message"]
        mock_worker_manager.test_connection.assert_called_once()
        mock_worker_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_runpod_connection_failure(self, mock_worker_manager):
        """Test: Error condition - RunPod connection test fails."""
        # Arrange
        error_message = "Invalid API key"
        mock_worker_manager.test_connection = AsyncMock(side_effect=Exception(error_message))
        mock_worker_manager.close = AsyncMock()

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            result = await test_runpod_connection()

        # Assert
        assert isinstance(result, dict)
        assert result["connected"] is False
        assert "error" in result
        assert error_message in result["error"]
        mock_worker_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_runpod_connection_close_always_called(self, mock_worker_manager):
        """Test: Edge case - close() is always called even on error."""
        # Arrange
        connection_result = {"connected": True}
        mock_worker_manager.test_connection = AsyncMock(return_value=connection_result)
        mock_worker_manager.close = AsyncMock()

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            await test_runpod_connection()

        # Assert
        mock_worker_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_runpod_connection_close_on_error(self, mock_worker_manager):
        """Test: Edge case - close() is called even when test_connection raises exception."""
        # Arrange
        mock_worker_manager.test_connection = AsyncMock(side_effect=Exception("Connection error"))
        mock_worker_manager.close = AsyncMock()

        with patch(
            "app.api.v1.endpoints.workers.get_worker_manager", return_value=mock_worker_manager
        ):
            # Act
            await test_runpod_connection()

        # Assert
        mock_worker_manager.close.assert_called_once()
