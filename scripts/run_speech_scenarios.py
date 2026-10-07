#!/usr/bin/env python3
"""Silent ROS text→local service→transcript/reply/animation contract scenarios."""

import argparse
import json
import os
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def main():
    if os.environ.get("ROS_DOMAIN_ID") != "73" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise SystemExit("Refusing to run outside isolated domain 73 / localhost-only")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="/test")
    args = parser.parse_args()
    prefix = args.prefix.rstrip("/")
    rclpy.init()
    node = Node("speech_scenario_observer")
    transcripts, replies, statuses, animations = [], [], [], []
    subscriptions = [node.create_subscription(String, prefix + topic, lambda msg, target=target: target.append(msg.data), 10)
                     for topic, target in [
                         ("/voice/transcript", transcripts), ("/voice/response", replies),
                         ("/voice/status", statuses), ("/animation_command", animations),
                     ]]
    commands = node.create_publisher(String, prefix + "/voice/command", 10)

    def wait_for(predicate, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            if predicate():
                return
        raise AssertionError("Timed out waiting for speech scenario output")

    try:
        wait_for(lambda: commands.get_subscription_count() > 0, 10)
        for text, expected_animation in [("Please dance", "dance"), ("Why do plants need water?", None)]:
            transcripts.clear(); replies.clear(); statuses.clear(); animations.clear()
            start = time.monotonic()
            commands.publish(String(data=text))
            wait_for(lambda: bool(replies) and "idle" in statuses, 20)
            assert transcripts == [text], transcripts
            assert replies[-1].strip(), replies
            assert "speaking" in statuses, statuses
            assert animations == ([expected_animation] if expected_animation else []), animations
            print(json.dumps({"scenario": "local_speech", "text": text,
                              "response": replies[-1], "statuses": statuses,
                              "animations": animations, "seconds": time.monotonic() - start}), flush=True)
        replies.clear(); animations.clear()
        commands.publish(String(data="x" * 2001))
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
        assert not replies and not animations, "Oversized input must not reach the backend"
        print(json.dumps({"scenario": "oversized_input_rejected", "passed": True}), flush=True)
    finally:
        for subscription in subscriptions:
            node.destroy_subscription(subscription)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
