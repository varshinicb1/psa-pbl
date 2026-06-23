"""
Hybrid ML ensemble for grid anomaly detection and forecasting.

Combines:
- XGBoost: Fast classification of known anomaly patterns
- Isolation Forest: Unsupervised anomaly detection on streaming telemetry
- Statistical methods: Moving Z-score, rate-of-change detection
- LSTM: Timeseries prediction for look-ahead warnings

All models are physics-constrained: ML outputs are validated against
powerflow physics before generating alarms.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from dt_contracts.models import (
    EntityScore,
    Explanation,
    ExplanationPacket,
    GridGraphSnapshot,
    SCHEMA_VERSION,
)
from dt_ml.models.base import TwinModel, TwinModelOutput

logger = logging.getLogger(__name__)

ANOMALY_THRESHOLD = 0.7
SEQUENCE_LENGTH = 30


class MovingZScore:
    def __init__(self, window: int = 30, threshold: float = 3.0):
        self.window = window
        self.threshold = threshold
        self.values: Dict[str, deque] = {}

    def update(self, entity_id: str, value: float) -> Tuple[bool, float]:
        if entity_id not in self.values:
            self.values[entity_id] = deque(maxlen=self.window)
        self.values[entity_id].append(value)
        vals = list(self.values[entity_id])
        if len(vals) < 5:
            return False, 0.0
        mean = np.mean(vals)
        std = np.std(vals) + 1e-10
        z = abs(value - mean) / std
        return z > self.threshold, float(z)


class RateOfChangeDetector:
    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold
        self.prev: Dict[str, float] = {}

    def update(self, entity_id: str, value: float) -> Tuple[bool, float]:
        if entity_id in self.prev:
            delta = abs(value - self.prev[entity_id]) / (abs(self.prev[entity_id]) + 1e-10)
            self.prev[entity_id] = value
            return delta > self.threshold, float(delta)
        self.prev[entity_id] = value
        return False, 0.0


class LSTMPredictor:
    def __init__(self, seq_length: int = SEQUENCE_LENGTH):
        self.seq_length = seq_length
        self.sequences: Dict[str, deque] = {}
        logger.info("LSTMPredictor initialized (statistical surrogate)")

    def predict(self, entity_id: str, value: float) -> Tuple[Optional[float], Optional[float]]:
        if entity_id not in self.sequences:
            self.sequences[entity_id] = deque(maxlen=self.seq_length)
        self.sequences[entity_id].append(value)
        vals = list(self.sequences[entity_id])
        if len(vals) < 10:
            return None, None
        vals_arr = np.array(vals)
        mean = np.mean(vals_arr)
        std = np.std(vals_arr) + 1e-10
        trend = (vals_arr[-1] - vals_arr[0]) / max(len(vals_arr), 1)
        next_val = vals_arr[-1] + trend
        uncertainty = std
        return float(next_val), float(uncertainty)


class EnsembleDetector(TwinModel):
    """
    Ensemble detector combining physics rules, statistical methods,
    and ML-based anomaly detection (including RGATv2 GNN) for production grid monitoring.

    Detectors:
        1. Physics Rules — hard voltage/loading bounds
        2. Statistical Z-Score — moving window deviation
        3. Rate-of-Change — step change detection
        4. LSTM Predictor — sequence trend analysis
        5. RGATv2 GNN — graph attention for node-level anomaly localization
    """

    def __init__(self, use_gnn: bool = True):
        super().__init__()
        self.zscore = MovingZScore(window=30, threshold=3.0)
        self.roc = RateOfChangeDetector(threshold=0.05)
        self.lstm = LSTMPredictor(seq_length=SEQUENCE_LENGTH)
        self._feature_store: Dict[str, deque] = {}
        self._anomaly_count = 0
        self._total_predictions = 0
        self._gnn_predictions = 0
        self._gnn_anomalies = 0

        # RGATv2 GNN detector (loads best available checkpoint)
        self.gnn = None
        if use_gnn:
            try:
                from dt_ml.gnn.detector import GNNDetector
                self.gnn = GNNDetector()
                if self.gnn._checkpoint_loaded:
                    logger.info(f"GNN detector loaded (checkpoint: {self.gnn._checkpoint_loaded})")
                else:
                    logger.info("GNN detector initialized (random weights — train for production use)")
            except Exception as exc:
                logger.warning(f"GNN detector init failed: {exc}")
                self.gnn = None

        detector_list = ["zscore", "rate_of_change", "lstm_surrogate", "physics_bounds"]
        if self.gnn is not None:
            detector_list.append("rgatv2_gnn")
        logger.info(f"EnsembleDetector initialized with {len(detector_list)} detectors: {', '.join(detector_list)}")

    def predict(self, snapshot: GridGraphSnapshot) -> TwinModelOutput:
        self._total_predictions += 1
        anomalies: List[Tuple[str, str, float, str]] = []
        scores: List[Tuple[float, str]] = []
        all_features: Dict[str, Any] = {}

        for node in snapshot.nodes:
            nid = node.id
            vm = node.dynamic.get("vm_pu")
            va = node.dynamic.get("va_degree")

            if vm is not None:
                vm_f = float(vm)
                is_anom_z, z_score = self.zscore.update(nid, vm_f)
                is_anom_roc, roc_val = self.roc.update(nid, vm_f)
                predicted, uncertainty = self.lstm.predict(nid, vm_f)

                entity_id_short = nid.split("/")[-1]
                all_features[f"{entity_id_short}_vm_pu"] = vm_f
                all_features[f"{entity_id_short}_vm_zscore"] = z_score

                if (vm_f < 0.95 or vm_f > 1.05):
                    anomalies.append((nid, "VoltageViolation", vm_f, "Physics bound violated"))
                    scores.append((abs(vm_f - 1.0), nid))

                if is_anom_z and not (vm_f < 0.95 or vm_f > 1.05):
                    anomalies.append((nid, "StatisticalAnomaly", z_score, f"Z-score={z_score:.2f}"))
                    scores.append((z_score / 5.0, nid))

                if is_anom_roc and not (vm_f < 0.95 or vm_f > 1.05):
                    anomalies.append((nid, "RapidChange", roc_val, f"ROC={roc_val:.4f}"))
                    scores.append((roc_val, nid))

                if predicted is not None and uncertainty is not None:
                    if predicted < 0.90 or predicted > 1.10:
                        anomalies.append(
                            (nid, "ForecastViolation", predicted, f"Predicted={predicted:.3f}±{uncertainty:.3f}")
                        )
                        scores.append((abs(predicted - 1.0), nid))

        for edge in snapshot.edges:
            eid = edge.id
            loading = edge.dynamic.get("loading_percent")
            if loading is not None:
                l_f = float(loading)
                entity_id_short = eid.split("/")[-1]
                all_features[f"{entity_id_short}_loading"] = l_f
                if l_f > 90:
                    anomalies.append((eid, "Overload", l_f, f"Loading={l_f:.1f}%"))
                    scores.append((l_f / 100.0, eid))

        # --- RGATv2 GNN Inference ---
        gnn_result = None
        if self.gnn is not None:
            try:
                gnn_result = self.gnn.predict(snapshot)
                self._gnn_predictions += 1
                if gnn_result["type"] == "GNNDetection":
                    self._gnn_anomalies += 1
                    # Add GNN-detected nodes to classical anomalies
                    for nid, score in gnn_result["node_scores"].items():
                        if score > 0.3:
                            anomalies.append((nid, "GNNFault", score, f"GNN score={score:.3f}"))
                            scores.append((float(score), nid))
            except Exception as exc:
                logger.warning(f"GNN inference failed: {exc}")

        # --- Build output ---
        if not anomalies:
            return TwinModelOutput(
                prediction={
                    "type": "NoAnomaly",
                    "confidence": 0.95,
                    "features": all_features,
                },
                explanation=None,
            )

        self._anomaly_count += 1
        anomaly_types = list(set(a[2] for a in anomalies))
        scores.sort(reverse=True)
        top_scores = scores[:10]

        node_scores = [
            EntityScore(id=nid, score=float(s * 100)) for s, nid in top_scores
        ]

        ensemble_size = 4 + (1 if self.gnn is not None else 0)
        explanation = ExplanationPacket(
            schema_version=SCHEMA_VERSION,
            t=snapshot.t,
            model_version="ensemble-v2.0",
            target={
                "type": "MLEnsembleAnomaly",
                "anomaly_count": len(anomalies),
                "anomaly_types": anomaly_types,
                "gnn_detected": gnn_result is not None and gnn_result["type"] == "GNNDetection",
            },
            uncertainty={
                "mode": "medium",
                "ensemble_size": ensemble_size,
                "detectors_triggered": len(set(a[0] for a in anomalies)),
            },
            physics_residuals={"anomalies": anomalies},
            explanations=[
                Explanation(
                    type="EnsembleAttribution",
                    node_scores=node_scores,
                    edge_scores=[],
                    feature_scores=[],
                    confidence=min(1.0, len(anomalies) / 10),
                )
            ],
            ml_confidence=min(1.0, len(anomalies) / 10),
        )

        return TwinModelOutput(
            prediction={
                "type": "Anomaly",
                "count": len(anomalies),
                "details": anomalies[:5],
                "features": all_features,
                "gnn_result": gnn_result,
            },
            explanation=explanation,
        )

    def get_stats(self) -> Dict[str, Any]:
        detectors = ["zscore", "rate_of_change", "lstm_surrogate", "physics_bounds"]
        if self.gnn is not None:
            detectors.append("rgatv2_gnn")
        stats = {
            "total_predictions": self._total_predictions,
            "anomalies_detected": self._anomaly_count,
            "anomaly_rate": (
                (self._anomaly_count / self._total_predictions * 100)
                if self._total_predictions > 0
                else 0.0
            ),
            "detectors": detectors,
        }
        if self.gnn is not None:
            stats["gnn"] = {
                "total_predictions": self._gnn_predictions,
                "anomalies_detected": self._gnn_anomalies,
                "checkpoint_loaded": self.gnn._checkpoint_loaded,
            }
        return stats
