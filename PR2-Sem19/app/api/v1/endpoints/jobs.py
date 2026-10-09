"""Job status endpoint for async transcription."""

import json
import logging
from typing import Union

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.models.schemas import JobsListResponse, JobSummary
from app.services.jobs.job_manager import JobManager
from app.utils.serialization import convert_to_camel_case

logger = logging.getLogger(__name__)

router = APIRouter()


def get_job_manager() -> JobManager:
    """Get job manager instance.

    Creates a new JobManager instance. Since JobManager uses class-level storage
    (_jobs) and Redis (if enabled), all instances share the same job data.
    This allows creating a new instance per request while maintaining data consistency.

    Returns:
        JobManager: Job manager instance that shares class-level storage with other instances.

    Note:
        This function is used as a dependency injection helper. In a production
        application, you might want to use a singleton pattern or dependency injection
        framework for better resource management.
    """
    return JobManager()


@router.get(
    "",
    response_model=JobsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List All Jobs",
    description="""
    Get list of all existing jobs with their statuses.

    Returns a list of all transcription jobs that have been created,
    along with their current statuses. This endpoint is useful for
    monitoring all jobs in the system.

    **Response Fields**:
    - `jobs`: List of job summaries, each containing:
      - `job_id`: Unique job identifier
      - `status`: Current status (queued, processing, completed, failed)
    - `total`: Total number of jobs

    **Usage**:
    Use this endpoint to get an overview of all jobs in the system.
    For detailed information about a specific job, use the GET /jobs/{job_id} endpoint.
    """,
)
async def list_jobs() -> JobsListResponse:
    """List all existing jobs with their statuses.

    Retrieves a list of all transcription jobs that have been created,
    showing only their IDs and current statuses.

    Returns:
        JobsListResponse: List of all jobs with their IDs and statuses.

    Example:
        >>> GET /v1/jobs
        {
            "jobs": [
                {
                    "jobId": "123e4567-e89b-12d3-a456-426614174000",
                    "status": "completed"
                },
                {
                    "jobId": "223e4567-e89b-12d3-a456-426614174001",
                    "status": "processing"
                }
            ],
            "total": 2
        }
    """
    job_manager = get_job_manager()
    all_jobs = job_manager.get_all_jobs()

    job_summaries = [
        JobSummary(job_id=job_id, status=job["status"]) for job_id, job in all_jobs.items()
    ]

    logger.info(f"List jobs requested: {len(job_summaries)} jobs found")
    return JobsListResponse(jobs=job_summaries, total=len(job_summaries))


@router.get(
    "/{job_id}",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Get Job Status",
    description="""
    Poll async transcription job status.

    Returns the current status of an async transcription job.
    Jobs progress through states: queued -> processing -> completed/failed

    **Response Fields**:
    - `job_id`: Unique job identifier
    - `status`: Current status (queued, processing, completed, failed)
    - `created_at`: Job creation timestamp
    - `completed_at`: Job completion timestamp (None if not completed)
    - `result`: Transcription result if completed (None otherwise)
    - `error`: Error message if failed (None otherwise)
    - `video_id`: YouTube video ID

    **Query Parameters**:
    - `stream` (bool): If True and result is large (>1MB), streams the response instead of loading into memory

    **Usage**:
    Poll this endpoint periodically (e.g., every 2-5 seconds) until status is "completed" or "failed".
    """,
)
async def get_job_status(
    job_id: str, stream: bool = Query(default=False, description="Stream large results")
) -> Union[Response, StreamingResponse]:
    """Get status of async transcription job.

    Retrieves the current status and result (if completed) of an async transcription job.
    This endpoint should be polled by clients to check job progress.

    Returns immediately with current status (queued, processing, completed, or failed).
    Only loads the full result if the job is completed.

    Args:
        job_id: Unique job identifier (UUID format).
        stream: If True and result is large (>1MB), streams the response instead of
            loading into memory.

    Returns:
        Union[Response, StreamingResponse]: Job status and result (if completed).
            Returns StreamingResponse for large results when stream=True, otherwise
            returns Response with JSON content.

    Raises:
        HTTPException: 404 if job not found.

    Example:
        >>> GET /v1/jobs/123e4567-e89b-12d3-a456-426614174000
        {
            "job_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "completed",
            "created_at": 1704067200.0,
            "completed_at": 1704067300.0,
            "result": {"transcript": "Hello world", ...},
            "error": null,
            "video_id": "dQw4w9WgXcQ"
        }
    """
    job_manager = get_job_manager()
    job = job_manager.get_job(job_id, include_result=False)

    if not job:
        logger.warning(f"Job status requested for non-existent job: {job_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    response_data = {
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "completed_at": job.get("completed_at"),
        "error": job.get("error"),
        "video_id": job["video_id"],
        "video_url": job.get("video_url"),
    }

    if job.get("status") == "completed":
        completed_job = job_manager.get_job(job_id, include_result=True)
        if completed_job and "result" in completed_job:
            result = completed_job["result"]
            try:
                result_size = len(json.dumps(result, default=str).encode("utf-8"))
                large_result_threshold = 1024 * 1024

                if result_size > large_result_threshold and stream:
                    logger.info(
                        f"Streaming large result for job {job_id}: {result_size / (1024*1024):.2f}MB"
                    )

                    def generate_stream():
                        """Generate JSON response chunks for streaming.

                        Yields:
                            str: JSON string chunks of the response data.
                        """
                        response_data_with_result = {**response_data, "result": result}
                        camel_case_data = convert_to_camel_case(response_data_with_result)
                        json_str = json.dumps(camel_case_data, default=str, ensure_ascii=False)
                        chunk_size = settings.download_chunk_size
                        for i in range(0, len(json_str), chunk_size):
                            yield json_str[i : i + chunk_size]

                    return StreamingResponse(
                        generate_stream(),
                        media_type="application/json",
                        headers={
                            "Content-Disposition": f'attachment; filename="job_{job_id}_result.json"',
                        },
                    )
            except Exception as e:
                logger.warning(
                    f"Error checking result size for streaming: {e}. Returning normal response."
                )

            response_data["result"] = result

    logger.info(f"Job status requested for job {job_id}: {job['status']}")
    camel_case_data = convert_to_camel_case(response_data)
    return Response(
        content=json.dumps(camel_case_data, default=str),
        media_type="application/json",
    )
