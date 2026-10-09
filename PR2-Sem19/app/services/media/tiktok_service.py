"""TikTok extraction service.

TikTok's own yt-dlp extractor is frequently broken by TikTok's anti-bot changes,
and TikTok blocks datacenter IPs (like Render). This service works around both:

1. **Captions-first (free, no GPU):** fetch the TikTok watch page through the
   WebShare residential proxy, read the embedded
   ``__UNIVERSAL_DATA_FOR_REHYDRATION__`` JSON, and pull TikTok's own
   auto-generated captions (webVTT). This mirrors the YouTube-captions fast path
   and never touches RunPod.

2. **Media fallback (RunPod):** when a video has no captions, resolve a direct,
   watermark-free MP4 URL via the free tikwm API and hand it to the existing ASR
   pipeline.

The whole thing is designed to add no new paid dependency: the proxy and RunPod
are already in use, and tikwm is free (limited to 1 request/second, handled here).
"""

import json
import logging
import re
import time
import threading
from typing import Optional

import httpx

from app.core.config import settings
from app.utils.webshare_proxy import get_webshare_proxy_url

logger = logging.getLogger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# tikwm free API allows 1 request/second. Serialize calls and pace them so a
# launch spike degrades into a short queue instead of a wall of failures.
_TIKWM_ENDPOINT = "https://www.tikwm.com/api/"
_tikwm_lock = threading.Lock()
_tikwm_last_call = 0.0


