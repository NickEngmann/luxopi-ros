#!/usr/bin/env python3
"""Native voice presentation/collision/session lifecycle, no audio playback."""
import json,os,time
if os.environ.get('ROS_DOMAIN_ID')!='73' or os.environ.get('ROS_LOCALHOST_ONLY')!='1':
    raise SystemExit('Requires domain73 localhost-only')
import rclpy
from rclpy.node import Node
from std_msgs.msg import String,Float32
from action_msgs.msg import GoalStatusArray
from sensor_msgs.msg import JointState
from luxo_interfaces.srv import RequestStateTransition

def main():
    rclpy.init();node=Node('voice_cue_scenarios');seen=dict(states=[],animations=[],joints=[],statuses={},interaction=[])
    for topic,key in [('/luxo/current_state','states'),('/roarm/current_animation','animations')]:
        node.create_subscription(String,topic,lambda m,key=key:seen[key].append(m.data),100)
    node.create_subscription(JointState,'/joint_states',lambda m:seen['joints'].append(list(m.position)),100)
    node.create_subscription(String,'/sim/interaction_status',lambda m:seen['interaction'].append(json.loads(m.data)),100)
    def statuses(msg):
        for status in msg.status_list:seen['statuses'][bytes(status.goal_info.goal_id.uuid).hex()]=status.status
    node.create_subscription(GoalStatusArray,'/play_animation/_action/status',statuses,100)
    voice=node.create_publisher(String,'/voice/status',10);transcript=node.create_publisher(String,'/voice/transcript',10)
    command=node.create_publisher(String,'/roarm/animation_command',10)
    collision=node.create_publisher(Float32,'/i2c/vl53_left/distance',10)
    states=node.create_client(RequestStateTransition,'/luxo/request_state_transition')
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.02)
    def wait(predicate,timeout=12):
        end=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>end:raise AssertionError(dict(reason='voice cue expectation timed out',states=seen['states'][-15:],animations=seen['animations'][-20:],statuses=seen['statuses']))
            spin(.02)
    def emit(status):voice.publish(String(data=status))
    def cue(name,start=0):wait(lambda:name in seen['animations'][start:])
    def idle():
        emit('idle');wait(lambda:seen['states'][-1]=='IDLE' and seen['animations'][-1]=='',timeout=20);spin(.3)
    def report(label,**evidence):print(json.dumps(dict(scenario=label,passed=True,**evidence)),flush=True)
    try:
        assert states.wait_for_service(timeout_sec=10);wait(lambda:seen['states'] and seen['joints'])
        req=RequestStateTransition.Request(requested_state='IDLE',requesting_node='voice_cue_scenarios',priority=100,force=True)
        future=states.call_async(req);wait(future.done);assert future.result().success;spin(.5)
        start=len(seen['animations']);emit('listening');cue('listening',start)
        wait(lambda:seen['states'][-1]=='USER_CONTROL');state_start=len(seen['states'])
        transcript.publish(String(data='hello'));cue('acknowledge',start)
        emit('thinking');cue('thinking',start);emit('speaking');cue('speaking',start)
        assert 'IDLE' not in seen['states'][state_start:]
        emit('idle');cue('settle',start);wait(lambda:seen['states'][-1]=='IDLE' and seen['animations'][-1]=='',timeout=20)
        order=[]
        for name in seen['animations'][start:]:
            if name and (not order or name!=order[-1]):order.append(name)
        assert order[:5]==['listening','acknowledge','thinking','speaking','settle'],order
        report('ordered_voice_cues_and_explicit_idle',order=order)
        start=len(seen['animations']);emit('thinking');cue('thinking',start);spin(.1)
        wait(lambda:any(v==2 for v in seen['statuses'].values()))
        old_goals={k for k,v in seen['statuses'].items() if v==2}
        assert len(old_goals)==1,old_goals
        state_start=len(seen['states']);baseline=len(seen['joints']);command.publish(String(data='nod'));cue('nod',start)
        wait(lambda:all(seen['statuses'].get(k) in (5,6) for k in old_goals))
        spin(.3)  # Allow old finally/callback effects and fresh state/animation telemetry.
        assert seen['animations'][-1]=='nod' and seen['states'][-1]=='USER_CONTROL', {'states':seen['states'][-10:],'animations':seen['animations'][-10:]}
        new_goals={k for k,v in seen['statuses'].items() if v==2 and k not in old_goals}
        assert len(new_goals)==1,new_goals
        wait(lambda:len(seen['joints'])>baseline+5 and max(max(abs(a-b) for a,b in zip(seen['joints'][baseline],p)) for p in seen['joints'][baseline:])>.02)
        wait(lambda:all(seen['statuses'].get(k)==4 for k in new_goals),timeout=20)
        wait(lambda:seen['animations'][-1]=='',timeout=20)
        assert seen['states'][-1]=='USER_CONTROL' and 'IDLE' not in seen['states'][state_start:]
        report('command_preempts_thinking_cue',joint_frames=len(seen['joints'])-baseline,old_terminal_statuses={k:seen['statuses'][k] for k in old_goals},replacement_terminal_statuses={k:seen['statuses'][k] for k in new_goals},replacement_owned_during_old_completion=True)
        idle()
        start=len(seen['animations']);emit('listening');cue('listening',start)
        emit('idle');wait(lambda:seen['states'][-1]=='IDLE')
        # Observe the intervening IDLE edge so an old USER_CONTROL cache cannot
        # masquerade as the newly granted session. Prior cue is still in flight.
        interaction_start=len(seen['interaction']);emit('listening')
        wait(lambda:seen['states'][-1]=='USER_CONTROL' and any(s.get('voice_status')=='listening' and s.get('voice_session_owned') for s in seen['interaction'][interaction_start:]))
        state_start=len(seen['states']);spin(2)
        assert seen['states'][-1]=='USER_CONTROL' and 'IDLE' not in seen['states'][state_start:], {'states':seen['states'][state_start:], 'interaction':seen['interaction'][-10:]}
        report('stale_cue_completion_preserves_new_session',state='USER_CONTROL')
        idle()
        start=len(seen['animations']);emit('thinking');cue('thinking',start)
        spin(.1)  # Drain the previous listening goal's terminal status before taking its successor.
        wait(lambda:any(v==2 for v in seen['statuses'].values()))
        active={k for k,v in seen['statuses'].items() if v==2}
        assert len(active)==1, {'executing_goals':active,'statuses':seen['statuses']}
        collision.publish(Float32(data=3.0));spin(.05);collision.publish(Float32(data=3.0));wait(lambda:seen['states'][-1]=='COLLISION_AVOIDING')
        wait(lambda:any(seen['statuses'].get(k) in (5,6) for k in active))
        report('collision_preempts_noninterrupting_visual_cue',terminal_statuses={k:seen['statuses'].get(k) for k in active})
        emit('idle');collision.publish(Float32(data=100.0));spin(.05);collision.publish(Float32(data=100.0));wait(lambda:seen['states'][-1]=='IDLE',timeout=20)
    finally:
        emit('idle');collision.publish(Float32(data=100.0));spin(.05);collision.publish(Float32(data=100.0));node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
