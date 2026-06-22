"""
Graph Neural Network module for Grid Digital Twin.

Implements the RGATv2 (Recurrent Graph Attention Network v2) architecture
for real-time power grid anomaly detection and fault classification.

Components:
    - GridBuilder: Converts GridGraphSnapshot into PyTorch Geometric Data objects
    - RGATv2: Multi-layer Recurrent Graph Attention Network with skip connections
    - FaultClassifier: Classification + isolation heads for 5 fault types
    - PretrainedModel: Wrapper for loading and running inference with checkpoints
"""

from .grid_builder import GridBuilder, build_from_snapshot
from .model import RGATv2, RGATv2Config, load_rgatv2, save_rgatv2
from .fault_types import FaultClassifier, FaultType, FaultPrediction, calibrate_with_physics
from .detector import GNNDetector

__all__ = [
    "GridBuilder",
    "build_from_snapshot",
    "RGATv2",
    "RGATv2Config",
    "load_rgatv2",
    "save_rgatv2",
    "FaultClassifier",
    "FaultType",
    "FaultPrediction",
    "calibrate_with_physics",
    "GNNDetector",
]
