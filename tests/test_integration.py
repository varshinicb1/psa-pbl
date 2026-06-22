"""End-to-end integration tests for the full grid digital twin pipeline.

Tests the complete data flow:
  Simulator -> Powerflow -> State Store -> Anomaly Detection -> Tick Output

Validates both IEEE-14 and BESCOM Bangalore backends.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "platform" / "dt-orchestrator"))
sys.path.insert(0, str(PROJECT_ROOT / "platform" / "dt-contracts" / "python" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "platform" / "dt-sim-pandapower"))
sys.path.insert(0, str(PROJECT_ROOT / "platform" / "dt-bescom" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "platform" / "dt-ml"))

from dt_contracts.exceptions import TickExecutionError
from dt_contracts.models import GridGraphSnapshot, ExplanationPacket


class TestIEEE14Backend:
    """Tests for IEEE-14 backend (backward compatibility)."""

    def test_runner_initializes(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="ieee14")
        assert runner is not None
        assert runner._is_bescom is False
        assert runner.adapter is not None

    def test_runner_initial_network(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="ieee14")
        snap = runner.store.get_latest()
        assert snap is not None
        assert len(snap.nodes) == 14
        assert len(snap.edges) > 0

    def test_run_one_tick_converges(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="ieee14", use_ml=False)
        out = runner.run_one_tick()
        assert out.snapshot is not None
        assert out.snapshot.tick_count == 1
        assert out.metrics.get("solved") is True

    def test_multiple_ticks(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="ieee14", use_ml=False)
        for i in range(5):
            out = runner.run_one_tick()
            assert out.snapshot.tick_count == i + 1

    def test_perturb_load(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="ieee14", use_ml=False)
        runner.perturb_load("0", 5.0, 2.0)
        out = runner.run_one_tick()
        assert out.metrics.get("solved") is True

    def test_anomaly_detection(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="ieee14", use_ml=True)
        out = runner.run_one_tick()
        assert out.explanation is None or isinstance(out.explanation, dict) or hasattr(out.explanation, 'model_dump')

    def test_store_maintains_history(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="ieee14", use_ml=False)
        for i in range(10):
            runner.run_one_tick()
        assert len(runner.store.history) == 11  # initial + 10 ticks


class TestBESCOMBackend:
    """Tests for BESCOM Bangalore backend (new integration)."""

    @pytest.mark.requires_pandapower
    def test_runner_initializes(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="bescom")
        assert runner is not None
        assert runner._is_bescom is True
        assert runner.adapter is None
        assert runner.bescom is not None

    @pytest.mark.requires_pandapower
    def test_initial_network_has_50_buses(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="bescom")
        snap = runner.store.get_latest()
        assert snap is not None
        assert len(snap.nodes) == 50
        assert len(snap.edges) > 80

    @pytest.mark.requires_pandapower
    def test_run_one_tick_converges(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="bescom", use_ml=False)
        out = runner.run_one_tick()
        assert out.snapshot is not None
        assert out.snapshot.tick_count == 1
        assert out.metrics.get("solved") is True
        assert out.metrics.get("grid_type") == "bescom"

    @pytest.mark.requires_pandapower
    def test_multiple_bescom_ticks(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="bescom", use_ml=False)
        for i in range(5):
            out = runner.run_one_tick()
            assert out.snapshot.tick_count == i + 1
            assert len(out.snapshot.nodes) == 50

    @pytest.mark.requires_pandapower
    def test_bescom_voltages_in_range(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="bescom", use_ml=False)
        out = runner.run_one_tick()
        for node in out.snapshot.nodes:
            vm = node.dynamic.get("vm_pu")
            if vm is not None:
                assert 0.90 <= vm <= 1.10, f"Bus {node.id} vm_pu={vm} out of range"

    @pytest.mark.requires_pandapower
    def test_bescom_perturb_load(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="bescom", use_ml=False)
        bescom_bus_id = "bescom/Nelamangala 400kV"
        runner.perturb_load(bescom_bus_id, 10.0)
        out = runner.run_one_tick()
        assert out.metrics.get("solved") is True

    @pytest.mark.requires_pandapower
    def test_bescom_store_history(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="bescom", use_ml=False)
        for i in range(10):
            runner.run_one_tick()
        assert len(runner.store.history) == 11

    @pytest.mark.requires_pandapower
    def test_bescom_anomaly_detection(self):
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        runner = RealtimeTickRunner(grid_type="bescom", use_ml=True)
        out = runner.run_one_tick()
        assert out.snapshot is not None
        assert out.metrics.get("solved") is True


class TestAPIIntegration:
    """Tests for the FastAPI server integration."""

    @pytest.mark.integration
    def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        from dt_orchestrator.api.app import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "grid_type" in data

    @pytest.mark.integration
    def test_snapshot_endpoint(self):
        from fastapi.testclient import TestClient
        from dt_orchestrator.api.app import app
        client = TestClient(app)
        resp = client.get("/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data

    @pytest.mark.integration
    def test_topology_endpoint(self):
        from fastapi.testclient import TestClient
        from dt_orchestrator.api.app import app
        client = TestClient(app)
        resp = client.get("/topology")
        assert resp.status_code == 200
        data = resp.json()
        assert "topology_hash" in data
        assert "nodes" in data

    @pytest.mark.integration
    def test_history_endpoint(self):
        from fastapi.testclient import TestClient
        from dt_orchestrator.api.app import app
        client = TestClient(app)
        resp = client.get("/history")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.integration
    def test_metrics_prometheus_endpoint(self):
        from fastapi.testclient import TestClient
        from dt_orchestrator.api.app import app
        client = TestClient(app)
        resp = client.get("/metrics/prometheus")
        assert resp.status_code == 200
        assert "dt_ticks_total" in resp.text
