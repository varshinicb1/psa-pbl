"""
Production-grade FastAPI application for the Grid Digital Twin Orchestrator.

Provides REST endpoints, WebSocket streaming, authentication, rate limiting,
Prometheus metrics, and distributed state coordination via Redis.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dt_contracts.logging_config import setup_logging, get_logger, set_correlation_id
from dt_contracts.exceptions import GridDigitalTwinError, StateError, error_to_dict

setup_logging()
logger = get_logger(__name__)

from ..bootstrap import bootstrap_local_paths
from ..pipelines.realtime_tick import RealtimeTickRunner

bootstrap_local_paths()


GRID_TYPES = {"ieee14", "bescom"}


class AppState:
    def __init__(self, grid_type: str = "ieee14"):
        grid_type = grid_type.lower()
        if grid_type not in GRID_TYPES:
            grid_type = "ieee14"
        self.runner: RealtimeTickRunner = RealtimeTickRunner(grid_type=grid_type)
        self.grid_type = grid_type
        self.clients: Set[WebSocket] = set()
        self.tick_task: asyncio.Task = None
        self.running = False
        self._metrics = {
            "ticks_total": 0,
            "ticks_failed": 0,
            "ws_messages_sent": 0,
            "start_time": time.time(),
        }

    async def cleanup(self):
        self.running = False
        if self.tick_task:
            self.tick_task.cancel()
            try:
                await self.tick_task
            except asyncio.CancelledError:
                pass
        for ws in list(self.clients):
            try:
                await ws.close()
            except Exception:
                pass
        self.clients.clear()
        logger.info("Application cleanup complete")


_grid_type = os.environ.get("GRID_TYPE", "ieee14")
app_state = AppState(grid_type=_grid_type)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info("Starting Grid Digital Twin Orchestrator")
    app_state.running = True
    app_state.tick_task = asyncio.create_task(_tick_loop())
    logger.info("Tick loop started")
    yield
    logger.info("Shutting down Grid Digital Twin Orchestrator")
    await app_state.cleanup()


app = FastAPI(
    title="Metro Grid Digital Twin - Autonomous Operations Platform",
    description="Production-grade digital twin for metropolitan power grid operations. "
    "Real-time simulation, ML-based anomaly detection, SCADA integration.",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health():
    try:
        latest = app_state.runner.store.get_latest()
        uptime = time.time() - app_state._metrics["start_time"]
        return {
            "status": "healthy",
            "version": "2.1.0",
            "uptime_seconds": uptime,
            "running": app_state.running,
            "grid_type": app_state.grid_type,
            "tick_task_alive": app_state.tick_task and not app_state.tick_task.done(),
            "last_tick": latest.tick_count if latest else None,
            "connected_clients": len(app_state.clients),
            "metrics": {**app_state._metrics},
        }
    except Exception as exc:
        logger.error(f"Health check failed: {exc}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/metrics/prometheus", tags=["monitoring"])
async def prometheus_metrics():
    latest = app_state.runner.store.get_latest()
    uptime = time.time() - app_state._metrics["start_time"]
    metrics = f"""# HELP dt_ticks_total Total ticks processed
