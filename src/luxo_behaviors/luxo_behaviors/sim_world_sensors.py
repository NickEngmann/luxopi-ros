"""Synthetic world-obstacle rays publishing the real collision node's inputs.

This node is for simulation only. Sensor mounts/proximity scaling are fixture
parameters and are not claims about Luxo's physical sensor extrinsics.
"""

import json
import math
import time

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32, Int16, String, UInt8

from luxo_behaviors.joint_profiles import ROARM_M3_LIMITS, ROARM_M3_NAMES
from luxo_behaviors.mujoco_runtime import build_m3_model
from luxo_behaviors.sim_world_geometry import raycast_fixture, transform_mount, validate_obstacles


DEFAULT_MOUNTS = {
    # The RoArm M3 model has no head/camera frame. Use the distal gripper link
    # as an explicit synthetic head/end-effector proxy so the rays follow the
    # model's actual pose; replace these extrinsics for calibrated hardware.
    # In the vendor's zero pose, gripper_link local +Z points along base +X.
    "front": {"frame": "gripper_link", "offset_m": [0.0, 0.0, 0.02], "direction": [0.0, 0.0, 1.0], "max_range_m": 0.25},
    "left": {"frame": "gripper_link", "offset_m": [0.0, 0.02, 0.02], "direction": [0.0, -1.0, 0.0], "max_range_m": 0.80},
    "right": {"frame": "gripper_link", "offset_m": [0.0, -0.02, 0.02], "direction": [0.0, 1.0, 0.0], "max_range_m": 0.80},
}
JOINT_FEEDBACK_LIMIT_TOLERANCE = 0.02


def validate_mounts(mounts):
    if not isinstance(mounts, dict) or set(mounts) != {"front", "left", "right"}:
        raise ValueError("sensor mounts must define exactly front, left, and right")
    validated = {}
    for direction, mount in mounts.items():
        if not isinstance(mount, dict):
            raise ValueError(f"{direction} mount must be an object")
        frame = mount.get("frame")
        if frame not in {"base_link", "link1", "link2", "link3", "link4", "link5", "gripper_link"}:
            raise ValueError(f"{direction} mount has unknown M3 link frame")
        offset = np.asarray(mount.get("offset_m"), dtype=np.float64)
        direction_vector = np.asarray(mount.get("direction"), dtype=np.float64)
        if offset.shape != (3,) or direction_vector.shape != (3,):
            raise ValueError(f"{direction} mount offset and direction must be 3-vectors")
        if not np.isfinite(offset).all() or not np.isfinite(direction_vector).all():
            raise ValueError(f"{direction} mount values must be finite")
        if np.max(np.abs(offset)) > 1.0:
            raise ValueError(f"{direction} mount offset exceeds the synthetic 1 m bound")
        magnitude = float(np.linalg.norm(direction_vector))
        if magnitude <= 1e-12 or magnitude > 5.0:
            raise ValueError(f"{direction} mount direction must be non-zero and bounded")
        max_range = float(mount.get("max_range_m"))
        if not math.isfinite(max_range) or not 0.01 <= max_range <= 1.2:
            raise ValueError(f"{direction} max_range_m must be within 0.01..1.2 m")
        validated[direction] = {
            "frame": frame,
            "offset_m": offset,
            "direction": direction_vector / magnitude,
            "max_range_m": max_range,
        }
    return validated


