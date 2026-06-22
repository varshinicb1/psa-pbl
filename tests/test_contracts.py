"""Tests for dt_contracts schema validation."""

from __future__ import annotations

import pytest
from datetime import datetime
from dt_contracts import (
    GridGraphSnapshot,
    GridNode,
    GridEdge,
    ExternalRef,
    TelemetryTick,
    Measurement,
    MeasurementQuality,
    ExplanationPacket,
    Explanation,
    EntityScore,
    FeatureScore,
    ActionPlan,
    Action,
)


class TestGridGraphSnapshot:
    """Tests for GridGraphSnapshot schema."""

    @pytest.mark.unit
    def test_grid_graph_snapshot_creation(self, sample_grid_graph):
        """Test creating GridGraphSnapshot from dict."""
        snapshot = GridGraphSnapshot(**sample_grid_graph)
        assert snapshot.t == "2026-06-16T04:47:00Z"
        assert snapshot.topology_hash == "abc123def456"
        assert len(snapshot.nodes) == 2
        assert len(snapshot.edges) == 1

    @pytest.mark.unit
    def test_grid_graph_snapshot_requires_time(self):
        """Test that GridGraphSnapshot requires timestamp."""
        with pytest.raises((ValueError, Exception)):
            GridGraphSnapshot(
                topology_hash="test",
                nodes=[],
                edges=[],
            )

    @pytest.mark.unit
    def test_grid_node_with_external_ref(self):
        """Test GridNode with external references."""
        node = GridNode(
            id="bus_1",
            type="BusTerminal",
            static={"voltage_kv": 115},
            external_refs=[
                ExternalRef(
                    engine="pandapower",
                    object_type="Bus",
                    object_name="Bus_1",
                )
            ],
        )
        assert node.id == "bus_1"
        assert len(node.external_refs) == 1
        assert node.external_refs[0].engine == "pandapower"

    @pytest.mark.unit
    def test_grid_edge_source_target_validation(self):
        """Test GridEdge validates source and target."""
        edge = GridEdge(
            id="line_1",
            type="Line",
            source="bus_1",
            target="bus_2",
            static={"r_ohm": 1.5, "x_ohm": 5.2},
        )
        assert edge.source == "bus_1"
        assert edge.target == "bus_2"
        assert edge.static["r_ohm"] == 1.5


class TestTelemetryTick:
    """Tests for TelemetryTick schema."""

    @pytest.mark.unit
    def test_telemetry_tick_creation(self, sample_telemetry_tick):
        """Test creating TelemetryTick from dict."""
        tick = TelemetryTick(**sample_telemetry_tick)
        assert tick.source == "pmu_01"
        assert len(tick.measurements) == 2
        assert tick.measurements[0].signal == "voltage"

    @pytest.mark.unit
    def test_telemetry_tick_requires_timestamps(self):
        """Test that TelemetryTick requires event and ingest timestamps."""
        with pytest.raises(ValueError):
            TelemetryTick(measurements=[])

    @pytest.mark.unit
    def test_measurement_quality_flags(self):
        """Test MeasurementQuality flags."""
        quality = MeasurementQuality(
            valid=True,
            missing=False,
            estimated=False,
            delay_ms=2.5,
        )
        assert quality.valid is True
        assert quality.delay_ms == 2.5

    @pytest.mark.unit
    def test_measurement_with_phase(self):
        """Test Measurement with phase information."""
        measurement = Measurement(
            entity_id="line_1",
            signal="current",
            value=245.5,
            unit="A",
            phase="A",
        )
        assert measurement.phase == "A"
        assert measurement.unit == "A"

    @pytest.mark.unit
    def test_measurement_various_types(self):
        """Test Measurement with different value types."""
        # Float value
        m1 = Measurement(entity_id="e1", signal="s1", value=1.5)
        assert isinstance(m1.value, float)

        # Int value
        m2 = Measurement(entity_id="e2", signal="s2", value=42)
        assert isinstance(m2.value, int)

        # Bool value
        m3 = Measurement(entity_id="e3", signal="s3", value=True)
        assert isinstance(m3.value, bool)

        # String value
        m4 = Measurement(entity_id="e4", signal="s4", value="status_ok")
        assert isinstance(m4.value, str)


