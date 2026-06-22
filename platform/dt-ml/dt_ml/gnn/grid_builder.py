"""
GridBuilder: Converts GridGraphSnapshot into PyTorch Geometric Data objects.

Handles:
- Node feature extraction (voltage magnitude, angle, load, generation)
- Edge feature extraction (line loading, impedance, flow)
- Topology encoding (adjacency matrix construction)
- Static attribute normalization
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import torch
import numpy as np

from dt_contracts.models import GridGraphSnapshot, GridNode, GridEdge

logger = logging.getLogger(__name__)

# Canonical feature dimension order
NODE_FEATURES = [
    "vm_pu",           # Voltage magnitude (p.u.)
    "va_degree",       # Voltage angle (degrees)
    "p_mw",            # Active power injection (MW)
    "q_mvar",          # Reactive power injection (MVAr)
    "vn_kv",           # Nominal voltage (kV)
    "in_service",      # Bus in service flag
    "load_p_mw",       # Connected load active (MW)
    "load_q_mvar",     # Connected load reactive (MVAr)
    "gen_p_mw",        # Generation active (MW)
    "gen_q_mvar",      # Generation reactive (MVAr)
]

EDGE_FEATURES = [
    "loading_percent",  # Line loading (%)
    "p_from_mw",       # Active power from (MW)
    "q_from_mvar",     # Reactive power from (MVAr)
    "p_to_mw",         # Active power to (MW)
    "q_to_mvar",       # Reactive power to (MVAr)
    "r_ohm",           # Resistance (Ohm)
    "x_ohm",           # Reactance (Ohm)
    "length_km",       # Line length (km)
    "max_i_ka",        # Rated current (kA)
    "in_service",      # In service flag
]

FAULT_TYPE_MAP = {
    0: "Normal",
    1: "SingleLineToGround",
    2: "LineToLineToGround",
    3: "LineToLine",
    4: "ThreePhase",
    5: "OpenCircuit",
}


class GridBuilder:
    """
    Converts GridDigitalTwin GridGraphSnapshot into PyTorch Geometric Data
    objects suitable for GNN training and inference.

    Supports dynamic topology changes via topology_hash tracking.
    """

    def __init__(
        self,
        node_features: Optional[List[str]] = None,
        edge_features: Optional[List[str]] = None,
        normalize: bool = True,
    ):
        self.node_features = node_features or NODE_FEATURES
        self.edge_features = edge_features or EDGE_FEATURES
        self.normalize = normalize

        # Feature statistics for normalization (computed on-the-fly)
        self._node_stats: Dict[str, Tuple[float, float]] = {}
        self._edge_stats: Dict[str, Tuple[float, float]] = {}
        self._topology_hash_seen: Optional[str] = None

    def build(self, snapshot: GridGraphSnapshot) -> Any:
        """
        Build a PyG Data object from a GridGraphSnapshot.

        Args:
            snapshot: Canonical grid state snapshot

        Returns:
            torch_geometric.data.Data object with:
                - x: Node feature matrix [num_nodes, num_node_features]
                - edge_index: Graph connectivity [2, num_edges]
                - edge_attr: Edge feature matrix [num_edges, num_edge_features]
                - topology_hash: String identifier for the topology
                - tick_count: Current simulation tick
        """
        import torch_geometric.data as pyg_data

        # Build node features
        node_ids: List[str] = []
        node_feat_list: List[torch.Tensor] = []

        for node in snapshot.nodes:
            node_ids.append(node.id)
            feats = self._extract_node_features(node)
            node_feat_list.append(feats)

        x = torch.stack(node_feat_list) if node_feat_list else torch.zeros((0, len(self.node_features)))

        # Build edge index + edge features
        edge_src: List[int] = []
        edge_dst: List[int] = []
        edge_feat_list: List[torch.Tensor] = []

        node_id_to_idx = {nid: i for i, nid in enumerate(node_ids)}

        for edge in snapshot.edges:
            if edge.type not in ("Line", "Transformer"):
                continue
            src_idx = node_id_to_idx.get(edge.source)
            dst_idx = node_id_to_idx.get(edge.target)
            if src_idx is None or dst_idx is None:
                continue

            edge_src.append(src_idx)
            edge_dst.append(dst_idx)

            # Add reverse edge for undirected graph
            edge_src.append(dst_idx)
            edge_dst.append(src_idx)

            feats = self._extract_edge_features(edge)
            edge_feat_list.append(feats)
            edge_feat_list.append(feats)  # same features for both directions

        edge_index = torch.tensor([edge_src, edge_dst], dtype=torch.long) if edge_src else torch.zeros((2, 0), dtype=torch.long)
        edge_attr = torch.stack(edge_feat_list) if edge_feat_list else torch.zeros((0, len(self.edge_features)))

        # Normalize if requested
        if self.normalize and len(node_feat_list) > 0:
            x = self._normalize_node_features(x)
        if self.normalize and len(edge_feat_list) > 0:
            edge_attr = self._normalize_edge_features(edge_attr)

        data = pyg_data.Data(
            x=x,
            edge_index=edge_index,
            edge_attr=edge_attr,
            topology_hash=snapshot.topology_hash,
            tick_count=snapshot.tick_count,
            num_nodes=len(snapshot.nodes),
        )

        # Track topology changes
        if self._topology_hash_seen is None:
            self._topology_hash_seen = snapshot.topology_hash
        elif self._topology_hash_seen != snapshot.topology_hash:
            logger.info(f"Topology changed: {self._topology_hash_seen[:8]} -> {snapshot.topology_hash[:8]}")
            self._topology_hash_seen = snapshot.topology_hash

        return data

    def _extract_node_features(self, node: GridNode) -> torch.Tensor:
        """Extract feature vector for a single grid node."""
        vals = []
        for feat in self.node_features:
            # Check dynamic state first
            val = node.dynamic.get(feat)
            if val is not None:
                vals.append(float(val))
                continue
            # Fall back to static attributes
            val = node.static.get(feat)
            if val is not None:
                vals.append(float(val) if not isinstance(val, bool) else float(val))
                continue
            # Try extracting from subfields
            if feat == "load_p_mw":
                vals.append(float(node.static.get("p_mw", 0.0)))
            elif feat == "load_q_mvar":
                vals.append(float(node.static.get("q_mvar", 0.0)))
            elif feat == "gen_p_mw":
                vals.append(0.0)
            elif feat == "gen_q_mvar":
                vals.append(0.0)
            else:
                vals.append(0.0)
        return torch.tensor(vals, dtype=torch.float32)

    def _extract_edge_features(self, edge: GridEdge) -> torch.Tensor:
        """Extract feature vector for a single grid edge."""
        vals = []
        for feat in self.edge_features:
            val = edge.dynamic.get(feat)
            if val is not None:
                vals.append(float(val))
                continue
            val = edge.static.get(feat)
            if val is not None:
                vals.append(float(val) if not isinstance(val, bool) else float(val))
                continue
            # Map to static line parameters
            if feat == "r_ohm":
                r_per_km = edge.static.get("r_ohm_per_km", 0.0)
                length = edge.static.get("length_km", 0.0)
                vals.append(float(r_per_km) * float(length))
            elif feat == "x_ohm":
                x_per_km = edge.static.get("x_ohm_per_km", 0.0)
                length = edge.static.get("length_km", 0.0)
                vals.append(float(x_per_km) * float(length))
            else:
                vals.append(0.0)
        return torch.tensor(vals, dtype=torch.float32)

    def _normalize_node_features(self, x: torch.Tensor) -> torch.Tensor:
        """Online normalization using running statistics."""
        if x.size(0) < 2:
            return x
        mean = x.mean(dim=0)
        std = x.std(dim=0).clamp(min=1e-8)
        return (x - mean) / std

    def _normalize_edge_features(self, edge_attr: torch.Tensor) -> torch.Tensor:
        """Online normalization for edge features."""
        if edge_attr.size(0) < 2:
            return edge_attr
        mean = edge_attr.mean(dim=0)
        std = edge_attr.std(dim=0).clamp(min=1e-8)
        return (edge_attr - mean) / std

    def get_feature_dim(self) -> int:
        """Return the node feature dimension."""
        return len(self.node_features)

    def get_edge_feature_dim(self) -> int:
        """Return the edge feature dimension."""
        return len(self.edge_features)

    def reset_normalization(self) -> None:
        """Reset running normalization statistics."""
        self._node_stats.clear()
        self._edge_stats.clear()


def build_from_snapshot(snapshot: GridGraphSnapshot, builder: Optional[GridBuilder] = None) -> Any:
    """
    Convenience function: build a PyG Data object from a snapshot.

    Args:
        snapshot: Grid state snapshot
        builder: Optional existing builder (creates new if None)

    Returns:
        torch_geometric.data.Data object
    """
    if builder is None:
        builder = GridBuilder()
    return builder.build(snapshot)
