#!/usr/bin/env python3
"""Native ROS action, direction and safety scenarios; no device/audio access."""
import argparse
import json
import math
import os
from pathlib import Path
import time

if os.environ.get('ROS_DOMAIN_ID') != '73' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
    raise SystemExit('Motion scenarios require ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1')

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile
from rclpy.action import ActionClient
from action_msgs.msg import GoalStatus
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float32, String
from luxo_interfaces.action import PlayAnimation
from luxo_interfaces.srv import RequestStateTransition
from luxo_behaviors.joint_motion import URDF_JOINT_LIMITS
from luxo_behaviors.joint_profiles import ROARM_M3_LIMITS
ALL_JOINT_LIMITS = {**URDF_JOINT_LIMITS, **ROARM_M3_LIMITS}


class Scenarios:
    def __init__(self):
        self.node = Node('motion_scenarios')
        self.actions = ActionClient(self.node, PlayAnimation, 'play_animation')
        self.states = self.node.create_client(RequestStateTransition, '/luxo/request_state_transition')
        self.direction = self.node.create_publisher(Float32, '/sim/audio_direction', 10)
        self.voice_active = self.node.create_publisher(Bool, '/voice/active', 10)
        self.manual = self.node.create_publisher(JointState, '/sim/manual_joint_target', 10)
        self.autonomy = self.node.create_publisher(Bool, '/sim/autonomy_enabled', 10)
        self.current_state = None
        self.current_animation = None
        self.autonomy_enabled = None
        self.voice_active_state = False
        self.voice_target = None
        self.joints, self.targets, self.errors = [], [], []
        self.results=[]
        self.expected_durations={}
        self.feasible_retiming=False
        self.continuous_retiming=False
        self.joint_names=[]
        self.node.create_subscription(String, '/luxo/current_state', lambda msg:setattr(self,'current_state',msg.data),10)
        self.node.create_subscription(String, '/roarm/current_animation', lambda msg:setattr(self,'current_animation',msg.data),10)
        self.node.create_subscription(Bool, '/voice/active', lambda msg:setattr(self,'voice_active_state',msg.data),10)
        autonomy_qos=QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=1,
                                durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.node.create_subscription(Bool, '/sim/autonomy_status',
                                      lambda msg:setattr(self,'autonomy_enabled',msg.data),
                                      autonomy_qos)
        self.node.create_subscription(Float32, '/voice/follow_direction', lambda msg:setattr(self,'voice_target',msg.data),10)
        self.node.create_subscription(JointState, '/joint_states', lambda msg:self.position(msg,self.joints),100)
        self.node.create_subscription(JointState, '/joint_states_target', lambda msg:self.position(msg,self.targets),100)

    def position(self, msg, output):
        if len(msg.name) != len(msg.position):
            self.errors.append('JointState names and positions differ')
        if len(set(msg.name)) != len(msg.name):
            self.errors.append('Duplicate joint names')
        for name,value in zip(msg.name,msg.position):
            if name not in ALL_JOINT_LIMITS:
                self.errors.append('Unknown joint '+name)
            if not math.isfinite(value):
                self.errors.append('Nonfinite joint '+name)
            if name in ALL_JOINT_LIMITS:
                lower,upper=ALL_JOINT_LIMITS[name]
                # MuJoCo's contact solver can leave measured qpos a few
                # milliradians beyond a hard stop; the production feedback
                # validator explicitly allows 0.02 rad. Command targets remain
                # strict so this tolerance only applies to physics feedback.
                tolerance = 0.02 if output is self.joints else 1e-6
                if not lower-tolerance<=value<=upper+tolerance:
                    self.errors.append(
                        f'Joint outside URDF limits {name}: {value:.9f} not in '
                        f'[{lower:.6f}, {upper:.6f}] ± {tolerance:.6f}'
                    )
        if output is self.joints: self.joint_names=list(msg.name)
        output.append((time.monotonic(),tuple(msg.position[:len(msg.name)])))

    def spin(self, seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            rclpy.spin_once(self.node,timeout_sec=min(.05,max(0,deadline-time.monotonic())))
        if self.errors:
            raise AssertionError(self.errors[-5:])

    def wait(self, predicate, timeout=10):
        deadline=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>deadline:
                raise TimeoutError('Expected ROS result/state was not observed')
            self.spin(.02)

    def future(self, future, timeout=10):
        self.wait(future.done,timeout)
        return future.result()

    def emit_direction(self, degrees, duration=.4):
        deadline=time.monotonic()+duration
        while time.monotonic()<deadline:
            self.direction.publish(Float32(data=degrees))
            self.spin(.05)

    def transition(self,state,priority=100,force=False,completion=False,requester='motion_scenarios'):
        request=RequestStateTransition.Request()
        request.requested_state=state;request.requesting_node=requester
        request.priority=priority;request.force=force;request.completion=completion
        response=self.future(self.states.call_async(request))
        if response.success:
            self.wait(lambda:self.current_state==response.current_state)
            self.spin(.3)  # State service replies before subscriber caches receive it.
        return response

    def goal(self,name,speed=2):
        feedback=[]
        goal=PlayAnimation.Goal()
        goal.animation_name=name;goal.speed_multiplier=float(speed)
        goal.allow_interruption=True;goal.use_hardware_feedback=False
        handle=self.future(self.actions.send_goal_async(goal,feedback_callback=lambda msg:feedback.append((time.monotonic(),msg.feedback))))
        if not handle.accepted:
            raise AssertionError('Action rejected '+name)
        return handle,feedback,handle.get_result_async()

    def record(self,name,**evidence):
        item=dict(scenario=name,passed=True,**evidence)
        self.results.append(item)
        print(json.dumps(item),flush=True)

    def prepare_deterministic_motion(self):
        """Pause idle activity and wait for an already running idle goal to stop."""
        self.wait(lambda:self.autonomy_enabled is not None,timeout=5)
        for _ in range(8):
            self.autonomy.publish(Bool(data=False))
            if self.autonomy_enabled is False:
                break
            self.spin(.1)
        self.wait(lambda:self.autonomy_enabled is False,timeout=3)
        self.voice_active.publish(Bool(data=False))
        self.spin(.3)
        self.transition('IDLE',force=True)
        self.wait(lambda:self.current_state=='IDLE' and self.current_animation in (None,''),timeout=12)
        self.spin(.3)

    def cancelled_dance(self):
        self.transition('IDLE',force=True)
        start=len(self.joints)
        handle,feedback,result=self.goal('dance',speed=1)
        self.wait(lambda:len(feedback)>=2 and len(self.joints)>start+5)
        self.spin(.35)
        cancel=self.future(handle.cancel_goal_async())
        assert cancel.goals_canceling,'Cancel request rejected'
        terminal=self.future(result)
        assert terminal.status==GoalStatus.STATUS_CANCELED,terminal
        assert terminal.result.final_state=='canceled'
        self.spin(.2) # Drain buffered target messages before stationary check.
        target_start=len(self.targets)
        self.spin(.4)
        targets=[p for _,p in self.targets[target_start:]]
        assert targets,'No target stream during stationary observation'
        assert max(max(abs(a-b) for a,b in zip(targets[0],p)) for p in targets)<1e-5,'Targets kept changing after cancellation'
        positions=[p for _,p in self.joints[start:]]
        assert max(max(abs(a-b) for a,b in zip(positions[0],p)) for p in positions)>.01,'Dance produced no joint motion'
        self.record('dance_cancel',status=terminal.status,feedback=len(feedback),joint_frames=len(positions),stationary_target_frames=len(targets))

    def preemption(self):
        old,oldfeedback,oldresult=self.goal('dance',speed=1)
        self.wait(lambda:len(oldfeedback)>=2)
        new,newfeedback,newresult=self.goal('nod',speed=2)
        first=self.future(oldresult)
        # The physics-backed nod can take ~32 wall seconds at its bounded
        # joint rates even with speed_multiplier=2; give it completion margin.
        second=self.future(newresult,timeout=180 if self.feasible_retiming else 60)
        assert first.result.final_state=='preempted' and not first.result.success
        assert first.status in (GoalStatus.STATUS_ABORTED,GoalStatus.STATUS_CANCELED)
        assert second.status==GoalStatus.STATUS_SUCCEEDED and second.result.success
        assert oldfeedback and newfeedback
        assert oldfeedback[-1][0]<=newfeedback[0][0]+.05,'Old and new action feedback overlapped after handoff'
        actual_publishers=self.node.get_publishers_info_by_topic('/joint_states')
        target_publishers=self.node.get_publishers_info_by_topic('/joint_states_target')
        assert len(actual_publishers)==1,'Multiple actual-joint writers'
        assert len(target_publishers)==1,'Multiple animation-target writers'
        self.record('action_preemption',old_status=first.status,old_final=first.result.final_state,new_status=second.status,
                    actual_writers=len(actual_publishers),target_writers=len(target_publishers))

    def directions(self):
        self.autonomy.publish(Bool(data=False));self.spin(.2)
        self.voice_active.publish(Bool(data=False));self.spin(.2)
        self.transition('IDLE',force=True)
        self.wait(lambda:self.current_state=='IDLE')
        # Start the translation check away from the cable stop: a direction
        # estimate on the opposite side is correctly clamped when yaw is
        # already at ±pi, which otherwise makes this displacement assertion
        # depend on whichever animation ran earlier in the suite.
        self.transition('USER_CONTROL',force=True)
        self.wait(lambda:self.current_state=='USER_CONTROL')
        self.spin(.2)
        centered=list(self.joints[-1][1]);centered[0]=0.0
        center=JointState();center.name=self.joint_names;center.position=centered
        self.manual.publish(center)
        self.wait(lambda:abs(self.joints[-1][1][0])<.03,timeout=10)
        self.transition('IDLE',force=True)
        self.wait(lambda:self.current_state=='IDLE')
        before=self.joints[-1][1][0]
        self.emit_direction(60.0)
        self.wait(lambda:self.current_state=='VOICE_FOLLOWING',timeout=5)
        self.wait(lambda:abs(self.joints[-1][1][0]-before)>.03,timeout=5)
        after=self.joints[-1][1][0]
        self.wait(lambda:self.current_state=='IDLE',timeout=7)
        self.record('audio_direction_to_motion_and_quiet',base_before=before,base_after=after,restored_state=self.current_state)

        # Exercise cable-safe wraparound through the same synthetic array,
        # shared DOA estimator and motion controller used by the dashboard.
        self.transition('USER_CONTROL',force=True)
        self.wait(lambda:self.current_state=='USER_CONTROL')
        self.spin(.2)
        pose=list(self.joints[-1][1]);pose[0]=math.radians(170.0)
        manual=JointState();manual.name=self.joint_names;manual.position=pose
        self.manual.publish(manual)
        self.wait(lambda:abs(self.joints[-1][1][0]-pose[0])<.03,timeout=10)
        self.transition('IDLE',force=True)
        self.wait(lambda:self.current_state=='IDLE')
        self.voice_target=None
        path_start=len(self.joints)
        cable_start=self.joints[-1][1][0]
        self.emit_direction(170.0)
        self.wait(lambda:self.voice_target is not None,timeout=5)
        self.wait(lambda:self.current_state=='VOICE_FOLLOWING',timeout=5)
        self.wait(lambda:abs(self.joints[-1][1][0]-cable_start)>.03,timeout=5)
        target=math.radians(self.voice_target)
        lower,upper=ROARM_M3_LIMITS[self.joint_names[0]]
        candidates=[]
        for turns in range(-2,3):
            equivalent=target+turns*2*math.pi
            candidates.append(min(upper,max(lower,equivalent)))
        expected=min(candidates,key=lambda angle:abs(angle-cable_start))
        self.wait(lambda:abs(self.joints[-1][1][0]-expected)<.05,timeout=8)
        path=[frame[1][0] for frame in self.joints[path_start:]]
        assert path and min(path)>math.radians(160), 'DOA crossed the cable-wrap seam instead of taking the short turn'
        assert max(path)<=upper+.02, 'DOA exceeded the vendor base-yaw limit'
        self.wait(lambda:self.current_state=='IDLE',timeout=7)
        self.record('doa_uses_shortest_cable_safe_turn',mic_angle=170.0,
                    target_robot_degrees=self.voice_target,
                    start_degrees=math.degrees(cable_start),
                    final_degrees=math.degrees(self.joints[-1][1][0]),
                    cable_limits_degrees=[math.degrees(lower),math.degrees(upper)],
                    quiet_state=self.current_state)

        # Speaking during an animation should steer only base yaw. The action
        # keeps FSM ownership and must complete normally after the DOA lease
        # expires instead of being canceled by VOICE_FOLLOWING preemption.
        self.transition('IDLE',force=True)
        self.wait(lambda:self.current_state=='IDLE')
        self.spin(.3)
        motion_start=len(self.joints)
        base_start=self.joints[-1][1][0]
        animation,animation_feedback,animation_result=self.goal('dance',speed=.5)
        # Inject immediately after action acceptance to cover the interval
        # where the animation intent is published but ANIMATING has not yet
        # reached this controller's state subscription.
        self.emit_direction(60.0,1.0)
        self.wait(lambda:self.voice_active_state,timeout=5)
        self.wait(lambda:self.current_state=='ANIMATING' and len(animation_feedback)>=2)
        self.wait(lambda:abs(self.joints[-1][1][0]-base_start)>.03,timeout=5)
        assert self.current_state=='ANIMATING',f'DOA interrupted animation: {self.current_state}'
        assert not animation_result.done(), 'DOA activity terminated the animation action'
        self.wait(lambda:not self.voice_active_state,timeout=5)
        assert self.current_state=='ANIMATING','Quiet DOA edge displaced animation state'
        assert not animation_result.done(), 'Animation did not continue through DOA quiet interval'
        overlay_frames=[positions for _,positions in self.joints[motion_start:]]
        assert any(max(abs(a-b) for a,b in zip(first[1:],frame[1:]))>.02
                   for first in overlay_frames[:1] for frame in overlay_frames[2:]), \
            'Animation joints stopped while base followed the speaker'
        animation_terminal=self.future(animation_result,timeout=90)
        assert animation_terminal.status==GoalStatus.STATUS_SUCCEEDED
        assert animation_terminal.result.success
        self.wait(lambda:self.current_state=='IDLE')
        self.record('doa_overlays_without_interrupting_animation',
                    activity_quieted=True,action_status=animation_terminal.status,
                    final_state=self.current_state,animation_joint_frames=len(overlay_frames))

        # Safety state must retain ownership despite new synthetic audio.
        response=self.transition('COLLISION_AVOIDING',priority=100,requester='behavior_coordinator')
        assert response.success,response.message
        self.wait(lambda:self.current_state=='COLLISION_AVOIDING')
        self.emit_direction(240.0,.3)
        self.spin(.8)
        assert self.current_state=='COLLISION_AVOIDING','Voice stole collision priority'
        denied=self.transition('VOICE_FOLLOWING',priority=75,requester='voice_following')
        assert not denied.success
        self.record('collision_rejects_voice',state=self.current_state,service_denied=True)
        self.voice_active.publish(Bool(data=False));self.spin(.1)
        self.transition('IDLE',force=True)
        self.autonomy.publish(Bool(data=True));self.spin(.2)

    def playlist(self,names):
        for name in names:
            self.transition('IDLE',force=True)
            self.wait(lambda:self.current_state=='IDLE')
            self.spin(.3)  # Allow action-server state subscription to observe reset.
            start=len(self.joints)
            expected=self.expected_durations.get(name,0)/2
            if self.feasible_retiming:
                from luxo_behaviors.animation_capabilities import ANIMATION_CLASSES
                from luxo_behaviors.joint_profiles import pose_to_animation_positions, animation_pose_for_profile
                from luxo_behaviors.trajectory_timing import retime_cubic_plan
                from luxo_behaviors.continuous_trajectory import ContinuousTrajectory
                plugin=ANIMATION_CLASSES[name](self.node)
                frames,durations=plugin.get_keyframes()
                initial=pose_to_animation_positions(self.joint_names,self.joints[-1][1])
                if getattr(plugin,'preserve_base_position',True):
                    frames=plugin.adjust_keyframes_to_current_base(frames,initial[0])
                frames=plugin.prepare_for_current_position(initial,frames)
                bounded=[]
                axes=min(5,len(self.joint_names))
                for frame in frames:
                    _,mapped=animation_pose_for_profile(frame,self.runtime_profile,
                        gripper_position=self.joints[-1][1][-1] if len(self.joint_names)==6 else 0.)
                    row=list(frame);row[:axes]=mapped[:axes];bounded.append(row)
                planner = ContinuousTrajectory if self.continuous_retiming else retime_cubic_plan
                timing = planner(initial,bounded,durations,speed_multiplier=2,
                    max_velocity=self.velocity_cap,max_acceleration=self.acceleration_cap,
                    axes=min(5,len(self.joint_names)))
                expected=sum(timing.durations if self.continuous_retiming else timing)
            _,feedback,result=self.goal(name,speed=2)
            terminal=self.future(result,timeout=max(60,expected+20))
            assert terminal.status==GoalStatus.STATUS_SUCCEEDED and terminal.result.success,(name,terminal)
            assert feedback,(name,'no action feedback')
            assert terminal.result.actual_duration>=expected*.75,(name,'Requested speed was applied more than once',terminal.result.actual_duration,expected)
            endpoint_error=None
            settled_velocity=None
            if self.feasible_retiming:
                assert self.targets and self.joints
                target=self.targets[-1][1]
                endpoint_error=max(abs(a-b) for a,b in zip(target,self.joints[-1][1]))
                assert endpoint_error <= .02,(name,'endpoint lag',endpoint_error)
                self.spin(.12)
                first,last=self.joints[-4],self.joints[-1]
                dt=last[0]-first[0]
                settled_velocity=max(abs(a-b)/dt for a,b in zip(first[1],last[1]))
                assert settled_velocity <= .02,(name,'unsettled endpoint',settled_velocity)
            self.record('animation_'+name,status=terminal.status,feedback=len(feedback),joint_frames=len(self.joints)-start,
                        duration=float(terminal.result.actual_duration),expected_duration_at_speed=expected,endpoint_error=endpoint_error,settled_velocity=settled_velocity,final_state=terminal.result.final_state)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--all-animations',action='store_true',help='Execute every manifest plugin in full at2x speed')
    parser.add_argument('--feasible-retiming',action='store_true',help='Require explicitly enabled runtime retiming and settled endpoints')
    parser.add_argument('--directions-only',action='store_true',help='Run DOA-to-motion, cable-wrap, quiet and safety-priority scenarios only')
    parser.add_argument('--output',default='/tmp/luxopi-motion-scenarios.json')
    args=parser.parse_args()
    rclpy.init(); suite=Scenarios()
    error=None
    if args.feasible_retiming:
        from rclpy.parameter_client import AsyncParameterClient
        parameters=AsyncParameterClient(suite.node,'animation_command')
        assert parameters.wait_for_services(timeout_sec=10)
        values=suite.future(parameters.get_parameters(['enable_feasible_retiming','max_joint_velocity','max_joint_acceleration','joint_profile','enable_continuous_retiming'])).values
        assert values[0].bool_value,'Runtime feasible retiming is not enabled'
        suite.feasible_retiming=True
        suite.velocity_cap=values[1].double_value
        suite.acceleration_cap=values[2].double_value
        suite.runtime_profile=values[3].string_value
        suite.continuous_retiming=values[4].bool_value
        assert suite.velocity_cap>0 and suite.acceleration_cap>0
    try:
        assert suite.actions.wait_for_server(timeout_sec=15),'Action server absent'
        assert suite.states.wait_for_service(timeout_sec=15),'State manager absent'
        suite.wait(lambda:bool(suite.joints) and suite.current_state is not None,timeout=15)
        suite.prepare_deterministic_motion()
        if args.directions_only:
            suite.directions()
        else:
            suite.cancelled_dance();suite.preemption();suite.directions()
        if args.all_animations:
            manifest=Path(__file__).resolve().parents[1]/'docs/feature-coverage.json'
            entries=json.loads(manifest.read_text())['inventory']['animations']
            suite.expected_durations={item['name']:item['duration_seconds'] for item in entries}
            names=[item['name'] for item in entries]
            suite.playlist(names)
    except Exception as exc:
        error=str(exc)
        raise
    finally:
        Path(args.output).write_text(json.dumps(dict(results=suite.results,error=error),indent=2)+'\n')
        if rclpy.ok():
            suite.autonomy.publish(Bool(data=True))
        suite.node.destroy_node();rclpy.shutdown()

if __name__=='__main__':
    main()
