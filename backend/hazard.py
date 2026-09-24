"""Multimodal hazard assessment (Form-2 units 130 / 140 / 150)."""

from __future__ import annotations

import time
import uuid

from protocol import HazardEvent, HazardSeverity, TelemetryPacket

THRESHOLDS = {
    "co_ppm_warn": 35.0,
    "co_ppm_crit": 100.0,
    "ch4_ppm_warn": 500.0,
    "ch4_ppm_crit": 5000.0,
    "co2_ppm_warn": 5000.0,
    "h2s_ppm_warn": 10.0,
    "h2s_ppm_crit": 50.0,
    "temp_warn_c": 40.0,
    "temp_crit_c": 55.0,
    "acoustic_distress_db": 70.0,
    "thermal_anomaly_delta": 15.0,
}


def assess(packet: TelemetryPacket) -> list[HazardEvent]:
    events: list[HazardEvent] = []
    gas, env, thermal, acoustic = packet.gas, packet.environment, packet.thermal, packet.acoustic

    if gas.co_ppm >= THRESHOLDS["co_ppm_crit"]:
        mods = ["gas"]
        if env.temperature_c >= THRESHOLDS["temp_warn_c"] or thermal.anomaly:
            mods.append("thermal" if thermal.anomaly else "environment")
        events.append(_ev("carbon_monoxide", HazardSeverity.CRITICAL, f"Critical CO {gas.co_ppm:.0f} ppm", mods, packet))
    elif gas.co_ppm >= THRESHOLDS["co_ppm_warn"]:
        mods = ["gas"] + (["environment"] if env.humidity_pct > 70 else [])
        events.append(_ev("carbon_monoxide", HazardSeverity.HIGH, f"Elevated CO {gas.co_ppm:.0f} ppm", mods, packet))

    if gas.ch4_ppm >= THRESHOLDS["ch4_ppm_crit"]:
        events.append(_ev("methane", HazardSeverity.CRITICAL, f"Critical CH₄ {gas.ch4_ppm:.0f} ppm — explosion risk", ["gas"], packet))
    elif gas.ch4_ppm >= THRESHOLDS["ch4_ppm_warn"]:
        mods = ["gas"] + (["thermal"] if thermal.anomaly or env.temperature_c >= THRESHOLDS["temp_warn_c"] else [])
        events.append(_ev("methane", HazardSeverity.HIGH, f"Elevated CH₄ {gas.ch4_ppm:.0f} ppm", mods, packet))

    if gas.h2s_ppm >= THRESHOLDS["h2s_ppm_crit"]:
        events.append(_ev("hydrogen_sulfide", HazardSeverity.CRITICAL, f"Critical H₂S {gas.h2s_ppm:.1f} ppm", ["gas"], packet))
    elif gas.h2s_ppm >= THRESHOLDS["h2s_ppm_warn"]:
        events.append(_ev("hydrogen_sulfide", HazardSeverity.MEDIUM, f"Elevated H₂S {gas.h2s_ppm:.1f} ppm", ["gas"], packet))

    if gas.co2_ppm >= THRESHOLDS["co2_ppm_warn"]:
        events.append(_ev("carbon_dioxide", HazardSeverity.MEDIUM, f"High CO₂ {gas.co2_ppm:.0f} ppm with humidity {env.humidity_pct:.0f}%", ["gas", "environment"], packet))

    if thermal.anomaly and env.temperature_c >= THRESHOLDS["temp_warn_c"]:
        sev = HazardSeverity.CRITICAL if env.temperature_c >= THRESHOLDS["temp_crit_c"] else HazardSeverity.HIGH
        events.append(_ev("thermal_anomaly", sev, f"Thermal anomaly — max {thermal.max_c:.0f}°C, ambient {env.temperature_c:.0f}°C", ["thermal", "environment"], packet))
    elif env.temperature_c >= THRESHOLDS["temp_crit_c"]:
        events.append(_ev("overheat", HazardSeverity.HIGH, f"Ambient temperature {env.temperature_c:.0f}°C", ["environment"], packet))

    if acoustic.event in ("distress", "voice") or (acoustic.level_db >= THRESHOLDS["acoustic_distress_db"] and acoustic.confidence >= 0.6):
        mods = ["acoustic"]
        if packet.visual_available:
            mods.append("visual")
        if thermal.anomaly:
            mods.append("thermal")
        events.append(_ev("acoustic_rescue", HazardSeverity.HIGH, f"Possible person / distress ({acoustic.event or 'loud event'}) @ {acoustic.level_db:.0f} dB", mods, packet))

    if not events and gas.co_ppm > 20 and thermal.max_c - thermal.avg_c >= THRESHOLDS["thermal_anomaly_delta"]:
        events.append(_ev("composite_fire_risk", HazardSeverity.MEDIUM, "CO rise correlated with thermal hotspot", ["gas", "thermal"], packet))

    return events


def merge_active(previous: list[HazardEvent], new_events: list[HazardEvent], ttl_sec: float = 30.0) -> list[HazardEvent]:
    now = time.time()
    by_type = {h.hazard_type: h for h in previous if now - h.ts < ttl_sec}
    for e in new_events:
        by_type[e.hazard_type] = e
    return list(by_type.values())


def _ev(hazard_type: str, severity: HazardSeverity, message: str, modalities: list[str], packet: TelemetryPacket) -> HazardEvent:
    return HazardEvent(
        id=str(uuid.uuid4())[:8],
        ts=packet.ts or time.time(),
        hazard_type=hazard_type,
        severity=severity,
        message=message,
        modalities=modalities,
        position=packet.position,
        snapshot={
            "gas": packet.gas.model_dump(),
            "environment": packet.environment.model_dump(),
            "thermal": packet.thermal.model_dump(),
            "acoustic": packet.acoustic.model_dump(),
        },
    )
