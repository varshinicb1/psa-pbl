from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from dt_contracts.models import EntityScore, Explanation, ExplanationPacket, GridGraphSnapshot, SCHEMA_VERSION

from .base import TwinModel, TwinModelOutput


class PhysicsRuleModel(TwinModel):
    """
    Baseline "physics-informed" model for the PoC (no learning yet).

    This is intentionally not a conventional classifier:
    - it consumes the full topology-aware snapshot
    - it emits an operator-facing ExplanationPacket (worst violating buses)
    - it supports fail-safe behavior (no silent failure)
    """

    def __init__(self, *, v_bounds_pu: Tuple[float, float] = (0.95, 1.05)) -> None:
        self.vmin, self.vmax = v_bounds_pu

    def predict(self, snapshot: GridGraphSnapshot) -> TwinModelOutput:
        violating: List[Tuple[float, str]] = []

        for n in snapshot.nodes:
            vm = n.dynamic.get("vm_pu")
            if vm is None:
                continue
            vm = float(vm)
            dev = max(0.0, vm - self.vmax, self.vmin - vm)
            if dev > 0:
                violating.append((dev, n.id))

        violating.sort(reverse=True)
        top = violating[:10]

        if not top:
            return TwinModelOutput(prediction={"type": "NoAnomaly"}, explanation=None)

        node_scores = [EntityScore(id=nid, score=float(dev)) for dev, nid in top]
        exp = ExplanationPacket(
            schema_version=SCHEMA_VERSION,
            t=snapshot.t,
            model_version="physics-rule-v0",
            target={"type": "VoltageAnomaly", "bounds_pu": [self.vmin, self.vmax]},
            uncertainty={"mode": "low"},
            physics_residuals={"rule": "vm_pu_out_of_bounds"},
            explanations=[Explanation(type="SubgraphAttribution", node_scores=node_scores, edge_scores=[], feature_scores=[])],
        )
        return TwinModelOutput(prediction={"type": "VoltageAnomaly", "count": len(violating)}, explanation=exp)

