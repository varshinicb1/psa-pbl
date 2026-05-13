from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict


def load_schema(schema_filename: str) -> Dict[str, Any]:
    """
    Load a JSON Schema packaged with dt-contracts.

    Parameters
    ----------
    schema_filename:
        One of: gridgraph.schema.json, telemetry.schema.json, actions.schema.json, explanations.schema.json
    """
    with resources.files("dt_contracts.schemas").joinpath(schema_filename).open("r", encoding="utf-8") as f:
        return json.load(f)

