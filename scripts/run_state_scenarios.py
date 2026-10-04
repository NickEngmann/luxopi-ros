#!/usr/bin/env python3
"""Repeatable state-service scenarios; run only in an isolated simulator graph."""
import json
import os
import time

# Never discover the physical/default ROS graph.
if os.environ.get('ROS_DOMAIN_ID') != '73' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
    raise SystemExit('Set ROS_DOMAIN_ID=73 and ROS_LOCALHOST_ONLY=1 for simulator scenarios')

import rclpy
from rclpy.node import Node
from luxo_interfaces.srv import RequestStateTransition


def main():
    rclpy.init()
    node = Node('luxopi_state_scenarios')
    client = node.create_client(RequestStateTransition, '/luxo/request_state_transition')
    results = []
    def request(label, target, requester='scenario', priority=100, force=False,
                completion=False, expected=None, success=True):
        req = RequestStateTransition.Request()
        req.requested_state, req.requesting_node = target, requester
        req.priority, req.force, req.completion = priority, force, completion
        started = time.monotonic()
        future = client.call_async(req)
        rclpy.spin_until_future_complete(node, future, timeout_sec=3)
        response = future.result() if future.done() else None
        passed = response is not None and response.success == success
        if expected is not None:
            passed = passed and response is not None and response.current_state == expected
        results.append(dict(scenario=label, passed=passed, milliseconds=round((time.monotonic()-started)*1000, 2),
                            state=response.current_state if response else None,
                            message=response.message if response else 'timeout'))
        if not passed:
            raise AssertionError(results[-1])
    try:
        if not client.wait_for_service(timeout_sec=10):
            raise RuntimeError('Simulator state manager is unavailable')
        request('reset idle', 'IDLE', force=True, expected='IDLE')
        request('dance state', 'ANIMATING', 'animation', 40, expected='ANIMATING')
        request('collision interrupts dance', 'COLLISION_AVOIDING', 'behavior_coordinator', 100, expected='COLLISION_AVOIDING')
        request('idle cannot steal safety state', 'IDLE', 'idle', 30, expected='COLLISION_AVOIDING', success=False)
        request('collision completion restores dance', 'IDLE', 'behavior_coordinator', 100, completion=True, expected='ANIMATING')
        request('dance finishes', 'IDLE', 'animation_command', 30, completion=True, expected='IDLE')
        request('voice heard', 'VOICE_FOLLOWING', 'voice_following', 75, expected='VOICE_FOLLOWING')
        request('capture command', 'USER_CONTROL', 'user_control', 80, expected='USER_CONTROL')
        request('voice response animation', 'ANIMATING', 'user_control', 80, expected='ANIMATING')
        request('response complete', 'IDLE', 'animation_command', 30, completion=True, expected='IDLE')
        request('animation before touch', 'ANIMATING', 'animation', 40, expected='ANIMATING')
        request('touch interrupts', 'PETTING', 'petting', 60, expected='PETTING')
        request('touch finishes restoring animation', 'IDLE', 'petting', 60, completion=True, expected='ANIMATING')
        request('restored animation owner finishes', 'IDLE', 'animation_command', 30, completion=True, expected='IDLE')
        for state in ('EMOTION_REACTING', 'RETURNING_HOME', 'ESCAPE_MODE', 'ERROR', 'INITIALIZING'):
            request('state entry '+state, state, force=True, expected=state)
            request('state recovery '+state, 'IDLE', force=True, expected='IDLE')
        request('invalid state', 'UNKNOWN', expected='IDLE', success=False)
        # Terminal state last; reset only with explicit force after observation.
        request('shutdown', 'SHUTDOWN', expected='SHUTDOWN')
        request('shutdown rejects ordinary restart', 'IDLE', expected='SHUTDOWN', success=False)
        request('reset after scenario suite', 'IDLE', force=True, expected='IDLE')
    finally:
        print(json.dumps({'results': results}, indent=2))
        node.destroy_node()
        rclpy.shutdown()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
