#!/usr/bin/env python3
"""Actual voice ownership → legacy command → action/motion → voice idle."""
import json,os,time
if os.environ.get('ROS_DOMAIN_ID')!='73' or os.environ.get('ROS_LOCALHOST_ONLY')!='1':
    raise SystemExit('Requires domain73 localhost-only')
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import JointState
from luxo_interfaces.srv import RequestStateTransition

def main():
    rclpy.init();node=Node('voice_motion_scenarios');seen=dict(states=[],joints=[],animations=[])
    for msg,topic,key in [(String,'/luxo/current_state','states'),(String,'/roarm/current_animation','animations')]:
        node.create_subscription(msg,topic,lambda m,key=key:seen[key].append(m.data),100)
    node.create_subscription(JointState,'/joint_states',lambda m:seen['joints'].append(list(m.position)),100)
    voice=node.create_publisher(String,'/voice/status',10)
    command=node.create_publisher(String,'/roarm/animation_command',10)
    state=node.create_client(RequestStateTransition,'/luxo/request_state_transition')
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.02)
    def wait(predicate,timeout=10):
        end=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>end:raise AssertionError(dict(reason='voice motion timeout',states=seen['states'][-10:],animations=seen['animations'][-10:]))
            spin(.02)
    try:
        assert state.wait_for_service(timeout_sec=10)
        wait(lambda:seen['states'] and seen['joints']);spin(.3)
        req=RequestStateTransition.Request(requested_state='IDLE',requesting_node='voice_motion_scenarios',priority=100,force=True)
        future=state.call_async(req);wait(future.done);assert future.result().success
        wait(lambda:seen['states'][-1]=='IDLE');spin(.3)
        voice.publish(String(data='listening'));wait(lambda:seen['states'][-1]=='USER_CONTROL');spin(.3)
        base=len(seen['joints']);state_start=len(seen['states'])
        command.publish(String(data='nod'))
        wait(lambda:'nod' in seen['animations'])
        wait(lambda:len(seen['joints'])>base+5 and max(max(abs(a-b) for a,b in zip(seen['joints'][base],p)) for p in seen['joints'][base:])>.02)
        wait(lambda:seen['animations'][-1]=='',timeout=180) # Complete feasible trajectory, not a release-latency bound.
        assert seen['states'][-1]=='USER_CONTROL',seen['states'][-10:]
        assert 'IDLE' not in seen['states'][state_start:],seen['states'][state_start:]
        print(json.dumps(dict(scenario='voice_user_control_legacy_animation_real_motion',passed=True,joint_frames=len(seen['joints'])-base,state='USER_CONTROL')),flush=True)
        voice.publish(String(data='idle'));wait(lambda:seen['states'][-1]=='IDLE')
        print(json.dumps(dict(scenario='voice_idle_releases_ownership',passed=True,state='IDLE')),flush=True)
    finally:
        voice.publish(String(data='idle'));node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
