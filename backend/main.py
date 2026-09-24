"""
MHARS server — run from this folder:

  .venv\\Scripts\\activate
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import hazard as hazard_engine
import navigation as nav_engine
from bridge import SerialBridge, list_serial_ports
from protocol import ControlCommand, HazardEvent, MovementCommand, SystemState, TelemetryPacket
from simulator import MineSimulator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mhars")

DASHBOARD_DIST = Path(__file__).resolve().parent.parent / "dashboard" / "dist"


class Hub:
    def __init__(self) -> None:
        self.state = SystemState(source="idle")
        self.sim = MineSimulator()
        self.mode = os.getenv("MHARS_MODE", "simulation")
        self.serial_port = os.getenv("MHARS_SERIAL", "")
        self.serial: Optional[SerialBridge] = None
        self.clients: set[WebSocket] = set()
        self.rover_sockets: set[WebSocket] = set()
        self.pending_manual: Optional[MovementCommand] = None
        self.last_nav_action = "forward"
        self.hazard_log: list[HazardEvent] = []
        self._lock = asyncio.Lock()

    async def broadcast(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, default=str)
        dead = []
        for ws in self.clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def send_to_rover(self, cmd: ControlCommand) -> None:
        data = cmd.model_dump_json()
        dead = []
        for ws in self.rover_sockets:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.rover_sockets.discard(ws)

    async def ingest(self, packet: TelemetryPacket, source: str) -> None:
        async with self._lock:
            new_hazards = hazard_engine.assess(packet)
            active = hazard_engine.merge_active(self.state.active_hazards, new_hazards)
            for h in new_hazards:
                self.hazard_log.insert(0, h)
            self.hazard_log = self.hazard_log[:200]
            nav = nav_engine.decide(packet, self.pending_manual)
            self.last_nav_action = nav.action.value
            path = (self.state.path + [packet.position])[-300:]
            self.state = SystemState(
                telemetry=packet,
                hazards=self.hazard_log[:50],
                active_hazards=active,
                navigation=nav,
                path=path,
                source=source,  # type: ignore[arg-type]
                last_update_ts=time.time(),
            )
        await self.broadcast({"type": "state", "data": self.state.model_dump()})
        await self.send_to_rover(ControlCommand(command=nav.action, speed=0.0 if nav.action == MovementCommand.STOP else 0.5))


hub = Hub()


async def simulation_loop() -> None:
    while True:
        if hub.mode == "simulation":
            await hub.ingest(hub.sim.tick(hub.last_nav_action), "simulation")
        await asyncio.sleep(0.4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(simulation_loop())
    if hub.mode == "hardware" and hub.serial_port:
        hub.serial = SerialBridge(hub.serial_port)
        await hub.serial.start(lambda p: hub.ingest(p, "serial"))
    logger.info("MHARS up — mode=%s", hub.mode)
    yield
    task.cancel()
    if hub.serial:
        await hub.serial.stop()


app = FastAPI(title="MHARS", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class ModeBody(BaseModel):
    mode: str
    serial_port: Optional[str] = None


class ScenarioBody(BaseModel):
    scenario: str
    duration_sec: float = 25.0


class ControlBody(BaseModel):
    command: MovementCommand
    speed: float = 0.5


@app.get("/api/health")
async def health():
    return {"ok": True, "system": "MHARS", "mode": hub.mode, "source": hub.state.source}


@app.get("/api/state")
async def get_state():
    return hub.state.model_dump()


@app.post("/api/telemetry")
async def post_telemetry(packet: TelemetryPacket):
    hub.mode = "hardware"
    await hub.ingest(packet, "wifi")
    return {"ok": True, "navigation": hub.state.navigation.model_dump() if hub.state.navigation else None}


@app.post("/api/control")
async def post_control(body: ControlBody):
    hub.pending_manual = body.command
    if hub.state.telemetry:
        hub.state.telemetry.status.mode = "manual" if body.command != MovementCommand.AUTO else "auto"
    await hub.send_to_rover(ControlCommand(command=body.command, speed=body.speed))
    return {"ok": True}


@app.post("/api/mode")
async def set_mode(body: ModeBody):
    hub.mode = body.mode
    if body.serial_port:
        hub.serial_port = body.serial_port
        if hub.serial:
            await hub.serial.stop()
        hub.serial = SerialBridge(body.serial_port)
        await hub.serial.start(lambda p: hub.ingest(p, "serial"))
    return {"ok": True, "mode": hub.mode}


@app.post("/api/scenario")
async def set_scenario(body: ScenarioBody):
    hub.sim.set_scenario(body.scenario, body.duration_sec)
    return {"ok": True}


@app.get("/api/serial/ports")
async def serial_ports():
    return {"ports": list_serial_ports()}


@app.get("/api/hazards")
async def hazards():
    return {"active": [h.model_dump() for h in hub.state.active_hazards], "log": [h.model_dump() for h in hub.hazard_log[:100]]}


@app.websocket("/ws/ui")
async def ws_ui(ws: WebSocket):
    await ws.accept()
    hub.clients.add(ws)
    await ws.send_text(json.dumps({"type": "state", "data": hub.state.model_dump()}, default=str))
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "control":
                cmd = MovementCommand(msg.get("command", "stop"))
                hub.pending_manual = cmd
                if hub.state.telemetry:
                    hub.state.telemetry.status.mode = "manual" if cmd != MovementCommand.AUTO else "auto"
                await hub.send_to_rover(ControlCommand(command=cmd))
            elif msg.get("type") == "scenario":
                hub.sim.set_scenario(msg.get("scenario", "patrol"), float(msg.get("duration_sec", 25)))
            elif msg.get("type") == "mode":
                hub.mode = msg.get("mode", "simulation")
    except WebSocketDisconnect:
        hub.clients.discard(ws)


@app.websocket("/ws/rover")
async def ws_rover(ws: WebSocket):
    await ws.accept()
    hub.rover_sockets.add(ws)
    hub.mode = "hardware"
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
                if data.get("type", "telemetry") == "telemetry":
                    await hub.ingest(TelemetryPacket.model_validate(data), "wifi")
            except Exception:
                pass
    except WebSocketDisconnect:
        hub.rover_sockets.discard(ws)


if DASHBOARD_DIST.exists():
    app.mount("/assets", StaticFiles(directory=DASHBOARD_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        file_path = DASHBOARD_DIST / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DASHBOARD_DIST / "index.html")
