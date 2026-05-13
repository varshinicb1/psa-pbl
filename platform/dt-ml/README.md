# dt-ml (skeleton)

Machine learning / inference layer for the digital twin.

This is currently a **skeleton** that provides:
- dataset loader for the minimal IEEE-14 anomaly dataset (`platform/datasets/ieee14_voltage_anomaly/`)
- a model interface (`TwinModel`) and a baseline `PhysicsRuleModel` that produces `ExplanationPacket`s

Next iterations will replace/augment the baseline with:
- temporal GNN / graph transformer models
- physics-informed loss terms (Kirchhoff/power-balance residuals)
- uncertainty estimation + calibration
- Captum / subgraph explainers