class SimWorldSensors(Node):
    """Use actual M3 feedback transforms to synthesize distinct raw samples."""

    def __init__(self, *, parameter_overrides=None):
        super().__init__("sim_world_sensors", parameter_overrides=parameter_overrides)
        self.declare_parameter("robot_description_file", "/tmp/luxopi-m3.urdf")
        self.declare_parameter("asset_directory", "")
        self.declare_parameter("obstacles_json", "[]")
        self.declare_parameter("sensor_mounts_json", json.dumps(DEFAULT_MOUNTS, separators=(",", ":")))
        self.declare_parameter("publish_rate", 20.0)
        self.declare_parameter("feedback_timeout", 0.5)
        self.declare_parameter("front_proximity_range_m", 0.12)

        publish_rate = float(self.get_parameter("publish_rate").value)
        self.feedback_timeout = float(self.get_parameter("feedback_timeout").value)
        self.front_proximity_range = float(self.get_parameter("front_proximity_range_m").value)
        if not math.isfinite(publish_rate) or not 1.0 <= publish_rate <= 50.0:
            raise ValueError("publish_rate must be within 1..50 Hz")
        if not math.isfinite(self.feedback_timeout) or self.feedback_timeout <= 0.0:
            raise ValueError("feedback_timeout must be finite and positive")
        if not math.isfinite(self.front_proximity_range) or not 0.01 <= self.front_proximity_range <= 1.0:
            raise ValueError("front_proximity_range_m must be within 0.01..1 m")

        assets_value = str(self.get_parameter("asset_directory").value).strip()
        from pathlib import Path
        import luxo_behaviors
        assets = Path(assets_value or Path(luxo_behaviors.__file__).parent / "assets/roarm_m3").resolve()
        description_path = Path(str(self.get_parameter("robot_description_file").value)).resolve()
        if not assets.is_dir() or not description_path.is_file():
            raise ValueError("M3 sensor fixture requires the vendor assets and generated URDF")
        self.obstacles = validate_obstacles(json.loads(str(self.get_parameter("obstacles_json").value)))
        self.mounts = validate_mounts(json.loads(str(self.get_parameter("sensor_mounts_json").value)))
        self.sensor_faults = {direction: False for direction in ("front", "left", "right")}
        self.mujoco, self.model, self.joint_ids = build_m3_model(
            description_path.read_text(encoding="utf-8"), assets, timestep=0.002, effort_limit=3.0
        )
        self.data = self.mujoco.MjData(self.model)
        self.qpos_addresses = [int(self.model.jnt_qposadr[joint]) for joint in self.joint_ids]
        self.body_ids = {
            key: self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_BODY, mount["frame"])
            for key, mount in self.mounts.items()
        }
        if any(body_id < 0 for body_id in self.body_ids.values()):
            raise ValueError("one or more synthetic sensor mount links are absent from the M3 model")
        self.last_joint_feedback = None
        self.last_joint_feedback_at = 0.0

        self.create_subscription(JointState, "/joint_states", self.joint_callback, 10)
        self.create_subscription(String, "/sim/sensor_faults", self.sensor_fault_callback, 10)
        self.front_pub = self.create_publisher(Int16, "/i2c/apds9960/proximity", 10)
        self.left_pub = self.create_publisher(Float32, "/i2c/vl53_left/distance", 10)
        self.right_pub = self.create_publisher(Float32, "/i2c/vl53_right/distance", 10)
        # This fixture owns all raw obstacle inputs. Its geometric scene models
        # optical ranges, not tactile contact, so publish explicit no-contact
        # samples rather than silently bypass physical FSR freshness checks.
        self.contact_pubs = {
            name: self.create_publisher(UInt8, f"/touch_sensors/{name}", 10)
            for name in ("head_bottom", "head_left", "head_right")
        }
        self.status_pub = self.create_publisher(String, "/sim/world_sensor_status", 10)
        self.timer = self.create_timer(1.0 / publish_rate, self.publish_samples)
        self.get_logger().info(
            f"Synthetic obstacle rays ready: {len(self.obstacles)} fixture(s), "
            "mount extrinsics and proximity scaling are uncalibrated simulation parameters"
        )

    def sensor_fault_callback(self, message):
        """Apply dashboard range dropouts at the synthetic sensor source."""
        try:
            faults = json.loads(message.data)
            if (not isinstance(faults, dict) or set(faults) != set(self.sensor_faults)
                    or any(not isinstance(value, bool) for value in faults.values())):
                raise ValueError("expected front/left/right boolean fault map")
            self.sensor_faults = dict(faults)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.get_logger().warning(f"Ignoring invalid simulator sensor faults: {exc}")

    def joint_callback(self, message):
        if len(message.name) != len(ROARM_M3_NAMES) or len(message.position) != len(ROARM_M3_NAMES):
            return
        if set(message.name) != set(ROARM_M3_NAMES) or len(set(message.name)) != len(message.name):
            return
        by_name = dict(zip(message.name, message.position))
        values = [float(by_name[name]) for name in ROARM_M3_NAMES]
        if not all(math.isfinite(value) for value in values):
            return
        if any(
            value < ROARM_M3_LIMITS[name][0] - JOINT_FEEDBACK_LIMIT_TOLERANCE
            or value > ROARM_M3_LIMITS[name][1] + JOINT_FEEDBACK_LIMIT_TOLERANCE
            for name, value in zip(ROARM_M3_NAMES, values)
        ):
            return
        self.data.qpos[self.qpos_addresses] = values
        self.mujoco.mj_forward(self.model, self.data)
        self.last_joint_feedback = values
        self.last_joint_feedback_at = time.monotonic()

    def _world_ray(self, direction):
        mount = self.mounts[direction]
        body_id = self.body_ids[direction]
        rotation = self.data.xmat[body_id].reshape(3, 3)
        origin, vector = transform_mount(
            self.data.xpos[body_id], rotation, mount["offset_m"], mount["direction"]
        )
        return origin, vector

    def distance(self, direction):
        origin, vector = self._world_ray(direction)
        mount = self.mounts[direction]
        hit = raycast_fixture(origin, vector, self.obstacles, mount["max_range_m"])
        return mount["max_range_m"] if hit is None else hit

    def publish_samples(self):
        age = time.monotonic() - self.last_joint_feedback_at
        if self.last_joint_feedback is None or age > self.feedback_timeout:
            return
        distances = {direction: self.distance(direction) for direction in ("front", "left", "right")}
        front = Int16()
        front.data = max(0, min(255, round(255.0 * max(
            0.0, 1.0 - distances["front"] / self.front_proximity_range
        ))))
        if not self.sensor_faults["front"]:
            self.front_pub.publish(front)
        left = Float32()
        left.data = float(distances["left"] * 100.0)
        if not self.sensor_faults["left"]:
            self.left_pub.publish(left)
        right = Float32()
        right.data = float(distances["right"] * 100.0)
        if not self.sensor_faults["right"]:
            self.right_pub.publish(right)
        for publisher in self.contact_pubs.values():
            publisher.publish(UInt8(data=0))
        status = String()
        status.data = json.dumps({
            "simulated": True,
            "extrinsics_calibrated": False,
            "contact_model": "explicit no-contact fixture samples; no tactile physics",
            "joint_feedback_age_seconds": age,
            "front_proximity": front.data,
            "left_distance_cm": left.data,
            "right_distance_cm": right.data,
            "obstacle_names": [obstacle["name"] for obstacle in self.obstacles],
            "sensor_faults": self.sensor_faults,
        }, separators=(",", ":"), allow_nan=False)
        self.status_pub.publish(status)


def main(args=None):
    rclpy.init(args=args)
    node = SimWorldSensors()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
