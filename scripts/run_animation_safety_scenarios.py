#!/usr/bin/env python3
"""Native checks for clean animation termination on invalid/stale safety data.

Run exclusively in the isolated simulator ROS domain. The runner starts real
PlayAnimation goals, drives only simulator sensor-input topics, and records
the received action/state/motion evidence. It does not play audio or access
hardware.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import time
from pathlib import Path


def main():
    if os.environ.get("ROS_DOMAIN_ID") != "73" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise SystemExit("Animation safety scenarios require domain 73, localhost-only")

    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from luxo_interfaces.action import PlayAnimation
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Float32, Int16, String, UInt8

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--animation", default="dance")
    parser.add_argument("--speed", type=float, default=2.0)
    args = parser.parse_args()
    if not math.isfinite(args.speed) or not 0.1 <= args.speed <= 2.0:
        raise SystemExit("--speed must be finite and between 0.1 and 2.0")

    rclpy.init()
    node = Node("animation_safety_scenarios")
    data = {
        "state": None,
        "motion": {},
        "sensors": {},
        "joints": None,
        "feedback": None,
        "feedback_changes": [],
        "hold_events": [],
        "adjust_started": None,
    }
    evidence = {
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "runtime_commit": os.environ.get("LUXOPI_RUNTIME_COMMIT", "unknown"),
        "runtime_source_sha256": os.environ.get("LUXOPI_RUNTIME_SOURCE_SHA256", "unknown"),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": [],
        "passed": False,
    }

    node.create_subscription(
        String, "/luxo/current_state", lambda msg: data.update(state=msg.data), 20
    )

    def receive_motion(msg):
        payload = json.loads(msg.data)
        previous_mode = data["motion"].get("avoidance_mode")
        if payload.get("avoidance_mode") == "adjust" and previous_mode != "adjust":
            data["adjust_started"] = time.monotonic()
        if payload.get("avoidance_mode", "").startswith("hold_"):
            data["hold_events"].append({"mode": payload["avoidance_mode"], "at": time.monotonic()})
        data["motion"] = payload

    def receive_sensor(msg):
        payload = json.loads(msg.data)
        data["sensors"][payload.get("direction")] = {**payload, "received_at": time.monotonic()}

    node.create_subscription(String, "/sim/motion_status", receive_motion, 50)
    node.create_subscription(String, "/collision/sensor_status", receive_sensor, 50)
    node.create_subscription(JointState, "/joint_states", lambda msg: data.update(joints=msg), 20)

    left = node.create_publisher(Float32, "/i2c/vl53_left/distance", 10)
    right = node.create_publisher(Float32, "/i2c/vl53_right/distance", 10)
    front = node.create_publisher(Int16, "/i2c/apds9960/proximity", 10)
    touches = {
        name: node.create_publisher(UInt8, f"/touch_sensors/head_{name}", 10)
        for name in ("top", "left", "right", "bottom")
    }
    actions = ActionClient(node, PlayAnimation, "play_animation")
    raw = {
        "enabled": True,
        "range_enabled": {"left": True, "right": True},
        "range_cm": {"left": 100.0, "right": 100.0},
        "hazard_side": "left",
        "last_sent": 0.0,
    }
    active_goal = {"handle": None, "result": None}

    def publish_raw():
        now = time.monotonic()
        if raw["range_enabled"]["left"]:
            left.publish(Float32(data=raw["range_cm"]["left"]))
        if raw["range_enabled"]["right"]:
            right.publish(Float32(data=raw["range_cm"]["right"]))
        front.publish(Int16(data=0))
        for publisher in touches.values():
            publisher.publish(UInt8(data=0))
        raw["last_sent"] = now

    def spin(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if raw["enabled"] and time.monotonic() - raw["last_sent"] >= 0.06:
                publish_raw()
            rclpy.spin_once(node, timeout_sec=0.01)

    def wait(predicate, timeout=10.0, description="condition"):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"timed out waiting for {description}; state={data['state']!r}; "
                    f"motion={data['motion']!r}; sensors={data['sensors']!r}"
                )
            spin(0.01)

    def record(name, **details):
        evidence["cases"].append({"name": name, "passed": True, **details})

    def start_goal():
        data["feedback"] = None
        goal = PlayAnimation.Goal()
        goal.animation_name = args.animation
        goal.speed_multiplier = args.speed
        goal.allow_interruption = True
        goal.use_hardware_feedback = False
        sent = actions.send_goal_async(goal, feedback_callback=receive_feedback)
        wait(sent.done, description="action acceptance")
        handle = sent.result()
        assert handle.accepted, "animation goal rejected"
        result = handle.get_result_async()
        active_goal.update(handle=handle, result=result)
        return handle, result

    def receive_feedback(message):
        feedback = message.feedback
        previous = data["feedback"]
        if previous is None or feedback.current_keyframe != previous["keyframe"]:
            data["feedback_changes"].append({
                "keyframe": feedback.current_keyframe,
                "total": feedback.total_keyframes,
                "at": time.monotonic(),
            })
        data["feedback"] = {
            "keyframe": feedback.current_keyframe,
            "total": feedback.total_keyframes,
            "at": time.monotonic(),
        }

    def wait_for_stale_mode(after_count, timeout=5.0):
        wait(lambda: data["motion"].get("avoidance_mode") == "hold_stale",
             timeout=timeout, description="atomic stale/invalid sensor hold")
        wait(lambda: len(data["hold_events"]) > after_count,
             timeout=1.0, description="new stale hold telemetry")
        event = data["hold_events"][-1]
        return event["at"]

    def latch_left_warning():
        direction = raw["hazard_side"]
        raw["range_enabled"][direction] = True
        raw["range_cm"][direction] = 10.0
        # The classifier requires distinct samples for the warning band.
        wait(lambda: data["sensors"].get(direction, {}).get("severity") == "warning",
             timeout=3.0, description=f"latched {direction} warning before coverage loss")
        wait(lambda: data["motion"].get("avoidance_mode") == "adjust",
             timeout=3.0, description="bounded warning retreat")

    def assert_clean_abort(result_future, hold_started, description):
        wait(result_future.done, timeout=1.0, description=f"{description} action termination")
        terminal_at = time.monotonic()
        wrapped = result_future.result()
        status = wrapped.status
        assert status in (5, 6), f"expected canceled/preempted safety result, got {status}"
        assert data["state"] != "ERROR", f"{description} incorrectly entered ERROR"
        assert terminal_at - hold_started < 0.14, (
            f"safety grace restarted inside the same goal: "
            f"hold-to-terminal was {terminal_at - hold_started:.3f}s"
        )
        wait(lambda: data["state"] == "IDLE", timeout=3.0,
             description=f"{description} owned-state release to IDLE")
        assert data["state"] != "ERROR", f"{description} entered ERROR during state release"
        return status, terminal_at - hold_started, data["state"]

    def current_base():
        return data["joints"].position[base_index]

    try:
        assert actions.wait_for_server(timeout_sec=10), "PlayAnimation action server unavailable"
        wait(lambda: data["state"] is not None and data["joints"] is not None,
             description="initial simulator state and joint feedback")
        for direction in ("front", "left", "right"):
            wait(lambda d=direction: data["sensors"].get(d, {}).get("valid") is True,
                 description=f"fresh {direction} coverage")
        spin(0.35)
        # The runner may follow earlier tests that left the base at a limit.
        # Select the configured retreat with more room so this scenario tests
        # stale-data handling rather than an unfeasible escape projection.
        base_index = next((i for i, name in enumerate(data["joints"].name)
                           if name in ("base_link_to_link1", "base_to_L1")), None)
        assert base_index is not None, f"base joint missing from feedback: {data['joints'].name}"
        base = data["joints"].position[base_index]
        raw["hazard_side"] = "left" if (3.1416 - base) >= (base + 3.1416) else "right"
        evidence["retreat_side"] = raw["hazard_side"]

        # First hold an animation in the warning-retreat mode. It must keep
        # moving away from the sensor, then finish cleanly at the 2s budget.
        wait(lambda: data["state"] == "IDLE", description="IDLE before invalid-data goal")
        handle, result = start_goal()
        wait(lambda: data["state"] == "ANIMATING", description="animation start")
        wait(lambda: data["motion"].get("avoidance_mode") == "clear",
             description="fresh animation intent clears prior replan hold")
        wait(lambda: data["feedback"] is not None and data["feedback"]["keyframe"] >= 3,
             timeout=30.0, description="same-goal short stages before warning")
        stage_count = data["feedback"]["keyframe"]
        retreat_sign = 1 if raw["hazard_side"] == "left" else -1
        latch_left_warning()
        adjust_started = data["adjust_started"]
        base_at_warning = current_base()
        wait(lambda: (current_base() - base_at_warning) * retreat_sign > .005,
             timeout=1.0, description="actual base feedback retreats from warning")
        assert not result.done(), "warning prematurely terminated animation before its 2s budget"
        wait(result.done, timeout=3.0, description="bounded 2s warning action termination")
        warning_finished = time.monotonic()
        warning_elapsed = warning_finished - adjust_started
        warning_status = result.result().status
        assert warning_status in (5, 6), f"warning budget produced action status {warning_status}"
        assert 1.8 <= warning_elapsed <= 2.8, f"warning window was {warning_elapsed:.3f}s"
        wait(lambda: data["state"] == "IDLE", timeout=3.0,
             description="warning action owned-state release to IDLE")
        assert data["state"] != "ERROR", "warning retirement entered ERROR"
        record("warning_retreat_is_visible_then_expires_cleanly",
               action_status=warning_status, warning_elapsed_seconds=warning_elapsed,
               retreat_axis=data["joints"].name[base_index], retreat_sign=retreat_sign,
               same_goal_keyframes=stage_count)

        # Active warning followed by fresh invalid data must fail closed too.
        raw["range_cm"][raw["hazard_side"]] = 100.0
        wait(lambda: data["motion"].get("avoidance_mode") == "hold_replan",
             timeout=5.0, description="warning clear dwell completes")
        handle, result = start_goal()
        wait(lambda: data["state"] == "ANIMATING", description="fresh-invalid animation start")
        wait(lambda: data["motion"].get("avoidance_mode") == "clear",
             description="fresh intent releases warning replan hold")
        wait(lambda: data["feedback"] is not None and data["feedback"]["keyframe"] >= 3,
             timeout=30.0, description="same-goal stages before invalid sample")
        stage_count = data["feedback"]["keyframe"]
        latch_left_warning()
        holds_before = len(data["hold_events"])
        hazard_side = raw["hazard_side"]
        raw["range_cm"][hazard_side] = float("nan")
        publish_raw()
        wait(lambda: data["sensors"].get(hazard_side, {}).get("valid") is False,
             timeout=3.0, description=f"fresh invalid {hazard_side} sensor status")
        invalid_hold_at = wait_for_stale_mode(holds_before)
        status, latency, state_after = assert_clean_abort(result, invalid_hold_at, "fresh-invalid")
        record("fresh_invalid_coverage_ends_goal_without_error",
               action_status=status, hold_to_terminal_seconds=latency,
               state_after=state_after,
               same_goal_keyframes=stage_count,
               invalid_sensor=data["sensors"][hazard_side])

        # Restore fresh clear coverage; the next goal's new UUID is the required
        # fresh intent after the safety clear edge.
        raw["range_cm"][hazard_side] = 100.0
        raw["range_enabled"][hazard_side] = True
        publish_raw()
        wait(lambda: data["state"] == "IDLE", description="IDLE after invalid-data goal")
        wait(lambda: data["motion"].get("avoidance_mode") == "hold_replan",
             timeout=5.0, description="clear dwell completed; waiting for a fresh intent")
        handle, result = start_goal()
        wait(lambda: data["state"] == "ANIMATING", description="stale-data animation start")
        wait(lambda: data["motion"].get("avoidance_mode") == "clear",
             description="new animation intent clears replan hold")
        wait(lambda: data["feedback"] is not None and data["feedback"]["keyframe"] >= 3,
             timeout=30.0, description="same-goal stages before sensor dropout")
        stage_count = data["feedback"]["keyframe"]
        latch_left_warning()
        holds_before = len(data["hold_events"])
        # Keep front/right and all FSR clear reports fresh, but let left range
        # expire. This isolates stale range coverage from total graph loss.
        raw["range_enabled"][hazard_side] = False
        wait(lambda: data["sensors"].get(hazard_side, {}).get("valid") is False,
             timeout=3.0, description=f"{hazard_side} sensor timeout status")
        stale_hold_at = wait_for_stale_mode(holds_before)
        status, latency, state_after = assert_clean_abort(result, stale_hold_at, "stale-range")
        record("stale_range_coverage_ends_goal_without_error",
               action_status=status, hold_to_terminal_seconds=latency,
               state_after=state_after,
               same_goal_keyframes=stage_count,
               range_sensor=data["sensors"][hazard_side])
        evidence["grace_contract"] = {
            "grace_seconds": 0.15,
            "grace_is_per_action_goal": True,
            "invalid_and_stale_holds_arrived_after_multiple_keyframes": True,
            "short_stage_loop_regression": "covered by test_short_stages_cannot_restart_the_per_goal_safety_grace",
        }
        evidence["passed"] = True
    except BaseException as exc:
        evidence["error"] = repr(exc)
        evidence["last_state"] = data["state"]
        evidence["last_motion"] = data["motion"]
        evidence["last_sensors"] = data["sensors"]
        evidence["feedback_tail"] = data["feedback_changes"][-10:]
        raise
    finally:
        # Leave the simulator with healthy synthetic inputs and no active
        # trajectory even when an assertion fails midway through a case.
        raw["enabled"] = True
        raw["range_enabled"] = {"left": True, "right": True}
        raw["range_cm"] = {"left": 100.0, "right": 100.0}
        if rclpy.ok():
            for _ in range(3):
                publish_raw()
                spin(0.03)
        handle = active_goal["handle"]
        result = active_goal["result"]
        if handle is not None and result is not None and not result.done():
            try:
                cancel = handle.cancel_goal_async()
                deadline = time.monotonic() + 1.0
                while not cancel.done() and time.monotonic() < deadline:
                    spin(0.02)
            except Exception as exc:
                evidence["cleanup_error"] = repr(exc)
        evidence["ended_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(args.output, "w", encoding="utf-8") as output:
            json.dump(evidence, output, indent=2, allow_nan=False)
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
