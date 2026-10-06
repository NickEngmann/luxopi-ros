#!/usr/bin/env python3
"""Observe actual state-manager lamp telemetry after real ROS control inputs."""
import json
import os
import time
if os.environ.get('ROS_DOMAIN_ID')!='73' or os.environ.get('ROS_LOCALHOST_ONLY')!='1':
    raise SystemExit('Lighting scenarios require ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1')
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool,String
from luxo_interfaces.srv import RequestStateTransition


def main():
    rclpy.init();node=Node('lighting_scenarios');latest={};results=[]
    def receive(msg):
        latest.clear();latest.update(json.loads(msg.data))
    node.create_subscription(String,'/luxo/light_state',receive,10)
    publishers={
        'light':node.create_publisher(Bool,'/luxo/light_control',10),
        'brightness':node.create_publisher(String,'/luxo/brightness_control',10),
        'color':node.create_publisher(String,'/luxo/color_control',10),
        'temperature':node.create_publisher(String,'/luxo/color_temp_control',10),
    }
    def wait(predicate,timeout=5):
        end=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>end:
                raise AssertionError(dict(reason='lamp telemetry expectation timed out',last=latest))
            rclpy.spin_once(node,timeout_sec=.05)
    def check(label,key,value,expected):
        old=latest.get('revision',-1)
        publishers[key].publish(value)
        wait(lambda:latest.get('revision',-1)>old and expected(latest))
        evidence=dict(scenario=label,passed=True,telemetry=dict(latest))
        results.append(evidence);print(json.dumps(evidence),flush=True)
    try:
        wait(lambda:bool(latest))
        assert latest.get('simulated') is True,'Physical lamp sink unexpectedly selected'
        states=node.create_client(RequestStateTransition,'/luxo/request_state_transition')
        assert states.wait_for_service(timeout_sec=5),'State manager service absent'
        request=RequestStateTransition.Request()
        request.requested_state='IDLE';request.requesting_node='lighting_scenarios';request.priority=100;request.force=True
        response=states.call_async(request)
        wait(response.done)
        assert response.result().success
        wait(lambda:latest.get('state')=='IDLE' and latest.get('effect')=='solid',timeout=8)
        check('lamp_on','light',Bool(data=True),lambda s:s['enabled']) if not latest.get('enabled') else None
        check('brightness_actual_consumer','brightness',String(data='brightness:0.25'),lambda s:s['brightness']==.25)
        for color,rgb in [('red',[255,0,0,0]),('blue',[0,0,255,0]),('green',[0,255,0,0])]:
            check('color_'+color,'color',String(data='color:'+color),lambda s,rgb=rgb:s['rgbw']==rgb)
        check('lamp_off','light',Bool(data=False),lambda s:not s['enabled'] and s['effect']=='off')
        check('lamp_on_again','light',Bool(data=True),lambda s:s['enabled'] and s['effect']!='off')
        # Explicitly seed the stored white before checking `color:white`:
        # prior browser/control suites may have changed the retained color temp.
        check('return_to_stored_white','color',String(data='color:white'),
              lambda s:len(s['rgbw'])==4 and s['rgbw'][:3]==[255,255,255])
        check('set_neutral_color_temperature','temperature',String(data='color_temp:0.5'),lambda s:s['rgbw']==[255,255,255,50])
        check('white_uses_stored_neutral_temperature','color',String(data='color:white'),lambda s:s['rgbw']==[255,255,255,50])
        check('warm_color_temperature','temperature',String(data='color_temp:1'),lambda s:s['rgbw']==[255,200,150,150])
        check('white_uses_stored_warm_temperature','color',String(data='color:white'),lambda s:s['rgbw']==[255,200,150,150])
        check('neutral_color_temperature','temperature',String(data='color_temp:0.5'),lambda s:s['rgbw']==[255,255,255,50])
        check('restore_brightness','brightness',String(data='brightness:0.5'),lambda s:s['brightness']==.5)
    finally:
        node.destroy_node();rclpy.shutdown()
    return 0

if __name__=='__main__':
    raise SystemExit(main())
