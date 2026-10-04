"""Safe ROS simulation backend for the RoArm motion target interface."""

import math
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float32, String
from luxo_interfaces.srv import RequestStateTransition

from luxo_behaviors.joint_motion import (
    JointMotionLimiter,
    URDF_JOINT_LIMITS,
    ordered_joint_target,
)


JOINT_NAMES = tuple(URDF_JOINT_LIMITS)
VOICE_FOLLOW_STATES = {"IDLE", "VOICE_FOLLOWING", "ANIMATING", "PETTING", "EMOTION_REACTING"}


class SimMotionController(Node):
    """Single owner for simulated `/joint_states` output.

    Animation and other behaviors share the hardware target topic. Voice
    following temporarily overrides only the base joint after the centralized
    state manager grants the VOICE_FOLLOWING state.
    """

    def __init__(self):
        super().__init__("sim_motion_controller")
        self.declare_parameter("publish_rate", 50.0)
        self.declare_parameter("max_joint_velocity", 0.5)
        self.declare_parameter("max_joint_acceleration", 1.0)
        self.declare_parameter("voice_follow_priority", 75)
        self.publish_rate = float(self.get_parameter("publish_rate").value)
        self.voice_priority = int(self.get_parameter("voice_follow_priority").value)
        self.limiter = JointMotionLimiter(
            JOINT_NAMES,
            max_velocity=self.get_parameter("max_joint_velocity").value,
            max_acceleration=self.get_parameter("max_joint_acceleration").value,
        )
        self.animation_target = [0.0] * len(JOINT_NAMES)
        self.voice_direction = None
        self.voice_active = False
        self.current_state = "INITIALIZING"
        self.last_tick = time.monotonic()

        self.target_sub = self.create_subscription(
            JointState, "/joint_states_target", self.target_callback, 10
        )
        self.voice_direction_sub = self.create_subscription(
            Float32, "/voice/follow_direction", self.direction_callback, 10
        )
        self.voice_active_sub = self.create_subscription(
            Bool, "/voice/active", self.active_callback, 10
        )
        self.state_sub = self.create_subscription(
            String, "/luxo/current_state", self.state_callback, 10
        )
        self.states = self.create_client(
            RequestStateTransition, "/luxo/request_state_transition"
        )
        self.joint_pub = self.create_publisher(JointState, "/joint_states", 10)
        self.timer = self.create_timer(1.0 / self.publish_rate, self.publish_step)

    def target_callback(self, message):
        try:
            candidate = ordered_joint_target(message.name, message.position, JOINT_NAMES)
        except (TypeError, ValueError) as exc:
            self.get_logger().warning(f"Rejected invalid simulated joint target: {exc}")
            return
        # Commit only after all fields pass validation; a bad message must not
        # poison the timer's next limiter step.
        self.animation_target = candidate

    def direction_callback(self, message):
        angle = float(message.data)
        if math.isfinite(angle):
            self.voice_direction = angle

    def state_callback(self, message):
        self.current_state = message.data.upper()

    def active_callback(self, message):
        active = bool(message.data)
        if active == self.voice_active:
            return
        self.voice_active = active
        if active:
            self._request_voice_following()
        elif self.current_state == "VOICE_FOLLOWING":
            self._request_completion()

    def _request_voice_following(self):
        self._request_state("VOICE_FOLLOWING", completion=False)

    def _request_completion(self):
        self._request_state("IDLE", completion=True)

    def _request_state(self, requested_state, completion):
        if not self.states.service_is_ready():
            self.get_logger().warning("State manager unavailable; voice motion remains gated")
            return
        request = RequestStateTransition.Request()
        request.requested_state = requested_state
        request.requesting_node = "voice_following"
        request.priority = self.voice_priority
        request.force = False
        request.completion = completion
        future = self.states.call_async(request)

        def report_result(result_future):
            try:
                response = result_future.result()
                if not response.success:
                    self.get_logger().warning(
                        f"State transition to {requested_state} denied: {response.message}"
                    )
            except Exception as exc:
                self.get_logger().error(f"State transition request failed: {exc}")

        future.add_done_callback(report_result)

    def publish_step(self):
        now = time.monotonic()
        dt = min(0.1, max(0.001, now - self.last_tick))
        self.last_tick = now

        target = list(self.animation_target)
        may_follow = (
            self.voice_active
            and self.voice_direction is not None
            and self.current_state == "VOICE_FOLLOWING"
            and self.current_state in VOICE_FOLLOW_STATES
        )
        if may_follow:
            base = math.radians(self.voice_direction)
            lower, upper = URDF_JOINT_LIMITS[JOINT_NAMES[0]]
            target[0] = min(upper, max(lower, base))

        if self.current_state in {"ERROR", "SHUTDOWN"}:
            target = list(self.limiter.positions)

        positions = self.limiter.step(target, dt)
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(JOINT_NAMES)
        message.position = positions
        message.velocity = list(self.limiter.velocities)
        self.joint_pub.publish(message)


def main(args=None):
    rclpy.init(args=args)
    node = SimMotionController()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