class TestExplanationPacket:
    """Tests for ExplanationPacket schema."""

    @pytest.mark.unit
    def test_explanation_packet_creation(self):
        """Test creating ExplanationPacket."""
        packet = ExplanationPacket(
            t="2026-06-16T04:47:00Z",
            model_version="1.0.0",
            target={"anomaly": "voltage_out_of_bounds"},
            explanations=[
                Explanation(
                    type="SubgraphAttribution",
                    node_scores=[EntityScore(id="bus_1", score=0.85)],
                )
            ],
        )
        assert packet.model_version == "1.0.0"
        assert len(packet.explanations) == 1
        assert packet.explanations[0].type == "SubgraphAttribution"

    @pytest.mark.unit
    def test_explanation_with_multiple_scores(self):
        """Test Explanation with node, edge, and feature scores."""
        explanation = Explanation(
            type="Attribution",
            node_scores=[
                EntityScore(id="bus_1", score=0.9),
                EntityScore(id="bus_2", score=0.7),
            ],
            edge_scores=[
                EntityScore(id="line_1", score=0.65),
            ],
            feature_scores=[
                FeatureScore(entity_id="bus_1", feature="voltage", score=0.95),
            ],
        )
        assert len(explanation.node_scores) == 2
        assert len(explanation.edge_scores) == 1
        assert len(explanation.feature_scores) == 1
        assert explanation.node_scores[0].score == 0.9


class TestActionPlan:
    """Tests for ActionPlan schema."""

    @pytest.mark.unit
    def test_action_plan_creation(self):
        """Test creating ActionPlan."""
        plan = ActionPlan(
            t="2026-06-16T04:47:00Z",
            plan_id="plan_001",
            actions=[
                Action(
                    type="open_breaker",
                    device_id="breaker_1",
                    desired_state="open",
                ),
                Action(
                    type="set_tap",
                    device_id="transformer_1",
                    desired_state=2,
                ),
            ],
            expected_outcome={"voltage_restoration": True},
        )
        assert plan.plan_id == "plan_001"
        assert len(plan.actions) == 2
        assert plan.actions[0].type == "open_breaker"

    @pytest.mark.unit
    def test_action_with_effective_time(self):
        """Test Action with effective time."""
        action = Action(
            type="load_shed",
            device_id="load_1",
            desired_state=0.8,
            effective_time="2026-06-16T04:47:10Z",
        )
        assert action.effective_time == "2026-06-16T04:47:10Z"
        assert action.desired_state == 0.8


class TestSchemaValidation:
    """Tests for schema validation utilities."""

    @pytest.mark.unit
    def test_validate_against_schema(self, sample_grid_graph):
        """Test schema validation."""
        from dt_contracts import validate_against_schema

        result = validate_against_schema(sample_grid_graph, "gridgraph.schema.json")
        assert result is True or result is None

    @pytest.mark.unit
    def test_schema_version_consistency(self, sample_grid_graph):
        """Test that schema versions are consistent."""
        snapshot = GridGraphSnapshot(**sample_grid_graph)
        assert snapshot.schema_version is not None
        # Verify version format (should be semver-like)
        assert "." in snapshot.schema_version

    @pytest.mark.unit
    def test_extra_fields_forbidden_grid_graph(self):
        """Test that extra fields are forbidden in GridGraphSnapshot."""
        with pytest.raises(ValueError):
            GridGraphSnapshot(
                t="2026-06-16T04:47:00Z",
                topology_hash="abc",
                extra_field="should_fail",
            )

    @pytest.mark.unit
    def test_extra_fields_allowed_in_action(self):
        """Test that Action allows extra fields."""
        action = Action(
            type="custom_action",
            device_id="dev_1",
            custom_param="custom_value",
        )
        assert action.type == "custom_action"
        # Custom param should be accessible
        assert hasattr(action, "custom_param")
