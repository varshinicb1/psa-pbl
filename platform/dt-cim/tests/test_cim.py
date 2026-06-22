"""Tests for CIM (Common Information Model) adapter."""
from __future__ import annotations

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
