"""Main transcription service for YouTube video captions."""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from cachetools import TTLCache  # type: ignore[import-untyped]
from youtube_transcript_api import (CouldNotRetrieveTranscript,
                                    TranscriptsDisabled)

from app.core.config import settings
from app.core.exceptions import (CaptionsNotAvailableError,
                                 InvalidVideoURLError, TranscriptionError,
                                 VideoTooLongError)
from app.models.schemas import OutputFormat, TranscriptSegment
from app.services.jobs.job_manager import JobManager
from app.services.media.audio_download_service import AudioDownloadService
from app.services.transcription.whisper_service import WhisperService
from app.services.transcription.youtube_captions import YouTubeCaptionsService
from app.utils.config_utils import get_int_setting
from app.utils.formatters import format_as_srt, format_as_text, format_as_vtt
from app.utils.serialization import convert_to_camel_case
from app.utils.youtube import extract_video_id

logger = logging.getLogger(__name__)

# Performance optimization: Cache for captions requests (5 minute TTL, max 1000 entries)
# Only cache Path A (captions) results, not ASR results
# Using TTLCache for automatic expiration and LRU eviction
_captions_cache: TTLCache[str, dict] = TTLCache(
    maxsize=settings.cache_max_size, ttl=settings.cache_ttl_seconds
)

# Performance optimization: Cache video_id extraction results to avoid repeated regex operations
# Video IDs are immutable, so they can be cached indefinitely
_video_id_cache: TTLCache[str, Optional[str]] = TTLCache(
    maxsize=settings.video_id_cache_max_size, ttl=settings.video_id_cache_ttl_seconds
)


def _log_cache_stats() -> None:
    """Log cache statistics for monitoring.

    Logs current cache size and capacity to help identify cache thrashing
    in high-traffic scenarios. Should be called periodically or on cache operations.

    Returns:
        None: This function does not return a value.
    """
    captions_size = len(_captions_cache)
    captions_maxsize = _captions_cache.maxsize
    video_id_size = len(_video_id_cache)
    video_id_maxsize = _video_id_cache.maxsize

    # Log warning if cache is near capacity (threshold from config)
    if captions_size >= captions_maxsize * settings.cache_warning_threshold:
        logger.warning(
            f"[CACHE] Captions cache near capacity: {captions_size}/{captions_maxsize} "
            f"({captions_size/captions_maxsize*100:.1f}%). Consider increasing maxsize or using Redis."
        )
    if video_id_size >= video_id_maxsize * settings.cache_warning_threshold:
        logger.warning(
            f"[CACHE] Video ID cache near capacity: {video_id_size}/{video_id_maxsize} "
            f"({video_id_size/video_id_maxsize*100:.1f}%). Consider increasing maxsize or using Redis."
        )

    logger.debug(
        f"[CACHE] Cache stats - Captions: {captions_size}/{captions_maxsize}, "
        f"Video ID: {video_id_size}/{video_id_maxsize}"
    )


