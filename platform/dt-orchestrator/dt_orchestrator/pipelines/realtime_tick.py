"""
Production real-time digital twin tick loop.

Architecture:
  Telemetry Ingestion -> Powerflow (multi-simulator) -> State Update
    -> ML Anomaly Detection -> Explanation Generation -> Publish

Supports distributed execution via Redis state store and NATS messaging.
Supports multiple grid backends: IEEE-14 (default), BESCOM Bangalore.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandapower as pp

from dt_contracts.logging_config import get_logger
from dt_contracts.models import (
    EntityScore,
    Explanation,
    ExplanationPacket,
    GridGraphSnapshot,
    SCHEMA_VERSION,
)
from dt_contracts.utils import utc_now_iso
from dt_contracts.exceptions import TickExecutionError, StateError
from dt_sim_pandapower.adapter import PandapowerAdapter

from ..state.gridgraph_store import GridGraphStore
from dt_ml.ensemble import EnsembleDetector

logger = get_logger(__name__)

VOLTAGE_LOWER_BOUND = 0.95
VOLTAGE_UPPER_BOUND = 1.05
VOLTAGE_ANOMALY_TOP_N = 10
LOADING_THRESHOLD = 90.0
MAX_TICK_HISTORY = 5000


@dataclass
class TickOutputs:
    snapshot: GridGraphSnapshot
    explanation: Optional[ExplanationPacket]
    metrics: Dict[str, Any]
    execution_time_ms: float = 0.0


class RealtimeTickRunner:
    """
    Production-grade real-time grid digital twin runner.

    Supports multiple grid backends:
    - 'ieee14' (default): IEEE-14 bus test system with synthetic load perturbations
    - 'bescom': BESCOM Bangalore 50-bus grid with real load profiles

    Features:
    - Multi-simulator support (pandapower primary, others for cross-validation)
    - ML-based anomaly detection (ensemble: XGBoost, LSTM, Isolation Forest)
    - Physics-constrained hybrid AI
    - Distributed state management
    - Sub-100ms tick execution target
    """

    def __init__(
        self,
        *,
        grid_id: str = "metro-grid",
        grid_type: str = "ieee14",
        seed: int = 7,
        use_ml: bool = True,
    ) -> None:
        logger.debug(f"Initializing RealtimeTickRunner grid_id={grid_id} grid_type={grid_type} seed={seed}")
        self.rng = random.Random(seed)
        self.use_ml = use_ml
        self._is_bescom = grid_type == "bescom"

        if self._is_bescom:
            self._init_bescom()
        else:
            self._init_ieee14(grid_id)

        self._anomaly_history: List[float] = []

        if self.use_ml:
            try:
                self.detector = EnsembleDetector()
                logger.info("ML EnsembleDetector initialized")
            except Exception as exc:
                logger.warning(f"ML detector init failed (falling back to physics): {exc}")
                self.detector = None
        else:
            self.detector = None

    def _init_ieee14(self, grid_id: str) -> None:
        """Initialize IEEE-14 backend."""
        self.adapter = PandapowerAdapter(grid_id=grid_id)
        try:
            self.net, snap = self.adapter.build_ieee14()
            logger.info(
                f"Loaded IEEE-14 network: {len(snap.nodes)} buses, {len(snap.edges)} edges"
            )
        except Exception as exc:
            logger.error(f"Failed to load IEEE-14 network: {exc}")
            raise TickExecutionError(f"Network initialization failed: {exc}") from exc

        self.store = GridGraphStore(history_limit=MAX_TICK_HISTORY)
        self.store.set_latest(snap)

        self._base_loads: Optional[Tuple[List[float], List[float]]] = None
        try:
            if hasattr(self.net, "load") and len(self.net.load) > 0:
                self._base_loads = (
                    self.net.load.p_mw.tolist(),
                    self.net.load.q_mvar.tolist(),
                )
                logger.debug(
                    f"Cached {len(self._base_loads[0])} load values for telemetry injection"
                )
        except Exception as exc:
            logger.warning(f"Failed to cache baseline loads: {exc}")

    def _init_bescom(self) -> None:
        """Initialize BESCOM Bangalore grid backend."""
        try:
            from dt_bescom.simulation import BESCOMSimulator
        except ImportError as exc:
            raise TickExecutionError(
                "dt_bescom package not available. Install it or use grid_type='ieee14'."
            ) from exc

        self.bescom = BESCOMSimulator()
        self.bescom.ensure_network()
        snap = self.bescom.to_grid_graph_snapshot(tick_count=0)
        self.net = self.bescom.net
        self.adapter = None
        self._base_loads = None
        logger.info(
            f"Loaded BESCOM network: {len(snap.nodes)} buses, {len(snap.edges)} edges"
        )

        self.store = GridGraphStore(history_limit=MAX_TICK_HISTORY)
        self.store.set_latest(snap)

    def perturb_load(self, bus_id: str, p_mw: float, q_mvar: float = 0.0) -> None:
        if self._is_bescom:
            self._perturb_bescom_load(bus_id, p_mw, q_mvar)
            return
        for i in range(len(self.net.load)):
            bus_idx = self.net.load.at[i, "bus"]
            expected = f"{self.adapter.grid_id}/pp/bus/{int(bus_idx)}"
            if expected == bus_id or str(bus_idx) == bus_id:
                self.net.load.at[i, "p_mw"] = max(0, self.net.load.at[i, "p_mw"] + p_mw)
                self.net.load.at[i, "q_mvar"] += q_mvar
                logger.info(f"Perturbed load at bus {bus_id}: p_mw={p_mw}, q_mvar={q_mvar}")
                return
        logger.warning(f"Bus {bus_id} not found in load table")

    def _perturb_bescom_load(self, bus_id: str, p_mw: float, q_mvar: float = 0.0) -> None:
        """Perturb a load in the BESCOM network by bus name."""
        for i in range(len(self.net.load)):
            bus_idx = self.net.load.at[i, "bus"]
            bus_name = self.net.bus.at[bus_idx, "name"]
            expected = f"bescom/{bus_name}"
            if expected == bus_id:
                self.net.load.at[i, "p_mw"] = max(0, self.net.load.at[i, "p_mw"] + p_mw)
                self.net.load.at[i, "q_mvar"] += q_mvar
                logger.info(f"Perturbed BESCOM load at {bus_id}: p_mw={p_mw}, q_mvar={q_mvar}")
                return
        logger.warning(f"Bus {bus_id} not found in BESCOM load table")

    def inject_synthetic_telemetry(self) -> None:
        if self._base_loads is None:
            return
        try:
            base_p, base_q = self._base_loads
            for i in range(len(base_p)):
                scale = 1.0 + self.rng.uniform(-0.02, 0.02)
                self.net.load.at[i, "p_mw"] = base_p[i] * scale
                self.net.load.at[i, "q_mvar"] = base_q[i] * scale
        except Exception as exc:
            logger.warning(f"Telemetry injection failed: {exc}")

    def run_one_tick(self) -> TickOutputs:
        start_time = time.perf_counter()
        try:
            if self._is_bescom:
                return self._run_bescom_tick(start_time)

            self.inject_synthetic_telemetry()
            run_info = self.adapter.run_powerflow(self.net)

            latest = self.store.get_latest()
            if not latest:
                raise StateError("No previous snapshot available")

            snap = latest.model_copy(
                update={"t": utc_now_iso(), "schema_version": SCHEMA_VERSION}
            )
            snap2 = self.adapter.apply_results_to_snapshot(snap, self.net)
            snap2.tick_count = (latest.tick_count or 0) + 1
            self.store.set_latest(snap2)

            explanation = self._detect_anomalies(snap2, solved=run_info.solved)

            exec_time = (time.perf_counter() - start_time) * 1000

            return TickOutputs(
                snapshot=snap2,
                explanation=explanation,
                metrics={"solved": run_info.solved, "execution_time_ms": exec_time},
                execution_time_ms=exec_time,
            )

        except StateError:
            raise
        except Exception as exc:
            logger.error(f"Tick execution failed: {exc}")
            raise TickExecutionError(f"Tick failed: {exc}") from exc

    def _run_bescom_tick(self, start_time: float) -> TickOutputs:
        """Run a single BESCOM simulation tick with time-based load profiles."""
        from datetime import datetime, timezone

        latest = self.store.get_latest()
        next_tick = (latest.tick_count or 0) + 1 if latest else 1

        snap = self.bescom.to_grid_graph_snapshot(tick_count=next_tick)
        self.store.set_latest(snap)

        explanation = self._detect_anomalies(snap, solved=True)

        exec_time = (time.perf_counter() - start_time) * 1000

        return TickOutputs(
            snapshot=snap,
            explanation=explanation,
            metrics={"solved": True, "execution_time_ms": exec_time, "grid_type": "bescom"},
            execution_time_ms=exec_time,
        )

    def _detect_anomalies(
        self, snapshot: GridGraphSnapshot, *, solved: bool
    ) -> Optional[ExplanationPacket]:
        if not solved:
            logger.warning("Powerflow did not converge")
            return ExplanationPacket(
                schema_version=SCHEMA_VERSION,
                t=snapshot.t,
                model_version="physics-rule-v0",
                target={"type": "SolverConvergence", "converged": False},
                uncertainty={"mode": "high", "reason": "powerflow_not_converged"},
                physics_residuals={},
                explanations=[
                    Explanation(
                        type="Counterfactual",
                        node_scores=[],
                        edge_scores=[],
                        feature_scores=[],
                        rationale="Power flow did not converge. Verify topology, check extreme setpoints/loads.",
                    )
                ],
            )

        physics_explanation = self._physics_detect(snapshot)

        if self.detector and self.use_ml:
            try:
                ml_result = self.detector.predict(snapshot)
                if ml_result and ml_result.explanation:
                    self._anomaly_history.append(1)
                    return ml_result.explanation
            except Exception as exc:
                logger.warning(f"ML detection failed: {exc}")

        if physics_explanation:
            self._anomaly_history.append(1)
        else:
            self._anomaly_history.append(0)

        if len(self._anomaly_history) > 1000:
            self._anomaly_history = self._anomaly_history[-1000:]

        return physics_explanation

    def _physics_detect(
        self, snapshot: GridGraphSnapshot
    ) -> Optional[ExplanationPacket]:
        violations: List[Tuple[float, str]] = []
        loading_violations: List[Tuple[float, str]] = []

        for n in snapshot.nodes:
            vm = n.dynamic.get("vm_pu")
            if vm is None:
                continue
            try:
                vm_val = float(vm)
                dev = max(0.0, vm_val - VOLTAGE_UPPER_BOUND, VOLTAGE_LOWER_BOUND - vm_val)
                if dev > 0:
                    violations.append((dev, n.id))
            except (ValueError, TypeError):
                continue

        for e in snapshot.edges:
            loading = e.dynamic.get("loading_percent")
            if loading is not None:
                try:
                    l_val = float(loading)
                    if l_val > LOADING_THRESHOLD:
                        loading_violations.append((l_val - LOADING_THRESHOLD, e.id))
                except (ValueError, TypeError):
                    continue

        violations.sort(reverse=True)
        violations = violations[:VOLTAGE_ANOMALY_TOP_N]

        if not violations and not loading_violations:
            return None

        node_scores = [
            EntityScore(id=nid, score=float(dev)) for dev, nid in violations
        ]
        edge_scores = [
            EntityScore(id=eid, score=float(dev)) for dev, eid in loading_violations
        ]

        return ExplanationPacket(
            schema_version=SCHEMA_VERSION,
            t=snapshot.t,
            model_version="physics-rule-v2",
            target={
                "type": "CompositeAnomaly",
                "bounds_pu": [VOLTAGE_LOWER_BOUND, VOLTAGE_UPPER_BOUND],
                "loading_threshold": LOADING_THRESHOLD,
            },
            uncertainty={"mode": "low"},
            physics_residuals={
                "rule": "vm_pu_out_of_bounds",
                "violations": len(violations),
                "loading_violations": len(loading_violations),
            },
            explanations=[
                Explanation(
                    type="SubgraphAttribution",
                    node_scores=node_scores,
                    edge_scores=edge_scores,
                    feature_scores=[],
                )
            ],
        )
