# Deployment & Operations Guide

## Autonomous Explainable Grid Digital Twin

This guide covers deployment, configuration, monitoring, and troubleshooting for production research environments.

## Prerequisites

- Python 3.10+
- pandapower 3.4.0+
- FastAPI + Uvicorn
- Node.js 18+ (for dashboard, optional)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/varshinicb1/psa-pbl.git
cd psa-pbl
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Production dependencies only
pip install -r platform/dt-orchestrator/requirements.txt

# Or with development tools (linting, testing, type checking)
pip install -r platform/dt-orchestrator/requirements-dev.txt
```

### 4. Verify Installation

```bash
python platform/dt-orchestrator/demo_run.py
```

Expected output:
- 5 ticks executed
- Voltage anomalies reported if detected
- No errors

## Configuration

### Environment Variables

Create `.env` file in repository root:

```env
# Simulation parameters
DT_SIM_VOLTAGE_LOWER_BOUND=0.95
DT_SIM_VOLTAGE_UPPER_BOUND=1.05
DT_SIM_TICK_INTERVAL_SECONDS=1.0
DT_SIM_MAX_POWERFLOW_ITERATIONS=50
DT_SIM_POWERFLOW_TOLERANCE=1e-6

# API settings
DT_API_HOST=0.0.0.0
DT_API_PORT=8000
DT_API_WORKERS=4
DT_API_WS_HEARTBEAT_INTERVAL=30.0
DT_API_WS_MAX_CONNECTIONS=100
DT_API_WS_MESSAGE_TIMEOUT=5.0

# Logging
DT_LOG_LEVEL=INFO
DT_LOG_FORMAT=json
DT_LOG_FILE=logs/dt.log
DT_LOG_CONSOLE=true

# Paths
DT_PATH_DATA_DIR=./data
DT_PATH_LOG_DIR=./logs
DT_PATH_TEMP_DIR=./tmp

# Environment
ENV=production
DEBUG=false
```

### Configuration Priority

1. Environment variables (highest)
2. `.env` file
3. Code defaults (lowest)

## Running the Application

### 1. Demo Mode (Offline Testing)

```bash
python platform/dt-orchestrator/demo_run.py
```

Output:
- 5 ticks of IEEE-14 grid simulation
- Console logs with anomalies
- Suitable for verification

### 2. API Server (Production Mode)

```bash
cd platform/dt-orchestrator
python -m uvicorn dt_orchestrator.api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4
```

Or use Python directly:
```bash
python -m dt_orchestrator.api.app
```

### 3. Dashboard (Optional UI)

```bash
cd platform/dt-dashboard
npm install
npm run dev
```

Access at: `http://localhost:5173`

## API Endpoints

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "running": true,
  "tick_task_alive": true,
  "last_tick": 42,
  "connected_clients": 3
}
```

### Current Snapshot

```bash
curl http://localhost:8000/snapshot
```

### WebSocket Streaming

```bash
# Python example
import asyncio
import websockets
import json

async def stream():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as ws:
        async for msg in ws:
            data = json.loads(msg)
            print(f"Tick {data['tick']}: {data['snapshot']['t']}")

