"""GPU worker script for Runpod pods to process transcription jobs."""

import asyncio
import logging
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.models.schemas import JobStatus, OutputFormat
from app.services.infrastructure.cost_control_service import CostControlService
from app.services.infrastructure.webhook_service import WebhookService
from app.services.jobs.job_manager import JobManager
from app.services.jobs.queue_service import QueueService
from app.services.media.s3_storage_service import S3StorageService
from app.services.transcription.transcription_service import \
    TranscriptionService
from app.services.transcription.whisper_service import WhisperService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GPUWorker:
    """
    GPU worker for processing transcription jobs from the queue.

    Polls the queue for jobs, downloads media from S3, transcribes using GPU,
    uploads results to S3, and updates job status.
    """

    def __init__(self) -> None:
        """Initialize the GPU worker."""
        self.worker_id = os.getenv("WORKER_ID", f"worker-{uuid.uuid4().hex[:8]}")
        self.runpod_pod_id = os.getenv("RUNPOD_POD_ID", "unknown")
        self.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        self.heartbeat_interval = settings.worker_heartbeat_interval_seconds
        self.running = True

        # Initialize services
        self.queue_service = QueueService()
        self.s3_storage = S3StorageService()
        self.job_manager = JobManager()
        self.transcription_service = TranscriptionService()
        self.whisper_service = WhisperService.get_instance()
        self.cost_control = CostControlService()
        self.webhook_service = WebhookService()

        # HTTP client for API calls
        self.http_client = httpx.AsyncClient(
            base_url=self.api_base_url,
            timeout=30.0,
        )

        logger.info(f"GPU Worker initialized: {self.worker_id} (pod: {self.runpod_pod_id})")

    async def register_with_api(self) -> None:
        """Register this worker with the API."""
        try:
            response = await self.http_client.post(
                "/v1/workers/register",
                params={
                    "worker_id": self.worker_id,
                    "runpod_pod_id": self.runpod_pod_id,
                    "gpu_type": os.getenv("GPU_TYPE", "Unknown"),
                },
            )
            response.raise_for_status()
            logger.info(f"Registered worker {self.worker_id} with API")
        except Exception as e:
            logger.error(f"Failed to register worker with API: {e}")
            # Continue anyway - worker can still process jobs

    async def send_heartbeat(self) -> None:
        """Send heartbeat to API."""
        try:
            model_loaded = self.whisper_service.is_model_loaded()
            response = await self.http_client.post(
                f"/v1/workers/{self.worker_id}/heartbeat",
                params={"model_loaded": model_loaded},
            )
            response.raise_for_status()
            logger.debug(f"Heartbeat sent for worker {self.worker_id}")
        except Exception as e:
            logger.warning(f"Failed to send heartbeat: {e}")

    async def warmup(self) -> None:
        """Warm up the worker by loading the model."""
        logger.info("Warming up worker - loading Whisper model...")
        try:
            self.whisper_service.ensure_model_loaded()
            logger.info("Worker warmup complete - model loaded")
        except Exception as e:
            logger.error(f"Failed to load model during warmup: {e}")
            raise

    async def process_job(self, job_data) -> None:
        """
        Process a transcription job.

        Args:
            job_data: EnhancedJobData object from queue
        """
        job_id = job_data.job_id
        start_time = time.time()

        logger.info(f"Processing job {job_id}")

        try:
            # Update job status to processing
            self.job_manager.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)

            # Download media from S3
            if not job_data.media_storage_path:
                raise TranscriptionError(
                    "No media storage path in job data",
                    code="JOB_ERROR",
                    details={"job_id": job_id},
                )

            logger.info(f"Downloading media from S3: {job_data.media_storage_path}")
            temp_media_path = Path(f"/tmp/{job_id}_media")
            self.s3_storage.download_media(job_data.media_storage_path, temp_media_path)

            # Get job details from job manager
            job = self.job_manager.get_job(job_id)
            if not job:
                raise TranscriptionError(
                    f"Job {job_id} not found in job manager",
                    code="JOB_ERROR",
                    details={"job_id": job_id},
                )

            translate_to = job.get("translate_to")
            format_str = job.get("format", "json")
            output_format = OutputFormat(format_str)

            # Transcribe media
            logger.info(f"Transcribing media for job {job_id}")
            result = await self.transcription_service.transcribe_media(
                file_path=temp_media_path,
                translate_to=translate_to,
                format=output_format,
                diarise=job.get("diarise", False),
            )

            # Extract metadata
            language = result.get("language")
            model = result.get("model", "whisper-base")
            duration = result.get("duration")

            # Complete job (uploads result to S3 if enabled)
            self.job_manager.complete_job(
                job_id=job_id,
                result=result,
                language=language,
                model=model,
                duration=duration,
                source="asr",
            )

            # Track cost
            processing_time = time.time() - start_time
            gpu_hours = processing_time / 3600.0
            self.cost_control.track_job_cost(job_id, gpu_hours)

            # Remove job from processing queue
            self.queue_service.remove_job_from_processing(job_id)

            # Send webhook if configured
            webhook_url = job.get("webhook_url")
            if webhook_url:
                await self.webhook_service.send_webhook(webhook_url, result, job_id)

            logger.info(
                f"Job {job_id} completed successfully "
                f"(processing time: {processing_time:.2f}s, GPU hours: {gpu_hours:.4f})"
            )

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            self.job_manager.fail_job(job_id, f"Processing failed: {str(e)}")

            # Requeue for retry or move to DLQ
            self.queue_service.requeue_failed_job(job_id, str(e))

        finally:
            # Cleanup temporary files
            if temp_media_path.exists():
                try:
                    temp_media_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_media_path}: {e}")

            # Cleanup S3 files if configured
            if self.s3_storage.is_enabled():
                try:
                    # Extract extension from media path
                    extension = Path(job_data.media_storage_path).suffix.lstrip(".")
                    self.s3_storage.cleanup_job_files(job_id, extension)
                except Exception as e:
                    logger.warning(f"Failed to cleanup S3 files for job {job_id}: {e}")

    async def run(self) -> None:
        """Main worker loop."""
        logger.info("Starting GPU worker...")

        # Register with API
        await self.register_with_api()

        # Warmup
        await self.warmup()

        # Send initial heartbeat
        await self.send_heartbeat()

        # Main loop
        last_heartbeat = time.time()
        consecutive_empty_polls = 0

        while self.running:
            try:
                # Send heartbeat periodically
                current_time = time.time()
                if current_time - last_heartbeat >= self.heartbeat_interval:
                    await self.send_heartbeat()
                    last_heartbeat = current_time

                # Check budget before processing
                if not self.cost_control.check_budget():
                    logger.warning("Budget exceeded, pausing job processing")
                    await asyncio.sleep(60)  # Wait 1 minute before checking again
                    continue

                # Dequeue job
                job_data = self.queue_service.dequeue_job(self.worker_id)

                if job_data:
                    consecutive_empty_polls = 0
                    await self.process_job(job_data)
                else:
                    # No jobs available
                    consecutive_empty_polls += 1
                    if consecutive_empty_polls > 10:
                        # Wait longer if no jobs for a while
                        await asyncio.sleep(5)
                    else:
                        await asyncio.sleep(1)

            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.running = False
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retrying

        logger.info("GPU worker shutting down...")
        await self.http_client.aclose()


async def main() -> None:
    """Main entry point for the worker."""
    worker = GPUWorker()
    try:
        await worker.run()
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
