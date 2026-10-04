"""Local browser control panel for a ROS-only Luxo simulation."""

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import rclpy
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float32, Int16, String, UInt8

from luxo_behaviors.simulator_protocol import MAX_EVENT_BYTES, normalize_event


STATE_AURAS = {
    "INITIALIZING": "#328dff",
    "IDLE": "#f0f4ff",
    "ANIMATING": "#e7e9f2",
    "VOICE_FOLLOWING": "#9ba8ff",
    "COLLISION_AVOIDING": "#ff9c36",
    "RETURNING_HOME": "#c9ec9e",
    "ESCAPE_MODE": "#ff3b55",
    "USER_CONTROL": "#ffd447",
    "EMOTION_REACTING": "#bf70ff",
    "PETTING": "#ff69b4",
    "ERROR": "#ff3b55",
    "SHUTDOWN": "#80838c",
}


class SimulatorDashboard(Node):
    """Small bounded HTTP/ROS bridge; it has no camera, audio, or serial path."""

    def __init__(self):
        super().__init__("simulator_dashboard")
        self.declare_parameter("host", "0.0.0.0")
        self.declare_parameter("port", 8080)
        host = self.get_parameter("host").value
        port = int(self.get_parameter("port").value)
        if not 1 <= port <= 65535:
            raise ValueError("port must be in the range 1..65535")

        self._events = queue.Queue(maxsize=64)
        self._mesh_dir = Path(get_package_share_directory("roarm")) / "meshes"
        self._lock = threading.Lock()
        self._snapshot = {
            "state": "INITIALIZING",
            "animation": "",
            "status": "idle",
            "transcript": "",
            "response": "",
            "joint_names": [],
            "positions": [],
            "direction": None,
            "direction_evidence": {},
            "voice_active": False,
            "motion": {},
            "sensors": {},
            "graph_nodes": [],
        }

        self._publishers = {
            "voice_command": self.create_publisher(String, "/voice/command", 10),
            "audio_direction": self.create_publisher(Float32, "/sim/audio_direction", 10),
            "touch": {
                name: self.create_publisher(UInt8, f"/touch_sensors/{name}", 10)
                for name in ("head_top", "head_left", "head_bottom", "head_right")
            },
            "gesture": self.create_publisher(String, "/i2c/apds9960/gesture", 10),
            "proximity": self.create_publisher(Int16, "/i2c/apds9960/proximity", 10),
            "distance": {
                side: self.create_publisher(Float32, f"/i2c/vl53_{side}/distance", 10)
                for side in ("left", "right")
            },
            "collision": {
                "front": self.create_publisher(Bool, "/head_collision_warning", 10),
                "left": self.create_publisher(Bool, "/left_collision_warning", 10),
                "right": self.create_publisher(Bool, "/right_collision_warning", 10),
            },
            "collision_status": self.create_publisher(
                String, "/collision_status_for_animation", 10
            ),
            "vision": self.create_publisher(String, "/camera/emotion", 10),
            "person_distance": self.create_publisher(
                Float32, "/camera/person_distance", 10
            ),
            "person_present": self.create_publisher(
                Bool, "/sim/vision/person_present", 10
            ),
        }

        self.create_subscription(String, "/luxo/current_state", self._state_cb, 10)
        self.create_subscription(String, "/roarm/current_animation", self._animation_cb, 10)
        self.create_subscription(JointState, "/joint_states", self._joint_cb, 10)
        self.create_subscription(String, "/sim/motion_status", self._motion_status_cb, 10)
        self.create_subscription(String, "/voice/transcript", self._transcript_cb, 10)
        self.create_subscription(String, "/voice/response", self._response_cb, 10)
        self.create_subscription(String, "/voice/status", self._status_cb, 10)
        self.create_subscription(Float32, "/voice/follow_direction", self._direction_cb, 10)
        self.create_subscription(Bool, "/voice/active", self._active_cb, 10)
        self.create_subscription(
            String, "/sim/direction_evidence", self._direction_evidence_cb, 10
        )
        self.create_subscription(Bool, "/head_collision_warning", self._collision_front_cb, 10)
        self.create_subscription(Bool, "/left_collision_warning", self._collision_left_cb, 10)
        self.create_subscription(Bool, "/right_collision_warning", self._collision_right_cb, 10)
        self.create_subscription(String, "/collision_details", self._collision_details_cb, 10)
        self.create_subscription(String, "/front_collision_severity", self._front_severity_cb, 10)
        self.create_subscription(String, "/left_collision_severity", self._left_severity_cb, 10)
        self.create_subscription(String, "/right_collision_severity", self._right_severity_cb, 10)
        self.create_subscription(String, "/collision/petting_events", self._petting_cb, 10)
        self.create_subscription(String, "/gestures", self._gesture_result_cb, 10)
        self.create_subscription(String, "/camera/emotion", self._emotion_cb, 10)
        self.create_subscription(Float32, "/camera/person_distance", self._person_distance_cb, 10)

        self._drain_timer = self.create_timer(0.02, self._drain_events)
        self._graph_timer = self.create_timer(1.0, self._refresh_graph)
        self._httpd = self._create_server(host, port)
        self._http_thread = threading.Thread(
            target=self._httpd.serve_forever, name="simulator-dashboard-http", daemon=True
        )
        self._http_thread.start()
        self.get_logger().info(f"Simulation dashboard at http://127.0.0.1:{port}")

    def _create_server(self, host, port):
        node = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def _reply(self, status, content, content_type="application/json; charset=utf-8"):
                self._reply_bytes(status, content.encode("utf-8"), content_type)

            def _reply_bytes(self, status, body, content_type):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/":
                    try:
                        html = Path(__file__).with_name("simulator_ui.html").read_text(
                            encoding="utf-8"
                        )
                    except OSError:
                        self._reply(500, "Dashboard asset missing", "text/plain; charset=utf-8")
                        return
                    self._reply(200, html, "text/html; charset=utf-8")
                elif path.startswith("/assets/"):
                    # Serve fixed vendored modules or the already-installed URDF mesh assets.
                    relative = path.removeprefix("/assets/")
                    vendor_files = {
                        "vendor/three.module.js",
                        "vendor/three.core.js",
                        "vendor/STLLoader.js",
                        "vendor/OrbitControls.js",
                    }
                    mesh_files = {"roarm/base.stl", "roarm/L1.stl", "roarm/L2.stl", "roarm/L3.stl", "roarm/L4.stl"}
                    if relative in vendor_files:
                        target = (Path(__file__).with_name("assets") / relative).resolve()
                    elif relative in mesh_files:
                        target = (node._mesh_dir / Path(relative).name).resolve()
                    else:
                        self._reply(404, "Not found", "text/plain; charset=utf-8")
                        return
                    if not target.is_file():
                        self._reply(404, "Not found", "text/plain; charset=utf-8")
                        return
                    content_type = (
                        "application/javascript; charset=utf-8"
                        if target.suffix == ".js"
                        else "model/stl"
                    )
                    self._reply_bytes(200, target.read_bytes(), content_type)
                elif path == "/api/state":
                    self._reply(200, json.dumps(node.get_snapshot()))
                else:
                    self._reply(404, json.dumps({"error": "not found"}))

            def do_POST(self):
                if urlparse(self.path).path != "/api/events":
                    self._reply(404, json.dumps({"error": "not found"}))
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > MAX_EVENT_BYTES:
                        raise ValueError("request size must be between 1 and 4096 bytes")
                    raw = self.rfile.read(length)
                    event = normalize_event(json.loads(raw.decode("utf-8")))
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    self._reply(400, json.dumps({"error": str(exc)}))
                    return
                try:
                    node._events.put_nowait(event)
                except queue.Full:
                    self._reply(429, json.dumps({"error": "simulator event queue is full"}))
                    return
                self._reply(202, json.dumps({"accepted": True}))

        return ThreadingHTTPServer((host, port), Handler)

    def get_snapshot(self):
        with self._lock:
            result = dict(self._snapshot)
            result["sensors"] = dict(self._snapshot["sensors"])
            result["aura"] = self._aura_color(result)
            result["health"] = self._health_summary(result)
            return result

    @staticmethod
    def _health_summary(snapshot):
        present = set(snapshot.get("graph_nodes", []))
        expected = (
            "state_manager",
            "animation_command",
            "sim_motion_controller",
            "sim_direction_node",
            "speech_bridge",
            "robot_state_publisher",
            "simulator_dashboard",
        )
        return {
            "node_count": len(present),
            "nodes": sorted(present),
            "components": {name: name in present for name in expected},
        }

    def _refresh_graph(self):
        try:
            names = [name for name, _namespace in self.get_node_names_and_namespaces()]
            self._update(graph_nodes=names)
        except Exception as exc:
            self.get_logger().debug(f"Could not sample local ROS graph: {exc}")

    @staticmethod
    def _aura_color(snapshot):
        voice_status = snapshot.get("status", "idle").lower()
        if voice_status == "listening":
            return "#3c92ff"
        if voice_status == "speaking":
            return "#ba62ff"
        if voice_status == "error":
            return "#ff3b55"
        if snapshot.get("voice_active"):
            return "#3c92ff"
        return STATE_AURAS.get(snapshot.get("state", "IDLE"), "#f0f4ff")

    def _update(self, **values):
        with self._lock:
            self._snapshot.update(values)

    def _state_cb(self, msg):
        self._update(state=msg.data)

    def _animation_cb(self, msg):
        self._update(animation=msg.data)

    def _joint_cb(self, msg):
        self._update(joint_names=list(msg.name), positions=list(msg.position))

    def _transcript_cb(self, msg):
        self._update(transcript=msg.data)

    def _response_cb(self, msg):
        self._update(response=msg.data)

    def _status_cb(self, msg):
        self._update(status=msg.data)

    def _direction_cb(self, msg):
        self._update(direction=float(msg.data))

    def _active_cb(self, msg):
        self._update(voice_active=bool(msg.data))

    def _motion_status_cb(self, msg):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            data = {"error": "motion status was not valid JSON"}
        self._update(motion=data)

    def _direction_evidence_cb(self, msg):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            data = {"error": "direction evidence was not valid JSON"}
        self._update(direction_evidence=data)

    def _collision_front_cb(self, msg):
        self._sensor_update(front_collision=bool(msg.data))

    def _collision_left_cb(self, msg):
        self._sensor_update(left_collision=bool(msg.data))

    def _collision_right_cb(self, msg):
        self._sensor_update(right_collision=bool(msg.data))

    def _collision_details_cb(self, msg):
        self._sensor_update(collision_details=msg.data)

    def _front_severity_cb(self, msg):
        self._sensor_update(front_severity=msg.data)

    def _left_severity_cb(self, msg):
        self._sensor_update(left_severity=msg.data)

    def _right_severity_cb(self, msg):
        self._sensor_update(right_severity=msg.data)

    def _petting_cb(self, msg):
        self._sensor_update(petting_event=msg.data)

    def _gesture_result_cb(self, msg):
        self._sensor_update(gesture_result=msg.data)

    def _emotion_cb(self, msg):
        self._sensor_update(emotion=msg.data)

    def _person_distance_cb(self, msg):
        self._sensor_update(person_distance=float(msg.data))

    def _sensor_update(self, **values):
        with self._lock:
            self._snapshot["sensors"].update(values)

    def _drain_events(self):
        for _ in range(32):
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return
            self._publish_event(event)

    def _publish_event(self, event):
        kind = event["type"]
        if kind == "voice_command":
            self._publishers[kind].publish(String(data=event["text"]))
            self._sensor_update(last_voice_command=event["text"])
        elif kind == "audio_direction":
            self._publishers[kind].publish(Float32(data=event["degrees"]))
            self._sensor_update(requested_mic_direction=event["degrees"])
        elif kind == "touch":
            self._publishers[kind][event["sensor"]].publish(UInt8(data=event["value"]))
            self._sensor_update(**{event["sensor"]: event["value"]})
        elif kind == "gesture":
            self._publishers[kind].publish(String(data=event["gesture"]))
            self._sensor_update(gesture=event["gesture"])
        elif kind == "proximity":
            # The production collision path validates distinct fresh samples,
            # not repeated timer reads; send two DDS samples for one UI event.
            self._publishers[kind].publish(Int16(data=event["value"]))
            self._publishers[kind].publish(Int16(data=event["value"]))
            self._sensor_update(proximity=event["value"])
        elif kind == "distance":
            publisher = self._publishers[kind][event["side"]]
            publisher.publish(Float32(data=event["metres"]))
            publisher.publish(Float32(data=event["metres"]))
            self._sensor_update(**{f"{event['side']}_distance": event["metres"]})
        elif kind == "collision":
            self._publishers[kind][event["side"]].publish(Bool(data=event["active"]))
            state = "blocked" if event["active"] else "safe"
            self._publishers["collision_status"].publish(String(data=state))
            self._sensor_update(**{f"{event['side']}_collision": event["active"]})
        elif kind == "vision":
            self._publishers["person_present"].publish(Bool(data=event["person_present"]))
            self._publishers["vision"].publish(String(data=event["emotion"]))
            self._publishers["person_distance"].publish(Float32(data=event["metres"]))
            self._sensor_update(
                person_present=event["person_present"],
                emotion=event["emotion"],
                person_distance=event["metres"],
            )

    def destroy_node(self):
        self._drain_timer.cancel()
        self._graph_timer.cancel()
        self._httpd.shutdown()
        self._httpd.server_close()
        self._http_thread.join(timeout=2.0)
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SimulatorDashboard()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
