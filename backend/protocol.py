"""JSON protocol — rover ↔ PC (matches Form-2 modules 121–126)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class HazardSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MovementCommand(str, Enum):
    FORWARD = "forward"
    BACKWARD = "backward"
    LEFT = "left"
    RIGHT = "right"
    STOP = "stop"
    AUTO = "auto"


class GasReading(BaseModel):
    co_ppm: float = 0.0
    ch4_ppm: float = 0.0
    co2_ppm: float = 400.0
    h2s_ppm: float = 0.0
    raw_mq2: Optional[float] = None
    raw_mq7: Optional[float] = None
    raw_mq135: Optional[float] = None


class EnvironmentReading(BaseModel):
    temperature_c: float = 25.0
    humidity_pct: float = 50.0


class ProximityReading(BaseModel):
    front_cm: float = 200.0
    left_cm: float = 200.0
    right_cm: float = 200.0
    rear_cm: Optional[float] = None


class AcousticReading(BaseModel):
    level_db: float = 40.0
    event: Optional[Literal["distress", "voice", "impact", "none"]] = None
    confidence: float = 0.0


class ThermalReading(BaseModel):
    max_c: float = 30.0
    avg_c: float = 28.0
    min_c: float = 26.0
    anomaly: bool = False


class PositionReading(BaseModel):
    x: float = 0.0
    y: float = 0.0
    heading_deg: float = 0.0
    relative_label: Optional[str] = None


class RoverStatus(BaseModel):
    battery_pct: float = 100.0
    mode: Literal["auto", "manual", "estop"] = "auto"
    speed_mps: float = 0.0
    connected: bool = True


class TelemetryPacket(BaseModel):
    type: Literal["telemetry"] = "telemetry"
    ts: float
    position: PositionReading = Field(default_factory=PositionReading)
    gas: GasReading = Field(default_factory=GasReading)
    environment: EnvironmentReading = Field(default_factory=EnvironmentReading)
    proximity: ProximityReading = Field(default_factory=ProximityReading)
    acoustic: AcousticReading = Field(default_factory=AcousticReading)
    thermal: ThermalReading = Field(default_factory=ThermalReading)
    visual_available: bool = False
    frame_jpeg_b64: Optional[str] = None
    status: RoverStatus = Field(default_factory=RoverStatus)
    extras: dict[str, Any] = Field(default_factory=dict)


class HazardEvent(BaseModel):
    id: str
    ts: float
    hazard_type: str
    severity: HazardSeverity
    message: str
    modalities: list[str]
    position: PositionReading
    snapshot: dict[str, Any] = Field(default_factory=dict)


class NavigationDecision(BaseModel):
    action: MovementCommand
    reason: str
    obstacle_cm: float
    auto: bool = True


class ControlCommand(BaseModel):
    type: Literal["control"] = "control"
    command: MovementCommand
    speed: float = 0.5


class SystemState(BaseModel):
    telemetry: Optional[TelemetryPacket] = None
    hazards: list[HazardEvent] = Field(default_factory=list)
    active_hazards: list[HazardEvent] = Field(default_factory=list)
    navigation: Optional[NavigationDecision] = None
    path: list[PositionReading] = Field(default_factory=list)
    source: Literal["simulation", "serial", "wifi", "idle"] = "idle"
    last_update_ts: float = 0.0
