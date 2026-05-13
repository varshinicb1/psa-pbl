# Autonomous Explainable Grid Digital Twin (PoC)

This folder contains a **working PoC pipeline** for an **Autonomous Explainable Power Grid Digital Twin Intelligence System**.

## Layout
- `dt-contracts/` — versioned schemas + validation utilities (canonical GridGraph + telemetry + actions + explanations)
- `dt-sim-pandapower/` — fast near-real-time simulation adapter (pandapower)
- `dt-orchestrator/` — streaming loop (ingest → state → PF → publish) + API
- `dt-dashboard/` — web UI (Vite + React) that streams `/ws` and displays snapshot/explanations
- `docs/` — upstream inspection notes + diagrams + interoperability maps

Upstream simulators are cloned under `../upstreams/` and accessed via adapters.

## Quickstart (after dependencies are installed)
1. Install Python deps (recommended: a virtualenv):
   - `pip install -r dt-orchestrator/requirements.txt`
2. Run the PoC demo:
   - `python dt-orchestrator/demo_run.py`
3. (Optional) Run the API server:
   - `python -m uvicorn dt_orchestrator.api.app:app --app-dir dt-orchestrator --host 127.0.0.1 --port 8000`
4. (Optional) Run the dashboard UI:
   - `cd dt-dashboard`
   - `npm install`
   - `npm run dev`

## Status
This is an initial scaffolding that focuses on:
- unified topology+telemetry contracts
- a pandapower-backed near-real-time loop
- structured hooks for multi-simulator expansion (OpenDSS / GridLAB-D / MATPOWER)
