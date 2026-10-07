#!/usr/bin/env python3
"""Exercise APDS gesture routing through the simulated ROS motion graph."""

import json
import os
import time

if os.environ.get("ROS_DOMAIN_ID") != "73" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
    raise SystemExit("Requires ROS_DOMAIN_ID=73 and ROS_LOCALHOST_ONLY=1")

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32, Int16, String, UInt8


GESTURE_ANIMATIONS = {
    "left": "look_around_casual",
    "right": "curious_exploration",
    "up": "neck_stretch",
    "down": "nod",
}


def main():
    rclpy.init()
    node = Node("gesture_motion_scenarios")
    seen = {"state": "", "animation": "", "joints": [], "interaction": {}, "gestures": []}
    node.create_subscription(String, "/luxo/current_state", lambda msg: seen.update(state=msg.data), 10)
    node.create_subscription(String, "/roarm/current_animation", lambda msg: seen.update(animation=msg.data), 10)
    node.create_subscription(JointState, "/joint_states", lambda msg: seen["joints"].append(list(msg.position)), 100)
    node.create_subscription(
        String, "/sim/interaction_status",
        lambda msg: seen.update(interaction=json.loads(msg.data)), 10,
    )
    node.create_subscription(String, "/gestures", lambda msg: seen["gestures"].append(msg.data), 20)
    gesture_publisher = node.create_publisher(String, "/i2c/apds9960/gesture", 10)
    front_publisher = node.create_publisher(Int16, "/i2c/apds9960/proximity", 10)
    left_publisher = node.create_publisher(Float32, "/i2c/vl53_left/distance", 10)
    right_publisher = node.create_publisher(Float32, "/i2c/vl53_right/distance", 10)
    touch_publishers = [
        node.create_publisher(UInt8, f"/touch_sensors/head_{side}", 10)
        for side in ("top", "left", "right", "bottom")
    ]
    last_safety_sample = 0.0

    def spin_for(seconds):
        nonlocal last_safety_sample
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now - last_safety_sample > 0.05:
                front_publisher.publish(Int16(data=0))
                left_publisher.publish(Float32(data=100.0))
                right_publisher.publish(Float32(data=100.0))
                for publisher in touch_publishers:
                    publisher.publish(UInt8(data=0))
                last_safety_sample = now
            rclpy.spin_once(node, timeout_sec=0.01)

    def wait_for(predicate, timeout, description):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline:
                details = {
                    "timeout": description,
                    "state": seen["state"],
                    "animation": seen["animation"],
                    "interaction": seen["interaction"],
                }
                raise RuntimeError(json.dumps(details, sort_keys=True))
            spin_for(0.02)

    results = []
    try:
        wait_for(
            lambda: seen["state"] == "IDLE" and len(seen["joints"]) > 3
            and seen["interaction"].get("state") == "IDLE",
            20,
            "initial ready",
        )
        for direction, animation in GESTURE_ANIMATIONS.items():
            wait_for(
                lambda: seen["state"] == "IDLE" and seen["animation"] == "",
                20,
                f"idle before {direction}",
            )
            baseline_index = len(seen["joints"])
            gesture_publisher.publish(String(data=direction))
            wait_for(
                lambda: seen["interaction"].get("gesture") == direction
                and seen["interaction"].get("gesture_animation") == animation
                and seen["interaction"].get("gesture_status") in ("pending", "accepted"),
                8,
                f"{direction} mapped to {animation}",
            )
            wait_for(
                lambda: seen["interaction"].get("gesture_status") == "completed"
                and seen["state"] == "IDLE" and seen["animation"] == "",
                180,
                f"{animation} finish",
            )
            trajectory = seen["joints"][baseline_index:]
            initial = seen["joints"][baseline_index - 1]
            delta = max(
                max(abs(a - b) for a, b in zip(initial, frame))
                for frame in trajectory
            )
            if delta <= 0.02:
                raise RuntimeError(f"{direction} produced no material joint movement: {delta}")
            if direction not in seen["gestures"]:
                raise RuntimeError(f"{direction} did not pass through /gestures")
            result = {
                "gesture": direction,
                "animation": animation,
                "joint_delta_max_rad": round(delta, 4),
                "joint_frames": len(trajectory),
                "terminal": seen["interaction"].get("gesture_status"),
                "fsm": seen["state"],
                "gesture_passthrough": True,
            }
            results.append(result)
            print(json.dumps(result), flush=True)
            spin_for(1.2)  # Exceed the consumer's gesture debounce interval.
        print(json.dumps({"all_four_passed": True, "results": results}), flush=True)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
