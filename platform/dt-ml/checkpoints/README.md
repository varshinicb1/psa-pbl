# Pretrained GNN Checkpoints

This directory stores pretrained RGATv2 model weights for production inference.

## Available Checkpoints

| File | Grid | Size | Val Loss | Accuracy | Notes |
|------|------|------|----------|----------|-------|
| `gridsentinel_ieee14.pt` | IEEE 14-bus | ~2 MB | — | — | Trained on synthetic perturbations |
| `gridsentinel_ieee118.pt` | IEEE 118-bus | ~12 MB | — | — | Requires downsampling for limited hardware |

## Training

To train from scratch:

```bash
# Generate synthetic fault data
python platform/dt-dataset-factory/generate_ieee14_voltage_anomaly.py

# Train the RGATv2 model
python -m dt_ml.gnn.train --grid ieee14 --epochs 200 --lr 1e-3
```

## Model Architecture

Each checkpoint contains:

- `model_state_dict` — RGATv2 + FaultClassifier weights
- `config` — RGATv2Config hyperparameters
- `epoch` — Training epoch at save
- `val_loss` — Best validation loss
- `metadata` — Training metadata (dataset size, grid type, etc.)

## Inference

```python
from dt_ml.gnn.model import load_rgatv2
from dt_ml.gnn import GridBuilder, FaultClassifier

model = load_rgatv2("checkpoints/gridsentinel_ieee14.pt")
model.eval()
```

## Citation

If using these models in research, please cite:

```
@software{gridsentinel2026,
  author = {Varshini C B and Dr. Manjunatha C},
  title  = {GridSentinel: GNN-based Anomaly Detection for Power Grids},
  year   = {2026},
}
```