asyncio.run(stream())
```

## Monitoring & Observability

### Structured Logging

All logs are JSON formatted with correlation IDs:

```json
{
  "timestamp": "2026-06-16T03:07:52.400Z",
  "level": "INFO",
  "logger": "dt_orchestrator.api.app",
  "message": "WebSocket connected - total clients: 1",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Log Levels

- `DEBUG`: Detailed execution flow (development only)
- `INFO`: Key events (start, ticks, connections)
- `WARNING`: Recoverable issues (convergence failures, timeouts)
- `ERROR`: Failures with context (exceptions with stack traces)
- `CRITICAL`: Service failures

### Health Checks for Kubernetes

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

## Performance Tuning

### Simulation Parameters

- `TICK_INTERVAL_SECONDS`: Time between simulation steps
  - Smaller = higher fidelity but higher CPU
  - Recommended: 0.5 - 2.0 seconds
  
- `MAX_POWERFLOW_ITERATIONS`: AC powerflow convergence limit
  - Higher = more accurate but slower
  - Recommended: 40 - 50 iterations

### API Tuning

- `WORKERS`: Number of worker processes
  - Set to `2 * CPU_COUNT` for I/O-bound workloads
  - Each worker runs independent event loop
  
- `WS_MAX_CONNECTIONS`: Maximum concurrent WebSocket connections
  - Memory scales with clients (snapshot size)
  - Monitor: `connected_clients` in health check

### Network

- `WS_MESSAGE_TIMEOUT`: Timeout for sending to slow clients (seconds)
  - Default 5s - increase if clients are distant
  - Too high risks memory buildup from slow connections

## Troubleshooting

### Powerflow Not Converging

**Symptom**: High rate of convergence failures (warnings in logs)

**Causes**:
- Extreme load/generation values
- Network topology issues
- Algorithm unsuitable for grid

**Solutions**:
1. Check synthetic load perturbation range (±2% default)
2. Verify IEEE-14 network loads are reasonable
3. Try different algorithm: `algorithm="bfsw"` in realtime_tick.py

### WebSocket Clients Disconnecting

**Symptom**: `WebSocket send timeout` or clients repeatedly reconnecting

**Causes**:
- Network latency
- Slow client processing
- Snapshot size too large

**Solutions**:
1. Increase `WS_MESSAGE_TIMEOUT` if latency > 5s
2. Check client processing speed
3. Monitor message sizes in debug logs

### Memory Growth

**Symptom**: Process memory increasing over time

**Causes**:
- Many WebSocket connections not closing properly
- Snapshot history limit too high
- Logging to file without rotation

**Solutions**:
1. Check active connections: `/health` endpoint
2. Reduce `history_limit` in GridGraphStore (default 500)
3. Ensure log rotation is configured in `/etc/logrotate.d/` or Docker

## Security Considerations

### Authentication (Future)

- API endpoints should use JWT or API keys
- WebSocket connections should authenticate on connect
- See: `dt_contracts/exceptions.py` for auth error types

### Input Validation

- All user inputs validated with Pydantic
- Grid size limits enforced (see config)
- Path traversal prevention for file operations

### Secrets Management

- No credentials in code (use environment variables)
- `.env` files should NOT be committed
- Use secrets management service (HashiCorp Vault, AWS Secrets Manager, etc.)

## Maintenance

### Backup

```bash
# Backup dataset directory
tar -czf backup_datasets_$(date +%Y%m%d).tar.gz platform/datasets/

# Backup logs
tar -czf backup_logs_$(date +%Y%m%d).tar.gz logs/
```

### Updates

```bash
# Update dependencies safely
pip install --upgrade -r platform/dt-orchestrator/requirements.txt

# Run tests to verify
pytest platform/ --cov=platform
```

### Database/State Cleanup

- GridGraphStore history is in-memory (no persistence)
- Snapshot limit: 500 (configurable)
- Periodic restarts clear history

## Kubernetes Deployment

### Docker Image

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -r platform/dt-orchestrator/requirements.txt
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "dt_orchestrator.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### StatefulSet Example

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: dt-orchestrator
spec:
  serviceName: dt-orchestrator
  replicas: 1
  selector:
    matchLabels:
      app: dt-orchestrator
  template:
    metadata:
      labels:
        app: dt-orchestrator
    spec:
      containers:
      - name: orchestrator
        image: dt-orchestrator:latest
        ports:
        - containerPort: 8000
        env:
        - name: DT_API_HOST
          value: "0.0.0.0"
        - name: DT_LOG_LEVEL
          value: "INFO"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

## Support & Debugging

### Enable Debug Logging

```bash
export DT_LOG_LEVEL=DEBUG
python -m dt_orchestrator.api.app
```

### Generate Debug Report

```bash
python platform/dt-orchestrator/debug_report.py > debug_report.txt
```

### Contact Research Team

- Issues: GitHub Issues tracker
- Questions: Documentation wiki
- Bugs: Email with correlation IDs and logs

---

**Last Updated**: 2026-06-16  
**Version**: 1.0.0  
**Status**: Production Ready for Research Environments
