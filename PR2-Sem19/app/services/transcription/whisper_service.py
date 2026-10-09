"""Service for ASR transcription using Runpod Serverless API."""

import asyncio
import logging
import time
from typing import List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.models.schemas import TranscriptSegment
from app.services.media.s3_storage_service import S3StorageService

logger = logging.getLogger(__name__)


class WhisperService:
    """
    Whisper ASR transcription service using Runpod Serverless API.

    This service provides automatic speech recognition (ASR) using Runpod's
    external GPU infrastructure. No local model is loaded.

    **Architecture**:
    - Accepts local file paths OR direct URLs
    - For local files: Uploads to S3 temporarily
    - For URLs: Sends directly to Runpod (faster)
    - Submits job to Runpod Serverless API
    - Polls for completion
    - Returns transcription segments

    **Features**:
    - No local GPU required
    - Pay-per-use pricing
    - Direct URL streaming (no S3 upload for URLs)
    - Scales automatically

    Example:
        >>> service = WhisperService()
        >>> segments, language, confidence = service.transcribe(
        ...     audio_path="/path/to/audio.m4a",
        ...     translate_to=None
        ... )
        >>> len(segments) > 0
        True
    """

    _instance: Optional["WhisperService"] = None

    def __init__(self) -> None:
        """Initialize the Whisper service."""
        self._api_key = settings.runpod_api_key
        self._endpoint_id = settings.runpod_endpoint_id
        self._s3_service = S3StorageService()

        if not self._api_key or not self._endpoint_id:
            logger.warning(
                "[ASR] Runpod not configured. "
                "Set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID environment variables."
            )

    @classmethod
    def get_instance(cls) -> "WhisperService":
        """Get singleton instance of WhisperService."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def health_check(self) -> dict:
        """
        Check health of the Whisper service.

        Returns:
            dict: Health status with keys:
                - loaded (bool): Whether Runpod is configured
                - device (str): Always 'runpod' (external GPU)
                - ready (bool): Whether service is ready for requests
                - runpod_configured (bool): Whether Runpod API key and endpoint are set
        """
        runpod_configured = bool(self._api_key and self._endpoint_id)
        return {
            "loaded": runpod_configured,
            "device": "runpod",
            "ready": runpod_configured,
            "runpod_configured": runpod_configured,
            "endpoint_id": self._endpoint_id if runpod_configured else None,
        }

    def _is_url(self, path: str) -> bool:
        """
        Check if the given path is a URL.

        Args:
            path: String to check

        Returns:
            bool: True if URL, False if local path
        """
        return path.startswith(('http://', 'https://'))

    def _upload_to_s3(self, audio_path: str) -> Tuple[str, str]:
        """
        Upload audio file to S3 for Runpod processing.

        Args:
            audio_path: Local path to audio file

        Returns:
            Tuple[str, str]: (S3 presigned URL, S3 key for cleanup)

        Raises:
            TranscriptionError: If upload fails
        """
        try:
            import uuid
            from pathlib import Path

            ext = Path(audio_path).suffix or ".mp3"
            key = f"temp/runpod/{uuid.uuid4()}{ext}"

            with open(audio_path, "rb") as f:
                self._s3_service.upload_file(f, key)

            # Generate presigned URL (valid for 1 hour)
            url = self._s3_service.generate_presigned_url(key, expiration=3600)
            logger.info(f"[ASR] Uploaded audio to S3: {key}")

            return url, key

        except Exception as e:
            logger.error(f"[ASR] Failed to upload audio to S3: {e}")
            raise TranscriptionError(
                message=f"Failed to upload audio for transcription: {str(e)}",
                code="S3_UPLOAD_ERROR"
            )

    def _delete_from_s3(self, key: str) -> None:
        """
        Delete file from S3 immediately after transcription.

        Args:
            key: S3 key to delete
        """
        try:
            self._s3_service.delete_file(key)
            logger.info(f"[ASR] Deleted audio from S3: {key}")
        except Exception as e:
            # Log error but don't fail - transcription already completed
            logger.warning(f"[ASR] Failed to delete audio from S3 {key}: {e}")

    def _download_url_to_temp(self, url: str) -> str:
        """
        Download URL to temporary file.

        Args:
            url: URL to download

        Returns:
            str: Path to temporary file

        Raises:
            TranscriptionError: If download fails
        """
        try:
            import tempfile
            import uuid
            from pathlib import Path

            # Determine extension from URL
            parsed = Path(url)
            ext = parsed.suffix or ".mp3"

            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_path = temp_file.name
            temp_file.close()

            # Download file
            logger.info(f"[ASR] Downloading audio from URL to temp file...")
            with httpx.Client(timeout=300.0) as client:
                with client.stream("GET", url, follow_redirects=True) as response:
                    response.raise_for_status()
                    with open(temp_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)

            logger.info(f"[ASR] Downloaded audio to: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"[ASR] Failed to download audio from URL: {e}")
            raise TranscriptionError(
                message=f"Failed to download audio: {str(e)}",
                code="DOWNLOAD_ERROR"
            )

    def _submit_job(self, audio_url: str, task: str = "transcribe") -> str:
        """
        Submit transcription job to Runpod.

        Args:
            audio_url: URL to audio file (S3 presigned URL)
            task: "transcribe" or "translate"

        Returns:
            str: Runpod job ID

        Raises:
            TranscriptionError: If submission fails
        """
        try:
            url = f"https://api.runpod.ai/v2/{self._endpoint_id}/run"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}"
            }
            # Faster Whisper template payload (from working Next.js implementation)
            payload = {
                "input": {
                    "audio": audio_url,
                    "model": "large-v3",
                    "transcription": "plain_text"
                }
            }

            logger.info(f"[ASR] Submitting job to Runpod: {url}")

            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            job_id = data.get("id")
            if not job_id:
                raise TranscriptionError(
                    message="Runpod did not return a job ID",
                    code="RUNPOD_ERROR"
                )

            logger.info(f"[ASR] Runpod job submitted: {job_id}")
            return job_id

        except httpx.HTTPStatusError as e:
            logger.error(f"[ASR] Runpod HTTP error: {e.response.status_code} - {e.response.text}")
            raise TranscriptionError(
                message=f"Runpod API error: {e.response.status_code}",
                code="RUNPOD_ERROR"
            )
        except Exception as e:
            logger.error(f"[ASR] Failed to submit Runpod job: {e}")
            raise TranscriptionError(
                message=f"Failed to submit transcription job: {str(e)}",
                code="RUNPOD_ERROR"
            )

    def _get_job_status(self, job_id: str) -> dict:
        """
        Check status of a Runpod job.

        Args:
            job_id: Runpod job ID

        Returns:
            dict: Job status and output

        Raises:
            TranscriptionError: If status check fails
        """
        try:
            url = f"https://api.runpod.ai/v2/{self._endpoint_id}/status/{job_id}"
            headers = {
                "Authorization": f"Bearer {self._api_key}"
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"[ASR] Failed to get Runpod job status: {e}")
            raise TranscriptionError(
                message=f"Failed to check transcription status: {str(e)}",
                code="RUNPOD_ERROR"
            )

    def _poll_for_completion(self, job_id: str, max_attempts: int = 180, delay: float = 2.0) -> dict:
        """
        Poll Runpod job until completion.

        Args:
            job_id: Runpod job ID
            max_attempts: Maximum polling attempts (default: 180 = 6 minutes)
            delay: Seconds between polls

        Returns:
            dict: Job output

        Raises:
            TranscriptionError: If job fails or times out
        """
        logger.info(f"[ASR] Polling job {job_id} for completion...")

        for attempt in range(max_attempts):
            status = self._get_job_status(job_id)
            state = status.get("status")

            if state == "COMPLETED":
                logger.info(f"[ASR] Job {job_id} completed")
                return status.get("output", {})

            elif state == "FAILED":
                error = status.get("error", "Unknown error")
                logger.error(f"[ASR] Job {job_id} failed: {error}")
                raise TranscriptionError(
                    message=f"Transcription failed: {error}",
                    code="TRANSCRIPTION_FAILED"
                )

            elif state in ["IN_PROGRESS", "IN_QUEUE"]:
                if attempt % 10 == 0:  # Log every 20 seconds
                    logger.info(f"[ASR] Job {job_id} status: {state} (attempt {attempt + 1})")
                time.sleep(delay)

            else:
                logger.warning(f"[ASR] Unknown job status: {state}")
                time.sleep(delay)

        raise TranscriptionError(
            message=f"Transcription timed out after {max_attempts * delay} seconds",
            code="TRANSCRIPTION_TIMEOUT"
        )

    def _parse_runpod_output(self, output: dict) -> Tuple[List[TranscriptSegment], str, Optional[float]]:
        """
        Parse Runpod output into transcript segments.

        Args:
            output: Raw output from Runpod

        Returns:
            Tuple of (segments, language, confidence)
        """
        logger.info(f"[ASR] Parsing Runpod output: {output}")
        segments = []
        language = output.get("language", "en")
        confidence = output.get("confidence")

        # Handle different output formats from Runpod
        if "segments" in output:
            # Full segment format
            for seg in output["segments"]:
                segments.append(
                    TranscriptSegment(
                        start=seg.get("start", 0.0),
                        end=seg.get("end", 0.0),
                        text=seg.get("text", "").strip()
                    )
                )
        elif "transcript" in output:
            # Plain text format - create single segment
            segments.append(
                TranscriptSegment(
                    start=0.0,
                    end=0.0,
                    text=output["transcript"].strip()
                )
            )
        else:
            # Try to find any text field
            text = str(output).strip()
            segments.append(
                TranscriptSegment(
                    start=0.0,
                    end=0.0,
                    text=text
                )
            )

        return segments, language, confidence

    def transcribe(
        self,
        audio_path: str,
        translate_to: Optional[str] = None,
    ) -> Tuple[List[TranscriptSegment], str, Optional[float]]:
        """
        Transcribe audio using Runpod Serverless API.

        Always uploads to S3 first (even for URLs) since Runpod endpoints
        typically cannot access external URLs directly. Deletes from S3
        immediately after transcription to minimize storage costs.

        Args:
            audio_path: Path to local audio file OR direct URL to audio file
            translate_to: Target language for translation (only "en" supported)

        Returns:
            Tuple of (segments, language, confidence)

        Raises:
            TranscriptionError: If transcription fails
        """
        import os

        if not self._api_key or not self._endpoint_id:
            raise TranscriptionError(
                message="Runpod not configured. Set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID.",
                code="RUNPOD_NOT_CONFIGURED"
            )

        temp_file_path: Optional[str] = None
        s3_key: Optional[str] = None

        try:
            # Step 1: Determine audio URL for Runpod
            if self._is_url(audio_path):
                # For URLs: send directly to Runpod (like working Next.js implementation)
                audio_url = audio_path
                logger.info(f"[ASR] Sending URL directly to Runpod: {audio_url}")
            else:
                # For local files: upload to S3 first
                local_path = audio_path
                logger.info(f"[ASR] Using local file: {local_path}")
                audio_url, s3_key = self._upload_to_s3(local_path)
                logger.info(f"[ASR] Uploaded local file to S3 for Runpod: {audio_url}")

            # Step 3: Submit job to Runpod
            task = "translate" if translate_to == "en" else "transcribe"
            job_id = self._submit_job(audio_url, task)

            # Step 4: Poll for completion
            output = self._poll_for_completion(job_id)

            # Step 5: Parse output
            segments, language, confidence = self._parse_runpod_output(output)

            logger.info(
                f"[ASR] Transcription complete: {len(segments)} segments, "
                f"language={language}, confidence={confidence}"
            )

            return segments, language, confidence

        except TranscriptionError:
            raise
        except Exception as e:
            logger.error(f"[ASR] Transcription failed: {e}")
            raise TranscriptionError(
                message=f"Transcription failed: {str(e)}",
                code="TRANSCRIPTION_ERROR"
            )
        finally:
            # Cleanup: Delete from S3 only for local files (not URLs)
            if s3_key:
                try:
                    self._delete_from_s3(s3_key)
                    logger.info(f"[ASR] Cleaned up S3 file: {s3_key}")
                except Exception as e:
                    logger.warning(f"[ASR] Failed to cleanup S3 file {s3_key}: {e}")

    async def transcribe_async(
        self,
        audio_path: str,
        translate_to: Optional[str] = None,
    ) -> Tuple[List[TranscriptSegment], str, Optional[float]]:
        """
        Async wrapper for transcribe method.

        Args:
            audio_path: Path to local audio file OR direct URL to audio file
            translate_to: Target language for translation

        Returns:
            Tuple of (segments, language, confidence)
        """
        # Run synchronous transcribe in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.transcribe, audio_path, translate_to
        )
