"""Service for orchestrating media transcription endpoint business logic."""

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from fastapi import UploadFile

from app.core.config import settings
from app.models.schemas import (EnhancedJobData, ErrorResponse, JobPriority,
                                JobResponse, JobStatus, OutputFormat)
from app.services.credits.credits_service import CreditsService
from app.services.jobs.job_manager import JobManager
from app.services.jobs.queue_service import QueueService
from app.services.media.file_storage import FileStorageService
from app.services.media.media_download_service import MediaDownloadService
from app.services.media.media_probe_service import MediaProbeService
from app.services.media.media_validation import MediaValidationService
from app.services.media.s3_storage_service import S3StorageService
from app.services.media.social_media_service import SocialMediaService
from app.services.transcription.transcription_service import \
    TranscriptionService

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionParams:
    """Parsed transcription parameters.

    Attributes:
        translate_to: Target language code for translation (e.g., "en", "es")
        output_format: Output format for transcription results
        webhook_url: Optional webhook callback URL for job completion notifications
    """

    translate_to: Optional[str]
    output_format: OutputFormat
    webhook_url: Optional[str]


@dataclass
class FileUploadResult:
    """Result of file upload processing.

    Attributes:
        job_id: Unique job identifier
        job: Job dictionary from job manager
        video_id: Video identifier for the uploaded file
        error: Optional error response if processing failed
        file_path: Optional path to saved file (for background task processing)
        metadata: Optional file metadata from validation
        params: Optional transcription parameters
    """

    job_id: str
    job: dict
    video_id: str
    error: Optional[ErrorResponse] = None
    file_path: Optional[Path] = None
    metadata: Optional[object] = None
    params: Optional[TranscriptionParams] = None


@dataclass
class UrlUploadResult:
    """Result of URL upload processing.

    Attributes:
        job_id: Unique job identifier
        job: Job dictionary from job manager
        video_id: Video identifier for the remote URL
        error: Optional error response if processing failed
        url: Optional remote media URL (for background task processing)
        metadata: Optional URL metadata from validation
        params: Optional transcription parameters
        file_path: Optional local file path (for Level 3: no re-download needed)
    """

    job_id: str
    job: dict
    video_id: str
    error: Optional[ErrorResponse] = None
    url: Optional[str] = None
    metadata: Optional[object] = None
    params: Optional[TranscriptionParams] = None
    file_path: Optional[Path] = None


