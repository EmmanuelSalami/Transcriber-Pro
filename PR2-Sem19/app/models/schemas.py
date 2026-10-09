"""Pydantic schemas for request/response models."""

from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Language(str, Enum):
    """Supported language codes for transcription and translation (ISO 639-1).

    Enumeration of language codes supported by the transcription API.
    These codes follow the ISO 639-1 standard (2-letter codes) and are used
    for specifying target languages for translation.

    Attributes:
        All attributes are language codes as strings (e.g., EN = "en", ES = "es")

    Example:
        >>> Language.EN
        <Language.EN: 'en'>
        >>> Language.EN.value
        'en'
    """

    # Major languages
    EN = "en"  # English
    ES = "es"  # Spanish
    FR = "fr"  # French
    DE = "de"  # German
    IT = "it"  # Italian
    PT = "pt"  # Portuguese
    RU = "ru"  # Russian
    JA = "ja"  # Japanese
    KO = "ko"  # Korean
    ZH = "zh"  # Chinese
    AR = "ar"  # Arabic
    HI = "hi"  # Hindi
    TR = "tr"  # Turkish
    PL = "pl"  # Polish
    NL = "nl"  # Dutch
    SV = "sv"  # Swedish
    NO = "no"  # Norwegian
    DA = "da"  # Danish
    FI = "fi"  # Finnish
    CS = "cs"  # Czech
    HU = "hu"  # Hungarian
    RO = "ro"  # Romanian
    UK = "uk"  # Ukrainian
    VI = "vi"  # Vietnamese
    TH = "th"  # Thai
    ID = "id"  # Indonesian
    HE = "he"  # Hebrew
    EL = "el"  # Greek
    BG = "bg"  # Bulgarian
    HR = "hr"  # Croatian
    SR = "sr"  # Serbian
    SK = "sk"  # Slovak
    SL = "sl"  # Slovenian
    ET = "et"  # Estonian
    LV = "lv"  # Latvian
    LT = "lt"  # Lithuanian
    CA = "ca"  # Catalan
    EU = "eu"  # Basque
    GL = "gl"  # Galician
    IS = "is"  # Icelandic
    GA = "ga"  # Irish
    MT = "mt"  # Maltese
    MK = "mk"  # Macedonian
    SQ = "sq"  # Albanian
    BS = "bs"  # Bosnian
    MS = "ms"  # Malay
    TL = "tl"  # Tagalog
    SW = "sw"  # Swahili
    AF = "af"  # Afrikaans
    AZ = "az"  # Azerbaijani
    BE = "be"  # Belarusian
    BN = "bn"  # Bengali
    CY = "cy"  # Welsh
    FA = "fa"  # Persian
    GU = "gu"  # Gujarati
    KA = "ka"  # Georgian
    KN = "kn"  # Kannada
    ML = "ml"  # Malayalam
    MR = "mr"  # Marathi
    NE = "ne"  # Nepali
    PA = "pa"  # Punjabi
    SI = "si"  # Sinhala
    TA = "ta"  # Tamil
    TE = "te"  # Telugu
    UR = "ur"  # Urdu
    MY = "my"  # Burmese
    KM = "km"  # Khmer
    LO = "lo"  # Lao
    MN = "mn"  # Mongolian
    UZ = "uz"  # Uzbek
    KK = "kk"  # Kazakh
    KY = "ky"  # Kyrgyz
    HY = "hy"  # Armenian
    AM = "am"  # Amharic
    HA = "ha"  # Hausa
    YO = "yo"  # Yoruba
    ZU = "zu"  # Zulu
    XH = "xh"  # Xhosa


class OutputFormat(str, Enum):
    """Supported output formats for transcription results.

    Enumeration of available output formats for transcription results.
    Each format provides a different representation of the transcript data.

    Attributes:
        JSON (str): JSON format with full metadata and segments (default).
        TEXT (str): Plain text format with transcript text only.
        SRT (str): SubRip subtitle format (.srt).
        VTT (str): WebVTT subtitle format (.vtt).

    Example:
        >>> OutputFormat.JSON
        <OutputFormat.JSON: 'json'>
        >>> OutputFormat.JSON.value
        'json'
    """

    JSON = "json"
    TEXT = "text"
    SRT = "srt"
    VTT = "vtt"


