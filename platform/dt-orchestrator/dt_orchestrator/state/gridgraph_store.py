from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from dt_contracts.models import GridGraphSnapshot


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GridGraphStore:
    """
    In-memory canonical store for the PoC.

    Design notes:
    - topology is versioned via (topology_hash, topology_version)
    - dynamic fields are updated every tick from simulator results
    - history is kept for replay/debug in PoC (bounded list)
    """

    history_limit: int = 200
    latest: Optional[GridGraphSnapshot] = None
    history: List[GridGraphSnapshot] = field(default_factory=list)

    def set_latest(self, snapshot: GridGraphSnapshot) -> None:
        self.latest = snapshot
        self.history.append(snapshot)
        if len(self.history) > self.history_limit:
            self.history = self.history[-self.history_limit :]

    def get_latest(self) -> GridGraphSnapshot:
        if self.latest is None:
            raise RuntimeError("GridGraphStore has no snapshot yet.")
        return self.latest

    def touch_time(self) -> None:
        """
        Update the snapshot time without changing topology.
        """
        snap = self.get_latest()
        self.set_latest(snap.model_copy(update={"t": _utc_now_iso()}))