class MediaEndpointService:
    """
    Service for orchestrating media transcription endpoint business logic.

    This service coordinates between validation, storage, transcription, and job
    management services to handle media transcription requests. It supports both
    Level 2 (local storage + background tasks) and Level 3 (S3 + queue) workflows.

    Example:
        >>> service = MediaEndpointService()
        >>> result = await service.handle_file_upload(
        ...     file=upload_file,
        ...     translate_to="en",
        ...     format="json",
        ...     webhook_url="https://example.com/callback"
        ... )
        >>> if result.error:
        ...     # Handle error
        ... else:
        ...     # Process success
    """

    def __init__(
        self,
        validation_service: Optional[MediaValidationService] = None,
        file_storage_service: Optional[FileStorageService] = None,
        media_download_service: Optional[MediaDownloadService] = None,
        transcription_service: Optional[TranscriptionService] = None,
        job_manager: Optional[JobManager] = None,
        queue_service: Optional[QueueService] = None,
        s3_storage_service: Optional[S3StorageService] = None,
        media_probe_service: Optional[MediaProbeService] = None,
        credits_service: Optional[CreditsService] = None,
    ):
        """Initialize MediaEndpointService.

        Args:
            validation_service: Service for validating media files and URLs.
                Defaults to new MediaValidationService instance.
            file_storage_service: Service for handling file uploads.
                Defaults to new FileStorageService instance.
            media_download_service: Service for downloading remote media.
                Defaults to new MediaDownloadService instance.
            transcription_service: Service for transcribing media.
                Defaults to new TranscriptionService instance.
            job_manager: Manager for job lifecycle.
                Defaults to new JobManager instance.
            queue_service: Optional queue service for Level 3 workflows.
                If None, Level 2 (local storage) workflow is used.
            s3_storage_service: Optional S3 storage service for Level 3 workflows.
                If None, Level 2 (local storage) workflow is used.
            media_probe_service: Optional service for probing media duration (ffprobe).
                If None, MediaProbeService instance is created.
            credits_service: Optional service for credit checks and deduction.
                If None, CreditsService instance is created.

        Returns:
            None: This method does not return a value.
        """
        self.validation_service = validation_service or MediaValidationService()
        self.media_probe_service = media_probe_service or MediaProbeService()
        self.credits_service = credits_service or CreditsService()
        self.file_storage_service = file_storage_service or FileStorageService()
        self.media_download_service = media_download_service or MediaDownloadService()
        self.transcription_service = transcription_service or TranscriptionService()
        self.job_manager = job_manager or JobManager()
        self.queue_service = queue_service
        self.s3_storage_service = s3_storage_service
        self.social_media_service = SocialMediaService()

    def is_level3_enabled(self) -> bool:
        """Check if Level 3 (queue + S3) is enabled.

        Returns:
            bool: True if both queue service and S3 storage are available and enabled,
                False otherwise.
        """
        return (
            self.queue_service is not None
            and self.s3_storage_service is not None
            and self.s3_storage_service.is_enabled()
        )

    def parse_format_parameter(
        self, format: str
    ) -> Tuple[Optional[OutputFormat], Optional[ErrorResponse]]:
        """Parse and validate format parameter.

        Args:
            format: Format string from request (e.g., "json", "srt", "vtt")

        Returns:
            Tuple[Optional[OutputFormat], Optional[ErrorResponse]]: Tuple containing:
                - OutputFormat enum if valid, None if invalid
                - ErrorResponse if format is invalid, None if valid

        Example:
            >>> service = MediaEndpointService()
            >>> output_format, error = service.parse_format_parameter("json")
            >>> output_format
            <OutputFormat.JSON: 'json'>
            >>> error is None
            True
        """
        try:
            output_format = OutputFormat(format.lower()) if format else OutputFormat.JSON
            return output_format, None
        except ValueError:
            error_response = ErrorResponse(
                code="INVALID_FORMAT",
                message=f"Invalid format: {format}. Supported formats: {[f.value for f in OutputFormat]}",
                details={
                    "provided_format": format,
                    "supported_formats": [f.value for f in OutputFormat],
                },
            )
            return None, error_response

    def parse_transcription_parameters(
        self,
        translate_to: Optional[str],
        format: str,
        webhook_url: Optional[str],
    ) -> Tuple[Optional[TranscriptionParams], Optional[ErrorResponse]]:
        """Parse and validate transcription parameters.

        Args:
            translate_to: Target language code for translation (e.g., "en", "es").
                If None, no translation is performed.
            format: Output format string (e.g., "json", "srt", "vtt")
            webhook_url: Optional webhook callback URL for job completion notifications

        Returns:
            Tuple[Optional[TranscriptionParams], Optional[ErrorResponse]]: Tuple containing:
                - TranscriptionParams if all parameters are valid, None if format is invalid
                - ErrorResponse if format is invalid, None if all parameters are valid

        Raises:
            AssertionError: If internal state is inconsistent (should not occur in normal operation)
        """
        output_format, format_error = self.parse_format_parameter(format)
        if format_error:
            return None, format_error

        # Assert output_format is not None (guaranteed if format_error is None)
        assert output_format is not None, "output_format should not be None if format_error is None"

        params = TranscriptionParams(
            translate_to=translate_to if translate_to else None,
            output_format=output_format,
            webhook_url=webhook_url if webhook_url else None,
        )
        return params, None

    def validate_uploaded_file(
        self, file: UploadFile
    ) -> Tuple[Optional[object], Optional[ErrorResponse]]:
        """Validate uploaded file.

        Args:
            file: Uploaded file to validate

        Returns:
            Tuple[Optional[object], Optional[ErrorResponse]]: Tuple containing:
                - MediaMetadata object if validation succeeds, None if validation fails
                - ErrorResponse if validation fails, None if validation succeeds

        Raises:
            Exception: If validation service raises an unexpected exception
        """
        try:
            metadata = self.validation_service.validate_upload(file)
            return metadata, None
        except Exception as e:
            logger.error(f"[MEDIA] File validation failed: {e}")
            error_response = ErrorResponse(
                code=getattr(e, "code", "VALIDATION_ERROR"),
                message=str(e),
                details=getattr(e, "details", {}),
            )
            return None, error_response

    def validate_remote_url(self, url: str) -> Tuple[Optional[object], Optional[ErrorResponse]]:
        """Validate remote URL and get media info.

        Args:
            url: Remote URL to validate

        Returns:
            Tuple[Optional[object], Optional[ErrorResponse]]: Tuple containing:
                - MediaMetadata object if validation succeeds, None if validation fails
                - ErrorResponse if validation fails, None if validation succeeds

        Raises:
            Exception: If validation or media info retrieval raises an unexpected exception
        """
        try:
            media_info = self.media_download_service.get_media_info(url)
            metadata = self.validation_service.validate_remote_url(
                url,
                content_type=media_info.get("content_type"),
                content_length=media_info.get("content_length"),
            )
            return metadata, None
        except Exception as e:
            logger.error(f"[MEDIA] URL validation failed: {e}")
            error_response = ErrorResponse(
                code=getattr(e, "code", "VALIDATION_ERROR"),
                message=str(e),
                details=getattr(e, "details", {}),
            )
            return None, error_response

    def _create_enhanced_job_data(self, job_id: str, s3_uri: str) -> EnhancedJobData:
        """Create enhanced job data for queue.

        Args:
            job_id: Job identifier
            s3_uri: S3 URI where media is stored

        Returns:
            EnhancedJobData: Enhanced job data instance configured for queue processing
        """
        return EnhancedJobData(
            job_id=job_id,
            priority=JobPriority.NORMAL,
            retry_count=0,
            max_retries=settings.queue_max_retries,
            media_storage_path=s3_uri,
            result_storage_path=None,
            assigned_worker_id=None,
            queue_position=None,
            estimated_processing_time=None,
        )

    async def handle_level3_file_upload(
        self,
        file: UploadFile,
        job_id: str,
        metadata: object,
        skip_enqueue: bool = False,
    ) -> Tuple[Optional[Path], Optional[str], Optional[ErrorResponse]]:
        """Handle Level 3 flow for file upload: save, upload to S3, keep local file for processing.

        Saves the uploaded file locally, uploads it to S3 for backup/storage, and keeps
        the local file for direct processing (no re-download needed). Enqueues the job
        unless skip_enqueue=True (used for credit pre-check before enqueue).

        Args:
            file: Uploaded file
            job_id: Job identifier
            metadata: File metadata from validation
            skip_enqueue: If True, save and upload but do not enqueue (for pre-check flow)

        Returns:
            Tuple[Optional[Path], Optional[str], Optional[ErrorResponse]]: Tuple containing:
                - Local file path if successful, None if error
                - S3 URI if successful, None if error
                - ErrorResponse if error occurs, None if successful

        Raises:
            ValueError: If S3 storage service or queue service is not available
        """
        try:
            media_format = metadata.media_format if hasattr(metadata, "media_format") else "mp4"
            file_path = await self.file_storage_service.save_upload(
                file, job_id, extension=media_format
            )
            if self.s3_storage_service is None:
                raise ValueError("S3 storage service is not available")
            s3_uri = self.s3_storage_service.upload_media(file_path, job_id, media_format)
            logger.info(f"[MEDIA] File uploaded to S3: {s3_uri}, keeping local file for processing")

            if not skip_enqueue:
                enhanced_job = self._create_enhanced_job_data(job_id, s3_uri)
                if self.queue_service is None:
                    raise ValueError("Queue service is not available")
                self.queue_service.enqueue_job(enhanced_job, JobPriority.NORMAL)
                logger.info(f"[MEDIA] Job {job_id} enqueued with S3 media: {s3_uri}")

            return file_path, s3_uri, None

        except Exception as e:
            logger.error(f"[MEDIA] Failed to upload to S3 or enqueue job {job_id}: {e}")
            self.job_manager.fail_job(job_id, f"Failed to upload to S3: {str(e)}")
            error_response = ErrorResponse(
                code="STORAGE_ERROR",
                message=f"Failed to upload file to S3: {str(e)}",
                details={"job_id": job_id},
            )
            return None, None, error_response

    def handle_level3_url_upload(
        self, url: str, job_id: str, metadata: object
    ) -> Tuple[Optional[Path], Optional[str], Optional[ErrorResponse]]:
        """Handle Level 3 flow for URL: download, upload to S3, keep local file for processing.

        Downloads the media from the remote URL, uploads it to S3 for backup/storage,
        and keeps the local file for direct processing (no re-download needed).
        Enqueues the job in the queue service for tracking.

        Args:
            url: Remote media URL
            job_id: Job identifier
            metadata: URL metadata from validation

        Returns:
            Tuple[Optional[Path], Optional[str], Optional[ErrorResponse]]: Tuple containing:
                - Local file path if successful, None if error
                - S3 URI if successful, None if error
                - ErrorResponse if error occurs, None if successful

        Raises:
            ValueError: If S3 storage service or queue service is not available
        """
        try:
            file_path = self.media_download_service.download_media(url, job_id)
            extension = metadata.media_format if hasattr(metadata, "media_format") else "mp4"
            if self.s3_storage_service is None:
                raise ValueError("S3 storage service is not available")
            s3_uri = self.s3_storage_service.upload_media(Path(file_path), job_id, extension)
            logger.info(f"[MEDIA] File uploaded to S3: {s3_uri}, keeping local file for processing")

            enhanced_job = self._create_enhanced_job_data(job_id, s3_uri)

            if self.queue_service is None:
                raise ValueError("Queue service is not available")
            self.queue_service.enqueue_job(enhanced_job, JobPriority.NORMAL)
            logger.info(f"[MEDIA] Job {job_id} enqueued with S3 media: {s3_uri}")

            return Path(file_path), s3_uri, None

        except Exception as e:
            logger.error(f"[MEDIA] Failed to download/upload to S3 or enqueue job {job_id}: {e}")
            self.job_manager.fail_job(job_id, f"Failed to process media URL: {str(e)}")
            error_response = ErrorResponse(
                code="STORAGE_ERROR",
                message=f"Failed to process media URL: {str(e)}",
                details={"job_id": job_id},
            )
            return None, None, error_response

    def handle_level3_file_upload_from_path(
        self, file_path: Path, job_id: str, metadata: object
    ) -> Tuple[Optional[Path], Optional[str], Optional[ErrorResponse]]:
        """Handle Level 3 flow for an existing file: upload to S3 and enqueue job.

        Uploads an already-existing local file to S3 for backup/storage, and keeps
        the local file for direct processing (no re-download needed). Enqueues the job
        in the queue service for tracking.

        This is used for social media downloads where yt-dlp has already saved the file.

        Args:
            file_path: Path to the existing local file
            job_id: Job identifier
            metadata: File metadata from validation

        Returns:
            Tuple[Optional[Path], Optional[str], Optional[ErrorResponse]]: Tuple containing:
                - Local file path if successful, None if error
                - S3 URI if successful, None if error
                - ErrorResponse if error occurs, None if successful

        Raises:
            ValueError: If S3 storage service or queue service is not available
        """
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            extension = metadata.media_format if hasattr(metadata, "media_format") else "mp4"
            
            if self.s3_storage_service is None:
                raise ValueError("S3 storage service is not available")
            
            s3_uri = self.s3_storage_service.upload_media(file_path, job_id, extension)
            logger.info(f"[MEDIA] File uploaded to S3: {s3_uri}, keeping local file for processing")

            enhanced_job = self._create_enhanced_job_data(job_id, s3_uri)

            if self.queue_service is None:
                raise ValueError("Queue service is not available")
            self.queue_service.enqueue_job(enhanced_job, JobPriority.NORMAL)
            logger.info(f"[MEDIA] Job {job_id} enqueued with S3 media: {s3_uri}")

            return file_path, s3_uri, None

        except Exception as e:
            logger.error(f"[MEDIA] Failed to upload to S3 or enqueue job {job_id}: {e}")
            self.job_manager.fail_job(job_id, f"Failed to upload to S3: {str(e)}")
            error_response = ErrorResponse(
                code="STORAGE_ERROR",
                message=f"Failed to upload file to S3: {str(e)}",
                details={"job_id": job_id},
            )
            return None, None, error_response

    async def process_media_upload_background(
        self,
        job_id: str,
        file_path: Path,
        metadata: object,
        params: TranscriptionParams,
    ) -> None:
        """Background task to process uploaded media file.

        Handles the complete workflow for uploaded media transcription:
        1. Updates job status to PROCESSING
        2. Uploads to S3 if enabled (even without queue)
        3. Transcribes media using Whisper ASR
        4. Completes job with result or fails with error
        5. Sends webhook callback if webhookUrl provided
        6. Cleans up uploaded file

        Args:
            job_id: Job identifier
            file_path: Path to uploaded file
            metadata: File metadata from validation
            params: Transcription parameters (format, translate_to, webhook_url)

        Returns:
            None: This method does not return a value. Results are stored in job manager.

        Raises:
            Exception: If transcription or job completion fails (errors are logged and job is marked as failed)
        """
        s3_uri = None
        use_s3_for_level2 = (
            self.s3_storage_service is not None and self.s3_storage_service.is_enabled()
        )

        try:
            self.job_manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)

            if use_s3_for_level2 and self.s3_storage_service is not None:
                try:
                    logger.info(f"[MEDIA] Uploading media to S3 for job {job_id}...")
                    media_format = (
                        metadata.media_format if hasattr(metadata, "media_format") else "mp4"
                    )
                    s3_uri = self.s3_storage_service.upload_media(file_path, job_id, media_format)
                    logger.info(
                        f"[MEDIA] Successfully uploaded media to S3 for job {job_id}: {s3_uri}"
                    )
                except Exception as e:
                    logger.error(
                        f"[MEDIA] Failed to upload to S3 for job {job_id}: {e}",
                        exc_info=True,
                    )

            result = await self.transcription_service.transcribe_media(
                file_path=file_path,
                translate_to=params.translate_to,
                format=params.output_format,
                diarise=False,
            )

            language = result.get("language")
            model = result.get("model", "whisper-base")
            duration = result.get("duration")

            self.job_manager.complete_job(
                job_id,
                result,
                language=language,
                model=model,
                duration=duration,
                source="asr",
            )

            # Credit deduction on completion (Phase 2b)
            job_after = self.job_manager.get_job(job_id)
            user_id = job_after.get("user_id") if job_after else None
            ip_hash = job_after.get("ip_hash") if job_after else None
            transcript_text = result.get("transcript") or result.get("content") or ""
            source_url_val = job_after.get("video_url") if job_after else None
            if user_id and duration is not None and duration > 0:
                minutes_charged = round(duration / 60.0, 2)
                await self.credits_service.deduct_asr_minutes(
                    user_id, job_id, minutes_charged, ip_hash=ip_hash
                )
                await self.credits_service.update_transcription_job(
                    job_id,
                    status="completed",
                    duration_minutes=minutes_charged,
                    minutes_charged=minutes_charged,
                    result_ref=job_after.get("resultRef"),
                    source_url=source_url_val,
                    transcript=transcript_text,
                )

            if params.webhook_url:
                from app.services.infrastructure.webhook_service import \
                    WebhookService

                webhook_service = WebhookService()
                await webhook_service.send_webhook(params.webhook_url, result, job_id)

        except Exception as e:
            logger.error(f"[MEDIA] Error processing uploaded media for job {job_id}: {e}")
            self.job_manager.fail_job(job_id, f"Processing failed: {str(e)}")
            job_for_update = self.job_manager.get_job(job_id)
            if job_for_update and job_for_update.get("user_id"):
                await self.credits_service.update_transcription_job(
                    job_id, status="failed", error_message=str(e)
                )
        finally:
            if not use_s3_for_level2 or s3_uri is None:
                try:
                    self.file_storage_service.cleanup_upload(file_path)
                except Exception as cleanup_error:
                    logger.error(
                        f"[MEDIA] Failed to cleanup file {file_path} for job {job_id}: {cleanup_error}"
                    )

    async def process_media_url_background(
        self,
        job_id: str,
        url: str,
        metadata: object,
        params: TranscriptionParams,
    ) -> None:
        """Background task to process remote media URL.

        Handles the complete workflow for remote media URL transcription:
        1. Updates job status to PROCESSING
        2. Downloads media from remote URL
        3. Uploads to S3 if enabled (even without queue)
        4. Transcribes media using Whisper ASR
        5. Completes job with result or fails with error
        6. Sends webhook callback if webhookUrl provided
        7. Cleans up downloaded file

        Args:
            job_id: Job identifier
            url: Remote media URL to download and transcribe
            metadata: URL metadata from validation
            params: Transcription parameters (format, translate_to, webhook_url)

        Returns:
            None: This method does not return a value. Results are stored in job manager.

        Raises:
            Exception: If download, transcription, or job completion fails
                (errors are logged and job is marked as failed)
        """
        file_path = None
        s3_uri = None
        use_s3_for_level2 = (
            self.s3_storage_service is not None and self.s3_storage_service.is_enabled()
        )

        try:
            self.job_manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)

            # For direct URL streaming to Runpod, skip download and pass URL directly
            # The whisper service will handle URL vs local file path
            logger.info(f"[MEDIA] Streaming URL directly to transcription service: {url}")
            
            # Call whisper service directly with URL as string
            from app.services.transcription.whisper_service import WhisperService
            whisper_service = WhisperService.get_instance()
            
            segments, language, confidence = await whisper_service.transcribe_async(
                audio_path=url,  # Pass URL directly as string
                translate_to=params.translate_to,
            )
            
            # Format result
            result = self.transcription_service._format_asr_result(
                segments, language, confidence, params.output_format
            )
            if params.output_format.value == "json" and isinstance(result, dict):
                result["duration"] = max((segment.end for segment in segments), default=0.0)
                result["model"] = "runpod-whisper"

            language = result.get("language")
            model = result.get("model", "whisper-base")
            duration = result.get("duration")

            self.job_manager.complete_job(
                job_id,
                result,
                language=language,
                model=model,
                duration=duration,
                source="asr",
            )

            # Credit deduction on completion (Phase 2b)
            job_after = self.job_manager.get_job(job_id)
            user_id = job_after.get("user_id") if job_after else None
            transcript_text = result.get("transcript") or result.get("content") or ""
            source_url_val = job_after.get("video_url") if job_after else url
            if user_id and duration is not None and duration > 0:
                minutes_charged = round(duration / 60.0, 2)
                ip_hash = job_after.get("ip_hash") if job_after else None
                await self.credits_service.deduct_asr_minutes(
                    user_id, job_id, minutes_charged, ip_hash=ip_hash
                )
                await self.credits_service.update_transcription_job(
                    job_id,
                    status="completed",
                    duration_minutes=minutes_charged,
                    minutes_charged=minutes_charged,
                    result_ref=job_after.get("resultRef"),
                    source_url=source_url_val,
                    transcript=transcript_text,
                )

            if params.webhook_url:
                from app.services.infrastructure.webhook_service import \
                    WebhookService

                webhook_service = WebhookService()
                await webhook_service.send_webhook(params.webhook_url, result, job_id)

        except Exception as e:
            logger.error(f"[MEDIA] Error processing remote media for job {job_id}: {e}")
            self.job_manager.fail_job(job_id, f"Processing failed: {str(e)}")
            job_for_update = self.job_manager.get_job(job_id)
            if job_for_update and job_for_update.get("user_id"):
                await self.credits_service.update_transcription_job(
                    job_id, status="failed", error_message=str(e)
                )
        # No cleanup needed - we didn't download the file, just streamed the URL

    async def process_level3_job(self, job_id: str, file_path: Path) -> None:
        """Process a Level 3 job using the local file (no S3 re-download needed).

        Transcribes the media file that was already downloaded/uploaded,
        completes the job, and cleans up the local file. This method is called
        for Level 3 workflows where the file is already available locally.

        Args:
            job_id: Job identifier
            file_path: Path to the local media file (already downloaded/uploaded)

        Returns:
            None: This method does not return a value. Results are stored in job manager.

        Raises:
            Exception: If transcription or job completion fails
                (errors are logged, job is marked as failed, and may be requeued)
        """
        try:
            job = self.job_manager.get_job(job_id)
            if not job:
                logger.error(f"[MEDIA] Job {job_id} not found in job manager")
                return

            self.job_manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)

            import uuid

            worker_id = f"api-worker-{uuid.uuid4().hex[:8]}"
            if self.queue_service is not None:
                try:
                    job_data = self.queue_service.dequeue_job(worker_id)
                    if job_data and job_data.job_id != job_id:
                        self.queue_service.enqueue_job(job_data, JobPriority.NORMAL)
                except Exception as e:
                    logger.warning(f"[MEDIA] Could not dequeue job {job_id} from queue: {e}")

            translate_to = job.get("translate_to")
            format_str = job.get("format", "json")
            output_format = OutputFormat(format_str)

            logger.info(
                f"[MEDIA] Transcribing media for job {job_id} using local file: {file_path}"
            )
            result = await self.transcription_service.transcribe_media(
                file_path=file_path,
                translate_to=translate_to,
                format=output_format,
                diarise=job.get("diarise", False),
            )

            language = result.get("language")
            model = result.get("model", "whisper-base")
            duration = result.get("duration")

            self.job_manager.complete_job(
                job_id=job_id,
                result=result,
                language=language,
                model=model,
                duration=duration,
                source="asr",
            )

            # Credit deduction on completion (Phase 2b)
            job_after = self.job_manager.get_job(job_id)
            user_id = job_after.get("user_id") if job_after else None
            transcript_text = result.get("transcript") or result.get("content") or ""
            source_url_val = job_after.get("video_url") if job_after else None
            if user_id and duration is not None and duration > 0:
                minutes_charged = round(duration / 60.0, 2)
                ip_hash = job_after.get("ip_hash") if job_after else None
                await self.credits_service.deduct_asr_minutes(
                    user_id, job_id, minutes_charged, ip_hash=ip_hash
                )
                await self.credits_service.update_transcription_job(
                    job_id,
                    status="completed",
                    duration_minutes=minutes_charged,
                    minutes_charged=minutes_charged,
                    result_ref=job_after.get("resultRef"),
                    source_url=source_url_val,
                    transcript=transcript_text,
                )

            if self.queue_service is not None:
                try:
                    self.queue_service.remove_job_from_processing(job_id)
                except Exception as e:
                    logger.warning(
                        f"[MEDIA] Could not remove job {job_id} from processing queue: {e}"
                    )

            webhook_url = job.get("webhook_url")
            if webhook_url:
                from app.services.infrastructure.webhook_service import \
                    WebhookService

                webhook_service = WebhookService()
                await webhook_service.send_webhook(webhook_url, result, job_id)

            logger.info(f"[MEDIA] Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"[MEDIA] Error processing Level 3 job {job_id}: {e}", exc_info=True)
            self.job_manager.fail_job(job_id, f"Processing failed: {str(e)}")
            job_for_update = self.job_manager.get_job(job_id)
            if job_for_update and job_for_update.get("user_id"):
                await self.credits_service.update_transcription_job(
                    job_id, status="failed", error_message=str(e)
                )
            if self.queue_service is not None:
                try:
                    self.queue_service.requeue_failed_job(job_id, str(e))
                except Exception as requeue_error:
                    logger.error(f"[MEDIA] Failed to requeue job {job_id}: {requeue_error}")
        finally:
            if file_path and file_path.exists():
                try:
                    if str(file_path).startswith("/app/temp_uploads/"):
                        self.file_storage_service.cleanup_upload(file_path)
                    elif str(file_path).startswith("/app/temp_downloads/"):
                        self.media_download_service.cleanup_media(str(file_path))
                    else:
                        file_path.unlink()
                    logger.debug(f"[MEDIA] Cleaned up local file: {file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"[MEDIA] Failed to cleanup file {file_path}: {cleanup_error}")

    def create_job_response(self, job_id: str, job: dict, video_id: str) -> JobResponse:
        """Create job response from job data.

        Args:
            job_id: Job identifier
            job: Job dictionary from job manager
            video_id: Video identifier

        Returns:
            JobResponse: Job response object with current job status and metadata
        """
        updated_job = self.job_manager.get_job(job_id, include_result=False)
        return JobResponse(
            job_id=job_id,
            status=updated_job["status"] if updated_job else job["status"],
            created_at=job["created_at"],
            video_id=video_id,
            video_url=job.get("video_url"),
        )

    async def handle_file_upload(
        self,
        file: UploadFile,
        translate_to: Optional[str],
        format: str,
        webhook_url: Optional[str],
        user_id: Optional[str] = None,
        ip_hash: Optional[str] = None,
    ) -> FileUploadResult:
        """Handle file upload transcription request.

        Validates the uploaded file, creates a job, and either:
        - Level 3: Saves file, uploads to S3, enqueues job, returns file path for processing
        - Level 2: Saves file locally, returns file path for background task processing

        Args:
            file: Uploaded file to transcribe
            translate_to: Target language code for translation (e.g., "en", "es").
                If None, no translation is performed.
            format: Output format string (e.g., "json", "srt", "vtt")
            webhook_url: Optional webhook callback URL for job completion notifications

        Returns:
            FileUploadResult: Result object containing job information, file path,
                metadata, and parameters. If validation fails, error field is set.

        Raises:
            AssertionError: If internal state is inconsistent (should not occur in normal operation)
        """
        logger.info(
            f"[MEDIA] File upload request: filename={file.filename}, "
            f"size={file.size}, format={format}, translateTo={translate_to}"
        )

        metadata, validation_error = self.validate_uploaded_file(file)
        if validation_error:
            return FileUploadResult(job_id="", job={}, video_id="", error=validation_error)

        params, format_error = self.parse_transcription_parameters(
            translate_to, format, webhook_url
        )
        if format_error:
            return FileUploadResult(job_id="", job={}, video_id="", error=format_error)

        assert params is not None, "params should not be None if format_error is None"

        job_id = str(uuid.uuid4())
        video_id = f"upload_{job_id}"

        # Credit pre-check: need duration first; for file upload we save then probe
        # So we create job, save, probe, pre-check, then continue or fail
        job_id, job = self.job_manager.create_job(
            video_url=f"upload:{file.filename}",
            video_id=video_id,
            translate_to=params.translate_to,
            format=params.output_format.value,
            diarise=False,
            webhook_url=params.webhook_url,
            user_id=user_id,
            ip_hash=ip_hash,
        )

        use_level3 = self.is_level3_enabled()

        if use_level3:
            file_path, s3_uri, level3_error = await self.handle_level3_file_upload(
                file, job_id, metadata, skip_enqueue=True
            )
            if level3_error:
                return FileUploadResult(
                    job_id=job_id, job=job, video_id=video_id, error=level3_error
                )
            # Probe duration for credit pre-check (Phase 2b)
            if file_path and metadata is not None:
                try:
                    duration = await self.media_probe_service.get_local_duration(file_path)
                    if hasattr(metadata, "duration"):
                        metadata.duration = duration
                except Exception as e:
                    logger.warning(f"[MEDIA] Could not probe duration for upload: {e}")
            # Pre-check: reject if insufficient credits
            duration_minutes = (getattr(metadata, "duration", None) or 0) / 60.0
            can_start, err_msg = await self.credits_service.check_can_start_asr_job(
                user_id, duration_minutes if duration_minutes > 0 else None, ip_hash=ip_hash
            )
            if not can_start:
                self.job_manager.fail_job(job_id, err_msg or "Insufficient credits")
                if file_path and file_path.exists():
                    try:
                        self.file_storage_service.cleanup_upload(file_path)
                    except Exception:
                        pass
                return FileUploadResult(
                    job_id=job_id,
                    job=job,
                    video_id=video_id,
                    error=ErrorResponse(
                        code="INSUFFICIENT_CREDITS",
                        message=err_msg or "Insufficient credits",
                        details={"duration_minutes": duration_minutes},
                    ),
                )
            # Enqueue now that pre-check passed
            if s3_uri and self.queue_service:
                enhanced_job = self._create_enhanced_job_data(job_id, s3_uri)
                self.queue_service.enqueue_job(enhanced_job, JobPriority.NORMAL)
                logger.info(f"[MEDIA] Job {job_id} enqueued with S3 media: {s3_uri}")
            self.job_manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)
            return FileUploadResult(
                job_id=job_id,
                job=job,
                video_id=video_id,
                error=None,
                file_path=file_path,
                metadata=metadata,
                params=params,
            )
        else:
            try:
                media_format = metadata.media_format if hasattr(metadata, "media_format") else "mp4"
                file_path = await self.file_storage_service.save_upload(
                    file, job_id, extension=media_format
                )
            except Exception as e:
                logger.error(f"[MEDIA] Failed to save upload for job {job_id}: {e}")
                self.job_manager.fail_job(job_id, f"Failed to save upload: {str(e)}")
                error_response = ErrorResponse(
                    code="STORAGE_ERROR",
                    message=f"Failed to save uploaded file: {str(e)}",
                    details={"job_id": job_id},
                )
                return FileUploadResult(
                    job_id=job_id, job=job, video_id=video_id, error=error_response
                )

            # Probe duration for credit pre-check (Phase 2b)
            if metadata is not None:
                try:
                    duration = await self.media_probe_service.get_local_duration(file_path)
                    if hasattr(metadata, "duration"):
                        metadata.duration = duration
                except Exception as e:
                    logger.warning(f"[MEDIA] Could not probe duration for upload: {e}")

            # Pre-check: reject if insufficient credits
            duration_minutes = (getattr(metadata, "duration", None) or 0) / 60.0
            can_start, err_msg = await self.credits_service.check_can_start_asr_job(
                user_id, duration_minutes if duration_minutes > 0 else None, ip_hash=ip_hash
            )
            if not can_start:
                self.job_manager.fail_job(job_id, err_msg or "Insufficient credits")
                try:
                    self.file_storage_service.cleanup_upload(file_path)
                except Exception:
                    pass
                return FileUploadResult(
                    job_id=job_id,
                    job=job,
                    video_id=video_id,
                    error=ErrorResponse(
                        code="INSUFFICIENT_CREDITS",
                        message=err_msg or "Insufficient credits",
                        details={"duration_minutes": duration_minutes},
                    ),
                )

            self.job_manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)

            return FileUploadResult(
                job_id=job_id,
                job=job,
                video_id=video_id,
                error=None,
                file_path=file_path,
                metadata=metadata,
                params=params,
            )

        return FileUploadResult(job_id=job_id, job=job, video_id=video_id)

    async def handle_remote_url(
        self,
        url: str,
        translate_to: Optional[str],
        format: str,
        webhook_url: Optional[str],
        user_id: Optional[str] = None,
        ip_hash: Optional[str] = None,
    ) -> UrlUploadResult:
        """Handle remote URL transcription request.

        Validates the remote URL, creates a job, and either:
        - Level 3: Downloads file, uploads to S3, enqueues job, returns file path for processing
        - Level 2: Returns URL and metadata for background task to download and process

        Args:
            url: Remote media URL to transcribe
            translate_to: Target language code for translation (e.g., "en", "es").
                If None, no translation is performed.
            format: Output format string (e.g., "json", "srt", "vtt")
            webhook_url: Optional webhook callback URL for job completion notifications

        Returns:
            UrlUploadResult: Result object containing job information, URL, metadata,
                and parameters. If validation fails, error field is set.

        Raises:
            AssertionError: If internal state is inconsistent (should not occur in normal operation)
        """
        logger.info(
            f"[MEDIA] Remote URL request: url={url}, "
            f"format={format}, translateTo={translate_to}"
        )

        # Check if this is a social media URL - these need special handling
        # because they often return temporary m3u8/HLS streams that Runpod can't process
        original_url = url
        is_social_media = self.social_media_service.is_social_media_url(url)
        social_media_file_path: Optional[Path] = None
        social_media_metadata: Optional[MediaMetadata] = None
        
        if is_social_media:
            try:
                logger.info(f"[MEDIA] Detected social media URL: {url}")
                # Download the media locally first (yt-dlp handles m3u8 downloads)
                downloaded_file, media_info = await self.social_media_service.download_media(url)
                social_media_file_path = downloaded_file
                
                # Create metadata from the downloaded file
                from app.services.media.media_validation import MediaMetadata
                import mimetypes
                
                file_size = downloaded_file.stat().st_size
                file_extension = downloaded_file.suffix.lstrip('.').lower() or 'mp4'
                mime_type = mimetypes.guess_type(str(downloaded_file))[0] or 'video/mp4'
                media_type = 'video' if file_extension in ['mp4', 'mkv', 'avi', 'mov', 'webm'] else 'audio'
                
                duration = media_info.get("duration")
                if duration is not None:
                    duration = float(duration)
                social_media_metadata = MediaMetadata(
                    media_type=media_type,
                    media_format=file_extension,
                    file_size=file_size,
                    mime_type=mime_type,
                    original_filename=downloaded_file.name,
                    is_valid=True,
                    duration=duration,
                )
                
                logger.info(
                    f"[MEDIA] Downloaded social media content: "
                    f"file={downloaded_file.name}, size={file_size} bytes, "
                    f"platform={media_info.get('platform')}"
                )
            except Exception as e:
                logger.error(f"[MEDIA] Failed to download social media from {original_url}: {e}")
                return UrlUploadResult(
                    job_id="",
                    job={},
                    video_id="",
                    error=ErrorResponse(
                        code="SOCIAL_MEDIA_DOWNLOAD_FAILED",
                        message=f"Failed to download media from social media URL: {str(e)}",
                        details={"original_url": original_url, "error": str(e)},
                    ),
                )

        # For regular URLs (not social media), validate the remote URL
        if not is_social_media:
            metadata, validation_error = self.validate_remote_url(url)
            if validation_error:
                return UrlUploadResult(job_id="", job={}, video_id="", error=validation_error)
            # Probe duration for direct URLs (ffprobe on HTTP URL)
            try:
                duration = await self.media_probe_service.get_remote_duration(url)
                if metadata is not None and hasattr(metadata, "duration"):
                    metadata.duration = duration
            except Exception as e:
                logger.warning(f"[MEDIA] Could not probe duration for URL: {e}")
        else:
            # Use the metadata from the downloaded social media file
            metadata = social_media_metadata

        params, format_error = self.parse_transcription_parameters(
            translate_to, format, webhook_url
        )
        if format_error:
            # Clean up downloaded file if there was an error
            if social_media_file_path and social_media_file_path.exists():
                try:
                    social_media_file_path.unlink()
                except:
                    pass
            return UrlUploadResult(job_id="", job={}, video_id="", error=format_error)

        assert params is not None, "params should not be None if format_error is None"

        # Pre-check: reject if insufficient credits (before creating job)
        duration_minutes = (getattr(metadata, "duration", None) or 0) / 60.0
        can_start, err_msg = await self.credits_service.check_can_start_asr_job(
            user_id, duration_minutes if duration_minutes > 0 else None, ip_hash=ip_hash
        )
        if not can_start:
            if social_media_file_path and social_media_file_path.exists():
                try:
                    social_media_file_path.unlink()
                except Exception:
                    pass
            return UrlUploadResult(
                job_id="",
                job={},
                video_id="",
                error=ErrorResponse(
                    code="INSUFFICIENT_CREDITS",
                    message=err_msg or "Insufficient credits",
                    details={"duration_minutes": duration_minutes},
                ),
            )

        job_id = str(uuid.uuid4())
        video_id = f"url_{job_id}"

        job_id, job = self.job_manager.create_job(
            video_url=original_url if is_social_media else url,
            video_id=video_id,
            translate_to=params.translate_to,
            format=params.output_format.value,
            diarise=False,
            webhook_url=params.webhook_url,
            user_id=user_id,
            ip_hash=ip_hash,
        )

        use_level3 = self.is_level3_enabled()

        if use_level3:
            if is_social_media and social_media_file_path:
                # For social media: upload downloaded file to S3 (like file uploads)
                # because m3u8 streams can't be passed directly to Runpod
                logger.info(
                    f"[MEDIA] Level 3 social media processing: "
                    f"uploading downloaded file to S3"
                )
                
                file_path, s3_uri, level3_error = self.handle_level3_file_upload_from_path(
                    social_media_file_path, job_id, metadata
                )
                
                # Note: File is NOT cleaned up here - it's needed for Level 3 processing
                # The file will be cleaned up after transcription completes in process_level3_job
                
                if level3_error:
                    return UrlUploadResult(
                        job_id=job_id, job=job, video_id=video_id, error=level3_error
                    )
                
                self.job_manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)
                return UrlUploadResult(
                    job_id=job_id,
                    job=job,
                    video_id=video_id,
                    error=None,
                    file_path=file_path,  # Signals to use local file processing path
                    metadata=metadata,
                    params=params,
                )
            else:
                # For regular URLs: stream directly to transcription service
                logger.info(f"[MEDIA] Level 3 URL processing: streaming directly to transcription service without download")
                self.job_manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)
                return UrlUploadResult(
                    job_id=job_id,
                    job=job,
                    video_id=video_id,
                    error=None,
                    url=url,
                    metadata=metadata,
                    params=params,
                    # No file_path - signals to use direct URL streaming path
                )
        else:
            self.job_manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)

            return UrlUploadResult(
                job_id=job_id,
                job=job,
                video_id=video_id,
                error=None,
                url=original_url if is_social_media else url,
                metadata=metadata,
                params=params,
            )

        return UrlUploadResult(job_id=job_id, job=job, video_id=video_id)
