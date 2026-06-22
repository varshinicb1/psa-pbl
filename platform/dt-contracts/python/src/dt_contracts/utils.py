"""
Shared utility functions for the Grid Digital Twin.

Consolidates duplicate functions from multiple modules to reduce code duplication.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict


def stable_hash(data: Dict[str, Any]) -> str:
    """
    Generate a stable hash of a dictionary.

    Useful for comparing snapshots or tracking changes.

    Args:
        data: Dictionary to hash

    Returns:
        Hexadecimal hash string
    """
    json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(json_str.encode()).hexdigest()


def utc_now_iso() -> str:
    """
    Get current UTC time as ISO 8601 string.

    Returns:
        ISO 8601 formatted timestamp
    """
    return datetime.now(timezone.utc).isoformat()


def validate_bounds(value: float, min_bound: float, max_bound: float, name: str = "value") -> bool:
    """
    Validate that a value is within bounds.

    Args:
        value: Value to check
        min_bound: Lower bound (inclusive)
        max_bound: Upper bound (inclusive)
        name: Name for error messages

    Returns:
        True if within bounds

    Raises:
        ValueError: If out of bounds
    """
    if not (min_bound <= value <= max_bound):
        raise ValueError(
            f"{name} {value} out of bounds [{min_bound}, {max_bound}]"
        )
    return True


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers.

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Value to return if denominator is zero

    Returns:
        Result of division or default
    """
    try:
        if abs(denominator) < 1e-12:  # Near-zero check
            return default
        return numerator / denominator
    except (ZeroDivisionError, TypeError):
        return default
