#!/usr/bin/env python3
"""Exclusive silent raw-sensor→avoidance→actual-feedback ROS evidence.

Requires a rebuilt graph with ReactiveAvoidancePolicy. Never run concurrently
with browser, animation, or other mutating scenario producers.
"""
import argparse
import datetime
import json
import math
import os
import time


def main():
    if os.environ.get('ROS_DOMAIN_ID') != '73' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
        raise SystemExit('Avoidance scenarios require domain73 localhost-only')
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String, Float32, UInt8, Int16
    from sensor_msgs.msg import JointState
    from luxo_interfaces.srv import RequestStateTransition
    from luxo_behaviors.joint_motion import URDF_JOINT_LIMITS
    from luxo_behaviors.joint_profiles import ROARM_M3_LIMITS
    limits = {**URDF_JOINT_LIMITS, **ROARM_M3_LIMITS}
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    rclpy.init()
    node = Node('raw_avoidance_scenarios')
    evidence = {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'runtime_commit': os.environ.get('LUXOPI_RUNTIME_COMMIT', 'unknown'),
                'cases': [], 'passed': False}
    data = {'joints': [], 'names': [], 'state': None, 'motion': {}, 'sensors': []}
    def joints(msg):
        assert len(msg.name) == len(msg.position) and all(math.isfinite(v) for v in msg.position)
        assert len(set(msg.name)) == len(msg.name)
        for name, value in zip(msg.name, msg.position):
            assert name in limits and limits[name][0]-.001 <= value <= limits[name][1]+.001
        data['names'] = list(msg.name)
        data['joints'].append(list(msg.position))
    node.create_subscription(JointState, '/joint_states', joints, 100)
    node.create_subscription(String, '/luxo/current_state', lambda m: data.update(state=m.data), 100)
    node.create_subscription(String, '/sim/motion_status', lambda m: data.update(motion=json.loads(m.data)), 100)
    node.create_subscription(String, '/collision/sensor_status', lambda m: data['sensors'].append(json.loads(m.data)), 100)
    dist = {s: node.create_publisher(Float32, '/i2c/vl53_'+s+'/distance', 10) for s in ('left', 'right')}
    front = node.create_publisher(Int16, '/i2c/apds9960/proximity', 10)
    contact = node.create_publisher(UInt8, '/touch_sensors/head_bottom', 10)
    manual = node.create_publisher(JointState, '/sim/manual_joint_target', 10)
    service = node.create_client(RequestStateTransition, '/luxo/request_state_transition')
    def spin(seconds):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.02)
    def wait(predicate, timeout=10):
        end = time.monotonic()+timeout
        while not predicate():
            if time.monotonic() > end:
                raise AssertionError(f'expectation timed out; state={data["state"]}; motion={data["motion"]}')
            spin(.02)
    def sample(left=100., right=100., head=0):
        for _ in range(2):
            dist['left'].publish(Float32(data=left)); dist['right'].publish(Float32(data=right))
            front.publish(Int16(data=head)); spin(.06)
    def command(index=0, delta=.12):
        values = list(data['joints'][-1]); values[index] += delta
        manual.publish(JointState(name=data['names'], position=values))
    def held(seconds=.4):
        spin(.2); start = len(data['joints']); spin(seconds)
        frames = data['joints'][start:]
        assert len(frames) >= 3
        drift = max(abs(a-b) for row in frames for a,b in zip(frames[0], row))
        assert drift < 1e-4, f'unsafe hold drift {drift}'
        return len(frames)
    def case(name, **values):
        evidence['cases'].append(dict(name=name, passed=True, **values))
    try:
        assert service.wait_for_service(timeout_sec=10)
        wait(lambda: data['joints'] and data['state'] == 'IDLE'); spin(6)
        request = RequestStateTransition.Request()
        request.requested_state = 'USER_CONTROL'; request.requesting_node = 'avoidance_scenarios'
        request.priority = 80; request.force = True
        future = service.call_async(request); wait(future.done); assert future.result().success
        wait(lambda: data['state'] == 'USER_CONTROL')
        sample(); command(); spin(.3)
        for side, index, sign in [('left', 0, 1), ('right', 0, -1), ('front', 1, 1)]:
            sample(); spin(.4); command(index, -sign*.3); spin(.1)
            baseline = data['joints'][-1][index]
            sample(left=6. if side=='left' else 100., right=6. if side=='right' else 100., head=20 if side=='front' else 0)
            wait(lambda: data['motion'].get('avoidance_mode') in ('adjust', 'continue_safe'))
            wait(lambda: (data['joints'][-1][index]-baseline)*sign > .005)
            assert data['state'] == 'COLLISION_AVOIDING'
            case('warning_'+side+'_redirects_actual_joint', axis=data['names'][index], sign=sign)
        sample(left=3.); wait(lambda: data['motion'].get('avoidance_mode', '').startswith('hold'))
        case('danger_holds', frames=held())
        sample(left=6., right=6.); wait(lambda: data['motion'].get('avoidance_mode', '').startswith('hold'))
        case('both_sides_blocked_hold', frames=held())
        sample(); spin(.4); command(); spin(.2)
        contact.publish(UInt8(data=50)); wait(lambda: data['motion'].get('avoidance_mode', '').startswith('hold'))
        case('contact_holds', frames=held()); contact.publish(UInt8(data=0))
        sample(left=6.); spin(.2)
        # Stop all raw samples: expiration must not silently release/replay the old target.
        wait(lambda: any(not s.get('valid', True) for s in data['sensors'][-20:]), timeout=15)
        wait(lambda: data['motion'].get('avoidance_mode', '').startswith('hold'))
        case('dropout_after_warning_holds', frames=held())
        sample(); spin(.4)
        case('fresh_clear_does_not_replay_old_target', frames=held())
        baseline = data['joints'][-1][:]; command()
        wait(lambda: max(abs(a-b) for a,b in zip(baseline, data['joints'][-1])) > .01)
        case('fresh_clear_new_target_replans', state=data['state'])
        evidence['passed'] = True
    except Exception as exc:
        evidence['error'] = repr(exc)
        raise
    finally:
        contact.publish(UInt8(data=0)); sample()
        evidence['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(args.output, 'w') as output:
            json.dump(evidence, output, indent=2)
        node.destroy_node(); rclpy.shutdown()


if __name__ == '__main__':
    main()
