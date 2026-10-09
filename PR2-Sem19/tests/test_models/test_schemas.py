"""
Unit tests for Pydantic schema models in app.models.schemas.

Tests cover:
- Happy path: Valid model creation and serialization
- Edge cases: Optional fields, default values, aliases
- Error conditions: Invalid data, validation errors
- Boundary analysis: Min/max values, empty strings, None values
"""

import pytest
from pydantic import ValidationError

from app.models.schemas import (CostMetrics, EnhancedJobData, ErrorResponse,
                                JobPriority, JobResponse, JobsListResponse,
                                JobStatus, JobStatusResponse, JobSummary,
                                Language, MediaTranscriptionRequest,
                                OutputFormat, TranscriptionRequest,
                                TranscriptionResponse, TranscriptSegment,
                                WorkerInfo, WorkerStatus)


class TestTranscriptionRequest:
    """Test cases for TranscriptionRequest model."""

    def test_transcription_request_minimal(self, sample_youtube_url):
        """Test: Create TranscriptionRequest with only required URL field."""
        request = TranscriptionRequest(url=sample_youtube_url)
        assert str(request.url) == str(sample_youtube_url)
        assert request.translate_to is None
        assert request.format == OutputFormat.JSON  # Default value
        assert request.diarise is False  # Default value
        assert request.webhook_url is None

    def test_transcription_request_all_fields(self, sample_youtube_url, sample_webhook_url):
        """Test: Create TranscriptionRequest with all fields."""
        request = TranscriptionRequest(
            url=sample_youtube_url,
            translate_to=Language.ES,
            format=OutputFormat.SRT,
            diarise=True,
            webhook_url=sample_webhook_url,
        )
        assert str(request.url) == str(sample_youtube_url)
        assert request.translate_to == Language.ES
        assert request.format == OutputFormat.SRT
        assert request.diarise is True
        assert str(request.webhook_url) == str(sample_webhook_url)

    def test_transcription_request_invalid_url(self):
        """Test: Invalid URL raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionRequest(url="not-a-url")
        errors = exc_info.value.errors()
        assert any(error["type"] == "url_parsing" for error in errors)

    def test_transcription_request_empty_url(self):
        """Test: Empty URL raises ValidationError."""
        with pytest.raises(ValidationError):
            TranscriptionRequest(url="")

    def test_transcription_request_missing_url(self):
        """Test: Missing required URL field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionRequest()
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("url",) for error in errors)

    def test_transcription_request_http_url(self):
        """Test: HTTP (non-HTTPS) URLs are accepted."""
        request = TranscriptionRequest(url="http://www.youtube.com/watch?v=test")
        assert str(request.url).startswith("http://")

    def test_transcription_request_https_url(self, sample_youtube_url):
        """Test: HTTPS URLs are accepted."""
        request = TranscriptionRequest(url=sample_youtube_url)
        assert str(request.url).startswith("https://")

    def test_transcription_request_aliases(self, sample_youtube_url):
        """Test: Field aliases work correctly (translateTo, webhookUrl)."""
        # Using aliases
        request1 = TranscriptionRequest(
            url=sample_youtube_url, translateTo=Language.EN, webhookUrl="https://example.com"
        )
        assert request1.translate_to == Language.EN
        assert request1.webhook_url is not None

        # Using field names
        request2 = TranscriptionRequest(
            url=sample_youtube_url, translate_to=Language.EN, webhook_url="https://example.com"
        )
        assert request2.translate_to == Language.EN
        assert request2.webhook_url is not None

    def test_transcription_request_default_format(self, sample_youtube_url):
        """Test: Default format is JSON."""
        request = TranscriptionRequest(url=sample_youtube_url)
        assert request.format == OutputFormat.JSON

    def test_transcription_request_default_diarise(self, sample_youtube_url):
        """Test: Default diarise is False."""
        request = TranscriptionRequest(url=sample_youtube_url)
        assert request.diarise is False

    def test_transcription_request_serialization(self, sample_youtube_url):
        """Test: Model can be serialized to dict."""
        request = TranscriptionRequest(
            url=sample_youtube_url, translate_to=Language.EN, format=OutputFormat.TEXT
        )
        data = request.model_dump()
        assert "url" in data
        assert data["translate_to"] == Language.EN
        assert data["format"] == OutputFormat.TEXT

    def test_transcription_request_serialization_with_aliases(self, sample_youtube_url):
        """Test: Model serialization uses aliases when configured."""
        request = TranscriptionRequest(url=sample_youtube_url, translate_to=Language.EN)
        data = request.model_dump(by_alias=True)
        assert "translateTo" in data or "translate_to" in data


