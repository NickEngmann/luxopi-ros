"""ROS adapter for local speech results and silent conversation simulation."""

import json
import queue
import threading

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from std_msgs.msg import String

from luxo_behaviors.conversation_transport import ConversationClient, SimulatedConversation, LocalEventReceiver


class SpeechBridge(Node):
    def __init__(self):
        super().__init__("speech_bridge")
        self.declare_parameter("backend", "simulation")
        self.declare_parameter("service_command", "[]")
        self.declare_parameter("service_cwd", "")
        self.declare_parameter("service_timeout", 15.0)
        self.declare_parameter("preview_speaking_seconds", 1.0)
        self.declare_parameter("event_socket", "")
        backend = self.get_parameter("backend").value
        if backend == "simulation":
            self.client = SimulatedConversation()
        elif backend == "local":
            command = json.loads(self.get_parameter("service_command").value)
            if not isinstance(command, list) or not all(isinstance(arg, str) for arg in command):
                raise ValueError("service_command must be a JSON array of arguments")
            self.client = ConversationClient(
                command, cwd=self.get_parameter("service_cwd").value or None,
                timeout=self.get_parameter("service_timeout").value,
            )
        else:
            raise ValueError("backend must be simulation or local")
        self.transcripts = self.create_publisher(String, "/voice/transcript", 10)
        self.responses = self.create_publisher(String, "/voice/response", 10)
        self.status = self.create_publisher(
            String, "/voice/status", QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.animations = self.create_publisher(String, "/roarm/animation_command", 10)
        self.subscription = self.create_subscription(String, "/voice/command", self.command, 10)
        self._pending = queue.Queue(maxsize=1)
        self._stopping = threading.Event()
        self._busy = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        event_socket = self.get_parameter("event_socket").value
        self._event_receiver = LocalEventReceiver(event_socket) if event_socket else None
        self._event_worker = None
        if self._event_receiver:
            self._event_worker = threading.Thread(target=self._read_events, daemon=True)
            self._event_worker.start()
        self._publish_status("idle")
        self.get_logger().info(f"Speech backend: {backend}; this bridge never plays audio")

    def _publish_status(self, status):
        self.status.publish(String(data=status))

    def _read_events(self):
        while not self._stopping.is_set():
            try:
                event = self._event_receiver.read()
                if not event or self._stopping.is_set():
                    continue
                kind = event.get("event")
                text = event.get("text")
                if kind in {"transcript", "response"} and isinstance(text, str) and len(text) <= 2000:
                    publisher = self.transcripts if kind == "transcript" else self.responses
                    publisher.publish(String(data=text))
                elif kind == "status" and event.get("status") in {"idle", "listening", "thinking", "speaking", "error"}:
                    self._publish_status(event["status"])
                elif kind == "animation" and event.get("animation") in SimulatedConversation.ANIMATIONS:
                    self.animations.publish(String(data=event["animation"]))
            except OSError:
                break  # Receiver was closed during shutdown.

    def command(self, message):
        text = message.data.strip()
        if not text or len(text) > 2000:
            self.get_logger().warning("Ignored empty or oversized voice command")
            return
        if self._busy.is_set():
            self.get_logger().warning("Conversation busy; command rejected instead of queued for later")
            return
        self._busy.set()
        self.transcripts.publish(String(data=text))
        self._publish_status("listening")
        try:
            self._pending.put_nowait(text)
        except queue.Full:
            self._busy.clear()

    def _run(self):
        while not self._stopping.is_set():
            try:
                text = self._pending.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._publish_status("thinking")
                result = self.client.request(text)
                if self._stopping.is_set():
                    break
                animation = result.get("animation")
                if animation in SimulatedConversation.ANIMATIONS:
                    self.animations.publish(String(data=animation))
                self.responses.publish(String(data=result["response"]))
                self._publish_status("speaking")
                # A visual preview, not actual audio playback or motor feedback.
                duration = max(0.0, min(10.0, self.get_parameter("preview_speaking_seconds").value))
                self._stopping.wait(duration)
            except Exception as exc:
                self.get_logger().error(f"Conversation failed: {exc}")
                self._publish_status("error")
            finally:
                self._busy.clear()
                if not self._stopping.is_set():
                    self._publish_status("idle")

    def destroy_node(self):
        self._stopping.set()
        if self._event_receiver:
            self._event_receiver.close()
            self._event_worker.join(timeout=1)
        self.client.close()
        self._worker.join(timeout=3)
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SpeechBridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
