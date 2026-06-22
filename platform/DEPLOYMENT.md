# Deployment Guide — Metro Grid Digital Twin

## Prerequisites

- Docker & Docker Compose (recommended for production)
- Python 3.10+ (for local development)
- Node.js 22+ (for dashboard development)

## Quick Start (Docker)

```bash
# From the platform/ directory
docker-compose up --build
```

This starts:
- **Orchestrator** (FastAPI) on `:8000`
- **Dashboard** (Vite dev) on `:5173`
- **Prometheus** on `:9090`
- **Grafana** on `:3000`
- **Redis** on `:6379`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRID_TYPE` | `ieee14` | Grid backend: `ieee14` or `bescom` |
| `DT_LOG_LEVEL` | `INFO` | Logging level |
| `DT_API_PORT` | `8000` | API server port |
| `DT_SIM_VOLTAGE_LOWER_BOUND` | `0.95` | Voltage anomaly lower bound (p.u.) |
| `DT_SIM_VOLTAGE_UPPER_BOUND` | `1.05` | Voltage anomaly upper bound (p.u.) |
| `REDIS_HOST` | `localhost` | Redis host for distributed mode |

## Production Deployment

### Single Node
```bash
DT_LOG_LEVEL=INFO GRID_TYPE=bescom \
  uvicorn dt_orchestrator.api.app:app \
  --host 0.0.0.0 --port 8000 --workers 4
```

### Kubernetes
See `k8s/` manifests for StatefulSet + Service definitions.

## Health Check

```bash
curl http://localhost:8000/health
# {"status":"healthy","version":"2.0.0","running":true,"grid_type":"ieee14",...}
```

## Monitoring

- **Prometheus metrics**: `GET /metrics/prometheus`
- **Grafana dashboards**: Import from `dt-infrastructure/monitoring/`
