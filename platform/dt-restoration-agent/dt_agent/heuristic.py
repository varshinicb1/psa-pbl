"""
Heuristic-based grid restoration agent.

Conservative baseline restoration advisor (shadow/advisory mode).
NOT automatic action execution - for approval/validation only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

from dt_contracts.logging_config import get_logger
from dt_contracts.models import Action, ActionPlan, GridGraphSnapshot, SCHEMA_VERSION
from dt_contracts.utils import utc_now_iso
from dt_contracts.exceptions import StateError

logger = get_logger(__name__)


@dataclass(frozen=True)
class RestorationDecision:
    """Advisory restoration decision."""

    plan: ActionPlan
    rationale: str


class HeuristicRestorationAgent:
    """
    Conservative baseline restoration agent for grid recovery.

    Responsibilities:
    - Identify controllable switch edges
    - Propose low-risk restoration actions
    - NEVER execute automatically - advisory only

    Current implementation:
    - Emits no-op plan if no switches available
    - For future: use optimization/heuristics for switch sequencing
    """

    def propose(self, snapshot: GridGraphSnapshot) -> RestorationDecision:
        """
        Propose a restoration action plan.

        Args:
            snapshot: Current grid snapshot

        Returns:
            RestorationDecision with ActionPlan and rationale

        Note:
            This is ADVISORY. Manual approval required before enactment.
        """
        try:
            switches = [e for e in snapshot.edges if e.type.lower() == "switch"]

            if not switches:
                logger.info("No controllable switches found - advisory: no-op plan")
                plan = ActionPlan(
                    schema_version=SCHEMA_VERSION,
                    t=snapshot.t,
                    plan_id="noop",
                    actions=[],
                )
                return RestorationDecision(
                    plan=plan,
                    rationale="No controllable switch edges found; emitting no-op plan (shadow advisory mode).",
                )

            # Advisory: Future iterations will use optimization
            # Current: emit no-op to prevent accidental execution
            logger.info(f"Found {len(switches)} controllable switches - awaiting optimization implementation")
            plan = ActionPlan(
                schema_version=SCHEMA_VERSION,
                t=snapshot.t,
                plan_id="advisory_noop",
                actions=[],
            )
            return RestorationDecision(
                plan=plan,
                rationale=f"Found {len(switches)} switches but optimization not yet implemented. Emitting advisory no-op. Future: heuristic switch sequencing.",
            )

        except Exception as exc:
            logger.error(f"Restoration proposal failed: {exc}")
            raise StateError(f"Failed to propose restoration plan: {exc}") from exc

