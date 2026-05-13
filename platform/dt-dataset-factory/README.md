# dt-dataset-factory (minimal)

Minimal synthetic scenario generator for the PoC.

Current generator:
- IEEE-14 via pandapower
- stochastic load perturbations per tick
- labels voltage anomalies (vm_pu outside [0.95, 1.05])

Outputs are written to `platform/datasets/` as CSV, and Parquet if `pyarrow` is installed.

