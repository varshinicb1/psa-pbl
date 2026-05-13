from __future__ import annotations

from typing import Any, Dict, Optional

from jsonschema import Draft202012Validator

from .schema_loader import load_schema


def validate_against_schema(payload: Dict[str, Any], schema_filename: str, *, schema: Optional[Dict[str, Any]] = None) -> None:
    """
    Validate a payload against a packaged JSON Schema.

    Raises jsonschema.ValidationError on failures.
    """
    schema_obj = schema if schema is not None else load_schema(schema_filename)
    Draft202012Validator(schema_obj).validate(payload)

