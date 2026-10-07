#!/usr/bin/env python3
"""Native isolated watchdog heartbeat fault/recovery test; no graph interruption."""
import json
import os
import subprocess
import signal
import time
if os.environ.get('ROS_DOMAIN_ID') != '73' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
    raise SystemExit('Requires ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1')
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import JointState
from luxo_interfaces.msg import StateInfo


def main():
    rclpy.init(); node = Node('watchdog_scenarios'); statuses = []; latest = []
    node.create_subscription(String,'/test/watchdog/status',lambda m:latest.append(m.data),10)
    state = node.create_publisher(StateInfo,'/test/watchdog/state',10)
    joints = node.create_publisher(JointState,'/test/watchdog/joints',10)
    command = ['ros2','run','luxo_behaviors','watchdog','--ros-args','-r','__node:=watchdog_fault_probe',
               '-r','/watchdog/status:=/test/watchdog/status','-p','state_topic:=/test/watchdog/state',
               '-p','joint_topic:=/test/watchdog/joints','-p','monitor_only:=true',
               '-p','state_timeout:=1.0','-p','joint_timeout:=1.0']
    process = subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    def spin(seconds):
        end = time.monotonic()+seconds
        while time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.05)
    def report(label):
        item=dict(scenario=label,passed=True,status=latest[-1]);statuses.append(item);print(json.dumps(item),flush=True)
    try:
        spin(7)
        assert latest and 'FAIL: STATE,JOINT' in latest[-1],latest
        assert 'Recoveries:' not in latest[-1],latest[-1]
        report('missing_heartbeats_detected_monitor_only')
        end=time.monotonic()+7
        while time.monotonic()<end:
            state.publish(StateInfo(current_state='IDLE'))
            joints.publish(JointState(name=['base_to_L1','L1_to_L2','L2_to_L3','L3_to_L4'],position=[0.]*4))
            spin(.1)
        assert 'FAIL:' not in latest[-1] and '(IDLE)' in latest[-1],latest[-1]
        report('fresh_four_joint_heartbeats_clear_fault')
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL);process.wait()
        node.destroy_node();rclpy.shutdown()

if __name__=='__main__': main()
