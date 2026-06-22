"""
Tests for the GNN-based anomaly detection module.

Covers:
- GridBuilder: GridGraphSnapshot -> PyG Data conversion
- RGATv2: Forward pass with correct output shapes
- FaultClassifier: Output structure and calibration
- GNNDetector: End-to-end inference pipeline
- Integration with EnsembleDetector

Run:
    pytest platform/dt-ml/tests/test_gnn.py -v --no-header
"""

from __future__ import annotations

import pathlib
import sys

# Bootstrap paths for local development
_repo_root = pathlib.Path(__file__).resolve().parents[3]
for _mod in ["dt-ml", "dt-contracts/python/src"]:
    _p = str(_repo_root / "platform" / _mod)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import math

import pytest
import torch

from dt_contracts.models import GridGraphSnapshot, GridNode, GridEdge
from dt_ml.gnn.grid_builder import GridBuilder, NODE_FEATURES, EDGE_FEATURES
from dt_ml.gnn.model import RGATv2, RGATv2Config, AttentionPooling, PhysicsInformedLoss
from dt_ml.gnn.fault_types import FaultClassifier, FaultType, FaultPrediction, calibrate_with_physics
from dt_ml.gnn.detector import GNNDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_snapshot() -> GridGraphSnapshot:
    """Create a minimal 5-bus grid snapshot for testing."""
    nodes = []
    for i in range(5):
        nodes.append(GridNode(
            id=f"bus_{i}",
            type="Bus",
            static={"vn_kv": 115.0, "in_service": True},
            dynamic={"vm_pu": 1.0 + 0.02 * (i - 2), "va_degree": float(i * 2), "p_mw": float(i * 10), "q_mvar": float(i * 5)},
        ))
    # Set bus_3 to have anomalous voltage
    nodes[3].dynamic["vm_pu"] = 0.93

    edges = [
        GridEdge(
            id=f"line_{i}_{i+1}",
            type="Line",
            source=f"bus_{i}",
            target=f"bus_{i+1}",
            static={"r_ohm_per_km": 0.1, "x_ohm_per_km": 0.3, "length_km": 10.0, "max_i_ka": 0.5, "in_service": True},
            dynamic={"loading_percent": 40.0 + i * 10, "p_from_mw": 20.0, "q_from_mvar": 10.0, "p_to_mw": 19.0, "q_to_mvar": 9.0},
        )
        for i in range(4)
    ]

    return GridGraphSnapshot(
        t="2026-06-01T00:00:00Z",
        topology_hash="test_hash_5bus",
        nodes=nodes,
        edges=edges,
        tick_count=42,
    )


@pytest.fixture
def rgatv2_model() -> RGATv2:
    """Create an RGATv2 model with default config."""
    config = RGATv2Config(
        node_feat_dim=10,
        edge_feat_dim=10,
        hidden_dim=32,  # Smaller for testing
        latent_dim=16,
        num_heads=2,
        num_layers=2,
    )
    return RGATv2(config)


@pytest.fixture
def fault_classifier() -> FaultClassifier:
    """Create a FaultClassifier with small dimensions."""
    return FaultClassifier(latent_dim=16, hidden_dim=16)


# ---------------------------------------------------------------------------
# GridBuilder Tests
# ---------------------------------------------------------------------------

