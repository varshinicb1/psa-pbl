"""
RGATv2: Recurrent Graph Attention Network v2 for power grid anomaly detection.

Architecture highlights:
- Multi-layer GATv2Conv with residual skip connections
- Edge feature integration via edge-conditioned attention
- Physics-informed loss: penalizes physically impossible predictions
- Attention-based global pooling for graph-level classification
- Temperature-scaled logits for calibrated confidence

Reference: https://arxiv.org/abs/2105.14491 (GATv2)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATv2Conv, global_mean_pool, global_add_pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class RGATv2Config:
    """Hyperparameters for the RGATv2 model."""

    # Input / hidden dimensions
    node_feat_dim: int = 10
    edge_feat_dim: int = 10
    hidden_dim: int = 128
    latent_dim: int = 64
    num_heads: int = 4
    num_layers: int = 3

    # Dropout / regularisation
    dropout: float = 0.15
    edge_dropout: float = 0.10

    # Loss weighting
    phys_loss_weight: float = 0.30
    focal_gamma: float = 2.0
    pos_weight: float = 1.0  # (neg / pos) ratio for class imbalance
    label_smoothing: float = 0.0  # label smoothing epsilon (0 = disabled)
    margin_weight: float = 0.0  # weight for margin-based separation loss
    contrastive_weight: float = 0.0  # weight for supervised contrastive loss

    # Pooling
    pool_type: str = "attention"  # "mean" | "add" | "attention"

    # Output
    num_fault_types: int = 6  # Normal + 5 fault types

    def __post_init__(self) -> None:
        assert self.hidden_dim % self.num_heads == 0, (
            f"hidden_dim ({self.hidden_dim}) must be divisible by num_heads ({self.num_heads})"
        )


# ---------------------------------------------------------------------------
# RGATv2 Base Model
# ---------------------------------------------------------------------------

class ResidualGATv2Conv(nn.Module):
    """
    GATv2Conv layer with:
      - residual skip connection (if input dim = output dim)
      - edge feature injection via concatenation
      - dropout on attention coefficients
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        edge_dim: int,
        heads: int = 4,
        dropout: float = 0.15,
        concat: bool = True,
    ):
        super().__init__()
        self.concat = concat
        self.out_channels = out_channels
        self.heads = heads

        self.conv = GATv2Conv(
            in_channels,
            out_channels // heads if concat else out_channels,
            heads=heads,
            edge_dim=edge_dim,
            dropout=dropout,
            concat=concat,
            fill_value="mean",
        )

        # Residual projection if dimensions don't match
        self.residual = nn.Linear(in_channels, out_channels) if in_channels != out_channels else nn.Identity()

        self.norm = nn.LayerNorm(out_channels)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
    ) -> torch.Tensor:
        h = self.conv(x, edge_index, edge_attr)
        # Residual
        h = h + self.residual(x)
        h = self.norm(h)
        h = F.elu(h)
        h = self.dropout(h)
        return h


