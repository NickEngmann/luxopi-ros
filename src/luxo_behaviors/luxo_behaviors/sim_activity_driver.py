"""Drive the normal animation and camera paths while the robot is idle in sim."""

import random

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile
from std_msgs.msg import Bool, Float32, String
from luxo_interfaces.action import PlayAnimation

from .animation_capabilities import ANIMATION_NAMES
from .shared_utils import IdleAnimationConfig


class SimActivityDriver(Node):
    """Generate non-overlapping idle motion and occasional synthetic person cues."""

    def __init__(self):
        super().__init__("sim_activity_driver")
        self.declare_parameter("idle_after", 7.0)
        self.declare_parameter("idle_interval", 20.0)
        self.declare_parameter("emotion_interval", 75.0)
        self.declare_parameter("person_hold", 2.5)
        self.idle_after = float(self.get_parameter("idle_after").value)
        self.idle_interval = float(self.get_parameter("idle_interval").value)
        self.emotion_interval = float(self.get_parameter("emotion_interval").value)
        self.person_hold = float(self.get_parameter("person_hold").value)
        self.time_scale = 1.0
        self.autonomy_enabled = True
        self.animations = [
            name for name in IdleAnimationConfig.DEFAULT_IDLE_ANIMATIONS
            if name in ANIMATION_NAMES
        ]
        if not self.animations:
            raise RuntimeError("No registered idle animations are available")
        self.current_state = "INITIALIZING"
        self.current_animation = ""
        self.last_activity = self._now()
        # Start the first quiet-time animation after idle_after, not after a
        # full interval; later animations use the configured cadence.
        self.last_idle_animation = self.last_activity - self.idle_interval
        self.last_emotion = self.last_activity
        self.person_until = 0.0
        self.previous_animation = ""
        self._idle_goal_pending = False
        self._idle_goal_handle = None
        self._animation_client = ActionClient(self, PlayAnimation, "play_animation")
        self._emotion_pub = self.create_publisher(String, "/sim/camera/emotion", 10)
        self._person_pub = self.create_publisher(Bool, "/sim/camera/person_present", 10)
        self._autonomy_status_pub = self.create_publisher(
            Bool,
            "/sim/autonomy_status",
            QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
        )
        self.create_subscription(String, "/luxo/current_state", self._state_cb, 10)
        self.create_subscription(String, "/roarm/current_animation", self._animation_cb, 10)
        self.create_subscription(Float32, "/sim/time_scale", self._time_scale_cb, 10)
        self.create_subscription(Bool, "/sim/autonomy_enabled", self._autonomy_cb, 10)
        self.create_timer(0.25, self._tick)
        self._publish_autonomy_status()
        self.get_logger().info(
            f"Autonomous simulation motion enabled ({len(self.animations)} idle animations)"
        )

    def _now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def _state_cb(self, msg):
        state = msg.data
        if state != self.current_state:
            self.last_activity = self._now()
        self.current_state = state

    def _animation_cb(self, msg):
        name = msg.data
        if name != self.current_animation:
            self.last_activity = self._now()
            self.current_animation = name

    def _time_scale_cb(self, msg):
        value = float(msg.data)
        if value in (1.0, 2.0, 3.0):
            self.time_scale = value

    def _autonomy_cb(self, msg):
        enabled = bool(msg.data)
        if enabled == self.autonomy_enabled:
            return
        self.autonomy_enabled = enabled
        self._publish_autonomy_status()
        # A pause/resume is a new quiet window. This prevents an overdue idle
        # goal racing the controls that intentionally paused the simulator.
        self.last_activity = self._now()
        if enabled:
            self.last_emotion = self.last_activity
            return
        if self.person_until:
            self._person_pub.publish(Bool(data=False))
            self.person_until = 0.0
        # Disabling autonomy is an immediate pause, including a goal that was
        # accepted just before this setting reached the activity driver.
        if self._idle_goal_handle is not None:
            try:
                self._idle_goal_handle.cancel_goal_async()
            except Exception as exc:
                self.get_logger().warning(f"Unable to cancel paused idle animation: {exc}")

    def _publish_autonomy_status(self):
        """Publish retained runtime state so dashboards synchronize on join."""
        self._autonomy_status_pub.publish(Bool(data=self.autonomy_enabled))

    def _play_idle(self, now):
        if self._idle_goal_pending or not self._animation_client.server_is_ready():
            return False
        choices = [name for name in self.animations if name != self.previous_animation]
        name = random.choice(choices or self.animations)
        goal = PlayAnimation.Goal()
        goal.animation_name = name
        goal.speed_multiplier = random.uniform(0.88, 1.12)
        goal.allow_interruption = True
        goal.use_hardware_feedback = False
        goal.trigger_source = "idle"
        self._idle_goal_pending = True
        try:
            future = self._animation_client.send_goal_async(goal)
        except Exception as exc:
            self._idle_goal_pending = False
            self.get_logger().warning(f"Idle animation submission failed: {exc}")
            return False
        future.add_done_callback(self._goal_sent)
        self.previous_animation = name
        self.last_idle_animation = now
        self.last_activity = now
        self.get_logger().info(f"Autonomous idle animation: {name}")
        return True

    def _goal_sent(self, future):
        try:
            handle = future.result()
            if handle.accepted:
                self._idle_goal_handle = handle
                if not self.autonomy_enabled:
                    handle.cancel_goal_async()
                result = handle.get_result_async()
                result.add_done_callback(
                    lambda result_future, owner=handle: self._idle_goal_complete(result_future, owner)
                )
            else:
                self._idle_goal_pending = False
                self.get_logger().warning("Idle animation goal was rejected")
        except Exception as exc:  # Keep the periodic driver alive if a goal fails.
            self._idle_goal_pending = False
            self.get_logger().warning(f"Idle animation request failed: {exc}")

    def _idle_goal_complete(self, future, owner):
        if self._idle_goal_handle is owner:
            self._idle_goal_handle = None
            self._idle_goal_pending = False
        try:
            future.result()
        except Exception as exc:
            self.get_logger().warning(f"Idle animation result failed: {exc}")

    def _tick(self):
        if not self.autonomy_enabled:
            return
        now = self._now()
        if self.person_until and now >= self.person_until:
            self._person_pub.publish(Bool(data=False))
            self.person_until = 0.0
        if self.current_state != "IDLE" or self.current_animation:
            return
        if now - self.last_emotion >= self.emotion_interval / self.time_scale:
            emotion = random.choice(("happy", "sad", "surprise", "anger"))
            self._person_pub.publish(Bool(data=True))
            self._emotion_pub.publish(String(data=emotion))
            self.person_until = now + self.person_hold / self.time_scale
            self.last_emotion = now
            self.last_activity = now
            self.get_logger().info(f"Autonomous simulated person emotion: {emotion}")
            return
        if now - self.last_idle_animation >= self.idle_interval / self.time_scale and now - self.last_activity >= self.idle_after / self.time_scale:
            self._play_idle(now)


def main(args=None):
    rclpy.init(args=args)
    node = SimActivityDriver()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
