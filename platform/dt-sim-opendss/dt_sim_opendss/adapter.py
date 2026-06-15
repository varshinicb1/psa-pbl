from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from dt_contracts.models import GridGraphSnapshot
from dt_contracts.utils import utc_now_iso, stable_hash


class OpenDSSBackendUnavailable(RuntimeError):
    pass


@dataclass
class OpenDSSConfig:
    """
    Configuration for OpenDSS execution.
    """

    master_dss_path: str
    grid_id: str = "demo-grid"


class OpenDSSAdapter:
    """
    Skeleton adapter around OpenDSSDirect.py.

    Intended responsibilities (next iterations):
    - compile/load OpenDSS model from master .dss
    - enumerate circuit objects (buses, lines, transformers, loads, switches, controls)
    - project into canonical GridGraphSnapshot with stable IDs and external_refs
    - run solve and extract per-phase results (V, I, P/Q) into dynamic attrs
    """

    def __init__(self, config: OpenDSSConfig) -> None:
        self.config = config
        self._dss = self._import_backend()

    @staticmethod
    def _import_backend():
        try:
            import opendssdirect as dss  # type: ignore

            return dss
        except Exception as e:
            raise OpenDSSBackendUnavailable(
                "OpenDSSDirect.py backend not available. Install with: pip install opendssdirect (and ensure OpenDSS engine dependencies are available)."
            ) from e

    def compile(self) -> None:
        """
        Compile the circuit from the configured master DSS file.
        """
        self._dss.Basic.ClearAll()
        self._dss.Text.Command(f"compile [{self.config.master_dss_path}]")

    def snapshot(self, *, t: Optional[str] = None) -> GridGraphSnapshot:
        """
        Placeholder: returns an empty snapshot with metadata.

        Next iteration should:
        - create nodes for BusTerminal (bus + phase)
        - create edges for lines/transformers/switches
        - fill static/dynamic fields and external_refs
        """
        t = t or utc_now_iso()
        # Even for the skeleton snapshot, emit a deterministic topology_hash so that downstream
        # components can rely on the contract shape.
        topology_hash = stable_hash(
            {
                "engine_projection": "opendss",
                "grid_id": self.config.grid_id,
                "nodes": [],
                "edges": [],
            }
        )
        return GridGraphSnapshot(
            t=t,
            topology_hash=topology_hash,
            topology_version=0,
            metadata={"engine_projection": "opendss", "grid_id": self.config.grid_id, "note": "skeleton"},
            nodes=[],
            edges=[],
        )
