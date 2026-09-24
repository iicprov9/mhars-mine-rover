"""USB serial bridge — newline JSON @ 115200 from MCU."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

from protocol import TelemetryPacket

logger = logging.getLogger("mhars.serial")
OnPacket = Callable[[TelemetryPacket], Awaitable[None]]


class SerialBridge:
    def __init__(self, port: str, baud: int = 115200) -> None:
        self.port = port
        self.baud = baud
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    async def start(self, on_packet: OnPacket) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run(on_packet))

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await asyncio.wait([self._task], timeout=2)

    async def _run(self, on_packet: OnPacket) -> None:
        try:
            import serial
        except ImportError:
            logger.error("pyserial missing")
            return

        while not self._stop.is_set():
            try:
                ser = serial.Serial(self.port, self.baud, timeout=0.2)
                logger.info("Serial open %s", self.port)
            except Exception as exc:
                logger.warning("Serial failed: %s", exc)
                await asyncio.sleep(3)
                continue

            buf = ""
            try:
                while not self._stop.is_set():
                    chunk = await asyncio.to_thread(ser.read, 256)
                    if chunk:
                        buf += chunk.decode("utf-8", errors="ignore")
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                if data.get("type", "telemetry") == "telemetry":
                                    await on_packet(TelemetryPacket.model_validate(data))
                            except Exception:
                                pass
                    else:
                        await asyncio.sleep(0.02)
            finally:
                ser.close()
            await asyncio.sleep(1)


def list_serial_ports() -> list[dict]:
    try:
        import serial.tools.list_ports

        return [{"device": p.device, "description": p.description} for p in serial.tools.list_ports.comports()]
    except Exception:
        return []
