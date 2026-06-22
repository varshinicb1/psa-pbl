"""Tests for CIM (Common Information Model) adapter."""

from __future__ import annotations

import pathlib
import sys

# Bootstrap paths for local development
_repo_root = pathlib.Path(__file__).resolve().parents[3]
for _mod in ["dt-cim/src", "dt-contracts/python/src"]:
    _p = str(_repo_root / "platform" / _mod)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from dt_cim.adapter import CIMAdapter, CIMConfig


class TestCIMAdapter:
    def test_simulated_topology(self):
        adapter = CIMAdapter()
        topo = adapter.get_bangalore_substations()
        assert len(topo) >= 2
        assert any("Bangalore" in s.name for s in topo)

    def test_cim_config(self):
        config = CIMConfig(utility="BESCOM", region="South")
        adapter = CIMAdapter(config)
        assert adapter.config.utility == "BESCOM"

    def test_to_grid_graph(self):
        adapter = CIMAdapter()
        graph = adapter.to_grid_graph()
        assert graph["utility"] == "BESCOM"
        assert len(graph["substations"]) > 0