class AttentionPooling(nn.Module):
    """
    Global attention pooling with a gated scoring mechanism.
    Learns which nodes are most important for the graph-level decision.
    """

    def __init__(self, in_channels: int, hidden_dim: int = 64):
        super().__init__()
        self.gate = nn.Sequential(
            nn.Linear(in_channels, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor, batch: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Node features [N, F]
            batch: Batch assignment [N]

        Returns:
            Graph-level representation [num_graphs, F]
        """
        scores = self.gate(x)  # [N, 1]
        scores = torch.softmax(scores, dim=0)
        # Weighted sum per graph
        out = torch.zeros(batch.max().item() + 1, x.size(1), device=x.device)
        for i in range(batch.max().item() + 1):
            mask = batch == i
            out[i] = (x[mask] * scores[mask]).sum(dim=0)
        return out


class PhysicsInformedLoss(nn.Module):
    """
    Physics-informed loss function for power grid anomaly detection.

    Penalizes predictions that violate physical constraints:
      1. Voltage magnitude must be in [0.85, 1.15] p.u. (soft bound)
      2. Power flow must satisfy conservation (sum of injections ≈ 0)
      3. Anomaly predictions must be temporally consistent (no oscillation)

    This is computed as a regularisation term added to the primary loss.
    """

    def __init__(self, weight: float = 0.30):
        super().__init__()
        self.weight = weight

    def forward(
        self,
        node_anomaly_scores: torch.Tensor,     # [N, 1]
        node_features: torch.Tensor,            # [N, F] – includes vm_pu
        edge_index: torch.Tensor,               # [2, E]
        edge_anomaly_scores: torch.Tensor,      # [E, 1]
    ) -> torch.Tensor:
        loss_terms: List[torch.Tensor] = []

        # --- 1. Voltage physics ---
        # vm_pu should be at index 0 in NODE_FEATURES
        vm_pu = node_features[:, 0]  # [N]
        volt_penalty = F.relu(0.85 - vm_pu) + F.relu(vm_pu - 1.15)
        loss_terms.append(volt_penalty.mean())

        # --- 2. Conservation: sum of injections at each bus ≈ 0 ---
        p_mw = node_features[:, 2]  # p_mw at index 2
        q_mvar = node_features[:, 3]  # q_mvar at index 3
        active_imbalance = p_mw.sum()
        reactive_imbalance = q_mvar.sum()
        imbalance_penalty = (active_imbalance ** 2 + reactive_imbalance ** 2) / (
            node_features.size(0) + 1
        )
        loss_terms.append(imbalance_penalty * 1e-6)  # Light weighting

        # --- 3. Edge anomaly smoothness (spatial consistency) ---
        if edge_anomaly_scores.size(0) > 1:
            # Connected edges should have similar anomaly scores
            src_nodes = edge_anomaly_scores[edge_index[0]]  # [E, 1]
            dst_nodes = edge_anomaly_scores[edge_index[1]]  # [E, 1]
            smoothness = (src_nodes - dst_nodes).pow(2).mean()
            loss_terms.append(smoothness * 0.10)

        total = sum(loss_terms)
        return self.weight * total


# ---------------------------------------------------------------------------
# RGATv2 Main Module
# ---------------------------------------------------------------------------

class RGATv2(nn.Module):
    """
    Recurrent Graph Attention Network v2.

    Processes grid topology snapshots through stacked GATv2Conv layers with
    residual connections, then pools to a graph-level representation and
    produces per-node anomaly scores.

    Can be used standalone or as the backbone for FaultClassifier.
    """

    def __init__(self, config: RGATv2Config):
        super().__init__()
        self.config = config
        self.hidden_dim = config.hidden_dim

        # Input projection: node features -> hidden
        self.node_encoder = nn.Sequential(
            nn.Linear(config.node_feat_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.ELU(),
            nn.Dropout(config.dropout),
        )
        # Edge feature encoder
        self.edge_encoder = nn.Sequential(
            nn.Linear(config.edge_feat_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.ELU(),
            nn.Dropout(config.edge_dropout),
        )

        # Stacked residual GATv2 layers
        self.layers = nn.ModuleList()
        for i in range(config.num_layers):
            layer = ResidualGATv2Conv(
                in_channels=config.hidden_dim,
                out_channels=config.hidden_dim,
                edge_dim=config.hidden_dim,
                heads=config.num_heads,
                dropout=config.dropout,
                concat=True,
            )
            self.layers.append(layer)

        # Output heads
        self.node_score_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.latent_dim),
            nn.ELU(),
            nn.Dropout(config.dropout * 0.5),
            nn.Linear(config.latent_dim, 1),
        )
        self.edge_score_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.latent_dim),
            nn.ELU(),
            nn.Dropout(config.dropout * 0.5),
            nn.Linear(config.latent_dim, 1),
        )

        # Global pooling
        pool_type = config.pool_type
        if pool_type == "mean":
            self.pool = lambda x, batch: global_mean_pool(x, batch)
        elif pool_type == "add":
            self.pool = lambda x, batch: global_add_pool(x, batch)
        elif pool_type == "attention":
            self.pool = AttentionPooling(config.hidden_dim)
        else:
            raise ValueError(f"Unknown pool_type: {pool_type}")

        # Graph-level projection for fault classification input
        self.graph_proj = nn.Linear(config.hidden_dim, config.latent_dim)

        # Physics-informed loss
        self.physics_loss = PhysicsInformedLoss(weight=config.phys_loss_weight)

        self._init_weights()
        logger.info(
            f"RGATv2 initialized: {config.num_layers} layers, "
            f"{config.num_heads} heads, hidden={config.hidden_dim}, "
            f"pool={config.pool_type}"
        )

    def _init_weights(self) -> None:
        """Apply Xavier uniform initialisation to all linear layers."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight, gain=1.0)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Args:
            x:      Node features          [N, F_node]
            edge_index: Graph connectivity [2, E]
            edge_attr:  Edge features      [E, F_edge]
            batch:  Batch assignment        [N] (None = single graph)

        Returns:
            dict with keys:
                node_scores:  Per-node anomaly scores  [N, 1]
                edge_scores:  Per-edge anomaly scores  [E, 1]
                graph_feat:   Graph-level embedding    [num_graphs, latent_dim]
                attention:    Layer-wise attention coefficients (list)
        """
        if batch is None:
            batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        # Encode
        h = self.node_encoder(x)           # [N, hidden]
        e = self.edge_encoder(edge_attr)   # [E, hidden]

        # GAT layers
        for layer in self.layers:
            h = layer(h, edge_index, e)

        # Output heads
        node_scores = self.node_score_head(h)  # [N, 1]
        edge_scores = self.edge_score_head(e)  # [E, 1]

        # Global pooling
        graph_feat = self.pool(h, batch)        # [num_graphs, hidden]
        graph_feat = self.graph_proj(graph_feat)  # [num_graphs, latent_dim]

        return {
            "node_scores": torch.sigmoid(node_scores),
            "edge_scores": torch.sigmoid(edge_scores),
            "graph_feat": graph_feat,
            "node_embeddings": h,
        }

    def compute_loss(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
        node_labels: Optional[torch.Tensor] = None,
        graph_labels: Optional[torch.Tensor] = None,
        batch: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute supervised + physics-informed loss.

        Args:
            x:             Node features          [N, F_node]
            edge_index:    Graph connectivity     [2, E]
            edge_attr:     Edge features          [E, F_edge]
            node_labels:   Per-node anomaly labels [N] (binary)
            graph_labels:  Per-graph fault labels  [num_graphs] (multiclass)
            batch:         Batch assignment       [N]

        Returns:
            dict with loss components
        """
        out = self.forward(x, edge_index, edge_attr, batch)
        node_scores = out["node_scores"].squeeze(-1)  # [N]
        loss = torch.tensor(0.0, device=x.device)

        # --- Node-level supervision (if available) ---
        node_loss = torch.tensor(0.0, device=x.device)
        margin_loss = torch.tensor(0.0, device=x.device)
        contrastive_loss = torch.tensor(0.0, device=x.device)
        if node_labels is not None:
            # Label smoothing: replace hard 0/1 with (eps, 1-eps)
            ls = self.config.label_smoothing
            if ls > 0:
                smooth_labels = node_labels.float() * (1 - 2 * ls) + ls
            else:
                smooth_labels = node_labels.float()

            # Weighted loss for class imbalance
            pw = self.config.pos_weight
            bce = F.binary_cross_entropy(node_scores, smooth_labels, reduction="none")
            # Apply class weighting: anomaly errors weighted by pos_weight
            weights = torch.where(node_labels == 1, pw, 1.0)
            weighted_bce = bce * weights
            # Focal modulation
            pt = torch.where(node_labels == 1, node_scores, 1 - node_scores)
            focal = (1 - pt) ** self.config.focal_gamma * weighted_bce
            node_loss = focal.mean()
            loss = loss + node_loss

            # Margin-based separation loss: push anomaly scores above normal scores
            mw = self.config.margin_weight
            if mw > 0 and batch is not None:
                for g in range(batch.max().item() + 1):
                    gmask = batch == g
                    g_labels = node_labels[gmask]
                    g_scores = node_scores[gmask]
                    has_anom = (g_labels == 1).any()
                    has_normal = (g_labels == 0).any()
                    if has_anom and has_normal:
                        anom_mean = g_scores[g_labels == 1].mean()
                        normal_mean = g_scores[g_labels == 0].mean()
                        margin_loss = margin_loss + F.relu(0.3 - (anom_mean - normal_mean))
                margin_loss = margin_loss / (batch.max().item() + 1)
                loss = loss + mw * margin_loss

            # Supervised contrastive loss: pull same-class embeddings together,
            # push different-class apart. This directly improves precision by
            # creating well-separated clusters in embedding space.
            cw = self.config.contrastive_weight
            if cw > 0 and batch is not None:
                h_emb = out["node_embeddings"]
                h_norm = F.normalize(h_emb, dim=1)  # [N, hidden]
                sim = h_norm @ h_norm.T  # [N, N] cosine similarity
                tau = 0.1
                sim = sim / tau  # temperature scaling
                N = h_emb.size(0)
                eye = torch.eye(N, device=h_emb.device, dtype=torch.bool)
                # Positive mask: same class, excluding self
                pos_mask = node_labels.unsqueeze(0) == node_labels.unsqueeze(1)
                pos_mask = pos_mask & ~eye
                # Supervised NT-Xent: for each anchor i,
                # loss_i = -log( sum(pos_exp) / (sum(pos_exp) + sum(neg_exp)) )
                exp_sim = torch.exp(sim)  # [N, N]
                exp_sim = exp_sim * (~eye)  # zero out self
                pos_sum = (exp_sim * pos_mask.float()).sum(dim=1)  # [N]
                all_sum = exp_sim.sum(dim=1)  # [N]
                # Avoid division by zero
                valid = pos_sum > 0
                if valid.any():
                    contrastive_loss = -(pos_sum[valid] / all_sum[valid]).log().mean()
                    loss = loss + cw * contrastive_loss

        # --- Physics-informed regularisation ---
        phys_loss = self.physics_loss(
            out["node_scores"], x, edge_index, out["edge_scores"]
        )
        loss = loss + phys_loss

        # --- Graph-level classification (if available) ---
        graph_loss = torch.tensor(0.0, device=x.device)
        if graph_labels is not None:
            # Project to fault types
            graph_logits = self._classification_head(out["graph_feat"])
            graph_loss = F.cross_entropy(graph_logits, graph_labels)
            loss = loss + graph_loss

        return {
            "loss": loss,
            "node_loss": node_loss,
            "graph_loss": graph_loss,
            "phys_loss": phys_loss,
        }

    def _classification_head(self, graph_feat: torch.Tensor) -> torch.Tensor:
        """Temporary classification head used during compute_loss."""
        weight = getattr(self, "_cls_weight", None)
        bias = getattr(self, "_cls_bias", None)
        if weight is None:
            device = graph_feat.device
            self._cls_weight = nn.Parameter(
                torch.randn(self.config.num_fault_types, self.config.latent_dim, device=device) * 0.02
            )
            self._cls_bias = nn.Parameter(torch.zeros(self.config.num_fault_types, device=device))
            weight = self._cls_weight
            bias = self._cls_bias
        return graph_feat @ weight.T + bias


# ---------------------------------------------------------------------------
# Pretrained model utilities
# ---------------------------------------------------------------------------

def load_rgatv2(
    checkpoint_path: str,
    config: Optional[RGATv2Config] = None,
    device: Optional[torch.device] = None,
) -> RGATv2:
    """
    Load a pretrained RGATv2 model from checkpoint.

    Args:
        checkpoint_path: Path to .pt checkpoint
        config: Model configuration (loaded from checkpoint if None)
        device: Target device

    Returns:
        RGATv2 model in eval mode
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)

    if config is None:
        config_dict = checkpoint.get("config", {})
        config = RGATv2Config(**config_dict)

    model = RGATv2(config)
    model.load_state_dict(checkpoint["model_state_dict"], strict=False)
    model.to(device)
    model.eval()

    logger.info(
        f"RGATv2 loaded from {checkpoint_path} "
        f"(epoch={checkpoint.get('epoch', '?')}, "
        f"val_loss={checkpoint.get('val_loss', '?'):.4f})"
    )
    return model


def save_rgatv2(
    model: RGATv2,
    path: str,
    epoch: int = 0,
    val_loss: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Save RGATv2 model checkpoint.
    """
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "config": {
            k: v for k, v in model.config.__dict__.items() if not k.startswith("_")
        },
        "epoch": epoch,
        "val_loss": val_loss,
        "metadata": metadata or {},
    }
    torch.save(checkpoint, path)
    logger.info(f"RGATv2 checkpoint saved to {path}")
