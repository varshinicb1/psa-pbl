from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from dt_contracts.models import Action, ActionPlan, GridGraphSnapshot, SCHEMA_VERSION


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RestorationDecision:
    plan: ActionPlan
    rationale: str


class HeuristicRestorationAgent:
    """
    Conservative baseline restoration agent (shadow/advisory).

    PoC behavior:
    - identify controllable switch edges (type == 'Switch')
    - if none exist (common for IEEE transmission cases), emit a no-op plan
    """

    def propose(self, snapshot: GridGraphSnapshot) -> RestorationDecision:
        switches = [e for e in snapshot.edges if e.type.lower() == "switch"]

        if not switches:
            plan = ActionPlan(schema_version=SCHEMA_VERSION, t=snapshot.t, plan_id="noop", actions=[])
            return RestorationDecision(plan=plan, rationale="No controllable switch edges found; emitting no-op plan (shadow mode).")

        # Placeholder: pick the first switch and propose toggling it (DO NOT EXECUTE automatically).
        sw = switches[0]
        current = bool(sw.dynamic.get("closed", True))
        actions: List[Action] = [
            Action(type="SwitchAction", device_id=sw.id, desired_state=not current, effective_time=_utc_now_iso())
        ]
        plan = ActionPlan(schema_version=SCHEMA_VERSION, t=snapshot.t, plan_id="toggle_first_switch", actions=actions)
        return RestorationDecision(plan=plan, rationale=f"Placeholder: toggling {sw.id} (current closed={current}). Validate with PF before enactment.")

