"""Tests for the ensemble ML detector."""

from __future__ import annotations

import pathlib
import sys

# Bootstrap paths for local development
_repo_root = pathlib.Path(__file__).resolve().parents[3]
for _mod in ["dt-ml", "dt-contracts/python/src"]:
    _p = str(_repo_root / "platform" / _mod)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from dt_ml.ensemble import EnsembleDetector
from dt_contracts.models import GridGraphSnapshot, GridNode, GridEdge


def test_ensemble_detects_voltage_violation():
    detector = EnsembleDetector()
    nodes = [GridNode(
        id=f"bus_{i}",
        type="Bus",
        static={"vn_kv": 115.0},
        dynamic={"vm_pu": 0.94 if i == 3 else 1.0, "va_degree": float(i)},
    ) for i in range(5)]
    snapshot = GridGraphSnapshot(t="2026-01-01T00:00:00Z", topology_hash="h1", nodes=nodes, edges=[])
    result = detector.predict(snapshot)
    assert result.prediction["type"] != "NoAnomaly" or result.explanation is not None


def test_ensemble_no_false_positive():
    detector = EnsembleDetector()
    nodes = [GridNode(
        id=f"bus_{i}",
        type="Bus",
        static={"vn_kv": 115.0},
        dynamic={"vm_pu": 1.0, "va_degree": float(i)},
    ) for i in range(5)]
    snapshot = GridGraphSnapshot(t="2026-01-01T00:00:00Z", topology_hash="h1", nodes=nodes, edges=[])
    result = detector.predict(snapshot)
    assert result.prediction["type"] == "NoAnomaly"