class TikTokService:
    """Resolve TikTok URLs to a transcript (captions) or a direct media URL."""

    def _proxy_url(self) -> Optional[str]:
        """Residential proxy URL for outbound TikTok requests, or None locally."""
        try:
            return get_webshare_proxy_url()
        except Exception as e:  # never let proxy lookup crash the request
            logger.warning(f"[TIKTOK] Could not get proxy URL: {e}")
            return None

    def _client(self, timeout: float = 25.0) -> httpx.Client:
        proxy = self._proxy_url()
        kwargs = {"timeout": timeout, "follow_redirects": True,
                  "headers": {"User-Agent": _BROWSER_UA}}
        if proxy:
            # httpx 0.25 uses the `proxies` argument
            kwargs["proxies"] = proxy
        return httpx.Client(**kwargs)

    # ---- Captions path -------------------------------------------------

    def get_transcript(self, url: str) -> Optional[dict]:
        """Return TikTok's own auto-captions as a transcript dict, or None.

        Returns a dict with keys: transcript, segments, language, source,
        confidence, duration, content. Returns None when the video has no
        captions or the page could not be read (caller then falls back to ASR).
        """
        try:
            html = self._fetch_page(url)
            if not html:
                return None
            item = self._extract_item_struct(html)
            if not item:
                logger.info(f"[TIKTOK] No item data found on page for {url}")
                return None

            caption = self._pick_caption(item)
            if not caption:
                logger.info(f"[TIKTOK] No captions available for {url}; will fall back to ASR")
                return None

            vtt = self._download_text(caption["url"])
            if not vtt:
                logger.info(f"[TIKTOK] Caption file empty/unreachable for {url}; falling back to ASR")
                return None

            segments = self._parse_vtt(vtt)
            if not segments:
                return None

            transcript = " ".join(s["text"] for s in segments).strip()
            duration = 0.0
            try:
                duration = float(item.get("video", {}).get("duration") or 0) or segments[-1]["end"]
            except Exception:
                duration = segments[-1]["end"] if segments else 0.0

            return {
                "transcript": transcript,
                "content": transcript,
                "segments": segments,
                "language": caption.get("language", "en"),
                "source": "tiktok_captions",
                "confidence": None,
                "duration": duration,
            }
        except Exception as e:
            logger.warning(f"[TIKTOK] Caption extraction failed for {url}: {e}")
            return None

    def _fetch_page(self, url: str) -> Optional[str]:
        try:
            with self._client() as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    logger.info(f"[TIKTOK] Page fetch HTTP {resp.status_code} for {url}")
                    return None
                return resp.text
        except Exception as e:
            logger.warning(f"[TIKTOK] Page fetch error for {url}: {e}")
            return None

    def _extract_item_struct(self, html: str) -> Optional[dict]:
        """Pull the itemStruct out of the embedded universal-data JSON."""
        m = re.search(
            r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not m:
            return None
        try:
            data = json.loads(m.group(1))
        except Exception:
            return None
        # Robust: recursively find the first dict that has an "itemStruct".
        item = self._find_key(data, "itemStruct")
        if isinstance(item, dict):
            return item
        # Some payloads nest the video fields directly under itemInfo
        info = self._find_key(data, "itemInfo")
        if isinstance(info, dict) and isinstance(info.get("itemStruct"), dict):
            return info["itemStruct"]
        return None

    @staticmethod
    def _find_key(obj, key):
        """Depth-first search for the first value under `key`."""
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if key in cur:
                    return cur[key]
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
        return None

    def _pick_caption(self, item: dict) -> Optional[dict]:
        """Choose the best caption track; prefer original/English webVTT."""
        video = item.get("video", {}) if isinstance(item, dict) else {}
        candidates = []

        # Newer schema: claInfo.captionInfos
        cla = video.get("claInfo", {}) or {}
        for c in (cla.get("captionInfos") or []):
            url = c.get("url") or (c.get("urlList") or [None])[0]
            if url and str(c.get("captionFormat", "webvtt")).lower() in ("webvtt", "vtt", ""):
                candidates.append({
                    "url": url,
                    "language": c.get("languageCode") or c.get("language") or "en",
                    "is_original": bool(c.get("isOriginalCaption")),
                })

        # Older schema: subtitleInfos
        for s in (video.get("subtitleInfos") or []):
            url = s.get("Url") or s.get("url")
            fmt = str(s.get("Format", "webvtt")).lower()
            if url and fmt in ("webvtt", "vtt", ""):
                candidates.append({
                    "url": url,
                    "language": (s.get("LanguageCodeName") or "en").split("-")[0],
                    "is_original": True,
                })

        if not candidates:
            return None

        def score(c):
            lang = (c.get("language") or "").lower()
            return (c.get("is_original", False), lang.startswith("en"))

        candidates.sort(key=score, reverse=True)
        return candidates[0]

    def _download_text(self, url: str) -> Optional[str]:
        try:
            with self._client() as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return None
                return resp.text
        except Exception as e:
            logger.warning(f"[TIKTOK] Caption download error: {e}")
            return None

    @staticmethod
    def _parse_vtt(vtt: str) -> list:
        """Parse webVTT into [{start, end, text}] segments."""
        segments = []
        ts = re.compile(
            r"(\d{2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})\s*-->\s*"
            r"(\d{2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})"
        )

        def to_sec(t: str) -> float:
            t = t.replace(",", ".")
            parts = t.split(":")
            parts = [float(p) for p in parts]
            while len(parts) < 3:
                parts.insert(0, 0.0)
            h, m, s = parts
            return h * 3600 + m * 60 + s

        blocks = re.split(r"\n\s*\n", vtt.replace("\r\n", "\n"))
        for block in blocks:
            lines = [ln for ln in block.split("\n") if ln.strip()]
            start = end = None
            text_lines = []
            for ln in lines:
                m = ts.search(ln)
                if m:
                    start, end = to_sec(m.group(1)), to_sec(m.group(2))
                elif ln.strip().upper() in ("WEBVTT",) or ln.strip().isdigit():
                    continue
                else:
                    text_lines.append(re.sub(r"<[^>]+>", "", ln).strip())
            text = " ".join(t for t in text_lines if t).strip()
            if start is not None and text:
                # TranscriptSegment requires end > start.
                end_v = end if (end is not None and end > start) else start + 0.001
                segments.append({"start": round(start, 3), "end": round(end_v, 3), "text": text})
        return segments

    # ---- Media fallback path (tikwm -> RunPod) -------------------------

    def resolve_media_url(self, url: str) -> Optional[str]:
        """Resolve a direct, watermark-free MP4 URL via the free tikwm API.

        Respects tikwm's 1 request/second free limit (serialized + paced with a
        retry on throttle). Returns the media URL, or None on failure.
        """
        for attempt in range(3):
            self._pace_tikwm()
            try:
                with httpx.Client(timeout=40.0, follow_redirects=True,
                                  headers={"User-Agent": _BROWSER_UA}) as client:
                    resp = client.get(_TIKWM_ENDPOINT, params={"url": url, "hd": 1})
                data = resp.json()
                if data.get("code") == 0:
                    d = data.get("data") or {}
                    media = d.get("hdplay") or d.get("play") or d.get("wmplay")
                    if media:
                        return media
                    logger.warning(f"[TIKTOK] tikwm returned no media url for {url}")
                    return None
                # code == -1 is the 1/sec throttle; back off and retry
                logger.info(f"[TIKTOK] tikwm throttle/err ({data.get('msg')}), retry {attempt+1}/3")
                time.sleep(1.2)
            except Exception as e:
                logger.warning(f"[TIKTOK] tikwm request failed: {e}")
                time.sleep(1.0)
        return None

    @staticmethod
    def _pace_tikwm() -> None:
        global _tikwm_last_call
        with _tikwm_lock:
            elapsed = time.monotonic() - _tikwm_last_call
            if elapsed < 1.1:
                time.sleep(1.1 - elapsed)
            _tikwm_last_call = time.monotonic()
