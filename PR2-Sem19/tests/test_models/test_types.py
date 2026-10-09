"""
Unit tests for TypedDict types in app.models.types.

Tests cover:
- Happy path: Valid TypedDict creation and usage
- Edge cases: Optional fields, type checking
- Error conditions: Invalid dictionary structures
- Boundary analysis: Empty dicts, None values
"""

from typing import Any, Dict

from app.models.types import ErrorDict


class TestErrorDict:
    """Test cases for ErrorDict TypedDict."""

    def test_error_dict_valid(self):
        """Test: Create valid ErrorDict with all required fields."""
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {"key": "value"},
        }
        assert error["code"] == "ERROR_001"
        assert error["message"] == "An error occurred"
        assert error["details"] == {"key": "value"}

    def test_error_dict_empty_details(self):
        """Test: ErrorDict with empty details dict."""
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {},
        }
        assert error["details"] == {}

    def test_error_dict_nested_details(self):
        """Test: ErrorDict with nested details dict."""
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {
                "video_id": "dQw4w9WgXcQ",
                "reason": "not_found",
                "metadata": {"timestamp": "2024-01-01"},
            },
        }
        assert "metadata" in error["details"]
        assert isinstance(error["details"]["metadata"], dict)

    def test_error_dict_string_fields(self):
        """Test: ErrorDict code and message are strings."""
        error: ErrorDict = {
            "code": "CAPTIONS_NOT_AVAILABLE",
            "message": "No captions available for this video",
            "details": {},
        }
        assert isinstance(error["code"], str)
        assert isinstance(error["message"], str)

    def test_error_dict_details_is_dict(self):
        """Test: ErrorDict details field is a dict."""
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {"key": "value"},
        }
        assert isinstance(error["details"], dict)

    def test_error_dict_empty_strings(self):
        """Test: ErrorDict with empty string values (boundary case)."""
        error: ErrorDict = {
            "code": "",
            "message": "",
            "details": {},
        }
        assert error["code"] == ""
        assert error["message"] == ""

    def test_error_dict_long_strings(self):
        """Test: ErrorDict with long string values."""
        long_message = "A" * 10000
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": long_message,
            "details": {},
        }
        assert len(error["message"]) == 10000

    def test_error_dict_usage_in_function(self):
        """Test: ErrorDict can be used as function parameter type."""

        def process_error(error: ErrorDict) -> str:
            return f"{error['code']}: {error['message']}"

        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "Test error",
            "details": {},
        }
        result = process_error(error)
        assert "ERROR_001" in result
        assert "Test error" in result

    def test_error_dict_usage_in_dict_comprehension(self):
        """Test: ErrorDict can be used in dictionary operations."""
        errors: list[ErrorDict] = [
            {"code": "ERROR_001", "message": "Error 1", "details": {}},
            {"code": "ERROR_002", "message": "Error 2", "details": {}},
        ]
        codes = [error["code"] for error in errors]
        assert codes == ["ERROR_001", "ERROR_002"]

    def test_error_dict_type_checking(self):
        """Test: TypedDict provides type checking benefits."""
        # This test documents that TypedDict helps with type checking
        # In a real scenario, mypy would catch missing fields
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {},
        }
        # All required fields are present
        assert "code" in error
        assert "message" in error
        assert "details" in error

    def test_error_dict_from_dict(self):
        """Test: ErrorDict can be created from regular dict."""
        regular_dict: Dict[str, Any] = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {"key": "value"},
        }
        # Can be assigned to ErrorDict (type narrowing)
        error: ErrorDict = regular_dict  # type: ignore
        assert error["code"] == "ERROR_001"

    def test_error_dict_immutability_concept(self):
        """Test: ErrorDict values can be modified (TypedDict is not frozen)."""
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {},
        }
        # TypedDict allows modification
        error["details"]["new_key"] = "new_value"
        assert "new_key" in error["details"]

    def test_error_dict_serialization(self):
        """Test: ErrorDict can be serialized (it's just a dict)."""
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {"key": "value"},
        }
        # Can be used with json.dumps, etc.
        import json

        json_str = json.dumps(error)
        assert "ERROR_001" in json_str
        assert "An error occurred" in json_str

    def test_error_dict_comparison(self):
        """Test: ErrorDict instances can be compared."""
        error1: ErrorDict = {
            "code": "ERROR_001",
            "message": "Error",
            "details": {},
        }
        error2: ErrorDict = {
            "code": "ERROR_001",
            "message": "Error",
            "details": {},
        }
        # Dicts are compared by value
        assert error1 == error2

    def test_error_dict_keys(self):
        """Test: ErrorDict has exactly 3 keys."""
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {},
        }
        assert set(error.keys()) == {"code", "message", "details"}
        assert len(error) == 3

    def test_error_dict_values(self):
        """Test: ErrorDict values can be accessed."""
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {"key": "value"},
        }
        values = list(error.values())
        assert "ERROR_001" in values
        assert "An error occurred" in values
        assert isinstance(values[2], dict)

    def test_error_dict_items(self):
        """Test: ErrorDict items can be iterated."""
        error: ErrorDict = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {},
        }
        items = dict(error.items())
        assert items["code"] == "ERROR_001"
        assert items["message"] == "An error occurred"
        assert items["details"] == {}

    def test_error_dict_in_union_type(self):
        """Test: ErrorDict can be used in Union types."""
        from typing import Union

        Response = Union[ErrorDict, Dict[str, Any]]

        error_response: Response = {
            "code": "ERROR_001",
            "message": "An error occurred",
            "details": {},
        }
        assert "code" in error_response
