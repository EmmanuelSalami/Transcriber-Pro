"""Media transcription endpoint for uploaded files and remote URLs."""

import logging
import uuid
from typing import Optional, Union

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form,
                     HTTPException, Request, Response, UploadFile, status)
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address

from app.core.auth import get_rate_limit_key, get_user_id_from_request, limiter, verify_api_key
from app.core.config import settings
from app.core.ip_utils import get_client_ip, hash_ip
from app.models.schemas import (ErrorResponse, JobResponse,
                                TranscriptionResponse)
from app.services.credits.credits_service import (
    CreditsService,
    FREE_PLAN_YOUTUBE_COUNT,
)
from app.services.jobs.queue_service import QueueService
from app.services.media.media_endpoint_service import MediaEndpointService
from app.services.media.s3_storage_service import S3StorageService

credits_service = CreditsService()

logger = logging.getLogger(__name__)

router = APIRouter()

queue_service: Optional[QueueService] = None
s3_storage_service: Optional[S3StorageService] = None

if settings.s3_enabled:
    try:
        s3_storage_service = S3StorageService()
        if not s3_storage_service.is_enabled():
            logger.warning("S3 storage service initialized but not enabled (check configuration)")
            s3_storage_service = None
        else:
            logger.info(
                f"S3 storage service initialized successfully (bucket: {settings.s3_bucket_name})"
            )
    except Exception as e:
        logger.error(f"Failed to initialize S3 storage service: {e}", exc_info=True)
        s3_storage_service = None
else:
    logger.info("S3 storage is disabled (S3_ENABLED=false)")

if settings.queue_backend == "redis":
    try:
        queue_service = QueueService()
    except Exception as e:
        logger.warning(f"Failed to initialize queue service: {e}")

media_endpoint_service = MediaEndpointService(
    queue_service=queue_service,
    s3_storage_service=s3_storage_service,
    credits_service=credits_service,
)


