"""Execute watchdog callbacks/checks without ROS or process recovery."""
import ast
import math
import threading
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

PATH = Path(__file__).parents[1]/'src/luxo_behaviors/luxo_behaviors/watchdog_node.py'

class Stamp:
    def __init__(self, seconds): self.nanoseconds = int(seconds*1e9)
    def __sub__(self, other): return Stamp((self.nanoseconds-other.nanoseconds)/1e9)

class Node:
    def __init__(self, name): self.params = {}; self.now = 0; self.subscriptions = []
    def declare_parameter(self, name, value): self.params[name] = value
    def get_parameter(self, name): return NS(value=self.params[name])
    def get_clock(self): return NS(now=lambda: Stamp(self.now))
    def get_logger(self): return NS(**{m: lambda *args: None for m in ['info','warning','error']})
    def create_subscription(self, cls, topic, callback, qos): self.subscriptions.append((cls, topic)); return None
    def create_publisher(self, *args): return NS(publish=lambda msg: None)
    def create_client(self, *args): return NS(service_is_ready=lambda: False)
    def create_timer(self, *args): return None


def node():
    cls = next(n for n in ast.parse(PATH.read_text()).body if isinstance(n, ast.ClassDef))
    ns = dict(Node=Node, threading=threading, math=math, time=time, datetime=datetime,
              StateInfo=type('StateInfo', (), {}), JointState=NS, String=NS,
              GoalStatusArray=NS, RequestStateTransition=NS)
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(PATH), 'exec'), ns)
    obj = ns['WatchdogNode'](); obj.monitor_only = True
    return obj


def test_contract_and_no_legacy_action_namespace():
    w = node()
    assert any(cls.__name__ == 'StateInfo' and t == '/luxo/state_info' for cls,t in w.subscriptions)
    assert any(t == '/play_animation/_action/status' for _,t in w.subscriptions)


def test_never_started_heartbeat_times_out_without_recovery():
    w = node(); w.now = 31; w.check_topics()
    assert w.state_failure_detected and w.joint_failure_detected
    assert not any(w.recovery_attempts.values())


def test_fresh_callbacks_clear_fault_and_four_joint_motion_is_tracked():
    w = node(); w.now = 31; w.check_topics()
    w.state_callback(NS(current_state='IDLE')); w.joint_callback(NS(position=[0.,0.,0.,0.]))
    assert not w.state_failure_detected and not w.joint_failure_detected
    assert w.last_joint_positions == [0.,0.,0.,0.]
    w.now = 32; w.joint_callback(NS(position=[.1,0.,0.,0.]))
    assert w.last_joint_change_time.nanoseconds == 32_000_000_000


def test_idle_and_collision_hold_are_not_stuck_or_silent_faults():
    for state in ['IDLE','COLLISION_AVOIDING','VOICE_FOLLOWING','USER_CONTROL']:
        w = node(); w.state_callback(NS(current_state=state)); w.joint_callback(NS(position=[0.]*4))
        w.animation_cmd_callback(NS(data='dance')); w.now = 1000
        w.state_callback(NS(current_state=state)); w.joint_callback(NS(position=[0.]*4))
        w.check_topics(); w.check_content(); w.check_correlations()
        assert not w.animation_failure_detected and not w.stuck_joints_detected
        assert not w.stuck_state_detected and not w.silent_failure_detected


def test_executing_action_status_timeout_then_terminal_is_not_active():
    w = node(); w.animation_status_callback(NS(status_list=[NS(status=2)]))
    w.now = 61; w.check_topics(); assert w.animation_failure_detected
    w.animation_status_callback(NS(status_list=[NS(status=4)])); assert not w.active_animation
