"""
Fault classification heads for the RGATv2 GNN.

Defines the 5 power system fault types as well as:
- FaultClassifier: graph-level classification + node-level isolation
- FaultPrediction: structured output with topology attribution
- Physics-constrained output calibration

Fault types (IEEE C37.04 / C37.10 standard categories):
  0. Normal (no fault)
  1. Single-Line-to-Ground (most common)
  2. Line-to-Line-to-Ground
  3. Line-to-Line (phase-to-phase)
  4. Three-Phase (bolted fault, most severe)
  5. Open Circuit (broken conductor)
"""

from __future__ import annotations

import enum
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fault type enum
# ---------------------------------------------------------------------------


class FaultType(int, enum.Enum):
    """IEEE standard power system fault categories."""

    NORMAL = 0
    SINGLE_LINE_TO_GROUND = 1
    LINE_TO_LINE_TO_GROUND = 2
    LINE_TO_LINE = 3
    THREE_PHASE = 4
    OPEN_CIRCUIT = 5

    @classmethod
    def names(cls) -> List[str]:
        return [e.name.replace("_", "-") for e in cls]

    @classmethod
    def descriptions(cls) -> Dict[int, str]:
        return {
            cls.NORMAL.value: "Normal operation — no fault detected",
            cls.SINGLE_LINE_TO_GROUND.value: "Single line to ground — most common, typically caused by lightning or contact",
            cls.LINE_TO_LINE_TO_GROUND.value: "Line-to-line-to-ground — two phases shorted to ground",
            cls.LINE_TO_LINE.value: "Line-to-line (phase-to-phase) — two phases shorted together",
            cls.THREE_PHASE.value: "Three-phase bolted fault — most severe, symmetrical",
            cls.OPEN_CIRCUIT.value: "Open circuit — broken conductor or failed splice",
        }


# ---------------------------------------------------------------------------
# Structured prediction output
# ---------------------------------------------------------------------------


@dataclass
class FaultPrediction:
    """
    Structured output from the GNN fault classifier.

    Attributes:
        fault_type: Predicted fault type (FaultType enum)
        confidence: Overall confidence [0, 1]
        node_anomaly_scores: Per-node anomaly attribution score [0, 1]
        edge_anomaly_scores: Per-edge anomaly attribution score [0, 1]
        severity_score: Estimated severity [0, 1] (0=normal, 1=critical)
        isolation_nodes: Top-K node IDs most likely affected
        topology_hash: Hash of the input topology snapshot
        explanation: Human-readable summary of the prediction
    """

    fault_type: FaultType
    confidence: float
    node_anomaly_scores: Dict[str, float]
    edge_anomaly_scores: Dict[str, float]
    severity_score: float
    isolation_nodes: List[str]
    topology_hash: str
    explanation: str


# ---------------------------------------------------------------------------
# Fault Classifier module
# ---------------------------------------------------------------------------


