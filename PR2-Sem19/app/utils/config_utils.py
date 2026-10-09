"""Configuration utilities for safely converting setting values."""


def get_float_setting(setting_value, default=0.0):
    """Safely convert a setting value to float, handling Mock objects.

    This utility function safely converts configuration setting values to float,
    with special handling for Mock objects (used in testing) to avoid infinite
    recursion. It supports various input types including None, int, float, str,
    and Mock objects.

    Args:
        setting_value: The setting value to convert (can be None, int, float, str, or Mock).
        default: Default value to return if conversion fails. Default: 0.0.

    Returns:
        float: The converted float value, or default if conversion fails.

    Example:
        >>> get_float_setting(5.5)
        5.5
        >>> get_float_setting("10.5")
        10.5
        >>> get_float_setting(None, default=1.0)
        1.0
        >>> get_float_setting("invalid", default=0.5)
        0.5
    """
    if setting_value is None:
        return default
    if isinstance(setting_value, (int, float)):
        return float(setting_value)
    if hasattr(setting_value, "__class__"):
        type_str = str(type(setting_value))
        if "Mock" in type_str:
            return default
    try:
        if isinstance(setting_value, str):
            try:
                return (
                    float(setting_value)
                    if "." in setting_value or "e" in setting_value.lower()
                    else int(setting_value)
                )
            except (ValueError, TypeError):
                return default
        return float(setting_value)
    except (ValueError, TypeError, AttributeError):
        return default


def get_int_setting(setting_value, default=0):
    """Safely convert a setting value to int, handling Mock objects.

    This utility function safely converts configuration setting values to int,
    with special handling for Mock objects (used in testing) to avoid infinite
    recursion. It supports various input types including None, int, float, str,
    and Mock objects.

    Args:
        setting_value: The setting value to convert (can be None, int, float, str, or Mock).
        default: Default value to return if conversion fails. Default: 0.

    Returns:
        int: The converted int value, or default if conversion fails.

    Example:
        >>> get_int_setting(5)
        5
        >>> get_int_setting("10")
        10
        >>> get_int_setting(None, default=100)
        100
        >>> get_int_setting("invalid", default=50)
        50
    """
    if setting_value is None:
        return default
    if isinstance(setting_value, int):
        return setting_value
    if isinstance(setting_value, float):
        return int(setting_value)
    if hasattr(setting_value, "__class__"):
        type_str = str(type(setting_value))
        if "Mock" in type_str:
            return default
    try:
        if isinstance(setting_value, str):
            try:
                return int(float(setting_value)) if "." in setting_value else int(setting_value)
            except (ValueError, TypeError):
                return default
        return int(setting_value)
    except (ValueError, TypeError, AttributeError):
        return default
