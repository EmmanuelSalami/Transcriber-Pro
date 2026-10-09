"""Application configuration settings."""

import logging
import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    This class manages all configuration settings for the YouTube Transcription API,
    including API configuration, security settings, rate limiting, and CORS configuration.
    Settings are loaded from environment variables or a .env file.

    Attributes:
        api_title (str): Title of the API (default: "YouTube Transcription API")
        api_version (str): API version string (default: "v1")
        api_prefix (str): API URL prefix (default: "/v1")
        api_keys (str): Comma-separated list of valid API keys (REQUIRED in production)
        secret_key (str): Secret key for JWT token signing (REQUIRED in production)
        rate_limit_per_minute (int): Default rate limit per API key per minute (default: 60)
        cors_origins (str): Comma-separated list of allowed CORS origins (default: "*")

    Example:
        Settings are automatically loaded from environment variables:
        >>> settings = Settings()
        >>> settings.api_version
        'v1'
        >>> settings.get_api_keys()
        ['key1', 'key2']
    """

    # API Configuration
    api_title: str = "YouTube Transcription API"
    api_version: str = "v1"
    api_prefix: str = "/v1"

    # Security
    api_keys: str = Field(
        default="",
        description="Comma-separated list of valid API keys (REQUIRED in production)",
    )
    secret_key: str = Field(
        default="", description="Secret key for JWT token signing (REQUIRED in production)"
    )

    # Rate Limiting
    rate_limit_per_minute: int = Field(
        default=60, description="Default rate limit per API key per minute"
    )

    # YouTube Configuration

    # === ASR Configuration (Plan B) ===

    # Whisper Model Settings
    whisper_model: str = Field(
        default="openai/whisper-base",
        description="Hugging Face Whisper model ID (base, small, medium, large-v3). "
        "Options: openai/whisper-base, openai/whisper-small, openai/whisper-medium, openai/whisper-large-v3. "
        "If whisper_model_path is set, this is used as fallback identifier.",
    )
    whisper_model_path: str = Field(
        default="",
        description="Local path to pre-downloaded Whisper model directory. "
        "If set, model will be loaded from this path instead of downloading from Hugging Face. "
        "For Docker: Use /app/models/whisper (container path) - models are stored in Docker volumes. "
        "For local development: Use ./models/whisper or any local path.",
    )
    whisper_device: str = Field(
        default="cpu",
        description="Device for Whisper: 'cpu', 'cuda' (GPU), or 'mps' (Mac Metal Performance Shaders)",
    )
    whisper_compute_type: str = Field(
        default="float32",
        description="Compute type: float32 (CPU), float16 (GPU), or int8 (quantized)",
    )

    # Processing Settings
    async_threshold_seconds: int = Field(
        default=300,
        description="Videos longer than this duration (5 minutes) trigger async processing or rejection. "
        "Videos shorter than this are processed synchronously. Default: 300 seconds (5 minutes)",
    )
    max_video_duration_seconds: int = Field(
        default=3600,
        description="Maximum video duration: 1 hour (3600 seconds). Videos longer than this will be rejected with VIDEO_TOO_LONG error",
    )

    # Download Settings
    yt_dlp_timeout: int = Field(
        default=300, description="yt-dlp download timeout in seconds (5 minutes)"
    )
    temp_audio_dir: str = Field(
        default="./temp_audio",
        description="Directory for temporary audio files downloaded from YouTube",
    )
    temp_store_dir: str = Field(
        default="./results",
        description="Directory for storing full job results (JSON files). "
        "Results are organized by date: results/YYYY-MM-DD/{job_id}.json. "
        "Full results are stored here, while minimal metadata is stored in Redis. "
        "Later this can be migrated to S3.",
    )

    # Job Settings
    job_ttl_seconds: int = Field(
        default=3600,
        description="Job results time-to-live: 1 hour (3600 seconds). "
        "Completed job results are kept for this duration before cleanup",
    )

    # Neon Postgres (credits, jobs history)
    database_url: str = Field(
        default="",
        description="PostgreSQL connection URL for Neon (user_credits, top_ups, transcription_jobs). "
        "Uses DATABASE_URL from env.",
    )

    # Credits / Pricing (PRICING_CREDITS_PLAN_V2.md)
    free_plan_asr_minutes: float = Field(
        default=10.0,
        description="Free plan ASR minutes cap (default: 10)",
    )
    min_balance_for_unknown_duration: float = Field(
        default=15.0,
        description="Min minutes required when ffprobe cannot get URL duration (Option C fallback)",
    )
    signup_ip_salt: str = Field(
        default="transcriber-signup",
        description="Salt for IP hashing (must match Next.js SIGNUP_IP_SALT). Used for ip_free_usage cap.",
    )

    # Stripe (Phase 3)
    stripe_secret_key: str = Field(
        default="",
        description="Stripe secret key (sk_live_... or sk_test_...)",
    )

    billing_enabled: bool = Field(
        default=False,
        description=(
            "Master switch for credits/billing. OFF by default: every signed-in user "
            "has unlimited transcription and no Stripe/credits setup is required. "
            "Set BILLING_ENABLED=true (and configure Stripe + credits) to charge users."
        ),
    )
    owner_emails: str = Field(
        default="",
        description="Comma-separated emails with unlimited minutes (e.g. owner@example.com)",
    )
    stripe_publishable_key: str = Field(
        default="",
        description="Stripe publishable key (pk_live_... or pk_test_...)",
    )
    stripe_webhook_secret: str = Field(
        default="",
        description="Stripe webhook signing secret (whsec_...) for signature verification",
    )
    stripe_price_id: str = Field(
        default="",
        description="Stripe Price ID for top-up (price_...). Create via Stripe CLI.",
    )
    stripe_success_url: str = Field(
        default="",
        description="URL to redirect after successful Checkout (e.g. /usage?topup=success)",
    )
    stripe_cancel_url: str = Field(
        default="",
        description="URL to redirect if user cancels Checkout (e.g. /usage)",
    )

    # Redis Configuration
    redis_enabled: bool = Field(
        default=True,
        description="Enable Redis for persistent job storage. "
        "If False, jobs are stored in-memory only (not recommended for production)",
    )
    redis_url: str = Field(
        default="",
        description="Redis connection URL (e.g., rediss://default:password@host:port). "
        "If provided, takes precedence over redis_host, redis_port, redis_password.",
    )
    redis_host: str = Field(
        default="localhost", description="Redis server hostname (default: localhost)"
    )
    redis_port: int = Field(default=6379, description="Redis server port (default: 6379)")
    redis_db: int = Field(default=0, description="Redis database number (default: 0)")
    redis_password: str = Field(default="", description="Redis password (empty for no password)")
    redis_socket_timeout: float = Field(
        default=5.0, description="Redis socket timeout in seconds (default: 5.0)"
    )
    redis_socket_connect_timeout: float = Field(
        default=5.0, description="Redis connection timeout in seconds (default: 5.0)"
    )
    redis_pool_max_connections: int = Field(
        default=50,
        description="Maximum number of connections in Redis connection pool (default: 50)",
    )
    redis_scan_count: int = Field(
        default=500,
        description="Number of keys to scan per iteration in Redis SCAN operations (default: 500). "
        "Larger values improve performance but use more memory.",
    )
    job_list_cache_ttl: int = Field(
        default=10,
        description="Time-to-live for job list cache in seconds (default: 10). "
        "Caches job list results to reduce Redis load.",
    )
    # Cache Configuration
    cache_max_size: int = Field(
        default=1000,
        description="Maximum number of entries in captions cache (default: 1000)",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        description="Time-to-live for captions cache in seconds (default: 300 = 5 minutes)",
    )
    video_id_cache_max_size: int = Field(
        default=5000,
        description="Maximum number of entries in video ID cache (default: 5000)",
    )
    video_id_cache_ttl_seconds: int = Field(
        default=3600,
        description="Time-to-live for video ID cache in seconds (default: 3600 = 1 hour)",
    )
    media_download_timeout_seconds: int = Field(
        default=300,
        description="Timeout for media download requests in seconds (default: 300 = 5 minutes)",
    )

    # CORS Configuration
    cors_origins: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins (use * for all, not recommended for production)",
    )

    # Security Configuration
    strict_cors_check: bool = Field(
        default=False,
        description="If True, raise error if CORS is set to '*' in production (default: False)",
    )
    dev_mode: bool = Field(
        default=False,
        description="Enable development mode (allows requests without API keys). "
        "Set via DEV_MODE environment variable. Not recommended for production.",
    )

    # Validation Constants
    max_segment_text_length: int = Field(
        default=10000,
        description="Maximum text length per transcript segment (bytes)",
    )
    cache_warning_threshold: float = Field(
        default=0.8,
        description="Cache size warning threshold (0.0-1.0). Warns when cache reaches this percentage of max size (default: 0.8 = 80%)",
    )
    max_languages_display: int = Field(
        default=10,
        description="Maximum number of languages to display in logs/errors before truncating (default: 10)",
    )
    min_text_length_for_detection: int = Field(
        default=10,
        description="Minimum text length in characters required for language detection (default: 10)",
    )
    log_result_sample_length: int = Field(
        default=500,
        description="Maximum length of result sample to log for debugging (default: 500 characters)",
    )
    max_language_codes: int = Field(
        default=10,
        description="Maximum number of language codes in a single request",
    )
    max_url_length: int = Field(
        default=2048,
        description="Maximum URL length (characters)",
    )
    # Form Field Validation
    max_translate_to_length: int = Field(
        default=10,
        description="Maximum length for translateTo form field (ISO 639-1 codes are 2-3 chars, allow some buffer)",
    )
    max_format_length: int = Field(
        default=10,
        description="Maximum length for format form field (format names are short)",
    )
    max_diarise_length: int = Field(
        default=5,
        description="Maximum length for diarise form field ('true' or 'false')",
    )
    # Language Code Validation
    min_language_code_length: int = Field(
        default=2,
        description="Minimum length for language codes (ISO 639-1 standard)",
    )
    max_language_code_length: int = Field(
        default=5,
        description="Maximum length for language codes (ISO 639-1 with variants like 'zh-Hans')",
    )
    # YouTube Video ID Validation
    youtube_video_id_length: int = Field(
        default=11,
        description="YouTube video ID length (YouTube standard is exactly 11 characters)",
    )
    # Preferred Languages for Captions
    preferred_languages: str = Field(
        default="en,es,fr,de,it,pt,ru",
        description="Comma-separated list of preferred languages for YouTube captions (ISO 639-1 codes)",
    )
    common_languages: str = Field(
        default="en,es,fr,de,it,pt,ru,ja,ko,zh-Hans,zh-Hant",
        description="Comma-separated list of common languages for YouTube captions fallback (ISO 639-1 codes)",
    )
    youtube_api_timeout: int = Field(
        default=30,
        description="Timeout for YouTube Transcript API requests (seconds)",
    )
    webshare_api_key: str = Field(
        default="",
        description="WebShare API key for fetching proxy credentials. Used to bypass YouTube IP blocking via rotating residential proxies.",
    )
    rate_limit_default_retry_after: int = Field(
        default=60,
        description="Default retry-after time in seconds for rate limit errors (default: 60)",
    )
    # Whisper Confidence Calculation Thresholds
    whisper_segment_density_optimal_min: float = Field(
        default=2.0,
        description="Minimum optimal segment density (segments per second) for confidence calculation (default: 2.0)",
    )
    whisper_segment_density_optimal_max: float = Field(
        default=5.0,
        description="Maximum optimal segment density (segments per second) for confidence calculation (default: 5.0)",
    )
    whisper_segment_density_max: float = Field(
        default=10.0,
        description="Maximum segment density (segments per second) before confidence penalty (default: 10.0)",
    )
    whisper_gap_score_small: float = Field(
        default=2.0,
        description="Small gap threshold in seconds for gap score calculation (default: 2.0)",
    )
    whisper_gap_score_medium: float = Field(
        default=5.0,
        description="Medium gap threshold in seconds for gap score calculation (default: 5.0)",
    )
    whisper_gap_score_large: float = Field(
        default=10.0,
        description="Large gap threshold in seconds for gap score calculation (default: 10.0)",
    )
    whisper_word_length_optimal_min: float = Field(
        default=3.0,
        description="Minimum optimal word length for confidence calculation (default: 3.0)",
    )
    whisper_word_length_optimal_max: float = Field(
        default=6.0,
        description="Maximum optimal word length for confidence calculation (default: 6.0)",
    )
    whisper_word_length_short: float = Field(
        default=2.0,
        description="Short word length threshold for confidence calculation (default: 2.0)",
    )
    whisper_word_length_long: float = Field(
        default=10.0,
        description="Long word length threshold for confidence calculation (default: 10.0)",
    )

    # Media Upload Settings (Level 2)
    max_file_size_mb: int = Field(
        default=500,
        description="Maximum file size for uploads in megabytes (default: 500MB). "
        "Files larger than this will be rejected to prevent DOS attacks.",
    )
    download_chunk_size: int = Field(
        default=8192,
        description="Chunk size in bytes for streaming downloads (default: 8192 = 8KB)",
    )
    max_url_query_length: int = Field(
        default=2000,
        description="Maximum length of URL query parameters in characters (default: 2000)",
    )
    max_file_extension_length: int = Field(
        default=10,
        description="Maximum length of file extension in characters (default: 10)",
    )
    temp_uploads_dir: str = Field(
        default="./temp_uploads",
        description="Directory for storing uploaded media files temporarily before processing",
    )
    temp_downloads_dir: str = Field(
        default="./temp_downloads",
        description="Directory for storing downloaded remote media files temporarily before processing",
    )
    webhook_timeout_seconds: int = Field(
        default=10,
        description="Timeout for webhook callback requests in seconds (default: 10)",
    )
    webhook_max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for failed webhook callbacks (default: 3)",
    )
    webhook_retry_backoff_base: float = Field(
        default=1.0,
        description="Base delay in seconds for exponential backoff in webhook retries (default: 1.0)",
    )
    webhook_connect_timeout: float = Field(
        default=5.0,
        description="Connection timeout for webhook requests in seconds (default: 5.0)",
    )
    webhook_write_timeout: float = Field(
        default=5.0,
        description="Write timeout for webhook requests in seconds (default: 5.0)",
    )
    webhook_pool_timeout: float = Field(
        default=5.0,
        description="Connection pool timeout for webhook requests in seconds (default: 5.0)",
    )
    webhook_user_agent: str = Field(
        default="TranscriptionService/1.0",
        description="User-Agent string for webhook requests (default: TranscriptionService/1.0)",
    )

    # Media Format Configuration
    allowed_audio_formats: str = Field(
        default="mp3,wav,m4a,flac,ogg",
        description="Comma-separated list of allowed audio format extensions (default: mp3,wav,m4a,flac,ogg)",
    )
    allowed_video_formats: str = Field(
        default="mp4,mkv,avi,mov,webm",
        description="Comma-separated list of allowed video format extensions (default: mp4,mkv,avi,mov,webm)",
    )
    default_file_extension: str = Field(
        default="mp4",
        description="Default file extension to use when extension cannot be determined from URL (default: mp4)",
    )

    # Whisper Confidence Calculation Weights
    whisper_confidence_coverage_weight: float = Field(
        default=0.4,
        description="Weight for coverage ratio in confidence calculation (default: 0.4)",
    )
    whisper_confidence_density_weight: float = Field(
        default=0.2,
        description="Weight for density score in confidence calculation (default: 0.2)",
    )
    whisper_confidence_text_quality_weight: float = Field(
        default=0.2,
        description="Weight for text quality metrics in confidence calculation (default: 0.2)",
    )
    whisper_confidence_gap_weight: float = Field(
        default=0.2,
        description="Weight for gap score in confidence calculation (default: 0.2)",
    )
    whisper_text_quality_punctuation_weight: float = Field(
        default=0.5,
        description="Weight for punctuation ratio within text quality (default: 0.5)",
    )
    whisper_text_quality_capitalization_weight: float = Field(
        default=0.3,
        description="Weight for capitalization ratio within text quality (default: 0.3)",
    )
    whisper_text_quality_word_length_weight: float = Field(
        default=0.2,
        description="Weight for word length score within text quality (default: 0.2)",
    )
    whisper_density_penalty_divisor: float = Field(
        default=20.0,
        description="Divisor for density penalty calculation when density exceeds max (default: 20.0)",
    )
    whisper_density_interpolation_multiplier: float = Field(
        default=0.5,
        description="Multiplier for density interpolation when density is below optimal min (default: 0.5)",
    )
    whisper_word_length_short_score: float = Field(
        default=0.5,
        description="Confidence score for short words (below short threshold) (default: 0.5)",
    )
    whisper_gap_score_very_large: float = Field(
        default=0.4,
        description="Gap score for very large gaps (above large threshold) (default: 0.4)",
    )
    # Whisper Confidence Calculation Additional Constants
    whisper_segment_end_offset: float = Field(
        default=0.1,
        description="Offset in seconds to add to segment start when end is invalid (default: 0.1)",
    )
    whisper_word_length_long_score: float = Field(
        default=0.7,
        description="Confidence score for long words (above long threshold) (default: 0.7)",
    )
    whisper_word_length_medium_score: float = Field(
        default=0.8,
        description="Confidence score for medium word length (between short and optimal) (default: 0.8)",
    )
    whisper_gap_score_single_segment: float = Field(
        default=0.9,
        description="Gap score for single segment (can't assess gaps) (default: 0.9)",
    )
    whisper_gap_score_medium_value: float = Field(
        default=0.8,
        description="Gap score for medium gaps (between small and medium threshold) (default: 0.8)",
    )
    whisper_gap_score_large_value: float = Field(
        default=0.6,
        description="Gap score for large gaps (between medium and large threshold) (default: 0.6)",
    )
    whisper_density_interpolation_factor: float = Field(
        default=0.1,
        description="Factor for density interpolation when density is between optimal_max and max (default: 0.1)",
    )

    # Redis Configuration
    redis_key_prefix: str = Field(
        default="job:",
        description="Prefix for Redis keys (default: job:)",
    )

    # File Storage Configuration
    result_file_extension: str = Field(
        default="json",
        description="File extension for result files (default: json)",
    )

    # === Level 3 Configuration (GPU Workers, Queue, S3, Observability) ===

    # Runpod Configuration
    runpod_api_key: str = Field(
        default="",
        description="Runpod API key for managing GPU workers (REQUIRED for Level 3)",
    )
    runpod_template_id: str = Field(
        default="",
        description="Runpod template ID for GPU worker pods (REQUIRED for Level 3)",
    )
    runpod_api_url: str = Field(
        default="https://api.runpod.io/graphql",
        description="Runpod GraphQL API URL (default: https://api.runpod.io/graphql)",
    )
    runpod_endpoint_id: str = Field(
        default="",
        description="Runpod Serverless endpoint ID for Whisper transcription (REQUIRED for external ASR)",
    )
    max_workers: int = Field(
        default=5,
        description="Maximum number of concurrent GPU workers (default: 5)",
    )
    min_workers: int = Field(
        default=0,
        description="Minimum number of GPU workers to keep running (default: 0)",
    )
    worker_idle_timeout_seconds: int = Field(
        default=300,
        description="Idle timeout in seconds before shutting down a worker (default: 300 = 5 minutes)",
    )
    worker_heartbeat_interval_seconds: int = Field(
        default=30,
        description="Interval in seconds for worker heartbeat checks (default: 30)",
    )
    worker_health_check_timeout_seconds: int = Field(
        default=120,
        description="Timeout in seconds before marking worker as unhealthy if no heartbeat (default: 120)",
    )
    worker_warmup_time_seconds: int = Field(
        default=60,
        description="Time in seconds for worker to warm up (load model) before accepting jobs (default: 60)",
    )
    # Auto-scaling Configuration
    worker_auto_scaling_enabled: bool = Field(
        default=True,
        description="Enable automatic worker scaling based on queue depth (default: True)",
    )
    worker_scale_up_queue_depth: int = Field(
        default=10,
        description="Queue depth threshold to trigger worker scale-up (default: 10)",
    )
    worker_scale_down_queue_depth: int = Field(
        default=2,
        description="Queue depth threshold to trigger worker scale-down (default: 2)",
    )
    worker_auto_scaling_interval_seconds: int = Field(
        default=60,
        description="Interval in seconds for auto-scaling checks (default: 60)",
    )

    # Queue Configuration
    queue_backend: str = Field(
        default="redis",
        description="Queue backend: 'redis' (Redis Queue) or 'sqs' (AWS SQS) (default: redis)",
    )
    queue_name: str = Field(
        default="transcription_jobs",
        description="Queue name for job processing (default: transcription_jobs)",
    )
    queue_max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for failed jobs (default: 3)",
    )
    queue_retry_delay_seconds: int = Field(
        default=60,
        description="Initial delay in seconds before retrying a failed job (default: 60)",
    )
    queue_visibility_timeout_seconds: int = Field(
        default=300,
        description="Visibility timeout in seconds for jobs in queue (default: 300 = 5 minutes)",
    )
    queue_max_job_time_seconds: int = Field(
        default=3600,
        description="Maximum time in seconds a job can run before being considered failed (default: 3600 = 1 hour)",
    )

    # S3 Storage Configuration
    s3_enabled: bool = Field(
        default=False,
        description="Enable S3-compatible storage (REQUIRED for Level 3). If False, uses local file system.",
    )
    s3_bucket_name: str = Field(
        default="",
        description="S3 bucket name for storing media files and results (REQUIRED if s3_enabled=True)",
    )
    s3_region: str = Field(
        default="us-east-1",
        description="S3 region (default: us-east-1)",
    )
    s3_access_key_id: str = Field(
        default="",
        description="S3 access key ID (REQUIRED if s3_enabled=True)",
    )
    s3_secret_access_key: str = Field(
        default="",
        description="S3 secret access key (REQUIRED if s3_enabled=True)",
    )
    s3_endpoint_url: str = Field(
        default="",
        description="S3 endpoint URL for S3-compatible storage (e.g., Cloudflare R2, MinIO). "
        "Leave empty for AWS S3 (default: empty = AWS S3)",
    )
    s3_media_prefix: str = Field(
        default="media/",
        description="S3 prefix for uploaded media files (default: media/). Files stored as media/{date}/{job_id}.{ext}",
    )
    s3_results_prefix: str = Field(
        default="results/",
        description="S3 prefix for transcription results (default: results/). Files stored as results/YYYY-MM-DD/{job_id}.json",
    )
    s3_multipart_threshold_mb: int = Field(
        default=100,
        description="File size threshold in MB for using multipart uploads (default: 100MB)",
    )
    s3_multipart_chunk_size_mb: int = Field(
        default=10,
        description="Chunk size in MB for multipart uploads (default: 10MB)",
    )

    # Cost Control Configuration
    cost_control_enabled: bool = Field(
        default=True,
        description="Enable cost control features (budget limits, idle timeout) (default: True)",
    )
    max_budget_usd: float = Field(
        default=100.0,
        description="Maximum budget in USD before rejecting new jobs (default: 100.0)",
    )
    gpu_cost_per_hour: float = Field(
        default=0.50,
        description="Cost per GPU hour in USD (default: 0.50). Used for cost tracking.",
    )
    cost_tracking_window_days: int = Field(
        default=30,
        description="Number of days to track costs for (default: 30)",
    )
    budget_alert_threshold: float = Field(
        default=0.8,
        description="Alert threshold as fraction of max_budget (0.0-1.0). Alert when budget reaches this (default: 0.8 = 80%)",
    )

    # Observability Configuration
    observability_enabled: bool = Field(
        default=True,
        description="Enable structured logging and metrics collection (default: True)",
    )
    log_format: str = Field(
        default="json",
        description="Log format: 'json' (structured) or 'text' (default: json)",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)",
    )
    metrics_enabled: bool = Field(
        default=True,
        description="Enable metrics collection (Prometheus) (default: True)",
    )
    metrics_port: int = Field(
        default=9090,
        description="Port for Prometheus metrics endpoint (default: 9090)",
    )
    tracing_enabled: bool = Field(
        default=False,
        description="Enable distributed tracing (OpenTelemetry) (default: False)",
    )
    tracing_endpoint: str = Field(
        default="",
        description="OpenTelemetry collector endpoint URL (default: empty = disabled)",
    )

    # Auto-scaling Configuration
    auto_scaling_enabled: bool = Field(
        default=True,
        description="Enable automatic worker scaling based on queue depth (default: True)",
    )
    scale_up_threshold: int = Field(
        default=10,
        description="Queue depth threshold to trigger scale-up (add worker) (default: 10)",
    )
    scale_down_threshold: int = Field(
        default=2,
        description="Queue depth threshold to trigger scale-down (remove worker) (default: 2)",
    )
    scale_cooldown_seconds: int = Field(
        default=300,
        description="Cooldown period in seconds between scaling operations (default: 300 = 5 minutes)",
    )

    model_config = SettingsConfigDict(
        extra="ignore",  # Ignore extra environment variables (e.g., whisper_model, yt_dlp_timeout)
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def get_api_keys(self) -> list[str]:
        """
        Parse API keys from comma-separated string.

        Converts the comma-separated api_keys string into a list of individual
        API keys, stripping whitespace from each key.

        Returns:
            list[str]: List of API keys. Returns empty list if no keys configured.

        Example:
            >>> settings = Settings(api_keys="key1, key2, key3")
            >>> settings.get_api_keys()
            ['key1', 'key2', 'key3']
        """
        if not self.api_keys:
            return []
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]

    def get_owner_emails(self) -> set[str]:
        """Parse owner emails (unlimited minutes) from comma-separated string."""
        if not self.owner_emails:
            return set()
        return {e.strip().lower() for e in self.owner_emails.split(",") if e.strip()}

    def get_allowed_audio_formats(self) -> set[str]:
        """
        Parse allowed audio formats from comma-separated string.

        Converts the comma-separated allowed_audio_formats string into a set
        of format extensions. Returns default formats if not configured.

        Returns:
            set[str]: Set of allowed audio format extensions (lowercase, no whitespace).
                Default: {"mp3", "wav", "m4a", "flac", "ogg"} if not configured

        Example:
            >>> settings = Settings(allowed_audio_formats="mp3, wav, ogg")
            >>> settings.get_allowed_audio_formats()
            {'mp3', 'wav', 'ogg'}
        """
        if not self.allowed_audio_formats:
            return {"mp3", "wav", "m4a", "flac", "ogg"}
        return {fmt.strip().lower() for fmt in self.allowed_audio_formats.split(",") if fmt.strip()}

    def get_allowed_video_formats(self) -> set[str]:
        """
        Parse allowed video formats from comma-separated string.

        Converts the comma-separated allowed_video_formats string into a set
        of format extensions. Returns default formats if not configured.

        Returns:
            set[str]: Set of allowed video format extensions (lowercase, no whitespace).
                Default: {"mp4", "mkv", "avi", "mov", "webm"} if not configured

        Example:
            >>> settings = Settings(allowed_video_formats="mp4, mkv, webm")
            >>> settings.get_allowed_video_formats()
            {'mp4', 'mkv', 'webm'}
        """
        if not self.allowed_video_formats:
            return {"mp4", "mkv", "avi", "mov", "webm"}
        return {fmt.strip().lower() for fmt in self.allowed_video_formats.split(",") if fmt.strip()}

    def get_preferred_languages(self) -> list[str]:
        """
        Parse preferred languages from comma-separated string.

        Converts the comma-separated preferred_languages string into a list
        of language codes. Returns default languages if not configured.

        Returns:
            list[str]: List of preferred language codes (ISO 639-1 format).
                Default: ["en", "es", "fr", "de", "it", "pt", "ru"] if not configured

        Example:
            >>> settings = Settings(preferred_languages="en, es, fr")
            >>> settings.get_preferred_languages()
            ['en', 'es', 'fr']
        """
        if not self.preferred_languages:
            return ["en", "es", "fr", "de", "it", "pt", "ru"]
        return [lang.strip() for lang in self.preferred_languages.split(",") if lang.strip()]

    def get_common_languages(self) -> list[str]:
        """
        Parse common languages from comma-separated string.

        Converts the comma-separated common_languages string into a list
        of language codes. Returns default languages if not configured.
        Used as a fallback when preferred languages are not available.

        Returns:
            list[str]: List of common language codes (ISO 639-1 format).
                Default: ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh-Hans", "zh-Hant"]
                if not configured

        Example:
            >>> settings = Settings(common_languages="en, ja, ko")
            >>> settings.get_common_languages()
            ['en', 'ja', 'ko']
        """
        if not self.common_languages:
            return ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh-Hans", "zh-Hant"]
        return [lang.strip() for lang in self.common_languages.split(",") if lang.strip()]

    def get_cors_origins(self) -> list[str]:
        """
        Parse CORS origins from comma-separated string with production safety checks.

        Converts the comma-separated cors_origins string into a list of allowed origins.
        Validates that origins start with http:// or https://, or are "*" for all origins.
        In production, warns or errors if CORS is set to allow all origins.

        Returns:
            list[str]: List of allowed CORS origins. ["*"] means all origins
                (not recommended for production). Returns ["*"] if empty or invalid.

        Raises:
            ValueError: If strict_cors_check is True and CORS is "*" in production

        Example:
            >>> settings = Settings(cors_origins="https://example.com, https://app.example.com")
            >>> settings.get_cors_origins()
            ['https://example.com', 'https://app.example.com']
        """
        if not self.cors_origins or self.cors_origins == "*":
            origins = ["*"]
        else:
            origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
            validated_origins = []
            for origin in origins:
                if origin.startswith(("http://", "https://")) or origin == "*":
                    validated_origins.append(origin)
            origins = validated_origins if validated_origins else ["*"]

        if self.is_production() and ("*" in origins or len(origins) == 0):
            error_msg = (
                "SECURITY ERROR: CORS set to allow all origins in production! "
                "This is a security risk. Please configure specific origins."
            )
            logger.error(error_msg)
            if self.strict_cors_check or os.getenv("STRICT_CORS_CHECK", "").lower() == "true":
                raise ValueError("CORS must be restricted in production")

        return origins

    def is_production(self) -> bool:
        """
        Check if running in production mode.

        Production mode is determined by:
        1. DEV_MODE environment variable is not "true"
        2. API keys are configured

        Returns:
            bool: True if in production mode, False otherwise (development mode)

        Example:
            >>> settings = Settings(api_keys="key1,key2")
            >>> settings.is_production()
            True
            >>> settings = Settings(api_keys="", dev_mode=True)
            >>> settings.is_production()
            False
        """
        dev_mode_env = os.getenv("DEV_MODE", "false").lower() == "true"
        if dev_mode_env or self.dev_mode:
            return False
        return bool(self.get_api_keys())

    def validate_production_settings(self) -> None:
        """
        Validate that production settings are properly configured.

        Checks that required production settings are present:
        - API keys must be configured
        - CORS origins must be restricted (if strict_cors_check is enabled)

        Skips validation if running in development mode.

        Returns:
            None: Completes successfully if validation passes

        Raises:
            ValueError: If production mode is enabled but required settings are missing.
                Error message includes details about which settings are invalid.

        Example:
            >>> settings = Settings(api_keys="key1,key2", strict_cors_check=True)
            >>> settings.validate_production_settings()  # Passes
            >>> settings = Settings(api_keys="")
            >>> settings.validate_production_settings()  # Raises ValueError
        """
        if not self.is_production():
            return

        errors = []

        if not self.get_api_keys():
            errors.append("API keys must be configured in production")

        cors_origins = self.get_cors_origins()
        if "*" in cors_origins or len(cors_origins) == 0:
            if self.strict_cors_check:
                errors.append("CORS must be restricted to specific origins in production")

        if errors:
            error_msg = "Production configuration validation failed:\n" + "\n".join(
                f"  - {e}" for e in errors
            )
            logger.error(error_msg)
            raise ValueError(error_msg)


settings = Settings()
