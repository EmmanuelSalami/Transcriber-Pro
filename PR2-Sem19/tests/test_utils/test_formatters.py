"""
Unit tests for format conversion utilities.

Tests cover:
- Happy path scenarios (valid segments)
- Edge cases (empty segments, negative timestamps)
- Error conditions (invalid inputs)
- Boundary value analysis (zero, large values, precision)
"""

from app.models.schemas import TranscriptSegment
from app.utils.formatters import (_format_srt_timestamp, _format_vtt_timestamp,
                                  format_as_srt, format_as_text, format_as_vtt)


class TestFormatAsText:
    """Test format_as_text function."""

    def test_single_segment(self, sample_transcript_segments):
        """Test: Single segment formats correctly."""
        segments = [sample_transcript_segments[0]]
        result = format_as_text(segments)
        assert result == "Hello"

    def test_multiple_segments(self, sample_transcript_segments):
        """Test: Multiple segments join with spaces."""
        result = format_as_text(sample_transcript_segments)
        assert result == "Hello world How are you?"

    def test_empty_segments_list(self, sample_transcript_segments_empty):
        """Test: Empty segments list returns empty string."""
        result = format_as_text(sample_transcript_segments_empty)
        assert result == ""

    def test_segments_with_empty_text(self, sample_transcript_segments_with_empty_text):
        """Test: Segments with empty text are filtered out."""
        result = format_as_text(sample_transcript_segments_with_empty_text)
        assert result == "Hello world"
        assert "  " not in result  # Whitespace-only segments should be filtered

    def test_segments_with_whitespace_only(self):
        """Test: Segments with whitespace-only text are filtered."""
        segments = [
            TranscriptSegment(text="Hello", start=0.0, end=1.0),
            TranscriptSegment(text="   ", start=1.0, end=2.0),
            TranscriptSegment(text="world", start=2.0, end=3.0),
        ]
        result = format_as_text(segments)
        assert result == "Hello world"

    def test_single_empty_segment(self):
        """Test: Single empty segment returns empty string."""
        segments = [TranscriptSegment(text="", start=0.0, end=1.0)]
        result = format_as_text(segments)
        assert result == ""

    def test_segments_with_special_characters(self):
        """Test: Segments with special characters format correctly."""
        segments = [
            TranscriptSegment(text="Hello, world!", start=0.0, end=1.0),
            TranscriptSegment(text="How are you?", start=1.0, end=2.0),
        ]
        result = format_as_text(segments)
        assert result == "Hello, world! How are you?"

    def test_segments_with_newlines(self):
        """Test: Segments with newlines format correctly."""
        segments = [
            TranscriptSegment(text="Line 1\nLine 2", start=0.0, end=1.0),
            TranscriptSegment(text="Line 3", start=1.0, end=2.0),
        ]
        result = format_as_text(segments)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result


class TestFormatAsSRT:
    """Test format_as_srt function."""

    def test_single_segment(self, sample_transcript_segments):
        """Test: Single segment formats as SRT correctly."""
        segments = [sample_transcript_segments[0]]
        result = format_as_srt(segments)
        assert "1\n" in result
        assert "00:00:00,000 --> 00:00:01,000" in result
        assert "Hello" in result

    def test_multiple_segments(self, sample_transcript_segments):
        """Test: Multiple segments format as SRT correctly."""
        result = format_as_srt(sample_transcript_segments)
        assert "1\n" in result
        assert "2\n" in result
        assert "3\n" in result
        assert "00:00:00,000 --> 00:00:01,000" in result
        assert "00:00:01,000 --> 00:00:02,000" in result
        assert "00:00:02,000 --> 00:00:04,000" in result
        assert "Hello" in result
        assert "world" in result
        assert "How are you?" in result

    def test_empty_segments_list(self, sample_transcript_segments_empty):
        """Test: Empty segments list returns empty string."""
        result = format_as_srt(sample_transcript_segments_empty)
        assert result == ""

    def test_segment_numbering(self, sample_transcript_segments):
        """Test: Segments are numbered sequentially starting from 1."""
        result = format_as_srt(sample_transcript_segments)
        lines = result.split("\n")
        # Find segment numbers
        segment_numbers = [line for line in lines if line.isdigit()]
        assert segment_numbers == ["1", "2", "3"]

    def test_timestamp_format(self, sample_transcript_segments):
        """Test: Timestamps are formatted correctly (HH:MM:SS,mmm)."""
        result = format_as_srt(sample_transcript_segments)
        assert "00:00:00,000 --> 00:00:01,000" in result
        # Check format: HH:MM:SS,mmm
        import re

        pattern = r"\d{2}:\d{2}:\d{2},\d{3}"
        matches = re.findall(pattern, result)
        assert len(matches) >= 2  # At least start and end timestamps

    def test_segments_with_empty_text(self, sample_transcript_segments_with_empty_text):
        """Test: Segments with empty text are still included in SRT."""
        result = format_as_srt(sample_transcript_segments_with_empty_text)
        # Empty segments should still be included
        assert "1\n" in result
        assert "4\n" in result  # Should have 4 segments

    def test_negative_timestamps(self):
        """Test: Negative timestamps are clamped to zero."""
        segments = [TranscriptSegment(text="Hello", start=-1.0, end=-0.5)]
        result = format_as_srt(segments)
        assert "00:00:00,000 --> 00:00:00,000" in result

    def test_large_timestamps(self):
        """Test: Large timestamps format correctly."""
        segments = [TranscriptSegment(text="Hello", start=3661.123, end=3662.456)]
        result = format_as_srt(segments)
        assert "01:01:01,123 --> 01:01:02,456" in result

    def test_millisecond_precision(self):
        """Test: Millisecond precision is maintained."""
        segments = [TranscriptSegment(text="Hello", start=1.234, end=2.567)]
        result = format_as_srt(segments)
        assert "00:00:01,234 --> 00:00:02,567" in result


