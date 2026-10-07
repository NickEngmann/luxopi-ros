"""Local browser control panel for a ROS-only Luxo simulation."""

import json
import re
import queue
import threading
import time
import os
import uuid
from collections import OrderedDict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import rclpy
from ament_index_python.packages import get_package_share_directory
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile
from luxo_interfaces.action import PlayAnimation
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float32, Int16, String, UInt8
from luxo_interfaces.srv import RequestStateTransition

from luxo_behaviors.simulator_protocol import (
    MANUAL_JOINT_LIMITS,
    MAX_AUDIO_BYTES,
    MAX_EVENT_BYTES,
    MAX_VISION_IMAGE_BYTES,
    ANIMATION_NAMES,
    normalize_event,
    normalize_vision_result,
    summarize_simulator_health,
    valid_joint_feedback,
    camera_input_publications,
    event_fingerprint,
    prune_expired_request_ids,
)
from luxo_behaviors.roarm_m3_kinematics import M3_JOINT_LIMITS, M3_JOINT_NAMES


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
    """Bounded HTTP/ROS bridge with optional private image inference forwarding."""

    def __init__(self):
        super().__init__("simulator_dashboard")
        self.declare_parameter("host", "0.0.0.0")
        self.declare_parameter("port", 8080)
        self.declare_parameter("audio_directory", "")
        self.declare_parameter("tts_directory", "")
        self.declare_parameter("simulation_backend", "kinematic")
        host = self.get_parameter("host").value
        port = int(self.get_parameter("port").value)
        self._audio_directory = str(self.get_parameter("audio_directory").value).strip()
        self._tts_directory = str(self.get_parameter("tts_directory").value).strip()
        self._audio_upload_enabled = bool(self._audio_directory)
        self._vision_url = os.environ.get("LUXOPI_VISION_URL", "").strip()
        if not 1 <= port <= 65535:
            raise ValueError("port must be in the range 1..65535")

        self._events = queue.Queue(maxsize=64)
        self._event_ingress_lock = threading.Lock()
        self._event_request_ids = OrderedDict()
        self._event_audit = deque(maxlen=100)
        self._event_ingress_counts = {"accepted": 0, "duplicates": 0, "rejected": 0, "queue_full": 0}
        self._mesh_dir = Path(get_package_share_directory("roarm")) / "meshes"
        self._animation_client = ActionClient(self, PlayAnimation, "play_animation")
        self._active_animation_goal = None
        self._animation_generation = 0
        self._animation_goal_pending = False
        self._cancel_animation_when_accepted = False
        self._state_client = self.create_client(
            RequestStateTransition, "/luxo/request_state_transition"
        )
        self._manual_target_publisher = self.create_publisher(
            JointState, "/sim/manual_joint_target", 10
        )
        self._pending_manual_target = None
        self._manual_generation = 0
        self._manual_granted = False
        self._manual_deadline = 0.0
        self._simulated_obstacles = {side: False for side in ("front", "left", "right")}
        self._simulated_sensor_faults = {side: False for side in ("front", "left", "right")}
        self._world_sensor_faults_pub = self.create_publisher(String, "/sim/sensor_faults", 10)
        self._obstacle_samples_until = 0.0
        self._lock = threading.Lock()
        self._snapshot = {
            "simulation_backend": str(self.get_parameter("simulation_backend").value),
            "state": "INITIALIZING",
            "animation": "",
            "status": "idle",
            "transcript": "",
            "response": "",
            "audio_response": "",
            "joint_names": [],
            "positions": [],
            "direction": None,
            "direction_evidence": {},
            "voice_active": False,
            "motion": {},
            "physics": {},
            "simulation_speed": 1.0,
            "sensors": {"simulator_autonomy_enabled": False},
            "graph_nodes": [],
        }

        # Do not shadow rclpy.node.Node._publishers, which is an internal list
        # consumed by Node.destroy_node().
        self._event_publishers = {
            "voice_command": self.create_publisher(String, "/voice/command", 10),
            "audio_file": self.create_publisher(String, "/voice/audio_file", 10),
            "audio_direction": self.create_publisher(Float32, "/sim/audio_direction", 10),
            "simulation_speed": self.create_publisher(Float32, "/sim/time_scale", 10),
            "simulator_autonomy": self.create_publisher(Bool, "/sim/autonomy_enabled", 10),
            "touch": {
                name: self.create_publisher(UInt8, f"/touch_sensors/{name}", 10)
                for name in ("head_top", "head_left", "head_bottom", "head_right")
            },
            "petting_zone": {
                zone: self.create_publisher(Bool, f"/sim/petting_zones/{zone}", 10)
                for zone in ("top_front", "antenna")
            },
            "gesture": self.create_publisher(String, "/i2c/apds9960/gesture", 10),
            "proximity": self.create_publisher(Int16, "/i2c/apds9960/proximity", 10),
            "distance": {
                side: self.create_publisher(Float32, f"/i2c/vl53_{side}/distance", 10)
                for side in ("left", "right")
            },
            "vision": self.create_publisher(String, "/sim/camera/emotion", 10),
            "person_distance": self.create_publisher(
                Float32, "/sim/camera/person_distance", 10
            ),
            "person_present": self.create_publisher(
                Bool, "/sim/camera/person_present", 10
            ),
            "light_control": self.create_publisher(Bool, "/luxo/light_control", 10),
            "brightness": self.create_publisher(String, "/luxo/brightness_control", 10),
            "color_temperature": self.create_publisher(String, "/luxo/color_temp_control", 10),
            "light_color": self.create_publisher(String, "/luxo/color_control", 10),
            "environment_obstacles": self.create_publisher(
                String, "/sim/environment_obstacles", 10
            ),
        }

        self.create_subscription(String, "/luxo/current_state", self._state_cb, 10)
        self.create_subscription(String, "/roarm/current_animation", self._animation_cb, 10)
        self.create_subscription(JointState, "/joint_states", self._joint_cb, 10)
        self.create_subscription(String, "/sim/motion_status", self._motion_status_cb, 10)
        self.create_subscription(String, "/sim/physics_status", self._physics_status_cb, 10)
        self.create_subscription(String, "/voice/transcript", self._transcript_cb, 10)
        self.create_subscription(String, "/voice/response", self._response_cb, 10)
        self.create_subscription(String, "/voice/audio_response", self._audio_response_cb, 10)
        self.create_subscription(String, "/voice/status", self._status_cb, 10)
        self.create_subscription(Float32, "/voice/follow_direction", self._direction_cb, 10)
        self.create_subscription(Bool, "/voice/active", self._active_cb, 10)
        self.create_subscription(
            Bool,
            "/sim/autonomy_status",
            self._autonomy_status_cb,
            QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            ),
        )
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
        self.create_subscription(Bool, "/camera/person_present", self._person_present_cb, 10)
        self.create_subscription(String, "/luxo/light_state", self._light_state_cb, 10)
        self.create_subscription(
            String, "/sim/interaction_status", self._interaction_status_cb, 10
        )

        self._drain_timer = self.create_timer(0.02, self._drain_events)
        self._obstacle_timer = self.create_timer(0.1, self._publish_simulated_obstacle_samples)
        self._graph_timer = self.create_timer(1.0, self._refresh_graph)
        self._httpd = self._create_server(host, port)
        self._http_thread = threading.Thread(
            target=self._httpd.serve_forever, name="simulator-dashboard-http", daemon=True
        )
        self._http_thread.start()
        self.get_logger().info(f"Simulation dashboard listening at http://{host}:{port}")

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
                if path.startswith("/api/audio-response/"):
                    self._get_audio_response(path.rsplit("/", 1)[-1])
                elif path == "/healthz":
                    snapshot = node.get_snapshot()
                    health = snapshot["health"]
                    code = 200 if health["healthy"] else 503
                    self._reply(code, json.dumps({"healthy": health["healthy"], "health": health}))
                elif path == "/":
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
                    m3_mesh_files = {
                        "roarm_m3/base_link.stl",
                        "roarm_m3/link1.stl",
                        "roarm_m3/link2.stl",
                        "roarm_m3/link3.stl",
                        "roarm_m3/link4.stl",
                        "roarm_m3/link5.stl",
                        "roarm_m3/gripper_link.stl",
                    }
                    prop_mesh_files = {
                        f"simulator_props/{name}.stl"
                        for name in ("crate", "wedge", "can", "cone", "rock")
                    }
                    if relative in vendor_files:
                        target = (Path(__file__).with_name("assets") / relative).resolve()
                    elif relative in mesh_files:
                        target = (node._mesh_dir / Path(relative).name).resolve()
                    elif relative in m3_mesh_files:
                        target = (Path(__file__).with_name("assets") / relative).resolve()
                    elif relative in prop_mesh_files:
                        target = (Path(__file__).with_name("assets") / relative).resolve()
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
                elif path == "/api/diagnostics":
                    snapshot = node.get_snapshot()
                    self._reply(200, json.dumps({
                        "healthy": snapshot["health"]["healthy"],
                        "health": snapshot["health"],
                        "event_ingress": snapshot["event_ingress"],
                    }))
                else:
                    self._reply(404, json.dumps({"error": "not found"}))

            def do_POST(self):
                request_path = urlparse(self.path).path
                if request_path == "/api/audio":
                    self._post_audio()
                    return
                if request_path == "/api/vision":
                    self._post_vision()
                    return
                if request_path != "/api/events":
                    self._reply(404, json.dumps({"error": "not found"}))
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > MAX_EVENT_BYTES:
                        raise ValueError("request size must be between 1 and 4096 bytes")
                    raw = self.rfile.read(length)
                    event = normalize_event(json.loads(raw.decode("utf-8")))
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    node._record_ingress("rejected", "invalid", detail=str(exc))
                    self._reply(400, json.dumps({"error": str(exc)}))
                    return
                event_id = event.get("request_id")
                fingerprint = event_fingerprint(event) if event_id else None
                with node._event_ingress_lock:
                    node._prune_request_ids_locked()
                    if event_id in node._event_request_ids:
                        previous = node._event_request_ids[event_id][0]
                        if previous != fingerprint:
                            node._event_ingress_counts["rejected"] += 1
                            node._record_ingress_locked(
                                "rejected", event["type"], event_id,
                                detail="request_id reused with different event",
                            )
                            self._reply(409, json.dumps({"error": "request_id was already used for a different event", "event_id": event_id}))
                            return
                        node._event_ingress_counts["duplicates"] += 1
                        node._record_ingress_locked("duplicate", event["type"], event_id)
                        self._reply(202, json.dumps({"accepted": True, "duplicate": True, "event_id": event_id}))
                        return
                    try:
                        node._events.put_nowait(event)
                    except queue.Full:
                        node._event_ingress_counts["queue_full"] += 1
                        node._event_ingress_counts["rejected"] += 1
                        node._record_ingress_locked("rejected", event["type"], event_id, detail="queue_full")
                        self._reply(429, json.dumps({"error": "simulator event queue is full"}))
                        return
                    if event_id:
                        node._event_request_ids[event_id] = (fingerprint, time.monotonic())
                        node._event_request_ids.move_to_end(event_id)
                        while len(node._event_request_ids) > 1024:
                            node._event_request_ids.popitem(last=False)
                    node._event_ingress_counts["accepted"] += 1
                    node._record_ingress_locked("accepted", event["type"], event_id)
                response = {"accepted": True}
                if event_id:
                    response["event_id"] = event_id
                self._reply(202, json.dumps(response))

            def _post_vision(self):
                if not node._vision_url:
                    self._reply(503, json.dumps({"error": "local vision inference is not configured"}))
                    return
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type not in {"image/jpeg", "image/png"}:
                    self._reply(415, json.dumps({"error": "Content-Type must be image/jpeg or image/png"}))
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length <= 0 or length > MAX_VISION_IMAGE_BYTES:
                    self._reply(413, json.dumps({"error": "image must be between 1 byte and 8 MiB"}))
                    return
                body = self.rfile.read(length)
                if len(body) != length:
                    self._reply(400, json.dumps({"error": "incomplete image upload"}))
                    return
                request = Request(node._vision_url, data=body,
                                  headers={"Content-Type": content_type}, method="POST")
                try:
                    with urlopen(request, timeout=45.0) as response:
                        result = json.loads(response.read(256 * 1024).decode("utf-8"))
                    event = normalize_vision_result(result)
                except HTTPError as exc:
                    self._reply(502, json.dumps({"error": f"vision service returned HTTP {exc.code}"}))
                    return
                except (URLError, TimeoutError, OSError):
                    self._reply(503, json.dumps({"error": "local vision service is unavailable"}))
                    return
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    self._reply(502, json.dumps({"error": f"invalid vision result: {exc}"}))
                    return
                try:
                    node._events.put_nowait(event)
                except queue.Full:
                    self._reply(429, json.dumps({"error": "simulator event queue is full"}))
                    return
                self._reply(202, json.dumps({"accepted": True, "vision": event}))

            def _post_audio(self):
                if not node._audio_upload_enabled:
                    self._reply(400, json.dumps({"error": "audio upload is disabled"}))
                    return
                if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "audio/wav":
                    self._reply(400, json.dumps({"error": "Content-Type must be audio/wav"}))
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length <= 0 or length > MAX_AUDIO_BYTES:
                    self._reply(400, json.dumps({"error": "audio size must be between 1 byte and 8 MiB"}))
                    return
                body = self.rfile.read(length)
                if len(body) != length:
                    self._reply(400, json.dumps({"error": "incomplete audio upload"}))
                    return
                try:
                    name = node._save_audio(body)
                    event = normalize_event({"type": "audio_file", "name": name})
                except (ValueError, OSError) as exc:
                    self._reply(400, json.dumps({"error": str(exc)}))
                    return
                try:
                    node._events.put_nowait(event)
                except queue.Full:
                    # The helper returns a validated UUID basename, so remove only
                    # the file created by this rejected request.
                    try:
                        from luxo_behaviors.audio_input import remove_audio

                        remove_audio(name, node._audio_directory)
                    except (OSError, ValueError) as exc:
                        node.get_logger().warning(f"could not remove rejected upload {name}: {exc}")
                    self._reply(429, json.dumps({"error": "simulator event queue is full"}))
                    return
                self._reply(202, json.dumps({"accepted": True, "name": name}))

            def _get_audio_response(self, name):
                if not node._tts_directory or not re.fullmatch(r"reply-[0-9a-f]{32}\.wav", name):
                    self._reply(404, json.dumps({"error": "audio response not found"}))
                    return
                target = (Path(node._tts_directory) / name).resolve()
                if (target.parent != Path(node._tts_directory).resolve()
                        or not target.is_file() or target.stat().st_size > 16 * 1024 * 1024):
                    self._reply(404, json.dumps({"error": "audio response not found"}))
                    return
                self._reply_bytes(200, target.read_bytes(), "audio/wav")

        return ThreadingHTTPServer((host, port), Handler)

    def get_snapshot(self):
        with self._lock:
            result = dict(self._snapshot)
            result["sensors"] = dict(self._snapshot["sensors"])
            joint_names = set(result.get("joint_names", []))
            result["aura"] = self._aura_color(result)
            result["health"] = summarize_simulator_health(result, time.monotonic())
            result.pop("_state_received_monotonic", None)
            result.pop("_joints_received_monotonic", None)
            result.pop("_joint_feedback_valid", None)
            result["audio_upload"] = self._audio_upload_enabled
            with self._event_ingress_lock:
                result["event_ingress"] = {
                    **self._event_ingress_counts,
                    "queue_depth": self._events.qsize(),
                    "queue_capacity": self._events.maxsize,
                    "request_id_cache_size": len(self._event_request_ids),
                    "recent": list(self._event_audit),
                }
            result["animation_names"] = sorted(ANIMATION_NAMES)
            if joint_names == set(M3_JOINT_NAMES):
                limits = M3_JOINT_LIMITS
            elif joint_names == set(MANUAL_JOINT_LIMITS):
                limits = MANUAL_JOINT_LIMITS
            else:
                limits = {}
            result["joint_limits"] = {
                name: list(bounds) for name, bounds in limits.items()
            }
            return result

    def _record_ingress(self, outcome, kind, event_id=None, detail=None):
        with self._event_ingress_lock:
            if outcome == "rejected":
                self._event_ingress_counts["rejected"] += 1
            self._record_ingress_locked(outcome, kind, event_id, detail)

    def _record_ingress_locked(self, outcome, kind, event_id=None, detail=None):
        entry = {"at_monotonic": round(time.monotonic(), 3), "outcome": outcome, "type": kind}
        if event_id:
            entry["request_id"] = event_id
        if detail:
            entry["detail"] = str(detail)[:160]
        self._event_audit.append(entry)

    def _prune_request_ids_locked(self):
        # Ordered insertion is enough for bounded replay protection. Old IDs
        # age out after one hour even if the cache never reaches its size cap.
        # Store timestamps alongside hashes without exposing them in snapshots.
        prune_expired_request_ids(self._event_request_ids, time.monotonic())

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
        self._update(state=msg.data, _state_received_monotonic=time.monotonic())

    def _animation_cb(self, msg):
        self._update(animation=msg.data)

    def _joint_cb(self, msg):
        if not valid_joint_feedback(list(msg.name), list(msg.position)):
            self._update(_joint_feedback_valid=False)
            return
        self._update(
            _joint_feedback_valid=True,
            joint_names=list(msg.name),
            positions=list(msg.position),
            _joints_received_monotonic=time.monotonic(),
        )

    def _transcript_cb(self, msg):
        self._update(transcript=msg.data)

    def _response_cb(self, msg):
        self._update(response=msg.data)

    def _audio_response_cb(self, msg):
        if re.fullmatch(r"reply-[0-9a-f]{32}\.wav", msg.data):
            self._update(audio_response=msg.data)

    def _status_cb(self, msg):
        self._update(status=msg.data)

    def _direction_cb(self, msg):
        self._update(direction=float(msg.data))

    def _active_cb(self, msg):
        self._update(voice_active=bool(msg.data))

    def _autonomy_status_cb(self, msg):
        self._sensor_update(simulator_autonomy_enabled=bool(msg.data))

    def _motion_status_cb(self, msg):
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            data = {"error": "motion status was not valid JSON"}
        self._update(motion=data)

    def _physics_status_cb(self, msg):
        try:
            data = json.loads(msg.data)
            if not isinstance(data, dict) or data.get("backend") != "mujoco":
                return
        except (TypeError, json.JSONDecodeError):
            data = {"error": "physics status was not valid JSON"}
        self._update(physics=data)

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

    def _person_present_cb(self, msg):
        if msg.data:
            self._sensor_update(person_present=True)
        else:
            self._sensor_update(person_present=False, emotion=None, person_distance=None)

    def _light_state_cb(self, msg):
        try:
            state = json.loads(msg.data)
        except json.JSONDecodeError:
            state = {"error": "light-state telemetry was not valid JSON"}
        self._sensor_update(light_state=state)

    def _interaction_status_cb(self, msg):
        try:
            state = json.loads(msg.data)
            if isinstance(state, dict):
                self._sensor_update(
                    interaction_status=state,
                    petting_zones=state.get("petting_zones", []),
                )
        except (TypeError, json.JSONDecodeError):
            self._sensor_update(interaction_status={"error": "invalid interaction telemetry"})

    def _sensor_update(self, **values):
        with self._lock:
            self._snapshot["sensors"].update(values)

    def _drain_events(self):
        self._flush_manual_target()
        for _ in range(32):
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return
            try:
                self._publish_event(event)
            except Exception as exc:  # An invalid action future must not kill the ROS node.
                self.get_logger().error(f"simulator event failed ({event.get('type')}): {exc}")
                self._sensor_update(last_event_error=str(exc))

    def _publish_simulated_obstacle_samples(self):
        """Publish held virtual ranges through the physical sensor classifier."""
        now = time.monotonic()
        if (not any(self._simulated_obstacles.values())
                and not any(self._simulated_sensor_faults.values())
                and now > self._obstacle_samples_until):
            return
        active = self._simulated_obstacles
        if not self._simulated_sensor_faults["front"]:
            self._event_publishers["proximity"].publish(
                Int16(data=22 if active["front"] else 0)
            )
        for side in ("left", "right"):
            if not self._simulated_sensor_faults[side]:
                self._event_publishers["distance"][side].publish(
                    Float32(data=10.0 if active[side] else 100.0)
                )
        # The geometric obstacle control does not represent physical contact.
        # Keep the classifier's three corresponding FSR coverage inputs fresh
        # and explicitly clear while the optical sensor reports the obstacle.
        for sensor in ("head_bottom", "head_left", "head_right"):
            self._event_publishers["touch"][sensor].publish(UInt8(data=0))

    def _save_audio(self, body):
        from luxo_behaviors.audio_input import save_audio

        return save_audio(body, self._audio_directory)

    def _publish_event(self, event):
        kind = event["type"]
        if kind == "state_request":
            request = RequestStateTransition.Request()
            request.requested_state = event["state"]
            request.requesting_node = ("home_return:" + uuid.uuid4().hex if event["state"] == "RETURNING_HOME"
                                       else "simulator_dashboard")
            request.priority = 50
            request.force = True
            request.completion = False
            self._sensor_update(state_request_result={"pending": event["state"]})
            if not self._state_client.service_is_ready():
                self._sensor_update(
                    state_request_result={"success": False, "message": "state service unavailable"}
                )
                return
            self._state_client.call_async(request).add_done_callback(
                lambda future: self._state_request_done(future, event["state"])
            )
        elif kind == "manual_joint_target":
            self._manual_generation += 1
            generation = self._manual_generation
            self._manual_granted = False
            self._manual_deadline = time.monotonic() + 3.0
            self._pending_manual_target = dict(event["positions"])
            request = RequestStateTransition.Request()
            request.requested_state = "USER_CONTROL"
            request.requesting_node = "simulator_dashboard"
            request.priority = 50
            request.force = True
            request.completion = False
            if not self._state_client.service_is_ready():
                self._pending_manual_target = None
                self._sensor_update(
                    manual_pose_result={"success": False, "message": "state service unavailable"}
                )
                return
            self._state_client.call_async(request).add_done_callback(
                lambda future: self._manual_state_request_done(future, generation)
            )
        elif kind == "animation":
            if not self._animation_client.server_is_ready():
                self._sensor_update(animation_error="play_animation action server unavailable")
                return
            goal = PlayAnimation.Goal()
            goal.animation_name = event["name"]
            goal.speed_multiplier = event["speed"]
            goal.allow_interruption = True
            goal.use_hardware_feedback = False
            self._animation_generation += 1
            generation = self._animation_generation
            self._animation_goal_pending = True
            self._cancel_animation_when_accepted = False
            self._sensor_update(
                animation_request=event["name"],
                animation_speed=event["speed"],
                animation_error="",
                animation_cancel_result=None,
                animation_result=None,
            )
            self._active_animation_goal = None
            self._animation_client.send_goal_async(goal).add_done_callback(
                lambda future: self._animation_goal_response(future, generation)
            )
        elif kind == "cancel_animation":
            handle = self._active_animation_goal
            if handle is not None and handle.accepted:
                generation = self._animation_generation
                handle.cancel_goal_async().add_done_callback(
                    lambda future: self._animation_cancel_response(future, generation)
                )
                self._sensor_update(animation_cancel_requested=True)
            elif self._animation_goal_pending:
                # Action goal acceptance is asynchronous. Remember a cancel
                # pressed during that window and apply it as soon as ROS
                # returns the accepted goal handle.
                self._cancel_animation_when_accepted = True
                self._sensor_update(
                    animation_cancel_requested=True,
                    animation_cancel_result=None,
                )
            else:
                self._sensor_update(animation_cancel_requested=False)
        elif kind == "voice_command":
            self._event_publishers[kind].publish(String(data=event["text"]))
            self._sensor_update(last_voice_command=event["text"])
        elif kind == "audio_file":
            self._event_publishers[kind].publish(String(data=event["name"]))
            self._sensor_update(last_audio_file=event["name"])
        elif kind == "audio_direction":
            self._event_publishers[kind].publish(Float32(data=event["degrees"]))
            self._sensor_update(requested_mic_direction=event["degrees"])
        elif kind == "simulation_speed":
            self._event_publishers[kind].publish(Float32(data=event["scale"]))
            self._update(simulation_speed=event["scale"])
            self._sensor_update(simulation_speed=event["scale"])
        elif kind == "simulator_autonomy":
            self._event_publishers[kind].publish(Bool(data=event["enabled"]))
        elif kind == "touch":
            self._event_publishers[kind][event["sensor"]].publish(UInt8(data=event["value"]))
            self._sensor_update(**{event["sensor"]: event["value"]})
        elif kind == "petting_zone":
            self._event_publishers[kind][event["zone"]].publish(Bool(data=event["active"]))
            self._sensor_update(
                petting_zone_requested={"zone": event["zone"], "active": event["active"]}
            )
        elif kind == "gesture":
            self._event_publishers[kind].publish(String(data=event["gesture"]))
            self._sensor_update(gesture=event["gesture"])
        elif kind == "proximity":
            # The production collision path validates distinct fresh samples,
            # not repeated timer reads; send two DDS samples for one UI event.
            self._event_publishers[kind].publish(Int16(data=event["value"]))
            self._event_publishers[kind].publish(Int16(data=event["value"]))
            self._sensor_update(proximity=event["value"])
        elif kind == "distance":
            publisher = self._event_publishers[kind][event["side"]]
            # Dashboard/API distances are metres; the physical VL53 topics
            # and shared collision classifier use centimetres.
            centimetres = event["metres"] * 100.0
            publisher.publish(Float32(data=centimetres))
            publisher.publish(Float32(data=centimetres))
            self._sensor_update(**{f"{event['side']}_distance": event["metres"]})
        elif kind == "collision":
            # Publish synthetic raw range samples, not a warning-only Bool:
            # the latter has no valid sensor coverage/severity for safe motion.
            self._simulated_obstacles[event["side"]] = event["active"]
            self._obstacle_samples_until = time.monotonic() + (0.0 if event["active"] else 1.5)
            self._event_publishers["environment_obstacles"].publish(
                String(data=json.dumps(self._simulated_obstacles, separators=(",", ":")))
            )
            self._sensor_update(simulated_obstacles=dict(self._simulated_obstacles))
            self._sensor_update(**{f"{event['side']}_collision": event["active"]})
        elif kind == "sensor_fault":
            self._simulated_sensor_faults[event["side"]] = event["active"]
            self._obstacle_samples_until = time.monotonic() + 1.5
            self._world_sensor_faults_pub.publish(
                String(data=json.dumps(self._simulated_sensor_faults, separators=(",", ":")))
            )
            self._sensor_update(simulated_sensor_faults=dict(self._simulated_sensor_faults))
        elif kind == "vision":
            for output, value in camera_input_publications(event):
                if output == "person_present":
                    self._event_publishers[output].publish(Bool(data=value))
                elif output == "emotion":
                    self._event_publishers["vision"].publish(String(data=value))
                else:
                    self._event_publishers["person_distance"].publish(Float32(data=value))
            self._sensor_update(vision_request=dict(
                person_present=event["person_present"],
                emotion=event["emotion"],
                person_distance=event["metres"],
            ))
        elif kind == "vision_inference":
            self._event_publishers["person_present"].publish(
                Bool(data=event["person_present"])
            )
            if event["person_present"]:
                self._event_publishers["vision"].publish(String(data=event["emotion"]))
            self._sensor_update(
                vision_inference={
                    "person_present": event["person_present"],
                    "emotion": event["emotion"],
                    "face_count": event["face_count"],
                    "distance_meters": None,
                }
            )
        elif kind == "light_control":
            self._event_publishers[kind].publish(Bool(data=event["enabled"]))
            self._sensor_update(light_control_requested=event["enabled"])
        elif kind == "brightness":
            self._event_publishers[kind].publish(String(data=f"brightness:{event['value']:.3f}"))
            self._sensor_update(brightness_requested=event["value"])
        elif kind == "color_temperature":
            self._event_publishers[kind].publish(String(data=f"color_temp:{event['value']:.3f}"))
            self._sensor_update(color_temperature_requested=event["value"])
        elif kind == "light_color":
            self._event_publishers[kind].publish(String(data=f"color:{event['color']}"))
            self._sensor_update(light_color_requested=event["color"])

    def _sensor_snapshot(self, key):
        with self._lock:
            return self._snapshot["sensors"].get(key)

    def _animation_goal_response(self, future, generation):
        try:
            handle = future.result()
        except Exception as exc:
            if generation == self._animation_generation:
                self._animation_goal_pending = False
                self._sensor_update(animation_error=f"animation goal failed: {exc}")
            return
        if generation != self._animation_generation:
            if handle.accepted:
                handle.cancel_goal_async()
            return
        self._animation_goal_pending = False
        if not handle.accepted:
            self._sensor_update(animation_error="animation goal rejected")
            self._sensor_update(animation_cancel_requested=False)
            self._cancel_animation_when_accepted = False
            return
        self._active_animation_goal = handle
        self._sensor_update(animation_cancel_requested=False, animation_error="")
        handle.get_result_async().add_done_callback(
            lambda result_future: self._animation_result(result_future, handle, generation)
        )
        if self._cancel_animation_when_accepted:
            self._cancel_animation_when_accepted = False
            handle.cancel_goal_async().add_done_callback(
                lambda cancel_future: self._animation_cancel_response(
                    cancel_future, generation
                )
            )
            self._sensor_update(animation_cancel_requested=True)

    def _animation_cancel_response(self, future, generation):
        try:
            response = future.result()
            accepted = bool(response.goals_canceling)
            result = {
                "accepted": accepted,
                "message": "cancel accepted" if accepted else "goal was not active",
            }
        except Exception as exc:
            result = {"accepted": False, "message": str(exc)}
        if generation == self._animation_generation:
            self._sensor_update(
                animation_cancel_result=result,
                animation_cancel_requested=False,
            )

    def _animation_result(self, future, handle, generation):
        try:
            wrapped = future.result()
            result = wrapped.result
            if generation == self._animation_generation:
                self._sensor_update(animation_result={
                    "success": bool(result.success),
                    "message": result.message,
                    "duration": float(result.actual_duration),
                    "state": result.final_state,
                }, animation_cancel_requested=False)
        except Exception as exc:
            if generation == self._animation_generation:
                self._sensor_update(animation_error=f"animation result failed: {exc}")
        finally:
            if self._active_animation_goal is handle:
                self._active_animation_goal = None
                if generation == self._animation_generation:
                    self._sensor_update(animation_cancel_requested=False)

    def _state_request_done(self, future, requested_state):
        try:
            response = future.result()
            result = {
                "success": bool(response.success),
                "state": response.current_state,
                "message": response.message,
                "requested": requested_state,
            }
        except Exception as exc:
            result = {"success": False, "message": f"state request failed: {exc}"}
        self._sensor_update(state_request_result=result)

    def _manual_state_request_done(self, future, generation):
        if generation != self._manual_generation:
            return
        try:
            response = future.result()
            if not response.success or response.current_state != "USER_CONTROL":
                self._pending_manual_target = None
                self._sensor_update(manual_pose_result={
                    "success": False, "state": response.current_state,
                    "message": response.message,
                })
                return
            # A service response does not mean the motion consumer has received
            # the state topic yet. Wait for its status acknowledgment.
            self._manual_granted = True
        except Exception as exc:
            self._pending_manual_target = None
            self._sensor_update(manual_pose_result={"success": False, "message": str(exc)})

    def _flush_manual_target(self):
        positions = self._pending_manual_target
        if not positions:
            return
        if time.monotonic() > self._manual_deadline:
            self._pending_manual_target = None
            self._sensor_update(manual_pose_result={
                "success": False, "message": "motion consumer did not acknowledge USER_CONTROL",
            })
            return
        with self._lock:
            acknowledged = (self._snapshot["state"] == "USER_CONTROL"
                            and self._snapshot["motion"].get("state") == "USER_CONTROL")
        if not self._manual_granted or not acknowledged:
            return
        message = JointState()
        message.header.frame_id = f"manual:{self._manual_generation}"
        message.name = list(positions)
        message.position = list(positions.values())
        self._manual_target_publisher.publish(message)
        self._sensor_update(manual_pose_result={
            "success": True, "state": "USER_CONTROL",
            "message": "pose sent through the simulator motion controller",
            "positions": positions,
        })
        self._pending_manual_target = None

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
