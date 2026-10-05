#!/usr/bin/env python3
"""Native ROS checks for voice-session and touch/petting state consumers."""
import json
import os
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class InteractionScenarios(Node):
    def __init__(self):
        super().__init__("sim_interaction_scenarios")
        self.state = None
        self.animation = ""
        self.adapter = {}
        self.status_pub = self.create_publisher(String, "/voice/status", 10)
        self.petting_pub = self.create_publisher(String, "/collision/petting_events", 10)
        self.create_subscription(String, "/luxo/current_state", self._state_cb, 10)
        self.create_subscription(String, "/roarm/current_animation", self._animation_cb, 10)
        self.create_subscription(String, "/sim/interaction_status", self._adapter_cb, 10)

    def _state_cb(self, msg):
        self.state = msg.data

    def _animation_cb(self, msg):
        self.animation = msg.data

    def _adapter_cb(self, msg):
        try:
            self.adapter = json.loads(msg.data)
        except json.JSONDecodeError:
            self.adapter = {"error": "invalid interaction status JSON"}

    def pump(self, seconds=0.1):
        rclpy.spin_once(self, timeout_sec=seconds)

    def wait_for(self, predicate, timeout, description):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pump(0.1)
            if predicate():
                return
        raise AssertionError(
            f"timed out waiting for {description}; state={self.state}, "
            f"animation={self.animation}, adapter={self.adapter}"
        )

    def publish_repeated(self, publisher, value, count=5):
        message = String(data=value)
        for _ in range(count):
            publisher.publish(message)
            self.pump(0.08)


def main():
    if os.environ.get("ROS_DOMAIN_ID") != "73" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise RuntimeError("run this test only in the isolated domain 73 container")
    rclpy.init()
    node = InteractionScenarios()
    try:
        node.wait_for(lambda: node.state == "IDLE", 30, "startup INITIALIZING→IDLE")

        node.publish_repeated(node.status_pub, "thinking")
        node.wait_for(
            lambda: node.state == "USER_CONTROL" and node.adapter.get("voice_session_owned"),
            5,
            "voice status to request USER_CONTROL",
        )
        node.publish_repeated(node.status_pub, "idle")
        node.wait_for(lambda: node.state == "IDLE", 5, "voice completion to return IDLE")

        node.publish_repeated(node.petting_pub, "petting_started:55")
        node.wait_for(lambda: node.state == "PETTING", 5, "touch event to request PETTING")
        node.wait_for(
            lambda: node.animation == "folded_wiggle",
            5,
            "petting state to start registered petting animation",
        )
        node.publish_repeated(node.petting_pub, "petting_stopped:0")
        node.wait_for(lambda: node.state == "IDLE", 20, "petting action completion to return IDLE")

        print(json.dumps({
            "startup_idle": True,
            "voice_user_control_and_idle": True,
            "petting_state_and_action": True,
            "petting_idle_recovery": True,
            "final_state": node.state,
        }, sort_keys=True))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
