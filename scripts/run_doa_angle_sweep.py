#!/usr/bin/env python3
"""Exercise simulated ReSpeaker angles through estimator and bounded motion."""
import json
import math
import os
from pathlib import Path
import time

if os.environ.get("ROS_DOMAIN_ID") != "73" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
    raise SystemExit("DOA angle sweep requires the isolated simulator ROS domain 73")

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float32, String
from luxo_interfaces.srv import RequestStateTransition
from luxo_behaviors.joint_profiles import ROARM_M3_LIMITS
from luxo_behaviors.sim_motion_rules import (
    nearest_cable_safe_angle,
    normalize_direction_degrees,
)


class AngleSweep(Node):
    def __init__(self):
        super().__init__("doa_angle_sweep")
        self.source = self.create_publisher(Float32, "/sim/audio_direction", 10)
        self.manual = self.create_publisher(JointState, "/sim/manual_joint_target", 10)
        self.states = self.create_client(RequestStateTransition, "/luxo/request_state_transition")
        self.state = ""
        self.active = False
        self.target_degrees = None
        self.evidence = None
        self.joint_names = []
        self.base = None
        self.positions = []
        self.history = []
        self.create_subscription(String, "/luxo/current_state", self.state_cb, 10)
        self.create_subscription(Bool, "/voice/active", self.active_cb, 10)
        self.create_subscription(Float32, "/voice/follow_direction", self.target_cb, 10)
        self.create_subscription(String, "/sim/direction_evidence", self.evidence_cb, 10)
        self.create_subscription(JointState, "/joint_states", self.joint_cb, 20)

    def state_cb(self, msg):
        self.state = msg.data

    def active_cb(self, msg):
        self.active = bool(msg.data)

    def target_cb(self, msg):
        self.target_degrees = float(msg.data)

    def evidence_cb(self, msg):
        try:
            self.evidence = json.loads(msg.data)
        except json.JSONDecodeError:
            self.evidence = None

    def joint_cb(self, msg):
        if not msg.name or len(msg.name) != len(msg.position):
            return
        self.joint_names = list(msg.name)
        self.positions = [float(value) for value in msg.position]
        self.base = float(msg.position[0])
        self.history.append((time.monotonic(), self.base))

    def spin(self, duration=.05):
        rclpy.spin_once(self, timeout_sec=duration)

    def wait(self, predicate, timeout, description):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline:
                raise TimeoutError(description)
            self.spin(.05)

    def transition(self, state):
        self.wait(lambda: self.states.service_is_ready(), 10, "state service unavailable")
        request = RequestStateTransition.Request()
        request.requested_state = state
        request.requesting_node = "doa_angle_sweep"
        request.priority = 100
        request.force = True
        future = self.states.call_async(request)
        self.wait(future.done, 10, "state transition timed out: " + state)
        response = future.result()
        assert response.success, response.message
        self.wait(lambda: self.state == state, 5, "state did not become " + state)

    def reset_base(self):
        self.transition("USER_CONTROL")
        pose = list(self.positions)
        pose[0] = 0.0
        message = JointState()
        message.name = self.joint_names
        message.position = pose
        for _ in range(5):
            self.manual.publish(message)
            self.spin(.05)
        self.wait(lambda: abs(self.base) < .02, 10, "manual reset to zero yaw failed")
        self.transition("IDLE")
        self.wait(lambda: self.state == "IDLE", 5, "reset did not return to IDLE")


def run(output):
    rclpy.init()
    node = AngleSweep()
    results = []
    try:
        node.wait(lambda: node.state and node.base is not None, 20, "initial state/feedback")
        for source_angle in (0.0, 90.0, 180.0, 270.0):
            node.wait(lambda: node.state == "IDLE" and not node.active, 12,
                      "previous DOA session did not return to IDLE")
            node.reset_base()
            before = node.base
            start_history = len(node.history)
            node.evidence = None
            node.target_degrees = None
            deadline = time.monotonic() + 12.0
            expected = None
            while time.monotonic() < deadline:
                node.source.publish(Float32(data=source_angle))
                node.spin(.05)
                if node.target_degrees is not None and node.base is not None:
                    lower, upper = ROARM_M3_LIMITS[node.joint_names[0]]
                    expected = nearest_cable_safe_angle(
                        before,
                        math.radians(normalize_direction_degrees(node.target_degrees)),
                        lower, upper,
                    )
                    if node.evidence is not None and abs(node.base - expected) <= .05:
                        break
            assert node.evidence is not None, f"No estimator evidence for {source_angle}°"
            assert node.target_degrees is not None, f"No DOA motion target for {source_angle}°"
            assert expected is not None and abs(node.base - expected) <= .05, (
                source_angle, node.base, expected
            )
            lower, upper = ROARM_M3_LIMITS[node.joint_names[0]]
            path = [value for _, value in node.history[start_history:]]
            assert path and min(path) >= lower - .02 and max(path) <= upper + .02, (
                source_angle, min(path), max(path), lower, upper
            )
            node.source.publish(Float32(data=source_angle))
            node.spin(.05)
            node.wait(lambda: not node.active and node.state == "IDLE", 8,
                      "DOA activity did not quiet back to IDLE")
            result = {
                "source_angle_degrees": source_angle,
                "measured_mic_angle_degrees": node.evidence.get("measured_mic_angle"),
                "robot_target_raw_degrees": node.target_degrees,
                "robot_target_degrees": normalize_direction_degrees(node.target_degrees),
                "base_before_degrees": math.degrees(before),
                "base_after_degrees": math.degrees(node.base),
                "final_error_degrees": math.degrees(abs(node.base - expected)),
                "base_path_min_degrees": math.degrees(min(path)),
                "base_path_max_degrees": math.degrees(max(path)),
                "feedback_frames": len(path),
                "quiet_state": node.state,
                "passed": True,
            }
            results.append(result)
            print(json.dumps(result), flush=True)
        output.write_text(json.dumps({
            "results": results,
            "error": None,
            "scope": "Synthetic delayed-array DOA angles through the shared estimator and MuJoCo motion controller; no physical microphones or speaker output.",
        }, indent=2) + "\n", encoding="utf-8")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/doa-angle-sweep.json"))
    args = parser.parse_args()
    run(args.output)
