"""Pytest fixtures and configuration for Grid Digital Twin tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
from pydantic import ValidationError

# Setup paths for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "platform" / "dt-orchestrator"))
sys.path.insert(0, str(PROJECT_ROOT / "platform" / "dt-contracts" / "python" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "platform" / "dt-ml"))
sys.path.insert(0, str(PROJECT_ROOT / "platform" / "dt-sim-pandapower"))
sys.path.insert(0, str(PROJECT_ROOT / "platform"))


@pytest.fixture
def ieee14_network_data() -> Dict[str, Any]:
    """Fixture for IEEE-14 bus network data."""
    return {
        "buses": 14,
        "lines": 20,
        "transformers": 3,
        "generators": 5,
        "loads": 11,
    }


@pytest.fixture
def sample_telemetry_tick() -> Dict[str, Any]:
    """Fixture for sample telemetry tick data."""
    from dt_contracts import TelemetryTick, Measurement, MeasurementQuality

    tick = TelemetryTick(
        t_event="2026-06-16T04:47:00Z",
        t_ingest="2026-06-16T04:47:01Z",
        source="pmu_01",
        measurements=[
            Measurement(
                entity_id="bus_1",
                signal="voltage",
                value=1.02,
                unit="pu",
                quality=MeasurementQuality(valid=True),
            ),
            Measurement(
                entity_id="line_1",
                signal="current",
                value=245.5,
                unit="A",
                quality=MeasurementQuality(valid=True),
            ),
        ],
    )
    return tick.model_dump()


@pytest.fixture
def sample_grid_graph() -> Dict[str, Any]:
    """Fixture for sample grid graph snapshot."""
    from dt_contracts import GridGraphSnapshot, GridNode, GridEdge, ExternalRef

    graph = GridGraphSnapshot(
        t="2026-06-16T04:47:00Z",
        topology_hash="abc123def456",
        nodes=[
            GridNode(
                id="bus_1",
                type="BusTerminal",
                static={"voltage_rating_kv": 115},
                external_refs=[
                    ExternalRef(
                        engine="pandapower",
                        object_type="Bus",
                        object_name="Bus_1",
                    )
                ],
            ),
            GridNode(
                id="bus_2",
                type="BusTerminal",
                static={"voltage_rating_kv": 115},
            ),
        ],
        edges=[
            GridEdge(
                id="line_1_2",
                type="Line",
                source="bus_1",
                target="bus_2",
                static={
                    "r_ohm": 1.5,
                    "x_ohm": 5.2,
                    "c_nf": 0.0,
                    "rating_ka": 1.2,
                },
            ),
        ],
    )
    return graph.model_dump()


@pytest.fixture
def mock_adapter_output() -> Dict[str, Any]:
    """Fixture for mock adapter output."""
    return {
        "converged": True,
        "solver_iterations": 5,
        "solved": True,
        "time_ms": 120.5,
        "voltage_pu": {
            "bus_1": 1.01,
            "bus_2": 0.99,
            "bus_3": 1.02,
        },
        "line_current_a": {
            "line_1": 245.5,
            "line_2": 198.3,
        },
        "losses_mw": 2.35,
    }


@pytest.fixture
def mock_pandapower_net() -> Dict[str, Any]:
    """Fixture for mock pandapower network."""
    try:
        import pandapower as pp

        net = pp.networks.case14()
        return net
    except ImportError:
        pytest.skip("pandapower not installed")


@pytest.fixture
def mock_ws_message() -> Dict[str, Any]:
    """Fixture for mock WebSocket message."""
    return {
        "type": "tick_result",
        "tick_number": 0,
        "timestamp": "2026-06-16T04:47:00Z",
        "converged": True,
        "topology_hash": "abc123",
    }


@pytest.fixture
def api_client():
    """Fixture for FastAPI test client."""
    from fastapi.testclient import TestClient
    from dt_orchestrator.api.app import app

    return TestClient(app)


@pytest.fixture
def mock_logger(caplog):
    """Fixture for capturing and testing logs."""
    return caplog


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "unit: mark test as a unit test",
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow (>1 second)",
    )
    config.addinivalue_line(
        "markers",
        "requires_pandapower: mark test as requiring pandapower",
    )
    config.addinivalue_line(
        "markers",
        "requires_opendss: mark test as requiring OpenDSS",
    )
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async",
    )
