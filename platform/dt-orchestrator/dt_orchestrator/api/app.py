from __future__ import annotations

import asyncio
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from ..bootstrap import bootstrap_local_paths

bootstrap_local_paths()

from ..pipelines.realtime_tick import RealtimeTickRunner  # noqa: E402


app = FastAPI(title="Grid Digital Twin Orchestrator (PoC)")
runner = RealtimeTickRunner()
clients: Set[WebSocket] = set()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/snapshot")
def snapshot():
    snap = runner.store.get_latest()
    return snap.model_dump()


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        # send current state immediately
        await websocket.send_json({"type": "snapshot", "payload": runner.store.get_latest().model_dump()})
        while True:
            # keep alive; actual pushes happen from background task
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        clients.discard(websocket)


async def _tick_loop():
    while True:
        out = runner.run_one_tick()
        payload = {"type": "tick", "snapshot": out.snapshot.model_dump(), "explanation": out.explanation.model_dump() if out.explanation else None}
        dead = []
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            clients.discard(ws)
        await asyncio.sleep(1.0)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_tick_loop())

