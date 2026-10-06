"""Simulation-only consumer for voice-session and touch/petting events."""

import json
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String
from luxo_interfaces.action import PlayAnimation
from luxo_interfaces.srv import RequestStateTransition
from luxo_behaviors.sim_interaction_rules import (
    VoiceCueLifecycle, parse_petting_event, should_cancel_stale_settle,
)
from luxo_behaviors.sim_gesture_rules import (
    GESTURE_ANIMATIONS, GESTURE_COOLDOWN_SECONDS, gesture_block_reason,
    normalize_gesture,
)


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
        self.voice_idle_pending = False
        self.voice_generation = 0
        self.voice_cues = VoiceCueLifecycle()
        self.current_animation = ""
        self.primary_animation_active = False
        self.cue_active = False
        self.cue_generation = None
        self.cue_goal_handle = None
        self.petting_active = False
        self.petting_transition_pending = False
        self.petting_transition_generation = None
        self.petting_session_owned = False
        self.petting_idle_pending = False
        self.last_petting_event = None
        self.petting_goal_handle = None
        self.petting_goal_generation = None
        self.petting_goal_pending = False
        self.petting_animation_active = False
        self.petting_generation = 0
        self.petting_cancel_requested = False
        self.last_error = ""
        self.last_gesture = ""
        self.gesture_animation = ""
        self.gesture_status = "idle"
        self.gesture_error = ""
        self.gesture_last_ignored = ""
        self.gesture_last_started_at = 0.0
        self.gesture_generation = 0
        self.gesture_goal_handle = None
        self.gesture_goal_pending = False
        self.gesture_animation_active = False

        self.state_client = self.create_client(
            RequestStateTransition, "/luxo/request_state_transition"
        )
        self.animation_client = ActionClient(self, PlayAnimation, "play_animation")
        self.create_subscription(String, "/luxo/current_state", self._state_cb, 10)
        self.create_subscription(String, "/voice/status", self._voice_status_cb, 10)
        self.create_subscription(String, "/voice/transcript", self._transcript_cb, 10)
        self.create_subscription(
            String, "/roarm/current_animation", self._animation_cb, 10
        )
        self.create_subscription(
            String, "/collision/petting_events", self._petting_cb, 10
        )
        self.create_subscription(String, "/gestures", self._gesture_cb, 10)
        self.status_publisher = self.create_publisher(
            String, "/sim/interaction_status", 10
        )
        self.create_timer(0.1, self._tick)

    def _state_cb(self, message):
        next_state = message.data.upper()
        previous = self.current_state
        self.current_state = next_state
        if next_state in SAFETY_STATES and self.gesture_animation_active:
            self._cancel_gesture_animation(f"state:{next_state.lower()}")
        if (previous == "PETTING" and next_state != "PETTING"
                and (self.petting_active or self.petting_animation_active)):
            self._stop_petting_session()
        if next_state == "IDLE" and self.petting_active:
            # A prior completion request can race a fresh touch. Reacquire
            # PETTING after the state owner publishes the completed transition.
            self._request_petting_state()
        elif next_state == "PETTING":
            if self.petting_active:
                self._start_petting_animation()
            else:
                # The touch may have ended while the asynchronous state grant
                # was in flight. Complete our just-granted ownership promptly.
                self._finish_petting_if_ready()
        if next_state == "IDLE" and self.voice_status == "idle":
            self.voice_session_owned = False

    def _voice_status_cb(self, message):
        status = message.data.strip().lower()
        if status not in ACTIVE_VOICE_STATUSES | {"idle", "error"}:
            self.last_error = f"ignored unknown voice status: {status[:80]}"
            self._publish_status()
            return
        if status in ACTIVE_VOICE_STATUSES and self.gesture_animation_active:
            self._cancel_gesture_animation("voice_session")
        new_voice_session = status in ACTIVE_VOICE_STATUSES and not self.voice_cues.active
        if (should_cancel_stale_settle(new_voice_session, self.current_animation)
                and self.cue_goal_handle is not None):
            # A previous session's settle is disposable presentation. Stop it
            # so it cannot make the new listening cue wait or get rejected.
            self.cue_goal_handle.cancel_goal_async()
        self.voice_status = status
        if status in ACTIVE_VOICE_STATUSES:
            self.voice_generation = self.voice_cues.status(status)
            self._request_voice_state()
        elif status == "idle":
            self.voice_generation = self.voice_cues.status(status)
            self._finish_voice_state()
        self._publish_status()

    def _request_voice_state(self):
        if (self.current_state == "USER_CONTROL" and not self.voice_idle_pending):
            return
        if self.voice_transition_pending:
            return
        if self.current_state in SAFETY_STATES:
            return
        self.voice_transition_pending = True
        generation = self.voice_generation
        self._request_state(
            "USER_CONTROL", "user_control", 80, False,
            lambda accepted, message: self._voice_transition_result(
                generation, accepted, message
            ),
        )

    def _voice_transition_result(self, generation, accepted, message):
        self.voice_transition_pending = False
        if not self.voice_cues.is_current(generation):
            # A short voice request can finish before the USER_CONTROL grant
            # arrives. If that stale grant was applied and no newer session
            # owns the state, immediately complete only our own state.
            if (accepted and self.voice_status == "idle"
                    and self.current_state == "USER_CONTROL"):
                self._request_state(
                    "IDLE", "user_control", 80, True,
                    lambda *_: None,
                )
            return
        self.voice_session_owned = accepted
        self.voice_idle_pending = False
        if not accepted:
            self.last_error = f"USER_CONTROL request denied: {message}"

    def _finish_voice_state(self):
        if (self.current_state == "USER_CONTROL" and self.voice_session_owned
                and not self.voice_idle_pending and not self.primary_animation_active):
            self.voice_idle_pending = True
            generation = self.voice_generation
            self._request_state(
                "IDLE", "user_control", 80, True,
                lambda accepted, message: self._voice_idle_result(
                    generation, accepted, message
                ),
            )

    def _voice_idle_result(self, generation, accepted, message):
        if generation != self.voice_generation:
            return
        self.voice_idle_pending = False
        if accepted:
            self.voice_session_owned = False
        if not accepted:
            self.last_error = f"voice completion was denied: {message}"

    def _transcript_cb(self, message):
        if message.data.strip():
            self.voice_cues.transcript()

    def _animation_cb(self, message):
        self.current_animation = message.data.strip()
        if self.current_animation and self.current_animation not in {
                "listening", "acknowledge", "thinking", "speaking", "settle"}:
            self.primary_animation_active = True
            self.voice_cues.suppress()
            self.cue_active = False
            self.cue_goal_handle = None
        elif not self.current_animation:
            self.primary_animation_active = False
            if self.voice_status == "idle":
                self._finish_voice_state()

    def _petting_cb(self, message):
        try:
            action, _pressure = parse_petting_event(message.data)
        except ValueError as exc:
            self.last_error = str(exc)
            self._publish_status()
            return
        self.last_petting_event = time.monotonic()
        if action == "petting_started":
            if not self.petting_active:
                self.petting_generation += 1
            self.petting_active = True
            self._request_petting_state()
        else:
            self._stop_petting_session()
            self._finish_petting_if_ready()
        self._publish_status()

    def _gesture_cb(self, message):
        gesture = normalize_gesture(message.data)
        if gesture is None:
            self.gesture_last_ignored = f"unknown:{str(message.data)[:40]}"
            self._publish_status()
            return
        self.last_gesture = gesture
        now = time.monotonic()
        reason = gesture_block_reason(
            state=self.current_state,
            voice_status=self.voice_status,
            primary_animation_active=self.primary_animation_active,
            cue_active=self.cue_active,
            petting_active=self.petting_active,
            gesture_active=self.gesture_animation_active or self.gesture_goal_pending,
            last_started_at=self.gesture_last_started_at,
            now=now,
        )
        if reason:
            self.gesture_last_ignored = f"{gesture}:{reason}"
            self._publish_status()
            return
        if not self.animation_client.server_is_ready():
            self.gesture_status = "unavailable"
            self.gesture_error = "play_animation action server unavailable"
            self._publish_status()
            return

        animation = GESTURE_ANIMATIONS[gesture]
        goal = PlayAnimation.Goal()
        goal.animation_name = animation
        goal.speed_multiplier = 1.5
        goal.allow_interruption = False
        goal.use_hardware_feedback = False
        self.gesture_generation += 1
        generation = self.gesture_generation
        self.gesture_animation = animation
        self.gesture_status = "pending"
        self.gesture_error = ""
        self.gesture_last_ignored = ""
        self.gesture_last_started_at = now
        self.gesture_goal_pending = True
        self.gesture_animation_active = True
        self.animation_client.send_goal_async(goal).add_done_callback(
            lambda future: self._gesture_goal_response(generation, future)
        )
        self._publish_status()

    def _gesture_goal_response(self, generation, future):
        try:
            handle = future.result()
        except Exception as exc:
            self._finish_gesture_goal(generation, "failed", str(exc))
            return
        if not handle.accepted:
            self._finish_gesture_goal(generation, "rejected", "gesture animation goal rejected")
            return
        if generation != self.gesture_generation or not self.gesture_animation_active:
            handle.cancel_goal_async()
            return
        self.gesture_goal_pending = False
        self.gesture_goal_handle = handle
        handle.get_result_async().add_done_callback(
            lambda result: self._gesture_goal_result(generation, result)
        )
        self._publish_status()

    def _gesture_goal_result(self, generation, future):
        try:
            wrapped = future.result()
            result = wrapped.result
            status = "completed" if result.success else str(result.final_state or "failed")
            error = "" if result.success else str(result.message)
        except Exception as exc:
            status, error = "failed", str(exc)
        self._finish_gesture_goal(generation, status, error)

    def _finish_gesture_goal(self, generation, status, error):
        if generation != self.gesture_generation:
            return
        self.gesture_goal_handle = None
        self.gesture_goal_pending = False
        self.gesture_animation_active = False
        self.gesture_status = status
        self.gesture_error = error
        self._publish_status()

    def _cancel_gesture_animation(self, reason):
        self.gesture_generation += 1
        handle = self.gesture_goal_handle
        self.gesture_goal_handle = None
        self.gesture_goal_pending = False
        self.gesture_animation_active = False
        self.gesture_status = "preempted"
        self.gesture_error = reason
        if handle is not None:
            handle.cancel_goal_async()

    def _stop_petting_session(self):
        if self.petting_active:
            self.petting_active = False
            self.petting_generation += 1
        if self.petting_animation_active:
            self.petting_cancel_requested = True
            if self.petting_goal_handle is not None:
                self.petting_goal_handle.cancel_goal_async()

    def _request_petting_state(self):
        if self.current_state in SAFETY_STATES or self.petting_transition_pending:
            return
        if self.current_state == "PETTING":
            self._start_petting_animation()
            return
        self.petting_transition_pending = True
        generation = self.petting_generation
        self.petting_transition_generation = generation
        self._request_state(
            "PETTING", "petting", 60, False,
            lambda accepted, message: self._petting_transition_result(
                generation, accepted, message
            ),
        )

    def _petting_transition_result(self, generation, accepted, message):
        self.petting_transition_pending = False
        self.petting_session_owned = accepted
        if accepted:
            if self.petting_active:
                self._start_petting_animation()
            else:
                self._finish_petting_if_ready()
        elif self.petting_active and generation == self.petting_generation:
            self.last_error = f"PETTING request denied: {message}"

    def _start_petting_animation(self):
        if (not self.petting_active or self.current_state != "PETTING"
                or self.petting_animation_active
                or not self.animation_client.server_is_ready()):
            return
        goal = PlayAnimation.Goal()
        goal.animation_name = PETTING_ANIMATION
        goal.speed_multiplier = 1.0
        goal.allow_interruption = True
        goal.use_hardware_feedback = False
        generation = self.petting_generation
        self.petting_goal_pending = True
        self.petting_goal_generation = generation
        self.petting_cancel_requested = False
        self.petting_animation_active = True
        self.animation_client.send_goal_async(goal).add_done_callback(
            lambda future: self._petting_goal_response(generation, future)
        )

    def _petting_goal_response(self, generation, future):
        try:
            handle = future.result()
            if not handle.accepted:
                self._finish_petting_goal(generation)
                if generation == self.petting_generation and self.petting_active:
                    self.last_error = "petting animation goal rejected"
                self._finish_petting_if_ready()
                return
            if (generation != self.petting_generation or not self.petting_active
                    or self.petting_cancel_requested):
                handle.cancel_goal_async()
            else:
                self.petting_goal_handle = handle
            handle.get_result_async().add_done_callback(
                lambda result: self._petting_goal_result(generation, result)
            )
        except Exception as exc:
            self._finish_petting_goal(generation)
            if generation == self.petting_generation and self.petting_active:
                self.last_error = f"petting action failed: {exc}"
            self._finish_petting_if_ready()

    def _petting_goal_result(self, generation, future):
        try:
            wrapped = future.result()
            result = wrapped.result
            canceled = getattr(wrapped, "status", None) == 5
            expected_cancel = (
                self.petting_cancel_requested
                or generation != self.petting_generation
                or not self.petting_active
            )
            if (not result.success and not canceled and not expected_cancel
                    and generation == self.petting_generation
                    and self.petting_active):
                self.last_error = f"petting animation failed: {result.message}"
        except Exception as exc:
            if generation == self.petting_generation and self.petting_active:
                self.last_error = f"petting result failed: {exc}"
        was_current = generation == self.petting_goal_generation
        self._finish_petting_goal(generation)
        if was_current and self.petting_active:
            self._start_petting_animation()
        self._finish_petting_if_ready()

    def _finish_petting_goal(self, generation):
        if generation != self.petting_goal_generation:
            return False
        self.petting_goal_handle = None
        self.petting_goal_pending = False
        self.petting_animation_active = False
        self.petting_goal_generation = None
        self.petting_cancel_requested = False
        return True

    def _finish_petting_if_ready(self):
        if (self.petting_active or self.petting_animation_active
                or self.petting_goal_pending or self.petting_transition_pending):
            return
        if (self.current_state == "PETTING" and self.petting_session_owned
                and not self.petting_idle_pending):
            self.petting_idle_pending = True
            generation = self.petting_generation
            self._request_state(
                "IDLE", "petting", 60, True,
                lambda accepted, message: self._petting_idle_result(
                    generation, accepted, message
                ),
            )

    def _petting_idle_result(self, generation, accepted, message):
        self.petting_idle_pending = False
        if generation != self.petting_generation:
            if accepted and self.petting_active and self.current_state != "PETTING":
                self._request_petting_state()
            elif self.petting_active:
                self._start_petting_animation()
            return
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
            self._stop_petting_session()
            self._finish_petting_if_ready()
        if self.voice_status in ACTIVE_VOICE_STATUSES:
            self._request_voice_state()
        elif self.voice_status == "idle":
            self._finish_voice_state()
        self._tick_voice_cues()
        self._publish_status()

    def _tick_voice_cues(self):
        if (self.cue_active or self.current_animation
                or not self.animation_client.server_is_ready()):
            return
        cue = self.voice_cues.pop()
        if cue is None:
            return
        if ((cue == "settle" and self.current_state != "IDLE")
                or (cue != "settle" and self.current_state != "USER_CONTROL")):
            # Keep the cue pending until the state owner accepts USER_CONTROL.
            self.voice_cues._pending.insert(0, cue)
            return
        goal = PlayAnimation.Goal()
        goal.animation_name = cue
        goal.speed_multiplier = 1.0
        goal.allow_interruption = False
        goal.use_hardware_feedback = False
        generation = self.voice_generation
        self.cue_active = True
        self.cue_generation = generation
        self.animation_client.send_goal_async(goal).add_done_callback(
            lambda future: self._cue_goal_response(generation, cue, future)
        )

    def _cue_goal_response(self, generation, cue, future):
        try:
            handle = future.result()
            if not handle.accepted:
                self.cue_active = False
                self.last_error = f"visual cue {cue} was rejected"
                return
            self.cue_goal_handle = handle
            if (cue == "settle" and generation != self.voice_generation
                    and self.voice_cues.active):
                handle.cancel_goal_async()
            handle.get_result_async().add_done_callback(
                lambda result: self._cue_goal_result(generation, cue, result)
            )
        except Exception as exc:
            self.cue_active = False
            self.last_error = f"visual cue {cue} failed: {exc}"

    def _cue_goal_result(self, generation, cue, future):
        try:
            wrapped = future.result()
            if not wrapped.result.success:
                self.last_error = f"visual cue {cue} ended: {wrapped.result.message}"
        except Exception as exc:
            self.last_error = f"visual cue {cue} result failed: {exc}"
        # A prior session's cue completion can only clear its own bookkeeping.
        if generation == self.cue_generation:
            self.cue_active = False
            self.cue_goal_handle = None

    def _publish_status(self):
        self.status_publisher.publish(String(data=json.dumps({
            "state": self.current_state,
            "voice_status": self.voice_status,
            "voice_session_owned": self.voice_session_owned,
            "primary_animation_active": self.primary_animation_active,
            "petting_active": self.petting_active,
            "petting_animation_active": self.petting_animation_active,
            "gesture": self.last_gesture,
            "gesture_animation": self.gesture_animation,
            "gesture_status": self.gesture_status,
            "gesture_error": self.gesture_error,
            "gesture_last_ignored": self.gesture_last_ignored,
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
