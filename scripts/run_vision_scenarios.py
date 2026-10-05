#!/usr/bin/env python3
"""Real ROS detection→shared reaction→animation/state/joint consumer evidence."""
import json,os,time
if os.environ.get('ROS_DOMAIN_ID')!='73' or os.environ.get('ROS_LOCALHOST_ONLY')!='1':
    raise SystemExit('Vision scenarios require domain73 localhost-only')
import rclpy
from rclpy.node import Node
from std_msgs.msg import String,Float32,Bool
from sensor_msgs.msg import JointState
from luxo_interfaces.srv import RequestStateTransition


def main():
    rclpy.init();node=Node('vision_scenarios')
    observed=dict(emotions=[],distances=[],presence=[],states=[],animations=[],joints=[])
    for message,topic,key in [(String,'/camera/emotion','emotions'),(Float32,'/camera/person_distance','distances'),
        (Bool,'/camera/person_present','presence'),(String,'/luxo/current_state','states'),
        (String,'/roarm/current_animation','animations')]:
        node.create_subscription(message,topic,lambda msg,key=key:observed[key].append(msg.data),100)
    node.create_subscription(JointState,'/joint_states',lambda msg:observed['joints'].append(list(msg.position)),100)
    emotion=node.create_publisher(String,'/sim/camera/emotion',10)
    distance=node.create_publisher(Float32,'/sim/camera/person_distance',10)
    person=node.create_publisher(Bool,'/sim/camera/person_present',10)
    states=node.create_client(RequestStateTransition,'/luxo/request_state_transition')
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.05)
    def wait(predicate,timeout=15):
        end=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>end:raise AssertionError('Vision consumer expectation timed out')
            spin(.05)
    try:
        assert states.wait_for_service(timeout_sec=10)
        req=RequestStateTransition.Request();req.requested_state='IDLE';req.requesting_node='vision_scenarios';req.priority=100;req.force=True
        future=states.call_async(req);wait(future.done);assert future.result().success
        # Preserve startup cooldown rather than speeding up an unrelated policy.
        spin(6)
        baseline=len(observed['joints'])
        for _ in range(20):
            distance.publish(Float32(data=1.2));emotion.publish(String(data='sad'));spin(.25)
        wait(lambda:'EMOTION_REACTING' in observed['states'] and 'sad' in observed['animations'])
        assert 'sad' in observed['emotions'] and 1.2 in observed['distances'] and True in observed['presence']
        poses=observed['joints'][baseline:]
        assert len(poses)>10
        assert max(max(abs(a-b) for a,b in zip(poses[0],pose)) for pose in poses)>.03,'No reaction joint motion'
        print(json.dumps(dict(scenario='detection_to_actual_emotion_reaction',passed=True,emotion='sad',
            state='EMOTION_REACTING',animation='sad',joint_frames=len(poses),person_distance=1.2)),flush=True)
        person.publish(Bool(data=False));wait(lambda:observed['presence'][-1] is False,timeout=5)
        print(json.dumps(dict(scenario='explicit_person_loss',passed=True)),flush=True)
        person.publish(Bool(data=True));wait(lambda:observed['presence'][-1] is True,timeout=5)
        wait(lambda:observed['presence'][-1] is False,timeout=5)
        print(json.dumps(dict(scenario='stale_person_presence_expires',passed=True)),flush=True)
    finally:
        node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
