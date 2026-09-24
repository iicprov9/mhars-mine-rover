"""Mine simulator — demo UI without hardware."""

from __future__ import annotations

import math
import random
import time
from typing import Optional

from protocol import (
    AcousticReading,
    EnvironmentReading,
    GasReading,
    PositionReading,
    ProximityReading,
    RoverStatus,
    TelemetryPacket,
    ThermalReading,
)


class MineSimulator:
    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0
        self.scenario = "patrol"
        self._scenario_until = 0.0
        self.battery = 92.0

    def set_scenario(self, name: str, duration_sec: float = 25.0) -> None:
        self.scenario = name
        self._scenario_until = time.time() + duration_sec

    def tick(self, nav_action: Optional[str] = "forward") -> TelemetryPacket:
        now = time.time()
        if now > self._scenario_until and self.scenario != "patrol":
            self.scenario = "patrol"

        speed = 0.35
        if nav_action == "stop":
            speed = 0.0
        elif nav_action == "backward":
            speed = -0.2
        elif nav_action == "left":
            self.heading = (self.heading - 8) % 360
            speed = 0.15
        elif nav_action == "right":
            self.heading = (self.heading + 8) % 360
            speed = 0.15

        rad = math.radians(self.heading)
        self.x += math.cos(rad) * speed * 0.5
        self.y += math.sin(rad) * speed * 0.5
        self.battery = max(5.0, self.battery - 0.002)

        temp = 28.0 + 2.0 * math.sin(now / 20)
        humidity = 62.0 + 5.0 * math.sin(now / 30)
        co, ch4, co2, h2s = 8.0, 120.0, 650.0, 0.5
        thermal_max, thermal_avg, anomaly = temp + 3, temp + 1, False
        acoustic_db, acoustic_event, conf = 42.0 + random.uniform(-2, 2), None, 0.0
        front = 120 + 40 * math.sin(now / 4)
        left = 90 + 20 * math.sin(now / 5)
        right = 95 + 25 * math.cos(now / 6)

        if self.scenario == "gas_leak":
            co, ch4, co2, humidity = 110 + 20 * math.sin(now), 600 + 100 * random.random(), 5200, 78
        elif self.scenario == "fire":
            temp, thermal_max, thermal_avg, anomaly, co, humidity = 58 + random.uniform(-2, 4), 95, 70, True, 45, 35
        elif self.scenario == "rescue":
            acoustic_db, acoustic_event, conf, front = 78, "distress", 0.85, 60
        elif self.scenario == "blocked":
            front, left, right = 18 + random.uniform(0, 4), 40, 110

        return TelemetryPacket(
            ts=now,
            position=PositionReading(x=round(self.x, 2), y=round(self.y, 2), heading_deg=round(self.heading, 1), relative_label=f"Gallery-{int(abs(self.x) // 10) + 1}"),
            gas=GasReading(co_ppm=round(co, 1), ch4_ppm=round(ch4, 1), co2_ppm=round(co2, 1), h2s_ppm=round(h2s, 2), raw_mq2=co * 8, raw_mq7=co * 10, raw_mq135=co2 / 5),
            environment=EnvironmentReading(temperature_c=round(temp, 1), humidity_pct=round(humidity, 1)),
            proximity=ProximityReading(front_cm=round(max(5, front), 1), left_cm=round(max(5, left), 1), right_cm=round(max(5, right), 1)),
            acoustic=AcousticReading(level_db=round(acoustic_db, 1), event=acoustic_event, confidence=conf),  # type: ignore[arg-type]
            thermal=ThermalReading(max_c=round(thermal_max, 1), avg_c=round(thermal_avg, 1), min_c=round(temp - 2, 1), anomaly=anomaly),
            visual_available=True,
            status=RoverStatus(battery_pct=round(self.battery, 1), mode="auto", speed_mps=round(abs(speed), 2), connected=True),
        )
