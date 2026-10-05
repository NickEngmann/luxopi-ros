#!/usr/bin/env python3
"""Raw ROS sensor → classifier → real state/action/motion consumers."""
import json,os,time
if os.environ.get('ROS_DOMAIN_ID')!='73' or os.environ.get('ROS_LOCALHOST_ONLY')!='1':
    raise SystemExit('Sensor scenarios require domain73 localhost-only')
import rclpy
from rclpy.node import Node
from std_msgs.msg import String,Float32,UInt8,Bool
from sensor_msgs.msg import JointState
from luxo_interfaces.srv import RequestStateTransition
from luxo_behaviors.joint_motion import URDF_JOINT_LIMITS


def main():
    rclpy.init();node=Node('sensor_scenarios')
    observed=dict(states=[],petting=[],animations=[],joints=[],gestures=[],front=[],left=[],right=[],motion=[])
    for message,topic,key in [(String,'/luxo/current_state','states'),(String,'/collision/petting_events','petting'),
        (String,'/roarm/current_animation','animations'),(String,'/gestures','gestures'),
        (Bool,'/head_collision_warning','front'),(Bool,'/left_collision_warning','left'),(Bool,'/right_collision_warning','right')]:
        node.create_subscription(message,topic,lambda msg,key=key:observed[key].append(msg.data),100)
    node.create_subscription(JointState,'/joint_states',lambda msg:observed['joints'].append(list(msg.position)),100)
    node.create_subscription(String,'/sim/motion_status',lambda msg:observed['motion'].append(json.loads(msg.data)),100)
    touch={side:node.create_publisher(UInt8,'/touch_sensors/head_'+side,10) for side in ('top','left','bottom','right')}
    distance=node.create_publisher(Float32,'/i2c/vl53_left/distance',10)
    gesture=node.create_publisher(String,'/i2c/apds9960/gesture',10)
    manual=node.create_publisher(JointState,'/sim/manual_joint_target',10)
    states=node.create_client(RequestStateTransition,'/luxo/request_state_transition')
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.02)
    def wait(predicate,timeout=10):
        end=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>end:raise AssertionError('Raw sensor consumer expectation timed out')
            spin(.02)
    def transition(state,priority=30):
        req=RequestStateTransition.Request();req.requested_state=state;req.requesting_node='sensor_scenarios';req.priority=priority;req.force=True
        future=states.call_async(req);wait(future.done);assert future.result().success
        wait(lambda:observed['states'][-1]==state);spin(.3)
    def report(scenario,**values):print(json.dumps(dict(scenario=scenario,passed=True,**values)),flush=True)
    try:
        assert states.wait_for_service(timeout_sec=10)
        wait(lambda:bool(observed['states']) and bool(observed['joints']))
        spin(6) # Actual classifier startup gate remains enabled.
        transition('IDLE')
        baseline=len(observed['joints'])
        touch['top'].publish(UInt8(data=50))
        wait(lambda:any(v.startswith('petting_started:') for v in observed['petting']))
        wait(lambda:'PETTING' in observed['states'] and 'folded_wiggle' in observed['animations'])
        wait(lambda:len(observed['joints'])>baseline+10)
        poses=observed['joints'][baseline:]
        wait(lambda:max(max(abs(a-b) for a,b in zip(observed['joints'][baseline],p)) for p in observed['joints'][baseline:])>.02)
        touch['top'].publish(UInt8(data=0))
        wait(lambda:any(v=='petting_stopped:0' for v in observed['petting']))
        wait(lambda:observed['states'][-1]=='IDLE',timeout=20)
        report('raw_head_touch_to_petting_action',classification=True,state='PETTING',animation='folded_wiggle',joint_frames=len(observed['joints'])-baseline)
        # Preserve legacy physical channel calibration: side FSR inputs are crossed.
        for side,output in [('left','right'),('bottom','front'),('right','left')]:
            transition('IDLE')
            start=len(observed[output])
            touch[side].publish(UInt8(data=50))
            wait(lambda:True in observed[output][start:],timeout=5)
            touch[side].publish(UInt8(data=0))
            wait(lambda:observed[output][-1] is False,timeout=5)
            report('raw_touch_'+side+'_collision',output=output,classified=True)
        transition('USER_CONTROL',priority=80)
        start=len(observed['joints'])
        manual.publish(JointState(name=list(URDF_JOINT_LIMITS),position=[.25,-.2,.1,.15]))
        wait(lambda:observed['motion'] and observed['motion'][-1].get('manual_override'))
        wait(lambda:max(abs(a-b) for a,b in zip(observed['joints'][start],observed['joints'][-1]))>.03)
        report('manual_input_actual_motion',state='USER_CONTROL',joint_frames=len(observed['joints'])-start)
        distance.publish(Float32(data=3.0));spin(.05);distance.publish(Float32(data=3.0))
        wait(lambda:observed['left'][-1] is True and observed['states'][-1]=='COLLISION_AVOIDING')
        spin(.1);start=len(observed['joints']);spin(.4)
        poses=observed['joints'][start:]
        assert poses and max(max(abs(a-b) for a,b in zip(poses[0],p)) for p in poses)<1e-5,'Raw collision did not freeze actual motion'
        distance.publish(Float32(data=100.0));spin(.05);distance.publish(Float32(data=100.0))
        wait(lambda:observed['left'][-1] is False and observed['states'][-1]!='COLLISION_AVOIDING')
        report('raw_distance_collision_motion_hold_and_recovery',held_joint_frames=len(poses),restored_state=observed['states'][-1])
        transition('IDLE')
        for value in ('left','right','up','down'):
            gesture.publish(String(data=value));spin(.1)
        wait(lambda:all(value in observed['gestures'] for value in ('left','right','up','down')),timeout=5)
        report('gesture_actual_passthrough',gestures=observed['gestures'],motion_mapping='not implemented, no claim')
    finally:
        touch['top'].publish(UInt8(data=0))
        node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
