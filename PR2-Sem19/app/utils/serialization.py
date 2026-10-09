"""Serialization utilities for converting data formats."""

from typing import Any

_CAMEL_CASE_MAP = {
    "job_id": "jobId",
    "created_at": "createdAt",
    "completed_at": "completedAt",
    "video_id": "videoId",
    "video_url": "videoUrl",
    "translate_to": "translateTo",
    "result_id": "resultId",
    "result_ref": "resultRef",
}


def convert_to_camel_case(data: Any) -> Any:
    """Convert dictionary keys from snake_case to camelCase based on Pydantic aliases.

    Recursively converts nested dictionaries and lists.
    Maps common field names to their camelCase equivalents using dictionary lookup
    for O(1) performance.

    Args:
        data: Dictionary, list, or primitive value to convert.
            If dict: converts all keys recursively.
            If list: converts all items recursively.
            If primitive: returns unchanged.

    Returns:
        Any: Converted data with camelCase keys. Type matches input:
            - dict -> dict (with camelCase keys)
            - list -> list (with converted items)
            - primitive -> unchanged

    Example:
        >>> convert_to_camel_case({"job_id": "123", "created_at": "2024-01-01"})
        {'jobId': '123', 'createdAt': '2024-01-01'}
        >>> convert_to_camel_case([{"video_id": "abc"}])
        [{'videoId': 'abc'}]
    """
    if isinstance(data, dict):
        converted = {}
        for key, value in data.items():
            camel_key = _CAMEL_CASE_MAP.get(key, key)
            converted[camel_key] = convert_to_camel_case(value)
        return converted
    elif isinstance(data, list):
        return [convert_to_camel_case(item) for item in data]
    else:
        return data
