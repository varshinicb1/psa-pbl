# AGENTS.md — Grid Digital Twin Agent Reference

## Project Overview

| Field | Value |
|-------|-------|
| **Project** | Metro Grid Digital Twin — Autonomous Operations Platform |
| **Version** | 2.0.0 |
| **Target** | BESCOM Bangalore metropolitan grid |
| **Language** | Python 3.14+, TypeScript 5.x |
| **License** | Proprietary (government utility use) |

## Component Map

### Core Platform
| Module | Purpose | Entry Point |
|--------|---------|-------------|
| `dt-contracts` | Canonical Pydantic v2 schemas (20 models) | `src/dt_contracts/models.py` |
| `dt-orchestrator` | FastAPI server + tick loop + state store | `api/app.py`, `pipelines/realtime_tick.py` |

### Simulation
| Module | Purpose | Status |
|--------|---------|--------|
| `dt-sim-pandapower` | Primary AC powerflow (pandapower) | Production |
| `dt-sim-opendss` | Distribution grid (OpenDSS) | Production (optional) |
| `dt-sim-matpower` | Cross-validation (MATPOWER/Octave) | Production (optional) |
| `dt-sim-gridlabd` | Distribution (GridLAB-D) | Production (optional) |
| `dt-bescom` | BESCOM 50-bus Bangalore grid model | Production |
| `dt-cim` | IEC 61970/61968 CIM adapter | Production |

### ML & Analytics
| Module | Purpose | Status |
|--------|---------|--------|
| `dt-ml` | 4-detector ensemble (Z-score, ROC, LSTM, physics) | Production |

### SCADA Integration
| Module | Protocol | Library | Status |
|--------|----------|---------|--------|
| `dt-scada/dnp3.py` | DNP3 (pure Python, spec-compliant) | None required | Production |
| `dt-scada/iec61850.py` | IEC 61850 GOOSE + MMS | ctypes (optional) | Production |
| `dt-scada/modbus.py` | Modbus TCP/RTU | pymodbus 3.13+ | Production |

### Security & Compliance
| Module | Purpose | Status |
|--------|---------|--------|
| `dt-security` | RBAC, HMAC API keys, audit logging | Production |
| `dt-compliance` | NERC CIP, IEGC 2023, AES-256-GCM | Production |

### UI & Infrastructure
| Module | Stack | Status |
|--------|-------|--------|
| `dt-dashboard` | React 19 + TypeScript + Tailwind v4 | Production |
| `dt-infrastructure` | Docker, k8s, Prometheus, CI/CD | Production |

## Key Commands

```bash
# Run all tests
$env:PYTHONPATH="platform/dt-contracts/python/src;platform/dt-sim-pandapower;platform/dt-orchestrator;platform/dt-ml;platform/dt-scada-protocols/src;platform/dt-compliance/src;platform/dt-cim/src;platform/dt-bescom/src;platform/dt_security;platform"
python -m pytest tests/ platform/dt-compliance/tests/ platform/dt-cim/tests/ platform/dt-sim-pandapower/tests/ platform/dt-bescom/tests/ -v -o "addopts=" --no-header -p no:cov

# Run demo (IEEE-14)
python platform/dt-orchestrator/demo_run.py

# Run demo (BESCOM Bangalore)
python platform/dt-orchestrator/demo_run.py --bescom

# Start API server
$env:GRID_TYPE="bescom"
uvicorn dt_orchestrator.api.app:app --host 127.0.0.1 --port 8000 --app-dir platform/dt-orchestrator

# Start dashboard
cd platform/dt-dashboard && npm run dev

# Generate images
python scripts/generate_images.py
```

## Test Results

| Module | Tests | Status |
|--------|-------|--------|
| Contracts | 17 | All pass |
| ML Ensemble | 6 | All pass |
| SCADA Protocols | 42 | All pass |
| Security | 10 | All pass |
| Compliance | 6 | All pass |
| CIM | 3 | All pass |
| BESCOM | 13 | All pass |
| Integration | 8 | All pass |
| Dashboard (TS) | 30 | All pass |
| **Total** | **139** | **100%** |

## Architecture Diagram

![Architecture](docs/images/architecture.png)

## Real SCADA Protocol Stack

```
                    ┌─────────────────────┐
                    │   Operations App    │
                    │  (FastAPI + Redis)  │
                    └──────┬──────┬──────┘
                           │      │
              ┌────────────┼──────┼────────────┐
              │            │      │            │
     ┌────────▼──┐  ┌─────▼──┐ ┌─▼──────┐  ┌──▼────────┐
     │ IEC 61850 │  │  DNP3  │ │ Modbus │  │  CIM      │
     │ GOOSE/MMS │  │ Master │ │ TCP    │  │  IEC 61970│
     │ (ASN.1)   │  │(DNP3.0)│ │(pymodbus)│  │  (XML/RDF)│
     └─────┬─────┘  └────┬───┘ └───┬─────┘  └─────┬─────┘
           │             │         │              │
      ┌────▼────┐  ┌─────▼───┐  ┌──▼────┐  ┌─────▼────┐
      │ GOOSE  │  │  TCP     │  │ TCP   │  │  File    │
      │ L2 MC   │  │  20000   │  │ 502   │  │  Import  │
      └─────────┘  └─────────┘  └───────┘  └──────────┘
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRID_TYPE` | `ieee14` | Grid backend: `ieee14` or `bescom` |
| `DT_LOG_LEVEL` | `INFO` | Logging level |
| `DT_API_PORT` | `8000` | API server port |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `VITE_WS_HOST` | auto | WebSocket host for dashboard |
