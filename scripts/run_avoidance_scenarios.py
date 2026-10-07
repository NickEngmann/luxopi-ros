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
    from rclpy.action import ActionClient
    from luxo_interfaces.action import PlayAnimation
    from std_msgs.msg import String, Float32, UInt8, Int16, Bool
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile
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
    data = {'joints': [], 'names': [], 'state': None, 'state_history': [], 'animation': None,
            'autonomy': None, 'world_sensors': None, 'motion': {},
            'sensors': [], 'velocity': [], 'hold_onset': None}
    def joints(msg):
        assert len(msg.name) == len(msg.position) and all(math.isfinite(v) for v in msg.position)
        assert len(set(msg.name)) == len(msg.name)
        for name, value in zip(msg.name, msg.position):
            assert name in limits and limits[name][0]-.001 <= value <= limits[name][1]+.001
        data['names'] = list(msg.name)
        data['joints'].append(list(msg.position))
        data['velocity']=list(msg.velocity)
    node.create_subscription(JointState, '/joint_states', joints, 100)
    def state(msg):
        data['state'] = msg.data
        data['state_history'].append(msg.data)
    node.create_subscription(String, '/luxo/current_state', state, 100)
    node.create_subscription(String, '/roarm/current_animation',
                             lambda msg: data.update(animation=msg.data), 10)
    autonomy = node.create_publisher(Bool, '/sim/autonomy_enabled', 10)
    autonomy_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1,
                              durability=DurabilityPolicy.TRANSIENT_LOCAL)
    node.create_subscription(Bool, '/sim/autonomy_status',
                             lambda msg: data.update(autonomy=msg.data), autonomy_qos)
    def motion_status(msg):
        status=json.loads(msg.data)
        if (status.get('motion_hold_requested')
                and not data['motion'].get('motion_hold_requested')
                and data['joints']):
            data['hold_onset']={'time':time.monotonic(),'position':data['joints'][-1][:],
                                'velocity':data['velocity'][:]}
        data['motion']=status
    node.create_subscription(String, '/sim/motion_status', motion_status, 100)
    node.create_subscription(String, '/collision/sensor_status', lambda m: data['sensors'].append(json.loads(m.data)), 100)
    node.create_subscription(String, '/sim/world_sensor_status',
                             lambda msg: data.update(world_sensors=json.loads(msg.data)), 10)
    dist = {s: node.create_publisher(Float32, '/i2c/vl53_'+s+'/distance', 10) for s in ('left', 'right')}
    front = node.create_publisher(Int16, '/i2c/apds9960/proximity', 10)
    touch = {s: node.create_publisher(UInt8, '/touch_sensors/head_'+s, 10) for s in ('top','left','right','bottom')}
    contact = touch['bottom']
    manual = node.create_publisher(JointState, '/sim/manual_joint_target', 10)
    sensor_faults = node.create_publisher(String, '/sim/sensor_faults', 10)
    service = node.create_client(RequestStateTransition, '/luxo/request_state_transition')
    actions = ActionClient(node, PlayAnimation, 'play_animation')
    raw={'left':100.,'right':100.,'head':0,'contact':0,'enabled':True,'sent':0.}
    def publish_raw():
        dist['left'].publish(Float32(data=raw['left']));dist['right'].publish(Float32(data=raw['right']))
        front.publish(Int16(data=raw['head']))
        for side,publisher in touch.items():publisher.publish(UInt8(data=raw['contact'] if side=='bottom' else 0))
        raw['sent']=time.monotonic()
    def spin(seconds):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            if raw['enabled'] and time.monotonic()-raw['sent']>.08: publish_raw()
            rclpy.spin_once(node, timeout_sec=.02)
    def wait(predicate, timeout=10):
        end = time.monotonic()+timeout
        while not predicate():
            if time.monotonic() > end:
                raise AssertionError(f'expectation timed out; state={data["state"]}; motion={data["motion"]}')
            spin(.02)
    def sample(left=100., right=100., head=0):
        raw.update(left=left,right=right,head=head,enabled=True)
        for _ in range(2):publish_raw();spin(.06)
    def command(index=0, delta=.12):
        values = list(data['joints'][-1]); values[index] += delta
        manual.publish(JointState(name=data['names'], position=values))
    def held(seconds=.4):
        onset=data['hold_onset']
        assert onset and len(onset['velocity'])==len(onset['position'])
        # Simulation caps are .5rad/s and 1rad/s², not hardware braking specs.
        acceleration=1.
        initial_speed=max(abs(v) for v in onset['velocity'])
        # The torque-limited MuJoCo servo adds a bounded physical settling
        # tail after the command-side deceleration profile completes.
        deadline=onset['time']+max(1.5, initial_speed/acceleration+.4)
        while not data['motion'].get('motion_frozen'):
            assert time.monotonic()<=deadline,(
                'Braking exceeded velocity/acceleration bound plus scheduling margin',
                {'initial_speed': initial_speed, 'elapsed': time.monotonic()-onset['time'],
                 'latest_velocity': data['velocity'], 'motion': data['motion']})
            spin(.02)
        stopped=data['joints'][-1]
        for before,after,velocity in zip(onset['position'],stopped,onset['velocity']):
            # MuJoCo's torque-limited servo adds a small tracking transient on
            # top of the kinematic stop envelope; allow 0.03 rad for that
            # model/controller discretization while still rejecting a runaway.
            bound=velocity*velocity/(2*acceleration)+2*.02*abs(velocity)+.03
            assert abs(after-before)<=bound,('braking travel exceeded bound',after-before,bound)
        start=len(data['joints']);spin(seconds)
        frames=data['joints'][start:]
        assert len(frames)>=3
        drift=max(abs(a-b) for row in frames for a,b in zip(frames[0],row))
        # At 500 Hz MuJoCo stepping the servo can settle by a few 1e-4 rad
        # between feedback publications; this tolerance still catches a
        # resumed command while avoiding a false failure on solver jitter.
        assert drift<5e-4,f'resumed motion after braking {drift}'
        return len(frames)
    def case(name, **values):
        evidence['cases'].append(dict(name=name, passed=True, **values))
    try:
        assert service.wait_for_service(timeout_sec=10)
        wait(lambda: data['joints'] and data['state'] is not None
             and data['autonomy'] is not None); spin(1)
        # Autonomous idle activity can start an animation while this suite
        # requests USER_CONTROL. Pause it through the same retained control
        # channel used by the other isolated ROS scenarios, and wait for any
        # in-flight action to relinquish motion ownership before testing.
        for _ in range(8):
            autonomy.publish(Bool(data=False))
            if data['autonomy'] is False:
                break
            spin(.1)
        wait(lambda: data['autonomy'] is False, timeout=3)
        wait(lambda: data['animation'] in (None, ''), timeout=10)
        spin(.3)
        # The physics world's geometric fixture is the normal source for the
        # raw optical topics. Suspend only those publishers while this test
        # injects controlled values through the same production ROS inputs.
        wait(lambda: data['world_sensors'] is not None, timeout=5)
        sensor_faults.publish(String(data=json.dumps(
            {'front': True, 'left': True, 'right': True}, separators=(',', ':'))))
        wait(lambda: data['world_sensors'].get('sensor_faults') ==
             {'front': True, 'left': True, 'right': True}, timeout=5)
        spin(.2)
        request = RequestStateTransition.Request()
        request.requested_state = 'USER_CONTROL'; request.requesting_node = 'avoidance_scenarios'
        request.priority = 80; request.force = True
        future = service.call_async(request); wait(future.done); assert future.result().success
        wait(lambda: data['state'] == 'USER_CONTROL')
        sample(); command(); spin(.3)
        for side, index, sign in [('left', 0, -1), ('right', 0, 1), ('front', 1, 1)]:
            sample(); spin(.4); command(index, -sign*.3); spin(.1)
            baseline = data['joints'][-1][index]
            state_history_start=len(data['state_history'])
            sample(left=6. if side=='left' else 100., right=6. if side=='right' else 100., head=20 if side=='front' else 0)
            wait(lambda: data['motion'].get('avoidance_mode') in ('adjust', 'continue_safe'))
            wait(lambda: (data['joints'][-1][index]-baseline)*sign > .005)
            wait(lambda: 'COLLISION_AVOIDING' in data['state_history'][state_history_start:])
            case('warning_'+side+'_redirects_actual_joint', axis=data['names'][index], sign=sign)
        sample(left=3.); wait(lambda: data['motion'].get('avoidance_mode')=='hold_imminent')
        case('danger_holds', frames=held())
        sample();spin(.4);command();spin(.15)
        sample(left=6., right=6.); wait(lambda: data['motion'].get('avoidance_mode')=='hold_blocked')
        case('both_sides_blocked_hold', frames=held())
        sample(); spin(.4); command(); spin(.2)
        raw['contact']=50; contact.publish(UInt8(data=50)); wait(lambda: data['motion'].get('avoidance_mode')=='hold_imminent')
        case('contact_holds', frames=held()); raw['contact']=0; contact.publish(UInt8(data=0))
        sample(left=6.); spin(.2)
        # Stop all raw samples: expiration must not silently release/replay the old target.
        raw['enabled']=False
        wait(lambda: any(not s.get('valid', True) for s in data['sensors'][-20:]), timeout=15)
        wait(lambda: data['motion'].get('avoidance_mode')=='hold_stale')
        case('dropout_after_warning_holds', frames=held())
        sample(); spin(.4)
        wait(lambda: data['motion'].get('avoidance_mode')=='hold_replan')
        case('fresh_clear_does_not_replay_old_target', frames=held())
        baseline = data['joints'][-1][:]; command()
        wait(lambda: max(abs(a-b) for a,b in zip(baseline, data['joints'][-1])) > .01)
        case('fresh_clear_new_target_replans', state=data['state'])
        # A real action must keep running through warning projection, then abort
        # on danger. Manual target projection alone cannot prove this bridge.
        sample(); spin(.4)
        idle = RequestStateTransition.Request()
        idle.requested_state = 'IDLE'; idle.requesting_node = 'avoidance_scenarios'
        idle.priority = 100; idle.force = True
        future = service.call_async(idle); wait(future.done); assert future.result().success
        wait(lambda: data['state'] == 'IDLE')
        assert actions.wait_for_server(timeout_sec=10)
        goal = PlayAnimation.Goal(); goal.animation_name = 'dance'
        # Slow the finite recipe enough that the active-warning and danger
        # phases cannot race the normal animation completion.
        goal.speed_multiplier = .1
        sent = actions.send_goal_async(goal); wait(sent.done)
        handle = sent.result(); assert handle.accepted
        result = handle.get_result_async()
        wait(lambda: data['state'] == 'ANIMATING')
        # Wait for actual unsafe yaw rather than assuming the first recipe
        # frame moves the base (it preserves current yaw).
        start_yaw=data['joints'][-1][0]
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            sample()
            yaw_delta=data['joints'][-1][0]-start_yaw
            # Catch the first measurable segment displacement. Waiting for a
            # larger offset can place the warning at the end of this short
            # yaw segment, making the action-completion assertion scheduler-
            # dependent rather than a clean mid-action safety check.
            if abs(yaw_delta)>.003: break
            assert not result.done(),'Action finished without observable yaw motion'
        assert abs(yaw_delta)>.003,'No moving yaw segment observed'
        side='right' if yaw_delta>0 else 'left'
        retreat_sign=1 if side=='right' else -1
        baseline=data['joints'][-1][0]
        adjusted=False
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            sample(left=6. if side=='left' else 100.,right=6. if side=='right' else 100.)
            adjusted=adjusted or data['motion'].get('avoidance_mode')=='adjust'
            if adjusted and (data['joints'][-1][0]-baseline)*retreat_sign>.005: break
        assert adjusted,data['motion']
        assert (data['joints'][-1][0]-baseline)*retreat_sign>.005
        assert not result.done(),'warning incorrectly terminated the action'
        case('active_animation_warning_redirects_without_abort',animation='dance',
             axis=data['names'][0],hazard=side,retreat_sign=retreat_sign,
             state_during_check=data['state'])
        sample(left=3. if side=='left' else 100.,right=3. if side=='right' else 100.)
        wait(result.done)
        assert result.result().status == 6, result.result().status
        case('active_animation_danger_aborts', terminal_status=result.result().status, held_frames=held())
        evidence['passed'] = True
    except BaseException as exc:
        evidence['error'] = repr(exc)
        evidence['last_motion']=data['motion']
        evidence['last_sensors']=data['sensors'][-6:]
        raise
    finally:
        evidence['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(args.output, 'w') as output:
            json.dump(evidence, output, indent=2)
        if rclpy.ok():
            raw['contact']=0; contact.publish(UInt8(data=0)); sample()
            raw.update(left=100., right=100., head=0, contact=0)
            publish_raw()
            sensor_faults.publish(String(data=json.dumps(
                {'front': False, 'left': False, 'right': False}, separators=(',', ':'))))
            autonomy.publish(Bool(data=True))
            spin(.2)
            node.destroy_node(); rclpy.shutdown()


if __name__ == '__main__':
    main()
