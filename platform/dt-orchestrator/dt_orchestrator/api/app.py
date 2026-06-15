"""
FastAPI application for the Grid Digital Twin Orchestrator.

Provides REST endpoints and WebSocket streaming for grid state and anomalies.
Uses proper async patterns, dependency injection, and structured logging.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

# Setup logging first
import sys
import logging
sys.path.insert(0, str(__file__).rsplit("/", 3)[0])  # Add platform to path

from dt_contracts.logging_config import setup_logging, get_logger, set_correlation_id
from dt_contracts.exceptions import GridDigitalTwinError, StateError, PublishError, error_to_dict

setup_logging()
logger = get_logger(__name__)

# Import after logging setup
from ..bootstrap import bootstrap_local_paths
from ..pipelines.realtime_tick import RealtimeTickRunner

bootstrap_local_paths()


class AppState:
    """Application state container for dependency injection."""

    def __init__(self):
        self.runner: RealtimeTickRunner = RealtimeTickRunner()
        self.clients: Set[WebSocket] = set()
        self.tick_task: asyncio.Task = None
        self.running = False

    async def cleanup(self):
        """Clean up resources on shutdown."""
        self.running = False
        if self.tick_task:
            self.tick_task.cancel()
            try:
                await self.tick_task
            except asyncio.CancelledError:
                pass

        # Close all WebSocket connections
        for ws in list(self.clients):
            try:
                await ws.close()
            except Exception:
                pass
        self.clients.clear()
        logger.info("Application cleanup complete")


# Application state
app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Manage application lifecycle - startup and shutdown."""
    logger.info("Starting Grid Digital Twin Orchestrator")
    app_state.running = True
    app_state.tick_task = asyncio.create_task(_tick_loop())
    logger.info("Tick loop started")

    yield

    logger.info("Shutting down Grid Digital Twin Orchestrator")
    await app_state.cleanup()


app = FastAPI(
    title="Autonomous Explainable Grid Digital Twin Orchestrator",
    description="Research-grade power grid simulation and anomaly detection",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["health"])
async def health():
    """Health check endpoint."""
    try:
        latest = app_state.runner.store.get_latest()
        return {
            "status": "healthy",
            "running": app_state.running,
            "tick_task_alive": app_state.tick_task and not app_state.tick_task.done(),
            "last_tick": latest.tick_count if latest else None,
            "connected_clients": len(app_state.clients),
        }
    except Exception as exc:
        logger.error(f"Health check failed: {exc}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/snapshot", tags=["state"])
async def get_snapshot():
    """Get the latest grid snapshot."""
    try:
        latest = app_state.runner.store.get_latest()
        if not latest:
            raise StateError("No snapshot available yet - simulation not started")
        return latest.model_dump()
    except Exception as exc:
        logger.error(f"Snapshot retrieval failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve snapshot")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming grid state and anomalies."""
    correlation_id = set_correlation_id()
    logger.info("WebSocket connection attempt")

    await websocket.accept()
    app_state.clients.add(websocket)
    logger.info(f"WebSocket connected - clients: {len(app_state.clients)}")

    try:
        # Send current state immediately
        latest = app_state.runner.store.get_latest()
        if latest:
            await websocket.send_json({"type": "snapshot", "payload": latest.model_dump()})
            logger.debug("Initial snapshot sent")

        # Keep connection alive
        while app_state.running:
            await asyncio.sleep(30)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except asyncio.CancelledError:
        logger.debug("WebSocket task cancelled")
    except Exception as exc:
        logger.error(f"WebSocket error: {exc}")
        try:
            await websocket.send_json({"type": "error", "message": "Connection error"})
        except Exception:
            pass
    finally:
        app_state.clients.discard(websocket)
        logger.info(f"WebSocket cleanup - remaining: {len(app_state.clients)}")


async def _tick_loop():
    """Main tick loop: run simulation and broadcast updates."""
    logger.info("Tick loop running")
    tick_count = 0

    while app_state.running:
        try:
            # Run tick in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            out = await loop.run_in_executor(None, app_state.runner.run_one_tick)

            tick_count += 1
            payload = {
                "type": "tick",
                "tick": tick_count,
                "snapshot": out.snapshot.model_dump(),
                "explanation": out.explanation.model_dump() if out.explanation else None,
            }

            # Send to all connected clients
            dead_clients = []
            for ws in list(app_state.clients):
                try:
                    await asyncio.wait_for(ws.send_json(payload), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("WebSocket send timeout")
                    dead_clients.append(ws)
                except Exception as exc:
                    logger.warning(f"Failed to send to client: {exc}")
                    dead_clients.append(ws)

            # Clean up dead connections
            for ws in dead_clients:
                app_state.clients.discard(ws)
                try:
                    await ws.close()
                except Exception:
                    pass

            if dead_clients:
                logger.info(f"Removed {len(dead_clients)} dead connections")

            await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("Tick loop cancelled")
            break
        except Exception as exc:
            logger.error(f"Tick loop error on tick {tick_count}: {exc}")
            await asyncio.sleep(1.0)

    logger.info(f"Tick loop exiting after {tick_count} ticks")

