"""Tests for BESCOM network model and simulation."""

from __future__ import annotations

import pathlib
import sys

# Bootstrap paths for local development
_repo_root = pathlib.Path(__file__).resolve().parents[3]
for _mod in ["dt-bescom/src", "dt-contracts/python/src", "dt-sim-pandapower"]:
    _p = str(_repo_root / "platform" / _mod)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from datetime import datetime, timezone
from dt_bescom.network_model import (
    build_bescom_network,
    BESCOMNetworkConfig,
    describe_network,
    BANGALORE_400KV_SUBSTATIONS,
    BANGALORE_220KV_SUBSTATIONS,
    BANGALORE_66KV_SUBSTATIONS,
)
from dt_bescom.load_profiles import (
    BESCOMLoadProfile,
    get_bangalore_daily_load_curve,
)
from dt_bescom.simulation import BESCOMSimulator


class TestNetworkModel:
    def test_build_full_network(self):
        net = build_bescom_network()
        assert len(net.bus) > 0
        assert len(net.line) > 0
        assert len(net.trafo) > 0
        assert len(net.load) > 0
        assert len(net.ext_grid) > 0

    def test_build_400kv_only(self):
        config = BESCOMNetworkConfig(include_220kv=False, include_66kv=False)
        net = build_bescom_network(config)
        assert len(net.bus) == len(BANGALORE_400KV_SUBSTATIONS)

    def test_build_220kv_only(self):
        config = BESCOMNetworkConfig(include_400kv=False, include_66kv=False)
        net = build_bescom_network(config)
        assert len(net.bus) == len(BANGALORE_220KV_SUBSTATIONS)

    def test_build_66kv_only(self):
        config = BESCOMNetworkConfig(include_400kv=False, include_220kv=False)
        net = build_bescom_network(config)
        assert len(net.bus) == len(BANGALORE_66KV_SUBSTATIONS)

    def test_describe(self):
        net = build_bescom_network()
        desc = describe_network(net)
        assert "BESCOM Bangalore" in desc
        assert "Buses:" in desc

    def test_substation_counts(self):
        assert len(BANGALORE_400KV_SUBSTATIONS) == 5
        assert len(BANGALORE_220KV_SUBSTATIONS) == 15
        assert len(BANGALORE_66KV_SUBSTATIONS) == 30


class TestLoadProfile:
    def test_daily_curve_has_24h(self):
        for h in range(24):
            factor = get_bangalore_daily_load_curve(h)
            assert 0.3 <= factor <= 1.0

    def test_load_profile_generates(self):
        prof = BESCOMLoadProfile()
        load = prof.get_current_load_mw(datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc))
        assert 2000 < load < 9500

    def test_season_detection(self):
        prof = BESCOMLoadProfile()
        assert prof.get_season(1) == "winter"
        assert prof.get_season(4) == "summer"
        assert prof.get_season(7) == "monsoon"
        assert prof.get_season(10) == "post_monsoon"


class TestSimulator:
    def test_simulator_initializes(self):
        sim = BESCOMSimulator()
        assert sim is not None

    def test_run_powerflow_converges(self):
        sim = BESCOMSimulator()
        result = sim.run_powerflow(datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc))
        assert result["converged"] is True
        assert result["total_load_mw"] > 0
        assert len(result["vm_pu"]) > 0

    def test_get_topology(self):
        sim = BESCOMSimulator()
        topo = sim.get_topology_snapshot()
        assert len(topo["nodes"]) > 0
        assert len(topo["edges"]) > 0
        assert "topology_hash" in topo

    def test_to_grid_graph_snapshot(self):
        sim = BESCOMSimulator()
        snap = sim.to_grid_graph_snapshot(tick_count=1)
        assert snap is not None
        assert len(snap.nodes) > 0
        assert len(snap.edges) > 0
        assert snap.tick_count == 1
