from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import pandapower as pp

from dt_contracts.models import (
    EntityScore,
    Explanation,
    ExplanationPacket,
    GridGraphSnapshot,
    SCHEMA_VERSION,
)
from dt_sim_pandapower.adapter import PandapowerAdapter

from ..state.gridgraph_store import GridGraphStore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TickOutputs:
    snapshot: GridGraphSnapshot
    explanation: Optional[ExplanationPacket]
    metrics: Dict[str, Any]


class RealtimeTickRunner:
    """
    Near-real-time loop for the PoC.

    This is intentionally NOT a "fault detection classifier".
    It is a topology-aware digital-twin loop that:
    - updates a canonical GridGraph state
    - runs a physics solver (pandapower PF)
    - produces explainable anomaly flags based on physics-derived state (vm_pu bounds)
    """

    def __init__(self, *, grid_id: str = "demo-grid", seed: int = 7) -> None:
        self.rng = random.Random(seed)
        self.adapter = PandapowerAdapter(grid_id=grid_id)
        self.net, snap = self.adapter.build_ieee14()
        self.store = GridGraphStore(history_limit=500)
        self.store.set_latest(snap)

        # Cache baseline loads for synthetic telemetry injection
        self._base_loads: Optional[Tuple[list[float], list[float]]] = None
        if hasattr(self.net, "load") and len(self.net.load) > 0:
            self._base_loads = (self.net.load.p_mw.tolist(), self.net.load.q_mvar.tolist())

    def inject_synthetic_telemetry(self) -> None:
        """
        PoC: randomly perturb loads slightly to emulate streaming conditions.
        """
        if self._base_loads is None:
            return
        base_p, base_q = self._base_loads
        for i in range(len(base_p)):
            scale = 1.0 + self.rng.uniform(-0.02, 0.02)
            self.net.load.at[i, "p_mw"] = base_p[i] * scale
            self.net.load.at[i, "q_mvar"] = base_q[i] * scale

    def run_one_tick(self) -> TickOutputs:
        self.inject_synthetic_telemetry()

        run_info = self.adapter.run_powerflow(self.net)
        snap = self.store.get_latest().model_copy(update={"t": _utc_now_iso(), "schema_version": SCHEMA_VERSION})
        snap2 = self.adapter.apply_results_to_snapshot(snap, self.net)
        self.store.set_latest(snap2)

        explanation = self._physics_explain_anomaly(snap2, solved=run_info.solved)
        return TickOutputs(snapshot=snap2, explanation=explanation, metrics={"solved": run_info.solved})

    def _physics_explain_anomaly(self, snapshot: GridGraphSnapshot, *, solved: bool) -> Optional[ExplanationPacket]:
        """
        PoC explainability: highlight buses with worst voltage magnitude deviations.
        """
        if not solved:
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

        worst = []
        for n in snapshot.nodes:
            vm = n.dynamic.get("vm_pu")
            if vm is None:
                continue
            dev = max(0.0, float(vm) - 1.05, 0.95 - float(vm))
            if dev > 0:
                worst.append((dev, n.id))
        worst.sort(reverse=True)
        worst = worst[:10]

        if not worst:
            return None

        node_scores = [EntityScore(id=nid, score=float(dev)) for dev, nid in worst]
        return ExplanationPacket(
            schema_version=SCHEMA_VERSION,
            t=snapshot.t,
            model_version="physics-rule-v0",
            target={"type": "VoltageAnomaly", "bounds_pu": [0.95, 1.05]},
            uncertainty={"mode": "low"},
            physics_residuals={"rule": "vm_pu_out_of_bounds"},
            explanations=[Explanation(type="SubgraphAttribution", node_scores=node_scores, edge_scores=[], feature_scores=[])],
        )

