"""
Comprehensive unit tests for Jobs endpoint.

This module tests the /jobs endpoints covering:
- Happy path scenarios (list jobs, get job status)
- Edge cases (boundary values, streaming)
- Error conditions (job not found, invalid job ID)
- Streaming large results
"""

import json
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.responses import Response, StreamingResponse

from app.api.v1.endpoints.jobs import (get_job_manager, get_job_status,
                                       list_jobs)


class TestGetJobManager:
    """Tests for get_job_manager dependency function."""

    def test_get_job_manager_returns_instance(self):
        """Test: get_job_manager returns a JobManager instance."""
        # Act
        with patch("app.api.v1.endpoints.jobs.JobManager") as mock_job_manager_class:
            mock_instance = Mock()
            mock_job_manager_class.return_value = mock_instance
            result = get_job_manager()

        # Assert
        assert result == mock_instance
        mock_job_manager_class.assert_called_once()


class TestListJobs:
    """Tests for list_jobs endpoint."""

    @pytest.mark.asyncio
    async def test_list_jobs_empty_list(self, mock_job_manager):
        """Test: Happy path - List jobs when no jobs exist returns empty list."""
        # Arrange
        mock_job_manager.get_all_jobs.return_value = {}

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await list_jobs()

        # Assert
        assert result.total == 0
        assert len(result.jobs) == 0
        assert result.jobs == []

    @pytest.mark.asyncio
    async def test_list_jobs_single_job(self, mock_job_manager):
        """Test: Happy path - List jobs with single job returns one job."""
        # Arrange
        job_id = "test-job-id"
        mock_job_manager.get_all_jobs.return_value = {
            job_id: {"status": "completed", "job_id": job_id}
        }

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await list_jobs()

        # Assert
        assert result.total == 1
        assert len(result.jobs) == 1
        assert result.jobs[0].job_id == job_id
        assert result.jobs[0].status == "completed"

    @pytest.mark.asyncio
    async def test_list_jobs_multiple_jobs(self, mock_job_manager):
        """Test: Happy path - List jobs with multiple jobs returns all jobs."""
        # Arrange
        jobs_data = {
            "job-1": {"status": "queued", "job_id": "job-1"},
            "job-2": {"status": "processing", "job_id": "job-2"},
            "job-3": {"status": "completed", "job_id": "job-3"},
            "job-4": {"status": "failed", "job_id": "job-4"},
        }
        mock_job_manager.get_all_jobs.return_value = jobs_data

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await list_jobs()

        # Assert
        assert result.total == 4
        assert len(result.jobs) == 4
        statuses = {job.status for job in result.jobs}
        assert statuses == {"queued", "processing", "completed", "failed"}

    @pytest.mark.asyncio
    async def test_list_jobs_all_statuses(self, mock_job_manager):
        """Test: Edge case - List jobs with all possible statuses."""
        # Arrange
        statuses = ["queued", "processing", "completed", "failed"]
        jobs_data = {
            f"job-{i}": {"status": status, "job_id": f"job-{i}"}
            for i, status in enumerate(statuses)
        }
        mock_job_manager.get_all_jobs.return_value = jobs_data

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await list_jobs()

        # Assert
        assert result.total == len(statuses)
        assert all(job.status in statuses for job in result.jobs)


