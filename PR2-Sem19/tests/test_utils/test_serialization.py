"""
Unit tests for serialization utilities.

Tests cover:
- Happy path scenarios (simple and nested dictionaries)
- Edge cases (empty structures, mixed types)
- Error conditions (invalid inputs)
- Boundary value analysis (deep nesting, large structures)
"""

from app.utils.serialization import convert_to_camel_case


class TestConvertToCamelCase:
    """Test convert_to_camel_case function."""

    # Happy Path Tests - Simple Dictionaries
    def test_simple_dict_single_key(self):
        """Test: Simple dictionary with one key converts correctly."""
        data = {"job_id": "123"}
        result = convert_to_camel_case(data)
        assert result == {"jobId": "123"}

    def test_simple_dict_multiple_keys(self):
        """Test: Simple dictionary with multiple keys converts correctly."""
        data = {"job_id": "123", "created_at": "2024-01-01", "video_id": "abc"}
        result = convert_to_camel_case(data)
        assert result == {
            "jobId": "123",
            "createdAt": "2024-01-01",
            "videoId": "abc",
        }

    def test_dict_with_all_mapped_keys(self):
        """Test: Dictionary with all mapped keys converts correctly."""
        data = {
            "job_id": "123",
            "created_at": "2024-01-01",
            "completed_at": "2024-01-02",
            "video_id": "abc",
            "video_url": "https://example.com",
            "translate_to": "en",
            "result_id": "456",
            "result_ref": "ref123",
        }
        result = convert_to_camel_case(data)
        assert result == {
            "jobId": "123",
            "createdAt": "2024-01-01",
            "completedAt": "2024-01-02",
            "videoId": "abc",
            "videoUrl": "https://example.com",
            "translateTo": "en",
            "resultId": "456",
            "resultRef": "ref123",
        }

    def test_dict_with_unmapped_keys(self):
        """Test: Dictionary with unmapped keys leaves them unchanged."""
        data = {"job_id": "123", "status": "completed", "custom_field": "value"}
        result = convert_to_camel_case(data)
        assert result == {"jobId": "123", "status": "completed", "custom_field": "value"}

    # Happy Path Tests - Nested Structures
    def test_nested_dict(self):
        """Test: Nested dictionary converts recursively."""
        data = {
            "job_id": "123",
            "result": {"video_id": "abc", "created_at": "2024-01-01"},
        }
        result = convert_to_camel_case(data)
        assert result == {
            "jobId": "123",
            "result": {"videoId": "abc", "createdAt": "2024-01-01"},
        }

    def test_deeply_nested_dict(self):
        """Test: Deeply nested dictionary converts recursively."""
        data = {
            "job_id": "123",
            "metadata": {
                "video": {"video_id": "abc", "video_url": "https://example.com"},
                "timing": {"created_at": "2024-01-01", "completed_at": "2024-01-02"},
            },
        }
        result = convert_to_camel_case(data)
        assert result == {
            "jobId": "123",
            "metadata": {
                "video": {"videoId": "abc", "videoUrl": "https://example.com"},
                "timing": {"createdAt": "2024-01-01", "completedAt": "2024-01-02"},
            },
        }

    def test_list_of_dicts(self):
        """Test: List of dictionaries converts each item."""
        data = [
            {"job_id": "123", "created_at": "2024-01-01"},
            {"job_id": "456", "created_at": "2024-01-02"},
        ]
        result = convert_to_camel_case(data)
        assert result == [
            {"jobId": "123", "createdAt": "2024-01-01"},
            {"jobId": "456", "createdAt": "2024-01-02"},
        ]

    def test_list_with_nested_dicts(self):
        """Test: List with nested dictionaries converts recursively."""
        data = [
            {"job_id": "123", "result": {"video_id": "abc"}},
            {"job_id": "456", "result": {"video_id": "def"}},
        ]
        result = convert_to_camel_case(data)
        assert result == [
            {"jobId": "123", "result": {"videoId": "abc"}},
            {"jobId": "456", "result": {"videoId": "def"}},
        ]

    def test_mixed_structure(self):
        """Test: Mixed structure with dicts and lists converts correctly."""
        data = {
            "job_id": "123",
            "segments": [
                {"text": "Hello", "start": 0.0, "created_at": "2024-01-01"},
                {"text": "world", "start": 1.0, "created_at": "2024-01-01"},
            ],
            "metadata": {"created_at": "2024-01-01", "video_id": "abc"},
        }
        result = convert_to_camel_case(data)
        assert result == {
            "jobId": "123",
            "segments": [
                {"text": "Hello", "start": 0.0, "createdAt": "2024-01-01"},
                {"text": "world", "start": 1.0, "createdAt": "2024-01-01"},
            ],
            "metadata": {"createdAt": "2024-01-01", "videoId": "abc"},
        }

    # Edge Cases - Primitives
    def test_primitive_string(self):
        """Test: Primitive string returns unchanged."""
        assert convert_to_camel_case("hello") == "hello"

    def test_primitive_int(self):
        """Test: Primitive integer returns unchanged."""
        assert convert_to_camel_case(123) == 123

    def test_primitive_float(self):
        """Test: Primitive float returns unchanged."""
        assert convert_to_camel_case(45.67) == 45.67

    def test_primitive_bool(self):
        """Test: Primitive boolean returns unchanged."""
        assert convert_to_camel_case(True) is True
        assert convert_to_camel_case(False) is False

    def test_primitive_none(self):
        """Test: None returns unchanged."""
        assert convert_to_camel_case(None) is None

    # Edge Cases - Empty Structures
    def test_empty_dict(self):
        """Test: Empty dictionary returns empty dictionary."""
        assert convert_to_camel_case({}) == {}

    def test_empty_list(self):
        """Test: Empty list returns empty list."""
        assert convert_to_camel_case([]) == []

    def test_list_with_empty_dict(self):
        """Test: List with empty dictionary converts correctly."""
        data = [{}]
        result = convert_to_camel_case(data)
        assert result == [{}]

    def test_dict_with_empty_list(self):
        """Test: Dictionary with empty list converts correctly."""
        data = {"job_id": "123", "items": []}
        result = convert_to_camel_case(data)
        assert result == {"jobId": "123", "items": []}

    # Edge Cases - Special Values
    def test_dict_with_none_value(self):
        """Test: Dictionary with None value converts correctly."""
        data = {"job_id": "123", "result": None}
        result = convert_to_camel_case(data)
        assert result == {"jobId": "123", "result": None}

    def test_dict_with_zero_value(self):
        """Test: Dictionary with zero value converts correctly."""
        data = {"job_id": "123", "count": 0}
        result = convert_to_camel_case(data)
        assert result == {"jobId": "123", "count": 0}

    def test_dict_with_false_value(self):
        """Test: Dictionary with False value converts correctly."""
        data = {"job_id": "123", "active": False}
        result = convert_to_camel_case(data)
        assert result == {"jobId": "123", "active": False}

    def test_dict_with_empty_string_value(self):
        """Test: Dictionary with empty string value converts correctly."""
        data = {"job_id": "123", "description": ""}
        result = convert_to_camel_case(data)
        assert result == {"jobId": "123", "description": ""}

    # Boundary Value Tests
    def test_very_large_dict(self):
        """Test: Very large dictionary converts correctly."""
        data = {f"job_id_{i}": f"value_{i}" for i in range(1000)}
        result = convert_to_camel_case(data)
        assert len(result) == 1000
        # Check that mapped keys are converted
        if "job_id_0" in data:
            # Since job_id_0 is not in the mapping, it stays unchanged
            assert "job_id_0" in result or "jobId_0" in result

    def test_very_deep_nesting(self):
        """Test: Very deep nesting converts correctly."""
        data = {"level1": {"level2": {"level3": {"level4": {"job_id": "123"}}}}}
        result = convert_to_camel_case(data)
        assert result["level1"]["level2"]["level3"]["level4"]["jobId"] == "123"

    def test_list_with_many_items(self):
        """Test: List with many items converts correctly."""
        data = [{"job_id": str(i), "created_at": "2024-01-01"} for i in range(100)]
        result = convert_to_camel_case(data)
        assert len(result) == 100
        assert result[0]["jobId"] == "0"
        assert result[99]["jobId"] == "99"

    # Additional Tests
    def test_dict_with_mixed_value_types(self):
        """Test: Dictionary with mixed value types converts correctly."""
        data = {
            "job_id": "123",
            "count": 42,
            "price": 99.99,
            "active": True,
            "tags": ["tag1", "tag2"],
            "metadata": {"key": "value"},
        }
        result = convert_to_camel_case(data)
        assert result["jobId"] == "123"
        assert result["count"] == 42
        assert result["price"] == 99.99
        assert result["active"] is True
        assert result["tags"] == ["tag1", "tag2"]
        assert result["metadata"] == {"key": "value"}

    def test_dict_with_unicode_keys(self):
        """Test: Dictionary with unicode keys (not in mapping) stays unchanged."""
        data = {"job_id": "123", "ключ": "значение"}
        result = convert_to_camel_case(data)
        assert result["jobId"] == "123"
        assert result["ключ"] == "значение"

    def test_dict_with_special_characters_in_unmapped_keys(self):
        """Test: Dictionary with special characters in unmapped keys stays unchanged."""
        data = {"job_id": "123", "key-with-dash": "value", "key_with_underscore": "value"}
        result = convert_to_camel_case(data)
        assert result["jobId"] == "123"
        assert result["key-with-dash"] == "value"
        assert result["key_with_underscore"] == "value"

    def test_preserves_order(self):
        """Test: Dictionary key order is preserved (Python 3.7+)."""
        data = {"job_id": "123", "created_at": "2024-01-01", "video_id": "abc"}
        result = convert_to_camel_case(data)
        keys = list(result.keys())
        # Order should be preserved
        assert keys[0] == "jobId"
        assert keys[1] == "createdAt"
        assert keys[2] == "videoId"

    def test_nested_list_with_dicts(self):
        """Test: Nested list with dictionaries converts correctly."""
        data = {
            "jobs": [
                [{"job_id": "123", "created_at": "2024-01-01"}],
                [{"job_id": "456", "created_at": "2024-01-02"}],
            ]
        }
        result = convert_to_camel_case(data)
        assert result["jobs"][0][0]["jobId"] == "123"
        assert result["jobs"][1][0]["jobId"] == "456"