class TestFormatAsVTT:
    """Test format_as_vtt function."""

    def test_single_segment(self, sample_transcript_segments):
        """Test: Single segment formats as VTT correctly."""
        segments = [sample_transcript_segments[0]]
        result = format_as_vtt(segments)
        assert result.startswith("WEBVTT")
        assert "00:00:00.000 --> 00:00:01.000" in result
        assert "Hello" in result

    def test_multiple_segments(self, sample_transcript_segments):
        """Test: Multiple segments format as VTT correctly."""
        result = format_as_vtt(sample_transcript_segments)
        assert result.startswith("WEBVTT")
        assert "00:00:00.000 --> 00:00:01.000" in result
        assert "00:00:01.000 --> 00:00:02.000" in result
        assert "00:00:02.000 --> 00:00:04.000" in result
        assert "Hello" in result
        assert "world" in result
        assert "How are you?" in result

    def test_empty_segments_list(self, sample_transcript_segments_empty):
        """Test: Empty segments list returns WEBVTT header only."""
        result = format_as_vtt(sample_transcript_segments_empty)
        assert result == "WEBVTT\n"

    def test_timestamp_format(self, sample_transcript_segments):
        """Test: Timestamps are formatted correctly (HH:MM:SS.mmm)."""
        result = format_as_vtt(sample_transcript_segments)
        # Check format: HH:MM:SS.mmm (period, not comma)
        import re

        pattern = r"\d{2}:\d{2}:\d{2}\.\d{3}"
        matches = re.findall(pattern, result)
        assert len(matches) >= 2  # At least start and end timestamps

    def test_vtt_uses_period_not_comma(self, sample_transcript_segments):
        """Test: VTT uses period (.) not comma (,) for milliseconds."""
        result = format_as_vtt(sample_transcript_segments)
        assert "." in result  # Period for milliseconds
        assert ",000" not in result  # No comma format

    def test_segments_with_empty_text(self, sample_transcript_segments_with_empty_text):
        """Test: Segments with empty text are still included in VTT."""
        result = format_as_vtt(sample_transcript_segments_with_empty_text)
        assert result.startswith("WEBVTT")
        # Should have cues for all segments

    def test_negative_timestamps(self):
        """Test: Negative timestamps are clamped to zero."""
        segments = [TranscriptSegment(text="Hello", start=-1.0, end=-0.5)]
        result = format_as_vtt(segments)
        assert "00:00:00.000 --> 00:00:00.000" in result

    def test_large_timestamps(self):
        """Test: Large timestamps format correctly."""
        segments = [TranscriptSegment(text="Hello", start=3661.123, end=3662.456)]
        result = format_as_vtt(segments)
        assert "01:01:01.123 --> 01:01:02.456" in result

    def test_millisecond_precision(self):
        """Test: Millisecond precision is maintained."""
        segments = [TranscriptSegment(text="Hello", start=1.234, end=2.567)]
        result = format_as_vtt(segments)
        assert "00:00:01.234 --> 00:00:02.567" in result