def get_rate_limit_key_from_request(request: Request) -> str:
    """Extract API key from request and generate rate limit key.

    Extracts the Bearer token from the Authorization header and generates
    a rate limit key. In production, requires API key. Falls back to IP address
    only in development mode.

    Args:
        request: FastAPI request object containing headers.

    Returns:
        str: Rate limit key string in format "api_key:{key}" if API key found,
            otherwise returns the client's IP address (dev mode only).

    Raises:
        HTTPException: 401 if no API key provided in production mode.

    Example:
        If Authorization header contains "Bearer my-api-key", returns "api_key:my-api-key".
        If no Authorization header in production, raises HTTPException.
        If no Authorization header in dev mode, returns the client's IP address.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        api_key = auth_header.replace("Bearer ", "")
        return get_rate_limit_key(api_key)

    if settings.is_production():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required for rate limiting",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return get_remote_address(request)


@router.post(
    "/media",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Transcribe Media File",
    description="""
    **Request Parameters** (multipart/form-data):

    **Input Parameters (Required - provide one)**:
    - **`file`**: Upload file (multipart) - Media file to upload. Supported formats: `mp3`, `wav`, `m4a`, `mp4`, `mkv`. Maximum file size: 500MB.
    - **`url`**: Remote media URL - Direct HTTP/HTTPS URL to a media file (or S3/R2 signed URL). Example: `https://example.com/audio.mp3` or `https://bucket.s3.amazonaws.com/file.mp3?X-Amz-Signature=...`
    
    **Note**: Either `file` OR `url` must be provided (not both).

    **Optional Parameters**:
    - **`translateTo`**: Target language code for translation (ISO 639-1, e.g., `en`, `es`, `fr`, `de`). If not provided, transcription will be in the original detected language.
    - **`format`**: Output format - `json` (default, full metadata with segments), `text` (plain text), `srt` (SubRip), `vtt` (WebVTT).
    - **`webhookUrl`**: Optional webhook callback URL. When job completes, a POST request with full transcription result will be sent to this URL. Includes retry logic, timeout protection, and SSRF protection.

    **Supported Media Types**:
    - Audio formats: mp3, wav, m4a, flac, ogg
    - Video formats: mp4, mkv, avi, mov, webm

    **Additional Features**:
    - Automatic language detection
    - Optional translation to target language (ISO 639-1 codes)
    - Multiple output formats: JSON, Text, SRT, VTT

    **Rate Limiting**: Each API key has a rate limit per minute.
    """,
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute", key_func=get_rate_limit_key_from_request)
async def transcribe_media(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
    file: UploadFile = File(None),
    url: str = Form(None, max_length=settings.max_url_length),
    translateTo: str = Form(None, max_length=settings.max_translate_to_length),
    format: str = Form("json", max_length=settings.max_format_length),
    webhookUrl: str = Form(None, max_length=settings.max_url_length),
) -> Union[TranscriptionResponse, Response, JobResponse]:
    """Transcribe media file endpoint.

    Supports two input methods:
    1. File upload (multipart/form-data): Upload a media file directly
    2. Remote URL (form field): Provide a URL to download media from

    All media transcription goes through async processing and returns a job ID.
    Clients should poll GET /v1/jobs/{job_id} to get results.

    Args:
        request: FastAPI request object (required for rate limiting).
        background_tasks: FastAPI background tasks for async processing.
        api_key: Verified API key from Bearer token (injected via dependency).
        file: Uploaded media file (optional, for file upload).
        url: Remote media URL (optional, for remote URL processing).
        translateTo: Optional target language code for translation (ISO 639-1).
        format: Output format (json, text, srt, vtt, default: json).
        webhookUrl: Optional webhook callback URL for completion notification.

    Returns:
        Union[TranscriptionResponse, Response, JobResponse]: Job response with job_id
            for polling. The response type depends on the processing mode and format.

    Raises:
        TranscriptionError: For transcription-related errors (handled by global
            error handlers).
        HTTPException: For authentication or rate limiting errors.
        InvalidFileTypeError: If file type is not supported.
        FileTooLargeError: If file size exceeds maximum allowed size.

    Example:
        >>> POST /v1/transcriptions/media (multipart/form-data)
        >>> file: audio.mp3
        >>> translateTo: en
        >>> format: json
        >>> webhookUrl: https://example.com/callback

        OR

        >>> POST /v1/transcriptions/media (multipart/form-data)
        >>> url: https://cdn.example.com/audio.mp3
        >>> translateTo: en
        >>> format: json
        >>> webhookUrl: https://example.com/callback
    """
    user_id = await get_user_id_from_request(request) or None
    ip_hash = hash_ip(get_client_ip(request))

    has_file = file and file.filename
    has_url = url and url.strip()

    if has_file and has_url:
        error_response = ErrorResponse(
            code="INVALID_INPUT",
            message="Cannot provide both 'file' and 'url' parameters. Please provide either a file upload OR a remote URL, not both.",
            details={
                "provided": "both",
                "required": "one_of",
                "options": ["file", "url"],
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump(),
        )

    if has_file:
        file_result = await media_endpoint_service.handle_file_upload(
            file, translateTo, format, webhookUrl, user_id=user_id, ip_hash=ip_hash
        )

        if file_result.error:
            status_code = (
                status.HTTP_402_PAYMENT_REQUIRED
                if file_result.error.code == "INSUFFICIENT_CREDITS"
                else status.HTTP_400_BAD_REQUEST
                if file_result.error.code in ["VALIDATION_ERROR", "INVALID_FORMAT"]
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            return JSONResponse(
                status_code=status_code,
                content=file_result.error.model_dump(),
            )

        if user_id:
            await credits_service.insert_transcription_job(
                file_result.job_id,
                user_id,
                "asr",
            )

        if media_endpoint_service.is_level3_enabled() and file_result.file_path:
            background_tasks.add_task(
                media_endpoint_service.process_level3_job,
                file_result.job_id,
                file_result.file_path,
            )
        elif file_result.file_path and file_result.params is not None:
            background_tasks.add_task(
                media_endpoint_service.process_media_upload_background,
                file_result.job_id,
                file_result.file_path,
                file_result.metadata,
                file_result.params,
            )

        return media_endpoint_service.create_job_response(
            file_result.job_id, file_result.job, file_result.video_id
        )

    elif has_url:
        url_result = await media_endpoint_service.handle_remote_url(
            url, translateTo, format, webhookUrl, user_id=user_id, ip_hash=ip_hash
        )

        if url_result.error:
            status_code = (
                status.HTTP_402_PAYMENT_REQUIRED
                if url_result.error.code == "INSUFFICIENT_CREDITS"
                else status.HTTP_400_BAD_REQUEST
                if url_result.error.code in ["VALIDATION_ERROR", "INVALID_FORMAT"]
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            return JSONResponse(
                status_code=status_code,
                content=url_result.error.model_dump(),
            )

        if user_id:
            await credits_service.insert_transcription_job(
                url_result.job_id,
                user_id,
                "asr",
            )

        if media_endpoint_service.is_level3_enabled() and url_result.file_path:
            background_tasks.add_task(
                media_endpoint_service.process_level3_job,
                url_result.job_id,
                url_result.file_path,
            )
        elif url_result.url and url_result.params is not None:
            background_tasks.add_task(
                media_endpoint_service.process_media_url_background,
                url_result.job_id,
                url_result.url,
                url_result.metadata,
                url_result.params,
            )

        return media_endpoint_service.create_job_response(
            url_result.job_id, url_result.job, url_result.video_id
        )

    else:
        error_response = ErrorResponse(
            code="MISSING_INPUT",
            message="Either 'file' (upload) or 'url' (remote URL) must be provided",
            details={},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump(),
        )


@router.post(
    "/transcribe",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Universal Transcription Endpoint",
    description="""
    **Universal endpoint for transcribing any video/audio URL.**
    
    This endpoint automatically detects the URL type and routes to the appropriate handler:
    - **YouTube URLs**: Uses YouTube captions (fastest, no GPU needed)
    - **Social Media URLs** (TikTok, Instagram, Facebook, Twitter/X, Reddit): Downloads and transcribes via ASR
    - **Direct Media URLs**: Streams or downloads and transcribes via ASR
    
    **Request Parameters** (multipart/form-data):
    
    **Required Parameters**:
    - **`url`**: Any supported video/audio URL - YouTube, TikTok, Instagram, Facebook, Twitter/X, Reddit, or direct media URL
    
    **Optional Parameters**:
    - **`translateTo`**: Target language code for translation (ISO 639-1, e.g., "en", "es", "fr", "de")
    - **`format`**: Output format - `json` (default), `text`, `srt`, `vtt`
    - **`webhookUrl`**: Optional webhook callback URL for async notifications
    
    **Perfect for iPhone Shortcuts**: Just send any URL and get back a transcript!
    """,
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute", key_func=get_rate_limit_key_from_request)
async def universal_transcribe(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
    url: str = Form(..., max_length=settings.max_url_length, description="Any video/audio URL (YouTube, TikTok, Instagram, etc.)"),
    translateTo: str = Form(
        None,
        max_length=settings.max_translate_to_length,
        description="Target language code for translation (ISO 639-1)",
    ),
    format: str = Form(
        "json",
        max_length=settings.max_format_length,
        description="Output format: json, text, srt, or vtt",
    ),
    webhookUrl: str = Form(
        None, max_length=settings.max_url_length, description="Optional webhook callback URL"
    ),
) -> Union[TranscriptionResponse, Response, JobResponse]:
    """Universal transcription endpoint - handles any URL type automatically.
    
    This endpoint detects the URL type and routes to the appropriate handler:
    - YouTube: Uses captions fast-path
    - Social media (TikTok, Instagram, etc.): Downloads and transcribes
    - Direct URLs: Streams or downloads and transcribes
    
    Args:
        request: FastAPI request object
        background_tasks: Background task manager
        api_key: Verified API key
        url: Video/audio URL to transcribe
        translateTo: Target language for translation
        format: Output format (json, text, srt, vtt)
        webhookUrl: Optional webhook URL for notifications
        
    Returns:
        TranscriptionResponse for sync results, JobResponse for async jobs, or Response for text formats
    """
    logger.info(f"[UNIVERSAL] Transcription request for URL: {url}")

    user_id = await get_user_id_from_request(request) or None
    ip_hash = hash_ip(get_client_ip(request))

    # Detect URL type
    url_lower = url.lower()

    # Check if it's a YouTube URL
    is_youtube = any(pattern in url_lower for pattern in [
        "youtube.com/watch",
        "youtu.be/",
        "youtube.com/shorts/",
        "youtube.com/embed/",
    ])
    
    if is_youtube:
        logger.info(f"[UNIVERSAL] Detected YouTube URL, routing to YouTube handler")
        # Pre-check: YouTube free plan limit (5 per user)
        if user_id:
            can_youtube, err_msg = await credits_service.check_can_youtube(user_id, ip_hash=ip_hash)
            if not can_youtube:
                return JSONResponse(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    content=ErrorResponse(
                        code="INSUFFICIENT_CREDITS",
                        message=err_msg or "YouTube limit reached",
                        details={"url": url},
                    ).model_dump(),
                )
        # Import and use the YouTube transcription service directly
        from app.services.transcription.transcription_service import TranscriptionService
        from app.models.schemas import OutputFormat

        transcription_service = TranscriptionService()
        
        # Convert format string to OutputFormat enum
        format_enum = OutputFormat.JSON
        if format == "text":
            format_enum = OutputFormat.TEXT
        elif format == "srt":
            format_enum = OutputFormat.SRT
        elif format == "vtt":
            format_enum = OutputFormat.VTT
        
        try:
            result = await transcription_service.transcribe(
                video_url=url,
                translate_to=translateTo,
                format=format_enum,
                diarise=False,
            )

            # Record YouTube sync transcription in history (for Usage/History page)
            if user_id:
                job_id = str(uuid.uuid4())
                duration_sec = result.get("duration", 0) or 0
                duration_min = duration_sec / 60.0 if duration_sec else 0.0
                transcript_text = result.get("transcript") or result.get("content") or ""
                await credits_service.insert_transcription_job(
                    job_id,
                    user_id,
                    "youtube_captions",
                    status="completed",
                    source_url=url,
                    transcript=transcript_text,
                )
                # First 5 YouTube: free. After 5: deduct minutes by duration.
                credits = await credits_service.get_user_credits(user_id, ip_hash=ip_hash)
                if credits and credits.free_plan_youtube_used >= FREE_PLAN_YOUTUBE_COUNT:
                    # Past free 5: deduct minutes
                    minutes_charged = duration_min
                    await credits_service.deduct_asr_minutes(user_id, job_id, minutes_charged, ip_hash=ip_hash)
                else:
                    # Still in free bucket: increment youtube used, no charge
                    minutes_charged = 0
                    await credits_service.increment_youtube_used(user_id)
                await credits_service.update_transcription_job(
                    job_id,
                    "completed",
                    duration_minutes=duration_min if duration_min else None,
                    minutes_charged=minutes_charged,
                    source_url=url,
                    transcript=transcript_text,
                )

            # Return based on format
            if format == "text":
                return Response(content=result["content"], media_type="text/plain")
            elif format == "srt":
                return Response(content=result["content"], media_type="text/plain")
            elif format == "vtt":
                return Response(content=result["content"], media_type="text/vtt")
            else:
                return TranscriptionResponse(
                    status="completed",
                    jobId=None,
                    source=result.get("source"),
                    language=result.get("language"),
                    confidence=result.get("confidence"),
                    transcript=result.get("transcript"),
                    segments=result.get("segments"),
                    warnings=result.get("warnings", []),
                )
                
        except Exception as e:
            logger.error(f"[UNIVERSAL] YouTube transcription failed: {e}")
            error_response = ErrorResponse(
                code="TRANSCRIPTION_FAILED",
                message=f"Failed to transcribe YouTube video: {str(e)}",
                details={"url": url, "error": str(e)},
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_response.model_dump(),
            )
    
    # TikTok: try TikTok's own auto-captions first (free, no GPU, near-instant).
    # Only fall through to the media handler (tikwm -> RunPod ASR) when the video
    # has no captions.
    is_tiktok = "tiktok.com" in url_lower
    if is_tiktok:
        logger.info("[UNIVERSAL] Detected TikTok URL, trying captions-first path")
        from fastapi.concurrency import run_in_threadpool
        from app.services.media.tiktok_service import TikTokService

        try:
            tiktok_result = await run_in_threadpool(TikTokService().get_transcript, url)
        except Exception as e:
            logger.warning(f"[UNIVERSAL] TikTok caption path error: {e}")
            tiktok_result = None

        if tiktok_result:
            logger.info("[UNIVERSAL] TikTok captions found; returning transcript")
            duration_min = (tiktok_result.get("duration") or 0) / 60.0
            # Bill TikTok on the same model it used before (ASR minutes by duration):
            # it counts toward the free 10-minute allowance, then requires credits.
            # Duration comes from the caption/video metadata, so no GPU is needed.
            if user_id:
                can_start, err_msg = await credits_service.check_can_start_asr_job(
                    user_id, duration_min if duration_min > 0 else None, ip_hash=ip_hash
                )
                if not can_start:
                    return JSONResponse(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        content=ErrorResponse(
                            code="INSUFFICIENT_CREDITS",
                            message=err_msg or "Insufficient credits",
                            details={"url": url},
                        ).model_dump(),
                    )
                job_id = str(uuid.uuid4())
                transcript_text = tiktok_result.get("transcript") or ""
                await credits_service.insert_transcription_job(
                    job_id,
                    user_id,
                    "tiktok_captions",
                    status="completed",
                    source_url=url,
                    transcript=transcript_text,
                )
                if duration_min > 0:
                    await credits_service.deduct_asr_minutes(
                        user_id, job_id, round(duration_min, 2), ip_hash=ip_hash
                    )
                await credits_service.update_transcription_job(
                    job_id,
                    "completed",
                    duration_minutes=round(duration_min, 2) if duration_min else None,
                    minutes_charged=round(duration_min, 2) if duration_min else 0,
                    source_url=url,
                    transcript=transcript_text,
                )

            if format == "text":
                return Response(
                    content=tiktok_result.get("content") or tiktok_result.get("transcript", ""),
                    media_type="text/plain",
                )
            elif format == "vtt":
                return Response(content=tiktok_result.get("content") or "", media_type="text/vtt")
            elif format == "srt":
                return Response(
                    content=tiktok_result.get("content") or tiktok_result.get("transcript", ""),
                    media_type="text/plain",
                )
            else:
                return TranscriptionResponse(
                    status="completed",
                    jobId=None,
                    source=tiktok_result.get("source"),
                    language=tiktok_result.get("language"),
                    confidence=tiktok_result.get("confidence"),
                    transcript=tiktok_result.get("transcript"),
                    segments=tiktok_result.get("segments"),
                    warnings=[],
                )
        else:
            logger.info("[UNIVERSAL] No TikTok captions; falling back to tikwm -> ASR")

    # For all other URLs (social media, direct URLs), use the media endpoint
    logger.info(f"[UNIVERSAL] Routing to media handler for URL: {url}")

    url_result = await media_endpoint_service.handle_remote_url(
        url=url,
        translate_to=translateTo,
        format=format,
        webhook_url=webhookUrl,
        user_id=user_id,
        ip_hash=ip_hash,
    )
    
    if url_result.error:
        status_code = status.HTTP_400_BAD_REQUEST
        if url_result.error.code == "INSUFFICIENT_CREDITS":
            status_code = status.HTTP_402_PAYMENT_REQUIRED
        elif url_result.error.code in ["STORAGE_ERROR", "DOWNLOAD_ERROR"]:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return JSONResponse(
            status_code=status_code,
            content=url_result.error.model_dump(),
        )
    
    if user_id:
        await credits_service.insert_transcription_job(
            url_result.job_id,
            user_id,
            "asr",
        )

    # Add background task for processing (same logic as transcribe_media endpoint)
    if media_endpoint_service.is_level3_enabled() and url_result.file_path:
        background_tasks.add_task(
            media_endpoint_service.process_level3_job,
            url_result.job_id,
            url_result.file_path,
        )
    elif url_result.url and url_result.params is not None:
        background_tasks.add_task(
            media_endpoint_service.process_media_url_background,
            url_result.job_id,
            url_result.url,
            url_result.metadata,
            url_result.params,
        )

    # Return job response - for async jobs, user polls /v1/jobs/{job_id}
    return media_endpoint_service.create_job_response(
        url_result.job_id, url_result.job, url_result.video_id
    )