class JobStatus(str, Enum):
    """Job processing status enumeration.

    Represents the current state of an asynchronous transcription job.
    Jobs progress through these states: QUEUED -> PROCESSING -> COMPLETED/FAILED.

    Attributes:
        QUEUED (str): Job has been created and is waiting to be processed.
        PROCESSING (str): Job is currently being processed.
        COMPLETED (str): Job has completed successfully.
        FAILED (str): Job has failed with an error.

    Example:
        >>> JobStatus.QUEUED
        <JobStatus.QUEUED: 'queued'>
        >>> JobStatus.QUEUED.value
        'queued'
    """

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobPriority(str, Enum):
    """Job priority enumeration for queue management.

    Used to prioritize jobs in the processing queue. Higher priority jobs
    are processed before lower priority jobs.

    Attributes:
        LOW (str): Low priority job (default).
        NORMAL (str): Normal priority job.
        HIGH (str): High priority job.

    Example:
        >>> JobPriority.HIGH
        <JobPriority.HIGH: 'high'>
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class WorkerStatus(str, Enum):
    """GPU worker status enumeration.

    Represents the current state of a GPU worker on Runpod.

    Attributes:
        IDLE (str): Worker is idle and ready to accept jobs.
        BUSY (str): Worker is currently processing a job.
        WARMING_UP (str): Worker is loading model and warming up.
        UNHEALTHY (str): Worker is unhealthy (no heartbeat, errors).

    Example:
        >>> WorkerStatus.IDLE
        <WorkerStatus.IDLE: 'idle'>
    """

    IDLE = "idle"
    BUSY = "busy"
    WARMING_UP = "warming_up"
    UNHEALTHY = "unhealthy"


class TranscriptionRequest(BaseModel):
    """Request model for YouTube transcription endpoint.

    Pydantic model for validating transcription API requests.
    Validates the YouTube URL and optional translation/format parameters.

    Attributes:
        url (HttpUrl): YouTube video URL (validated as HTTP/HTTPS URL).
        translate_to (Optional[Language]): Optional target language code for translation
            (ISO 639-1). If not provided, transcription will be in original language.
        format (Optional[OutputFormat]): Output format (default: JSON).
        diarise (Optional[bool]): Enable speaker diarization (forces ASR mode, Level 2 feature).
        webhook_url (Optional[HttpUrl]): Optional webhook callback URL for async jobs.

    Raises:
        ValidationError: If URL is invalid or parameters don't match expected types.

    Example:
        >>> request = TranscriptionRequest(
        ...     url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ...     translate_to=Language.EN,
        ...     format=OutputFormat.JSON,
        ...     webhook_url="https://example.com/callback"
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    url: HttpUrl = Field(..., description="YouTube video URL")
    translate_to: Optional[Language] = Field(
        None,
        alias="translateTo",
        description=(
            "Target language code for translation (ISO 639-1). "
            "If not provided, the transcription will be in the original language of the video. "
            "Supported languages: en, es, fr, de, it, pt, ru, ja, ko, zh, ar, hi, tr, pl, nl, sv, no, da, fi, "
            "cs, hu, ro, uk, vi, th, id, he, el, bg, hr, sr, sk, sl, et, lv, lt, ca, eu, gl, is, ga, mt, mk, "
            "sq, bs, ms, tl, sw, af, az, be, bn, cy, fa, gu, ka, kn, ml, mr, ne, pa, si, ta, te, ur, my, km, "
            "lo, mn, uz, kk, ky, hy, am, ha, yo, zu, xh"
        ),
    )
    format: Optional[OutputFormat] = Field(
        OutputFormat.JSON, description="Output format: json, text, srt, or vtt"
    )
    diarise: Optional[bool] = Field(
        False,
        description="Enable speaker diarization (forces ASR mode, Level 2 feature). "
        "When True, transcription will use ASR fallback even if captions are available.",
    )
    webhook_url: Optional[HttpUrl] = Field(
        None,
        alias="webhookUrl",
        description="Optional webhook callback URL. "
        "If provided, transcription result will be POSTed to this URL when job completes. "
        "Only used for async jobs (videos that require background processing).",
    )


class TranscriptSegment(BaseModel):
    """Represents a single segment of the transcript with timing information.

    Each segment contains a portion of the transcript text along with its
    start and end timestamps in seconds.

    Attributes:
        text (str): Transcript text for this segment.
        start (float): Start time in seconds (non-negative).
        end (float): End time in seconds (must be greater than start).

    Raises:
        ValidationError: If end time is not greater than start time.

    Example:
        >>> segment = TranscriptSegment(
        ...     text="Hello world",
        ...     start=0.0,
        ...     end=2.5
        ... )
        >>> segment.end > segment.start
        True
    """

    model_config = ConfigDict(populate_by_name=True)

    text: str = Field(..., description="Transcript text for this segment")
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")


class TranscriptionResponse(BaseModel):
    """Response model for successful transcription.

    Complete transcription response containing the full transcript, individual
    segments with timing, detected language, source information, video ID,
    confidence score, and video duration.

    Attributes:
        status (str): Status of transcription ("completed", "queued", "processing", "failed").
        jobId (Optional[str]): Job identifier if async processing, None for sync.
        source (str): Source of transcription ("youtube_captions" or "asr").
        language (str): Detected language code (ISO 639-1).
        confidence (Optional[float]): Confidence score (0.0-1.0), None if not available.
        transcript (str): Full transcript text (all segments joined).
        segments (List[TranscriptSegment]): List of transcript segments with timings.
        warnings (List[str]): List of warning messages.
        video_url (Optional[str]): Video URL if provided.

    Example:
        >>> response = TranscriptionResponse(
        ...     status="completed",
        ...     jobId=None,
        ...     source="asr",
        ...     language="en",
        ...     confidence=0.95,
        ...     transcript="Hello world",
        ...     segments=[TranscriptSegment(text="Hello world", start=0.0, end=2.0)],
        ...     warnings=[],
        ...     video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(
        ..., description="Status of transcription: 'completed', 'queued', 'processing', or 'failed'"
    )
    jobId: Optional[str] = Field(
        None,
        serialization_alias="jobId",
        description="Job identifier if async processing, None for sync",
    )
    source: str = Field(..., description="Source of transcription: 'youtube_captions' or 'asr'")
    language: str = Field(..., description="Detected language code (ISO 639-1)")
    confidence: Optional[float] = Field(
        None, description="Confidence score (0.0-1.0), None if not available"
    )
    transcript: str = Field(..., description="Full transcript text")
    segments: List[TranscriptSegment] = Field(
        ..., description="List of transcript segments with timings"
    )
    warnings: List[str] = Field(default_factory=list, description="List of warning messages")
    video_url: Optional[str] = Field(
        None, serialization_alias="videoUrl", description="Video URL if provided"
    )


class JobResponse(BaseModel):
    """Response model for async transcription job creation.

    Returned when a transcription job is created asynchronously (for long videos).
    Clients should poll the job status endpoint using the job_id.

    Attributes:
        job_id (str): Unique job identifier for polling status.
        status (JobStatus): Current job status (always "queued" on creation).
        created_at (str): Job creation timestamp (ISO 8601 format).
        video_id (str): YouTube video ID.
        video_url (Optional[str]): Video URL if provided.

    Example:
        >>> job = JobResponse(
        ...     job_id="123e4567-e89b-12d3-a456-426614174000",
        ...     status=JobStatus.QUEUED,
        ...     created_at="2024-01-01T12:00:00Z",
        ...     video_id="dQw4w9WgXcQ",
        ...     video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(..., serialization_alias="jobId", description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    created_at: str = Field(
        ..., serialization_alias="createdAt", description="Job creation timestamp (ISO 8601 format)"
    )
    video_id: str = Field(..., serialization_alias="videoId", description="YouTube video ID")
    video_url: Optional[str] = Field(
        None, serialization_alias="videoUrl", description="Video URL if provided"
    )


class JobStatusResponse(BaseModel):
    """Response model for job status check.

    Returned when querying the status of an async transcription job.
    Contains the current status, result (if completed), or error (if failed).

    Attributes:
        job_id (str): Unique job identifier.
        status (JobStatus): Current job status.
        created_at (str): Job creation timestamp (ISO 8601 format).
        completed_at (Optional[str]): Job completion timestamp (ISO 8601 format, None if not completed).
        result (Optional[Union[TranscriptionResponse, dict]]): Transcription result if completed.
        error (Optional[str]): Error message if failed.
        video_id (str): YouTube video ID.
        video_url (Optional[str]): Video URL if provided.
        source (Optional[str]): Source of transcription ("youtube_captions" or "asr", None until completed).
        language (Optional[str]): Detected language code (None until completed).
        confidence (Optional[float]): Confidence score (0.0-1.0, None until completed or not available).
        transcript (Optional[str]): Full transcript text (None until completed).
        segments (Optional[List[TranscriptSegment]]): List of transcript segments (None until completed).
        warnings (Optional[List[str]]): List of warning messages.

    Example:
        >>> status = JobStatusResponse(
        ...     job_id="123e4567-e89b-12d3-a456-426614174000",
        ...     status=JobStatus.COMPLETED,
        ...     created_at="2024-01-01T12:00:00Z",
        ...     completed_at="2024-01-01T12:05:00Z",
        ...     result={"transcript": "Hello world", ...},
        ...     video_id="dQw4w9WgXcQ",
        ...     video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ...     source="asr",
        ...     language="en",
        ...     confidence=0.95
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(..., serialization_alias="jobId", description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    created_at: str = Field(
        ..., serialization_alias="createdAt", description="Job creation timestamp (ISO 8601 format)"
    )
    completed_at: Optional[str] = Field(
        None,
        serialization_alias="completedAt",
        description="Job completion timestamp (ISO 8601 format)",
    )
    result: Optional[Union[TranscriptionResponse, dict]] = Field(
        None, description="Transcription result if completed"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    video_id: str = Field(..., serialization_alias="videoId", description="YouTube video ID")
    video_url: Optional[str] = Field(
        None, serialization_alias="videoUrl", description="Video URL if provided"
    )
    source: Optional[str] = Field(
        None,
        description="Source of transcription: 'youtube_captions' or 'asr' (None until completed)",
    )
    language: Optional[str] = Field(
        None, description="Detected language code (ISO 639-1, None until completed)"
    )
    confidence: Optional[float] = Field(
        None, description="Confidence score (0.0-1.0, None until completed or not available)"
    )
    transcript: Optional[str] = Field(
        None, description="Full transcript text (None until completed)"
    )
    segments: Optional[List[TranscriptSegment]] = Field(
        None, description="List of transcript segments (None until completed)"
    )
    warnings: Optional[List[str]] = Field(None, description="List of warning messages")


class JobSummary(BaseModel):
    """Summary model for a job in the jobs list.

    Contains minimal information about a job: its ID and current status.
    Used for listing all jobs without returning full job details.

    Attributes:
        job_id (str): Unique job identifier.
        status (str): Current job status ("queued", "processing", "completed", "failed").

    Example:
        >>> summary = JobSummary(
        ...     job_id="123e4567-e89b-12d3-a456-426614174000",
        ...     status="processing"
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(..., serialization_alias="jobId", description="Unique job identifier")
    status: str = Field(..., description="Current job status")


class JobsListResponse(BaseModel):
    """Response model for listing all jobs.

    Returns a list of all existing jobs with their IDs and statuses.

    Attributes:
        jobs (List[JobSummary]): List of job summaries with ID and status.
        total (int): Total number of jobs.

    Example:
        >>> response = JobsListResponse(
        ...     jobs=[
        ...         JobSummary(job_id="123e4567-e89b-12d3-a456-426614174000", status="completed"),
        ...         JobSummary(job_id="223e4567-e89b-12d3-a456-426614174001", status="processing")
        ...     ],
        ...     total=2
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    jobs: List[JobSummary] = Field(..., description="List of job summaries")
    total: int = Field(..., description="Total number of jobs")


class ErrorResponse(BaseModel):
    """Standard error response model.

    Consistent error response format used across all API error handlers.
    Provides error code, human-readable message, and optional additional details.

    Attributes:
        code (str): Error code for programmatic error handling.
        message (str): Human-readable error message.
        details (dict): Additional error details (default: empty dict).

    Example:
        >>> error = ErrorResponse(
        ...     code="CAPTIONS_NOT_AVAILABLE",
        ...     message="No captions available for this video",
        ...     details={"video_id": "dQw4w9WgXcQ"}
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict = Field(default_factory=dict, description="Additional error details")


class WorkerInfo(BaseModel):
    """Information about a GPU worker.

    Contains metadata about a worker including its status, Runpod pod ID,
    current job assignment, and health information.

    Attributes:
        worker_id (str): Unique worker identifier.
        status (WorkerStatus): Current worker status.
        runpod_pod_id (str): Runpod pod ID for this worker.
        gpu_type (str): GPU type (e.g., "RTX 4090", "A100").
        current_job_id (Optional[str]): ID of job currently being processed, None if idle.
        last_heartbeat (str): ISO 8601 timestamp of last heartbeat.
        model_loaded (bool): Whether the Whisper model is loaded and ready.
        jobs_processed (int): Total number of jobs processed by this worker.
        total_gpu_hours (float): Total GPU hours consumed by this worker.

    Example:
        >>> worker = WorkerInfo(
        ...     worker_id="worker-123",
        ...     status=WorkerStatus.IDLE,
        ...     runpod_pod_id="pod-abc",
        ...     gpu_type="RTX 4090",
        ...     current_job_id=None,
        ...     last_heartbeat="2024-01-01T12:00:00Z",
        ...     model_loaded=True,
        ...     jobs_processed=10,
        ...     total_gpu_hours=2.5
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    worker_id: str = Field(..., description="Unique worker identifier")
    status: WorkerStatus = Field(..., description="Current worker status")
    runpod_pod_id: str = Field(..., description="Runpod pod ID for this worker")
    gpu_type: str = Field(..., description="GPU type (e.g., RTX 4090, A100)")
    current_job_id: Optional[str] = Field(
        None, serialization_alias="currentJobId", description="ID of job currently being processed"
    )
    last_heartbeat: str = Field(
        ..., serialization_alias="lastHeartbeat", description="ISO 8601 timestamp of last heartbeat"
    )
    model_loaded: bool = Field(
        ..., serialization_alias="modelLoaded", description="Whether the Whisper model is loaded"
    )
    jobs_processed: int = Field(
        default=0, serialization_alias="jobsProcessed", description="Total jobs processed"
    )
    total_gpu_hours: float = Field(
        default=0.0, serialization_alias="totalGpuHours", description="Total GPU hours consumed"
    )


class EnhancedJobData(BaseModel):
    """Enhanced job data with queue and worker management fields.

    Extends basic job data with priority, retry information, storage paths,
    and worker assignment for Level 3 distributed processing.

    Attributes:
        job_id (str): Unique job identifier.
        priority (JobPriority): Job priority (low, normal, high).
        retry_count (int): Current retry attempt number.
        max_retries (int): Maximum number of retry attempts.
        media_storage_path (Optional[str]): S3 path to uploaded media file.
        result_storage_path (Optional[str]): S3 path to transcription result.
        assigned_worker_id (Optional[str]): ID of worker assigned to process this job.
        queue_position (Optional[int]): Position in queue (for monitoring).
        estimated_processing_time (Optional[float]): Estimated processing time in seconds.

    Example:
        >>> job_data = EnhancedJobData(
        ...     job_id="job-123",
        ...     priority=JobPriority.NORMAL,
        ...     retry_count=0,
        ...     max_retries=3,
        ...     media_storage_path="s3://bucket/media/job-123.mp3",
        ...     assigned_worker_id="worker-456"
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(..., serialization_alias="jobId", description="Unique job identifier")
    priority: JobPriority = Field(
        default=JobPriority.NORMAL, description="Job priority (low, normal, high)"
    )
    retry_count: int = Field(
        default=0, serialization_alias="retryCount", description="Current retry attempt number"
    )
    max_retries: int = Field(
        default=3, serialization_alias="maxRetries", description="Maximum number of retry attempts"
    )
    media_storage_path: Optional[str] = Field(
        None,
        serialization_alias="mediaStoragePath",
        description="S3 path to uploaded media file",
    )
    result_storage_path: Optional[str] = Field(
        None,
        serialization_alias="resultStoragePath",
        description="S3 path to transcription result",
    )
    assigned_worker_id: Optional[str] = Field(
        None,
        serialization_alias="assignedWorkerId",
        description="ID of worker assigned to process this job",
    )
    queue_position: Optional[int] = Field(
        None, serialization_alias="queuePosition", description="Position in queue"
    )
    estimated_processing_time: Optional[float] = Field(
        None,
        serialization_alias="estimatedProcessingTime",
        description="Estimated processing time in seconds",
    )


class CostMetrics(BaseModel):
    """Cost tracking metrics for GPU workers.

    Tracks total costs, GPU hours, and budget information for monitoring
    and cost control.

    Attributes:
        total_gpu_hours (float): Total GPU hours consumed across all workers.
        cost_per_job (float): Average cost per job in USD.
        total_cost (float): Total cost in USD.
        budget_remaining (float): Remaining budget in USD.
        jobs_processed (int): Total number of jobs processed.
        active_workers (int): Current number of active workers.

    Example:
        >>> metrics = CostMetrics(
        ...     total_gpu_hours=100.5,
        ...     cost_per_job=0.05,
        ...     total_cost=50.25,
        ...     budget_remaining=49.75,
        ...     jobs_processed=1005,
        ...     active_workers=3
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    total_gpu_hours: float = Field(
        ..., serialization_alias="totalGpuHours", description="Total GPU hours consumed"
    )
    cost_per_job: float = Field(
        ..., serialization_alias="costPerJob", description="Average cost per job in USD"
    )
    total_cost: float = Field(..., serialization_alias="totalCost", description="Total cost in USD")
    budget_remaining: float = Field(
        ..., serialization_alias="budgetRemaining", description="Remaining budget in USD"
    )
    jobs_processed: int = Field(
        ..., serialization_alias="jobsProcessed", description="Total number of jobs processed"
    )
    active_workers: int = Field(
        ..., serialization_alias="activeWorkers", description="Current number of active workers"
    )


class MediaTranscriptionRequest(BaseModel):
    """Request model for remote media URL transcription endpoint.

    Pydantic model for validating media transcription API requests from remote URLs.
    Validates the media URL and optional translation/format/webhook parameters.

    Attributes:
        url (HttpUrl): Remote media URL (HTTP/HTTPS, not YouTube).
        translate_to (Optional[Language]): Optional target language code for translation
            (ISO 639-1). If not provided, transcription will be in original language.
        format (Optional[OutputFormat]): Output format (default: JSON).
        diarise (Optional[bool]): Enable speaker diarization (forces ASR mode).
        webhook_url (Optional[HttpUrl]): Optional webhook callback URL for async jobs.
            If provided, result will be POSTed to this URL when job completes.

    Raises:
        ValidationError: If URL is invalid or parameters don't match expected types.

    Example:
        >>> request = MediaTranscriptionRequest(
        ...     url="https://cdn.example.com/audio.mp3",
        ...     translate_to=Language.EN,
        ...     format=OutputFormat.JSON,
        ...     webhook_url="https://example.com/callback"
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    url: HttpUrl = Field(..., description="Remote media URL (HTTP/HTTPS, not YouTube)")
    translate_to: Optional[Language] = Field(
        None,
        alias="translateTo",
        description=(
            "Target language code for translation (ISO 639-1). "
            "If not provided, the transcription will be in the original language of the media. "
            "Supported languages: en, es, fr, de, it, pt, ru, ja, ko, zh, ar, hi, tr, pl, nl, sv, no, da, fi, "
            "cs, hu, ro, uk, vi, th, id, he, el, bg, hr, sr, sk, sl, et, lv, lt, ca, eu, gl, is, ga, mt, mk, "
            "sq, bs, ms, tl, sw, af, az, be, bn, cy, fa, gu, ka, kn, ml, mr, ne, pa, si, ta, te, ur, my, km, "
            "lo, mn, uz, kk, ky, hy, am, ha, yo, zu, xh"
        ),
    )
    format: Optional[OutputFormat] = Field(
        OutputFormat.JSON, description="Output format: json, text, srt, or vtt"
    )
    diarise: Optional[bool] = Field(
        False,
        description="Enable speaker diarization (forces ASR mode). "
        "When True, transcription will use ASR even if other methods are available.",
    )
    webhook_url: Optional[HttpUrl] = Field(
        None,
        alias="webhookUrl",
        description="Optional webhook callback URL. "
        "If provided, transcription result will be POSTed to this URL when job completes. "
        "Only used for async jobs (media files that require background processing).",
    )
