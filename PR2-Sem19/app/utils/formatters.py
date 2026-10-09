"""Format converters for transcription output (JSON, SRT, VTT, Text)."""

from typing import List

from app.models.schemas import TranscriptSegment


def format_as_text(segments: List[TranscriptSegment]) -> str:
    """Convert transcript segments to plain text format.

    Joins all segment texts with spaces to create a continuous text transcript.
    Empty segments are skipped.

    Args:
        segments: List of transcript segments with text and timing.

    Returns:
        str: Plain text transcript with segments joined by spaces.
            Returns empty string if segments list is empty.

    Example:
        >>> segments = [
        ...     TranscriptSegment(text="Hello", start=0.0, end=1.0),
        ...     TranscriptSegment(text="world", start=1.0, end=2.0)
        ... ]
        >>> format_as_text(segments)
        'Hello world'
    """
    if not segments:
        return ""
    texts = [seg.text for seg in segments if seg.text and seg.text.strip()]
    return " ".join(texts)


def format_as_srt(segments: List[TranscriptSegment]) -> str:
    """Convert transcript segments to SRT (SubRip) subtitle format.

    Creates a standard SRT subtitle file with numbered entries, timestamps,
    and text content. Each segment becomes a subtitle entry.

    Args:
        segments: List of transcript segments with text and timing.

    Returns:
        str: SRT formatted string with numbered subtitles.
            Returns empty string if segments list is empty.

    Example:
        >>> segments = [
        ...     TranscriptSegment(text="Hello", start=0.0, end=1.0),
        ...     TranscriptSegment(text="world", start=1.0, end=2.0)
        ... ]
        >>> format_as_srt(segments)
        '1\\n00:00:00,000 --> 00:00:01,000\\nHello\\n\\n2\\n00:00:01,000 --> 00:00:02,000\\nworld\\n\\n'
    """
    if not segments:
        return ""
    srt_lines = []
    for idx, segment in enumerate(segments, start=1):
        start_time = _format_srt_timestamp(segment.start)
        end_time = _format_srt_timestamp(segment.end)

        srt_lines.append(f"{idx}")
        srt_lines.append(f"{start_time} --> {end_time}")
        srt_lines.append(segment.text)
        srt_lines.append("")

    return "\n".join(srt_lines)


def format_as_vtt(segments: List[TranscriptSegment]) -> str:
    """Convert transcript segments to VTT (WebVTT) subtitle format.

    Creates a standard WebVTT subtitle file with WEBVTT header, timestamps,
    and text content. Each segment becomes a cue entry.

    Args:
        segments: List of transcript segments with text and timing.

    Returns:
        str: VTT formatted string with WEBVTT header and cues.
            Returns "WEBVTT\\n" if segments list is empty.

    Example:
        >>> segments = [
        ...     TranscriptSegment(text="Hello", start=0.0, end=1.0),
        ...     TranscriptSegment(text="world", start=1.0, end=2.0)
        ... ]
        >>> format_as_vtt(segments)
        'WEBVTT\\n\\n00:00:00.000 --> 00:00:01.000\\nHello\\n\\n00:00:01.000 --> 00:00:02.000\\nworld\\n\\n'
    """
    if not segments:
        return "WEBVTT\n"
    vtt_lines = ["WEBVTT", ""]

    for segment in segments:
        start_time = _format_vtt_timestamp(segment.start)
        end_time = _format_vtt_timestamp(segment.end)
        cue_text = segment.text

        vtt_lines.append(f"{start_time} --> {end_time}")
        vtt_lines.append(cue_text)
        vtt_lines.append("")

    return "\n".join(vtt_lines)


def _format_srt_timestamp(seconds: float) -> str:
    """Format seconds to SRT timestamp format (HH:MM:SS,mmm).

    Converts a time value in seconds to the SRT subtitle timestamp format.
    Negative values are clamped to 0.

    Args:
        seconds: Time in seconds (will be clamped to 0 if negative or invalid).

    Returns:
        str: Formatted timestamp string in HH:MM:SS,mmm format.

    Example:
        >>> _format_srt_timestamp(125.5)
        '00:02:05,500'
        >>> _format_srt_timestamp(3661.123)
        '01:01:01,123'
    """
    if not isinstance(seconds, (int, float)) or seconds != seconds:
        seconds = 0.0
    elif seconds == float("inf") or seconds == float("-inf"):
        seconds = 0.0

    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds % 1) * 1000))
    if millis >= 1000:
        millis = 0
        secs += 1
        if secs >= 60:
            secs = 0
            minutes += 1
            if minutes >= 60:
                minutes = 0
                hours += 1

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_timestamp(seconds: float) -> str:
    """Format seconds to VTT timestamp format (HH:MM:SS.mmm).

    Converts a time value in seconds to the WebVTT subtitle timestamp format.
    Negative values are clamped to 0. Note: VTT uses period (.) as millisecond separator,
    while SRT uses comma (,).

    Args:
        seconds: Time in seconds (will be clamped to 0 if negative or invalid).

    Returns:
        str: Formatted timestamp string in HH:MM:SS.mmm format.

    Example:
        >>> _format_vtt_timestamp(125.5)
        '00:02:05.500'
        >>> _format_vtt_timestamp(3661.123)
        '01:01:01.123'
    """
    if not isinstance(seconds, (int, float)) or seconds != seconds:
        seconds = 0.0
    elif seconds == float("inf") or seconds == float("-inf"):
        seconds = 0.0

    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds % 1) * 1000))
    if millis >= 1000:
        millis = 0
        secs += 1
        if secs >= 60:
            secs = 0
            minutes += 1
            if minutes >= 60:
                minutes = 0
                hours += 1

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