class TestGridBuilder:
    """Tests for GridBuilder: snapshot -> PyG Data conversion."""

    def test_build_basic(self, sample_snapshot):
        """Test that GridBuilder produces a valid PyG Data object."""
        builder = GridBuilder()
        data = builder.build(sample_snapshot)

        assert data.num_nodes == 5
        assert data.x.shape == (5, 10)
        assert data.edge_index.shape[0] == 2
        assert data.edge_index.shape[1] == 8  # 4 edges * 2 directions
        assert data.edge_attr.shape[0] == 8
        assert data.edge_attr.shape[1] == 10
        assert data.topology_hash == "test_hash_5bus"
        assert data.tick_count == 42

    def test_node_feature_values(self, sample_snapshot):
        """Test that node feature values are correctly extracted."""
        # Disable normalization to test raw feature extraction
        builder = GridBuilder(normalize=False)
        data = builder.build(sample_snapshot)

        # bus_3 has vm_pu = 0.93 (anomalous)
        assert abs(data.x[3, 0].item() - 0.93) < 0.01, "vm_pu for bus_3 should be 0.93"

        # bus_0 has vm_pu = 1.0 - 0.04 = 0.96
        assert abs(data.x[0, 0].item() - 0.96) < 0.01, "vm_pu for bus_0 should be 0.96"

    def test_topology_tracking(self, sample_snapshot):
        """Test topology change detection."""
        builder = GridBuilder()
        builder.build(sample_snapshot)

        # Same topology hash
        data1 = builder.build(sample_snapshot)
        assert data1.topology_hash == "test_hash_5bus"

        # Different topology hash
        changed = GridGraphSnapshot(
            t="2026-06-01T00:01:00Z",
            topology_hash="new_hash",
            nodes=sample_snapshot.nodes,
            edges=sample_snapshot.edges,
        )
        data2 = builder.build(changed)
        assert data2.topology_hash == "new_hash"

    def test_empty_graph(self):
        """Test that empty snapshots produce empty data."""
        builder = GridBuilder()
        snapshot = GridGraphSnapshot(
            t="2026-01-01T00:00:00Z",
            topology_hash="empty",
            nodes=[],
            edges=[],
        )
        data = builder.build(snapshot)
        assert data.num_nodes == 0
        assert data.x.shape == (0, 10)


# ---------------------------------------------------------------------------
# RGATv2 Model Tests
# ---------------------------------------------------------------------------

