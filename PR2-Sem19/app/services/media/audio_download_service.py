"""Service for downloading audio from YouTube using yt-dlp."""

import logging
import os
from pathlib import Path

import yt_dlp  # type: ignore[import-untyped]

from app.core.config import settings
from app.core.exceptions import InvalidVideoURLError
from app.utils.webshare_proxy import get_webshare_proxy_url

logger = logging.getLogger(__name__)


class AudioDownloadService:
    """
    Service for downloading audio from YouTube videos.

    This service handles downloading audio from YouTube videos using yt-dlp.
    It provides methods to:
    - Get video duration without downloading the full video
    - Download audio in a format suitable for Whisper transcription
    - Clean up temporary audio files after processing

    The service downloads audio in m4a format (best quality) and stores files
    in a temporary directory that can be cleaned up after transcription.

    Attributes:
        temp_dir (Path): Directory where temporary audio files are stored

    Example:
        >>> service = AudioDownloadService()
        >>> duration = service.get_video_duration("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        >>> audio_path = service.download_audio("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ")
        >>> service.cleanup_audio(audio_path)
    """

    def __init__(self) -> None:
        """
        Initialize the audio download service.

        Creates the temporary directory for storing downloaded audio files
        if it doesn't already exist. The directory path is resolved from
        settings.temp_audio_dir configuration.

        Raises:
            OSError: If the temporary directory cannot be created or accessed
        """
        self.temp_dir = Path(settings.temp_audio_dir).resolve()

        # Check if path exists and is a file (not a directory)
        if self.temp_dir.exists() and not self.temp_dir.is_dir():
            from app.core.exceptions import TranscriptionError

            raise TranscriptionError(
                f"Temp audio directory path exists but is not a directory: {self.temp_dir}",
                code="STORAGE_ERROR",
                details={"temp_dir": str(self.temp_dir)},
            )

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[ASR] AudioDownloadService initialized with temp directory: {self.temp_dir}")

    def get_video_duration(self, video_url: str) -> float:
        """
        Get video duration WITHOUT downloading the full video.

        Uses yt-dlp to extract video metadata and return the duration.
        This is a lightweight operation that doesn't download the video content.

        Args:
            video_url (str): YouTube video URL

        Returns:
            float: Video duration in seconds

        Raises:
            InvalidVideoURLError: If video URL is invalid, video not found,
                or duration cannot be determined

        Example:
            >>> service = AudioDownloadService()
            >>> duration = service.get_video_duration("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            >>> duration > 0
            True
        """
        # Use same approach as test.py - quiet mode but allow some output for debugging
        ydl_opts = {
            "quiet": True,  # Suppress most yt-dlp output
            "no_warnings": False,  # Show warnings (helps with debugging restrictions)
            "no_download": True,  # Don't download, just extract info
        }
        proxy_url = get_webshare_proxy_url()
        if proxy_url:
            ydl_opts["proxy"] = proxy_url

        try:
            logger.info(f"[ASR] Getting video duration for URL: {video_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                duration = info.get("duration", 0)

                if duration is None or duration <= 0:
                    logger.error(f"[ASR] Could not determine video duration for URL: {video_url}")
                    raise InvalidVideoURLError(
                        "Could not determine video duration. Video may be unavailable or invalid.",
                        details={"video_url": video_url},
                    )

                logger.info(f"[ASR] Video duration: {duration}s ({duration / 60:.2f} minutes)")
                return float(duration)

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            logger.error(f"[ASR] yt-dlp download error getting video duration: {error_msg}")
            raise InvalidVideoURLError(
                f"Failed to get video info: {error_msg}",
                details={"video_url": video_url, "error": error_msg},
            )
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            logger.error(
                f"[ASR] Unexpected error getting video duration: {error_type} - {error_msg}"
            )
            raise InvalidVideoURLError(
                f"Failed to get video info: {error_msg}",
                details={"video_url": video_url, "error": error_msg, "error_type": error_type},
            )

    def download_audio(self, video_url: str, video_id: str) -> str:
        """
        Download audio from YouTube video.

        Downloads the best quality audio from the video and converts it to WAV format
        optimized for Whisper (16kHz, mono). Uses the same approach as test.py.

        Args:
            video_url (str): YouTube video URL
            video_id (str): YouTube video ID (used for filename)

        Returns:
            str: Absolute path to the downloaded audio file (WAV format, 16kHz, mono)

        Raises:
            InvalidVideoURLError: If download fails, video is unavailable,
                or audio file cannot be created

        Example:
            >>> service = AudioDownloadService()
            >>> audio_path = service.download_audio(
            ...     "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            ...     "dQw4w9WgXcQ"
            ... )
            >>> os.path.exists(audio_path)
            True
        """
        # Ensure temp directory exists before downloading
        # This is a safety check in case directory was deleted after initialization
        try:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            if not self.temp_dir.is_dir():
                raise InvalidVideoURLError(
                    f"Temp directory path exists but is not a directory: {self.temp_dir}",
                    details={"temp_dir": str(self.temp_dir)},
                )
        except PermissionError as e:
            logger.error(f"[ASR] Permission denied creating temp directory: {self.temp_dir}")
            raise InvalidVideoURLError(
                f"Permission denied creating temp directory: {str(e)}",
                details={"temp_dir": str(self.temp_dir), "error": str(e)},
            )
        except OSError as e:
            logger.error(f"[ASR] Failed to create temp directory: {self.temp_dir} - {str(e)}")
            raise InvalidVideoURLError(
                f"Failed to create temp directory: {str(e)}",
                details={"temp_dir": str(self.temp_dir), "error": str(e)},
            )

        audio_format = "wav"
        sample_rate = 16000

        # Use video_id for filename to avoid issues with special characters
        # This ensures filesystem compatibility across different systems
        safe_filename = f"{video_id}.{audio_format}"
        output_template = str(self.temp_dir / safe_filename)

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template.replace(
                f".{audio_format}", ".%(ext)s"
            ),  # yt-dlp will add extension
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                    "preferredquality": "192" if audio_format == "mp3" else "0",
                }
            ],
            "postprocessor_args": [
                "-ar",
                str(sample_rate),  # Set sample rate
                "-ac",
                "1",  # Convert to mono
            ],
            "quiet": False,
            "no_warnings": False,
        }
        proxy_url = get_webshare_proxy_url()
        if proxy_url:
            ydl_opts["proxy"] = proxy_url

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"[ASR] Downloading and extracting audio from: {video_url}")
                ydl.extract_info(video_url, download=True)

            # Use the safe filename we specified
            audio_file = self.temp_dir / safe_filename

            # Ensure we return an absolute path for Docker compatibility
            audio_path = str(audio_file.resolve())

            # Verify the file exists
            if not os.path.exists(audio_path):
                # Try to find the actual file if filename doesn't match
                # yt-dlp might sanitize the filename differently
                logger.warning(
                    f"[ASR] Expected file not found: {audio_path}, searching for actual file..."
                )
                # List files in temp_dir to find the actual downloaded file
                wav_files = list(self.temp_dir.glob(f"*.{audio_format}"))
                if wav_files:
                    # Use the most recently modified file (should be the one we just downloaded)
                    audio_path = str(max(wav_files, key=lambda p: p.stat().st_mtime).resolve())
                    logger.info(f"[ASR] Found actual downloaded file: {audio_path}")
                else:
                    raise InvalidVideoURLError(
                        f"Downloaded audio file not found at expected path: {audio_path}",
                        details={
                            "video_id": video_id,
                            "video_url": video_url,
                            "temp_dir": str(self.temp_dir),
                        },
                    )

            logger.info(f"[ASR] Audio downloaded to: {audio_path}")
            return audio_path

        except Exception as e:
            error_msg = str(e)
            raise InvalidVideoURLError(
                f"Audio download failed: {error_msg}",
                details={"video_id": video_id, "video_url": video_url, "error": error_msg},
            )

    def cleanup_audio(self, audio_path: str) -> None:
        """
        Delete temporary audio file.

        Safely removes the audio file from the filesystem.
        Logs warnings if cleanup fails but doesn't raise exceptions
        (cleanup failures are not critical).

        Args:
            audio_path (str): Path to the audio file to delete

        Returns:
            None: This method does not return a value. Cleanup failures are logged
                but do not raise exceptions.

        Example:
            >>> service = AudioDownloadService()
            >>> audio_path = service.download_audio(url, video_id)
            >>> service.cleanup_audio(audio_path)
            >>> os.path.exists(audio_path)
            False
        """
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"Cleaned up audio file: {audio_path}")
            else:
                logger.debug(f"Audio file does not exist, skipping cleanup: {audio_path}")
        except OSError as e:
            # OSError includes PermissionError, FileNotFoundError, etc.
            logger.warning(
                f"Failed to cleanup audio file {audio_path}: {type(e).__name__} - {str(e)}"
            )
        except Exception as e:
            error_type = type(e).__name__
            logger.warning(
                f"Unexpected error during audio cleanup for {audio_path}: "
                f"{error_type} - {str(e)}"
            )