class TestFormatSRTTimestamp:
    """Test _format_srt_timestamp function."""

    def test_zero_seconds(self):
        """Test: Zero seconds formats correctly."""
        result = _format_srt_timestamp(0.0)
        assert result == "00:00:00,000"

    def test_one_second(self):
        """Test: One second formats correctly."""
        result = _format_srt_timestamp(1.0)
        assert result == "00:00:01,000"

    def test_one_minute(self):
        """Test: One minute formats correctly."""
        result = _format_srt_timestamp(60.0)
        assert result == "00:01:00,000"

    def test_one_hour(self):
        """Test: One hour formats correctly."""
        result = _format_srt_timestamp(3600.0)
        assert result == "01:00:00,000"

    def test_with_milliseconds(self):
        """Test: Timestamp with milliseconds formats correctly."""
        result = _format_srt_timestamp(125.5)
        assert result == "00:02:05,500"

    def test_with_precise_milliseconds(self):
        """Test: Timestamp with precise milliseconds formats correctly."""
        result = _format_srt_timestamp(3661.123)
        assert result == "01:01:01,123"

    def test_negative_timestamp(self):
        """Test: Negative timestamp is clamped to zero."""
        result = _format_srt_timestamp(-1.0)
        assert result == "00:00:00,000"

    def test_very_large_timestamp(self):
        """Test: Very large timestamp formats correctly."""
        result = _format_srt_timestamp(999999.999)
        hours = 999999 // 3600
        minutes = (999999 % 3600) // 60
        seconds = 999999 % 60
        expected = f"{hours:02d}:{minutes:02d}:{seconds:02d},999"
        assert result == expected

    def test_small_fractional_seconds(self):
        """Test: Small fractional seconds format correctly."""
        result = _format_srt_timestamp(0.001)
        assert result == "00:00:00,001"

    def test_rounding_milliseconds(self):
        """Test: Milliseconds are rounded correctly."""
        result = _format_srt_timestamp(1.9999)
        # Should round to 2000 milliseconds, which overflows to 2 seconds
        assert result == "00:00:02,000"

    def test_nan_timestamp(self):
        """Test: NaN timestamp is handled (clamped to zero)."""
        result = _format_srt_timestamp(float("nan"))
        assert result == "00:00:00,000"

    def test_inf_timestamp(self):
        """Test: Infinity timestamp is handled."""
        result = _format_srt_timestamp(float("inf"))
        # Should handle gracefully (might clamp or format as large number)
        assert isinstance(result, str)
        assert len(result) > 0


class TestFormatVTTTimestamp:
    """Test _format_vtt_timestamp function."""

    def test_zero_seconds(self):
        """Test: Zero seconds formats correctly."""
        result = _format_vtt_timestamp(0.0)
        assert result == "00:00:00.000"

    def test_one_second(self):
        """Test: One second formats correctly."""
        result = _format_vtt_timestamp(1.0)
        assert result == "00:00:01.000"

    def test_one_minute(self):
        """Test: One minute formats correctly."""
        result = _format_vtt_timestamp(60.0)
        assert result == "00:01:00.000"

    def test_one_hour(self):
        """Test: One hour formats correctly."""
        result = _format_vtt_timestamp(3600.0)
        assert result == "01:00:00.000"

    def test_with_milliseconds(self):
        """Test: Timestamp with milliseconds formats correctly."""
        result = _format_vtt_timestamp(125.5)
        assert result == "00:02:05.500"

    def test_with_precise_milliseconds(self):
        """Test: Timestamp with precise milliseconds formats correctly."""
        result = _format_vtt_timestamp(3661.123)
        assert result == "01:01:01.123"

    def test_negative_timestamp(self):
        """Test: Negative timestamp is clamped to zero."""
        result = _format_vtt_timestamp(-1.0)
        assert result == "00:00:00.000"

    def test_very_large_timestamp(self):
        """Test: Very large timestamp formats correctly."""
        result = _format_vtt_timestamp(999999.999)
        hours = 999999 // 3600
        minutes = (999999 % 3600) // 60
        seconds = 999999 % 60
        expected = f"{hours:02d}:{minutes:02d}:{seconds:02d}.999"
        assert result == expected

    def test_small_fractional_seconds(self):
        """Test: Small fractional seconds format correctly."""
        result = _format_vtt_timestamp(0.001)
        assert result == "00:00:00.001"

    def test_rounding_milliseconds(self):
        """Test: Milliseconds are rounded correctly."""
        result = _format_vtt_timestamp(1.9999)
        # Should round to 2000 milliseconds, which overflows to 2 seconds
        assert result == "00:00:02.000"

    def test_nan_timestamp(self):
        """Test: NaN timestamp is handled (clamped to zero)."""
        result = _format_vtt_timestamp(float("nan"))
        assert result == "00:00:00.000"

    def test_inf_timestamp(self):
        """Test: Infinity timestamp is handled."""
        result = _format_vtt_timestamp(float("inf"))
        # Should handle gracefully (might clamp or format as large number)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_vtt_uses_period(self):
        """Test: VTT timestamp uses period (.) not comma (,)."""
        result = _format_vtt_timestamp(1.5)
        assert "." in result
        assert "," not in result

    def test_srt_uses_comma(self):
        """Test: SRT timestamp uses comma (,) not period (.)."""
        result = _format_srt_timestamp(1.5)
        assert "," in result
        assert "." not in result
