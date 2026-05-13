# dt-dashboard (PoC UI)

Vite + React dashboard that shows:
- latest `GridGraphSnapshot`
- latest explanation packet
- live updates via WebSocket

## Run (dev)

1) Start the backend API (from repo root `pbl/`):
```bash
python -m uvicorn dt_orchestrator.api.app:app --app-dir platform/dt-orchestrator --host 127.0.0.1 --port 8000
```

2) Start the UI (from `platform/dt-dashboard/`):
```bash
npm install
npm run dev
```

The dev server proxies:
- `/api/*` → `http://127.0.0.1:8000/*`
- `/ws` → `ws://127.0.0.1:8000/ws`

