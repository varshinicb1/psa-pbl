"""
GNNDetector: GNN-based anomaly detector for the ML ensemble pipeline.

Wraps RGATv2 + FaultClassifier + GridBuilder into a drop-in detector
that can be used alongside statistical and physics-based detectors.

Handles:
- Model initialization with pretrained checkpoint loading (graceful fallback)
- GridGraphSnapshot -> PyG Data conversion
- RGATv2 inference for node/edge anomaly scores
- FaultClassifier inference for fault type + severity
- ExplanationPacket generation compatible with the TwinModel interface
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch

from dt_contracts.models import (
    EntityScore,
    Explanation,
    ExplanationPacket,
    GridGraphSnapshot,
    SCHEMA_VERSION,
)
from dt_ml.gnn.grid_builder import GridBuilder
from dt_ml.gnn.model import RGATv2, RGATv2Config
from dt_ml.gnn.fault_types import FaultClassifier, FaultType, FaultPrediction, calibrate_with_physics

logger = logging.getLogger(__name__)

# Default checkpoint paths (relative to project root)
DEFAULT_CHECKPOINT_DIR = Path(__file__).resolve().parents[2] / "checkpoints"
CHECKPOINT_NAMES = {
    14: "gridsentinel_ieee14.pt",
    118: "gridsentinel_ieee118.pt",
}


def _detect_grid_size(snapshot: GridGraphSnapshot) -> int:
    """Heuristic: detect approximate grid size from node count."""
    n = len(snapshot.nodes)
    if n <= 20:
        return 14
    elif n <= 120:
        return 118
    else:
        return 300


class GNNDetector:
    """
    GNN-based anomaly detector wrapping RGATv2 + FaultClassifier.

    Can run in two modes:
      1. **Production** — loads pretrained checkpoint for inference
      2. **Development** — initialises with random weights (architecture test)

    Usage:
        detector = GNNDetector()
        output = detector.predict(snapshot)  # -> TwinModelOutput-compatible dict
    """

    def __init__(
        self,
        checkpoint_path: Optional[Path] = None,
        device: Optional[torch.device] = None,
        force_cpu: bool = False,
    ):
        if device is None:
            self.device = torch.device("cpu" if force_cpu or not torch.cuda.is_available() else "cuda")
        else:
            self.device = device

        # Build components
        self.config = RGATv2Config(
            node_feat_dim=10,
            edge_feat_dim=10,
            hidden_dim=128,
            latent_dim=64,
            num_heads=4,
            num_layers=3,
            dropout=0.15,
            phys_loss_weight=0.30,
        )

        self.grid_builder = GridBuilder()
        self.rgatv2 = RGATv2(self.config).to(self.device)
        self.classifier = FaultClassifier(
            latent_dim=self.config.latent_dim,
            node_feat_dim=self.config.hidden_dim,
            num_fault_types=6,
        ).to(self.device)

        self._checkpoint_loaded = False
        self._total_predictions = 0
        self._anomaly_predictions = 0

        # Try loading checkpoint
        if checkpoint_path is not None:
            self._load_checkpoint(checkpoint_path)
        else:
            logger.info("GNNDetector initialized with random weights (untrained)")

    def _load_checkpoint(self, path: Path) -> None:
        """Load pretrained weights from checkpoint."""
        if not path.exists():
            logger.warning(f"Checkpoint not found: {path} — using random weights")
            return
        try:
            checkpoint = torch.load(path, map_location=self.device, weights_only=True)
            # Load RGATv2 weights
            model_state = {k: v for k, v in checkpoint["model_state_dict"].items()
                          if not k.startswith("classifier.")}
            self.rgatv2.load_state_dict(model_state, strict=False)

            # Load FaultClassifier weights if present
            cls_state = {k.replace("classifier.", ""): v
                        for k, v in checkpoint["model_state_dict"].items()
                        if k.startswith("classifier.")}
            if cls_state:
                self.classifier.load_state_dict(cls_state, strict=False)

            epoch = checkpoint.get("epoch", "?")
            val_loss = checkpoint.get("val_loss", None)
            loss_str = f", val_loss={val_loss:.4f}" if val_loss is not None else ""
            logger.info(f"GNNDetector checkpoint loaded from {path.name} (epoch={epoch}{loss_str})")
            self._checkpoint_loaded = True
        except Exception as e:
            logger.warning(f"Failed to load checkpoint {path}: {e} — using random weights")

    def predict(self, snapshot: GridGraphSnapshot) -> Dict[str, Any]:
        """
        Run GNN inference on a grid snapshot.

        Args:
            snapshot: Current grid state

        Returns:
            dict with keys:
                - type: "GNNDetection" | "NoGNNAnomaly"
                - node_scores: Dict[node_id, anomaly_score]
                - edge_scores: Dict[edge_id, anomaly_score]
                - fault_prediction: FaultPrediction (or None)
                - isolation_nodes: List of top-K affected node IDs
                - severity: Estimated severity [0, 1]
        """
        self._total_predictions += 1

        # Build PyG Data object
        data = self.grid_builder.build(snapshot)
        if data.num_nodes == 0:
            return {
                "type": "NoGNNAnomaly",
                "node_scores": {},
                "edge_scores": {},
                "fault_prediction": None,
                "isolation_nodes": [],
                "severity": 0.0,
            }

        # Move to device
        data = data.to(self.device)
        batch = torch.zeros(data.num_nodes, dtype=torch.long, device=self.device)

        # RGATv2 forward pass
        with torch.no_grad():
            rgat_out = self.rgatv2.forward(data.x, data.edge_index, data.edge_attr, batch)
            cls_out = self.classifier.forward(
                rgat_out["graph_feat"],
                rgat_out["node_embeddings"],
                rgat_out["node_scores"],
                batch,
            )

        # Physics-calibrated node scores
        vm_pu = data.x[:, 0] if data.x.size(1) > 0 else torch.ones(data.num_nodes, device=self.device)
        calibrated_scores = calibrate_with_physics(rgat_out["node_scores"], vm_pu)

        # Build node_id -> score mapping
        node_scores: Dict[str, float] = {}
        for i, node in enumerate(snapshot.nodes):
            score = float(calibrated_scores[i].cpu().item())
            node_scores[node.id] = score

        # Build edge_id -> score mapping
        edge_scores: Dict[str, float] = {}
        for i, edge in enumerate(snapshot.edges):
            if i < rgat_out["edge_scores"].size(0):
                score = float(rgat_out["edge_scores"][i].cpu().item())
                edge_scores[edge.id] = score

        # Determine fault type
        fault_probs = cls_out["fault_probs"].cpu().squeeze(0)
        fault_type_idx = int(fault_probs.argmax().item())
        fault_confidence = float(fault_probs[fault_type_idx].item())
        fault_type = FaultType(fault_type_idx)

        severity = float(cls_out["severity"].cpu().squeeze(0).item())

        # Top-K isolation nodes
        sorted_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)
        isolation_nodes = [nid for nid, s in sorted_nodes if s > 0.3][:10]

        # Build prediction
        prediction = FaultPrediction(
            fault_type=fault_type,
            confidence=fault_confidence,
            node_anomaly_scores=node_scores,
            edge_anomaly_scores=edge_scores,
            severity_score=severity,
            isolation_nodes=isolation_nodes,
            topology_hash=snapshot.topology_hash,
            explanation=self._generate_explanation(fault_type, fault_confidence, severity, len(isolation_nodes)),
        )

        # Detect if there's actually an anomaly (non-normal with confidence)
        is_anomaly = fault_type != FaultType.NORMAL and fault_confidence > 0.4
        if is_anomaly:
            self._anomaly_predictions += 1

        return {
            "type": "GNNDetection" if is_anomaly else "NoGNNAnomaly",
            "node_scores": node_scores,
            "edge_scores": edge_scores,
            "fault_prediction": prediction,
            "isolation_nodes": isolation_nodes,
            "severity": severity,
        }

    def _generate_explanation(
        self, fault_type: FaultType, confidence: float,
        severity: float, num_isolation_nodes: int,
    ) -> str:
        """Generate a human-readable explanation of the GNN prediction."""
        desc = FaultType.descriptions().get(fault_type.value, "Unknown fault type")
        parts = [
            f"GNN detected {fault_type.name.replace('_', '-')}: {desc}",
        ]
        if num_isolation_nodes > 0:
            parts.append(f"Top-{min(num_isolation_nodes, 5)} affected buses identified for isolation")
        if severity > 0.6:
            parts.append(f"High severity ({severity:.0%}) — immediate action recommended")
        return " | ".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Return detection statistics."""
        return {
            "total_predictions": self._total_predictions,
            "anomaly_predictions": self._anomaly_predictions,
            "checkpoint_loaded": self._checkpoint_loaded,
            "device": str(self.device),
            "model_params": sum(p.numel() for p in self.rgatv2.parameters()),
        }

    def to_explanation_packet(
        self, snapshot: GridGraphSnapshot, result: Dict[str, Any]
    ) -> Optional[ExplanationPacket]:
        """Convert GNN result to ExplanationPacket for the ensemble pipeline."""
        if result["type"] == "NoGNNAnomaly":
            return None

        pred = result["fault_prediction"]
        if pred is None:
            return None

        # Build node scores for the explanation
        node_scores_list = [
            EntityScore(id=nid, score=float(score * 100))
            for nid, score in list(pred.node_anomaly_scores.items())[:10]
        ]

        return ExplanationPacket(
            schema_version=SCHEMA_VERSION,
            t=snapshot.t,
            model_version="gnn-rgatv2-v1.0",
            target={
                "type": pred.fault_type.name.replace("_", "-"),
                "confidence": round(pred.confidence, 4),
                "severity": round(pred.severity_score, 4),
                "isolation_nodes": pred.isolation_nodes[:5],
            },
            uncertainty={
                "mode": "low",
                "ensemble_size": 1,
                "detectors_triggered": len(pred.isolation_nodes),
            },
            physics_residuals={
                "explanation": pred.explanation,
            },
            explanations=[
                Explanation(
                    type="GNNGraphAttention",
                    node_scores=node_scores_list,
                    edge_scores=[
                        EntityScore(id=eid, score=float(score * 100))
                        for eid, score in list(pred.edge_anomaly_scores.items())[:10]
                    ],
                    feature_scores=[],
                    confidence=pred.confidence,
                )
            ],
            ml_confidence=pred.confidence,
        )