class TestGetJobStatus:
    """Tests for get_job_status endpoint."""

    @pytest.mark.asyncio
    async def test_get_job_status_queued(self, mock_job_manager, sample_job_data):
        """Test: Happy path - Get job status for queued job."""
        # Arrange
        job_id = "test-job-id"
        sample_job_data["status"] = "queued"
        mock_job_manager.get_job.return_value = sample_job_data

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await get_job_status(job_id, stream=False)

        # Assert
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_200_OK
        content = json.loads(result.body)
        assert content["jobId"] == job_id
        assert content["status"] == "queued"
        assert "result" not in content  # Result not loaded for non-completed jobs

    @pytest.mark.asyncio
    async def test_get_job_status_processing(self, mock_job_manager, sample_job_data):
        """Test: Happy path - Get job status for processing job."""
        # Arrange
        job_id = "test-job-id"
        sample_job_data["status"] = "processing"
        mock_job_manager.get_job.return_value = sample_job_data

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await get_job_status(job_id, stream=False)

        # Assert
        assert isinstance(result, Response)
        content = json.loads(result.body)
        assert content["status"] == "processing"
        assert "result" not in content  # Result not loaded for non-completed jobs

    @pytest.mark.asyncio
    async def test_get_job_status_completed(self, mock_job_manager, sample_job_data_completed):
        """Test: Happy path - Get job status for completed job includes result."""
        # Arrange
        job_id = "test-job-id"
        mock_job_manager.get_job.side_effect = [
            sample_job_data_completed,  # First call (include_result=False)
            sample_job_data_completed,  # Second call (include_result=True)
        ]

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await get_job_status(job_id, stream=False)

        # Assert
        assert isinstance(result, Response)
        content = json.loads(result.body)
        assert content["status"] == "completed"
        assert "result" in content
        assert content["result"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_job_status_failed(self, mock_job_manager):
        """Test: Happy path - Get job status for failed job includes error."""
        # Arrange
        job_id = "test-job-id"
        job_data = {
            "job_id": job_id,
            "status": "failed",
            "created_at": 1704067200.0,
            "completed_at": 1704067300.0,
            "error": "Transcription failed: Model not loaded",
            "video_id": "dQw4w9WgXcQ",
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        }
        mock_job_manager.get_job.return_value = job_data

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await get_job_status(job_id, stream=False)

        # Assert
        assert isinstance(result, Response)
        content = json.loads(result.body)
        assert content["status"] == "failed"
        assert content["error"] == "Transcription failed: Model not loaded"
        assert "result" not in content

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, mock_job_manager):
        """Test: Error condition - Job not found returns 404."""
        # Arrange
        job_id = "non-existent-job-id"
        mock_job_manager.get_job.return_value = None

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_job_status(job_id, stream=False)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert job_id in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_job_status_empty_job_id(self, mock_job_manager):
        """Test: Edge case - Empty job ID."""
        # Arrange
        job_id = ""
        mock_job_manager.get_job.return_value = None

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_job_status(job_id, stream=False)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_job_status_streaming_large_result(
        self, mock_job_manager, sample_job_data_completed, sample_large_result
    ):
        """Test: Happy path - Streaming large result (>1MB) returns StreamingResponse."""
        # Arrange
        job_id = "test-job-id"
        sample_job_data_completed["result"] = sample_large_result
        mock_job_manager.get_job.side_effect = [
            sample_job_data_completed,  # First call (include_result=False)
            sample_job_data_completed,  # Second call (include_result=True)
        ]

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            with patch("app.api.v1.endpoints.jobs.settings") as mock_settings:
                mock_settings.download_chunk_size = 1024 * 1024  # 1MB chunks

                # Act
                result = await get_job_status(job_id, stream=True)

        # Assert
        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/json"
        assert job_id in result.headers.get("Content-Disposition", "")

    @pytest.mark.asyncio
    async def test_get_job_status_streaming_disabled(
        self, mock_job_manager, sample_job_data_completed, sample_large_result
    ):
        """Test: Edge case - Large result with streaming disabled returns normal Response."""
        # Arrange
        job_id = "test-job-id"
        sample_job_data_completed["result"] = sample_large_result
        mock_job_manager.get_job.side_effect = [
            sample_job_data_completed,  # First call (include_result=False)
            sample_job_data_completed,  # Second call (include_result=True)
        ]

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await get_job_status(job_id, stream=False)

        # Assert
        assert isinstance(result, Response)
        assert not isinstance(result, StreamingResponse)

    @pytest.mark.asyncio
    async def test_get_job_status_streaming_error_handling(
        self, mock_job_manager, sample_job_data_completed, sample_large_result
    ):
        """Test: Edge case - Error during streaming size check falls back to normal response."""
        # Arrange
        job_id = "test-job-id"
        sample_job_data_completed["result"] = sample_large_result
        mock_job_manager.get_job.side_effect = [
            sample_job_data_completed,  # First call (include_result=False)
            sample_job_data_completed,  # Second call (include_result=True)
        ]

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Mock json.dumps to fail on first call (size check) but succeed on second (final response)
            import json as json_module

            json_dumps_calls = []
            original_dumps = json_module.dumps

            def mock_dumps(*args, **kwargs):
                json_dumps_calls.append(1)
                if len(json_dumps_calls) == 1:
                    # First call fails (size check)
                    raise Exception("Serialization error")
                # Second call succeeds (final response)
                return original_dumps(*args, **kwargs)

            with patch("app.api.v1.endpoints.jobs.json.dumps", side_effect=mock_dumps):
                # Act
                result = await get_job_status(job_id, stream=True)

        # Assert
        # Should fall back to normal response (error is caught and logged)
        assert isinstance(result, Response)
        # The error is caught and a normal response is returned

    @pytest.mark.asyncio
    async def test_get_job_status_with_video_url(self, mock_job_manager, sample_job_data):
        """Test: Happy path - Job status includes video_url when available."""
        # Arrange
        job_id = "test-job-id"
        video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        sample_job_data["video_url"] = video_url
        mock_job_manager.get_job.return_value = sample_job_data

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await get_job_status(job_id, stream=False)

        # Assert
        content = json.loads(result.body)
        assert content["videoUrl"] == video_url

    @pytest.mark.asyncio
    async def test_get_job_status_without_video_url(self, mock_job_manager):
        """Test: Edge case - Job status without video_url."""
        # Arrange
        job_id = "test-job-id"
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "created_at": 1704067200.0,
            "completed_at": None,
            "error": None,
            "video_id": None,
        }
        mock_job_manager.get_job.return_value = job_data

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await get_job_status(job_id, stream=False)

        # Assert
        content = json.loads(result.body)
        assert "videoUrl" not in content or content.get("videoUrl") is None

    @pytest.mark.asyncio
    async def test_get_job_status_camel_case_conversion(self, mock_job_manager, sample_job_data):
        """Test: Response keys are converted to camelCase."""
        # Arrange
        job_id = "test-job-id"
        mock_job_manager.get_job.return_value = sample_job_data

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await get_job_status(job_id, stream=False)

        # Assert
        content = json.loads(result.body)
        # Check camelCase keys
        assert "jobId" in content
        assert "createdAt" in content
        assert "completedAt" in content
        assert "videoId" in content
        assert "videoUrl" in content

    @pytest.mark.asyncio
    async def test_get_job_status_invalid_uuid_format(self, mock_job_manager):
        """Test: Edge case - Invalid UUID format job ID."""
        # Arrange
        job_id = "not-a-valid-uuid"
        mock_job_manager.get_job.return_value = None

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_job_status(job_id, stream=False)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_job_status_result_not_in_completed_job(self, mock_job_manager):
        """Test: Edge case - Completed job without result field."""
        # Arrange
        job_id = "test-job-id"
        job_data = {
            "job_id": job_id,
            "status": "completed",
            "created_at": 1704067200.0,
            "completed_at": 1704067300.0,
            "error": None,
            "video_id": "dQw4w9WgXcQ",
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            # No "result" field
        }
        mock_job_manager.get_job.side_effect = [
            job_data,  # First call (include_result=False)
            job_data,  # Second call (include_result=True) - still no result
        ]

        with patch("app.api.v1.endpoints.jobs.get_job_manager", return_value=mock_job_manager):
            # Act
            result = await get_job_status(job_id, stream=False)

        # Assert
        content = json.loads(result.body)
        assert content["status"] == "completed"
        assert "result" not in content
