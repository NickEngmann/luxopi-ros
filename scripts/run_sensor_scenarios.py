#!/usr/bin/env python3
"""Raw ROS sensor → classifier → real state/action/motion consumers."""
import json,os,time
if os.environ.get('ROS_DOMAIN_ID')!='73' or os.environ.get('ROS_LOCALHOST_ONLY')!='1':
    raise SystemExit('Sensor scenarios require domain73 localhost-only')
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile
from std_msgs.msg import String,Float32,UInt8,Bool,Int16
from sensor_msgs.msg import JointState
from luxo_interfaces.srv import RequestStateTransition
from luxo_behaviors.joint_motion import URDF_JOINT_LIMITS


def main():
    rclpy.init();node=Node('sensor_scenarios')
    observed=dict(states=[],petting=[],animations=[],joints=[],joint_names=[],gestures=[],front=[],left=[],right=[],motion=[],world_sensors=None)
    for message,topic,key in [(String,'/luxo/current_state','states'),(String,'/collision/petting_events','petting'),
        (String,'/roarm/current_animation','animations'),(String,'/gestures','gestures'),
        (Bool,'/head_collision_warning','front'),(Bool,'/left_collision_warning','left'),(Bool,'/right_collision_warning','right')]:
        node.create_subscription(message,topic,lambda msg,key=key:observed[key].append(msg.data),100)
    def joint_callback(msg):
        observed['joints'].append(list(msg.position));observed['joint_names']=list(msg.name)
    node.create_subscription(JointState,'/joint_states',joint_callback,100)
    node.create_subscription(String,'/sim/motion_status',lambda msg:observed['motion'].append(json.loads(msg.data)),100)
    node.create_subscription(String,'/sim/world_sensor_status',
                             lambda msg:observed.update(world_sensors=json.loads(msg.data)),10)
    touch={side:node.create_publisher(UInt8,'/touch_sensors/head_'+side,10) for side in ('top','left','bottom','right')}
    distance=node.create_publisher(Float32,'/i2c/vl53_left/distance',10)
    right_distance=node.create_publisher(Float32,'/i2c/vl53_right/distance',10)
    proximity=node.create_publisher(Int16,'/i2c/apds9960/proximity',10)
    raw=dict(left=100.,right=100.,touch={s:0 for s in touch},sent=0.)
    def send_raw():
        distance.publish(Float32(data=raw['left']));right_distance.publish(Float32(data=raw['right']))
        proximity.publish(Int16(data=0))
        for side,publisher in touch.items():publisher.publish(UInt8(data=raw['touch'][side]))
        raw['sent']=time.monotonic()
    def set_touch(side,value):
        raw['touch'][side]=value;touch[side].publish(UInt8(data=value))
    gesture=node.create_publisher(String,'/i2c/apds9960/gesture',10)
    manual=node.create_publisher(JointState,'/sim/manual_joint_target',10)
    autonomy=node.create_publisher(Bool,'/sim/autonomy_enabled',10)
    sensor_faults=node.create_publisher(String,'/sim/sensor_faults',10)
    autonomy_state={'enabled':None}
    autonomy_qos=QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=1,
                            durability=DurabilityPolicy.TRANSIENT_LOCAL)
    node.create_subscription(Bool,'/sim/autonomy_status',
                             lambda msg:autonomy_state.update(enabled=msg.data),autonomy_qos)
    states=node.create_client(RequestStateTransition,'/luxo/request_state_transition')
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if time.monotonic()-raw['sent']>.08:send_raw()
            rclpy.spin_once(node,timeout_sec=.02)
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
        wait(lambda:autonomy_state['enabled'] is not None,timeout=5)
        for _ in range(8):
            autonomy.publish(Bool(data=False))
            if autonomy_state['enabled'] is False:break
            spin(.1)
        wait(lambda:autonomy_state['enabled'] is False,timeout=3)
        # Isolate raw production-topic injection from sim_world_sensors, which
        # otherwise publishes geometric ranges to these same optical topics.
        wait(lambda:observed['world_sensors'] is not None,timeout=5)
        sensor_faults.publish(String(data=json.dumps(
            {'front':True,'left':True,'right':True},separators=(',',':'))))
        wait(lambda:observed['world_sensors'].get('sensor_faults')==
             {'front':True,'left':True,'right':True},timeout=5)
        spin(.2)
        spin(6) # Actual classifier startup gate remains enabled.
        transition('IDLE')
        baseline=len(observed['joints'])
        set_touch('top',50)
        wait(lambda:any(v.startswith('petting_started:') for v in observed['petting']))
        wait(lambda:'PETTING' in observed['states'] and 'folded_wiggle' in observed['animations'])
        wait(lambda:len(observed['joints'])>baseline+10)
        poses=observed['joints'][baseline:]
        wait(lambda:max(max(abs(a-b) for a,b in zip(observed['joints'][baseline],p)) for p in observed['joints'][baseline:])>.02)
        set_touch('top',0)
        wait(lambda:any(v=='petting_stopped:0' for v in observed['petting']))
        wait(lambda:observed['states'][-1]=='IDLE',timeout=20)
        report('raw_head_touch_to_petting_action',classification=True,state='PETTING',animation='folded_wiggle',joint_frames=len(observed['joints'])-baseline)
        # Preserve legacy physical channel calibration: side FSR inputs are crossed.
        for side,output in [('left','right'),('bottom','front'),('right','left')]:
            transition('IDLE')
            start=len(observed[output])
            set_touch(side,50)
            wait(lambda:True in observed[output][start:],timeout=5)
            set_touch(side,0)
            wait(lambda:observed[output][-1] is False,timeout=5)
            report('raw_touch_'+side+'_collision',output=output,classified=True)
        spin(.4) # Fresh safe ranges+FSR and clear dwell; next target is a replan.
        transition('USER_CONTROL',priority=80)
        start=len(observed['joints'])
        names=observed['joint_names']
        desired=list(observed['joints'][-1])
        assert len(names)==len(desired) and len(names) in (4,6),names
        desired[:4]=[.25,-.2,.1,.15]
        manual.publish(JointState(name=names,position=desired))
        wait(lambda:observed['motion'] and observed['motion'][-1].get('manual_override'))
        wait(lambda:max(abs(a-b) for a,b in zip(observed['joints'][start],observed['joints'][-1]))>.03)
        report('manual_input_actual_motion',state='USER_CONTROL',joint_frames=len(observed['joints'])-start)
        collision_start_pose=observed['joints'][-1][:]
        start=len(observed['joints'])
        raw['left']=3.;send_raw();spin(.12)
        wait(lambda:observed['left'][-1] is True and observed['states'][-1]=='COLLISION_AVOIDING')
        wait(lambda:observed['motion'][-1].get('motion_frozen'),timeout=3)
        spin(1.0)
        poses=observed['joints'][start:]
        assert len(poses)>=10,'No measured joint feedback during collision braking'
        stopping_excursion=max(max(abs(a-b) for a,b in zip(collision_start_pose,p)) for p in poses)
        settled=poses[-10:]
        settled_drift=max(max(abs(a-b) for a,b in zip(settled[0],p)) for p in settled)
        assert stopping_excursion<.25, f'Collision stopping excursion exceeded bounded envelope: {stopping_excursion:.4f} rad'
        assert settled_drift<.001, f'Joint feedback did not settle under collision hold: {settled_drift:.6f} rad'
        raw['left']=100.;send_raw();spin(.4)
        wait(lambda:observed['left'][-1] is False and observed['states'][-1]!='COLLISION_AVOIDING')
        held_after_clear=observed['joints'][-1][:]
        spin(.2)
        assert max(abs(a-b) for a,b in zip(held_after_clear,observed['joints'][-1]))<1e-5,'Clear replayed stale target'
        replan=held_after_clear[:];replan[0]+=.08
        manual.publish(JointState(name=names,position=replan))
        wait(lambda:max(abs(a-b) for a,b in zip(held_after_clear,observed['joints'][-1]))>.01)
        report('raw_distance_collision_motion_hold_and_recovery',held_joint_frames=len(poses),
               stopping_excursion_radians=round(stopping_excursion,5),
               settled_drift_radians=round(settled_drift,6),restored_state=observed['states'][-1])
        # Passthrough is independent of the new reaction consumer. Keep user
        # control leased here so this raw-input suite does not leave a gesture
        # animation running into the next sequential voice suite.
        transition('USER_CONTROL', priority=80)
        for value in ('left','right','up','down'):
            gesture.publish(String(data=value));spin(.1)
        wait(lambda:all(value in observed['gestures'] for value in ('left','right','up','down')),timeout=5)
        report('gesture_actual_passthrough',gestures=observed['gestures'],
               motion_mapping='guarded during USER_CONTROL; action consumer validated separately')
        transition('IDLE')
    finally:
        raw['left']=100.;raw['right']=100.
        for side in raw['touch']:raw['touch'][side]=0
        send_raw();spin(.5)
        sensor_faults.publish(String(data=json.dumps(
            {'front':False,'left':False,'right':False},separators=(',',':'))))
        spin(.1)
        autonomy.publish(Bool(data=True));spin(.1)
        node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
