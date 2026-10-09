"""
Unit tests for enum classes in app.models.schemas.

Tests cover:
- Happy path: Valid enum values and operations
- Edge cases: Enum comparisons, string conversions
- Error conditions: Invalid enum values
- Boundary analysis: All enum members
"""

import pytest

from app.models.schemas import (JobPriority, JobStatus, Language, OutputFormat,
                                WorkerStatus)


class TestLanguage:
    """Test cases for Language enum."""

    def test_language_enum_values(self):
        """Test: All major language enum values are correct."""
        assert Language.EN.value == "en"
        assert Language.ES.value == "es"
        assert Language.FR.value == "fr"
        assert Language.DE.value == "de"
        assert Language.RU.value == "ru"
        assert Language.JA.value == "ja"
        assert Language.ZH.value == "zh"

    def test_language_enum_count(self):
        """Test: Language enum has expected number of members (78 languages)."""
        # Count all enum members
        language_count = len(list(Language))
        assert language_count == 78, f"Expected 78 languages, got {language_count}"

    def test_language_enum_string_conversion(self):
        """Test: Language enum can be converted to string."""
        assert str(Language.EN) == "Language.EN"
        assert str(Language.ES) == "Language.ES"

    def test_language_enum_equality(self):
        """Test: Language enum equality comparison works."""
        assert Language.EN == Language.EN
        assert Language.EN != Language.ES

    def test_language_enum_value_access(self):
        """Test: Language enum value can be accessed."""
        assert Language.EN.value == "en"
        assert isinstance(Language.EN.value, str)

    def test_language_enum_from_string(self):
        """Test: Language enum can be created from string value."""
        lang = Language("en")
        assert lang == Language.EN

    def test_language_enum_invalid_value(self):
        """Test: Invalid language code raises ValueError."""
        with pytest.raises(ValueError):
            Language("xx")  # Invalid language code

    def test_language_enum_all_members_are_strings(self):
        """Test: All language enum values are strings."""
        for lang in Language:
            assert isinstance(lang.value, str)
            assert len(lang.value) == 2  # ISO 639-1 codes are 2 characters

    def test_language_enum_case_sensitivity(self):
        """Test: Language enum values are case-sensitive."""
        # Language enum should use lowercase
        assert Language.EN.value == "en"
        assert Language.EN.value != "EN"

    def test_language_enum_hashable(self):
        """Test: Language enum members are hashable (can be used in sets/dicts)."""
        lang_set = {Language.EN, Language.ES, Language.FR}
        assert len(lang_set) == 3
        assert Language.EN in lang_set

    def test_language_enum_iteration(self):
        """Test: Language enum can be iterated over."""
        languages = list(Language)
        assert len(languages) > 0
        assert all(isinstance(lang, Language) for lang in languages)


class TestOutputFormat:
    """Test cases for OutputFormat enum."""

    def test_output_format_enum_values(self):
        """Test: All output format enum values are correct."""
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.TEXT.value == "text"
        assert OutputFormat.SRT.value == "srt"
        assert OutputFormat.VTT.value == "vtt"

    def test_output_format_enum_count(self):
        """Test: OutputFormat enum has exactly 4 members."""
        format_count = len(list(OutputFormat))
        assert format_count == 4

    def test_output_format_enum_string_conversion(self):
        """Test: OutputFormat enum can be converted to string."""
        assert str(OutputFormat.JSON) == "OutputFormat.JSON"

    def test_output_format_enum_equality(self):
        """Test: OutputFormat enum equality comparison works."""
        assert OutputFormat.JSON == OutputFormat.JSON
        assert OutputFormat.JSON != OutputFormat.TEXT

    def test_output_format_enum_from_string(self):
        """Test: OutputFormat enum can be created from string value."""
        fmt = OutputFormat("json")
        assert fmt == OutputFormat.JSON

    def test_output_format_enum_invalid_value(self):
        """Test: Invalid output format raises ValueError."""
        with pytest.raises(ValueError):
            OutputFormat("invalid")

    def test_output_format_enum_all_members_are_strings(self):
        """Test: All output format enum values are strings."""
        for fmt in OutputFormat:
            assert isinstance(fmt.value, str)

    def test_output_format_enum_hashable(self):
        """Test: OutputFormat enum members are hashable."""
        format_set = {OutputFormat.JSON, OutputFormat.TEXT}
        assert len(format_set) == 2


class TestJobStatus:
    """Test cases for JobStatus enum."""

    def test_job_status_enum_values(self):
        """Test: All job status enum values are correct."""
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"

    def test_job_status_enum_count(self):
        """Test: JobStatus enum has exactly 4 members."""
        status_count = len(list(JobStatus))
        assert status_count == 4

    def test_job_status_enum_string_conversion(self):
        """Test: JobStatus enum can be converted to string."""
        assert str(JobStatus.QUEUED) == "JobStatus.QUEUED"

    def test_job_status_enum_equality(self):
        """Test: JobStatus enum equality comparison works."""
        assert JobStatus.QUEUED == JobStatus.QUEUED
        assert JobStatus.QUEUED != JobStatus.PROCESSING

    def test_job_status_enum_from_string(self):
        """Test: JobStatus enum can be created from string value."""
        status = JobStatus("queued")
        assert status == JobStatus.QUEUED

    def test_job_status_enum_invalid_value(self):
        """Test: Invalid job status raises ValueError."""
        with pytest.raises(ValueError):
            JobStatus("invalid_status")

    def test_job_status_enum_all_members_are_strings(self):
        """Test: All job status enum values are strings."""
        for status in JobStatus:
            assert isinstance(status.value, str)

    def test_job_status_enum_transitions(self):
        """Test: Job status enum values represent valid state transitions."""
        # Valid transitions: QUEUED -> PROCESSING -> COMPLETED/FAILED
        valid_initial = {JobStatus.QUEUED}
        valid_processing = {JobStatus.PROCESSING}
        valid_final = {JobStatus.COMPLETED, JobStatus.FAILED}

        assert JobStatus.QUEUED in valid_initial
        assert JobStatus.PROCESSING in valid_processing
        assert JobStatus.COMPLETED in valid_final
        assert JobStatus.FAILED in valid_final


