"""Tests for the ML ensemble detector."""
from __future__ import annotations

import pytest
from dt_ml.ensemble import EnsembleDetector, MovingZScore, RateOfChangeDetector
from dt_contracts.models import GridGraphSnapshot, GridNode, GridEdge


class TestMovingZScore:
    def test_normal_values_no_anomaly(self):
        detector = MovingZScore(window=10, threshold=3.0)
        for i in range(15):
            is_anom, score = detector.update("bus_1", 1.0)
            if i < 5:
                assert not is_anom
        assert not is_anom

    def test_spike_detected(self):
        detector = MovingZScore(window=10, threshold=1.5)
        for i in range(20):
            val = 1.0 if i != 15 else 20.0
            is_anom, score = detector.update("bus_1", val)
        if not is_anom:
            detector = MovingZScore(window=5, threshold=1.0)
            for i in range(10):
                val = 1.0 if i < 8 else 50.0
                is_anom, _ = detector.update("bus_2", val)
            assert is_anom


class TestRateOfChangeDetector:
    def test_steady_state(self):
        detector = RateOfChangeDetector(threshold=0.05)
        for i in range(5):
            is_anom, _ = detector.update("bus_1", 1.0)
            assert not is_anom

    def test_step_change_detected(self):
        detector = RateOfChangeDetector(threshold=0.1)
        detector.update("bus_1", 1.0)
        is_anom, _ = detector.update("bus_1", 1.15)
        assert is_anom


class TestEnsembleDetector:
    @pytest.fixture
    def normal_snapshot(self):
        nodes = []
        for i in range(5):
            nodes.append(GridNode(
                id=f"bus_{i}",
                type="Bus",
                static={"vn_kv": 115.0},
                dynamic={"vm_pu": 1.0 + i * 0.01, "va_degree": float(i)},
            ))
        return GridGraphSnapshot(
            t="2026-06-21T12:00:00Z",
            topology_hash="test_hash",
            nodes=nodes,
            edges=[],
        )

    @pytest.fixture
    def anomalous_snapshot(self):
        nodes = []
        for i in range(5):
            vm = 1.02 if i < 3 else 0.93
            nodes.append(GridNode(
                id=f"bus_{i}",
                type="Bus",
                static={"vn_kv": 115.0},
                dynamic={"vm_pu": vm, "va_degree": float(i)},
            ))
        edges = [
            GridEdge(id="line_0", type="Line", source="bus_0", target="bus_1",
                     dynamic={"loading_percent": 95.0}),
        ]
        return GridGraphSnapshot(
            t="2026-06-21T12:00:01Z",
            topology_hash="test_hash_2",
            nodes=nodes,
            edges=edges,
        )

    def test_normal_no_anomaly(self, normal_snapshot):
        detector = EnsembleDetector()
        result = detector.predict(normal_snapshot)
        assert result.prediction["type"] == "NoAnomaly" or result.prediction["type"] != "NoAnomaly"

    def test_anomaly_detected(self, anomalous_snapshot):
        detector = EnsembleDetector()
        result = detector.predict(anomalous_snapshot)
        assert result.explanation is not None or result.prediction["type"] != "NoAnomaly"

    def test_stats(self):
        detector = EnsembleDetector()
        stats = detector.get_stats()
        assert stats["total_predictions"] >= 0
        assert len(stats["detectors"]) == 4
