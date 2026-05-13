# Verification / How to Run (PoC)

## 0) Prereqs
- Python 3.10+

## 1) Install dependencies
From the `platform/` folder (or repo root), install:
```bash
python -m pip install -r dt-orchestrator/requirements.txt
python -m pip install pandapower pydantic jsonschema pytest
```

## 2) Run the near-real-time PoC loop (console)
```bash
python dt-orchestrator/demo_run.py
```
Expected behavior:
- builds IEEE-14 using pandapower
- runs 5 ticks of “near-real-time” (synthetic load perturbations)
- runs AC powerflow each tick
- emits an **explainable anomaly packet** when voltage bounds are violated

## 3) Run adapter unit test
```bash
python -m pytest dt-sim-pandapower/tests -q
```

## 3b) MATPOWER backend (optional)
`dt-sim-matpower` is implemented but requires either:
- GNU Octave installed (`octave` on PATH), or
- Docker daemon running (MATPOWER image)

Run optional test:
```bash
python -m pytest dt-sim-matpower/tests -q
```

## 4) Start the API server (optional)
```bash
python -m uvicorn dt_orchestrator.api.app:app --app-dir dt-orchestrator --host 127.0.0.1 --port 8000
```

Endpoints:
- `GET /health`
- `GET /snapshot`
- `WS /ws` streams `{tick, snapshot, explanation}` messages

## Notes
- This PoC currently uses pandapower as the fast “per tick” physics engine. The OpenDSS / GridLAB-D / MATPOWER adapters are planned next (see the approved plan).
