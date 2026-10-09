"""Service for probing media duration via ffprobe (remote URLs and local files)."""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


class MediaProbeService:
    """
    Service for extracting media duration using ffprobe.

    Supports:
    - Remote HTTP/HTTPS URLs (ffprobe fetches metadata only, minimal bandwidth)
    - Local file paths

    Used for credit pre-check: we must know duration before starting ASR jobs
    to reject requests that would exceed the user's remaining credits.

    Edge cases:
    - MP4 moov-at-end: ffprobe uses range requests where supported
    - HLS/m3u8: May return None (use Option C fallback: require min balance)
    - Redirects: ffprobe follows HTTP redirects
    """

    def __init__(self) -> None:
        """Initialize the media probe service."""
        self._ffprobe_path: Optional[str] = shutil.which("ffprobe")

    def _ensure_ffprobe(self) -> None:
        """Raise if ffprobe is not available."""
        if not self._ffprobe_path:
            raise RuntimeError(
                "ffprobe not found. Install ffmpeg (includes ffprobe) to probe media duration."
            )

    async def get_remote_duration(self, url: str) -> Optional[float]:
        """
        Get duration of remote media via ffprobe (HTTP/HTTPS URL).

        ffprobe supports HTTP URLs natively and fetches only metadata (a few KB).
        No full download required.

        Args:
            url: Remote media URL (e.g. https://cdn.example.com/podcast.mp3)

        Returns:
            Duration in seconds, or None if duration cannot be determined
            (e.g. HLS/m3u8, unsupported format, or probe failure)

        Example:
            >>> service = MediaProbeService()
            >>> duration = await service.get_remote_duration("https://example.com/audio.mp3")
            >>> duration  # e.g. 185.5
        """
        self._ensure_ffprobe()
        return await self._run_ffprobe_duration(url)

    async def get_local_duration(self, path: Union[Path, str]) -> Optional[float]:
        """
        Get duration of local media file via ffprobe.

        Args:
            path: Path to local media file

        Returns:
            Duration in seconds, or None if duration cannot be determined

        Example:
            >>> service = MediaProbeService()
            >>> duration = await service.get_local_duration(Path("/tmp/audio.mp3"))
        """
        self._ensure_ffprobe()
        path_str = str(Path(path).resolve())
        if not Path(path).exists():
            logger.warning(f"[MEDIA_PROBE] Local file not found: {path_str}")
            return None
        return await self._run_ffprobe_duration(path_str)

    async def _run_ffprobe_duration(self, input_spec: str) -> Optional[float]:
        """
        Run ffprobe to extract format duration.

        Args:
            input_spec: URL or local file path

        Returns:
            Duration in seconds, or None on failure
        """
        cmd = [
            self._ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            "-i",
            input_spec,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err = (stderr or b"").decode(errors="replace").strip()
                logger.warning(
                    f"[MEDIA_PROBE] ffprobe failed for {input_spec[:80]!r}: {err}"
                )
                return None

            out = (stdout or b"").decode(errors="replace").strip()
            if not out:
                return None

            duration = float(out)
            if duration <= 0:
                return None

            return round(duration, 2)

        except asyncio.TimeoutError:
            logger.warning(f"[MEDIA_PROBE] ffprobe timeout for {input_spec[:80]!r}")
            return None
        except (ValueError, OSError) as e:
            logger.warning(f"[MEDIA_PROBE] ffprobe error for {input_spec[:80]!r}: {e}")
            return None
