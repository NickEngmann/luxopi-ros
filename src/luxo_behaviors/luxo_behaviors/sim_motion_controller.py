"""Safe ROS simulation backend for the RoArm motion target interface."""

import math
import json
import time
from collections import deque

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float32, String
from luxo_interfaces.srv import RequestStateTransition
from luxo_interfaces.msg import StateInfo

from luxo_behaviors.joint_motion import JointMotionLimiter, ordered_joint_target, clamp_joint_positions
from luxo_behaviors.joint_profiles import joint_profile
from luxo_behaviors.sim_motion_rules import (
    inactive_voice_reconcile_due,
    motion_is_frozen,
    nearest_cable_safe_angle,
    normalize_direction_degrees,
    validate_manual_pose,
    validate_feedback,
    voice_direction_is_fresh,
    voice_overlay_allowed,
    voice_state_request_allowed,
)
from luxo_behaviors.reactive_avoidance import ReactiveAvoidance
from luxo_behaviors.home_sequence import HomeSequence


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
        self.declare_parameter("voice_direction_max_age", 2.0)
        self.declare_parameter("required_sensor_directions", "")
        self.publish_rate = float(self.get_parameter("publish_rate").value)
        self.profile = str(self.get_parameter("joint_profile").value)
        self.joint_names, self.joint_limits = joint_profile(self.profile)
        self.publish_feedback = bool(self.get_parameter("publish_joint_states").value)
        self.command_topic = str(self.get_parameter("command_topic").value)
        self.voice_priority = int(self.get_parameter("voice_follow_priority").value)
        self.voice_direction_max_age = max(
            0.0, float(self.get_parameter("voice_direction_max_age").value)
        )
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
        self.stale_sensor_directions = []
        self.manual_target = None
        self.manual_target_rejected = ""
        self.voice_direction = None
        self.voice_direction_received_at = None
        self.voice_active = False
        self.voice_state_request_pending = False
        self.animation_active = False
        self.voice_inactive_since = None
        self.voice_idle_request_at = None
        self.current_state = "INITIALIZING"
        self.collision_active = {"front": False, "left": False, "right": False}
        self.home_sequence = None
        self.home_owner = None
        self.retired_home_owners = deque(maxlen=128)
        self.home_received_at = None
        self.home_completion_pending = False
        self.home_warning_started = None
        self.blocked_animation_intent_id = None
        self.hold_target = None
        self.hold_was_active = False
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
        self.state_info_sub = self.create_subscription(
            StateInfo, "/luxo/state_info", self.state_info_callback, 10
        )
        self.animation_status_sub = self.create_subscription(
            String, "/roarm/current_animation", self.animation_status_callback, 10
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
            # The legacy Bool only represents the hard proximity threshold.
            # Prefer a fresh atomic classifier record when available, because
            # its warning band can be active before the Bool becomes true.
            was_direction_active = self.collision_active[direction]
            status = self._sensor_status_payload.get(direction)
            status_is_fresh = (
                status is not None
                and time.monotonic() - self._sensor_status_at.get(direction, float("-inf"))
                <= self.reactive_avoidance.stale_after
                and status.get("valid") is True
            )
            hazard_active = bool(message.data)
            if status_is_fresh:
                if message.data and status.get("severity") == "safe":
                    # The Bool carries no severity. If it contradicts a fresh
                    # clear record, hold for an updated atomic record instead
                    # of misclassifying a warning threshold as imminent danger.
                    self.reactive_avoidance.update_sensor(
                        direction, True, time.monotonic(), severity="warning", valid=False
                    )
                self._sync_collision_state(time.monotonic())
            else:
                self._set_collision_active(direction, hazard_active)
            if message.data and not was_direction_active:
                now = time.monotonic()
                if not status_is_fresh:
                    # Bool warns immediately, but cannot set severity. Latch an
                    # unknown warning hold until the next atomic record arrives.
                    self.reactive_avoidance.update_sensor(
                        direction, True, now, severity="warning", valid=False
                    )
            if not hazard_active:
                self._warning_started_at.pop(direction, None)
        return receive

    def _set_collision_active(self, direction, active):
        was_active = any(self.collision_active.values())
        self.collision_active[direction] = bool(active)
        is_active = any(self.collision_active.values())
        if is_active and not was_active and self.current_state not in {
            "INITIALIZING", "COLLISION_AVOIDING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"
        }:
            self._request_state("COLLISION_AVOIDING", completion=False, safety=True)
        elif was_active and not is_active and self.current_state == "COLLISION_AVOIDING":
            self._request_state("IDLE", completion=True, safety=True)

    def _sync_collision_state(self, now):
        """Keep the FSM hazard lease aligned with the debounced sensor policy."""
        hazards, stale, _ = self.reactive_avoidance.snapshot(now)
        current = {
            direction: direction in hazards or direction in stale
            for direction in self.collision_active
        }
        was_active = any(self.collision_active.values())
        self.collision_active = current
        is_active = any(current.values())
        if is_active and not was_active and self.current_state not in {
            "INITIALIZING", "COLLISION_AVOIDING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"
        }:
            self._request_state("COLLISION_AVOIDING", completion=False, safety=True)
        elif was_active and not is_active and self.current_state == "COLLISION_AVOIDING":
            self._request_state("IDLE", completion=True, safety=True)

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
            if payload["valid"] is True:
                self._sync_collision_state(now)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.get_logger().warning(f"Rejected malformed collision sensor status: {exc}")

    def direction_callback(self, message):
        try:
            angle = normalize_direction_degrees(message.data)
        except (TypeError, ValueError, OverflowError) as exc:
            self.get_logger().warning(f"Ignoring invalid voice direction: {exc}")
            return
        self.voice_direction = angle
        self.voice_direction_received_at = time.monotonic()
        # /voice/active and /voice/follow_direction are independent topics;
        # the direction can arrive just after the activity edge.
        if (self.voice_active and not self.animation_active
                and voice_state_request_allowed(self.current_state)):
            self._request_voice_following()

    def animation_status_callback(self, message):
        # The action server announces its intent before asking the FSM for
        # ANIMATING. Honor that short startup window too, so simultaneous DOA
        # and animation requests cannot race for IDLE ownership.
        self.animation_active = bool(message.data.strip())

    def state_callback(self, message):
        next_state = message.data.upper()
        if next_state != "IDLE":
            # The FSM observation closes the request lease; repeated DOA
            # frames while its service call is in flight must not flood it.
            self.voice_state_request_pending = False
        if next_state == "VOICE_FOLLOWING" and not self.voice_active:
            # Completion may arrive while COLLISION_AVOIDING is still active;
            # releasing that lease can then restore an already-ended session.
            self.voice_inactive_since = time.monotonic()
        elif next_state != "VOICE_FOLLOWING":
            self.voice_inactive_since = None
            self.voice_idle_request_at = None
        if next_state != "USER_CONTROL":
            self.manual_target = None
        if next_state != self.current_state:
            if (self.current_state in {"RETURNING_HOME", "USER_CONTROL"}
                    or motion_is_frozen(self.current_state, ())):
                self.animation_target = list(self.measured_positions if not self.publish_feedback
                                             else self.limiter.positions)
                self.blocked_animation_intent_id = (self.animation_intent_id
                                                    or self.blocked_animation_intent_id)
                if self.home_sequence is not None:
                    self.home_sequence.interrupt('state_replaced')
                    if self.home_owner:
                        self.retired_home_owners.append(self.home_owner)
                    # Release the suspended home lease too, so clearing a
                    # collision cannot restore and automatically restart it.
                    self._complete_home()
                self.home_sequence = None
                self.home_owner = None
        self.current_state = next_state

    def state_info_callback(self, message):
        if message.current_state != self.current_state or self.current_state != "RETURNING_HOME":
            return
        owner = message.requested_by
        if not (owner == 'home_return' or owner.startswith('home_return:')):
            return  # A forced FSM test state alone is not an executable home request.
        if owner == self.home_owner or owner in self.retired_home_owners:
            return
        current = list(self.measured_positions if not self.publish_feedback else self.limiter.positions)
        self.home_received_at = time.monotonic()
        self.home_sequence = HomeSequence(self.profile, current, self.home_received_at)
        self.home_owner = owner
        self.home_completion_pending = False
        self.home_warning_started = None

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
            self.voice_inactive_since = None
            self.voice_idle_request_at = None
            if (not self.animation_active
                    and voice_state_request_allowed(self.current_state)
                    and voice_direction_is_fresh(
                        self.voice_direction, self.voice_direction_received_at,
                        time.monotonic(), max_age=self.voice_direction_max_age,
                    )):
                self._request_voice_following()
        elif self.current_state == "VOICE_FOLLOWING":
            self.voice_inactive_since = time.monotonic()
            self.voice_idle_request_at = self.voice_inactive_since
            self._request_completion()
        if not active:
            # Do not let a later activity edge reuse the prior speaker angle.
            self.voice_direction = None
            self.voice_direction_received_at = None

    def _request_voice_following(self):
        # An animation/petting/emotion owns the state machine while active.
        # DOA remains a base-yaw overlay in those states and must not preempt
        # the action merely because a voice activity edge arrived.
        if (not self.animation_active
                and voice_state_request_allowed(self.current_state)
                and not self.voice_state_request_pending):
            self.voice_state_request_pending = True
            self._request_state(
                "VOICE_FOLLOWING", completion=False, voice_request=True
            )

    def _request_completion(self):
        self._request_state("IDLE", completion=True)

    def _request_state(self, requested_state, completion, safety=False, voice_request=False):
        if not self.states.service_is_ready():
            self.get_logger().warning("State manager unavailable; voice motion remains gated")
            if voice_request:
                self.voice_state_request_pending = False
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
                    if voice_request:
                        self.voice_state_request_pending = False
                    self.get_logger().warning(
                        f"State transition to {requested_state} denied: {response.message}"
                    )
            except Exception as exc:
                if voice_request:
                    self.voice_state_request_pending = False
                self.get_logger().error(f"State transition request failed: {exc}")

        future.add_done_callback(report_result)

    def _complete_home(self):
        if self.home_completion_pending or not self.home_owner or not self.states.service_is_ready():
            return
        self.home_completion_pending = True
        request = RequestStateTransition.Request()
        request.requested_state = "IDLE"
        request.requesting_node = self.home_owner
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
        if self.current_state == "VOICE_FOLLOWING" and not self.voice_active:
            if self.voice_inactive_since is None:
                self.voice_inactive_since = now
            if inactive_voice_reconcile_due(
                self.current_state, self.voice_active, self.voice_inactive_since,
                self.voice_idle_request_at, now,
            ):
                self.voice_idle_request_at = now
                self._request_completion()
        dt = min(0.1, max(0.001, now - self.last_tick))
        self.last_tick = now

        target = list(self.animation_target)
        home = self.home_sequence if self.current_state == "RETURNING_HOME" else None
        if self.current_state == "RETURNING_HOME" and home is None:
            target = list(self.measured_positions if not self.publish_feedback else self.limiter.positions)
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
            and voice_direction_is_fresh(
                self.voice_direction, self.voice_direction_received_at, now,
                max_age=self.voice_direction_max_age,
            )
            and voice_overlay_allowed(self.current_state)
        )
        if may_follow:
            lower, upper = self.joint_limits[self.joint_names[0]]
            current_base = self.measured_positions[0] if self.publish_feedback else self.limiter.positions[0]
            target[0] = nearest_cable_safe_angle(
                current_base, math.radians(self.voice_direction), lower, upper
            )

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
        self.stale_sensor_directions = avoidance["stale"]

        emergency_hold = motion_is_frozen(self.current_state, ())
        avoidance_hold = self.avoidance_mode.startswith("hold_")
        hold_requested = emergency_hold or avoidance_hold
        if hold_requested and not self.hold_was_active:
            self.hold_target = list(current)
            if (self.publish_feedback and self.feedback_received_at is not None
                    and now - self.feedback_received_at <= 0.5):
                # Start the stop profile from the physical state. The command
                # limiter can lag MuJoCo feedback during normal tracking; using
                # its stale velocity here can accelerate the arm briefly in the
                # wrong direction as a hold begins.
                self.limiter.positions = list(current)
                self.limiter.velocities = [
                    max(-limit, min(limit, velocity))
                    for velocity, limit in zip(
                        self.measured_velocities, self.limiter.max_velocity
                    )
                ]
        elif not hold_requested:
            self.hold_target = None
        self.hold_was_active = hold_requested
        feedback_fresh = (self.publish_feedback and self.feedback_received_at is not None
                          and now - self.feedback_received_at <= 0.5)
        safety_holds_motion = any(self.collision_active.values()) or bool(
            self.avoidance_directions
        )
        if hold_requested:
            # Keep the first measured pose as a fixed stop target. Tracking the
            # current measured pose every tick lets the target follow a moving
            # arm and can add braking distance under physics feedback.
            target = list(self.hold_target or current)
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
        if feedback_fresh:
            # A low measured velocity alone can be a transient zero crossing
            # while the servo is still chasing its target. Require the
            # measured body, command trajectory, and limiter to have all
            # settled before exposing a frozen status.
            motion_frozen = hold_requested and (
                all(abs(value) < 1e-3 for value in self.measured_velocities)
                and all(abs(measured - commanded) < 2e-3
                        for measured, commanded in zip(self.measured_positions, positions))
                and all(abs(value) < 1e-3 for value in self.limiter.velocities)
            )
        else:
            motion_frozen = hold_requested and all(
                abs(velocity) < 1e-6 for velocity in self.limiter.velocities
            )
        status = String()
        status.data = json.dumps({
            "state": self.current_state,
            "exclusive_motion_owner": "returning_home" if self.current_state == "RETURNING_HOME" else "",
            "home_stage": home.stage + 1 if home is not None else None,
            "home_status": home.status if home is not None else "",
            "home_reason": home.reason if home is not None else "",
            "collision_active": any(self.collision_active.values()),
            "collision_directions": [
                direction for direction, active in self.collision_active.items() if active
            ],
            "avoidance_mode": self.avoidance_mode,
            "avoidance_directions": self.avoidance_directions,
            "stale": self.stale_sensor_directions,
            "voice_override": bool(may_follow and not safety_holds_motion),
            "manual_override": bool(manual_override and not hold_requested),
            "manual_target_rejected": self.manual_target_rejected,
            "motion_hold_requested": hold_requested,
            "motion_frozen": motion_frozen,
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