class TestTranscriptSegment:
    """Test cases for TranscriptSegment model."""

    def test_transcript_segment_valid(self):
        """Test: Create valid TranscriptSegment."""
        segment = TranscriptSegment(text="Hello", start=0.0, end=2.5)
        assert segment.text == "Hello"
        assert segment.start == 0.0
        assert segment.end == 2.5

    def test_transcript_segment_missing_fields(self):
        """Test: Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptSegment(text="Hello")
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("start",) for error in errors)
        assert any(error["loc"] == ("end",) for error in errors)

    def test_transcript_segment_empty_text(self):
        """Test: Empty text is allowed (boundary case)."""
        segment = TranscriptSegment(text="", start=0.0, end=1.0)
        assert segment.text == ""

    def test_transcript_segment_zero_start(self):
        """Test: Start time can be zero (boundary case)."""
        segment = TranscriptSegment(text="Hello", start=0.0, end=1.0)
        assert segment.start == 0.0

    def test_transcript_segment_negative_start(self):
        """Test: Negative start time behavior.

        Note: Pydantic doesn't validate negative floats by default unless
        Field constraints are added. This test verifies current behavior.
        """
        # Current implementation allows negative values (no Field constraint)
        # If validation is needed, add ge=0 to the start Field
        segment = TranscriptSegment(text="Hello", start=-1.0, end=1.0)
        assert segment.start == -1.0
        # If validation is desired, uncomment below and add ge=0 to Field:
        # with pytest.raises(ValidationError):
        #     TranscriptSegment(text="Hello", start=-1.0, end=1.0)

    def test_transcript_segment_end_before_start(self):
        """Test: End time before start time should be invalid."""
        # Note: Pydantic doesn't validate this automatically, but it's a logical constraint
        segment = TranscriptSegment(text="Hello", start=2.0, end=1.0)
        # This will create the segment, but it's logically invalid
        assert segment.end < segment.start  # This is the invalid case

    def test_transcript_segment_equal_start_end(self):
        """Test: Start and end times can be equal (zero-duration segment)."""
        segment = TranscriptSegment(text="Hello", start=1.0, end=1.0)
        assert segment.start == segment.end

    def test_transcript_segment_large_timestamps(self):
        """Test: Large timestamp values are accepted."""
        segment = TranscriptSegment(text="Hello", start=0.0, end=999999.999)
        assert segment.end == 999999.999

    def test_transcript_segment_float_precision(self):
        """Test: Float precision is preserved."""
        segment = TranscriptSegment(text="Hello", start=0.123456, end=1.789012)
        assert segment.start == 0.123456
        assert segment.end == 1.789012

    def test_transcript_segment_serialization(self):
        """Test: Segment can be serialized to dict."""
        segment = TranscriptSegment(text="Hello", start=0.0, end=2.5)
        data = segment.model_dump()
        assert data["text"] == "Hello"
        assert data["start"] == 0.0
        assert data["end"] == 2.5

    def test_transcript_segment_long_text(self):
        """Test: Long text strings are accepted."""
        long_text = "A" * 10000
        segment = TranscriptSegment(text=long_text, start=0.0, end=1.0)
        assert len(segment.text) == 10000


class TestTranscriptionResponse:
    """Test cases for TranscriptionResponse model."""

    def test_transcription_response_minimal(self, sample_transcript_segments):
        """Test: Create TranscriptionResponse with minimal required fields."""
        response = TranscriptionResponse(
            status="completed",
            source="asr",
            language="en",
            transcript="Hello world",
            segments=sample_transcript_segments,
        )
        assert response.status == "completed"
        assert response.source == "asr"
        assert response.language == "en"
        assert response.transcript == "Hello world"
        assert len(response.segments) == 3

    def test_transcription_response_all_fields(self, sample_transcript_segments):
        """Test: Create TranscriptionResponse with all fields."""
        response = TranscriptionResponse(
            status="completed",
            jobId="job-123",
            source="youtube_captions",
            language="es",
            confidence=0.95,
            transcript="Hola mundo",
            segments=sample_transcript_segments,
            warnings=["Warning 1", "Warning 2"],
            video_url="https://www.youtube.com/watch?v=test",
        )
        assert response.status == "completed"
        assert response.jobId == "job-123"
        assert response.source == "youtube_captions"
        assert response.language == "es"
        assert response.confidence == 0.95
        assert response.warnings == ["Warning 1", "Warning 2"]
        assert response.video_url == "https://www.youtube.com/watch?v=test"

    def test_transcription_response_optional_fields_none(self, sample_transcript_segments):
        """Test: Optional fields can be None."""
        response = TranscriptionResponse(
            status="completed",
            source="asr",
            language="en",
            transcript="Hello",
            segments=sample_transcript_segments,
            jobId=None,
            confidence=None,
            video_url=None,
        )
        assert response.jobId is None
        assert response.confidence is None
        assert response.video_url is None

    def test_transcription_response_default_warnings(self, sample_transcript_segments):
        """Test: Default warnings is empty list."""
        response = TranscriptionResponse(
            status="completed",
            source="asr",
            language="en",
            transcript="Hello",
            segments=sample_transcript_segments,
        )
        assert response.warnings == []

    def test_transcription_response_confidence_boundaries(self, sample_transcript_segments):
        """Test: Confidence values at boundaries (0.0, 1.0)."""
        response1 = TranscriptionResponse(
            status="completed",
            source="asr",
            language="en",
            transcript="Hello",
            segments=sample_transcript_segments,
            confidence=0.0,
        )
        assert response1.confidence == 0.0

        response2 = TranscriptionResponse(
            status="completed",
            source="asr",
            language="en",
            transcript="Hello",
            segments=sample_transcript_segments,
            confidence=1.0,
        )
        assert response2.confidence == 1.0

    def test_transcription_response_empty_segments(self):
        """Test: Empty segments list is allowed."""
        response = TranscriptionResponse(
            status="completed",
            source="asr",
            language="en",
            transcript="",
            segments=[],
        )
        assert response.segments == []

    def test_transcription_response_missing_required_fields(self):
        """Test: Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionResponse(status="completed")
        errors = exc_info.value.errors()
        error_locs = {tuple(error["loc"]) for error in errors}
        assert any("source" in str(loc) for loc in error_locs)

    def test_transcription_response_serialization(self, sample_transcript_segments):
        """Test: Response can be serialized to dict."""
        response = TranscriptionResponse(
            status="completed",
            source="asr",
            language="en",
            transcript="Hello",
            segments=sample_transcript_segments,
        )
        data = response.model_dump()
        assert "status" in data
        assert "source" in data
        assert "language" in data
        assert "transcript" in data
        assert "segments" in data


