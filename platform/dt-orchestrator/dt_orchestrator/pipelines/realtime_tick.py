"""
Real-time digital twin tick loop for grid state updates and anomaly detection.

Handles: telemetry injection → powerflow → state update → explainability.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

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

logger = get_logger(__name__)

# Voltage anomaly detection constants (per unit)
VOLTAGE_LOWER_BOUND = 0.95
VOLTAGE_UPPER_BOUND = 1.05
VOLTAGE_ANOMALY_TOP_N = 10  # Report worst N nodes


@dataclass
class TickOutputs:
    """Output from a single tick execution."""

    snapshot: GridGraphSnapshot
    explanation: Optional[ExplanationPacket]
    metrics: Dict[str, Any]


class RealtimeTickRunner:
    """
    Near-real-time loop for the Grid Digital Twin.

    Responsibilities:
    - Maintain canonical GridGraph state
    - Run AC powerflow simulation (pandapower)
    - Produce explainable anomaly flags based on physics (vm_pu bounds)
    - Emit structured telemetry

    NOT a classifier: uses physics-derived heuristics, not ML.
    """

    def __init__(self, *, grid_id: str = "demo-grid", seed: int = 7) -> None:
        """
        Initialize the tick runner.

        Args:
            grid_id: Grid identifier for external references
            seed: Random seed for synthetic telemetry
        """
        logger.debug(f"Initializing RealtimeTickRunner grid_id={grid_id} seed={seed}")
        self.rng = random.Random(seed)
        self.adapter = PandapowerAdapter(grid_id=grid_id)

        try:
            self.net, snap = self.adapter.build_ieee14()
            logger.info(f"Loaded IEEE-14 network: {len(snap.nodes)} buses, {len(snap.edges)} edges")
        except Exception as exc:
            logger.error(f"Failed to load IEEE-14 network: {exc}")
            raise TickExecutionError(f"Network initialization failed: {exc}") from exc

        self.store = GridGraphStore(history_limit=500)
        self.store.set_latest(snap)

        # Cache baseline loads for synthetic perturbations
        self._base_loads: Optional[Tuple[list[float], list[float]]] = None
        try:
            if hasattr(self.net, "load") and len(self.net.load) > 0:
                self._base_loads = (self.net.load.p_mw.tolist(), self.net.load.q_mvar.tolist())
                logger.debug(f"Cached {len(self._base_loads[0])} load values for telemetry injection")
        except Exception as exc:
            logger.warning(f"Failed to cache baseline loads: {exc}")

    def inject_synthetic_telemetry(self) -> None:
        """
        Perturb loads slightly to emulate streaming conditions.

        Range: ±2% random variation on each load.
        """
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
            # Non-fatal: continue without perturbation

    def run_one_tick(self) -> TickOutputs:
        """
        Execute one simulation tick.

        Returns:
            TickOutputs with snapshot, explanation, and metrics

        Raises:
            TickExecutionError: If tick execution fails
            StateError: If state management fails
        """
        try:
            self.inject_synthetic_telemetry()

            # Run powerflow
            run_info = self.adapter.run_powerflow(self.net)

            # Update snapshot with new timestamp
            latest = self.store.get_latest()
            if not latest:
                raise StateError("No previous snapshot available")

            snap = latest.model_copy(update={"t": utc_now_iso(), "schema_version": SCHEMA_VERSION})
            snap2 = self.adapter.apply_results_to_snapshot(snap, self.net)
            self.store.set_latest(snap2)

            # Generate explanation if needed
            explanation = self._physics_explain_anomaly(snap2, solved=run_info.solved)

            return TickOutputs(
                snapshot=snap2, explanation=explanation, metrics={"solved": run_info.solved}
            )

        except StateError:
            raise
        except Exception as exc:
            logger.error(f"Tick execution failed: {exc}")
            raise TickExecutionError(f"Tick failed: {exc}") from exc

    def _physics_explain_anomaly(
        self, snapshot: GridGraphSnapshot, *, solved: bool
    ) -> Optional[ExplanationPacket]:
        """
        Generate explainability packet based on physics-derived state.

        Highlights buses with voltage magnitude deviations outside bounds [LOWER, UPPER].

        Args:
            snapshot: Grid snapshot with voltage results
            solved: Whether powerflow converged

        Returns:
            ExplanationPacket if anomaly detected, None otherwise
        """
        if not solved:
            logger.warning("Powerflow did not converge - anomaly: solver failure")
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
                        rationale="Power flow did not converge. Recommend: verify topology, check extreme setpoints/loads, rerun with different init/algorithm.",
                    )
                ],
            )

        # Identify nodes with voltage magnitude violations
        worst = []
        for n in snapshot.nodes:
            vm = n.dynamic.get("vm_pu")
            if vm is None:
                continue

            try:
                vm_val = float(vm)
                # Deviation: how far outside the bounds
                dev = max(0.0, vm_val - VOLTAGE_UPPER_BOUND, VOLTAGE_LOWER_BOUND - vm_val)
                if dev > 0:
                    worst.append((dev, n.id))
            except (ValueError, TypeError):
                logger.debug(f"Invalid vm_pu value for node {n.id}: {vm}")
                continue

        worst.sort(reverse=True)
        worst = worst[:VOLTAGE_ANOMALY_TOP_N]

        if not worst:
            logger.debug("No voltage anomalies detected")
            return None

        logger.warning(f"Voltage anomaly detected: {len(worst)} nodes out of bounds")

        node_scores = [EntityScore(id=nid, score=float(dev)) for dev, nid in worst]
        return ExplanationPacket(
            schema_version=SCHEMA_VERSION,
            t=snapshot.t,
            model_version="physics-rule-v0",
            target={"type": "VoltageAnomaly", "bounds_pu": [VOLTAGE_LOWER_BOUND, VOLTAGE_UPPER_BOUND]},
            uncertainty={"mode": "low"},
            physics_residuals={"rule": "vm_pu_out_of_bounds"},
            explanations=[
                Explanation(
                    type="SubgraphAttribution",
                    node_scores=node_scores,
                    edge_scores=[],
                    feature_scores=[],
                )
            ],
        )

