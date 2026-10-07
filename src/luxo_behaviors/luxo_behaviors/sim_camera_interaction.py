"""Detection-boundary simulator using the live camera reaction implementation."""
from collections import deque
import math
import os
import threading
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String,Float32,Bool
from luxo_interfaces.action import PlayAnimation
from .vision_reactions import VisionReactionMixin,EMOTION_ANIMATIONS


class SimCameraInteraction(VisionReactionMixin,Node):
    def __init__(self):
        super().__init__('sim_camera_interaction')
        self.emotion_to_animation={e:list(names) for e,names in EMOTION_ANIMATIONS.items()}
        self.declare_parameter('emotion_buffer_duration',2.0)
        self.declare_parameter('emotion_threshold',50.0)
        self.declare_parameter('emotion_cooldown',5.0)
        self.declare_parameter('post_animation_delay',3.0)
        for name in ('emotion_buffer_duration','emotion_threshold','emotion_cooldown','post_animation_delay'):
            setattr(self,name,float(self.get_parameter(name).value))
        self.verbose=False
        self.data_lock=threading.Lock()
        now=self.get_clock().now()
        self.last_emotion='neutral';self.last_animation_time=now;self.last_any_animation_end_time=now
        self.last_emotion_display_time=now;self.displayed_emotion=None
        self.current_animation_name=None;self.current_state='INITIALIZING';self._active_goal_handle=None
        self.recent_emotions=deque(maxlen=3);self.emotion_buffer=deque(maxlen=60);self.emotion_buffer_start_time=now
        self.detected_emotion=None;self.person_distance=None;self.person_present=False;self.last_detection=None
        self._animation_action_client=ActionClient(self,PlayAnimation,'play_animation')
        self.emotion_publisher=self.create_publisher(String,'/camera/emotion',10)
        self.distance_publisher=self.create_publisher(Float32,'/camera/person_distance',10)
        self.person_publisher=self.create_publisher(Bool,'/camera/person_present',10)
        self.create_subscription(String,'/sim/camera/emotion',self.emotion_input,10)
        self.create_subscription(Float32,'/sim/camera/person_distance',self.distance_input,10)
        self.create_subscription(Bool,'/sim/camera/person_present',self.person_input,10)
        self.create_subscription(String,'/luxo/current_state',lambda m:setattr(self,'current_state',m.data),10)
        self.create_subscription(String,'/roarm/current_animation',self.animation_input,10)
        self.create_timer(.1,self.process_detection)

    def emotion_input(self,msg):
        if msg.data not in self.emotion_to_animation:
            self.get_logger().warning('Invalid simulated emotion '+msg.data);return
        self.detected_emotion=msg.data;self.last_detection=self.get_clock().now()
        self.person_present=True
        self.person_publisher.publish(Bool(data=True))
        self.emotion_publisher.publish(msg)

    def distance_input(self,msg):
        if not math.isfinite(msg.data) or not .3<msg.data<4:
            self.get_logger().warning('Invalid simulated person distance');return
        self.person_distance=float(msg.data);self.last_detection=self.get_clock().now()
        self.person_present=True
        self.distance_publisher.publish(msg);self.person_publisher.publish(Bool(data=True))

    def person_input(self,msg):
        self.person_present=bool(msg.data)
        if not self.person_present:
            self.detected_emotion=None;self.person_distance=None;self.emotion_buffer.clear()
        else:
            self.last_detection=self.get_clock().now()
        self.person_publisher.publish(msg)

    def animation_input(self,msg):
        name=msg.data
        if not name:
            if self.current_animation_name:
                self.last_any_animation_end_time=self.get_clock().now()
            self.current_animation_name=None
        else:
            self.current_animation_name=name

    def process_detection(self):
        now=self.get_clock().now()
        if self.last_detection is not None and (now-self.last_detection).nanoseconds/1e9>3:
            if self.person_present:
                self.person_publisher.publish(Bool(data=False))
            self.person_present=False;self.detected_emotion=None;self.person_distance=None
        if self.person_present and self.detected_emotion:
            # One UI detection represents a brief stable detector observation;
            # synthesize frame cadence, not model inference, through shared buffer.
            self.emotion_buffer.append((self.detected_emotion,self.person_distance,now))
        self.process_emotion_buffer()


def main(args=None):
    if os.environ.get('ROS_DOMAIN_ID')!='73' or os.environ.get('ROS_LOCALHOST_ONLY')!='1':
        raise RuntimeError('Sim camera requires domain73 and localhost-only')
    rclpy.init(args=args);node=SimCameraInteraction()
    try:rclpy.spin(node)
    finally:node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
