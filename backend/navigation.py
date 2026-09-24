"""Navigation & response — obstacle-based movement (Form-2 unit 160)."""

from __future__ import annotations

from protocol import MovementCommand, NavigationDecision, TelemetryPacket

STOP_CM = 25.0
SLOW_CM = 50.0
CLEAR_CM = 80.0


def decide(packet: TelemetryPacket, manual: MovementCommand | None = None) -> NavigationDecision:
    front = packet.proximity.front_cm
    left = packet.proximity.left_cm
    right = packet.proximity.right_cm

    if packet.status.mode == "estop":
        return NavigationDecision(action=MovementCommand.STOP, reason="Emergency stop engaged", obstacle_cm=front, auto=False)

    if packet.status.mode == "manual" and manual is not None:
        if front < STOP_CM and manual == MovementCommand.FORWARD:
            return NavigationDecision(action=MovementCommand.STOP, reason=f"Obstacle {front:.0f} cm ahead — forward blocked", obstacle_cm=front, auto=False)
        return NavigationDecision(action=manual, reason="Manual operator command", obstacle_cm=front, auto=False)

    if front < STOP_CM:
        if left > right and left > CLEAR_CM:
            return NavigationDecision(action=MovementCommand.LEFT, reason=f"Obstacle {front:.0f} cm — turn left", obstacle_cm=front)
        if right >= left and right > CLEAR_CM:
            return NavigationDecision(action=MovementCommand.RIGHT, reason=f"Obstacle {front:.0f} cm — turn right", obstacle_cm=front)
        return NavigationDecision(action=MovementCommand.STOP, reason=f"Path blocked ({front:.0f} cm) — stop", obstacle_cm=front)

    if front < SLOW_CM:
        prefer = MovementCommand.LEFT if left > right else MovementCommand.RIGHT
        side = left if prefer == MovementCommand.LEFT else right
        if side > CLEAR_CM:
            return NavigationDecision(action=prefer, reason=f"Narrow path {front:.0f} cm — nudge {prefer.value}", obstacle_cm=front)

    return NavigationDecision(action=MovementCommand.FORWARD, reason="Path clear", obstacle_cm=front)
