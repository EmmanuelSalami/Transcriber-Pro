"""Type definitions for type guards and type narrowing."""

from typing import TypedDict


class ErrorDict(TypedDict):
    """TypedDict for error response dictionaries.

    Used for type narrowing when checking if a dictionary is an error response.
    This improves type checking and makes code more maintainable.

    Attributes:
        code (str): Error code for programmatic error handling.
        message (str): Human-readable error message.
        details (dict): Additional error details dictionary.
    """

    code: str
    message: str
    details: dict
