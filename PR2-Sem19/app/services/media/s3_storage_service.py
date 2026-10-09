"""S3-compatible storage service for media files and transcription results."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, cast

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.utils.serialization import convert_to_camel_case

logger = logging.getLogger(__name__)

# Lazy import boto3 to avoid dependency if S3 is disabled
try:
    import boto3  # type: ignore[import-untyped]
    from botocore.exceptions import (  # type: ignore[import-untyped]
        BotoCoreError, ClientError)

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None  # type: ignore
    BotoCoreError = Exception  # type: ignore
    ClientError = Exception  # type: ignore


class S3StorageService:
    """
    S3-compatible storage service for media files and transcription results.

    Provides methods to upload, download, and manage files in S3-compatible storage
    (AWS S3, Cloudflare R2, MinIO, etc.). Handles multipart uploads for large files
    and provides automatic cleanup capabilities.

    Attributes:
        _s3_client (Optional[boto3.client]): Boto3 S3 client if enabled
        _bucket_name (str): S3 bucket name
        _media_prefix (str): S3 prefix for media files
        _results_prefix (str): S3 prefix for results
        _enabled (bool): Whether S3 storage is enabled

    Example:
        >>> storage = S3StorageService()
        >>> if storage.is_enabled():
        ...     s3_path = storage.upload_media(file_path, "job-123", "mp3")
        ...     result = storage.download_result("job-123")
    """

    def __init__(self) -> None:
        """
        Initialize the S3 storage service.

        Creates boto3 S3 client if S3 is enabled and configured. Falls back
        gracefully if S3 is disabled or misconfigured.

        Raises:
            TranscriptionError: If S3 is enabled but configuration is invalid
        """
        self._enabled = settings.s3_enabled
        self._bucket_name = settings.s3_bucket_name
        self._media_prefix = settings.s3_media_prefix.rstrip("/") + "/"
        self._results_prefix = settings.s3_results_prefix.rstrip("/") + "/"
        self._s3_client: Optional[Any] = None

        if not self._enabled:
            logger.info("S3 storage is disabled. Using local file system.")
            return

        if not self._bucket_name:
            raise TranscriptionError(
                "S3 bucket name is required when s3_enabled=True",
                code="CONFIG_ERROR",
                details={"setting": "s3_bucket_name"},
            )

        if not settings.s3_access_key_id or not settings.s3_secret_access_key:
            raise TranscriptionError(
                "S3 access key ID and secret access key are required when s3_enabled=True",
                code="CONFIG_ERROR",
                details={"settings": ["s3_access_key_id", "s3_secret_access_key"]},
            )

        if not BOTO3_AVAILABLE:
            raise TranscriptionError(
                "boto3 is required for S3 storage. Install with: pip install boto3",
                code="DEPENDENCY_ERROR",
                details={"package": "boto3"},
            )

        try:
            s3_config = {
                "aws_access_key_id": settings.s3_access_key_id,
                "aws_secret_access_key": settings.s3_secret_access_key,
                "region_name": settings.s3_region,
            }

            if settings.s3_endpoint_url:
                s3_config["endpoint_url"] = settings.s3_endpoint_url

            self._s3_client = boto3.client("s3", **s3_config)

            try:
                self._s3_client.head_bucket(Bucket=self._bucket_name)
                logger.info(
                    f"S3StorageService initialized successfully "
                    f"(bucket: {self._bucket_name}, region: {settings.s3_region})"
                )
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "404":
                    raise TranscriptionError(
                        f"S3 bucket '{self._bucket_name}' does not exist",
                        code="S3_ERROR",
                        details={"bucket": self._bucket_name},
                    )
                else:
                    raise TranscriptionError(
                        f"Failed to access S3 bucket '{self._bucket_name}': {str(e)}",
                        code="S3_ERROR",
                        details={"bucket": self._bucket_name, "error": str(e)},
                    )

        except (BotoCoreError, ClientError, Exception) as e:
            logger.error(f"Failed to initialize S3 storage service: {e}")
            raise TranscriptionError(
                f"Failed to initialize S3 storage: {str(e)}",
                code="S3_ERROR",
                details={"error": str(e)},
            )

    def is_enabled(self) -> bool:
        """
        Check if S3 storage is enabled.

        Returns:
            bool: True if S3 is enabled and configured, False otherwise

        Example:
            >>> storage = S3StorageService()
            >>> if storage.is_enabled():
            ...     # Use S3 operations
        """
        return self._enabled and self._s3_client is not None

    def _build_media_key(self, job_id: str, extension: str) -> str:
        """
        Build S3 key for media file.

        Constructs S3 key in format: {media_prefix}/{date}/{job_id}.{extension}
        Example: "media/2024-01-15/abc123.mp3"

        Args:
            job_id (str): Unique job identifier
            extension (str): File extension (e.g., "mp3", "wav")

        Returns:
            str: S3 key (path) for the media file
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{job_id}.{extension}"
        return f"{self._media_prefix}{date_str}/{filename}"

    def _build_result_key(self, job_id: str) -> str:
        """
        Build S3 key for result file.

        Constructs S3 key in format: results/YYYY-MM-DD/{job_id}.json
        Example: "results/2024-01-15/abc123.json"

        Args:
            job_id (str): Unique job identifier

        Returns:
            str: S3 key (path) for the result file
        """
        from datetime import date

        date_str = date.today().isoformat()
        filename = f"{job_id}.json"
        return f"{self._results_prefix}{date_str}/{filename}"

    def upload_media(
        self, file_path: Path, job_id: str, extension: str, content_type: Optional[str] = None
    ) -> str:
        """
        Upload a media file to S3.

        Uploads a media file to S3 with the path: media/{date}/{job_id}.{extension}
        Uses multipart upload for large files (>100MB by default).

        Args:
            file_path (Path): Local path to the media file
            job_id (str): Unique job identifier
            extension (str): File extension (e.g., "mp3", "wav")
            content_type (Optional[str]): MIME type (auto-detected if None)

        Returns:
            str: S3 URI (s3://bucket/path) of the uploaded file

        Raises:
            TranscriptionError: If upload fails

        Example:
            >>> storage = S3StorageService()
            >>> s3_uri = storage.upload_media(Path("audio.mp3"), "job-123", "mp3")
            >>> print(s3_uri)
            's3://bucket/media/2024-01-15/job-123.mp3'
        """
        if not self.is_enabled():
            raise TranscriptionError(
                "S3 storage is not enabled",
                code="S3_ERROR",
                details={"operation": "upload_media"},
            )

        if not file_path.exists():
            raise TranscriptionError(
                f"File not found: {file_path}",
                code="FILE_NOT_FOUND",
                details={"file_path": str(file_path)},
            )

        try:
            s3_key = self._build_media_key(job_id, extension)

            file_size = file_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)

            if not content_type:
                content_type = self._guess_content_type(extension)

            multipart_threshold_mb = settings.s3_multipart_threshold_mb
            if file_size_mb > multipart_threshold_mb:
                logger.info(
                    f"Uploading large file ({file_size_mb:.2f}MB) using multipart upload: {s3_key}"
                )
                self._upload_multipart(file_path, s3_key, content_type)
            else:
                logger.info(f"Uploading file ({file_size_mb:.2f}MB) to S3: {s3_key}")
                if self._s3_client is None:
                    raise TranscriptionError(
                        "S3 client is not available",
                        code="S3_ERROR",
                        details={"operation": "upload_media"},
                    )
                with open(file_path, "rb") as f:
                    self._s3_client.upload_fileobj(
                        f, self._bucket_name, s3_key, ExtraArgs={"ContentType": content_type}
                    )

            s3_uri = f"s3://{self._bucket_name}/{s3_key}"
            logger.info(f"Successfully uploaded media to S3: {s3_uri}")
            return s3_uri

        except (BotoCoreError, ClientError, OSError) as e:
            logger.error(f"Failed to upload media to S3 for job {job_id}: {e}")
            raise TranscriptionError(
                f"Failed to upload media to S3: {str(e)}",
                code="S3_ERROR",
                details={"job_id": job_id, "file_path": str(file_path), "error": str(e)},
            )

    def _upload_multipart(self, file_path: Path, s3_key: str, content_type: str) -> None:
        """
        Upload a large file using multipart upload.

        Private helper method for multipart uploads. Splits the file into
        chunks and uploads them in parallel for better performance.

        Args:
            file_path (Path): Local path to the file
            s3_key (str): S3 key (path) for the file
            content_type (str): MIME type

        Raises:
            TranscriptionError: If multipart upload fails
        """
        if self._s3_client is None:
            raise TranscriptionError(
                "S3 client is not available",
                code="S3_ERROR",
                details={"operation": "_upload_multipart"},
            )

        try:
            chunk_size_mb = settings.s3_multipart_chunk_size_mb
            chunk_size = chunk_size_mb * 1024 * 1024

            multipart_response = self._s3_client.create_multipart_upload(
                Bucket=self._bucket_name, Key=s3_key, ContentType=content_type
            )
            upload_id = multipart_response["UploadId"]

            parts = []
            part_number = 1

            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    part_response = self._s3_client.upload_part(
                        Bucket=self._bucket_name,
                        Key=s3_key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=chunk,
                    )
                    parts.append({"ETag": part_response["ETag"], "PartNumber": part_number})
                    part_number += 1

            self._s3_client.complete_multipart_upload(
                Bucket=self._bucket_name,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )

        except (BotoCoreError, ClientError, OSError) as e:
            try:
                if "upload_id" in locals():
                    self._s3_client.abort_multipart_upload(
                        Bucket=self._bucket_name, Key=s3_key, UploadId=upload_id
                    )
            except Exception:
                pass  # Ignore abort errors

            raise TranscriptionError(
                f"Multipart upload failed: {str(e)}",
                code="S3_ERROR",
                details={"s3_key": s3_key, "error": str(e)},
            )

    def download_media(self, s3_uri: str, local_path: Path) -> Path:
        """
        Download a media file from S3 to local path.

        Downloads a media file from S3 and saves it to the specified local path.

        Args:
            s3_uri (str): S3 URI (s3://bucket/path) or S3 key
            local_path (Path): Local path where file should be saved

        Returns:
            Path: Path to the downloaded file

        Raises:
            TranscriptionError: If download fails

        Example:
            >>> storage = S3StorageService()
            >>> local_file = storage.download_media("s3://bucket/media/job-123.mp3", Path("audio.mp3"))
        """
        if not self.is_enabled():
            raise TranscriptionError(
                "S3 storage is not enabled",
                code="S3_ERROR",
                details={"operation": "download_media"},
            )

        try:
            if s3_uri.startswith("s3://"):
                parts = s3_uri[5:].split("/", 1)
                bucket = parts[0]
                s3_key = parts[1] if len(parts) > 1 else ""
            else:
                bucket = self._bucket_name
                s3_key = s3_uri

            local_path.parent.mkdir(parents=True, exist_ok=True)

            if self._s3_client is None:
                raise TranscriptionError(
                    "S3 client is not available",
                    code="S3_ERROR",
                    details={"operation": "download_media"},
                )
            logger.info(f"Downloading media from S3: {s3_uri} -> {local_path}")
            self._s3_client.download_file(bucket, s3_key, str(local_path))

            logger.info(f"Successfully downloaded media from S3: {local_path}")
            return local_path

        except (BotoCoreError, ClientError, OSError) as e:
            logger.error(f"Failed to download media from S3: {e}")
            raise TranscriptionError(
                f"Failed to download media from S3: {str(e)}",
                code="S3_ERROR",
                details={"s3_uri": s3_uri, "local_path": str(local_path), "error": str(e)},
            )

    def upload_result(self, result: Dict[str, Any], job_id: str) -> str:
        """
        Upload transcription result to S3.

        Uploads a transcription result dictionary as JSON to S3 with the path:
        results/YYYY-MM-DD/{job_id}.json

        Args:
            result (Dict[str, Any]): Transcription result dictionary
            job_id (str): Unique job identifier

        Returns:
            str: S3 URI (s3://bucket/path) of the uploaded result

        Raises:
            TranscriptionError: If upload fails

        Example:
            >>> storage = S3StorageService()
            >>> result = {"transcript": "Hello world", "segments": [...]}
            >>> s3_uri = storage.upload_result(result, "job-123")
        """
        if not self.is_enabled():
            raise TranscriptionError(
                "S3 storage is not enabled",
                code="S3_ERROR",
                details={"operation": "upload_result"},
            )

        try:
            s3_key = self._build_result_key(job_id)

            result_camel = convert_to_camel_case(result)
            result_json = json.dumps(result_camel, indent=2, default=str, ensure_ascii=False)

            if self._s3_client is None:
                raise TranscriptionError(
                    "S3 client is not available",
                    code="S3_ERROR",
                    details={"operation": "upload_result"},
                )
            logger.info(f"Uploading result to S3: {s3_key}")
            self._s3_client.put_object(
                Bucket=self._bucket_name,
                Key=s3_key,
                Body=result_json.encode("utf-8"),
                ContentType="application/json",
            )

            s3_uri = f"s3://{self._bucket_name}/{s3_key}"
            logger.info(f"Successfully uploaded result to S3: {s3_uri}")
            return s3_uri

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload result to S3 for job {job_id}: {e}")
            raise TranscriptionError(
                f"Failed to upload result to S3: {str(e)}",
                code="S3_ERROR",
                details={"job_id": job_id, "error": str(e)},
            )

    def download_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Download transcription result from S3.

        Downloads and deserializes a transcription result from S3.

        Args:
            job_id (str): Unique job identifier

        Returns:
            Optional[Dict[str, Any]]: Result dictionary if found, None otherwise

        Raises:
            TranscriptionError: If download fails

        Example:
            >>> storage = S3StorageService()
            >>> result = storage.download_result("job-123")
            >>> if result:
            ...     print(result["transcript"])
        """
        if not self.is_enabled():
            raise TranscriptionError(
                "S3 storage is not enabled",
                code="S3_ERROR",
                details={"operation": "download_result"},
            )

        if self._s3_client is None:
            raise TranscriptionError(
                "S3 storage is not enabled",
                code="S3_ERROR",
                details={"operation": "download_result"},
            )

        try:
            s3_key = self._build_result_key(job_id)
            logger.info(f"Downloading result from S3: {s3_key}")
            try:
                response = self._s3_client.get_object(Bucket=self._bucket_name, Key=s3_key)
                result_json = response["Body"].read().decode("utf-8")
                result = json.loads(result_json)
                logger.info(f"Successfully downloaded result from S3: {s3_key}")
                return cast(Dict[str, Any], result)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NoSuchKey":
                    old_s3_key1 = f"{self._results_prefix}data/{job_id}/{job_id}.json"
                    old_s3_key2 = f"{self._results_prefix}{job_id}.json"
                    for old_key in [old_s3_key1, old_s3_key2]:
                        logger.debug(
                            f"Result not found at new path {s3_key}, trying old path: {old_key}"
                        )
                        try:
                            response = self._s3_client.get_object(
                                Bucket=self._bucket_name, Key=old_key
                            )
                            result_json = response["Body"].read().decode("utf-8")
                            result = json.loads(result_json)
                            logger.info(
                                f"Successfully downloaded result from S3 (old path): {old_key}"
                            )
                            return cast(Dict[str, Any], result)
                        except ClientError as old_e:
                            old_error_code = old_e.response.get("Error", {}).get("Code", "Unknown")
                            if old_error_code == "NoSuchKey":
                                continue
                            raise
                    logger.debug(f"Result not found in S3 for job {job_id} (tried all paths)")
                    return None
                else:
                    raise

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.debug(f"Result not found in S3 for job {job_id}")
                return None
            else:
                logger.error(f"Failed to download result from S3 for job {job_id}: {e}")
                raise TranscriptionError(
                    f"Failed to download result from S3: {str(e)}",
                    code="S3_ERROR",
                    details={"job_id": job_id, "error": str(e)},
                )
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse result JSON from S3 for job {job_id}: {e}")
            raise TranscriptionError(
                f"Failed to parse result JSON: {str(e)}",
                code="S3_ERROR",
                details={"job_id": job_id, "error": str(e)},
            )

    def cleanup_job_files(self, job_id: str, extension: Optional[str] = None) -> None:
        """
        Clean up job files from S3 (media and result).

        Deletes both the media file and result file for a job from S3.
        This is a best-effort operation - failures are logged but don't raise exceptions.

        Args:
            job_id (str): Unique job identifier
            extension (Optional[str]): File extension for media file (auto-detected if None)

        Example:
            >>> storage = S3StorageService()
            >>> storage.cleanup_job_files("job-123", "mp3")
        """
        if not self.is_enabled():
            return

        if self._s3_client is None:
            return

        try:
            if extension:
                media_key = self._build_media_key(job_id, extension)
                try:
                    self._s3_client.delete_object(Bucket=self._bucket_name, Key=media_key)
                    logger.debug(f"Deleted media file from S3: {media_key}")
                except ClientError as e:
                    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                    old_date_key = f"{self._media_prefix}{yesterday}/{job_id}.{extension}"
                    try:
                        self._s3_client.delete_object(Bucket=self._bucket_name, Key=old_date_key)
                        logger.debug(
                            f"Deleted media file from S3 (yesterday's date): {old_date_key}"
                        )
                    except ClientError:
                        old_media_key1 = f"{self._media_prefix}data/{job_id}/{job_id}.{extension}"
                        old_media_key2 = f"{self._media_prefix}{job_id}.{extension}"
                        for old_key in [old_media_key1, old_media_key2]:
                            try:
                                self._s3_client.delete_object(Bucket=self._bucket_name, Key=old_key)
                                logger.debug(f"Deleted media file from S3 (old path): {old_key}")
                                break
                            except ClientError:
                                continue
                        else:
                            logger.warning(f"Failed to delete media file {media_key}: {e}")

            result_key = self._build_result_key(job_id)
            try:
                self._s3_client.delete_object(Bucket=self._bucket_name, Key=result_key)
                logger.debug(f"Deleted result file from S3: {result_key}")
            except ClientError as e:
                old_result_key1 = f"{self._results_prefix}data/{job_id}/{job_id}.json"
                old_result_key2 = f"{self._results_prefix}{job_id}.json"
                for old_key in [old_result_key1, old_result_key2]:
                    try:
                        self._s3_client.delete_object(Bucket=self._bucket_name, Key=old_key)
                        logger.debug(f"Deleted result file from S3 (old path): {old_key}")
                        break
                    except ClientError:
                        continue
                else:
                    logger.warning(f"Failed to delete result file {result_key}: {e}")

            logger.info(f"Cleaned up S3 files for job {job_id}")

        except Exception as e:
            logger.warning(f"Error during S3 cleanup for job {job_id}: {e}")

    def _guess_content_type(self, extension: str) -> str:
        """
        Guess MIME type from file extension.

        Private helper method to determine content type based on file extension.

        Args:
            extension (str): File extension (without dot)

        Returns:
            str: MIME type (default: application/octet-stream)
        """
        content_types = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "m4a": "audio/mp4",
            "flac": "audio/flac",
            "ogg": "audio/ogg",
            "mp4": "video/mp4",
            "mkv": "video/x-matroska",
            "avi": "video/x-msvideo",
            "mov": "video/quicktime",
            "webm": "video/webm",
            "json": "application/json",
        }
        return content_types.get(extension.lower(), "application/octet-stream")

    def upload_file(self, file_obj, key: str, content_type: Optional[str] = None) -> str:
        """
        Upload a file object to S3 at a specific key.

        Args:
            file_obj: File-like object to upload
            key: S3 key (path) for the file
            content_type: MIME type (optional)

        Returns:
            str: S3 URI of the uploaded file

        Raises:
            TranscriptionError: If upload fails
        """
        if not self.is_enabled():
            raise TranscriptionError(
                "S3 storage is not enabled",
                code="S3_ERROR",
                details={"operation": "upload_file"},
            )

        try:
            if self._s3_client is None:
                raise TranscriptionError(
                    "S3 client is not available",
                    code="S3_ERROR",
                    details={"operation": "upload_file"},
                )

            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            self._s3_client.upload_fileobj(file_obj, self._bucket_name, key, ExtraArgs=extra_args)

            s3_uri = f"s3://{self._bucket_name}/{key}"
            logger.info(f"Successfully uploaded file to S3: {s3_uri}")
            return s3_uri

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload file to S3 at key {key}: {e}")
            raise TranscriptionError(
                f"Failed to upload file to S3: {str(e)}",
                code="S3_ERROR",
                details={"key": key, "error": str(e)},
            )

    def delete_file(self, key: str) -> None:
        """
        Delete a file from S3 by key.

        Args:
            key: S3 key (path) of the file to delete

        Raises:
            TranscriptionError: If deletion fails
        """
        if not self.is_enabled():
            raise TranscriptionError(
                "S3 storage is not enabled",
                code="S3_ERROR",
                details={"operation": "delete_file"},
            )

        try:
            if self._s3_client is None:
                raise TranscriptionError(
                    "S3 client is not available",
                    code="S3_ERROR",
                    details={"operation": "delete_file"},
                )

            self._s3_client.delete_object(Bucket=self._bucket_name, Key=key)
            logger.info(f"Successfully deleted file from S3: {key}")

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to delete file from S3 at key {key}: {e}")
            raise TranscriptionError(
                f"Failed to delete file from S3: {str(e)}",
                code="S3_ERROR",
                details={"key": key, "error": str(e)},
            )

    def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for accessing a file in S3.

        Args:
            key: S3 key (path) of the file
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            str: Presigned URL for accessing the file

        Raises:
            TranscriptionError: If URL generation fails
        """
        if not self.is_enabled():
            raise TranscriptionError(
                "S3 storage is not enabled",
                code="S3_ERROR",
                details={"operation": "generate_presigned_url"},
            )

        try:
            if self._s3_client is None:
                raise TranscriptionError(
                    "S3 client is not available",
                    code="S3_ERROR",
                    details={"operation": "generate_presigned_url"},
                )

            url = self._s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket_name, "Key": key},
                ExpiresIn=expiration,
            )

            return url

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to generate presigned URL for key {key}: {e}")
            raise TranscriptionError(
                f"Failed to generate presigned URL: {str(e)}",
                code="S3_ERROR",
                details={"key": key, "error": str(e)},
            )