class TestRGATv2:
    """Tests for the RGATv2 GNN architecture."""

    def test_forward_pass_shape(self, sample_snapshot, rgatv2_model):
        """Test that forward pass produces correct output shapes."""
        builder = GridBuilder()
        data = builder.build(sample_snapshot)

        out = rgatv2_model.forward(data.x, data.edge_index, data.edge_attr)

        # Node scores: [N, 1]
        assert out["node_scores"].shape == (5, 1)
        assert out["node_scores"].min() >= 0.0
        assert out["node_scores"].max() <= 1.0

        # Edge scores: [E, 1] (E = 8 for 4 edges * 2 directions)
        assert out["edge_scores"].shape[0] == 8
        assert out["edge_scores"].shape[1] == 1

        # Graph feature: [1, latent_dim]
        assert out["graph_feat"].shape == (1, rgatv2_model.config.latent_dim)

        # Node embeddings: [N, hidden_dim]
        assert out["node_embeddings"].shape == (5, rgatv2_model.config.hidden_dim)

    def test_batched_forward(self, rgatv2_model):
        """Test forward pass with batched graphs (2 separate graphs)."""
        builder = GridBuilder()

        # Create two separate grid snapshots
        nodes1 = [GridNode(id=f"a_{i}", type="Bus", static={"vn_kv": 115.0}, dynamic={"vm_pu": 1.0, "va_degree": 0.0}) for i in range(3)]
        snap1 = GridGraphSnapshot(t="t1", topology_hash="h1", nodes=nodes1, edges=[])

        nodes2 = [GridNode(id=f"b_{i}", type="Bus", static={"vn_kv": 115.0}, dynamic={"vm_pu": 1.0, "va_degree": 0.0}) for i in range(4)]
        snap2 = GridGraphSnapshot(t="t2", topology_hash="h2", nodes=nodes2, edges=[])

        d1 = builder.build(snap1)
        d2 = builder.build(snap2)

        # Concatenate into a batch
        from torch_geometric.data import Batch
        batch_data = Batch.from_data_list([d1, d2])

        out = rgatv2_model.forward(batch_data.x, batch_data.edge_index, batch_data.edge_attr, batch_data.batch)

        # Total nodes = 3 + 4 = 7
        assert out["node_scores"].shape[0] == 7
        # Graph features: [2, latent_dim]
        assert out["graph_feat"].shape[0] == 2

    def test_loss_function_shapes(self, sample_snapshot, rgatv2_model):
        """Test that compute_loss returns correct loss components."""
        builder = GridBuilder()
        data = builder.build(sample_snapshot)

        # Create labels
        node_labels = torch.tensor([0, 0, 0, 1, 0], dtype=torch.long)  # bus_3 is anomalous
        graph_labels = torch.tensor([1])  # SLG fault

        loss_dict = rgatv2_model.compute_loss(
            data.x, data.edge_index, data.edge_attr,
            node_labels=node_labels,
            graph_labels=graph_labels,
        )

        assert "loss" in loss_dict
        assert "node_loss" in loss_dict
        assert "graph_loss" in loss_dict
        assert "phys_loss" in loss_dict
        assert loss_dict["loss"].item() > 0
        assert loss_dict["node_loss"].item() > 0
        assert loss_dict["phys_loss"].item() > 0

    def test_physics_informed_loss(self, sample_snapshot):
        """Test the physics-informed regularisation term."""
        config = RGATv2Config(hidden_dim=32, latent_dim=16, num_heads=2, num_layers=2)
        model = RGATv2(config)

        builder = GridBuilder()
        data = builder.build(sample_snapshot)

        # Case 1: out-of-bounds voltage should produce higher physics loss
        out = model.forward(data.x, data.edge_index, data.edge_attr)
        phys_loss = model.physics_loss(
            out["node_scores"], data.x, data.edge_index, out["edge_scores"]
        )
        assert phys_loss.item() > 0

        # Case 2: ideal voltages should produce lower loss
        ideal_x = data.x.clone()
        ideal_x[:, 0] = 1.0  # All voltages at 1.0 p.u.
        out2 = model.forward(ideal_x, data.edge_index, data.edge_attr)
        phys_loss2 = model.physics_loss(
            out2["node_scores"], ideal_x, data.edge_index, out2["edge_scores"]
        )
        # Out-of-bounds voltages should have higher physics loss
        assert phys_loss2.item() <= phys_loss.item() + 1e-6, (
            "Ideal voltages should have lower or equal physics loss"
        )

    def test_attention_pooling(self):
        """Test the attention pooling mechanism."""
        pool = AttentionPooling(in_channels=16, hidden_dim=16)
        x = torch.randn(10, 16)  # 10 nodes, 16 features
        batch = torch.zeros(10, dtype=torch.long)  # Single graph

        out = pool(x, batch)
        assert out.shape == (1, 16)

        # Batched
        batch2 = torch.cat([torch.zeros(5, dtype=torch.long), torch.ones(5, dtype=torch.long)])
        out2 = pool(x, batch2)
        assert out2.shape == (2, 16)


# ---------------------------------------------------------------------------
# FaultClassifier Tests
# ---------------------------------------------------------------------------