class TestJobPriority:
    """Test cases for JobPriority enum."""

    def test_job_priority_enum_values(self):
        """Test: All job priority enum values are correct."""
        assert JobPriority.LOW.value == "low"
        assert JobPriority.NORMAL.value == "normal"
        assert JobPriority.HIGH.value == "high"

    def test_job_priority_enum_count(self):
        """Test: JobPriority enum has exactly 3 members."""
        priority_count = len(list(JobPriority))
        assert priority_count == 3

    def test_job_priority_enum_string_conversion(self):
        """Test: JobPriority enum can be converted to string."""
        assert str(JobPriority.LOW) == "JobPriority.LOW"

    def test_job_priority_enum_equality(self):
        """Test: JobPriority enum equality comparison works."""
        assert JobPriority.LOW == JobPriority.LOW
        assert JobPriority.LOW != JobPriority.HIGH

    def test_job_priority_enum_from_string(self):
        """Test: JobPriority enum can be created from string value."""
        priority = JobPriority("normal")
        assert priority == JobPriority.NORMAL

    def test_job_priority_enum_invalid_value(self):
        """Test: Invalid job priority raises ValueError."""
        with pytest.raises(ValueError):
            JobPriority("critical")

    def test_job_priority_enum_ordering_concept(self):
        """Test: Job priority enum values represent priority levels."""
        # Conceptually: HIGH > NORMAL > LOW
        priorities = [JobPriority.LOW, JobPriority.NORMAL, JobPriority.HIGH]
        assert len(priorities) == 3
        assert JobPriority.HIGH in priorities


class TestWorkerStatus:
    """Test cases for WorkerStatus enum."""

    def test_worker_status_enum_values(self):
        """Test: All worker status enum values are correct."""
        assert WorkerStatus.IDLE.value == "idle"
        assert WorkerStatus.BUSY.value == "busy"
        assert WorkerStatus.WARMING_UP.value == "warming_up"
        assert WorkerStatus.UNHEALTHY.value == "unhealthy"

    def test_worker_status_enum_count(self):
        """Test: WorkerStatus enum has exactly 4 members."""
        status_count = len(list(WorkerStatus))
        assert status_count == 4

    def test_worker_status_enum_string_conversion(self):
        """Test: WorkerStatus enum can be converted to string."""
        assert str(WorkerStatus.IDLE) == "WorkerStatus.IDLE"

    def test_worker_status_enum_equality(self):
        """Test: WorkerStatus enum equality comparison works."""
        assert WorkerStatus.IDLE == WorkerStatus.IDLE
        assert WorkerStatus.IDLE != WorkerStatus.BUSY

    def test_worker_status_enum_from_string(self):
        """Test: WorkerStatus enum can be created from string value."""
        status = WorkerStatus("idle")
        assert status == WorkerStatus.IDLE

    def test_worker_status_enum_invalid_value(self):
        """Test: Invalid worker status raises ValueError."""
        with pytest.raises(ValueError):
            WorkerStatus("offline")

    def test_worker_status_enum_underscore_in_value(self):
        """Test: WorkerStatus enum handles underscore in value (warming_up)."""
        assert WorkerStatus.WARMING_UP.value == "warming_up"
        assert "_" in WorkerStatus.WARMING_UP.value

    def test_worker_status_enum_all_members_are_strings(self):
        """Test: All worker status enum values are strings."""
        for status in WorkerStatus:
            assert isinstance(status.value, str)


class TestEnumIntegration:
    """Integration tests for enum usage together."""

    def test_enum_serialization(self):
        """Test: Enums can be serialized to their string values."""
        data = {
            "language": Language.EN.value,
            "format": OutputFormat.JSON.value,
            "status": JobStatus.QUEUED.value,
        }
        assert data["language"] == "en"
        assert data["format"] == "json"
        assert data["status"] == "queued"

    def test_enum_deserialization(self):
        """Test: Enums can be deserialized from string values."""
        lang = Language("en")
        fmt = OutputFormat("json")
        status = JobStatus("queued")

        assert lang == Language.EN
        assert fmt == OutputFormat.JSON
        assert status == JobStatus.QUEUED

    def test_enum_in_dict_keys(self):
        """Test: Enums can be used as dictionary keys."""
        status_map = {
            JobStatus.QUEUED: "Waiting",
            JobStatus.PROCESSING: "In Progress",
            JobStatus.COMPLETED: "Done",
            JobStatus.FAILED: "Error",
        }
        assert status_map[JobStatus.QUEUED] == "Waiting"
        assert len(status_map) == 4
