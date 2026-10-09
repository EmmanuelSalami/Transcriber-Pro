"""Service for fetching YouTube captions using youtube-transcript-api."""

import logging
from typing import Any, List, Optional

from youtube_transcript_api import (CouldNotRetrieveTranscript,
                                    NoTranscriptFound, TranscriptsDisabled,
                                    VideoUnavailable, YouTubeTranscriptApi)
from youtube_transcript_api.proxies import WebshareProxyConfig

from app.core.config import settings
from app.utils.webshare_proxy import get_webshare_proxy_credentials
from app.models.schemas import TranscriptSegment
from app.utils.error_detection import is_ip_blocked_error
from app.utils.youtube import extract_video_id

logger = logging.getLogger(__name__)


class YouTubeCaptionsService:
    """
    Service for fetching and processing YouTube captions.

    This service handles the complete workflow of fetching YouTube video captions,
    including:
    - Validating video URLs and extracting video IDs
    - Listing available transcripts for a video
    - Fetching transcripts in original or translated languages
    - Handling translation from source languages to target languages
    - Converting raw transcript data to structured segment format
    - Error handling for IP blocking, unavailable videos, and other API errors

    The service uses the youtube-transcript-api library to interact with YouTube's
    transcript API. It implements sophisticated fallback logic for translation,
    trying multiple source languages if the preferred language is not available.

    Attributes:
        None: Service is stateless, YouTubeTranscriptApi is instantiated per request

    Example:
        >>> service = YouTubeCaptionsService()
        >>> segments, language = service.fetch_transcript(
        ...     "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ...     translate_to="en"
        ... )
        >>> len(segments) > 0
        True
    """

    def __init__(self) -> None:
        """Initialize the YouTube captions service.

        Creates a new instance of the service. The service is stateless,
        and YouTubeTranscriptApi instances are created per request.
        """
        pass

    def _validate_input(
        self,
        video_url: str,
        language_codes: Optional[List[str]],
        translate_to: Optional[str],
    ) -> tuple[str, str]:
        """Validate and sanitize input parameters.

        Args:
            video_url (str): YouTube video URL.
            language_codes (Optional[List[str]]): Optional list of preferred language codes.
            translate_to (Optional[str]): Optional target language code for translation.

        Returns:
            tuple[str, str]: Tuple of (sanitized video_url, video_id).

        Raises:
            ValueError: If validation fails (empty URL, invalid format, etc.).
        """
        if not video_url:
            raise ValueError("Video URL cannot be empty")

        video_url = str(video_url).strip()
        if not video_url:
            raise ValueError("Video URL cannot be empty")

        if len(video_url) > settings.max_url_length:
            raise ValueError(
                f"Video URL is too long (maximum {settings.max_url_length} characters)"
            )

        video_id = extract_video_id(video_url)
        if not video_id:
            raise ValueError(f"Invalid YouTube URL: {video_url}")

        if (
            len(video_id) != settings.youtube_video_id_length
            or not video_id.replace("-", "").replace("_", "").isalnum()
        ):
            raise ValueError(f"Invalid YouTube video ID format: {video_id}")

        if language_codes:
            if len(language_codes) > settings.max_language_codes:
                raise ValueError(
                    f"Too many language codes specified (maximum {settings.max_language_codes})"
                )
            for lang_code in language_codes:
                if not lang_code or not isinstance(lang_code, str):
                    raise ValueError(f"Invalid language code: {lang_code}")
                lang_code_clean = lang_code.strip()
                if not (
                    settings.min_language_code_length
                    <= len(lang_code_clean)
                    <= settings.max_language_code_length
                    and lang_code_clean.replace("-", "").isalpha()
                ):
                    raise ValueError(f"Invalid language code format: {lang_code}")

        if translate_to:
            translate_to = translate_to.strip()
            if not (
                settings.min_language_code_length
                <= len(translate_to)
                <= settings.max_language_code_length
                and translate_to.replace("-", "").isalpha()
            ):
                raise ValueError(f"Invalid translation language code format: {translate_to}")

        return video_url, video_id

    def _list_transcripts(
        self, ytt_api: YouTubeTranscriptApi, video_id: str
    ) -> tuple[Any, list[Any]]:
        """List available transcripts for a video with error handling.

        Args:
            ytt_api (YouTubeTranscriptApi): YouTubeTranscriptApi instance.
            video_id (str): YouTube video ID.

        Returns:
            tuple[Any, list[Any]]: Tuple of (transcript_list, transcript_list_iter).

        Raises:
            CouldNotRetrieveTranscript: If transcripts cannot be retrieved.
        """
        try:
            transcript_list = ytt_api.list(video_id)
            transcript_list_iter = list(transcript_list)
            return transcript_list, transcript_list_iter
        except (CouldNotRetrieveTranscript, Exception) as e:
            if is_ip_blocked_error(e):
                error_details = str(e)
                logger.error(
                    f"[CAPTIONS] IP blocking detected when listing transcripts: {type(e).__name__} - {error_details}"
                )
                raise
            if isinstance(e, CouldNotRetrieveTranscript):
                raise
            error_details = str(e)
            raise CouldNotRetrieveTranscript(f"Error listing transcripts: {error_details}")

    def _log_available_transcripts(self, transcript_list_iter: list, video_id: str) -> None:
        """Log information about available transcripts.

        Args:
            transcript_list_iter (list): List of available transcripts.
            video_id (str): YouTube video ID for logging.

        Returns:
            None: This function does not return a value.
        """
        logger.info(f"[CAPTIONS] Available transcripts for video {video_id}:")
        for transcript in transcript_list_iter:
            logger.info(
                f"[CAPTIONS]   - {transcript.language} ({transcript.language_code}), "
                f"generated={transcript.is_generated}, "
                f"translatable={transcript.is_translatable}"
            )

    def _get_base_language_code(self, language_code: str) -> str:
        """Extract base language code from a language code (e.g., 'en' from 'en-GB').

        Args:
            language_code (str): Language code (e.g., 'en', 'en-GB', 'en-US', 'es-MX').

        Returns:
            str: Base language code (e.g., 'en', 'es').
        """
        return language_code.split("-")[0].split("_")[0].lower()

    def _is_same_base_language(self, lang1: str, lang2: str) -> bool:
        """Check if two language codes share the same base language.

        Args:
            lang1 (str): First language code.
            lang2 (str): Second language code.

        Returns:
            bool: True if both codes share the same base language (e.g., 'en' and 'en-GB').
        """
        return self._get_base_language_code(lang1) == self._get_base_language_code(lang2)

    def _find_direct_transcript(
        self, transcript_list: Any, translate_to: str, transcript_list_iter: Optional[list] = None
    ) -> tuple[bool, Optional[Any], Optional[str]]:
        """Try to find transcript directly in target language.

        First tries exact match, then tries language variants (e.g., 'en' matches 'en-GB').

        Args:
            transcript_list (Any): TranscriptList object from youtube-transcript-api.
            translate_to (str): Target language code.
            transcript_list_iter (Optional[list]): Optional list of available transcripts for variant matching.

        Returns:
            tuple[bool, Optional[Any], Optional[str]]: Tuple of (success, fetched_transcript, detected_language).
        """
        try:
            logger.info(
                f"[CAPTIONS] Attempting to find transcript directly in target language '{translate_to}'"
            )
            transcript = transcript_list.find_transcript([translate_to])
            fetched_transcript = transcript.fetch()
            detected_language = translate_to
            logger.info(
                f"[CAPTIONS] Successfully fetched transcript in target language: {translate_to}"
            )
            return True, fetched_transcript, detected_language
        except (NoTranscriptFound, CouldNotRetrieveTranscript):
            if transcript_list_iter:
                base_target = self._get_base_language_code(translate_to)
                logger.info(
                    f"[CAPTIONS] Exact match for '{translate_to}' not found. "
                    f"Checking for language variants with base language '{base_target}'..."
                )

                for transcript in transcript_list_iter:
                    transcript_base = self._get_base_language_code(transcript.language_code)
                    if transcript_base == base_target:
                        logger.info(
                            f"[CAPTIONS] Found variant transcript: {transcript.language_code} "
                            f"({transcript.language}) matches base language '{base_target}'. "
                            f"Using it directly without translation."
                        )
                        try:
                            variant_transcript = transcript_list.find_transcript(
                                [transcript.language_code]
                            )
                            fetched_transcript = variant_transcript.fetch()
                            detected_language = transcript.language_code
                            logger.info(
                                f"[CAPTIONS] Successfully fetched variant transcript: {transcript.language_code}"
                            )
                            return True, fetched_transcript, detected_language
                        except (NoTranscriptFound, CouldNotRetrieveTranscript) as e:
                            logger.debug(
                                f"[CAPTIONS] Failed to fetch variant {transcript.language_code}: {e}. "
                                "Trying next variant..."
                            )
                            continue
                        except Exception as e:
                            logger.warning(
                                f"[CAPTIONS] Unexpected error fetching variant {transcript.language_code}: {e}"
                            )
                            continue

                logger.info(
                    f"[CAPTIONS] No variant transcripts found for base language '{base_target}'. "
                    "Will attempt translation from available source transcript."
                )
            else:
                logger.info(
                    f"[CAPTIONS] Transcript not available directly in target language '{translate_to}'. "
                    "This is normal - will attempt translation from available source transcript."
                )
            return False, None, None
        except Exception as e:
            error_type = type(e).__name__
            error_details = str(e)
            logger.warning(
                f"[CAPTIONS] Unexpected error fetching transcript in {translate_to}: "
                f"{error_type} - {error_details}. Will try translation approach."
            )
            return False, None, None

    def _log_translation_capabilities(self, transcript_list_iter: list, video_id: str) -> None:
        """Log detailed information about each transcript's translation capabilities.

        Args:
            transcript_list_iter (list): List of available transcripts.
            video_id (str): YouTube video ID for logging.

        Returns:
            None: This function does not return a value.
        """
        logger.info(
            f"[CAPTIONS] Analyzing {len(transcript_list_iter)} available transcript(s) for translation:"
        )
        for transcript in transcript_list_iter:
            translation_info = "N/A"
            if hasattr(transcript, "translation_languages") and transcript.translation_languages:
                try:
                    available_langs = [
                        lang.language_code for lang in transcript.translation_languages
                    ]
                    max_display = settings.max_languages_display
                    translation_info = (
                        f"can translate to: {', '.join(available_langs[:max_display])}"
                        + (
                            f" (and {len(available_langs) - max_display} more)"
                            if len(available_langs) > max_display
                            else ""
                        )
                    )
                except (AttributeError, TypeError) as e:
                    translation_info = f"translation_languages check failed: {type(e).__name__}"
            logger.info(
                f"[CAPTIONS]   - {transcript.language} ({transcript.language_code}), "
                f"generated={transcript.is_generated}, "
                f"translatable={transcript.is_translatable}, "
                f"{translation_info}"
            )

    def _build_candidate_transcripts(
        self,
        transcript_list: Any,
        transcript_list_iter: list[Any],
        language_codes: Optional[List[str]],
    ) -> list[Any]:
        """Build list of candidate source transcripts for translation.

        Args:
            transcript_list (Any): TranscriptList object from youtube-transcript-api.
            transcript_list_iter (list[Any]): List of available transcripts.
            language_codes (Optional[List[str]]): Optional list of preferred language codes.

        Returns:
            list[Any]: List of candidate transcripts to try for translation.
        """
        candidate_transcripts = []

        if language_codes:
            for lang_code in language_codes:
                try:
                    transcript = transcript_list.find_transcript([lang_code])
                    candidate_transcripts.append(transcript)
                except (NoTranscriptFound, CouldNotRetrieveTranscript):
                    continue

        if not candidate_transcripts:
            try:
                candidate_transcripts.append(
                    transcript_list.find_manually_created_transcript(
                        settings.get_preferred_languages()
                    )
                )
            except (NoTranscriptFound, CouldNotRetrieveTranscript):
                pass

        for transcript in transcript_list_iter:
            if transcript not in candidate_transcripts:
                candidate_transcripts.append(transcript)

        return candidate_transcripts

    def _can_translate(
        self, source_transcript: Any, translate_to: str
    ) -> tuple[bool, Optional[str]]:
        """Check if transcript can be translated to target language.

        Args:
            source_transcript (Any): Source transcript object to check.
            translate_to (str): Target language code.

        Returns:
            tuple[bool, Optional[str]]: Tuple of (can_translate, error_message).
                - can_translate: True if translation should be attempted.
                - error_message: Error message if translation cannot be attempted, None otherwise.
        """
        if self._is_same_base_language(source_transcript.language_code, translate_to):
            logger.info(
                f"[CAPTIONS] Source language '{source_transcript.language_code}' and target language "
                f"'{translate_to}' share the same base language. Translation not needed - should use "
                f"variant matching instead."
            )
            return False, (
                f"Source language '{source_transcript.language_code}' and target language "
                f"'{translate_to}' are the same base language. Use variant matching instead."
            )

        if not source_transcript.is_translatable:
            logger.debug(
                f"[CAPTIONS] Transcript in '{source_transcript.language_code}' is not translatable, "
                f"trying next candidate..."
            )
            return False, f"Transcript '{source_transcript.language_code}' is not translatable"

        if (
            hasattr(source_transcript, "translation_languages")
            and source_transcript.translation_languages
        ):
            try:
                available_langs = [
                    lang.language_code for lang in source_transcript.translation_languages
                ]
                if translate_to not in available_langs:
                    logger.info(
                        f"[CAPTIONS] Target language '{translate_to}' not in available translation "
                        f"languages for '{source_transcript.language_code}'. Available: {', '.join(available_langs[:settings.max_languages_display])}"
                        + (
                            f" (and {len(available_langs) - settings.max_languages_display} more)"
                            if len(available_langs) > settings.max_languages_display
                            else ""
                        )
                        + ". Trying next candidate..."
                    )
                    return (
                        False,
                        f"Language '{translate_to}' not available for translation from '{source_transcript.language_code}'",
                    )
                else:
                    logger.info(
                        f"[CAPTIONS] Target language '{translate_to}' is available in translation languages "
                        f"for '{source_transcript.language_code}'. Proceeding with translation..."
                    )
            except (AttributeError, TypeError) as e:
                logger.debug(
                    f"[CAPTIONS] Could not check translation_languages (error: {type(e).__name__}), "
                    f"proceeding with translation attempt"
                )

        return True, None

    def _try_translate_transcript(
        self, source_transcript: Any, translate_to: str
    ) -> tuple[bool, Optional[Any], Optional[str], Optional[str]]:
        """Attempt to translate a single transcript.

        Args:
            source_transcript (Any): Source transcript object to translate.
            translate_to (str): Target language code.

        Returns:
            tuple[bool, Optional[Any], Optional[str], Optional[str]]: Tuple of (success, fetched_transcript, detected_language, error_message).
                - success: True if translation succeeded.
                - fetched_transcript: Translated transcript data if successful, None otherwise.
                - detected_language: Target language code if successful, None otherwise.
                - error_message: Error message if translation failed, None otherwise.
        """
        try:
            logger.debug(
                f"[CAPTIONS] Calling translate() method for {source_transcript.language_code} -> {translate_to}"
            )
            translated_transcript = source_transcript.translate(translate_to)
            logger.debug(
                "[CAPTIONS] translate() succeeded, now fetching translated transcript data"
            )
            fetched_transcript = translated_transcript.fetch()
            detected_language = translate_to
            logger.info(
                f"[CAPTIONS] Successfully translated transcript from {source_transcript.language_code} "
                f"({source_transcript.language}) to {translate_to}"
            )
            return True, fetched_transcript, detected_language, None

        except (NoTranscriptFound, CouldNotRetrieveTranscript) as e:
            error_type = type(e).__name__
            error_details = str(e)

            logger.warning(
                f"[CAPTIONS] Translation failed for {source_transcript.language_code} -> {translate_to}. "
                f"Exception: {error_type}. Details: {error_details[:200]}"
            )

            error_summary = f"{error_type}"
            if error_details and len(error_details) < 100:
                error_summary += f": {error_details}"
            return False, None, None, error_summary

        except (TranscriptsDisabled, VideoUnavailable) as e:
            logger.warning(f"[CAPTIONS] Video issue detected: {type(e).__name__} - {str(e)}")
            raise

        except Exception as e:
            if is_ip_blocked_error(e):
                error_details = str(e)
                error_type = type(e).__name__
                logger.error(
                    f"[CAPTIONS] IP blocking detected in unexpected exception: {error_type} - {error_details}. "
                    f"Re-raising immediately."
                )
                raise CouldNotRetrieveTranscript(error_details)

            error_type = type(e).__name__
            error_details = str(e)
            logger.warning(
                f"[CAPTIONS] Unexpected error translating from '{source_transcript.language_code}' "
                f"to '{translate_to}': {error_type} - {error_details}. Trying next candidate..."
            )
            return False, None, None, f"{error_type}: {error_details[:100]}"

    def _attempt_translation(
        self,
        candidate_transcripts: list,
        translate_to: str,
        video_id: str,
    ) -> tuple[bool, Optional[Any], Optional[str], list[str]]:
        """Attempt to translate transcript from candidate sources.

        High-level orchestrator that tries each candidate transcript until one succeeds.

        Args:
            candidate_transcripts (list): List of candidate transcripts to try.
            translate_to (str): Target language code.
            video_id (str): YouTube video ID for logging.

        Returns:
            tuple[bool, Optional[Any], Optional[str], list[str]]: Tuple of (success, fetched_transcript, detected_language, translation_errors).
        """
        translation_errors = []
        translation_success = False
        fetched_transcript = None
        detected_language = None

        for source_transcript in candidate_transcripts:
            logger.info(
                f"[CAPTIONS] Attempting to translate from {source_transcript.language_code} "
                f"({source_transcript.language}) to {translate_to}. "
                f"Is translatable: {source_transcript.is_translatable}"
            )

            can_translate, check_error = self._can_translate(source_transcript, translate_to)
            if not can_translate:
                if check_error:
                    translation_errors.append(check_error)
                continue

            success, result_transcript, result_language, translate_error = (
                self._try_translate_transcript(source_transcript, translate_to)
            )

            if success:
                fetched_transcript = result_transcript
                detected_language = result_language
                translation_success = True
                break
            else:
                if translate_error:
                    translation_errors.append(translate_error)

        return translation_success, fetched_transcript, detected_language, translation_errors

    def _fetch_translated_transcript(
        self,
        ytt_api: YouTubeTranscriptApi,
        video_id: str,
        translate_to: str,
        language_codes: Optional[List[str]],
    ) -> tuple[Any, str]:
        """Fetch transcript with translation to target language.

        Args:
            ytt_api (YouTubeTranscriptApi): YouTubeTranscriptApi instance.
            video_id (str): YouTube video ID.
            translate_to (str): Target language code for translation.
            language_codes (Optional[List[str]]): Optional list of preferred language codes.

        Returns:
            tuple[Any, str]: Tuple of (fetched_transcript, detected_language).

        Raises:
            CouldNotRetrieveTranscript: If translation fails.
        """
        transcript_list: Any
        transcript_list_iter: list[Any]
        transcript_list, transcript_list_iter = self._list_transcripts(ytt_api, video_id)

        self._log_available_transcripts(transcript_list_iter, video_id)

        transcript_found, fetched_transcript, detected_language = self._find_direct_transcript(
            transcript_list, translate_to, transcript_list_iter
        )

        if not transcript_found:
            logger.info(
                f"[CAPTIONS] Proceeding with translation workflow for language '{translate_to}'"
            )

            if not transcript_list_iter:
                raise CouldNotRetrieveTranscript(
                    f"Could not retrieve a transcript for the video https://www.youtube.com/watch?v={video_id}! "
                    "No transcripts available for translation."
                )

            self._log_translation_capabilities(transcript_list_iter, video_id)

            candidate_transcripts = self._build_candidate_transcripts(
                transcript_list, transcript_list_iter, language_codes
            )

            translation_success, fetched_transcript, detected_language, translation_errors = (
                self._attempt_translation(candidate_transcripts, translate_to, video_id)
            )

            if not translation_success:
                error_summary = (
                    "; ".join(translation_errors[:3])
                    if translation_errors
                    else "Translation not available"
                )
                error_msg = (
                    f"Could not translate transcript to '{translate_to}'. "
                    f"Tried {len(candidate_transcripts)} source transcript(s). "
                    f"Note: Even though the transcript may indicate translation is available, "
                    f"YouTube's translation API may have restrictions or the translation endpoint may be unavailable. "
                    f"Errors: {error_summary}"
                )
                logger.warning(f"[CAPTIONS] Translation failed for video {video_id}: {error_msg}")
                raise CouldNotRetrieveTranscript(
                    f"Could not retrieve a translated transcript for the video https://www.youtube.com/watch?v={video_id}! "
                    f"Translation to '{translate_to}' is not available. "
                    "The original transcript may be available without translation."
                )

        assert fetched_transcript is not None, "fetched_transcript should not be None at this point"
        assert detected_language is not None, "detected_language should not be None at this point"
        return fetched_transcript, detected_language

    def _fetch_original_transcript(
        self,
        ytt_api: YouTubeTranscriptApi,
        video_id: str,
        language_codes: Optional[List[str]],
    ) -> tuple[Any, str]:
        """Fetch transcript in original language.

        Args:
            ytt_api (YouTubeTranscriptApi): YouTubeTranscriptApi instance.
            video_id (str): YouTube video ID.
            language_codes (Optional[List[str]]): Optional list of preferred language codes.

        Returns:
            tuple[Any, str]: Tuple of (fetched_transcript, detected_language).

        Raises:
            CouldNotRetrieveTranscript: If transcript cannot be retrieved.
        """
        transcript_list: Any
        transcript_list_iter: list[Any]
        transcript_list, transcript_list_iter = self._list_transcripts(ytt_api, video_id)

        if not transcript_list_iter:
            raise CouldNotRetrieveTranscript(
                f"Could not retrieve a transcript for the video https://www.youtube.com/watch?v={video_id}! "
                "No transcripts available for this video."
            )

        if language_codes:
            transcript = None
            for lang_code in language_codes:
                try:
                    transcript = transcript_list.find_transcript([lang_code])
                    break
                except (NoTranscriptFound, CouldNotRetrieveTranscript):
                    continue

            if transcript is None:
                transcript = transcript_list_iter[0]
                logger.info(
                    f"[CAPTIONS] Preferred languages {language_codes} not available, "
                    f"using {transcript.language_code} ({transcript.language})"
                )

            fetched_transcript = transcript.fetch()
            detected_language = transcript.language_code
        else:
            transcript = None
            common_languages = settings.get_common_languages()

            for lang_code in common_languages:
                try:
                    transcript = transcript_list.find_transcript([lang_code])
                    break
                except (NoTranscriptFound, CouldNotRetrieveTranscript):
                    continue

            if transcript is None:
                transcript = transcript_list_iter[0]
                logger.info(
                    f"[CAPTIONS] No common language transcript found, "
                    f"using {transcript.language_code} ({transcript.language})"
                )

            fetched_transcript = transcript.fetch()
            detected_language = transcript.language_code

        return fetched_transcript, detected_language

    def _convert_segments(self, fetched_transcript, video_id: str) -> List[TranscriptSegment]:
        """Convert FetchedTranscript to list of TranscriptSegment objects.

        Uses list comprehension with filtering for better performance and reduced memory allocations.

        Args:
            fetched_transcript (Any): FetchedTranscript object from youtube-transcript-api.
            video_id (str): YouTube video ID for logging.

        Returns:
            List[TranscriptSegment]: List of TranscriptSegment objects.
        """

        def _process_snippet(snippet):
            """Process a single snippet into a TranscriptSegment or None."""
            if not snippet.text or not snippet.text.strip():
                return None
            try:
                start_time = float(snippet.start)
                duration_time = float(snippet.duration)
                end_time = start_time + duration_time

                if start_time < 0:
                    logger.warning(
                        f"[CAPTIONS] Skipping segment with negative start time for video {video_id}: {start_time}"
                    )
                    return None
                if end_time <= start_time:
                    logger.warning(
                        f"[CAPTIONS] Skipping segment with invalid time range for video {video_id}: "
                        f"start={start_time}, end={end_time}"
                    )
                    return None

                text = snippet.text.strip()
                if len(text) > settings.max_segment_text_length:
                    logger.warning(
                        f"[CAPTIONS] Truncating segment text exceeding {settings.max_segment_text_length} "
                        f"characters for video {video_id}"
                    )
                    text = text[: settings.max_segment_text_length]

                return TranscriptSegment(
                    text=text,
                    start=start_time,
                    end=end_time,
                )
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(
                    f"[CAPTIONS] Skipping invalid segment for video {video_id}: {type(e).__name__} - {str(e)}"
                )
                return None

        segments = [
            seg
            for seg in (_process_snippet(snippet) for snippet in fetched_transcript)
            if seg is not None
        ]
        return segments

    def fetch_transcript(
        self,
        video_url: str,
        language_codes: Optional[List[str]] = None,
        translate_to: Optional[str] = None,
    ) -> tuple[List[TranscriptSegment], str]:
        """
        Fetch transcript from YouTube captions.

        Args:
            video_url (str): YouTube video URL.
            language_codes (Optional[List[str]]): Optional list of preferred language codes (ISO 639-1).
            translate_to (Optional[str]): Optional target language code for translation.

        Returns:
            tuple[List[TranscriptSegment], str]: Tuple of (list of transcript segments, detected language code).

        Raises:
            CouldNotRetrieveTranscript: If transcripts are not available or other API errors.
            TranscriptsDisabled: If transcripts are disabled for the video.
            NoTranscriptFound: If no transcript found for the specified languages.
            VideoUnavailable: If the video is unavailable.
            ValueError: If video URL is invalid.
        """
        video_url, video_id = self._validate_input(video_url, language_codes, translate_to)

        try:
            proxy_config = None
            creds = get_webshare_proxy_credentials()
            if creds:
                proxy_config = WebshareProxyConfig(
                    proxy_username=creds[0],
                    proxy_password=creds[1],
                    retries_when_blocked=10,
                )
            ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)

            if translate_to:
                fetched_transcript, detected_language = self._fetch_translated_transcript(
                    ytt_api, video_id, translate_to, language_codes
                )
            else:
                fetched_transcript, detected_language = self._fetch_original_transcript(
                    ytt_api, video_id, language_codes
                )

            try:
                original_count = (
                    len(fetched_transcript) if hasattr(fetched_transcript, "__len__") else 0
                )
            except (TypeError, AttributeError):
                original_count = 0

            segments = self._convert_segments(fetched_transcript, video_id)

            if original_count > 0 and len(segments) < original_count:
                filtered_count = original_count - len(segments)
                logger.warning(
                    f"[CAPTIONS] Filtered out {filtered_count} invalid segments "
                    f"out of {original_count} total for video {video_id}"
                )

            if not segments:
                raise CouldNotRetrieveTranscript(
                    f"Could not retrieve valid transcript segments for video "
                    f"https://www.youtube.com/watch?v={video_id}!"
                )

            logger.info(
                f"[CAPTIONS] Successfully fetched {len(segments)} segments for video {video_id}, "
                f"language: {detected_language}"
            )
            return segments, detected_language

        except TranscriptsDisabled:
            logger.warning(f"[CAPTIONS] Transcripts disabled for video {video_id}")
            raise
        except NoTranscriptFound:
            logger.warning(f"[CAPTIONS] No transcript found for video {video_id}")
            raise
        except VideoUnavailable:
            logger.warning(f"[CAPTIONS] Video unavailable: {video_id}")
            raise
        except CouldNotRetrieveTranscript as e:
            logger.error(f"[CAPTIONS] YouTube Transcript API error for video {video_id}: {str(e)}")
            raise

    def is_transcript_available(self, video_url: str) -> bool:
        """Check if transcript is available for the given video.

        Args:
            video_url (str): YouTube video URL.

        Returns:
            bool: True if transcript is available, False otherwise.
        """
        if not video_url:
            return False

        video_url = str(video_url).strip()
        if not video_url:
            return False

        video_id = extract_video_id(video_url)
        if not video_id:
            return False

        try:
            proxy_config = None
            creds = get_webshare_proxy_credentials()
            if creds:
                proxy_config = WebshareProxyConfig(
                    proxy_username=creds[0],
                    proxy_password=creds[1],
                    retries_when_blocked=10,
                )
            ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
            transcript_list = ytt_api.list(video_id)
            transcript_list_iter = list(transcript_list)
            return len(transcript_list_iter) > 0
        except Exception as e:
            logger.debug(
                f"Transcript check failed for video {video_id}: {type(e).__name__} - {str(e)}"
            )
            return False
