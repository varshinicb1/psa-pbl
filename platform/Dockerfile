FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY dt-orchestrator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY dt-contracts/python/src /app/dt-contracts
COPY dt-sim-pandapower /app/dt-sim-pandapower
COPY dt-orchestrator /app/dt-orchestrator
COPY dt-ml /app/dt-ml
COPY dt-scada-protocols/src /app/dt-scada

ENV PYTHONPATH="/app/dt-contracts:/app/dt-sim-pandapower:/app/dt-orchestrator:/app/dt-ml:/app/dt-scada"

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app /app

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "dt_orchestrator.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