class FaultClassifier(nn.Module):
    """
    Fault classification and isolation module built on top of RGATv2.

    Architecture:
        - Takes RGATv2 graph-level embedding + per-node embeddings
        - Multi-head classifier with temperature scaling
        - Node-level isolation head for affected bus identification
        - Severity regression head
        - Output calibrated with temperature scaling
    """

    def __init__(
        self,
        latent_dim: int = 64,
        hidden_dim: int = 32,
        node_feat_dim: int = 128,  # RGATv2 hidden_dim for node_embeddings
        num_fault_types: int = 6,
        dropout: float = 0.15,
        temperature: float = 1.0,
    ):
        super().__init__()
        self.num_fault_types = num_fault_types
        # Learned temperature parameter (must init before setter)
        self.log_temperature = nn.Parameter(torch.zeros(1))
        self.temperature = temperature  # calls setter to bake initial value

        # --- Fault type classifier (graph-level) ---
        self.classifier = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ELU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(hidden_dim // 2, num_fault_types),
        )

        # --- Node-level isolation head ---
        # Takes concatenated [node_embeddings (node_feat_dim), node_anomaly_scores (1)]
        iso_input_dim = node_feat_dim + 1
        self.isolation_head = nn.Sequential(
            nn.Linear(iso_input_dim, hidden_dim),
            nn.ELU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(hidden_dim, 1),
        )

        # --- Severity regression head ---
        self.severity_head = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim // 2),
            nn.ELU(),
            nn.Dropout(dropout * 0.3),
            nn.Linear(hidden_dim // 2, 1),
        )

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight, gain=0.8)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    @property
    def temperature(self) -> float:
        return self.log_temperature.exp().item()

    @temperature.setter
    def temperature(self, value: float) -> None:
        self.log_temperature.data.fill_(math.log(max(value, 0.01)))

    def forward(
        self,
        graph_feat: torch.Tensor,           # [B, latent_dim]  graph-level
        node_embeddings: torch.Tensor,       # [N, hidden_dim]  per-node
        node_anomaly_scores: torch.Tensor,   # [N, 1]           from RGATv2
        batch: torch.Tensor,                 # [N]
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass through fault classification and isolation heads.

        Returns:
            dict with keys:
                fault_logits:    [B, num_fault_types] — uncalibrated logits
                fault_probs:     [B, num_fault_types] — temperature-scaled softmax
                isolation_scores: [N, 1] — per-node anomaly attribution
                severity:        [B, 1] — normalised severity [0, 1]
        """
        # Graph-level fault classification
        fault_logits = self.classifier(graph_feat)  # [B, num_fault_types]
        fault_probs = F.softmax(fault_logits / self.log_temperature.exp(), dim=-1)

        # Node-level isolation
        # Combine node embeddings with RGATv2 anomaly scores as bias
        iso_input = torch.cat([node_embeddings, node_anomaly_scores], dim=-1)
        isolation_scores = torch.sigmoid(self.isolation_head(iso_input))  # [N, 1]

        # Severity regression (bounded to [0, 1])
        severity = torch.sigmoid(self.severity_head(graph_feat))  # [B, 1]

        return {
            "fault_logits": fault_logits,
            "fault_probs": fault_probs,
            "isolation_scores": isolation_scores,
            "severity": severity,
        }


# ---------------------------------------------------------------------------
# Physics-constrained output calibration
# ---------------------------------------------------------------------------

def calibrate_with_physics(
    node_anomaly_scores: torch.Tensor,
    vm_pu: torch.Tensor,
    v_min: float = 0.90,
    v_max: float = 1.10,
) -> torch.Tensor:
    """
    Physics-constrained calibration of GNN anomaly scores.

    Boosts scores for nodes where voltage is outside physics bounds,
    even if the GNN assigns a low score (reducing false negatives).

    Args:
        node_anomaly_scores: Raw GNN anomaly scores [N, 1]
        vm_pu: Voltage magnitudes [N]
        v_min, v_max: Physics voltage bounds (p.u.)

    Returns:
        Calibrated anomaly scores [N, 1]
    """
    # Deviation from nominal (1.0 p.u.)
    volt_dev = torch.abs(vm_pu - 1.0)
    # Physics-boost factor: linear ramp from 0 at bound to 0.3 at extreme
    phys_boost = torch.clamp((volt_dev - (1.0 - v_min)) / (v_max - 1.0), min=0.0, max=0.3)
    calibrated = node_anomaly_scores.squeeze(-1) + phys_boost
    return torch.clamp(calibrated, 0.0, 1.0).unsqueeze(-1)


def predict_explanation(
    fault_pred: FaultPrediction,
    node_ids: List[str],
    edge_ids: List[str],
) -> str:
    """
    Generate a human-readable explanation of the GNN fault prediction.

    Args:
        fault_pred: Structured fault prediction
        node_ids: Full list of node IDs in the grid
        edge_ids: Full list of edge IDs in the grid

    Returns:
        Formatted explanation string
    """
    parts = [
        f"Fault type: {fault_pred.fault_type.name.replace('_', '-')} "
        f"(confidence={fault_pred.confidence:.1%})"
    ]

    if fault_pred.severity_score > 0.7:
        parts.append(f"Severity: CRITICAL ({fault_pred.severity_score:.0%})")
    elif fault_pred.severity_score > 0.4:
        parts.append(f"Severity: HIGH ({fault_pred.severity_score:.0%})")
    else:
        parts.append(f"Severity: LOW ({fault_pred.severity_score:.0%})")

    if fault_pred.isolation_nodes:
        top_nodes = fault_pred.isolation_nodes[:5]
        parts.append(f"Affected buses: {', '.join(top_nodes)}")

    parts.append(fault_pred.explanation)
    return " | ".join(parts)
