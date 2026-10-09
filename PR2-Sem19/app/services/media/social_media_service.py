"""Service for extracting media from social media platforms.

This service handles extraction of media from social media platforms
using yt-dlp. It supports Twitter/X, Instagram, TikTok, Facebook, and Reddit.

The service downloads the media content locally (since many social platforms
return temporary m3u8/HLS streams that can't be passed directly to Runpod),
allowing the file to be uploaded to S3 and then processed.

Attributes:
    None (stateless service)

Example:
    >>> service = SocialMediaService()
    >>> file_path = await service.download_media("https://twitter.com/user/status/123...")
    >>> print(file_path)
    Path("/tmp/social_media_abc123.mp4")
"""

import logging
import re
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from app.core.exceptions import TranscriptionError
from app.core.config import settings
from app.utils.webshare_proxy import get_webshare_proxy_url

logger = logging.getLogger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Try to import yt-dlp
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    logger.warning("yt-dlp not available. Social media extraction will not work.")


class SocialMediaService:
    """Service for extracting media from social media platforms.
    
    Uses yt-dlp to download media from social media posts.
    Supports Twitter/X, Instagram, TikTok, Facebook, and Reddit.
    
    The extraction process:
    1. Validate URL is from a supported platform
    2. Use yt-dlp to download the media to a temp file
    3. Return the local file path for S3 upload and processing
    
    Note:
        This service requires yt-dlp to be installed.
        Install with: pip install yt-dlp
    """
    
    # Platform URL patterns
    PLATFORM_PATTERNS = {
        "twitter": [
            r"https?://(?:www\.)?twitter\.com/[^/]+/status/\d+",
            r"https?://(?:www\.)?x\.com/[^/]+/status/\d+",
            r"https?://t\.co/\w+",
        ],
        "instagram": [
            r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/[^/]+",
            r"https?://(?:www\.)?instagr\.am/(?:p|reel|reels|tv)/[^/]+",
        ],
        "tiktok": [
            r"https?://(?:www\.)?tiktok\.com/@[^/]+/video/\d+",
            r"https?://(?:www\.)?tiktok\.com/t/\w+",
            r"https?://(?:vm|vt)\.tiktok\.com/\w+",
        ],
        "facebook": [
            r"https?://(?:www\.)?facebook\.com/[^/]+/(?:videos|posts)/\d+",
            r"https?://(?:www\.)?facebook\.com/watch/?\?v=\d+",
            r"https?://fb\.watch/\w+",
        ],
        "reddit": [
            r"https?://(?:www\.)?reddit\.com/r/[^/]+/comments/[^/]+",
            r"https?://redd\.it/\w+",
        ],
    }
    
    def __init__(self) -> None:
        """Initialize the social media service.
        
        Checks if yt-dlp is available and logs a warning if not.
        """
        if not YT_DLP_AVAILABLE:
            logger.warning(
                "yt-dlp is not installed. Social media extraction will fail. "
                "Install with: pip install yt-dlp"
            )
    
    def is_social_media_url(self, url: str) -> bool:
        """Check if URL is from a supported social media platform.
        
        Args:
            url: The URL to check
            
        Returns:
            bool: True if URL is from a supported platform, False otherwise
            
        Example:
            >>> service = SocialMediaService()
            >>> service.is_social_media_url("https://twitter.com/user/status/123...")
            True
            >>> service.is_social_media_url("https://example.com/video.mp4")
            False
        """
        for platform_patterns in self.PLATFORM_PATTERNS.values():
            for pattern in platform_patterns:
                if re.match(pattern, url, re.IGNORECASE):
                    return True
        return False
    
    def get_platform(self, url: str) -> Optional[str]:
        """Identify which platform a URL belongs to.
        
        Args:
            url: The URL to identify
            
        Returns:
            Optional[str]: Platform name (twitter, instagram, tiktok, etc.) or None
            
        Example:
            >>> service = SocialMediaService()
            >>> service.get_platform("https://twitter.com/user/status/123...")
            "twitter"
        """
        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, url, re.IGNORECASE):
                    return platform
        return None
    
    async def download_media(self, url: str, download_dir: Optional[str] = None) -> Tuple[Path, dict]:
        """Download media from social media post to a local file.
        
        Uses yt-dlp to download the media content. This is necessary because
        many social platforms (especially Twitter/X) return temporary m3u8/HLS
        stream URLs that cannot be passed directly to Runpod workers.
        
        Args:
            url: Social media post URL (Twitter, Instagram, TikTok, etc.)
            download_dir: Directory to download to (defaults to temp_downloads_dir from settings)
            
        Returns:
            Tuple[Path, dict]: Path to downloaded file and media info dict
            
        Raises:
            TranscriptionError: If yt-dlp is not available, URL is invalid,
                or no media found in the post
                
        Example:
            >>> service = SocialMediaService()
            >>> file_path, info = await service.download_media(
            ...     "https://twitter.com/user/status/123456"
            ... )
            >>> print(file_path)
            Path("/tmp/social_media_abc123.mp4")
        """
        if not YT_DLP_AVAILABLE:
            raise TranscriptionError(
                "yt-dlp is not installed. Cannot extract social media URLs.",
                code="DEPENDENCY_ERROR",
                details={"url": url, "package": "yt-dlp"}
            )
        
        if not self.is_social_media_url(url):
            raise TranscriptionError(
                f"URL is not from a supported social media platform: {url}",
                code="UNSUPPORTED_PLATFORM",
                details={"url": url, "supported_platforms": list(self.PLATFORM_PATTERNS.keys())}
            )
        
        platform = self.get_platform(url)
        logger.info(f"[SOCIAL_MEDIA] Downloading media from {platform}: {url}")
        
        # Use provided download dir or default from settings
        if download_dir is None:
            download_dir = settings.temp_downloads_dir
        
        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # Generate a unique filename
            import uuid
            file_id = str(uuid.uuid4())[:8]

            # TikTok: yt-dlp's TikTok extractor is frequently broken by TikTok's
            # anti-bot changes, so resolve a direct MP4 via the free tikwm API and
            # download that instead. (Captions-first is handled upstream in the
            # universal endpoint; this is the ASR fallback for caption-less videos.)
            if platform == "tiktok":
                return await self._download_tiktok(url, download_path, file_id)

            output_template = str(download_path / f"social_media_{file_id}_%(title).50s.%(ext)s")

            # Route yt-dlp through the WebShare residential proxy so requests are not
            # blocked as coming from Render's datacenter IP (this is the Instagram fix).
            proxy_url = get_webshare_proxy_url()

            # yt-dlp options - download best audio or video
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "format": "bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best",
                "outtmpl": output_template,
                "noplaylist": True,  # Only download single video, not playlists
            }
            if proxy_url:
                ydl_opts["proxy"] = proxy_url
                logger.info(f"[SOCIAL_MEDIA] Using residential proxy for {platform} extraction")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # First, extract info to get metadata
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise TranscriptionError(
                        f"Could not extract media info from URL: {url}",
                        code="EXTRACTION_FAILED",
                        details={"url": url, "platform": platform}
                    )
                
                # Now download the file
                ydl.download([url])
                
                # Find the downloaded file
                # The filename is based on the template, but extension comes from actual download
                expected_filename = ydl.prepare_filename(info)
                downloaded_file = Path(expected_filename)
                
                # If the expected file doesn't exist, try to find it with different extensions
                if not downloaded_file.exists():
                    # Try common extensions
                    for ext in [".mp4", ".m4a", ".webm", ".mp3", ".mkv"]:
                        candidate = downloaded_file.with_suffix(ext)
                        if candidate.exists():
                            downloaded_file = candidate
                            break
                
                if not downloaded_file.exists():
                    # List directory contents to debug
                    files = list(download_path.glob("*"))
                    logger.error(f"[SOCIAL_MEDIA] Downloaded file not found. Directory contents: {files}")
                    raise TranscriptionError(
                        f"Download completed but file not found for: {url}",
                        code="DOWNLOAD_ERROR",
                        details={"url": url, "platform": platform, "expected_file": str(downloaded_file)}
                    )
                
                logger.info(
                    f"[SOCIAL_MEDIA] Successfully downloaded media from {platform}: "
                    f"file={downloaded_file.name}, "
                    f"title='{info.get('title', 'N/A')}', "
                    f"duration={info.get('duration', 'N/A')}s"
                )
                
                # Build media info dict
                media_info = {
                    "title": info.get("title"),
                    "description": info.get("description"),
                    "duration": info.get("duration"),
                    "uploader": info.get("uploader"),
                    "platform": platform,
                    "original_url": url,
                    "file_size": downloaded_file.stat().st_size,
                }
                
                return downloaded_file, media_info
                
        except TranscriptionError:
            raise
        except Exception as e:
            logger.error(f"[SOCIAL_MEDIA] Failed to download media from {url}: {e}", exc_info=True)
            raise TranscriptionError(
                f"Failed to download media from social media post: {str(e)}",
                code="DOWNLOAD_ERROR",
                details={"url": url, "platform": platform, "error": str(e)}
            )
    
    async def _download_tiktok(self, url: str, download_path: Path, file_id: str) -> Tuple[Path, dict]:
        """Download a TikTok video via the free tikwm API (yt-dlp fallback).

        yt-dlp's TikTok extractor is currently broken by TikTok's anti-bot, so we
        resolve a direct, watermark-free MP4 URL through tikwm and download it.
        The downloaded file then flows through the normal S3 -> RunPod ASR path.
        """
        import httpx
        from app.services.media.tiktok_service import TikTokService

        media_url = TikTokService().resolve_media_url(url)
        if not media_url:
            raise TranscriptionError(
                f"Could not resolve TikTok media for URL: {url}",
                code="EXTRACTION_FAILED",
                details={"url": url, "platform": "tiktok"},
            )

        out_file = download_path / f"social_media_{file_id}_tiktok.mp4"
        try:
            with httpx.Client(timeout=120.0, follow_redirects=True,
                              headers={"User-Agent": _BROWSER_UA}) as client:
                with client.stream("GET", media_url) as resp:
                    resp.raise_for_status()
                    with open(out_file, "wb") as fh:
                        for chunk in resp.iter_bytes(chunk_size=65536):
                            fh.write(chunk)
        except Exception as e:
            raise TranscriptionError(
                f"Failed to download TikTok media: {str(e)}",
                code="DOWNLOAD_ERROR",
                details={"url": url, "platform": "tiktok", "error": str(e)},
            )

        if not out_file.exists() or out_file.stat().st_size == 0:
            raise TranscriptionError(
                f"TikTok download produced an empty file for URL: {url}",
                code="DOWNLOAD_ERROR",
                details={"url": url, "platform": "tiktok"},
            )

        logger.info(
            f"[SOCIAL_MEDIA] Downloaded TikTok media via tikwm: "
            f"file={out_file.name}, size={out_file.stat().st_size} bytes"
        )
        media_info = {
            "title": None,
            "description": None,
            "duration": None,
            "uploader": None,
            "platform": "tiktok",
            "original_url": url,
            "file_size": out_file.stat().st_size,
        }
        return out_file, media_info

    async def get_media_info(self, url: str) -> dict:
        """Get media information from social media post without downloading.
        
        Useful for validation and getting metadata (title, duration, etc.)
        before processing.
        
        Args:
            url: Social media post URL
            
        Returns:
            dict: Media information including title, duration, uploader, etc.
            
        Raises:
            TranscriptionError: If extraction fails
        """
        if not YT_DLP_AVAILABLE:
            raise TranscriptionError(
                "yt-dlp is not installed.",
                code="DEPENDENCY_ERROR",
                details={"package": "yt-dlp"}
            )
        
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "no_download": True,
            }
            proxy_url = get_webshare_proxy_url()
            if proxy_url:
                ydl_opts["proxy"] = proxy_url

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    "title": info.get("title"),
                    "description": info.get("description"),
                    "duration": info.get("duration"),
                    "uploader": info.get("uploader"),
                    "platform": self.get_platform(url),
                    "url": url,
                }
                
        except Exception as e:
            logger.error(f"[SOCIAL_MEDIA] Failed to get media info: {e}")
            raise TranscriptionError(
                f"Failed to get media info: {str(e)}",
                code="EXTRACTION_ERROR",
                details={"url": url, "error": str(e)}
            )