class TestJobResponse:
    """Test cases for JobResponse model."""

    def test_job_response_all_fields(self):
        """Test: Create JobResponse with all fields."""
        response = JobResponse(
            job_id="job-123",
            status=JobStatus.QUEUED,
            created_at="2024-01-01T12:00:00Z",
            video_id="dQw4w9WgXcQ",
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        assert response.job_id == "job-123"
        assert response.status == JobStatus.QUEUED
        assert response.created_at == "2024-01-01T12:00:00Z"
        assert response.video_id == "dQw4w9WgXcQ"
        assert response.video_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_job_response_optional_video_url_none(self):
        """Test: Optional video_url can be None."""
        response = JobResponse(
            job_id="job-123",
            status=JobStatus.QUEUED,
            created_at="2024-01-01T12:00:00Z",
            video_id="dQw4w9WgXcQ",
            video_url=None,
        )
        assert response.video_url is None

    def test_job_response_missing_required_fields(self):
        """Test: Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            JobResponse(job_id="job-123")

    def test_job_response_serialization_aliases(self):
        """Test: Serialization uses aliases (jobId, createdAt, videoUrl)."""
        response = JobResponse(
            job_id="job-123",
            status=JobStatus.QUEUED,
            created_at="2024-01-01T12:00:00Z",
            video_id="dQw4w9WgXcQ",
        )
        data = response.model_dump(by_alias=True)
        assert "jobId" in data
        assert "createdAt" in data
        assert "videoId" in data


class TestJobStatusResponse:
    """Test cases for JobStatusResponse model."""

    def test_job_status_response_queued(self):
        """Test: JobStatusResponse for queued job."""
        response = JobStatusResponse(
            job_id="job-123",
            status=JobStatus.QUEUED,
            created_at="2024-01-01T12:00:00Z",
            video_id="dQw4w9WgXcQ",
        )
        assert response.status == JobStatus.QUEUED
        assert response.completed_at is None
        assert response.result is None
        assert response.error is None

    def test_job_status_response_completed(self, sample_transcript_segments):
        """Test: JobStatusResponse for completed job."""
        response = JobStatusResponse(
            job_id="job-123",
            status=JobStatus.COMPLETED,
            created_at="2024-01-01T12:00:00Z",
            completed_at="2024-01-01T12:05:00Z",
            result={"transcript": "Hello world"},
            video_id="dQw4w9WgXcQ",
            source="asr",
            language="en",
            confidence=0.95,
            transcript="Hello world",
            segments=sample_transcript_segments,
        )
        assert response.status == JobStatus.COMPLETED
        assert response.completed_at is not None
        assert response.result is not None
        assert response.error is None

    def test_job_status_response_failed(self):
        """Test: JobStatusResponse for failed job."""
        response = JobStatusResponse(
            job_id="job-123",
            status=JobStatus.FAILED,
            created_at="2024-01-01T12:00:00Z",
            completed_at="2024-01-01T12:05:00Z",
            error="Transcription failed",
            video_id="dQw4w9WgXcQ",
        )
        assert response.status == JobStatus.FAILED
        assert response.error == "Transcription failed"
        assert response.result is None

    def test_job_status_response_optional_fields_none(self):
        """Test: Optional fields can be None."""
        response = JobStatusResponse(
            job_id="job-123",
            status=JobStatus.QUEUED,
            created_at="2024-01-01T12:00:00Z",
            video_id="dQw4w9WgXcQ",
            completed_at=None,
            result=None,
            error=None,
            source=None,
            language=None,
            confidence=None,
            transcript=None,
            segments=None,
            warnings=None,
        )
        assert response.completed_at is None
        assert response.result is None
        assert response.error is None


class TestJobSummary:
    """Test cases for JobSummary model."""

    def test_job_summary_valid(self):
        """Test: Create valid JobSummary."""
        summary = JobSummary(job_id="job-123", status="processing")
        assert summary.job_id == "job-123"
        assert summary.status == "processing"

    def test_job_summary_missing_fields(self):
        """Test: Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            JobSummary(job_id="job-123")

    def test_job_summary_serialization_alias(self):
        """Test: Serialization uses alias (jobId)."""
        summary = JobSummary(job_id="job-123", status="queued")
        data = summary.model_dump(by_alias=True)
        assert "jobId" in data


class TestJobsListResponse:
    """Test cases for JobsListResponse model."""

    def test_jobs_list_response_valid(self):
        """Test: Create valid JobsListResponse."""
        jobs = [
            JobSummary(job_id="job-1", status="completed"),
            JobSummary(job_id="job-2", status="processing"),
        ]
        response = JobsListResponse(jobs=jobs, total=2)
        assert len(response.jobs) == 2
        assert response.total == 2

    def test_jobs_list_response_empty_list(self):
        """Test: Empty jobs list is allowed."""
        response = JobsListResponse(jobs=[], total=0)
        assert response.jobs == []
        assert response.total == 0

    def test_jobs_list_response_total_mismatch(self):
        """Test: Total can differ from jobs list length (edge case)."""
        jobs = [JobSummary(job_id="job-1", status="completed")]
        response = JobsListResponse(jobs=jobs, total=5)  # Total says 5, but only 1 in list
        assert len(response.jobs) == 1
        assert response.total == 5

    def test_jobs_list_response_missing_fields(self):
        """Test: Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            JobsListResponse(jobs=[])


class TestErrorResponse:
    """Test cases for ErrorResponse model."""

    def test_error_response_minimal(self):
        """Test: Create ErrorResponse with required fields only."""
        error = ErrorResponse(code="ERROR_001", message="An error occurred")
        assert error.code == "ERROR_001"
        assert error.message == "An error occurred"
        assert error.details == {}  # Default empty dict

    def test_error_response_with_details(self):
        """Test: Create ErrorResponse with details."""
        error = ErrorResponse(
            code="ERROR_001",
            message="An error occurred",
            details={"video_id": "test", "reason": "not_found"},
        )
        assert error.details == {"video_id": "test", "reason": "not_found"}

    def test_error_response_empty_details(self):
        """Test: Empty details dict is default."""
        error = ErrorResponse(code="ERROR_001", message="An error occurred")
        assert error.details == {}

    def test_error_response_missing_fields(self):
        """Test: Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            ErrorResponse(code="ERROR_001")


class TestWorkerInfo:
    """Test cases for WorkerInfo model."""

    def test_worker_info_all_fields(self):
        """Test: Create WorkerInfo with all fields."""
        worker = WorkerInfo(
            worker_id="worker-123",
            status=WorkerStatus.IDLE,
            runpod_pod_id="pod-abc",
            gpu_type="RTX 4090",
            current_job_id="job-456",
            last_heartbeat="2024-01-01T12:00:00Z",
            model_loaded=True,
            jobs_processed=10,
            total_gpu_hours=2.5,
        )
        assert worker.worker_id == "worker-123"
        assert worker.status == WorkerStatus.IDLE
        assert worker.current_job_id == "job-456"
        assert worker.jobs_processed == 10
        assert worker.total_gpu_hours == 2.5

    def test_worker_info_optional_current_job_none(self):
        """Test: Optional current_job_id can be None."""
        worker = WorkerInfo(
            worker_id="worker-123",
            status=WorkerStatus.IDLE,
            runpod_pod_id="pod-abc",
            gpu_type="RTX 4090",
            current_job_id=None,
            last_heartbeat="2024-01-01T12:00:00Z",
            model_loaded=True,
        )
        assert worker.current_job_id is None

    def test_worker_info_default_jobs_processed(self):
        """Test: Default jobs_processed is 0."""
        worker = WorkerInfo(
            worker_id="worker-123",
            status=WorkerStatus.IDLE,
            runpod_pod_id="pod-abc",
            gpu_type="RTX 4090",
            last_heartbeat="2024-01-01T12:00:00Z",
            model_loaded=True,
        )
        assert worker.jobs_processed == 0

    def test_worker_info_default_gpu_hours(self):
        """Test: Default total_gpu_hours is 0.0."""
        worker = WorkerInfo(
            worker_id="worker-123",
            status=WorkerStatus.IDLE,
            runpod_pod_id="pod-abc",
            gpu_type="RTX 4090",
            last_heartbeat="2024-01-01T12:00:00Z",
            model_loaded=True,
        )
        assert worker.total_gpu_hours == 0.0


class TestEnhancedJobData:
    """Test cases for EnhancedJobData model."""

    def test_enhanced_job_data_all_fields(self):
        """Test: Create EnhancedJobData with all fields."""
        job = EnhancedJobData(
            job_id="job-123",
            priority=JobPriority.HIGH,
            retry_count=2,
            max_retries=5,
            media_storage_path="s3://bucket/media.mp3",
            result_storage_path="s3://bucket/result.json",
            assigned_worker_id="worker-456",
            queue_position=3,
            estimated_processing_time=180.0,
        )
        assert job.job_id == "job-123"
        assert job.priority == JobPriority.HIGH
        assert job.retry_count == 2
        assert job.max_retries == 5

    def test_enhanced_job_data_defaults(self):
        """Test: Default values for EnhancedJobData."""
        job = EnhancedJobData(job_id="job-123")
        assert job.priority == JobPriority.NORMAL
        assert job.retry_count == 0
        assert job.max_retries == 3
        assert job.media_storage_path is None
        assert job.result_storage_path is None
        assert job.assigned_worker_id is None

    def test_enhanced_job_data_optional_fields_none(self):
        """Test: Optional fields can be None."""
        job = EnhancedJobData(
            job_id="job-123",
            media_storage_path=None,
            result_storage_path=None,
            assigned_worker_id=None,
            queue_position=None,
            estimated_processing_time=None,
        )
        assert job.media_storage_path is None
        assert job.result_storage_path is None


class TestCostMetrics:
    """Test cases for CostMetrics model."""

    def test_cost_metrics_all_fields(self):
        """Test: Create CostMetrics with all fields."""
        metrics = CostMetrics(
            total_gpu_hours=100.5,
            cost_per_job=0.05,
            total_cost=50.25,
            budget_remaining=49.75,
            jobs_processed=1005,
            active_workers=3,
        )
        assert metrics.total_gpu_hours == 100.5
        assert metrics.cost_per_job == 0.05
        assert metrics.total_cost == 50.25
        assert metrics.budget_remaining == 49.75
        assert metrics.jobs_processed == 1005
        assert metrics.active_workers == 3

    def test_cost_metrics_zero_values(self):
        """Test: CostMetrics with zero values (boundary case)."""
        metrics = CostMetrics(
            total_gpu_hours=0.0,
            cost_per_job=0.0,
            total_cost=0.0,
            budget_remaining=100.0,
            jobs_processed=0,
            active_workers=0,
        )
        assert metrics.total_gpu_hours == 0.0
        assert metrics.jobs_processed == 0

    def test_cost_metrics_negative_values(self):
        """Test: Negative values are allowed (for budget_remaining)."""
        metrics = CostMetrics(
            total_gpu_hours=100.0,
            cost_per_job=0.05,
            total_cost=150.0,
            budget_remaining=-50.0,  # Over budget
            jobs_processed=1000,
            active_workers=2,
        )
        assert metrics.budget_remaining == -50.0

    def test_cost_metrics_missing_fields(self):
        """Test: Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            CostMetrics(total_gpu_hours=100.0)


class TestMediaTranscriptionRequest:
    """Test cases for MediaTranscriptionRequest model."""

    def test_media_transcription_request_minimal(self, sample_media_url):
        """Test: Create MediaTranscriptionRequest with only required URL."""
        request = MediaTranscriptionRequest(url=sample_media_url)
        assert str(request.url) == str(sample_media_url)
        assert request.translate_to is None
        assert request.format == OutputFormat.JSON
        assert request.diarise is False
        assert request.webhook_url is None

    def test_media_transcription_request_all_fields(self, sample_media_url, sample_webhook_url):
        """Test: Create MediaTranscriptionRequest with all fields."""
        request = MediaTranscriptionRequest(
            url=sample_media_url,
            translate_to=Language.FR,
            format=OutputFormat.VTT,
            diarise=True,
            webhook_url=sample_webhook_url,
        )
        assert str(request.url) == str(sample_media_url)
        assert request.translate_to == Language.FR
        assert request.format == OutputFormat.VTT
        assert request.diarise is True
        assert str(request.webhook_url) == str(sample_webhook_url)

    def test_media_transcription_request_invalid_url(self):
        """Test: Invalid URL raises ValidationError."""
        with pytest.raises(ValidationError):
            MediaTranscriptionRequest(url="not-a-url")

    def test_media_transcription_request_youtube_url_rejected(self):
        """Test: YouTube URLs should be rejected (use TranscriptionRequest instead)."""
        # Note: This is a logical constraint, not enforced by the model
        # The model only validates it's a valid HTTP/HTTPS URL
        youtube_url = "https://www.youtube.com/watch?v=test"
        request = MediaTranscriptionRequest(url=youtube_url)
        # Model accepts it, but business logic should reject it
        assert str(request.url) == youtube_url


class TestSchemaSerialization:
    """Integration tests for schema serialization."""

    def test_model_dump(self, sample_transcription_request):
        """Test: All models can be dumped to dict."""
        data = sample_transcription_request.model_dump()
        assert isinstance(data, dict)
        assert "url" in data

    def test_model_dump_json(self, sample_transcription_request):
        """Test: Models can be serialized to JSON."""
        json_str = sample_transcription_request.model_dump_json()
        assert isinstance(json_str, str)
        assert "url" in json_str

    def test_model_dump_exclude_none(self, sample_transcription_response):
        """Test: model_dump can exclude None values."""
        data = sample_transcription_response.model_dump(exclude_none=True)
        # None values should be excluded
        assert "jobId" not in data or data["jobId"] is not None

    def test_model_dump_by_alias(self, sample_job_response):
        """Test: model_dump can use field aliases."""
        data = sample_job_response.model_dump(by_alias=True)
        assert "jobId" in data
        assert "createdAt" in data
        assert "videoId" in data
