"""ROS-free conservative projection for collision-aware motion targets.

The default directional conventions preserve the existing live movement
validator. Retreats are configurable and must be calibrated for a robot's
sensor frame before physical use; this joint-space policy is not a geometric
collision detector.
"""

import math


DIRECTIONS = ("front", "left", "right")
SEVERITY_RANK = {"safe": 0, "warning": 1, "danger": 2, "contact": 2, "imminent": 2}
JOINT_ALIASES = {
    "base": ("base_to_L1", "base_link_to_link1"),
    "shoulder": ("L1_to_L2", "link1_to_link2"),
}
DEFAULT_RETREATS = {
    # ROS base frame is x-forward/y-left. Positive base yaw rotates the forward
    # gripper toward the robot's left, so side hazards require the opposite yaw.
    "front": {"axis": "shoulder", "sign": 1},
    "left": {"axis": "base", "sign": -1},
    "right": {"axis": "base", "sign": 1},
}


class ReactiveAvoidance:
    """Latch atomic sensor statuses and adapt only along configured retreats.

    A true warning replaces motion with a bounded retreat on its configured
    axis. Imminent/contact, conflicting left+right hazards, unknown coverage,
    or a retreat that cannot fit within joint limits requests a hold. A fresh
    measured clear must persist through the dwell and a new target must arrive
    after that clear edge before the previous course can resume.
    """

    def __init__(self, *, limits=None, retreats=None, escape_step=0.08,
                 stale_after=0.5, clear_dwell=0.25, required_directions=()):
        self.limits = dict(limits or {})
        self.retreats = self._validate_retreats(
            DEFAULT_RETREATS if retreats is None else retreats
        )
        self.escape_step = self._positive_finite(escape_step, "escape_step")
        self.stale_after = self._positive_finite(stale_after, "stale_after")
        self.clear_dwell = self._positive_finite(clear_dwell, "clear_dwell")
        if isinstance(required_directions, str):
            required_directions = [
                value.strip() for value in required_directions.split(",") if value.strip()
            ]
        self.required_directions = frozenset(required_directions)
        unknown = self.required_directions.difference(DIRECTIONS)
        if unknown:
            raise ValueError(f"unknown required sensor directions: {sorted(unknown)}")
        self._sensors = {
            direction: {
                "active": False,
                "severity": "safe",
                "valid": False,
                "last_update": None,
                "clear_since": None,
            }
            for direction in DIRECTIONS
        }
        self._replan_after = None

    @staticmethod
    def _positive_finite(value, name):
        result = float(value)
        if not math.isfinite(result) or result <= 0.0:
            raise ValueError(f"{name} must be finite and positive")
        return result

    @staticmethod
    def _validate_retreats(retreats):
        if not isinstance(retreats, dict):
            raise ValueError("retreats must be a direction mapping")
        result = {}
        for direction, spec in retreats.items():
            if direction not in DIRECTIONS or not isinstance(spec, dict):
                raise ValueError(f"invalid retreat direction: {direction!r}")
            axis, sign = spec.get("axis"), spec.get("sign")
            if axis not in {"base", "shoulder"} or sign not in (-1, 1):
                raise ValueError(f"invalid retreat vector for {direction}")
            if (direction == "front" and axis != "shoulder") or (
                direction in {"left", "right"} and axis != "base"
            ):
                raise ValueError(f"retreat axis does not match {direction} sensor")
            result[direction] = {"axis": axis, "sign": int(sign)}
        return result

    def update_sensor(self, direction, active, now, *, severity="warning", valid=True):
        """Record one atomic classifier output with monotonic receipt time.

        Invalid/timeout output is unknown coverage, never a real clear sample.
        """
        if direction not in self._sensors:
            raise ValueError(f"unknown hazard direction: {direction}")
        now = self._finite(now, "sensor timestamp")
        severity = str(severity).lower()
        if severity not in SEVERITY_RANK:
            raise ValueError(f"unknown severity: {severity}")
        sensor = self._sensors[direction]
        sensor["last_update"] = now
        sensor["valid"] = bool(valid)
        # Collision ROS publishes the useful 8–15 cm band as severity=warning
        # while its legacy hard collision Bool remains false. Preserve the
        # warning as a course-adjustment signal for both hardware and sim.
        hazard = bool(active) or SEVERITY_RANK[severity] > SEVERITY_RANK["safe"]
        if hazard:
            sensor["active"] = True
            if SEVERITY_RANK[severity] > SEVERITY_RANK[sensor["severity"]]:
                sensor["severity"] = severity
            sensor["clear_since"] = None
        elif sensor["active"] and sensor["clear_since"] is None and sensor["valid"]:
            sensor["clear_since"] = now
        elif not sensor["valid"]:
            # Preserve the active latch until a fresh explicit clear arrives.
            sensor["clear_since"] = None

    def snapshot(self, now):
        """Return latched, stale, and imminent directions."""
        now = self._finite(now, "snapshot timestamp")
        active, stale, imminent = set(), set(), set()
        for direction, sensor in self._sensors.items():
            if direction in self.required_directions and (
                not sensor["valid"] or sensor["last_update"] is None
                or now - sensor["last_update"] > self.stale_after
            ):
                stale.add(direction)
            if not sensor["active"]:
                continue
            if (not sensor["valid"] or sensor["last_update"] is None
                    or now - sensor["last_update"] > self.stale_after):
                stale.add(direction)
                continue
            clear_since = sensor["clear_since"]
            if clear_since is not None:
                if now - clear_since >= self.clear_dwell:
                    sensor["active"] = False
                    sensor["severity"] = "safe"
                    sensor["clear_since"] = None
                    self._replan_after = max(
                        self._replan_after or float("-inf"),
                        clear_since + self.clear_dwell,
                    )
                    continue
            active.add(direction)
            if SEVERITY_RANK[sensor["severity"]] >= SEVERITY_RANK["danger"]:
                imminent.add(direction)
        return active, stale, imminent

    def adjust_target(self, current, requested, joint_names, *, now,
                      target_received_at=None):
        """Project one requested target and return target/mode/hazard metadata."""
        now = self._finite(now, "decision timestamp")
        if len(current) != len(requested) or len(current) != len(joint_names):
            raise ValueError("joint names and position arrays must have equal lengths")
        if len(set(joint_names)) != len(joint_names):
            raise ValueError("joint names must be unique")
        current = self._clamp(
            [self._finite(v, "current position") for v in current], joint_names
        )
        requested = self._clamp(
            [self._finite(v, "requested position") for v in requested], joint_names
        )
        hazards, stale, imminent = self.snapshot(now)
        if stale:
            return self._decision(current, "hold_stale", hazards, stale)
        if imminent:
            return self._decision(current, "hold_imminent", hazards, stale)
        if {"left", "right"}.issubset(hazards):
            return self._decision(current, "hold_blocked", hazards, stale)

        if not hazards:
            if self._replan_after is not None:
                received = target_received_at
                if (received is None or not math.isfinite(float(received))
                        or float(received) <= self._replan_after):
                    return self._decision(current, "hold_replan", hazards, stale)
                self._replan_after = None
            return self._decision(requested, "clear", hazards, stale)

        indices = {axis: self._find_index(joint_names, axis) for axis in ("base", "shoulder")}
        # A warning is a constrained escape maneuver, not permission to keep
        # executing the rest of an unverified animation keyframe. Start from
        # measured pose and change only the explicitly configured retreat axes.
        projected = list(current)
        adjusted = True
        retreat_attempts = []
        for direction in hazards:
            spec = self.retreats.get(direction)
            if spec is None:
                return self._decision(current, "hold_unconfigured", hazards, stale)
            index = indices[spec["axis"]]
            if index is None:
                return self._decision(current, "hold_unconfigured", hazards, stale)
            sign = spec["sign"]
            # Advance by one bounded step per controller tick. This deliberately
            # suppresses simultaneous wrist/elbow/roll requests until the
            # sensor reports a fresh clear and the caller replans.
            projected[index] = current[index] + sign * self.escape_step
            retreat_attempts.append((index, sign))

        projected = self._clamp(projected, joint_names)
        if any((projected[index] - current[index]) * sign < self.escape_step - 1e-9
               for index, sign in retreat_attempts):
            return self._decision(current, "hold_no_safe_projection", hazards, stale)
        for direction in hazards:
            spec = self.retreats[direction]
            index = indices[spec["axis"]]
            if (projected[index] - current[index]) * spec["sign"] < -1e-9:
                return self._decision(current, "hold_no_safe_projection", hazards, stale)
        return self._decision(projected, "adjust" if adjusted else "continue_safe", hazards, stale)

    @staticmethod
    def _finite(value, name):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"{name} must be finite")
        return result

    @staticmethod
    def _find_index(names, semantic):
        for alias in JOINT_ALIASES[semantic]:
            if alias in names:
                return names.index(alias)
        return None

    def _clamp(self, positions, names):
        result = list(positions)
        for index, name in enumerate(names):
            bounds = self.limits.get(name)
            if bounds is not None:
                lower, upper = map(float, bounds)
                if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
                    raise ValueError(f"invalid joint limits for {name}")
                result[index] = min(upper, max(lower, result[index]))
        return result

    @staticmethod
    def _decision(target, mode, hazards, stale):
        return {
            "target": list(target),
            "mode": mode,
            "hazards": sorted(hazards),
            "stale": sorted(stale),
        }
