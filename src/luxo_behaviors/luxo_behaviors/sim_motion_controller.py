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
    validate_feedback,
)
from luxo_behaviors.reactive_avoidance import ReactiveAvoidance
from luxo_behaviors.home_sequence import HomeSequence


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
        self.declare_parameter("required_sensor_directions", "")
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
        self.animation_intent_id = None
        self.animation_target_received_at = time.monotonic()
        self.manual_intent_id = None
        self.manual_target_received_at = None
        self.measured_positions = [0.0] * len(self.joint_names)
        self.measured_velocities = [0.0] * len(self.joint_names)
        self.feedback_received_at = None
        self.reactive_avoidance = ReactiveAvoidance(
            limits=self.joint_limits,
            required_directions=str(self.get_parameter("required_sensor_directions").value),
        )
        self._sensor_status_seen = set()
        self._sensor_status_at = {}
        self._sensor_status_payload = {}
        self._warning_started_at = {}
        self.avoidance_mode = "clear"
        self.avoidance_directions = []
        self.manual_target = None
        self.manual_target_rejected = ""
        self.voice_direction = None
        self.voice_active = False
        self.current_state = "INITIALIZING"
        self.collision_active = {"front": False, "left": False, "right": False}
        self.home_sequence = None
        self.home_received_at = None
        self.home_completion_pending = False
        self.home_warning_started = None
        self.blocked_animation_intent_id = None
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
        self.sensor_status_sub = self.create_subscription(
            String, "/collision/sensor_status", self.sensor_status_callback, 10
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
            was_direction_active = self.collision_active[direction]
            self.collision_active[direction] = bool(message.data)
            if message.data and not was_direction_active:
                now = time.monotonic()
                self._warning_started_at[direction] = now
                last_status = self._sensor_status_payload.get(direction)
                status_is_active_and_fresh = (
                    last_status is not None
                    and last_status["active"]
                    and now - self._sensor_status_at.get(direction, float("-inf"))
                    <= self.reactive_avoidance.stale_after
                )
                if not status_is_active_and_fresh:
                    # Bool warns immediately, but cannot set severity. Latch an
                    # unknown warning hold until the next atomic record arrives.
                    self.reactive_avoidance.update_sensor(
                        direction, True, now, severity="warning", valid=False
                    )
            else:
                if not message.data:
                    self._warning_started_at.pop(direction, None)
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
        intent = str(getattr(message.header, "frame_id", "") or "")
        intent = intent or self.animation_intent_id or "legacy-unknown-intent"
        if self.current_state == "RETURNING_HOME" or motion_is_frozen(self.current_state, ()):
            # A home plan owns the command writer. Retain the ignored old intent
            # so its heartbeat cannot resurrect after home completion.
            self.blocked_animation_intent_id = intent or self.animation_intent_id
            return
        if self.blocked_animation_intent_id and intent == self.blocked_animation_intent_id:
            return
        if intent and intent != self.blocked_animation_intent_id:
            self.blocked_animation_intent_id = None
        # Commit only after all fields pass validation; a bad message must not
        # poison the timer's next limiter step.
        self.animation_target = candidate
        intent_id = str(getattr(message.header, "frame_id", "") or "")
        if not intent_id:
            # Older publishers lack an intent ID. Accept their first target,
            # then treat subsequent unknown-ID updates as keepalives only.
            intent_id = self.animation_intent_id or "legacy-unknown-intent"
        if intent_id != self.animation_intent_id:
            self.animation_intent_id = intent_id
            self.animation_target_received_at = time.monotonic()

    def feedback_callback(self, message):
        """Store physics feedback separately from the persistent command trajectory."""
        try:
            measured, velocities = validate_feedback(
                message.name, message.position, message.velocity, self.profile
            )
        except (TypeError, ValueError) as exc:
            self.get_logger().warning(f"Rejected invalid physics feedback: {exc}")
            return
        self.measured_positions = measured
        if velocities is not None:
            self.measured_velocities = velocities
        self.feedback_received_at = time.monotonic()

    def sensor_status_callback(self, message):
        """Consume classifier state atomically so warning severity isn't lost."""
        try:
            payload = json.loads(message.data)
            direction = payload["direction"]
            now = time.monotonic()
            self.reactive_avoidance.update_sensor(
                direction,
                payload["active"],
                now,
                severity=payload["severity"],
                valid=payload["valid"],
            )
            self._sensor_status_seen.add(direction)
            self._sensor_status_at[direction] = now
            self._sensor_status_payload[direction] = payload
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.get_logger().warning(f"Rejected malformed collision sensor status: {exc}")

    def direction_callback(self, message):
        angle = float(message.data)
        if math.isfinite(angle):
            self.voice_direction = angle

    def state_callback(self, message):
        next_state = message.data.upper()
        if next_state != "USER_CONTROL":
            self.manual_target = None
        if next_state != self.current_state:
            if (self.current_state == "RETURNING_HOME"
                    or motion_is_frozen(self.current_state, ())):
                self.animation_target = list(self.measured_positions if not self.publish_feedback
                                             else self.limiter.positions)
                self.blocked_animation_intent_id = (self.animation_intent_id
                                                    or self.blocked_animation_intent_id)
                self.home_sequence = None
            if next_state == "RETURNING_HOME":
                current = list(self.measured_positions if not self.publish_feedback
                               else self.limiter.positions)
                self.home_received_at = time.monotonic()
                self.home_sequence = HomeSequence(self.profile, current, self.home_received_at)
                self.home_completion_pending = False
                self.home_warning_started = None
        self.current_state = next_state

    def manual_target_callback(self, message):
        """Accept bounded manual poses only while the FSM grants user control."""
        try:
            self.manual_target = validate_manual_pose(
                self.current_state, message.name, message.position, self.profile
            )
            intent_id = str(getattr(message.header, "frame_id", "") or "")
            if not intent_id:
                # Manual topic messages are explicit commands, not keepalives.
                intent_id = f"legacy-manual-{time.monotonic_ns()}"
            if intent_id != self.manual_intent_id:
                self.manual_intent_id = intent_id
                self.manual_target_received_at = time.monotonic()
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

    def _complete_home(self):
        if self.home_completion_pending or not self.states.service_is_ready():
            return
        self.home_completion_pending = True
        request = RequestStateTransition.Request()
        request.requested_state = "IDLE"
        request.requesting_node = "home_return"
        request.priority = 50
        request.force = False
        request.completion = True
        future = self.states.call_async(request)
        def report(result):
            try:
                response = result.result()
                if not response.success:
                    self.get_logger().warning(f"Home completion declined: {response.message}")
            except Exception as exc:
                self.get_logger().warning(f"Home completion failed: {exc}")
        future.add_done_callback(report)

    def publish_step(self):
        now = time.monotonic()
        dt = min(0.1, max(0.001, now - self.last_tick))
        self.last_tick = now

        target = list(self.animation_target)
        home = self.home_sequence if self.current_state == "RETURNING_HOME" else None
        if home is not None:
            target = home.target if home.status == 'running' else list(
                self.measured_positions if not self.publish_feedback else self.limiter.positions)
        manual_override = self.current_state == "USER_CONTROL" and self.manual_target is not None
        if manual_override:
            target = list(self.manual_target)
            target_received_at = self.manual_target_received_at
        else:
            target_received_at = self.home_received_at if home is not None else self.animation_target_received_at
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

        current = list(self.limiter.positions)
        if (self.feedback_received_at is not None
                and now - self.feedback_received_at <= 0.5):
            current = list(self.measured_positions)
        avoidance = self.reactive_avoidance.adjust_target(
            current,
            target,
            self.joint_names,
            now=now,
            target_received_at=target_received_at,
        )
        self.avoidance_mode = avoidance["mode"]
        self.avoidance_directions = avoidance["hazards"]

        emergency_hold = motion_is_frozen(self.current_state, ())
        avoidance_hold = self.avoidance_mode.startswith("hold_")
        hold_requested = emergency_hold or avoidance_hold
        safety_holds_motion = any(self.collision_active.values()) or bool(
            self.avoidance_directions
        )
        if emergency_hold:
            target = current
        else:
            target = avoidance["target"]

        if home is not None:
            feedback_fresh = self.publish_feedback or (self.feedback_received_at is not None
                                                       and now - self.feedback_received_at <= 0.3)
            if self.avoidance_mode == 'adjust':
                self.home_warning_started = (now if self.home_warning_started is None
                                             else self.home_warning_started)
                if now - self.home_warning_started >= 2.0:
                    home.interrupt('warning_requires_replan')
            else:
                self.home_warning_started = None
            if avoidance_hold:
                home.interrupt(self.avoidance_mode)
            elif not feedback_fresh:
                home.interrupt('stale_physics_feedback')
                target = current
            velocities = list(self.limiter.velocities if self.publish_feedback else self.measured_velocities)
            outcome = home.advance(current, velocities, now, fresh=feedback_fresh)
            if outcome != 'running':
                target = current
                self.animation_target = list(current)
                self._complete_home()

        positions = self.limiter.step(target, dt)
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(self.joint_names)
        message.position = positions
        message.velocity = list(self.limiter.velocities)
        self.joint_pub.publish(message)
        status = String()
        status.data = json.dumps({
            "state": self.current_state,
            "exclusive_motion_owner": "returning_home" if home is not None else "",
            "home_stage": home.stage + 1 if home is not None else None,
            "home_status": home.status if home is not None else "",
            "home_reason": home.reason if home is not None else "",
            "collision_active": any(self.collision_active.values()),
            "collision_directions": [
                direction for direction, active in self.collision_active.items() if active
            ],
            "avoidance_mode": self.avoidance_mode,
            "avoidance_directions": self.avoidance_directions,
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
