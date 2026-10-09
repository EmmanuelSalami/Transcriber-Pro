"""YouTube transcription endpoint."""

import logging
from typing import Union

from fastapi import (APIRouter, BackgroundTasks, Depends, Form, HTTPException,
                     Request, Response, status)
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address

from app.core.auth import get_rate_limit_key, limiter, verify_api_key
from app.core.config import settings
from app.models.schemas import (ErrorResponse, JobResponse, OutputFormat,
                                TranscriptionResponse)
from app.services.transcription import TranscriptionService
from app.utils.security import sanitize_for_logging

logger = logging.getLogger(__name__)

router = APIRouter()
transcription_service = TranscriptionService()


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
    "/youtube",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Transcribe YouTube Video",
    description="""
    **Request Parameters** (multipart/form-data):

    **Required Parameters**:
    - **`url`**: YouTube video URL - Full YouTube video URL (e.g., `https://www.youtube.com/watch?v=dQw4w9WgXcQ`)

    **Optional Parameters**:
    - **`translateTo`**: Target language code for translation (ISO 639-1, e.g., `en`, `es`, `fr`, `de`). If not provided, transcription will be in the original detected language.
    - **`format`**: Output format - `json` (default, full metadata with segments), `text` (plain text), `srt` (SubRip), `vtt` (WebVTT).
    - **`diarise`**: Enable speaker diarization - `true` to identify different speakers, `false` (default) to disable. Diarization requires ASR processing and may take longer.
    - **`webhookUrl`**: Optional webhook callback URL. When job completes, a POST request with full transcription result will be sent to this URL. Includes retry logic, timeout protection, and SSRF protection.

    **Two-Path Strategy**:
    - **Path A (Fast-path)**: Uses existing YouTube captions (preferred, no GPU needed)
    - **Path B (ASR Fallback)**: Uses Whisper model when captions unavailable or diarization requested

    **Additional Features**:
    - Automatic language detection
    - Optional translation to target language (ISO 639-1 codes)
    - Multiple output formats: JSON, Text, SRT, VTT
    - Speaker diarization support

    **Processing Modes**:
    - Videos < 5 minutes: Synchronous processing (returns result immediately)
    - Videos 5 minutes - 1 hour: Asynchronous processing (returns job ID for polling)
    - Videos > 1 hour: Rejected with VIDEO_TOO_LONG error

    **Rate Limiting**: Each API key has a rate limit per minute.
    """,
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute", key_func=get_rate_limit_key_from_request)
async def transcribe_youtube(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
    url: str = Form(..., max_length=settings.max_url_length, description="YouTube video URL"),
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
    diarise: str = Form(
        "false",
        max_length=settings.max_diarise_length,
        description="Enable speaker diarization (true/false)",
    ),
    webhookUrl: str = Form(
        None, max_length=settings.max_url_length, description="Optional webhook callback URL"
    ),
) -> Union[TranscriptionResponse, Response, JobResponse]:
    """Transcribe YouTube video endpoint.

    Main API endpoint for transcribing YouTube videos using two-path strategy:
    - Path A: Fast-path using existing captions (preferred, no GPU needed)
    - Path B: ASR fallback using Whisper model (when captions unavailable or diarization requested)

    Supports automatic language detection, optional translation, multiple
    output formats (JSON, Text, SRT, VTT), and speaker diarization.

    Path B processing modes:
    - Videos < 5 minutes: Synchronous processing (returns result immediately)
    - Videos 5 minutes - 1 hour: Asynchronous processing (returns job ID for polling)
    - Videos > 1 hour: Rejected with VIDEO_TOO_LONG error

    Args:
        request: FastAPI request object (required for rate limiting).
        background_tasks: FastAPI background tasks for async processing.
        api_key: Verified API key from Bearer token (injected via dependency).
        url: YouTube video URL (required).
        translateTo: Optional target language code for translation (ISO 639-1).
        format: Output format (json, text, srt, vtt, default: json).
        diarise: Enable speaker diarization ("true" or "false", default: "false").
        webhookUrl: Optional webhook callback URL for completion notification.

    Returns:
        Union[TranscriptionResponse, Response, JobResponse]: Transcription response:
            - For JSON format: TranscriptionResponse with full metadata (sync)
            - For text/srt/vtt formats: Response with content string and proper
              content-type header (sync)
            - For async jobs: JobResponse with job_id for polling

    Raises:
        TranscriptionError: For transcription-related errors (handled by global
            error handlers).
        HTTPException: For authentication or rate limiting errors.
        InvalidVideoURLError: If video URL is invalid.
        VideoTooLongError: If video is longer than 1 hour (VIDEO_TOO_LONG error code).

    Example:
        >>> POST /v1/transcriptions/youtube (multipart/form-data)
        >>> url: https://www.youtube.com/watch?v=dQw4w9WgXcQ
        >>> translateTo: en
        >>> format: json
        >>> diarise: false
        >>> webhookUrl: https://example.com/callback
    """
    url_str = str(url)
    video_id = url_str.split("v=")[-1].split("&")[0] if "v=" in url_str else url_str[:50]
    api_key_hash = sanitize_for_logging(api_key)
    logger.info(
        f"Transcription request - Video ID: {video_id}, "
        f"format: {format}, "
        f"translateTo: {translateTo}, "
        f"diarise: {diarise}, "
        f"API key hash: {api_key_hash}"
    )

    translate_to_str = translateTo if translateTo else None
    try:
        output_format = OutputFormat(format.lower()) if format else OutputFormat.JSON
    except ValueError:
        error_response = ErrorResponse(
            code="INVALID_FORMAT",
            message=f"Invalid format: {format}. Supported formats: {[f.value for f in OutputFormat]}",
            details={
                "provided_format": format,
                "supported_formats": [f.value for f in OutputFormat],
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump(),
        )
    diarise_bool = diarise.lower() == "true" if diarise else False
    webhook_url_str = webhookUrl if webhookUrl else None

    result = await transcription_service.transcribe(
        video_url=url_str,
        translate_to=translate_to_str,
        format=output_format,
        diarise=diarise_bool,
        webhook_url=webhook_url_str,
    )

    if result.get("jobId") is not None:
        job_id = result["jobId"]
        logger.info(f"Scheduling async transcription job {job_id} for video {video_id}")

        from app.models.schemas import JobStatus

        transcription_service.job_manager.update_job_status(
            job_id, JobStatus.PROCESSING, progress=0.0
        )

        process_func = transcription_service.job_manager.schedule_async_transcription(
            job_id=job_id,
            audio_service=transcription_service.audio_service,
            whisper_service=transcription_service.whisper_service,
        )

        background_tasks.add_task(process_func)

        job_data = transcription_service.job_manager.get_job(job_id, include_result=False)
        video_url = job_data.get("video_url") if job_data else None
        updated_status = (
            job_data.get("status", "queued") if job_data else result.get("status", "queued")
        )

        job_response_data = {
            "job_id": job_id,
            "status": updated_status,
            "created_at": result.get("created_at") or result.get("createdAt"),
            "video_id": video_id,
            "video_url": video_url,
        }
        return JobResponse(**job_response_data)

    if output_format == OutputFormat.JSON:
        return TranscriptionResponse(**result)
    else:
        content = result.get("content", "")

        if output_format == OutputFormat.TEXT:
            media_type = "text/plain"
            file_extension = "txt"
        elif output_format == OutputFormat.SRT:
            media_type = "text/srt"
            file_extension = "srt"
        elif output_format == OutputFormat.VTT:
            media_type = "text/vtt"
            file_extension = "vtt"
        else:
            media_type = "text/plain"
            file_extension = "txt"

        filename = f"transcription.{file_extension}"

        return Response(
            content=content,
            media_type=media_type,
            status_code=status.HTTP_200_OK,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
