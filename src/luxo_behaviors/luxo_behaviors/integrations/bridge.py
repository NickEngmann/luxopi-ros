"""Optional ROS bridge for HA status, Music Assistant and a Sendspin player."""

import json
import os
import queue
import threading
import time
from urllib.parse import urlsplit, urlunsplit

import rclpy
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String
from luxo_interfaces.action import PlayAnimation

from luxo_behaviors.conversation_transport import SimulatedConversation
from luxo_behaviors.integrations.api_clients import (
    ApiError, HA_DEFAULT_URL, HomeAssistantClient, MusicAssistantClient,
    default_music_assistant_url, integration_config,
)
from luxo_behaviors.integrations.home_assistant_events import normalize_command


class SmartHomeBridge(Node):
    """Best-effort adapters; local motion and safety remain independent."""

    def __init__(self):
        super().__init__("smart_home_bridge")
        self.state = "UNKNOWN"
        self.motion = {}
        self._stopping = threading.Event()
        self._commands = queue.Queue(maxsize=64)
        self._music = queue.Queue(maxsize=32)
        self._health_wakeup = threading.Event()
        self._ha = self._create_ha()
        self._ma = self._create_ma()
        self.actions = ActionClient(self, PlayAnimation, "play_animation")
        self.create_subscription(String, "/luxo/current_state", self._state_cb, 10)
        self.create_subscription(String, "/sim/motion_status", self._motion_cb, 10)
        self.create_subscription(String, "/luxo/music_request", self._music_cb, 10)
        self.create_timer(0.05, self._dispatch_commands)
        self._music_thread = threading.Thread(target=self._music_worker, daemon=True)
        self._music_thread.start()
        self._health_thread = threading.Thread(target=self._health_worker, daemon=True)
        self._health_thread.start()
        self._event_thread = None
        if self._ha and os.environ.get("LUXOPI_HA_COMMANDS", "false").lower() in {"1", "true", "yes"}:
            self._event_thread = threading.Thread(target=self._ha_events, daemon=True)
            self._event_thread.start()
        self.get_logger().info(
            f"Smart-home adapters ready; Home Assistant={'enabled' if self._ha else 'off'}, "
            f"Music Assistant={'enabled' if self._ma else 'off'}"
        )

    def _create_ha(self):
        base, token = integration_config("ha", default_url=HA_DEFAULT_URL)
        if not token:
            return None
        try:
            return HomeAssistantClient(base, token)
        except ValueError as exc:
            self.get_logger().warning(f"Home Assistant adapter disabled: {exc}")
            return None

    def _create_ma(self):
        ha_url, _ = integration_config("ha", default_url=HA_DEFAULT_URL)
        base, token = integration_config("ma", default_url=default_music_assistant_url(ha_url))
        player = os.environ.get("LUXOPI_MA_PLAYER_ID")
        if not token or not player:
            return None
        try:
            return MusicAssistantClient(base, token, player)
        except ValueError as exc:
            self.get_logger().warning(f"Music Assistant adapter disabled: {exc}")
            return None

    def _state_cb(self, message):
        self.state = str(message.data)[:64]

    def _motion_cb(self, message):
        try:
            payload = json.loads(message.data)
            self.motion = payload if isinstance(payload, dict) else {}
        except (TypeError, ValueError):
            self.motion = {}

    def _music_cb(self, message):
        try:
            payload = json.loads(message.data)
        except (TypeError, ValueError):
            self.get_logger().warning("Ignored malformed Music Assistant request")
            return
        operation = payload.get("operation") if isinstance(payload, dict) else None
        query = payload.get("query") if isinstance(payload, dict) else None
        source = payload.get("source") if isinstance(payload, dict) else None
        if operation == "select_source" and source in {"Spotify", "Music Assistant"}:
            try:
                self._music.put_nowait({"operation": operation, "source": source})
            except queue.Full:
                self.get_logger().warning("Smart-home command queue full; request dropped")
            return
        if operation not in {*MusicAssistantClient.COMMANDS, "play_media"}:
            self.get_logger().warning("Ignored unsupported Music Assistant operation")
            return
        if operation == "play_media" and (not isinstance(query, str) or not query.strip() or len(query) > 240):
            self.get_logger().warning("Ignored invalid Music Assistant search query")
            return
        try:
            self._music.put_nowait({"operation": operation, "query": query})
        except queue.Full:
            self.get_logger().warning("Music Assistant queue full; request dropped")

    def _music_worker(self):
        while not self._stopping.is_set():
            try:
                item = self._music.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                if item["operation"] == "select_source":
                    entity = os.environ.get("LUXOPI_HA_MUSIC_PLAYER_ENTITY", "")
                    if self._ha and entity:
                        self._ha.call_service("media_player", "select_source", {
                            "entity_id": entity, "source": item["source"],
                        })
                    else:
                        self.get_logger().warning("Source selection ignored: Home Assistant music player entity is not configured")
                elif self._ma:
                    self._ma.command(item["operation"], query=item.get("query"))
                else:
                    self.get_logger().warning("Music command ignored: Music Assistant is not configured")
            except (ApiError, OSError, ValueError) as exc:
                self.get_logger().warning(f"Music Assistant request failed: {exc}")
            finally:
                self._music.task_done()

    def _publish_health(self):
        if not self._ha:
            return
        try:
            self._ha.set_state("sensor.luxopi_state", self.state, {
                "friendly_name": "LuxoPI state", "motion_owner": self.motion.get("exclusive_motion_owner", ""),
                "avoidance_mode": self.motion.get("avoidance_mode", "unknown"),
            })
            self._ha.set_state("binary_sensor.luxopi_available", "on", {
                "friendly_name": "LuxoPI available", "device_class": "connectivity",
                "local_state": self.state, "last_report_unix": time.time(),
                "motion_hold": bool(self.motion.get("motion_hold_requested", False)),
            })
        except (ApiError, OSError, ValueError) as exc:
            self.get_logger().warning(f"Home Assistant update failed; local behavior is unaffected: {exc}")

    def _health_worker(self):
        """Keep slow optional REST calls out of the ROS executor thread."""
        while not self._stopping.is_set():
            self._publish_health()
            self._health_wakeup.wait(10.0)
            self._health_wakeup.clear()

    def _ha_events(self):
        """Subscribe to a user-defined HA event without adding a hard dependency."""
        raw_url, token = integration_config("ha", default_url=HA_DEFAULT_URL)
        raw_url = raw_url.rstrip("/")
        parts = urlsplit(raw_url)
        ws_url = urlunsplit(("wss" if parts.scheme == "https" else "ws", parts.netloc,
                             "/api/websocket", "", ""))
        while not self._stopping.is_set():
            try:
                from websockets.sync.client import connect
                with connect(ws_url, open_timeout=4, close_timeout=1) as socket:
                    first = json.loads(socket.recv())
                    if first.get("type") != "auth_required":
                        raise ApiError("unexpected Home Assistant WebSocket handshake")
                    socket.send(json.dumps({"type": "auth", "access_token": token}))
                    auth = json.loads(socket.recv())
                    if auth.get("type") != "auth_ok":
                        raise ApiError("Home Assistant WebSocket authentication failed")
                    socket.send(json.dumps({"id": 1, "type": "subscribe_events",
                                            "event_type": "luxopi_command"}))
                    result = json.loads(socket.recv())
                    if result.get("type") != "result" or not result.get("success"):
                        raise ApiError("Home Assistant event subscription failed")
                    while not self._stopping.is_set():
                        message = json.loads(socket.recv())
                        event = message.get("event", {})
                        data = event.get("data", {}) if isinstance(event, dict) else {}
                        command = normalize_command(data)
                        if command:
                            try:
                                self._commands.put_nowait(command)
                            except queue.Full:
                                self.get_logger().warning("Home Assistant command queue full")
            except Exception as exc:
                if not self._stopping.is_set():
                    self.get_logger().warning(f"Home Assistant command stream reconnecting: {exc}")
                    self._stopping.wait(5)

    def _dispatch_commands(self):
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                break
            if command["kind"] == "music":
                payload = {"operation": command["operation"]}
                if "query" in command:
                    payload["query"] = command["query"]
                if "source" in command:
                    payload["source"] = command["source"]
                try:
                    self._music.put_nowait(payload)
                except queue.Full:
                    self.get_logger().warning("Music Assistant queue full")
            elif command["kind"] == "animation" and command["name"] in SimulatedConversation.ANIMATIONS:
                goal = PlayAnimation.Goal()
                goal.animation_name = command["name"]
                goal.speed_multiplier = 1.0
                if self.actions.server_is_ready():
                    self.actions.send_goal_async(goal)
                else:
                    self.get_logger().warning("Animation action server unavailable for HA command")
            self._commands.task_done()

    def destroy_node(self):
        self._stopping.set()
        self._health_wakeup.set()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SmartHomeBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