class TranscriptionService:
    """
    Main transcription service orchestrating Path A (captions) and Path B (ASR fallback).

    This service implements a two-path transcription strategy:
    - Path A: Fast-path using existing YouTube captions (preferred, no GPU needed)
    - Path B: ASR fallback using Whisper model (when captions unavailable or diarization requested)

    The service automatically decides which path to use based on:
    - Availability of captions
    - Request for diarization (forces Path B)
    - Video duration (sync vs async processing)

    Attributes:
        captions_service (YouTubeCaptionsService): Service for fetching YouTube captions (Path A)
        audio_service (AudioDownloadService): Service for downloading audio (Path B)
        whisper_service (WhisperService): Service for ASR transcription (Path B)
        job_manager (JobManager): Manager for async transcription jobs (Path B)
    """

    def __init__(self) -> None:
        """Initialize transcription service with all required services.

        Creates instances of:
        - YouTubeCaptionsService for Path A (captions)
        - AudioDownloadService for Path B (audio download)
        - WhisperService for Path B (ASR transcription)
        - JobManager for Path B (async job management)
        """
        self.captions_service = YouTubeCaptionsService()
        self.audio_service = AudioDownloadService()
        self.whisper_service = WhisperService()
        self.job_manager = JobManager()

    def _get_cache_key(
        self, video_id: str, translate_to: Optional[str], format: OutputFormat
    ) -> str:
        """
        Generate cache key for captions request.

        Creates a unique cache key based on video ID, translation target language,
        and output format. This ensures that different requests for the same video
        with different parameters are cached separately.

        Args:
            video_id (str): YouTube video ID
            translate_to (Optional[str]): Target language for translation (ISO 639-1).
                If None, uses "none" in the cache key.
            format (OutputFormat): Output format enum (JSON, TEXT, SRT, or VTT)

        Returns:
            str: Cache key string in format "{video_id}:{translate_to}:{format}"

        Example:
            >>> service = TranscriptionService()
            >>> key = service._get_cache_key("dQw4w9WgXcQ", "en", OutputFormat.JSON)
            >>> key
            'dQw4w9WgXcQ:en:json'
        """
        translate_str = translate_to if translate_to is not None else "none"
        format_str = format.value if isinstance(format, OutputFormat) else str(format)
        return f"{video_id}:{translate_str}:{format_str}"

    def _validate_video_url(self, video_url: str) -> str:
        """
        Validate and sanitize video URL with strict checks.

        Validates:
        - URL is not empty and is a string
        - URL length is within limits
        - URL uses HTTP/HTTPS protocol
        - URL is a valid YouTube domain
        - Query parameters are not excessively long

        Args:
            video_url (str): Video URL to validate

        Returns:
            str: Sanitized video URL

        Raises:
            InvalidVideoURLError: If URL is invalid, malformed, or not a YouTube URL
        """
        if not video_url or not isinstance(video_url, str):
            raise InvalidVideoURLError("Video URL cannot be empty")

        video_url = video_url.strip()
        if not video_url:
            raise InvalidVideoURLError("Video URL cannot be empty or whitespace only")

        max_length = get_int_setting(settings.max_url_length, 2048)
        if len(video_url) > max_length:
            raise InvalidVideoURLError(
                f"Video URL exceeds maximum length ({max_length} characters)"
            )

        if not video_url.startswith(("http://", "https://")):
            raise InvalidVideoURLError("Video URL must be a valid HTTP/HTTPS URL")

        try:
            from urllib.parse import urlparse

            parsed = urlparse(video_url)

            valid_youtube_domains = [
                "youtube.com",
                "www.youtube.com",
                "youtu.be",
                "m.youtube.com",
                "youtube-nocookie.com",
            ]

            domain = parsed.netloc.lower()
            if ":" in domain:
                domain = domain.split(":")[0]

            domain_clean = domain.replace("www.", "")

            is_valid_domain = any(
                domain_clean == valid_domain or domain_clean.endswith(f".{valid_domain}")
                for valid_domain in valid_youtube_domains
            )

            if not is_valid_domain:
                raise InvalidVideoURLError(
                    f"URL must be a valid YouTube URL. Domain '{domain}' is not a recognized YouTube domain."
                )

            if parsed.query and len(parsed.query) > settings.max_url_query_length:
                raise InvalidVideoURLError(
                    f"Video URL query parameters are too long (exceeds {settings.max_url_query_length} characters)"
                )

        except ValueError as e:
            raise InvalidVideoURLError(f"Invalid URL format: {str(e)}")
        except Exception as e:
            raise InvalidVideoURLError(f"Failed to parse URL: {str(e)}")

        return video_url

    def _extract_and_validate_video_id(self, video_url: str) -> str:
        """
        Extract and validate video ID from YouTube URL.

        Args:
            video_url (str): YouTube video URL

        Returns:
            str: Validated video ID

        Raises:
            InvalidVideoURLError: If video URL is invalid or video ID cannot be extracted
        """
        video_url = self._validate_video_url(str(video_url))

        video_id = _video_id_cache.get(video_url)
        if video_id is None:
            video_id = extract_video_id(video_url)
            if video_id:
                _video_id_cache[video_url] = video_id
        if not video_id:
            raise InvalidVideoURLError(f"Invalid YouTube URL: {video_url}")

        return video_id

    async def _try_captions_path(
        self,
        video_url: str,
        video_id: str,
        translate_to: Optional[str],
        format: OutputFormat,
    ) -> dict:
        """
        Attempt Path A: Fetch captions from YouTube.

        Tries to fetch existing captions from YouTube. Returns cached result if available,
        otherwise fetches and caches the result.

        Args:
            video_url (str): YouTube video URL
            video_id (str): YouTube video ID
            translate_to (Optional[str]): Target language for translation
            format (OutputFormat): Output format

        Returns:
            dict: Transcription result from captions

        Raises:
            CouldNotRetrieveTranscript: If captions cannot be retrieved
            TranscriptsDisabled: If transcripts are disabled
            CaptionsNotAvailableError: If no captions available
        """
        cache_key = self._get_cache_key(video_id, translate_to, format)
        if cache_key in _captions_cache:
            logger.info(f"[CAPTIONS] Cache hit for video {video_id}")
            # Cast to Dict[str, Any] to satisfy mypy
            return cast(Dict[str, Any], _captions_cache[cache_key])

        logger.info(f"[CAPTIONS] Attempting YouTube Captions (Path A) for video {video_id}")
        result = self._path_a_captions(video_url, video_id, translate_to, format)
        _captions_cache[cache_key] = result
        _log_cache_stats()
        return result

    async def transcribe(
        self,
        video_url: str,
        translate_to: Optional[str] = None,
        format: OutputFormat = OutputFormat.JSON,
        diarise: bool = False,
        webhook_url: Optional[str] = None,
    ) -> dict:
        """
        Main transcription method with Path A/B decision logic.

        Attempts Path A (captions) first, falls back to Path B (ASR) if:
        - Captions are unavailable/disabled/unavailable
        - Captions fetch fails (private/age-gated/blocked)
        - Diarization is requested (diarise=True)
        - translateTo requested but captions can't satisfy it

        For Path B:
        - Videos < 5 minutes: Synchronous processing (returns result immediately)
        - Videos 5 minutes - 1 hour: Asynchronous processing (returns job ID for polling)
        - Videos > 1 hour: Rejected with VIDEO_TOO_LONG error

        Args:
            video_url (str): YouTube video URL (supports various YouTube URL formats)
            translate_to (Optional[str]): Optional target language code for translation
                (ISO 639-1 format, e.g., "en", "es", "fr"). If None, uses original language.
            format (OutputFormat): Output format enum (default: OutputFormat.JSON).
                Supported formats: JSON, TEXT, SRT, VTT
            diarise (bool): Enable speaker diarization. When True, forces Path B (ASR mode).
                Level 1 requirement: diarise=True must trigger ASR mode (implemented).
                Level 2 feature: Actual speaker identification/labeling in segments (not yet implemented).
                Default: False
            webhook_url (Optional[str]): Optional webhook callback URL for async jobs.
                If provided, transcription result will be POSTed to this URL when job completes.
                Only used for async jobs (videos that require background processing).

        Returns:
            dict: Dictionary containing transcription data:
                - For JSON format: Full response with transcript, segments, language, source, video_id, duration (sync)
                - For other formats: Dictionary with "content" (formatted string) and "format" keys (sync)
                - For async jobs: Dictionary with "job_id", "status", "created_at", "video_id"

        Raises:
            InvalidVideoURLError: If video URL is invalid or cannot be parsed
            VideoTooLongError: If video is longer than 1 hour (VIDEO_TOO_LONG error code)
            CaptionsNotAvailableError: If captions are not available (triggers Path B fallback)
            CouldNotRetrieveTranscript: If YouTube API fails to retrieve transcript (triggers Path B fallback)
            TranscriptsDisabled: If transcripts are disabled (triggers Path B fallback)

        Example:
            >>> service = TranscriptionService()
            >>> result = service.transcribe(
            ...     "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            ...     translate_to="en",
            ...     format=OutputFormat.JSON,
            ...     diarise=False
            ... )
            >>> result["source"] in ["youtube_captions", "asr"]
            True
        """
        video_id = self._extract_and_validate_video_id(video_url)

        if not diarise:
            try:
                return await self._try_captions_path(video_url, video_id, translate_to, format)
            except (
                CouldNotRetrieveTranscript,
                TranscriptsDisabled,
                CaptionsNotAvailableError,
            ) as e:
                logger.info(
                    f"[CAPTIONS] Path A failed for {video_id}: {type(e).__name__}. "
                    f"[ASR] Falling back to Whisper ASR (Path B)"
                )
        else:
            logger.info(
                f"[ASR] Diarization requested for {video_id}, skipping Path A (Captions), using Path B (Whisper ASR)"
            )

        return await self._path_b_asr(
            video_url, video_id, translate_to, format, diarise, webhook_url
        )

    def _path_a_captions(
        self, video_url: str, video_id: str, translate_to: Optional[str], format: OutputFormat
    ) -> dict:
        """
        Path A: Fetch captions from YouTube (fast-path, no GPU needed).

        Extracts videoId from YouTube URL and attempts to fetch existing captions/transcript
        using youtube-transcript-api (no official YouTube Data API key required).

        If captions exist and are accessible:
        - Returns segments with timestamps
        - Sets source = "youtube_captions"
        - Converts to requested format (JSON/Text/SRT/VTT)
        - Supports translateTo if the captions provider supports it

        Storage Policy:
        - Results are NOT stored (neither in Redis nor temp_store)
        - Captions are cheap to re-fetch compared to GPU ASR
        - Source of truth is YouTube captions anyway
        - Optional: Short-term caching can be added later (SETEX captions:{videoId}:{lang}:{format})

        If translateTo is requested but captions can't satisfy it, raises exception
        which triggers Path B fallback.

        Args:
            video_url (str): YouTube video URL
            video_id (str): YouTube video ID (already extracted)
            translate_to (Optional[str]): Target language for translation (ISO 639-1)
            format (OutputFormat): Output format

        Returns:
            dict: Transcription response in requested format with source="youtube_captions"

        Raises:
            CouldNotRetrieveTranscript: If captions cannot be retrieved (triggers Path B)
            TranscriptsDisabled: If transcripts are disabled (triggers Path B)
            CaptionsNotAvailableError: If no captions available (triggers Path B)
        """
        # Attempt to fetch captions (with translation if requested)
        # If translation fails, CouldNotRetrieveTranscript will be raised, triggering Path B
        segments, language = self.captions_service.fetch_transcript(
            video_url, translate_to=translate_to
        )

        if not segments:
            raise CaptionsNotAvailableError(
                "No transcript segments found",
                details={"video_id": video_id},
            )

        full_transcript = format_as_text(segments)

        duration = max((segment.end for segment in segments), default=0.0)

        response_data = {
            "status": "completed",
            "jobId": None,
            "source": "youtube_captions",  # Always set source to "youtube_captions" for Path A
            "language": language,
            "confidence": None,  # Captions don't have confidence scores
            "transcript": full_transcript,
            "segments": [segment.model_dump() for segment in segments],
            "warnings": [],
            "video_id": video_id,
            "video_url": video_url,
            "duration": duration,
        }

        if format == OutputFormat.TEXT:
            return {"content": full_transcript, "format": "text"}
        elif format == OutputFormat.SRT:
            return {"content": format_as_srt(segments), "format": "srt"}
        elif format == OutputFormat.VTT:
            return {"content": format_as_vtt(segments), "format": "vtt"}
        else:
            return response_data

    async def _path_b_asr(
        self,
        video_url: str,
        video_id: str,
        translate_to: Optional[str],
        format: OutputFormat,
        diarise: bool,
        webhook_url: Optional[str] = None,
    ) -> dict:
        """
        Path B: ASR transcription with Whisper (fallback when captions unavailable).

        Downloads audio from YouTube and transcribes using Whisper model.
        - Videos < 5 minutes: Processed synchronously (returns result immediately)
        - Videos 5 minutes - 1 hour: Processed asynchronously (returns job ID)
        - Videos > 1 hour: Rejected with error (VIDEO_TOO_LONG)

        Args:
            video_url (str): YouTube video URL
            video_id (str): YouTube video ID
            translate_to (Optional[str]): Target language for translation
            format (OutputFormat): Output format
            diarise (bool): Whether diarization is requested

        Returns:
            dict: Transcription response (sync) or job response (async) in requested format

        Raises:
            VideoTooLongError: If video is longer than 1 hour (3600 seconds)
            InvalidVideoURLError: If video URL is invalid or duration cannot be determined
        """
        duration = self.audio_service.get_video_duration(video_url)

        threshold_minutes = settings.async_threshold_seconds / 60
        max_duration_hours = settings.max_video_duration_seconds / 3600
        logger.info(
            f"[ASR] Video duration check for {video_id}: duration={duration}s ({duration/60:.1f} min), "
            f"sync_threshold={settings.async_threshold_seconds}s ({threshold_minutes:.1f} min), "
            f"max_duration={settings.max_video_duration_seconds}s ({max_duration_hours:.1f} hours)"
        )

        if duration > settings.max_video_duration_seconds:
            max_hours = settings.max_video_duration_seconds / 3600
            raise VideoTooLongError(
                f"Video too long: {duration}s ({duration/3600:.1f} hours). Maximum allowed duration is {settings.max_video_duration_seconds}s ({max_hours:.1f} hours).",
                details={
                    "video_id": video_id,
                    "duration": duration,
                    "duration_hours": duration / 3600,
                    "max_duration_seconds": settings.max_video_duration_seconds,
                    "max_duration_hours": max_hours,
                },
            )

        if duration < settings.async_threshold_seconds:
            logger.info(
                f"[ASR] Processing video {video_id} synchronously (duration: {duration}s, "
                f"threshold: {settings.async_threshold_seconds}s ({threshold_minutes:.1f} minutes))"
            )
            return await self._asr_sync(
                video_url, video_id, translate_to, format, diarise, duration, webhook_url
            )
        else:
            logger.info(
                f"[ASR] Processing video {video_id} asynchronously (duration: {duration}s, "
                f"threshold: {settings.async_threshold_seconds}s ({threshold_minutes:.1f} minutes))"
            )
            return self._asr_async(
                video_url, video_id, translate_to, format, diarise, duration, webhook_url
            )

    def _format_asr_result(
        self,
        segments: List[TranscriptSegment],
        language: str,
        confidence: Optional[float],
        format: OutputFormat,
        video_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Format ASR transcription result according to requested format.

        Converts transcript segments into the requested output format (JSON, TEXT, SRT, or VTT).
        For JSON format, returns a standardized response with all metadata.
        For other formats, returns a dictionary with "content" and "format" keys.

        Args:
            segments (List[TranscriptSegment]): List of transcript segments with text and timing
            language (str): Detected language code (ISO 639-1, e.g., "en", "es", "fr")
            confidence (Optional[float]): Confidence score (0.0-1.0) or None if not available
            format (OutputFormat): Output format enum (JSON, TEXT, SRT, or VTT)

        Returns:
            Dict[str, Any]: Formatted result dictionary:
                - For JSON: Full response with status, source, language, confidence, transcript, segments, warnings
                - For TEXT/SRT/VTT: Dictionary with "content" (formatted string) and "format" keys
        """
        full_transcript = format_as_text(segments)

        if format == OutputFormat.TEXT:
            return {"content": full_transcript, "format": "text"}
        elif format == OutputFormat.SRT:
            return {"content": format_as_srt(segments), "format": "srt"}
        elif format == OutputFormat.VTT:
            return {"content": format_as_vtt(segments), "format": "vtt"}
        else:
            # JSON format - standardized format
            result = {
                "status": "completed",
                "jobId": None,
                "source": "asr",
                "language": language,
                "confidence": confidence,
                "transcript": full_transcript,
                "segments": [segment.model_dump() for segment in segments],
                "warnings": [],
            }
            if video_url:
                result["video_url"] = video_url
            return result

    def _store_sync_result(
        self,
        result_data: Dict[str, Any],
        video_id: str,
        video_url: str,
        translate_to: Optional[str],
        format: OutputFormat,
        diarise: bool,
        language: str,
        model_name: str,
        duration: float,
    ) -> Optional[str]:
        """
        Store synchronous ASR result in S3 (if enabled) or temp_store and Redis.

        Saves the full transcription result to S3 (if enabled) or a JSON file in temp_store directory
        and stores minimal metadata in Redis for tracking. This ensures consistency
        between sync and async ASR results (both are stored the same way).

        Args:
            result_data (Dict[str, Any]): Formatted result data dictionary
            video_id (str): YouTube video ID
            video_url (str): YouTube video URL
            translate_to (Optional[str]): Target language for translation (ISO 639-1)
            format (OutputFormat): Output format enum (JSON, TEXT, SRT, or VTT)
            diarise (bool): Whether diarization was requested
            language (str): Detected language code (ISO 639-1)
            model_name (str): Model name used (e.g., "whisper-base", "whisper-small")
            duration (float): Video duration in seconds

        Returns:
            Optional[str]: Result reference (S3 URI if S3 enabled, otherwise relative path) if successful,
                None if storage failed. Format: "s3://bucket/path" or "temp_store/{result_id}.{settings.result_file_extension}"

        Note:
            If storage fails, metadata is not stored in Redis either.
            Failures are logged but don't raise exceptions (non-critical operation).
        """
        result_id = str(uuid.uuid4())

        stored_result = {
            **result_data,
            "result_id": result_id,
            "video_id": video_id,
            "video_url": video_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "language": language,
            "model": model_name,
            "duration": duration,
            "source": "asr",
            "format": format.value if isinstance(format, OutputFormat) else format,
        }

        stored_result_camel = convert_to_camel_case(stored_result)

        # Try to use job_manager's S3 storage (which handles both S3 and local fallback)
        result_ref: Optional[str] = None
        try:
            # Use job_manager's _save_result_to_file which handles S3 if enabled
            result_ref = self.job_manager._save_result_to_file(result_id, stored_result_camel)
            logger.info(f"[ASR] Sync result stored: {result_ref} " f"(result_id: {result_id})")
        except Exception as e:
            logger.warning(f"[ASR] Failed to store sync result: {e}. Continuing with response.")
            result_ref = None

        if result_ref:
            try:
                self.job_manager.store_sync_result_metadata(
                    result_id=result_id,
                    video_id=video_id,
                    video_url=video_url,
                    translate_to=translate_to,
                    format=format.value if isinstance(format, OutputFormat) else format,
                    diarise=diarise,
                    result_ref=result_ref,
                    language=language,
                    model=model_name,
                    duration=duration,
                    source="asr",
                )
            except Exception as e:
                logger.warning(
                    f"[ASR] Failed to store sync result metadata in Redis: {e}. "
                    "Result file stored but metadata not available in Redis."
                )

        return result_ref

    async def _asr_sync(
        self,
        video_url: str,
        video_id: str,
        translate_to: Optional[str],
        format: OutputFormat,
        diarise: bool,
        duration: float,
        webhook_url: Optional[str] = None,
    ) -> dict:
        """
        Synchronous ASR processing for short videos (async implementation).

        Downloads audio, uploads to S3 if enabled, transcribes with Whisper in a thread pool
        (non-blocking), formats result, stores in S3/temp_store, and cleans up. Whisper inference
        runs in a thread pool to avoid blocking the event loop.

        Note: Results are stored in S3 (if enabled) or temp_store for durability, and metadata is stored
        in Redis (same as async ASR) for consistency and tracking.

        Args:
            video_url (str): YouTube video URL
            video_id (str): YouTube video ID
            translate_to (Optional[str]): Target language for translation
            format (OutputFormat): Output format
            diarise (bool): Whether diarization is requested
            duration (float): Video duration in seconds

        Returns:
            dict: Transcription response in requested format

        Raises:
            TranscriptionError: If transcription fails
        """
        from pathlib import Path

        logger.info(f"[ASR] Starting synchronous ASR transcription for video {video_id}")
        audio_path = self.audio_service.download_audio(video_url, video_id)
        s3_uri = None

        try:
            if self.job_manager._s3_storage and self.job_manager._s3_storage.is_enabled():
                try:
                    audio_path_obj = Path(audio_path)
                    extension = audio_path_obj.suffix.lstrip(".") or "wav"
                    logger.info(f"[ASR] Uploading audio to S3 for video {video_id}...")
                    s3_uri = self.job_manager._s3_storage.upload_media(
                        audio_path_obj, video_id, extension
                    )
                    logger.info(
                        f"[ASR] Successfully uploaded audio to S3 for video {video_id}: {s3_uri}"
                    )
                except Exception as e:
                    logger.error(
                        f"[ASR] Failed to upload audio to S3 for video {video_id}: {e}",
                        exc_info=True,
                    )

            logger.info(f"[ASR] Transcribing audio with Whisper for video {video_id}")
            result = await self.whisper_service.transcribe_async(
                audio_path=audio_path,
                translate_to=translate_to,
            )

            if isinstance(result, dict) and "code" in result:
                raise TranscriptionError(
                    result["message"],
                    code=result["code"],
                    details=result.get("details", {}),
                )

            segments, language, confidence = result
            logger.info(
                f"[ASR] Whisper transcription complete for video {video_id}: "
                f"{len(segments)} segments, language: {language}, confidence: {confidence if confidence is not None else 'N/A'}"
            )

            model_name = getattr(self.whisper_service, "_model_id", "whisper-base")
            if hasattr(self.whisper_service, "model_id"):
                model_name = self.whisper_service.model_id

            result_data = self._format_asr_result(segments, language, confidence, format, video_url)

            self._store_sync_result(
                result_data,
                video_id,
                video_url,
                translate_to,
                format,
                diarise,
                language,
                model_name,
                duration,
            )

            return result_data
        finally:
            self.audio_service.cleanup_audio(audio_path)

    def _asr_async(
        self,
        video_url: str,
        video_id: str,
        translate_to: Optional[str],
        format: OutputFormat,
        diarise: bool,
        duration: float,
        webhook_url: Optional[str] = None,
    ) -> dict:
        """
        Asynchronous ASR processing for medium-length videos (5 minutes - 1 hour).

        Creates a job and returns job ID. Actual processing happens in background task.
        Client should poll job status endpoint to get results.

        Args:
            video_url (str): YouTube video URL.
            video_id (str): YouTube video ID.
            translate_to (Optional[str]): Target language for translation.
            format (OutputFormat): Output format.
            diarise (bool): Whether diarization is requested.
            duration (float): Video duration in seconds (for logging).
            webhook_url (Optional[str]): Optional webhook callback URL for async jobs.

        Returns:
            dict: Job response with job_id, status, created_at, video_id.
        """
        logger.info(f"[ASR] Creating async job for video {video_id} (duration: {duration}s)")
        job_id, job = self.job_manager.create_job(
            video_url=video_url,
            video_id=video_id,
            translate_to=translate_to,
            format=format.value if isinstance(format, OutputFormat) else format,
            diarise=diarise,
            webhook_url=webhook_url,
        )
        logger.info(f"[ASR] Async job created: {job_id} for video {video_id}")

        return {
            "status": job.get("status", "queued"),
            "jobId": job_id,
            "source": job.get("source"),  # None until completed
            "language": job.get("language"),  # None until completed
            "confidence": job.get("confidence"),  # None until completed
            "transcript": job.get("transcript"),  # None until completed
            "segments": job.get("segments"),  # None until completed
            "warnings": job.get("warnings", []),  # Default to empty list
            "created_at": job.get("created_at"),  # ISO 8601 timestamp
        }

    async def transcribe_media(
        self,
        file_path: Path,
        translate_to: Optional[str] = None,
        format: OutputFormat = OutputFormat.JSON,
        diarise: bool = False,
    ) -> dict:
        """
        Transcribe media file (audio or video) using Whisper ASR.

        This method processes uploaded or downloaded media files (not YouTube videos).
        It extracts audio from the media file and transcribes it using Whisper.
        All media transcription goes through ASR (no captions fallback like YouTube).

        Args:
            file_path (Path): Path to the media file (audio or video)
            translate_to (Optional[str]): Optional target language code for translation
                (ISO 639-1 format, e.g., "en", "es", "fr"). If None, uses original language.
            format (OutputFormat): Output format enum (default: OutputFormat.JSON).
                Supported formats: JSON, TEXT, SRT, VTT
            diarise (bool): Enable speaker diarization. When True, enables diarization mode.
                Level 2 feature: Actual speaker identification/labeling in segments (not yet implemented).
                Default: False

        Returns:
            dict: Dictionary containing transcription data:
                - For JSON format: Full response with transcript, segments, language, source, duration
                - For other formats: Dictionary with "content" (formatted string) and "format" keys

        Raises:
            TranscriptionError: If transcription fails, file is invalid, or model inference fails

        Example:
            >>> service = TranscriptionService()
            >>> result = await service.transcribe_media(
            ...     Path("/path/to/audio.mp3"),
            ...     translate_to="en",
            ...     format=OutputFormat.JSON,
            ...     diarise=False
            ... )
            >>> result["source"] == "asr"
            True
        """
        logger.info(
            f"[MEDIA] Transcribing media file: {file_path}, "
            f"translate_to={translate_to}, format={format}, diarise={diarise}"
        )

        logger.info(f"[MEDIA] Transcribing audio with Whisper: {file_path}")
        result = await self.whisper_service.transcribe_async(
            audio_path=str(file_path),
            translate_to=translate_to,
        )

        if isinstance(result, dict) and "code" in result:
            raise TranscriptionError(
                result["message"],
                code=result["code"],
                details=result.get("details", {}),
            )

        segments, language, confidence = result
        logger.info(
            f"[MEDIA] Whisper transcription complete: "
            f"{len(segments)} segments, language: {language}, "
            f"confidence: {confidence if confidence is not None else 'N/A'}"
        )

        model_name = getattr(self.whisper_service, "_model_id", "whisper-base")
        if hasattr(self.whisper_service, "model_id"):
            model_name = self.whisper_service.model_id

        duration = max((segment.end for segment in segments), default=0.0)

        result_data = self._format_asr_result(segments, language, confidence, format)

        if format == OutputFormat.JSON and isinstance(result_data, dict):
            result_data["duration"] = duration
            result_data["model"] = model_name

        return result_data
