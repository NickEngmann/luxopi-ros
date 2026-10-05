"""Simulation-only consumer for voice-session and touch/petting events."""

import json
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String
from luxo_interfaces.action import PlayAnimation
from luxo_interfaces.srv import RequestStateTransition
from luxo_behaviors.sim_interaction_rules import parse_petting_event


PETTING_ANIMATION = "folded_wiggle"
ACTIVE_VOICE_STATUSES = {"listening", "thinking", "speaking"}
SAFETY_STATES = {"COLLISION_AVOIDING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"}


class SimInteractionAdapter(Node):
    """Run the existing voice-session and petting state paths without hardware."""

    def __init__(self):
        super().__init__("sim_interaction_adapter")
        self.declare_parameter("petting_timeout", 5.0)
        self.petting_timeout = float(self.get_parameter("petting_timeout").value)
        self.current_state = "INITIALIZING"
        self.voice_status = "idle"
        self.voice_session_owned = False
        self.voice_transition_pending = False
        self.petting_active = False
        self.petting_transition_pending = False
        self.petting_session_owned = False
        self.last_petting_event = None
        self.petting_goal_handle = None
        self.petting_animation_active = False
        self.last_error = ""

        self.state_client = self.create_client(
            RequestStateTransition, "/luxo/request_state_transition"
        )
        self.animation_client = ActionClient(self, PlayAnimation, "play_animation")
        self.create_subscription(String, "/luxo/current_state", self._state_cb, 10)
        self.create_subscription(String, "/voice/status", self._voice_status_cb, 10)
        self.create_subscription(
            String, "/collision/petting_events", self._petting_cb, 10
        )
        self.status_publisher = self.create_publisher(
            String, "/sim/interaction_status", 10
        )
        self.create_timer(0.1, self._tick)

    def _state_cb(self, message):
        next_state = message.data.upper()
        previous = self.current_state
        self.current_state = next_state
        if (previous == "PETTING" and next_state != "PETTING"
                and self.petting_animation_active and self.petting_goal_handle):
            self.petting_goal_handle.cancel_goal_async()
        if next_state == "IDLE" and self.voice_status == "idle":
            self.voice_session_owned = False

    def _voice_status_cb(self, message):
        status = message.data.strip().lower()
        if status not in ACTIVE_VOICE_STATUSES | {"idle", "error"}:
            self.last_error = f"ignored unknown voice status: {status[:80]}"
            self._publish_status()
            return
        self.voice_status = status
        if status in ACTIVE_VOICE_STATUSES:
            self._request_voice_state()
        elif status == "idle":
            self._finish_voice_state()
        self._publish_status()

    def _request_voice_state(self):
        if self.current_state == "USER_CONTROL" or self.voice_transition_pending:
            return
        if self.current_state in SAFETY_STATES:
            return
        self.voice_transition_pending = True
        self._request_state(
            "USER_CONTROL", "user_control", 80, False,
            self._voice_transition_result,
        )

    def _voice_transition_result(self, accepted, message):
        self.voice_transition_pending = False
        self.voice_session_owned = accepted
        if not accepted:
            self.last_error = f"USER_CONTROL request denied: {message}"

    def _finish_voice_state(self):
        if self.current_state == "USER_CONTROL" and self.voice_session_owned:
            self._request_state("IDLE", "user_control", 80, True, self._voice_idle_result)

    def _voice_idle_result(self, accepted, message):
        if not accepted:
            self.last_error = f"voice completion was denied: {message}"

    def _petting_cb(self, message):
        try:
            action, _pressure = parse_petting_event(message.data)
        except ValueError as exc:
            self.last_error = str(exc)
            self._publish_status()
            return
        self.last_petting_event = time.monotonic()
        self.petting_active = action == "petting_started"
        if self.petting_active:
            self._request_petting_state()
        else:
            self._finish_petting_if_ready()
        self._publish_status()

    def _request_petting_state(self):
        if self.current_state in SAFETY_STATES or self.petting_transition_pending:
            return
        if self.current_state == "PETTING":
            self._start_petting_animation()
            return
        self.petting_transition_pending = True
        self._request_state(
            "PETTING", "petting", 60, False, self._petting_transition_result
        )

    def _petting_transition_result(self, accepted, message):
        self.petting_transition_pending = False
        self.petting_session_owned = accepted
        if accepted:
            self._start_petting_animation()
        else:
            self.last_error = f"PETTING request denied: {message}"

    def _start_petting_animation(self):
        if self.petting_animation_active or not self.animation_client.server_is_ready():
            return
        goal = PlayAnimation.Goal()
        goal.animation_name = PETTING_ANIMATION
        goal.speed_multiplier = 1.0
        goal.allow_interruption = True
        goal.use_hardware_feedback = False
        self.petting_animation_active = True
        self.animation_client.send_goal_async(goal).add_done_callback(
            self._petting_goal_response
        )

    def _petting_goal_response(self, future):
        try:
            handle = future.result()
            if not handle.accepted:
                self.petting_animation_active = False
                self.last_error = "petting animation goal rejected"
                self._finish_petting_if_ready()
                return
            self.petting_goal_handle = handle
            handle.get_result_async().add_done_callback(self._petting_goal_result)
        except Exception as exc:
            self.petting_animation_active = False
            self.last_error = f"petting action failed: {exc}"
            self._finish_petting_if_ready()

    def _petting_goal_result(self, future):
        try:
            result = future.result().result
            if not result.success:
                self.last_error = f"petting animation failed: {result.message}"
        except Exception as exc:
            self.last_error = f"petting result failed: {exc}"
        self.petting_animation_active = False
        self.petting_goal_handle = None
        self._finish_petting_if_ready()

    def _finish_petting_if_ready(self):
        if (self.petting_active or self.petting_animation_active
                or self.petting_transition_pending):
            return
        if self.current_state == "PETTING" and self.petting_session_owned:
            self._request_state("IDLE", "petting", 60, True, self._petting_idle_result)

    def _petting_idle_result(self, accepted, message):
        if accepted:
            self.petting_session_owned = False
        else:
            self.last_error = f"petting completion was denied: {message}"

    def _request_state(self, state, requester, priority, completion, callback):
        if not self.state_client.service_is_ready():
            callback(False, "state service unavailable")
            return
        request = RequestStateTransition.Request()
        request.requested_state = state
        request.requesting_node = requester
        request.priority = priority
        request.force = False
        request.completion = completion
        future = self.state_client.call_async(request)

        def done(result_future):
            try:
                result = result_future.result()
                callback(bool(result.success), result.message)
            except Exception as exc:
                callback(False, str(exc))

        future.add_done_callback(done)

    def _tick(self):
        if (self.petting_active and self.last_petting_event is not None
                and time.monotonic() - self.last_petting_event > self.petting_timeout):
            self.petting_active = False
            self._finish_petting_if_ready()
        if self.voice_status in ACTIVE_VOICE_STATUSES:
            self._request_voice_state()
        elif self.voice_status == "idle":
            self._finish_voice_state()
        self._publish_status()

    def _publish_status(self):
        self.status_publisher.publish(String(data=json.dumps({
            "state": self.current_state,
            "voice_status": self.voice_status,
            "voice_session_owned": self.voice_session_owned,
            "petting_active": self.petting_active,
            "petting_animation_active": self.petting_animation_active,
            "error": self.last_error,
        })))


def main(args=None):
    rclpy.init(args=args)
    node = SimInteractionAdapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