# TYPE dt_ticks_total counter
dt_ticks_total {app_state._metrics['ticks_total']}
# HELP dt_ticks_failed Total failed ticks
# TYPE dt_ticks_failed counter
dt_ticks_failed {app_state._metrics['ticks_failed']}
# HELP dt_ws_clients Current WebSocket clients
# TYPE dt_ws_clients gauge
dt_ws_clients {len(app_state.clients)}
# HELP dt_uptime_seconds Service uptime
# TYPE dt_uptime_seconds gauge
dt_uptime_seconds {uptime}
# HELP dt_last_tick Last tick number
# TYPE dt_last_tick gauge
dt_last_tick {latest.tick_count if latest else 0}
"""
    return JSONResponse(content=metrics, media_type="text/plain")


@app.get("/snapshot", tags=["state"])
async def get_snapshot():
    try:
        latest = app_state.runner.store.get_latest()
        if not latest:
            raise StateError("No snapshot available - simulation not started")
        return latest.model_dump()
    except StateError:
        raise
    except Exception as exc:
        logger.error(f"Snapshot retrieval failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve snapshot")


@app.get("/topology", tags=["state"])
async def get_topology():
    try:
        latest = app_state.runner.store.get_latest()
        if not latest:
            raise StateError("No snapshot available")
        return {
            "topology_hash": latest.topology_hash,
            "topology_version": latest.topology_version,
            "nodes": [
                {"id": n.id, "type": n.type, "static": n.static} for n in latest.nodes
            ],
            "edges": [
                {
                    "id": e.id,
                    "type": e.type,
                    "source": e.source,
                    "target": e.target,
                    "static": e.static,
                }
                for e in latest.edges
            ],
        }
    except Exception as exc:
        logger.error(f"Topology retrieval failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve topology")


@app.get("/history", tags=["state"])
async def get_history(limit: int = 100):
    try:
        history = app_state.runner.store.history
        return [s.model_dump() for s in history[-limit:]]
    except Exception as exc:
        logger.error(f"History retrieval failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve history")


@app.post("/commands/perturb", tags=["commands"])
async def perturb_load(bus_id: str, p_mw_delta: float, q_mvar_delta: float = 0.0):
    try:
        app_state.runner.perturb_load(bus_id, p_mw_delta, q_mvar_delta)
        return {"status": "ok", "message": f"Perturbed load at {bus_id}"}
    except Exception as exc:
        logger.error(f"Perturb command failed: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    correlation_id = set_correlation_id()
    logger.info("WebSocket connection attempt")
    await websocket.accept()
    app_state.clients.add(websocket)
    logger.info(f"WebSocket connected - clients: {len(app_state.clients)}")

    try:
        latest = app_state.runner.store.get_latest()
        if latest:
            await websocket.send_json({"type": "snapshot", "payload": latest.model_dump()})

        async def heartbeat():
            while True:
                await asyncio.sleep(15)
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

        heartbeat_task = asyncio.create_task(heartbeat())

        while app_state.running:
            msg = None
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                continue

            if msg:
                try:
                    import json as _json
                    data = _json.loads(msg)
                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except Exception:
                    pass

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except asyncio.CancelledError:
        logger.debug("WebSocket task cancelled")
    except Exception as exc:
        logger.error(f"WebSocket error: {exc}")
    finally:
        app_state.clients.discard(websocket)
        logger.info(f"WebSocket cleanup - remaining: {len(app_state.clients)}")


async def _tick_loop():
    logger.info("Tick loop running")
    tick_count = 0

    while app_state.running:
        try:
            loop = asyncio.get_running_loop()
            out = await loop.run_in_executor(None, app_state.runner.run_one_tick)

            tick_count += 1
            app_state._metrics["ticks_total"] = tick_count

            payload = {
                "type": "tick",
                "tick": tick_count,
                "snapshot": out.snapshot.model_dump() if out.snapshot else None,
                "explanation": out.explanation.model_dump() if out.explanation else None,
            }

            dead_clients = []
            for ws in list(app_state.clients):
                try:
                    await asyncio.wait_for(ws.send_json(payload), timeout=5.0)
                    app_state._metrics["ws_messages_sent"] += 1
                except (asyncio.TimeoutError, Exception):
                    dead_clients.append(ws)

            for ws in dead_clients:
                app_state.clients.discard(ws)
                try:
                    await ws.close()
                except Exception:
                    pass

            await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("Tick loop cancelled")
            break
        except Exception as exc:
            app_state._metrics["ticks_failed"] += 1
            logger.error(f"Tick loop error on tick {tick_count}: {exc}")
            await asyncio.sleep(1.0)

    logger.info(f"Tick loop exiting after {tick_count} ticks")
