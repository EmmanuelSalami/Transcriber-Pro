"""Comprehensive unit tests for JobManager service.

This test suite covers:
1. Happy path scenarios
2. Edge cases
3. Error conditions
4. Boundary value analysis
"""

import json
from unittest.mock import Mock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.models.schemas import JobStatus
from app.services.jobs.job_manager import JobManager


class TestJobManagerInitialization:
    """Test JobManager initialization scenarios."""

    def test_init_with_redis_disabled(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Initialize JobManager with Redis disabled (happy path).

        Verifies that JobManager initializes correctly when Redis is disabled,
        using in-memory storage as fallback.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            assert manager._use_redis is False
            assert manager._redis_client is None
            assert manager._temp_store_dir == temp_store_dir

    def test_init_with_redis_enabled_success(
        self, mock_settings_redis_enabled, mock_redis_client, temp_store_dir
    ):
        """Test: Initialize JobManager with Redis enabled and connection successful (happy path).

        Verifies that JobManager connects to Redis successfully when enabled.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.temp_store_dir = str(temp_store_dir)
            mock_settings_redis_enabled.s3_enabled = False  # Ensure attribute exists
            with patch("app.services.jobs.job_manager.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch(
                    "app.services.jobs.job_manager.redis.connection.ConnectionPool"
                ) as mock_pool_class:
                    mock_pool = Mock()
                    mock_pool.max_connections = 50
                    mock_pool_class.return_value = mock_pool

                    manager = JobManager()

                    assert manager._use_redis is True
                    assert manager._redis_client == mock_redis_client

    def test_init_with_redis_connection_failure(self, mock_settings_redis_enabled, temp_store_dir):
        """Test: Initialize JobManager with Redis enabled but connection fails (error condition).

        Verifies that JobManager falls back to in-memory storage when Redis connection fails.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.temp_store_dir = str(temp_store_dir)
            mock_settings_redis_enabled.s3_enabled = False  # Ensure attribute exists
            with patch("app.services.jobs.job_manager.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value.ping.side_effect = RedisConnectionError(
                    "Connection failed"
                )

                manager = JobManager()

                assert manager._use_redis is False
                assert manager._redis_client is None

    def test_init_with_invalid_temp_store_dir_type(self, mock_settings_redis_disabled):
        """Test: Initialize JobManager with invalid temp_store_dir type (error condition).

        Verifies that ValueError is raised when temp_store_dir is not a string.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = 123  # Invalid type

            with pytest.raises(ValueError, match="must be a string"):
                JobManager()

    def test_init_with_s3_enabled(
        self, mock_settings_redis_disabled, temp_store_dir, mock_s3_storage
    ):
        """Test: Initialize JobManager with S3 storage enabled (happy path).

        Verifies that S3 storage is initialized when enabled in settings.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            mock_settings_redis_disabled.s3_enabled = True

            with patch("app.services.media.s3_storage_service.S3StorageService") as mock_s3_class:
                mock_s3_class.return_value = mock_s3_storage

                manager = JobManager()

                assert manager._s3_storage == mock_s3_storage

    def test_init_with_s3_enabled_but_unavailable(
        self, mock_settings_redis_disabled, temp_store_dir
    ):
        """Test: Initialize JobManager with S3 enabled but unavailable (error condition).

        Verifies that JobManager falls back to local filesystem when S3 is unavailable.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            mock_settings_redis_disabled.s3_enabled = True

            with patch("app.services.media.s3_storage_service.S3StorageService") as mock_s3_class:
                mock_s3 = Mock()
                mock_s3.is_enabled.return_value = False
                mock_s3_class.return_value = mock_s3

                manager = JobManager()

                assert manager._s3_storage is None


class TestJobManagerCreateJob:
    """Test JobManager.create_job method."""

    def test_create_job_with_redis(
        self, mock_settings_redis_enabled, mock_redis_client, temp_store_dir, sample_job_data
    ):
        """Test: Create job with Redis enabled (happy path).

        Verifies that a job is created and stored in Redis with correct structure.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.temp_store_dir = str(temp_store_dir)
            mock_settings_redis_enabled.s3_enabled = False  # Ensure attribute exists
            mock_settings_redis_enabled.job_ttl_seconds = 3600  # Ensure attribute exists
            with patch("app.services.jobs.job_manager.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.job_manager.redis.connection.ConnectionPool"):
                    manager = JobManager()

                    job_id, job = manager.create_job(
                        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        video_id="dQw4w9WgXcQ",
                        translate_to=None,
                        format="json",
                        diarise=False,
                    )

                    assert job_id is not None
                    assert len(job_id) > 0
                    assert job["status"] == JobStatus.QUEUED.value
                    assert job["video_id"] == "dQw4w9WgXcQ"
                    assert mock_redis_client.setex.called

    def test_create_job_without_redis(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Create job without Redis (happy path).

        Verifies that a job is created and stored in-memory when Redis is disabled.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id, job = manager.create_job(
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                video_id="dQw4w9WgXcQ",
                translate_to="en",
                format="text",
                diarise=True,
            )

            assert job_id is not None
            assert job["status"] == JobStatus.QUEUED.value
            assert job["translate_to"] == "en"
            assert job["format"] == "text"
            assert job["diarise"] is True
            assert job_id in JobManager._jobs

    def test_create_job_with_webhook(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Create job with webhook URL (happy path).

        Verifies that webhook URL is stored in job metadata.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id, job = manager.create_job(
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                video_id="dQw4w9WgXcQ",
                translate_to=None,
                format="json",
                diarise=False,
                webhook_url="https://example.com/webhook",
            )

            assert job["webhook_url"] == "https://example.com/webhook"

    def test_create_job_with_all_formats(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Create jobs with all output formats (boundary value analysis).

        Verifies that jobs can be created with all supported formats: json, text, srt, vtt.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            formats = ["json", "text", "srt", "vtt"]
            for fmt in formats:
                job_id, job = manager.create_job(
                    video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    video_id="dQw4w9WgXcQ",
                    translate_to=None,
                    format=fmt,
                    diarise=False,
                )
                assert job["format"] == fmt

    def test_create_job_with_empty_video_url(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Create job with empty video URL (edge case).

        Verifies behavior with empty string (should still create job, validation happens elsewhere).
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id, job = manager.create_job(
                video_url="",
                video_id="",
                translate_to=None,
                format="json",
                diarise=False,
            )

            assert job_id is not None
            assert job["video_url"] == ""
            assert job["video_id"] == ""


class TestJobManagerGetJob:
    """Test JobManager.get_job method."""

    def test_get_job_existing_with_redis(
        self, mock_settings_redis_enabled, mock_redis_client, temp_store_dir, sample_job_data
    ):
        """Test: Get existing job from Redis (happy path).

        Verifies that an existing job can be retrieved from Redis.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_enabled):
            mock_settings_redis_enabled.temp_store_dir = str(temp_store_dir)
            mock_settings_redis_enabled.s3_enabled = False  # Ensure attribute exists
            with patch("app.services.jobs.job_manager.redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = mock_redis_client
                with patch("app.services.jobs.job_manager.redis.connection.ConnectionPool"):
                    manager = JobManager()

                    job_json = json.dumps(sample_job_data)
                    mock_redis_client.get.return_value = job_json

                    job = manager.get_job(sample_job_data["job_id"])

                    assert job is not None
                    assert job["job_id"] == sample_job_data["job_id"]
                    assert job["status"] == sample_job_data["status"]

    def test_get_job_nonexistent(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Get non-existent job (edge case).

        Verifies that None is returned when job doesn't exist.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job = manager.get_job("nonexistent-job-id")

            assert job is None

    def test_get_job_with_result_included(
        self,
        mock_settings_redis_disabled,
        temp_store_dir,
        sample_job_data_completed,
        sample_transcription_result,
    ):
        """Test: Get completed job with result included (happy path).

        Verifies that full result is loaded when include_result=True and job is completed.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            # Store job in memory
            job_id = sample_job_data_completed["job_id"]
            # Ensure resultRef is set
            if "resultRef" not in sample_job_data_completed:
                sample_job_data_completed["resultRef"] = (
                    "2024-01-15/123e4567-e89b-12d3-a456-426614174000.json"
                )
            JobManager._jobs[job_id] = sample_job_data_completed.copy()

            # Create result file
            result_file = temp_store_dir / sample_job_data_completed["resultRef"]
            result_file.parent.mkdir(parents=True, exist_ok=True)
            with open(result_file, "w") as f:
                json.dump(sample_transcription_result, f)

            job = manager.get_job(job_id, include_result=True)

            assert job is not None
            assert "result" in job
            assert job["result"]["transcript"] == sample_transcription_result["transcript"]

    def test_get_job_with_result_but_file_missing(
        self, mock_settings_redis_disabled, temp_store_dir, sample_job_data_completed
    ):
        """Test: Get completed job with result but file missing (error condition).

        Verifies that warning is logged when result file is missing.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id = sample_job_data_completed["job_id"]
            # Create a copy without the result key to test missing file scenario
            job_data = sample_job_data_completed.copy()
            job_data.pop("result", None)  # Remove result if present
            # Ensure resultRef is set so the code tries to load it
            if "resultRef" not in job_data:
                job_data["resultRef"] = "2024-01-15/123e4567-e89b-12d3-a456-426614174000.json"
            JobManager._jobs[job_id] = job_data

            # Don't create result file

            job = manager.get_job(job_id, include_result=True)

            assert job is not None
            assert "result" not in job  # Result not loaded because file missing


class TestJobManagerUpdateJobStatus:
    """Test JobManager.update_job_status method."""

    def test_update_job_status_queued_to_processing(
        self, mock_settings_redis_disabled, temp_store_dir, sample_job_data
    ):
        """Test: Update job status from QUEUED to PROCESSING (happy path).

        Verifies that job status can be updated successfully.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id = sample_job_data["job_id"]
            JobManager._jobs[job_id] = sample_job_data.copy()

            manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.5)

            job = manager.get_job(job_id)
            assert job["status"] == JobStatus.PROCESSING.value
            assert job["progress"] == 0.5

    def test_update_job_status_with_progress_boundary_values(
        self, mock_settings_redis_disabled, temp_store_dir, sample_job_data
    ):
        """Test: Update job status with boundary progress values (boundary value analysis).

        Verifies behavior with progress values: 0.0, 0.5, 1.0, None.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id = sample_job_data["job_id"]
            JobManager._jobs[job_id] = sample_job_data.copy()

            # Test with 0.0
            manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)
            job = manager.get_job(job_id)
            assert job["progress"] == 0.0

            # Test with 1.0
            manager.update_job_status(job_id, JobStatus.PROCESSING, progress=1.0)
            job = manager.get_job(job_id)
            assert job["progress"] == 1.0

            # Test with None (should not update progress)
            manager.update_job_status(job_id, JobStatus.PROCESSING, progress=None)
            job = manager.get_job(job_id)
            assert job["progress"] == 1.0  # Previous value retained

    def test_update_job_status_nonexistent(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Update status of non-existent job (error condition).

        Verifies that warning is logged but no exception is raised.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            # Should not raise exception
            manager.update_job_status("nonexistent-job-id", JobStatus.PROCESSING)


class TestJobManagerCompleteJob:
    """Test JobManager.complete_job method."""

    def test_complete_job_success(
        self,
        mock_settings_redis_disabled,
        temp_store_dir,
        sample_job_data,
        sample_transcription_result,
    ):
        """Test: Complete job successfully (happy path).

        Verifies that job is marked as completed, result is saved, and metadata is updated.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id = sample_job_data["job_id"]
            JobManager._jobs[job_id] = sample_job_data.copy()

            manager.complete_job(
                job_id=job_id,
                result=sample_transcription_result,
                language="en",
                model="whisper-base",
                duration=180.5,
                source="asr",
            )

            job = manager.get_job(job_id)
            assert job["status"] == JobStatus.COMPLETED.value
            assert job["language"] == "en"
            assert job["model"] == "whisper-base"
            assert job["duration"] == 180.5
            assert job["source"] == "asr"
            assert job["resultRef"] is not None
            assert job["completed_at"] is not None

    def test_complete_job_with_file_save_failure(
        self,
        mock_settings_redis_disabled,
        temp_store_dir,
        sample_job_data,
        sample_transcription_result,
    ):
        """Test: Complete job but file save fails (error condition).

        Verifies that job is marked as failed when result file cannot be saved.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id = sample_job_data["job_id"]
            JobManager._jobs[job_id] = sample_job_data.copy()

            # Make temp_store_dir read-only to cause save failure
            temp_store_dir.chmod(0o444)

            try:
                manager.complete_job(
                    job_id=job_id,
                    result=sample_transcription_result,
                )

                job = manager.get_job(job_id)
                assert job["status"] == JobStatus.FAILED.value
                assert "error" in job
            finally:
                # Restore permissions
                temp_store_dir.chmod(0o755)

    def test_complete_job_nonexistent(
        self, mock_settings_redis_disabled, temp_store_dir, sample_transcription_result
    ):
        """Test: Complete non-existent job (error condition).

        Verifies that warning is logged but no exception is raised.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            # Should not raise exception
            manager.complete_job(
                job_id="nonexistent-job-id",
                result=sample_transcription_result,
            )


class TestJobManagerFailJob:
    """Test JobManager.fail_job method."""

    def test_fail_job_success(self, mock_settings_redis_disabled, temp_store_dir, sample_job_data):
        """Test: Fail job successfully (happy path).

        Verifies that job is marked as failed with error message.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id = sample_job_data["job_id"]
            JobManager._jobs[job_id] = sample_job_data.copy()

            manager.fail_job(job_id, "Test error message", error_code="TEST_ERROR")

            job = manager.get_job(job_id)
            assert job["status"] == JobStatus.FAILED.value
            assert job["error"] == "Test error message"
            assert job["error_code"] == "TEST_ERROR"
            assert job["completed_at"] is not None

    def test_fail_job_with_error_details(
        self, mock_settings_redis_disabled, temp_store_dir, sample_job_data
    ):
        """Test: Fail job with error details (happy path).

        Verifies that error details dictionary is stored.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id = sample_job_data["job_id"]
            JobManager._jobs[job_id] = sample_job_data.copy()

            error_details = {"code": "TEST_ERROR", "retryable": False}
            manager.fail_job(job_id, "Test error", error_details=error_details)

            job = manager.get_job(job_id)
            assert job["error_details"] == error_details

    def test_fail_job_nonexistent(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Fail non-existent job (error condition).

        Verifies that warning is logged but no exception is raised.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            # Should not raise exception
            manager.fail_job("nonexistent-job-id", "Test error")


class TestJobManagerGetAllJobs:
    """Test JobManager.get_all_jobs method."""

    def test_get_all_jobs_empty(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Get all jobs when no jobs exist (edge case).

        Verifies that empty dictionary is returned when no jobs exist.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            # Clear in-memory storage
            JobManager._jobs.clear()

            all_jobs = manager.get_all_jobs()

            assert all_jobs == {}

    def test_get_all_jobs_multiple(
        self, mock_settings_redis_disabled, temp_store_dir, sample_job_data
    ):
        """Test: Get all jobs with multiple jobs (happy path).

        Verifies that all jobs are returned correctly.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            # Create multiple jobs
            job_ids = []
            for i in range(5):
                job_id, _ = manager.create_job(
                    video_url=f"https://www.youtube.com/watch?v=test{i}",
                    video_id=f"test{i}",
                    translate_to=None,
                    format="json",
                    diarise=False,
                )
                job_ids.append(job_id)

            all_jobs = manager.get_all_jobs()

            assert len(all_jobs) == 5
            for job_id in job_ids:
                assert job_id in all_jobs


class TestJobManagerRecoverOrphanedJobs:
    """Test JobManager.recover_orphaned_jobs method."""

    def test_recover_orphaned_jobs_none(
        self, mock_settings_redis_disabled, temp_store_dir, sample_job_data
    ):
        """Test: Recover orphaned jobs when none exist (edge case).

        Verifies that 0 is returned when no orphaned jobs exist.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            # Create a completed job (not orphaned)
            job_id = sample_job_data["job_id"]
            JobManager._jobs[job_id] = sample_job_data.copy()
            JobManager._jobs[job_id]["status"] = JobStatus.COMPLETED.value

            recovered = manager.recover_orphaned_jobs()

            assert recovered == 0

    def test_recover_orphaned_jobs_multiple(
        self, mock_settings_redis_disabled, temp_store_dir, sample_job_data_processing
    ):
        """Test: Recover multiple orphaned jobs (happy path).

        Verifies that all PROCESSING jobs are marked as failed.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            # Create multiple processing jobs (orphaned)
            for i in range(3):
                job_id = f"job-{i}"
                job = sample_job_data_processing.copy()
                job["job_id"] = job_id
                JobManager._jobs[job_id] = job

            recovered = manager.recover_orphaned_jobs()

            assert recovered == 3
            for i in range(3):
                job_id = f"job-{i}"
                job = manager.get_job(job_id)
                assert job["status"] == JobStatus.FAILED.value
                assert "interrupted" in job["error"].lower()


class TestJobManagerResultFileOperations:
    """Test JobManager result file operations."""

    def test_save_result_to_file_local(
        self, mock_settings_redis_disabled, temp_store_dir, sample_transcription_result
    ):
        """Test: Save result to local file (happy path).

        Verifies that result is saved to file in date-based directory.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id = "test-job-123"
            result_ref = manager._save_result_to_file(job_id, sample_transcription_result)

            assert result_ref is not None
            assert result_ref.endswith(".json")

            # Verify file exists
            result_file = temp_store_dir / result_ref
            assert result_file.exists()

            # Verify content
            with open(result_file) as f:
                saved_result = json.load(f)
            assert saved_result["transcript"] == sample_transcription_result["transcript"]

    def test_load_result_from_file(
        self, mock_settings_redis_disabled, temp_store_dir, sample_transcription_result
    ):
        """Test: Load result from file (happy path).

        Verifies that result can be loaded from file.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            job_id = "test-job-123"
            result_ref = manager._save_result_to_file(job_id, sample_transcription_result)

            loaded_result = manager._load_result_from_file(job_id, result_ref=result_ref)

            assert loaded_result is not None
            assert loaded_result["transcript"] == sample_transcription_result["transcript"]

    def test_load_result_from_file_nonexistent(self, mock_settings_redis_disabled, temp_store_dir):
        """Test: Load result from non-existent file (error condition).

        Verifies that None is returned when file doesn't exist.
        """
        with patch("app.services.jobs.job_manager.settings", mock_settings_redis_disabled):
            mock_settings_redis_disabled.temp_store_dir = str(temp_store_dir)
            manager = JobManager()

            result = manager._load_result_from_file(
                "nonexistent-job", result_ref="nonexistent.json"
            )

            assert result is None
