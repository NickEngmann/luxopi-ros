"""Silent synthetic array → shared GCC estimator → real voice motion topics."""
import json
import os
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32, String
from .direction_estimation import DirectionActivity, estimate_direction, robot_angle, synthesize_direction


class SimDirectionNode(Node):
    def __init__(self):
        super().__init__('sim_direction_node')
        self.declare_parameter('direction_offset', 250.0)
        self.declare_parameter('noise', 0.02)
        self.activity = DirectionActivity()
        self.direction = self.create_publisher(Float32, '/voice/direction', 10)
        self.follow = self.create_publisher(Float32, '/voice/follow_direction', 10)
        self.active = self.create_publisher(Bool, '/voice/active', 10)
        self.evidence = self.create_publisher(String, '/sim/direction_evidence', 10)
        self.create_subscription(Float32, '/sim/audio_direction', self.heard, 10)
        self.create_timer(0.05, self.quiet)

    def heard(self, message):
        angle = float(message.data)
        offset = float(self.get_parameter('direction_offset').value)
        noise = float(self.get_parameter('noise').value)
        frames = synthesize_direction(angle, direction_offset=offset, noise=noise)
        measured = estimate_direction(frames, direction_offset=offset)
        if measured is None:
            return
        # Live amplitude distance estimate maps a loud/peak fixture to .5m.
        target = robot_angle(measured, distance=0.5)
        self.direction.publish(Float32(data=target))
        self.follow.publish(Float32(data=target))
        self.active.publish(Bool(data=True))
        self.activity.heard(time.monotonic())
        self.evidence.publish(String(data=json.dumps(dict(
            requested_mic_angle=angle, measured_mic_angle=measured,
            robot_angle=target, channels=6, sample_rate=16000,
            method='shared GCC-PHAT on delayed PCM', noise=noise))))

    def quiet(self):
        if self.activity.expire(time.monotonic()):
            self.active.publish(Bool(data=False))


def main(args=None):
    if os.environ.get('ROS_DOMAIN_ID') != '73' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
        raise RuntimeError('Synthetic direction requires ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1')
    rclpy.init(args=args)
    node = SimDirectionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
