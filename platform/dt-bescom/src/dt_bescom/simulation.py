"""
BESCOM Simulation Runner.

Integrates the BESCOM network model, load profiles, and data fetcher
into the existing Grid Digital Twin platform's simulation pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .network_model import (
    BESCOMNetworkConfig,
    build_bescom_network,
    describe_network,
)
from .load_profiles import BESCOMLoadProfile

logger = logging.getLogger(__name__)


class BESCOMSimulator:
    """
    Runs power flow simulations on the BESCOM Bangalore grid model.

    Integrates with the existing Grid Digital Twin platform's simulation
    pipeline by producing GridGraphSnapshots compatible with the dt-contracts.
    """

    def __init__(self, config: Optional[BESCOMNetworkConfig] = None):
        self.config = config or BESCOMNetworkConfig()
        self.net = None
        self._built = False
        self._tick_count = 0
        self._load_profile = BESCOMLoadProfile()

    def ensure_network(self):
        """Build the network on first access."""
        if not self._built:
            logger.info("Building BESCOM Bangalore network model...")
            self.net = build_bescom_network(self.config)
            self._built = True
            for line in describe_network(self.net).split("\n"):
                logger.info(f"  {line}")

    def run_powerflow(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Run a single power flow simulation at the given time.

        Returns simulation results including bus voltages, line loadings,
        and convergence status.
        """
        import pandapower as pp

        self.ensure_network()

        if dt is None:
            dt = datetime.now(timezone.utc)

        # Set time-dependent loads
        load_factor = self._load_profile.get_hourly_factor(dt)
        self.net.load.scaling = load_factor

        # Run power flow
        try:
            pp.runpp(self.net, numba=False, tolerance_mva=1e-6)
            converged = self.net.converged
        except pp.powerflow.LoadflowNotConverged:
            converged = False

        self._tick_count += 1

        # Extract results
        result = {
            "tick": self._tick_count,
            "timestamp": dt.isoformat(),
            "converged": converged,
            "load_factor": load_factor,
            "total_load_mw": float(self.net.res_load.p_mw.sum()) if converged else 0,
            "total_loss_mw": float(self.net.res_line.pl_mw.sum()) if converged and len(self.net.res_line) > 0 else 0,
            "n_buses": len(self.net.bus),
            "n_lines": len(self.net.line),
            "n_transformers": len(self.net.trafo),
            "vm_pu": {},
            "loading_percent": {},
        }

        if converged:
            for idx in self.net.bus.index:
                name = self.net.bus.at[idx, "name"]
                result["vm_pu"][name] = float(self.net.res_bus.at[idx, "vm_pu"])
            for idx in self.net.line.index:
                name = self.net.line.at[idx, "name"]
                loading = float(self.net.res_line.at[idx, "loading_percent"])
                result["loading_percent"][name] = loading

        return result

    def get_topology_snapshot(self) -> Dict[str, Any]:
        """Get the current network topology as a JSON-serializable dict."""
        self.ensure_network()

        nodes = []
        for idx in self.net.bus.index:
            bus = self.net.bus.loc[idx]
            nodes.append({
                "id": f"bescom/{bus['name']}",
                "type": "Bus",
                "static": {"vn_kv": float(bus["vn_kv"])},
                "dynamic": {},
            })

        edges = []
        for idx in self.net.line.index:
            line = self.net.line.loc[idx]
            from_bus = self.net.bus.at[line["from_bus"], "name"]
            to_bus = self.net.bus.at[line["to_bus"], "name"]
            edges.append({
                "id": f"bescom/{line['name']}",
                "type": "Line",
                "source": f"bescom/{from_bus}",
                "target": f"bescom/{to_bus}",
                "static": {"length_km": float(line["length_km"])},
                "dynamic": {},
            })

        for idx in self.net.trafo.index:
            trafo = self.net.trafo.loc[idx]
            hv_bus = self.net.bus.at[trafo["hv_bus"], "name"]
            lv_bus = self.net.bus.at[trafo["lv_bus"], "name"]
            edges.append({
                "id": f"bescom/{trafo['name']}",
                "type": "Transformer",
                "source": f"bescom/{hv_bus}",
                "target": f"bescom/{lv_bus}",
                "static": {"sn_mva": float(trafo["sn_mva"])},
                "dynamic": {},
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "topology_hash": str(hash(frozenset(n["id"] for n in nodes))),
            "topology_version": 1,
        }

    def to_grid_graph_snapshot(self, tick_count: int = 0):
        """Convert current simulation state to GridGraphSnapshot."""
        from dt_contracts.models import GridGraphSnapshot, GridNode, GridEdge

        self.ensure_network()
        import pandapower as pp

        try:
            pp.runpp(self.net, numba=False, tolerance_mva=1e-6)
        except pp.powerflow.LoadflowNotConverged:
            pass

        nodes = []
        for idx in self.net.bus.index:
            bus = self.net.bus.loc[idx]
            vm = float(self.net.res_bus.at[idx, "vm_pu"]) if self.net.converged else 1.0
            va = float(self.net.res_bus.at[idx, "va_degree"]) if self.net.converged else 0.0
            nodes.append(GridNode(
                id=f"bescom/{bus['name']}",
                type="Bus",
                static={"vn_kv": float(bus["vn_kv"])},
                dynamic={"vm_pu": vm, "va_degree": va},
                coordinates=None,
            ))

        edges = []
        for idx in self.net.line.index:
            line = self.net.line.loc[idx]
            from_name = self.net.bus.at[line["from_bus"], "name"]
            to_name = self.net.bus.at[line["to_bus"], "name"]
            loading = float(self.net.res_line.at[idx, "loading_percent"]) if self.net.converged and idx in self.net.res_line.index else 0.0
            edges.append(GridEdge(
                id=f"bescom/{line['name']}",
                type="Line",
                source=f"bescom/{from_name}",
                target=f"bescom/{to_name}",
                static={"length_km": float(line["length_km"])},
                dynamic={"loading_percent": loading, "i_ka": 0.0, "pl_mw": 0.0},
            ))

        for idx in self.net.trafo.index:
            trafo = self.net.trafo.loc[idx]
            hv_name = self.net.bus.at[trafo["hv_bus"], "name"]
            lv_name = self.net.bus.at[trafo["lv_bus"], "name"]
            loading = float(self.net.res_trafo.at[idx, "loading_percent"]) if self.net.converged and idx in self.net.res_trafo.index else 0.0
            edges.append(GridEdge(
                id=f"bescom/{trafo['name']}",
                type="Transformer",
                source=f"bescom/{hv_name}",
                target=f"bescom/{lv_name}",
                static={"sn_mva": float(trafo["sn_mva"])},
                dynamic={"loading_percent": loading},
            ))

        return GridGraphSnapshot(
            t=datetime.now(timezone.utc).isoformat(),
            topology_hash=f"bescom-v1-{tick_count}",
            topology_version=1,
            tick_count=tick_count,
            nodes=nodes,
            edges=edges,
            metadata={"source": "BESCOM Bangalore Grid", "peak_mw": 8472},
        )
