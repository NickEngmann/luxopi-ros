#!/usr/bin/env python3
"""Verify camera-triggered motion is preempted by classified raw collision data.

Run only against an isolated ROS graph (domain 73, localhost-only). The scenario
uses the actual camera reaction, collision classifier, animation action server,
state manager and joint controller; it never publishes classified warnings.
"""
import argparse
import datetime
import json
import math
import os
import time


def main():
    if os.environ.get('ROS_DOMAIN_ID') != '73' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
        raise SystemExit('Vision/collision scenarios require domain73 localhost-only')

    import rclpy
    from action_msgs.msg import GoalStatusArray
    from rclpy.node import Node
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Float32, Int16, String, UInt8

    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    rclpy.init()
    node = Node('vision_collision_scenarios')
    data = {
        'state': None, 'animation': None, 'joints': [], 'sensors': [],
        'motion': {}, 'action_status': [], 'action_status_history': [],
    }
    node.create_subscription(String, '/luxo/current_state', lambda m: data.update(state=m.data), 50)
    node.create_subscription(String, '/roarm/current_animation', lambda m: data.update(animation=m.data), 50)
    def joint_cb(msg):
        assert len(msg.name) == len(msg.position) and len(set(msg.name)) == len(msg.name)
        assert all(math.isfinite(value) for value in msg.position)
        data['joints'].append(dict(names=list(msg.name), position=list(msg.position)))
    node.create_subscription(JointState, '/joint_states', joint_cb, 100)
    node.create_subscription(String, '/collision/sensor_status',
                             lambda m: data['sensors'].append(json.loads(m.data)), 50)
    node.create_subscription(String, '/sim/motion_status',
                             lambda m: data.update(motion=json.loads(m.data)), 50)
    def action_status_cb(msg):
        statuses = [int(status.status) for status in msg.status_list]
        data['action_status'] = statuses
        data['action_status_history'].append(statuses)
    node.create_subscription(GoalStatusArray, '/play_animation/_action/status', action_status_cb, 50)

    emotion = node.create_publisher(String, '/sim/camera/emotion', 10)
    distance = node.create_publisher(Float32, '/sim/camera/person_distance', 10)
    front = node.create_publisher(Int16, '/i2c/apds9960/proximity', 10)
    sides = [node.create_publisher(Float32, f'/i2c/vl53_{side}/distance', 10)
             for side in ('left', 'right')]
    contacts = [node.create_publisher(UInt8, f'/touch_sensors/head_{part}', 10)
                for part in ('bottom', 'left', 'right')]
    evidence = {
        'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'runtime_commit': os.environ.get('LUXOPI_RUNTIME_COMMIT', 'unknown'),
        'cases': [], 'passed': False,
    }
    latest = {'left_cm': 100.0, 'right_cm': 100.0, 'proximity': 0}
    last_raw = 0.0
    def publish_sensors():
        nonlocal last_raw
        front.publish(Int16(data=latest['proximity']))
        for pub, value in zip(sides, (latest['left_cm'], latest['right_cm'])):
            pub.publish(Float32(data=value))
        for pub in contacts:
            pub.publish(UInt8(data=0))
        last_raw = time.monotonic()
    def spin(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if time.monotonic() - last_raw > 0.08:
                publish_sensors()
            rclpy.spin_once(node, timeout_sec=0.02)
    def wait(predicate, timeout=15, description='condition'):
        end = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() > end:
                raise AssertionError(f'timed out waiting for {description}; state={data["state"]}, '
                                     f'animation={data["animation"]}, motion={data["motion"]}')
            spin(0.02)

    try:
        wait(lambda: data['joints'] and data['state'] is not None, description='initial feedback')
        # Preserve actual startup reaction cooldown; don't rush the consumer.
        spin(6.0)
        publish_sensors()
        spin(0.5)
        baseline = data['joints'][-1]['position']
        for _ in range(20):
            distance.publish(Float32(data=1.2))
            emotion.publish(String(data='sad'))
            spin(0.1)
        wait(lambda: data['state'] == 'EMOTION_REACTING' and data['animation'] == 'sad',
             timeout=15, description='vision-triggered sad action')
        wait(lambda: 2 in data['action_status'], timeout=5,
             description='active action goal before injecting collision')
        wait(lambda: len(data['joints']) >= 12 and
             max(abs(a - b) for a, b in zip(baseline, data['joints'][-1]['position'])) > 0.03,
             timeout=25, description='emotion joint movement')
        active_start = time.monotonic()
        evidence['cases'].append({
            'name': 'camera_emotion_starts_real_animation', 'passed': True,
            'state': data['state'], 'animation': data['animation'],
            'joint_names': data['joints'][-1]['names'],
            'joint_displacement_rad': max(abs(a - b) for a, b in zip(baseline, data['joints'][-1]['position'])),
        })

        # Continue feeding fresh, clear raw sensors, then introduce a real front
        # proximity hazard. Two distinct APDS samples are required by classifier.
        latest['proximity'] = 255
        for _ in range(3):
            publish_sensors()
            spin(0.06)
        wait(lambda: any(s.get('direction') == 'front' and s.get('valid') and
                         s.get('severity') in ('danger', 'imminent') for s in data['sensors'][-30:]),
             timeout=5, description='classified front danger from raw APDS')
        wait(lambda: data['state'] == 'COLLISION_AVOIDING', timeout=5,
             description='collision-priority state')
        wait(lambda: not data['animation'] or data['animation'] != 'sad', timeout=10,
             description='emotion action preemption')
        assert time.monotonic() - active_start < 35, 'emotion action was not interrupted promptly'
        assert max(abs(a - b) for a, b in zip(baseline, data['joints'][-1]['position'])) > 0.03
        assert 6 in data['action_status'], f'no canceled animation action terminal status: {data["action_status"]}'
        evidence['cases'].append({
            'name': 'raw_collision_preempts_vision_animation', 'passed': True,
            'collision_state': data['state'], 'terminal_action_status': 6,
            'action_status_history': data['action_status_history'],
            'joint_frames': len(data['joints']),
            'front_sensor_status': [s for s in data['sensors'][-30:] if s.get('direction') == 'front'][-1],
        })

        # Clear the physical inputs and let the classifier's clear dwell finish.
        # Recovery must not resume the old emotion goal; only a new intent may move.
        latest['proximity'] = 0
        latest['left_cm'] = latest['right_cm'] = 100.0
        wait(lambda: data['state'] == 'IDLE' and data['motion'].get('avoidance_mode') == 'hold_replan',
             timeout=20, description='clear collision enters fresh-intent hold')
        parked = data['joints'][-1]['position'][:]
        spin(1.0)
        drift = max(abs(a - b) for row in data['joints'][-10:] for a, b in zip(parked, row['position']))
        assert drift < 0.01, f'old vision animation resumed without a fresh intent (drift {drift})'
        evidence['cases'].append({
            'name': 'collision_clear_does_not_resume_stale_vision_goal', 'passed': True,
            'state': data['state'], 'avoidance_mode': data['motion'].get('avoidance_mode'),
            'joint_drift_rad': drift,
        })
        evidence['passed'] = True
    except BaseException as exc:
        evidence['error'] = repr(exc)
        evidence['last_state'] = data['state']
        evidence['last_animation'] = data['animation']
        evidence['last_motion'] = data['motion']
        evidence['last_action_status'] = data['action_status']
        evidence['last_sensors'] = data['sensors'][-6:]
        raise
    finally:
        latest['proximity'] = 0
        latest['left_cm'] = latest['right_cm'] = 100.0
        publish_sensors()
        evidence['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(args.output, 'w') as output:
            json.dump(evidence, output, indent=2)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
