# Metro Grid Digital Twin — Autonomous Operations Platform

[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-00cec9)](https://python.org)
[![TypeScript 5.x](https://img.shields.io/badge/TypeScript-5.x-0984e3)](https://typescriptlang.org)
[![Tests](https://img.shields.io/badge/Tests-139-6c5ce7)](https://github.com/varshinicb1/psa-pbl)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**Production-grade digital twin for metropolitan power grid operations.** Real-time simulation, ML-based anomaly detection, SCADA protocol integration (IEC 61850, DNP3, Modbus), and a world-class operations dashboard — built for the **BESCOM Bangalore** 50-bus metropolitan grid.

---

## Table of Contents

- [Quick Install](#-quick-install)
- [Project Architecture](#-project-architecture)
- [Module Reference](#-module-reference)
- [Running the Project](#-running-the-project)
- [Testing](#-testing)
- [Automatic Commit & Push](#-automatic-commit--push)
- [Contributing](#-contributing)
- [Docker Deployment](#-docker-deployment)
- [Environment Variables](#-environment-variables)
- [API Reference](#-api-reference)
- [License](#-license)

---

## 🚀 Quick Install

### Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10+ (3.14 recommended) | `python --version` |
| Node.js | 22+ | `node --version` |
| npm | 10+ | `npm --version` |
| Git | Any recent | `git --version` |

### 1. Clone the Repository

```bash
git clone https://github.com/varshinicb1/psa-pbl.git
cd psa-pbl
```

### 2. Python Setup (Virtual Environment)

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
# Production dependencies
pip install -r platform/dt-orchestrator/requirements.txt

# Development dependencies (testing, linting, docs)
pip install -r platform/dt-orchestrator/requirements-dev.txt

# Additional runtime dependencies
pip install numpy pandapower pymodbus
```

### 4. Install Dashboard Dependencies

```bash
cd platform/dt-dashboard
npm install
cd ../../
```

### 5. Install Pre-commit Hooks (Optional but Recommended)

```bash
pip install pre-commit
pre-commit install
```

---

## 🏗 Project Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    dt-orchestrator (FastAPI)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Bootstrap │→│ Tick Loop│→│Powerflow │→│ ML Detection     │  │
│  │ (paths)   │  │(asyncio) │  │(adapter) │  │(Physics + ML)   │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┬─────────┘  │
│                                                      │             │
│  ┌───────────────────────────────────────────────────▼──────────┐  │
│  │              Publish (REST + WebSocket)                       │  │
│  │  /health  /snapshot  /topology  /history  /ws  /metrics      │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                    dt-dashboard (React + Vite + D3)                  │
│  StatusBar │ QuickStats │ TopologyMap │ VoltageChart                │
│  AnomalyPanel │ TimelineChart │ NodeInspector │ ErrorBoundary       │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Simulator Adapters                    SCADA / Compliance         │
│  ┌──────────┐ ┌────────┐ ┌─────────┐  ┌──────────┐ ┌──────────┐ │
│  │Pandapower│ │OpenDSS │ │MATPOWER │  │IEC 61850 │ │NERC CIP  │ │
│  │ (Active) │ │(Skel.) │ │(Skel.)  │  │ DNP3     │ │IEGC 2023 │ │
│  └──────────┘ └────────┘ └─────────┘  │ Modbus   │ │AES-256   │ │
│  ┌──────────┐ ┌────────┐              └──────────┘ └──────────┘ │
│  │GridLAB-D │ │BESCOM  │                                        │
│  │ (Skel.)  │ │ (50bus)│  ┌──────────────┐  ┌───────────────┐  │
│  └──────────┘ └────────┘  │  ML Ensemble  │  │ Restoration   │  │
│                           │ Z-Score / ROC  │  │ Agent (Advisor)│  │
│                           │ LSTM / Physics │  └───────────────┘  │
│                           └────────────────┘                     │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow (Per Tick)

```
Telemetry Ingestion → Powerflow (pandapower) → State Update
    → ML Anomaly Detection (4-detector ensemble)
    → Explanation Generation → Publish (WebSocket)
```

### Grid Backends

| Grid | Buses | Lines | Transformers | Purpose |
|------|-------|-------|-------------|---------|
| **IEEE-14** (default) | 14 | 20 | 3 | Testing & development |
| **BESCOM Bangalore** | 50 | 37 | 63 | Production metropolitan grid |

---

## 📦 Module Reference

All modules live under `platform/`:

| Module | Status | Description |
|--------|--------|-------------|
| `dt-orchestrator/` | ✅ **Production** | Central orchestrator with FastAPI server, tick loop, state store, REST/WebSocket endpoints |
| `dt-contracts/` | ✅ **Production** | Canonical Pydantic v2 schemas (GridGraphSnapshot, TelemetryTick, ActionPlan, ExplanationPacket) |
| `dt-sim-pandapower/` | ✅ **Production** | Primary simulator adapter — fast AC powerflow via pandapower |
| `dt-bescom/` | ✅ **Production** | BESCOM Bangalore 50-bus grid model with real load profiles and CSV data |
| `dt-dashboard/` | ✅ **Production** | React 19 + Vite + D3.js operations dashboard (234 kB production build) |
| `dt-ml/` | 🟡 **Active** | 4-detector ML ensemble (Physics Rule, Z-Score, Rate-of-Change, LSTM) + RGATv2 GNN checkpoints |
| `dt-scada-protocols/` | 🟡 **Active** | Real SCADA protocol stack — IEC 61850 (GOOSE/MMS), DNP3, Modbus |
| `dt-compliance/` | 🟡 **Active** | NERC CIP (10 requirements), Indian Grid Code IEGC 2023 (7 checks), AES-256 encryption |
| `dt-cim/` | 🟡 **Active** | Common Information Model adapter for utility data exchange |
| `dt_security/` | 🟡 **Active** | RBAC (5 roles), HMAC-SHA256 API keys, immutable audit logging |
| `dt-restoration-agent/` | 🔧 **Skeleton** | Advisory grid restoration with safety constraints |
| `dt-sim-opendss/` | 🔧 **Skeleton** | OpenDSS adapter for distribution/unbalanced simulation |
| `dt-sim-matpower/` | 🔧 **Skeleton** | MATPOWER adapter for transmission PF/OPF benchmarking |
| `dt-sim-gridlabd/` | 🔧 **Skeleton** | GridLAB-D adapter for time-domain simulation |
| `dt-dataset-factory/` | 🔧 **Skeleton** | Synthetic IEEE-14 anomaly dataset generator |
| `dt-infrastructure/` | 🔧 **Skeleton** | Docker, Kubernetes, Prometheus/Grafana monitoring configs |

---

## 🎮 Running the Project

### Demo (IEEE-14, 5 ticks)

```bash
# From the repo root
python platform/dt-orchestrator/demo_run.py
```

### Demo (BESCOM Bangalore Grid)

```bash
python platform/dt-orchestrator/demo_run.py --bescom
```

### API Server

```bash
# IEEE-14 backend (default)
uvicorn dt_orchestrator.api.app:app --host 127.0.0.1 --port 8000 --app-dir platform/dt-orchestrator

# BESCOM backend
GRID_TYPE=bescom uvicorn dt_orchestrator.api.app:app --host 127.0.0.1 --port 8000 --app-dir platform/dt-orchestrator
```

### Dashboard (Dev Mode)

```bash
# In a separate terminal — start the backend first
cd platform/dt-dashboard
npm install
npm run dev
```

The dashboard auto-proxies:
- `/api/*` → `http://127.0.0.1:8000/*`
- `/ws` → `ws://127.0.0.1:8000/ws`

Open **http://localhost:5173** in your browser.

### BESCOM Standalone Demo

```bash
cd platform/dt-bescom
python demo_bescom.py
```

---

## 🧪 Testing

### Running All Tests

```bash
# Set PYTHONPATH for all modules
export PYTHONPATH="platform/dt-contracts/python/src:platform/dt-sim-pandapower:platform/dt-orchestrator:platform/dt-ml:platform/dt-scada-protocols/src:platform/dt-compliance/src:platform/dt-cim/src:platform/dt-bescom/src:platform/dt_security:platform"

# Run all tests
python -m pytest platform/dt-sim-pandapower/tests/ platform/dt-ml/tests/ -v --no-header -p no:cov
```

### Test Suites

| Suite | Command | Requires |
|-------|---------|----------|
| ML Ensemble | `pytest platform/dt-ml/tests/ -v` | numpy |
| Pandapower | `pytest platform/dt-sim-pandapower/tests/ -v` | pandapower |
| BESCOM | `pytest platform/dt-bescom/tests/ -v` | pandapower |
| Compliance | `pytest platform/dt-compliance/tests/ -v` | — |
| CIM | `pytest platform/dt-cim/tests/ -v` | — |
| Dashboard | `cd platform/dt-dashboard && npx vitest run` | Node.js |

### Code Quality Checks

```bash
# Format code
black platform/

# Lint
ruff check platform/

# Type check
mypy platform/
```

---

## 🤖 Automatic Commit & Push

A convenience script `git-auto.sh` handles the entire commit-and-push workflow:

```bash
# Commit and push with a default timestamp message
bash git-auto.sh

# Commit and push with a custom message
bash git-auto.sh "Your commit message here"
```

**What it does:**
1. Stages all changes (`git add -A`)
2. Skips if nothing to commit
3. Shows staged file summary
4. Commits with your message (or auto-generated timestamp)
5. Pushes to the current branch on `origin`

For Windows users who want to automate this, add the script as a scheduled task or git alias:

```bash
git config --global alias.auto '!bash git-auto.sh'
git auto  # Now works like any git command
```

---

## 👥 Contributing

We welcome contributions! Here's how to get started.

### Development Workflow

```bash
# 1. Create a feature branch
git checkout -b feature/my-feature

# 2. Make your changes

# 3. Run tests to verify
bash git-auto.sh test  # or pytest directly

# 4. Format and lint
black platform/
ruff check platform/

# 5. Commit and push
bash git-auto.sh "feat(scope): description of changes"
```

### Code Standards

- **Python**: Black formatter (line length 100), Ruff linter, MyPy type checker
- **TypeScript**: Strict TypeScript config, Vitest for testing
- **Pre-commit**: Auto-formatting on commit (install with `pre-commit install`)

### Commit Message Format

```
<type>(<scope>): <subject>

<body>
```

**Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `style`, `perf`, `security`

**Example:**
```
feat(api): add graceful WebSocket shutdown

- Implement lifespan context manager for cleanup
- Cancel background tasks on shutdown
- Close client connections with proper timeout
```

### Pull Request Checklist

- [ ] Tests pass (`pytest platform/*/tests/`)
- [ ] Code formatted (`black platform/`)
- [ ] Lint passes (`ruff check platform/`)
- [ ] Types check (`mypy platform/`)
- [ ] Pre-commit hooks pass
- [ ] Added/updated documentation

### Project Structure Guidelines

- Each module is self-contained under `platform/dt-*/`
- Shared schemas belong in `dt-contracts/`
- Simulator adapters follow the `adapter.py` pattern
- Tests go in `tests/` within each module
- Use structured logging (`dt_contracts.logging_config`) not `print()`

### Need Help?

- Check existing module READMEs in `platform/`
- Review this README for architecture context
- Create a GitHub issue for questions

---

## 🐳 Docker Deployment

### Full Stack

```bash
cd platform
docker-compose up --build
```

This starts: Orchestrator (`:8000`), Dashboard (`:5173`), Prometheus (`:9090`), Grafana (`:3000`), Redis (`:6379`).

### Individual Containers

```bash
# Build orchestrator
docker build -f platform/Dockerfile -t dt-orchestrator:latest .
docker run -p 8000:8000 dt-orchestrator:latest

# Build dashboard (production)
docker build -f platform/dt-dashboard/Dockerfile -t dt-dashboard:latest platform/dt-dashboard
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRID_TYPE` | `ieee14` | Grid backend: `ieee14` or `bescom` |
| `DT_LOG_LEVEL` | `INFO` | Logging level |
| `DT_API_PORT` | `8000` | API server port |
| `DT_SIM_VOLTAGE_LOWER_BOUND` | `0.95` | Voltage anomaly lower bound (p.u.) |
| `DT_SIM_VOLTAGE_UPPER_BOUND` | `1.05` | Voltage anomaly upper bound (p.u.) |
| `DT_SIM_TICK_INTERVAL_SECONDS` | `1.0` | Seconds between ticks |
| `DT_SIM_LOADING_THRESHOLD_PERCENT` | `90.0` | Line loading alarm threshold |
| `REDIS_HOST` | `localhost` | Redis host for distributed mode |
| `REDIS_PORT` | `6379` | Redis port |

---

## 📡 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with version, uptime, grid type |
| `/snapshot` | GET | Latest grid snapshot (full state) |
| `/topology` | GET | Grid topology (nodes + edges) |
| `/history?limit=100` | GET | Tick history |
| `/metrics/prometheus` | GET | Prometheus-format metrics |
| `/commands/perturb` | POST | Inject load perturbation |
| `/ws` | WS | Real-time tick stream |

---

## 📄 License

[MIT License](LICENSE) — Copyright (c) 2026 Varshini CB, Vedant, Sethu S, Aravind Kumar N

---

## 👥 Team

- **Varshini CB**
- **Vedant**
- **Sethu S**
- **Aravind Kumar N**

*6th Semester Power System Analysis — Project Based Learning (PBL), 2026.*

**Version 2.0.0**
