from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import pandapower as pp
import pandapower.networks as ppnw

from dt_contracts.models import ExternalRef, GridEdge, GridGraphSnapshot, GridNode, SCHEMA_VERSION


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class PowerFlowRunInfo:
    solved: bool
    algorithm: str
    metrics: Dict[str, Any]


class PandapowerAdapter:
    """
    pandapower adapter that projects a pandapowerNet into the canonical GridGraph snapshot.

    PoC scope:
    - buses as nodes
    - lines/transformers as edges
    - switch table as "Switch" edges (connectivity controls)
    """

    def __init__(self, *, grid_id: str = "demo-grid") -> None:
        self.grid_id = grid_id

    # -------------------------------
    # Model loading (PoC helpers)
    # -------------------------------
    def load_ieee14(self) -> pp.pandapowerNet:
        return ppnw.case14()

    # -------------------------------
    # Mapping: pandapowerNet -> GridGraph
    # -------------------------------
    def gridgraph_from_net(self, net: pp.pandapowerNet, *, t: str | None = None, topology_version: int = 0) -> GridGraphSnapshot:
        t = t or _utc_now_iso()

        nodes: List[GridNode] = []
        edges: List[GridEdge] = []

        # Nodes (buses)
        for bus_idx, bus in net.bus.iterrows():
            node_id = f"{self.grid_id}/pp/bus/{int(bus_idx)}"
            nodes.append(
                GridNode(
                    id=node_id,
                    type="Bus",
                    static={
                        "name": str(bus.get("name", "")),
                        "vn_kv": float(bus["vn_kv"]),
                        "type": str(bus.get("type", "")),
                        "zone": bus.get("zone", None),
                        "in_service": bool(bus.get("in_service", True)),
                    },
                    dynamic={},
                    external_refs=[ExternalRef(engine="pandapower", object_type="bus", object_name=str(int(bus_idx)))],
                )
            )

        # Edges (lines)
        if hasattr(net, "line"):
            for line_idx, line in net.line.iterrows():
                from_bus = f"{self.grid_id}/pp/bus/{int(line.from_bus)}"
                to_bus = f"{self.grid_id}/pp/bus/{int(line.to_bus)}"
                edge_id = f"{self.grid_id}/pp/line/{int(line_idx)}"
                edges.append(
                    GridEdge(
                        id=edge_id,
                        type="Line",
                        source=from_bus,
                        target=to_bus,
                        static={
                            "name": str(line.get("name", "")),
                            "length_km": float(line.get("length_km", 0.0)),
                            "r_ohm_per_km": float(line.get("r_ohm_per_km", 0.0)),
                            "x_ohm_per_km": float(line.get("x_ohm_per_km", 0.0)),
                            "c_nf_per_km": float(line.get("c_nf_per_km", 0.0)),
                            "max_i_ka": float(line.get("max_i_ka", 0.0)) if "max_i_ka" in line else None,
                            "in_service": bool(line.get("in_service", True)),
                        },
                        dynamic={},
                        external_refs=[ExternalRef(engine="pandapower", object_type="line", object_name=str(int(line_idx)))],
                    )
                )

        # Edges (transformers)
        if hasattr(net, "trafo"):
            for trafo_idx, trafo in net.trafo.iterrows():
                hv_bus = f"{self.grid_id}/pp/bus/{int(trafo.hv_bus)}"
                lv_bus = f"{self.grid_id}/pp/bus/{int(trafo.lv_bus)}"
                edge_id = f"{self.grid_id}/pp/trafo/{int(trafo_idx)}"
                edges.append(
                    GridEdge(
                        id=edge_id,
                        type="Transformer",
                        source=hv_bus,
                        target=lv_bus,
                        static={
                            "name": str(trafo.get("name", "")),
                            "sn_mva": float(trafo.get("sn_mva", 0.0)),
                            "vn_hv_kv": float(trafo.get("vn_hv_kv", 0.0)),
                            "vn_lv_kv": float(trafo.get("vn_lv_kv", 0.0)),
                            "vk_percent": float(trafo.get("vk_percent", 0.0)),
                            "vkr_percent": float(trafo.get("vkr_percent", 0.0)),
                            "pfe_kw": float(trafo.get("pfe_kw", 0.0)),
                            "i0_percent": float(trafo.get("i0_percent", 0.0)),
                            "in_service": bool(trafo.get("in_service", True)),
                        },
                        dynamic={},
                        external_refs=[ExternalRef(engine="pandapower", object_type="trafo", object_name=str(int(trafo_idx)))],
                    )
                )

        # Switches as controllable connectivity edges
        if hasattr(net, "switch"):
            for sw_idx, sw in net.switch.iterrows():
                # sw.element is either a line/trafo/bus depending on sw.et; for PoC treat as bus-bus when possible.
                # For bus-bus, element points to another bus index.
                source = f"{self.grid_id}/pp/bus/{int(sw.bus)}"
                target = source
                if str(sw.et) == "b":
                    target = f"{self.grid_id}/pp/bus/{int(sw.element)}"
                edge_id = f"{self.grid_id}/pp/switch/{int(sw_idx)}"
                edges.append(
                    GridEdge(
                        id=edge_id,
                        type="Switch",
                        source=source,
                        target=target,
                        static={"et": str(sw.et), "element": int(sw.element)},
                        dynamic={"closed": bool(sw.closed)},
                        external_refs=[ExternalRef(engine="pandapower", object_type="switch", object_name=str(int(sw_idx)))],
                    )
                )

        topology_material = {
            "grid_id": self.grid_id,
            "bus": [(n.id, n.static.get("vn_kv")) for n in nodes],
            "edge": [(e.id, e.type, e.source, e.target) for e in edges],
        }
        topo_hash = _stable_hash(topology_material)

        return GridGraphSnapshot(
            schema_version=SCHEMA_VERSION,
            t=t,
            topology_hash=topo_hash,
            topology_version=topology_version,
            metadata={"engine_projection": "pandapower", "grid_id": self.grid_id},
            nodes=nodes,
            edges=edges,
        )

    # -------------------------------
    # Simulation
    # -------------------------------
    def run_powerflow(self, net: pp.pandapowerNet, *, algorithm: str = "nr") -> PowerFlowRunInfo:
        """
        Run AC PF using pandapower.
        """
        # init="auto" generally works for repeated runs in PoC
        pp.runpp(net, algorithm=algorithm, init="auto")
        return PowerFlowRunInfo(solved=bool(net["converged"]), algorithm=algorithm, metrics={})

    def apply_results_to_snapshot(self, snapshot: GridGraphSnapshot, net: pp.pandapowerNet) -> GridGraphSnapshot:
        """
        Return a new snapshot with dynamic fields updated from net.res_* tables.
        """
        node_by_id: Dict[str, GridNode] = {n.id: n for n in snapshot.nodes}
        edge_by_id: Dict[str, GridEdge] = {e.id: e for e in snapshot.edges}

        # Bus results
        if hasattr(net, "res_bus") and len(net.res_bus) == len(net.bus):
            for bus_idx, res in net.res_bus.iterrows():
                nid = f"{self.grid_id}/pp/bus/{int(bus_idx)}"
                if nid in node_by_id:
                    node_by_id[nid].dynamic.update(
                        {
                            "vm_pu": float(res.get("vm_pu")),
                            "va_degree": float(res.get("va_degree")),
                            "p_mw": float(res.get("p_mw", 0.0)) if "p_mw" in res else None,
                            "q_mvar": float(res.get("q_mvar", 0.0)) if "q_mvar" in res else None,
                        }
                    )

        # Line results
        if hasattr(net, "res_line") and hasattr(net, "line"):
            for line_idx, res in net.res_line.iterrows():
                eid = f"{self.grid_id}/pp/line/{int(line_idx)}"
                if eid in edge_by_id:
                    edge_by_id[eid].dynamic.update(
                        {
                            "loading_percent": float(res.get("loading_percent")),
                            "p_from_mw": float(res.get("p_from_mw")),
                            "q_from_mvar": float(res.get("q_from_mvar")),
                            "p_to_mw": float(res.get("p_to_mw")),
                            "q_to_mvar": float(res.get("q_to_mvar")),
                            "i_from_ka": float(res.get("i_from_ka")) if "i_from_ka" in res else None,
                            "i_to_ka": float(res.get("i_to_ka")) if "i_to_ka" in res else None,
                        }
                    )

        # Transformer results
        if hasattr(net, "res_trafo") and hasattr(net, "trafo"):
            for trafo_idx, res in net.res_trafo.iterrows():
                eid = f"{self.grid_id}/pp/trafo/{int(trafo_idx)}"
                if eid in edge_by_id:
                    edge_by_id[eid].dynamic.update(
                        {
                            "loading_percent": float(res.get("loading_percent")),
                            "p_hv_mw": float(res.get("p_hv_mw")) if "p_hv_mw" in res else None,
                            "q_hv_mvar": float(res.get("q_hv_mvar")) if "q_hv_mvar" in res else None,
                            "p_lv_mw": float(res.get("p_lv_mw")) if "p_lv_mw" in res else None,
                            "q_lv_mvar": float(res.get("q_lv_mvar")) if "q_lv_mvar" in res else None,
                        }
                    )

        return snapshot.model_copy(update={"nodes": list(node_by_id.values()), "edges": list(edge_by_id.values())})

    # -------------------------------
    # Convenience: net + snapshot in one go
    # -------------------------------
    def build_ieee14(self) -> Tuple[pp.pandapowerNet, GridGraphSnapshot]:
        net = self.load_ieee14()
        snap = self.gridgraph_from_net(net)
        return net, snap

