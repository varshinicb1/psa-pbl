"""
RGATv2 training script for power grid anomaly detection.

Generates synthetic IEEE-14 powerflow data on-the-fly (or loads pre-generated
CSV datasets), builds PyG Data objects, and trains the RGATv2 GNN with
physics-informed loss.

Usage:
    # Generate data on-the-fly and train
    python -m dt_ml.gnn.train --epochs 50 --scenarios 30 --ticks 60

    # Load pre-generated CSV dataset
    python -m dt_ml.gnn.train --dataset platform/datasets/ieee14_voltage_anomaly

    # Resume from checkpoint
    python -m dt_ml.gnn.train --resume checkpoints/gridsentinel_ieee14.pt

    # Quick smoke test (2 epochs, 4 scenarios)
    python -m dt_ml.gnn.train --epochs 2 --scenarios 4 --ticks 10 --quick
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sys
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torch.utils.tensorboard import SummaryWriter

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_repo_root = Path(__file__).resolve().parents[4]
for _mod in ["dt-orchestrator", "dt-ml", "dt-contracts/python/src", "dt-sim-pandapower"]:
    _p = str(_repo_root / "platform" / _mod)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Imports (after path bootstrap)
# ---------------------------------------------------------------------------

import pandas as pd

from dt_ml.gnn.grid_builder import GridBuilder
from dt_ml.gnn.model import RGATv2, RGATv2Config, save_rgatv2, load_rgatv2
from dt_ml.gnn.fault_types import FaultClassifier, FaultType

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ---------------------------------------------------------------------------
# Synthetic data generator
# ---------------------------------------------------------------------------


class SyntheticGridGenerator:
    """
    Generates labeled IEEE-14 grid snapshots with controlled anomalies.

    Uses the RealtimeTickRunner to generate realistic powerflow snapshots,
    then injects synthetic load perturbations to create labeled anomaly
    scenarios. Produces (PyG Data, node_labels, graph_label) triples.
    """

    def __init__(
        self,
        num_scenarios: int = 20,
        ticks_per_scenario: int = 60,
        anomaly_prob: float = 0.15,
        base_seed: int = 42,
        voltage_lower: float = 0.95,
        voltage_upper: float = 1.05,
        quick: bool = False,
    ):
        self.num_scenarios = num_scenarios
        self.ticks_per_scenario = ticks_per_scenario
        self.anomaly_prob = anomaly_prob
        self.base_seed = base_seed
        self.voltage_lower = voltage_lower
        self.voltage_upper = voltage_upper
        self.quick = quick

        self.grid_builder = GridBuilder(normalize=False)

        # Initialize runner
        from dt_orchestrator.pipelines.realtime_tick import RealtimeTickRunner
        self.runner = RealtimeTickRunner(grid_id="ds/ieee14/train", seed=base_seed)

        # Cache base load values for perturbation
        self._base_loads: Optional[Tuple[List[float], List[float]]] = None
        if hasattr(self.runner.net, "load") and len(self.runner.net.load) > 0:
            self._base_loads = (
                self.runner.net.load.p_mw.tolist(),
                self.runner.net.load.q_mvar.tolist(),
            )

        # Fault type distribution for labeling
        self.fault_types = [FaultType.NORMAL, FaultType.SINGLE_LINE_TO_GROUND,
                           FaultType.LINE_TO_LINE_TO_GROUND, FaultType.THREE_PHASE]

    def __len__(self) -> int:
        return self.num_scenarios * self.ticks_per_scenario

    def __iter__(self) -> Iterator[Tuple[Any, torch.Tensor, torch.Tensor]]:
        """Iterate over (PyG Data, node_labels, graph_label) triples."""
        for s in range(self.num_scenarios):
            yield from self._generate_scenario(s)

    def _generate_scenario(self, scenario_id: int) -> Iterator[Tuple[Any, torch.Tensor, torch.Tensor]]:
        """
        Generate one scenario (sequence of ticks with consistent anomalies).

        Yields (PyG Data, node_labels, graph_label) for each tick.
        """
        rng = random.Random(self.base_seed + scenario_id * 1000)

        # Decide if this scenario has anomalies
        has_anomaly = rng.random() < self.anomaly_prob
        if has_anomaly:
            # Pick a fault type and affected bus
            fault_type = rng.choice(self.fault_types[1:])  # skip NORMAL
            affected_bus_idx = rng.randint(0, 13)  # IEEE-14 has 14 buses (0-13)
            severity = rng.uniform(0.5, 1.0)
        else:
            fault_type = FaultType.NORMAL
            affected_bus_idx = -1
            severity = 0.0

        # Reset network loads for this scenario
        self._reset_loads()

        for tick in range(self.ticks_per_scenario):
            if self.quick and tick >= 10:
                break

            # Perturb loads directly (do NOT call inject_synthetic_telemetry which
            # would overwrite our controlled perturbations with random values)
            self._perturb_loads(rng, has_anomaly, affected_bus_idx, severity, tick)

            # Run powerflow on the perturbed network directly
            try:
                run_info = self.runner.adapter.run_powerflow(self.runner.net)
            except Exception:
                continue

            if not run_info.solved:
                continue

            # Get latest snapshot
            latest = self.runner.store.get_latest()
            if latest is None:
                continue

            snap = latest.model_copy(update={"t": str(scenario_id), "schema_version": "1.0"})
            snap2 = self.runner.adapter.apply_results_to_snapshot(snap, self.runner.net)
            snap2.tick_count = tick

            # Build PyG Data
            data = self.grid_builder.build(snap2)

            # Create labels
            if has_anomaly:
                # Node labels: 1 for affected bus, 0 for others
                node_labels = torch.zeros(len(snap2.nodes), dtype=torch.long)
                for i, node in enumerate(snap2.nodes):
                    # Check if this bus has voltage out of bounds
                    vm = node.dynamic.get("vm_pu", 1.0)
                    try:
                        vm_f = float(vm)
                        if vm_f < self.voltage_lower or vm_f > self.voltage_upper:
                            node_labels[i] = 1
                    except (ValueError, TypeError):
                        pass

                # If powerflow didn't produce bounds violations, simulate artificially
                if node_labels.sum() == 0:
                    node_labels[affected_bus_idx] = 1

                # Graph label: fault type index
                graph_label = torch.tensor([fault_type.value], dtype=torch.long)
            else:
                node_labels = torch.zeros(len(snap2.nodes), dtype=torch.long)
                graph_label = torch.tensor([FaultType.NORMAL.value], dtype=torch.long)

            yield data, node_labels, graph_label

            # Update store
            self.runner.store.set_latest(snap2)

    def _reset_loads(self) -> None:
        """Reset network loads to baseline."""
        if self._base_loads is None:
            return
        base_p, base_q = self._base_loads
        for i in range(len(base_p)):
            self.runner.net.load.at[i, "p_mw"] = base_p[i]
            self.runner.net.load.at[i, "q_mvar"] = base_q[i]

    def _perturb_loads(
        self, rng: random.Random, has_anomaly: bool,
        affected_bus_idx: int, severity: float, tick: int,
    ) -> None:
        """Apply synthetic load perturbations."""
        if self._base_loads is None:
            return

        base_p, base_q = self._base_loads

        for i in range(len(base_p)):
            scale = 1.0 + rng.uniform(-0.02, 0.02)

            if has_anomaly and i == affected_bus_idx:
                # Heavy perturbation on the affected bus
                phase = math.sin(2 * math.pi * tick / 20)
                anomaly_scale = 1.0 + severity * 0.15 * phase
                scale *= anomaly_scale

            self.runner.net.load.at[i, "p_mw"] = max(0, base_p[i] * scale)
            self.runner.net.load.at[i, "q_mvar"] = base_q[i] * scale

    def generate_dataset(self) -> List[Tuple[Any, torch.Tensor, torch.Tensor]]:
        """Generate the full dataset as a list."""
        data_list: List[Tuple[Any, torch.Tensor, torch.Tensor]] = []
        for data, node_labels, graph_label in self:
            data_list.append((data, node_labels, graph_label))
        return data_list


# ---------------------------------------------------------------------------
# Dataset class
# ---------------------------------------------------------------------------


class GridAnomalyDataset(Dataset):
    """
    PyTorch Dataset for grid anomaly detection.

    Loads pre-generated (data, node_labels, graph_label) triples.
    Works with DataLoader for batched training.
    """

    def __init__(self, samples: List[Tuple[Any, torch.Tensor, torch.Tensor]]):
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[Any, torch.Tensor, torch.Tensor]:
        return self.samples[idx]


def collate_gnn_batch(
    batch: List[Tuple[Any, torch.Tensor, torch.Tensor]],
) -> Tuple[Any, torch.Tensor, torch.Tensor]:
    """
    Collate function for DataLoader.

    Batches multiple PyG Data objects plus their labels.
    """
    from torch_geometric.data import Batch as PyGBatch

    data_list = [item[0] for item in batch]
    node_labels_list = [item[1] for item in batch]
    graph_labels_list = [item[2] for item in batch]

    batch_data = PyGBatch.from_data_list(data_list)
    batch_node_labels = torch.cat(node_labels_list, dim=0)
    batch_graph_labels = torch.cat(graph_labels_list, dim=0)

    return batch_data, batch_node_labels, batch_graph_labels


# ---------------------------------------------------------------------------
# Training utilities
# ---------------------------------------------------------------------------


class EarlyStopping:
    """Stop training when validation loss stops decreasing."""

    def __init__(self, patience: int = 10, min_delta: float = 1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.best_loss = float("inf")
        self.counter = 0

    def step(self, val_loss: float) -> bool:
        """Returns True if training should stop."""
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
            return False
        self.counter += 1
        return self.counter >= self.patience


def compute_metrics(
    node_preds: torch.Tensor,
    node_labels: torch.Tensor,
    graph_logits: torch.Tensor,
    graph_labels: torch.Tensor,
) -> Dict[str, float]:
    """Compute training metrics: accuracy, precision, recall, F1."""
    # Node-level metrics
    node_pred_binary = (node_preds > 0.5).long()
    node_correct = (node_pred_binary == node_labels).float().mean().item()

    # Anomaly detection accuracy (graph-level)
    graph_preds = graph_logits.argmax(dim=-1)
    graph_accuracy = (graph_preds == graph_labels).float().mean().item()

    # Precision / recall for anomaly class
    tp = ((node_pred_binary == 1) & (node_labels == 1)).float().sum().item()
    fp = ((node_pred_binary == 1) & (node_labels == 0)).float().sum().item()
    fn = ((node_pred_binary == 0) & (node_labels == 1)).float().sum().item()

    precision = tp / (tp + fp + 1e-10)
    recall = tp / (tp + fn + 1e-10)
    f1 = 2 * precision * recall / (precision + recall + 1e-10)

    return {
        "node_accuracy": node_correct,
        "graph_accuracy": graph_accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------


def train(args: argparse.Namespace) -> None:
    """Main training entry point."""
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    logger.info(f"Using device: {device}")

    # Output directories
    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    writer = SummaryWriter(log_dir=str(log_dir))

    # -----------------------------------------------------------------------
    # Data generation / loading
    # -----------------------------------------------------------------------
    if args.dataset:
        # Load pre-generated CSV dataset
        logger.info(f"Loading dataset from {args.dataset}")
        data_dir = Path(args.dataset)
        from dt_ml.data.loaders import load_ieee14_voltage_anomaly_dataset
        dataset = load_ieee14_voltage_anomaly_dataset(data_dir)

        # Build samples from CSV
        samples = _build_samples_from_csv(dataset, args)
        logger.info(f"Built {len(samples)} training samples from CSV")

        # Split into train/val
        rng = random.Random(args.seed)
        rng.shuffle(samples)
        val_size = min(max(1, int(len(samples) * args.val_split)), len(samples) - 1)
        val_size = max(0, val_size)

        # Compute anomaly ratio for pos_weight
        all_labels = torch.cat([s[1] for s in samples])
        pos_ratio = all_labels.float().mean().item()

        # Guard against empty splits
        if len(samples) == 0:
            logger.error("No training samples generated — check data generation")
            sys.exit(1)
    else:
        # Generate data on-the-fly
        logger.info(f"Generating synthetic data: {args.scenarios} scenarios x {args.ticks} ticks")

        generator = SyntheticGridGenerator(
            num_scenarios=args.scenarios,
            ticks_per_scenario=args.ticks,
            anomaly_prob=args.anomaly_prob,
            base_seed=args.seed,
            quick=args.quick,
        )
        all_samples = generator.generate_dataset()
        rng = random.Random(args.seed)
        rng.shuffle(all_samples)

        if len(all_samples) == 0:
            logger.error("No training samples generated — check data generation")
            sys.exit(1)

        val_size = min(max(1, int(len(all_samples) * args.val_split)), len(all_samples) - 1)
        val_size = max(0, val_size)
        val_samples = all_samples[:val_size]
        train_samples = all_samples[val_size:]

        # Compute pos_ratio from train labels
        all_train_labels = torch.cat([s[1] for s in train_samples])
        pos_ratio = all_train_labels.float().mean().item()

        # Save generated dataset for reproducibility
        if args.save_dataset:
            save_path = Path(args.save_dataset)
            save_path.mkdir(parents=True, exist_ok=True)
            _save_samples_to_csv(all_samples, save_path)
            logger.info(f"Saved dataset to {save_path}")

        logger.info(f"Train: {len(train_samples)} samples, Val: {len(val_samples)} samples")

        train_dataset = GridAnomalyDataset(train_samples)
        val_dataset = GridAnomalyDataset(val_samples)

    # -----------------------------------------------------------------------
    # Model initialization
    # -----------------------------------------------------------------------
    config = RGATv2Config(
        node_feat_dim=10,
        edge_feat_dim=10,
        hidden_dim=args.hidden_dim,
        latent_dim=args.latent_dim,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
        dropout=args.dropout,
        phys_loss_weight=args.phys_loss_weight,
        focal_gamma=args.focal_gamma,
        pos_weight=max(1.0, (1.0 - pos_ratio) / (pos_ratio + 1e-8)),
    )

    if args.resume:
        logger.info(f"Resuming from checkpoint: {args.resume}")
        model = load_rgatv2(args.resume, device=device)
        # Override config with args if provided
        model.config = config
    else:
        model = RGATv2(config)

    model = model.to(device)

    # Build FaultClassifier (matches model output dimensions)
    classifier = FaultClassifier(
        latent_dim=config.latent_dim,
        node_feat_dim=config.hidden_dim,
        num_fault_types=config.num_fault_types,
        dropout=args.dropout,
    ).to(device)

    # Optimizer
    optimizer = torch.optim.AdamW(
        list(model.parameters()) + list(classifier.parameters()),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    # LR scheduler
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=args.learning_rate * 0.01
    )

    early_stopping = EarlyStopping(patience=args.patience)

    # -----------------------------------------------------------------------
    # Training loop
    # -----------------------------------------------------------------------
    best_val_loss = float("inf")
    start_time = time.time()
    global_step = 0

    logger.info(f"Starting training: {args.epochs} epochs, lr={args.learning_rate}")
    logger.info(f"Model params: {sum(p.numel() for p in model.parameters()):,}")
    logger.info(f"Imbalance: pos_ratio={pos_ratio:.4f}, pos_weight={config.pos_weight:.2f}")

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True,
        collate_fn=collate_gnn_batch, num_workers=0,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False,
        collate_fn=collate_gnn_batch, num_workers=0,
    )

    for epoch in range(1, args.epochs + 1):
        # ---- Train ----
        model.train()
        classifier.train()
        train_loss = 0.0
        train_metrics: Dict[str, float] = {}
        num_train_batches = 0

        for batch_data, node_labels, graph_labels in train_loader:
            batch_data = batch_data.to(device)
            node_labels = node_labels.to(device)
            graph_labels = graph_labels.to(device)

            optimizer.zero_grad()

            # RGATv2 forward
            out = model.forward(
                batch_data.x, batch_data.edge_index, batch_data.edge_attr, batch_data.batch
            )

            # FaultClassifier forward
            cls_out = classifier.forward(
                out["graph_feat"], out["node_embeddings"],
                out["node_scores"], batch_data.batch,
            )

            # Loss: supervised + physics-informed
            loss_dict = model.compute_loss(
                batch_data.x, batch_data.edge_index, batch_data.edge_attr,
                node_labels=node_labels,
                graph_labels=graph_labels,
                batch=batch_data.batch,
            )
            total_loss = loss_dict["loss"]

            # Also add FaultClassifier loss
            cls_graph_loss = F.cross_entropy(cls_out["fault_logits"], graph_labels)
            total_loss = total_loss + cls_graph_loss * 0.5

            total_loss.backward()

            if args.grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(
                    list(model.parameters()) + list(classifier.parameters()),
                    args.grad_clip,
                )

            optimizer.step()

            train_loss += total_loss.item()
            num_train_batches += 1
            global_step += 1

            # Log step
            if global_step % args.log_interval == 0:
                writer.add_scalar("train/step_loss", total_loss.item(), global_step)
                writer.add_scalar("train/lr", scheduler.get_last_lr()[0], global_step)

                # Node prediction metrics
                node_scores = out["node_scores"].squeeze(-1)
                graph_logits = cls_out["fault_logits"]
                metrics = compute_metrics(node_scores, node_labels, graph_logits, graph_labels)
                for k, v in metrics.items():
                    writer.add_scalar(f"train/{k}", v, global_step)

        avg_train_loss = train_loss / max(num_train_batches, 1)

        # ---- Validation ----
        model.eval()
        classifier.eval()
        val_loss = 0.0
        val_metrics: Dict[str, List[float]] = {
            "node_accuracy": [], "graph_accuracy": [],
            "precision": [], "recall": [], "f1": [],
        }
        num_val_batches = 0

        with torch.no_grad():
            for batch_data, node_labels, graph_labels in val_loader:
                batch_data = batch_data.to(device)
                node_labels = node_labels.to(device)
                graph_labels = graph_labels.to(device)

                out = model.forward(
                    batch_data.x, batch_data.edge_index, batch_data.edge_attr, batch_data.batch
                )
                cls_out = classifier.forward(
                    out["graph_feat"], out["node_embeddings"],
                    out["node_scores"], batch_data.batch,
                )

                loss_dict = model.compute_loss(
                    batch_data.x, batch_data.edge_index, batch_data.edge_attr,
                    node_labels=node_labels,
                    graph_labels=graph_labels,
                    batch=batch_data.batch,
                )
                cls_graph_loss = F.cross_entropy(cls_out["fault_logits"], graph_labels)
                total_val_loss = loss_dict["loss"] + cls_graph_loss * 0.5

                val_loss += total_val_loss.item()
                num_val_batches += 1

                # Metrics
                node_scores = out["node_scores"].squeeze(-1)
                graph_logits = cls_out["fault_logits"]
                metrics = compute_metrics(node_scores, node_labels, graph_logits, graph_labels)
                for k, v in metrics.items():
                    val_metrics[k].append(v)

        avg_val_loss = val_loss / max(num_val_batches, 1)

        # Average validation metrics
        avg_val_metrics = {k: float(np.mean(v)) for k, v in val_metrics.items()}

        # Log epoch
        writer.add_scalar("epoch/train_loss", avg_train_loss, epoch)
        writer.add_scalar("epoch/val_loss", avg_val_loss, epoch)
        for k, v in avg_val_metrics.items():
            writer.add_scalar(f"epoch/val_{k}", v, epoch)

        # Scheduler step
        scheduler.step()

        # Print progress
        if epoch % args.print_interval == 0 or epoch == 1:
            elapsed = time.time() - start_time
            logger.info(
                f"Epoch {epoch:3d}/{args.epochs} | "
                f"Train: {avg_train_loss:.4f} | "
                f"Val: {avg_val_loss:.4f} | "
                f"Acc: {avg_val_metrics['node_accuracy']:.3f} | "
                f"F1: {avg_val_metrics['f1']:.3f} | "
                f"Prec: {avg_val_metrics['precision']:.3f} | "
                f"Rec: {avg_val_metrics['recall']:.3f} | "
                f"{elapsed:.0f}s"
            )

        # Checkpoint
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            checkpoint_path = checkpoint_dir / "gridsentinel_ieee14.pt"
            save_rgatv2(
                model, str(checkpoint_path),
                epoch=epoch, val_loss=avg_val_loss,
                metadata={
                    "train_samples": len(train_dataset),
                    "val_samples": len(val_dataset),
                    "args": vars(args),
                    "val_metrics": avg_val_metrics,
                },
            )
            # Also save FaultClassifier weights combined
            combined_state = {
                "model_state_dict": {
                    **model.state_dict(),
                    **{f"classifier.{k}": v for k, v in classifier.state_dict().items()},
                },
                "config": {k: v for k, v in config.__dict__.items() if not k.startswith("_")},
                "epoch": epoch,
                "val_loss": avg_val_loss,
                "metadata": {
                    "train_samples": len(train_dataset),
                    "val_samples": len(val_dataset),
                    "val_metrics": avg_val_metrics,
                },
            }
            combined_path = checkpoint_dir / "gridsentinel_ieee14_full.pt"
            torch.save(combined_state, str(combined_path))
            logger.info(f"Checkpoint saved (val_loss={avg_val_loss:.4f})")

        # Early stopping
        if early_stopping.step(avg_val_loss):
            logger.info(f"Early stopping at epoch {epoch}")
            break

    # ---- Final save ----
    final_path = checkpoint_dir / "gridsentinel_ieee14_final.pt"
    save_rgatv2(model, str(final_path), epoch=args.epochs, val_loss=best_val_loss)
    logger.info(f"Training complete. Best val_loss: {best_val_loss:.4f}")
    logger.info(f"Final model: {final_path}")

    writer.close()


# ---------------------------------------------------------------------------
# CSV-based data building
# ---------------------------------------------------------------------------


# IEEE-14 static topology edges for CSV data reconstruction
# From pandapower IEEE-14 standard test case (bus indices 0-13)
IEEE14_EDGES: List[Tuple[str, str]] = [
    ("bus_0", "bus_1"), ("bus_0", "bus_4"), ("bus_1", "bus_2"), ("bus_1", "bus_3"),
    ("bus_1", "bus_4"), ("bus_2", "bus_3"), ("bus_3", "bus_4"), ("bus_4", "bus_5"),
    ("bus_4", "bus_6"), ("bus_4", "bus_7"), ("bus_4", "bus_8"), ("bus_6", "bus_9"),
    ("bus_6", "bus_10"), ("bus_6", "bus_11"), ("bus_6", "bus_12"), ("bus_7", "bus_8"),
    ("bus_9", "bus_10"), ("bus_11", "bus_12"), ("bus_12", "bus_13"),
]


def _build_samples_from_csv(
    dataset: Any, args: argparse.Namespace = None,
) -> List[Tuple[Any, torch.Tensor, torch.Tensor]]:
    """
    Build training samples from CSV dataset.

    Each (scenario_id, tick) group becomes one sample.
    Edge topology is reconstructed from the static IEEE-14 template.
    """
    from dt_ml.data.loaders import VoltageAnomalyDataset

    assert isinstance(dataset, VoltageAnomalyDataset)
    df_nodes = dataset.node_timeseries
    df_labels = dataset.labels

    samples: List[Tuple[Any, torch.Tensor, torch.Tensor]] = []
    grid_builder = GridBuilder(normalize=False)

    # Build static edges once (same topology for all samples)
    from dt_contracts.models import GridGraphSnapshot, GridNode, GridEdge

    static_edges = [
        GridEdge(
            id=f"line_{s}_{t}", type="Line",
            source=s, target=t,
            static={"r_ohm_per_km": 0.1, "x_ohm_per_km": 0.3, "length_km": 10.0,
                    "max_i_ka": 0.5, "in_service": True},
            dynamic={"loading_percent": 50.0, "p_from_mw": 0.0, "q_from_mvar": 0.0,
                     "p_to_mw": 0.0, "q_to_mvar": 0.0},
        )
        for s, t in IEEE14_EDGES
    ]

    # Group by (scenario_id, tick)
    grouped = df_labels.groupby(["scenario_id", "tick"])

    for (scenario_id, tick), label_row in grouped:
        # Get node data for this tick
        tick_nodes = df_nodes[(df_nodes["scenario_id"] == scenario_id) & (df_nodes["tick"] == tick)]

        if tick_nodes.empty:
            continue

        has_anomaly = bool(label_row["label_voltage_anomaly"].iloc[0])

        nodes = []
        for _, row in tick_nodes.iterrows():
            node = GridNode(
                id=str(row["node_id"]),
                type="Bus",
                static={"vn_kv": 115.0, "in_service": True},
                dynamic={"vm_pu": float(row["vm_pu"]), "va_degree": float(row["va_degree"])},
            )
            nodes.append(node)

        snap = GridGraphSnapshot(
            t=f"ds/{scenario_id}/{tick}",
            topology_hash=f"csv_{scenario_id}_{tick}",
            nodes=nodes,
            edges=static_edges,
        )

        data = grid_builder.build(snap)

        # Labels
        node_labels = torch.zeros(len(nodes), dtype=torch.long)
        if has_anomaly:
            worst_node = label_row["worst_node_id"].iloc[0]
            if worst_node is not None:
                for i, node in enumerate(nodes):
                    if node.id == worst_node:
                        node_labels[i] = 1
                        break

        graph_label = torch.tensor([1 if has_anomaly else 0], dtype=torch.long)

        samples.append((data, node_labels, graph_label))

    return samples


def _save_samples_to_csv(
    samples: List[Tuple[Any, torch.Tensor, torch.Tensor]],
    save_dir: Path,
) -> None:
    """Save generated samples as CSV for reproducibility."""
    rows = []
    label_rows = []

    for idx, (data, node_labels, graph_label) in enumerate(samples):
        n_nodes = data.x.size(0) if hasattr(data, "x") else 0
        for i in range(n_nodes):
            rows.append({
                "sample_id": idx,
                "node_idx": i,
                "vm_pu": data.x[i, 0].item() if hasattr(data, "x") and data.x.size(0) > i else 0.0,
                "va_degree": data.x[i, 1].item() if hasattr(data, "x") and data.x.size(1) > 1 else 0.0,
                "p_mw": data.x[i, 2].item() if hasattr(data, "x") and data.x.size(1) > 2 else 0.0,
                "label_anomaly": int(node_labels[i].item()) if i < len(node_labels) else 0,
            })

        label_rows.append({
            "sample_id": idx,
            "graph_label": int(graph_label[0].item()),
            "num_nodes": n_nodes,
        })

    pd.DataFrame(rows).to_csv(save_dir / "node_timeseries.csv", index=False)
    pd.DataFrame(label_rows).to_csv(save_dir / "labels.csv", index=False)
    # Metadata
    (save_dir / "_DONE.txt").write_text(
        f"samples={len(samples)}\n"
        f"anomaly_labels={sum(1 for _, _, gl in samples if gl[0].item() > 0)}\n",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    p = argparse.ArgumentParser(description="Train RGATv2 GNN for grid anomaly detection")

    # Data
    p.add_argument("--dataset", type=str, default=None,
                   help="Path to pre-generated CSV dataset (skip generation)")
    p.add_argument("--scenarios", type=int, default=20,
                   help="Number of training scenarios to generate")
    p.add_argument("--ticks", type=int, default=60,
                   help="Ticks per scenario")
    p.add_argument("--anomaly-prob", type=float, default=0.15,
                   help="Probability of anomaly in a scenario")
    p.add_argument("--val-split", type=float, default=0.15,
                   help="Validation split ratio")
    p.add_argument("--save-dataset", type=str, default=None,
                   help="Path to save generated dataset")

    # Model
    p.add_argument("--hidden-dim", type=int, default=128)
    p.add_argument("--latent-dim", type=int, default=64)
    p.add_argument("--num-heads", type=int, default=4)
    p.add_argument("--num-layers", type=int, default=3)
    p.add_argument("--dropout", type=float, default=0.15)
    p.add_argument("--phys-loss-weight", type=float, default=0.30)
    p.add_argument("--focal-gamma", type=float, default=2.0)

    # Training
    p.add_argument("--epochs", type=int, default=50,
                   help="Number of training epochs")
    p.add_argument("--batch-size", type=int, default=16,
                   help="Batch size for DataLoader")
    p.add_argument("--learning-rate", type=float, default=1e-3,
                   help="Initial learning rate")
    p.add_argument("--weight-decay", type=float, default=1e-5,
                   help="AdamW weight decay")
    p.add_argument("--grad-clip", type=float, default=1.0,
                   help="Gradient clipping norm (0 to disable)")
    p.add_argument("--patience", type=int, default=15,
                   help="Early stopping patience")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed")

    # Logging / checkpoints
    p.add_argument("--checkpoint-dir", type=str, default="checkpoints",
                   help="Checkpoint output directory")
    p.add_argument("--log-dir", type=str, default="runs/gnn",
                   help="TensorBoard log directory")
    p.add_argument("--log-interval", type=int, default=10,
                   help="Steps between logging")
    p.add_argument("--print-interval", type=int, default=5,
                   help="Epochs between printing")

    # Misc
    p.add_argument("--resume", type=str, default=None,
                   help="Resume from checkpoint path")
    p.add_argument("--cpu", action="store_true",
                   help="Force CPU even if CUDA available")
    p.add_argument("--quick", action="store_true",
                   help="Quick smoke test (reduced data)")

    args = p.parse_args(argv)
    return args


def main() -> None:
    """CLI entry point."""
    args = parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("dt_ml").setLevel(logging.DEBUG if args.quick else logging.INFO)

    # Seed
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)

    logger.info("=" * 60)
    logger.info("RGATv2 Training Pipeline")
    logger.info("=" * 60)

    train(args)


if __name__ == "__main__":
    main()
