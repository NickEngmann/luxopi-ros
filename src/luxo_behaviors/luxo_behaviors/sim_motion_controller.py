"""Safe ROS simulation backend for the RoArm motion target interface."""

import math
import json
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float32, String
from luxo_interfaces.srv import RequestStateTransition

from luxo_behaviors.joint_motion import JointMotionLimiter, ordered_joint_target, clamp_joint_positions
from luxo_behaviors.joint_profiles import joint_profile
from luxo_behaviors.sim_motion_rules import (
    motion_is_frozen,
    validate_manual_pose,
)


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
        self.declare_parameter("joint_profile", "urdf4")
        self.declare_parameter("publish_joint_states", True)
        self.declare_parameter("command_topic", "/sim/bounded_joint_command")
        self.declare_parameter("max_joint_velocity", 0.5)
        self.declare_parameter("max_joint_acceleration", 1.0)
        self.declare_parameter("voice_follow_priority", 75)
        self.publish_rate = float(self.get_parameter("publish_rate").value)
        self.profile = str(self.get_parameter("joint_profile").value)
        self.joint_names, self.joint_limits = joint_profile(self.profile)
        self.publish_feedback = bool(self.get_parameter("publish_joint_states").value)
        self.command_topic = str(self.get_parameter("command_topic").value)
        self.voice_priority = int(self.get_parameter("voice_follow_priority").value)
        self.limiter = JointMotionLimiter(
            self.joint_names,
            limits=self.joint_limits,
            max_velocity=self.get_parameter("max_joint_velocity").value,
            max_acceleration=self.get_parameter("max_joint_acceleration").value,
        )
        self.animation_target = [0.0] * len(self.joint_names)
        self.manual_target = None
        self.manual_target_rejected = ""
        self.voice_direction = None
        self.voice_active = False
        self.current_state = "INITIALIZING"
        self.collision_active = {"front": False, "left": False, "right": False}
        self.last_tick = time.monotonic()

        self.target_sub = self.create_subscription(
            JointState, "/joint_states_target", self.target_callback, 10
        )
        self.feedback_sub = None
        if not self.publish_feedback:
            self.feedback_sub = self.create_subscription(
                JointState, "/joint_states", self.feedback_callback, 10
            )
        self.manual_target_sub = self.create_subscription(
            JointState, "/sim/manual_joint_target", self.manual_target_callback, 10
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
        self.collision_subscriptions = [
            self.create_subscription(
                Bool, topic, self._collision_callback(direction), 10
            )
            for direction, topic in (
                ("front", "/head_collision_warning"),
                ("left", "/left_collision_warning"),
                ("right", "/right_collision_warning"),
            )
        ]
        self.states = self.create_client(
            RequestStateTransition, "/luxo/request_state_transition"
        )
        output_topic = "/joint_states" if self.publish_feedback else self.command_topic
        self.joint_pub = self.create_publisher(JointState, output_topic, 10)
        self.motion_status = self.create_publisher(String, "/sim/motion_status", 10)
        self.timer = self.create_timer(1.0 / self.publish_rate, self.publish_step)

    def _collision_callback(self, direction):
        def receive(message):
            was_active = any(self.collision_active.values())
            self.collision_active[direction] = bool(message.data)
            active = any(self.collision_active.values())
            if active and not was_active and self.current_state not in {
                "INITIALIZING", "COLLISION_AVOIDING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"
            }:
                self._request_state("COLLISION_AVOIDING", completion=False, safety=True)
            elif was_active and not active and self.current_state == "COLLISION_AVOIDING":
                self._request_state("IDLE", completion=True, safety=True)
        return receive

    def target_callback(self, message):
        try:
            candidate = ordered_joint_target(message.name, message.position, self.joint_names)
        except (TypeError, ValueError) as exc:
            self.get_logger().warning(f"Rejected invalid simulated joint target: {exc}")
            return
        # Commit only after all fields pass validation; a bad message must not
        # poison the timer's next limiter step.
        self.animation_target = candidate

    def feedback_callback(self, message):
        """Use physics-owned feedback as the limiter's measured state."""
        try:
            measured = ordered_joint_target(message.name, message.position, self.joint_names)
            measured = clamp_joint_positions(self.joint_names, measured, self.joint_limits)
        except (TypeError, ValueError) as exc:
            self.get_logger().warning(f"Rejected invalid physics feedback: {exc}")
            return
        self.limiter.positions = measured
        # Velocity is computed by Gazebo but not relied on for a new target;
        # resetting avoids carrying simulated acceleration across feedback gaps.
        self.limiter.velocities = [0.0] * len(self.joint_names)

    def direction_callback(self, message):
        angle = float(message.data)
        if math.isfinite(angle):
            self.voice_direction = angle

    def state_callback(self, message):
        next_state = message.data.upper()
        if next_state != "USER_CONTROL":
            self.manual_target = None
        self.current_state = next_state

    def manual_target_callback(self, message):
        """Accept bounded manual poses only while the FSM grants user control."""
        try:
            self.manual_target = validate_manual_pose(
                self.current_state, message.name, message.position, self.profile
            )
            self.manual_target_rejected = ""
        except (TypeError, ValueError) as exc:
            self.manual_target_rejected = str(exc)
            self.get_logger().warning(f"Rejected simulated manual pose: {exc}")

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

    def _request_state(self, requested_state, completion, safety=False):
        if not self.states.service_is_ready():
            self.get_logger().warning("State manager unavailable; voice motion remains gated")
            return
        request = RequestStateTransition.Request()
        request.requested_state = requested_state
        request.requesting_node = "behavior_coordinator" if safety else "voice_following"
        request.priority = 100 if safety else self.voice_priority
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
        manual_override = self.current_state == "USER_CONTROL" and self.manual_target is not None
        if manual_override:
            target = list(self.manual_target)
        may_follow = (
            self.voice_active
            and self.voice_direction is not None
            and self.current_state == "VOICE_FOLLOWING"
            and self.current_state in VOICE_FOLLOW_STATES
        )
        if may_follow:
            base = math.radians(self.voice_direction)
            lower, upper = self.joint_limits[self.joint_names[0]]
            target[0] = min(upper, max(lower, base))

        safety_holds_motion = any(self.collision_active.values())
        hold_requested = motion_is_frozen(
            self.current_state, self.collision_active.values()
        )
        if hold_requested:
            target = list(self.limiter.positions)

        positions = self.limiter.step(target, dt)
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(JOINT_NAMES)
        message.position = positions
        message.velocity = list(self.limiter.velocities)
        self.joint_pub.publish(message)
        status = String()
        status.data = json.dumps({
            "state": self.current_state,
            "collision_active": any(self.collision_active.values()),
            "collision_directions": [
                direction for direction, active in self.collision_active.items() if active
            ],
            "voice_override": bool(may_follow and not safety_holds_motion),
            "manual_override": bool(manual_override and not hold_requested),
            "manual_target_rejected": self.manual_target_rejected,
            "motion_hold_requested": hold_requested,
            "motion_frozen": hold_requested and all(
                abs(velocity) < 1e-6 for velocity in self.limiter.velocities
            ),
            "positions": positions,
            "target": target,
        })
        self.motion_status.publish(status)


def main(args=None):
    rclpy.init(args=args)
    node = SimMotionController()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