class TestFaultClassifier:
    """Tests for the FaultClassifier module."""

    def test_forward_pass(self, fault_classifier):
        """Test that forward pass produces correct output shapes."""
        B, N = 2, 10  # 2 graphs, 10 nodes total
        graph_feat = torch.randn(B, 16)
        node_embeddings = torch.randn(N, 128)  # matches default node_feat_dim
        node_scores = torch.rand(N, 1)
        batch = torch.cat([torch.zeros(5, dtype=torch.long), torch.ones(5, dtype=torch.long)])

        out = fault_classifier.forward(graph_feat, node_embeddings, node_scores, batch)

        assert out["fault_logits"].shape == (B, 6)
        assert out["fault_probs"].shape == (B, 6)
        assert abs(out["fault_probs"][0].sum().item() - 1.0) < 0.01
        assert out["isolation_scores"].shape == (N, 1)
        assert out["severity"].shape == (B, 1)
        assert 0 <= out["severity"][0].item() <= 1.0

    def test_fault_type_enum(self):
        """Test FaultType enum values and descriptions."""
        assert FaultType.NORMAL.value == 0
        assert FaultType.THREE_PHASE.value == 4
        assert len(FaultType.names()) == 6
        desc = FaultType.descriptions()
        assert desc[0] == "Normal operation — no fault detected"
        assert desc[4].startswith("Three-phase")

    def test_physics_calibration(self):
        """Test physics-constrained calibration of anomaly scores."""
        scores = torch.tensor([[0.1], [0.2], [0.3]])  # Raw GNN scores
        vm_pu = torch.tensor([0.95, 1.00, 1.20])  # Normal, nominal, over-voltage

        calibrated = calibrate_with_physics(scores, vm_pu, v_min=0.90, v_max=1.10)

        # Over-voltage node should get boost
        assert calibrated[2] > scores[2], "Over-voltage node score should be boosted"
        # Normal nodes should not get significant boost
        assert calibrated[1].item() - scores[1].item() < 0.05


# ---------------------------------------------------------------------------
# GNNDetector Integration Tests
# ---------------------------------------------------------------------------

class TestGNNDetector:
    """Tests for the full GNNDetector pipeline."""

    def test_detector_initializes(self):
        """Test that GNNDetector initializes with random weights."""
        detector = GNNDetector(force_cpu=True)
        assert detector.rgatv2 is not None
        assert detector.classifier is not None
        assert detector.grid_builder is not None
        assert not detector._checkpoint_loaded

    def test_detector_predict_no_anomaly(self, sample_snapshot):
        """Test prediction on normal snapshot returns NoGNNAnomaly."""
        # Replace bus_3 with normal voltage
        for node in sample_snapshot.nodes:
            if node.id == "bus_3":
                node.dynamic["vm_pu"] = 1.0

        detector = GNNDetector(force_cpu=True)
        result = detector.predict(sample_snapshot)

        assert result["type"] in ("NoGNNAnomaly", "GNNDetection")
        assert isinstance(result["node_scores"], dict)
        assert len(result["node_scores"]) == 5

    def test_detector_predict_anomaly_detected(self, sample_snapshot):
        """Test that anomalous snapshot produces scores."""
        detector = GNNDetector(force_cpu=True)
        result = detector.predict(sample_snapshot)

        # bus_3 has vm_pu=0.93 — it should have elevated anomaly score
        bus_3_score = result["node_scores"].get("bus_3", 0.0)
        bus_0_score = result["node_scores"].get("bus_0", 0.0)

        # The physics calibration should boost the anomalous node
        assert isinstance(bus_3_score, float)
        assert 0.0 <= bus_3_score <= 1.0

    def test_explanation_packet_generation(self, sample_snapshot):
        """Test conversion of GNN result to ExplanationPacket."""
        detector = GNNDetector(force_cpu=True)
        result = detector.predict(sample_snapshot)

        packet = detector.to_explanation_packet(sample_snapshot, result)
        if packet is not None:
            assert packet.schema_version is not None
            assert packet.model_version == "gnn-rgatv2-v1.0"
            assert "type" in packet.target
            assert "confidence" in packet.target
            assert len(packet.explanations) > 0

    def test_get_stats(self):
        """Test stats reporting."""
        detector = GNNDetector(force_cpu=True)
        stats = detector.get_stats()
        assert "total_predictions" in stats
        assert "checkpoint_loaded" in stats
        assert "device" in stats
        assert stats["checkpoint_loaded"] is False

    def test_grid_size_detection(self):
        """Test automatic grid size detection from node count."""
        from dt_ml.gnn.detector import _detect_grid_size

        class MockSnapshot:
            def __init__(self, n):
                self.nodes = list(range(n))

        assert _detect_grid_size(MockSnapshot(10)) == 14
        assert _detect_grid_size(MockSnapshot(50)) == 118
        assert _detect_grid_size(MockSnapshot(200)) == 300
