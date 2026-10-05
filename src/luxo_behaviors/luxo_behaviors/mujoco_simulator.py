"""MuJoCo-backed M3 simulator publishing measured ROS joint states."""

import json
import math
from pathlib import Path
import time

import numpy as np
import rclpy
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import JointState
from std_msgs.msg import String

from luxo_behaviors.joint_motion import ordered_joint_target, clamp_joint_positions
from luxo_behaviors.joint_profiles import ROARM_M3_NAMES, ROARM_M3_LIMITS
from luxo_behaviors.mujoco_runtime import build_m3_model, servo_torque


class MujocoSimulator(Node):
    """Run vendor M3 inertias/collisions and publish actual MuJoCo feedback."""

    def __init__(self):
        super().__init__("mujoco_simulator")
        self.declare_parameter("robot_description_file", "/tmp/luxopi-m3.urdf")
        self.declare_parameter("asset_directory", "")
        self.declare_parameter("physics_rate", 500.0)
        self.declare_parameter("servo_omega", 25.0)
        self.declare_parameter("damping_ratio", 1.0)
        self.declare_parameter("effort_limit", 3.0)
        self.declare_parameter("command_timeout", 0.5)
        self.declare_parameter("feedback_rate", 50.0)
        self.declare_parameter("command_topic", "/sim/bounded_joint_command")
        self.declare_parameter("joint_states_topic", "/joint_states")
        self.declare_parameter("status_topic", "/sim/physics_status")

        self.physics_rate = float(self.get_parameter("physics_rate").value)
        self.feedback_rate = float(self.get_parameter("feedback_rate").value)
        self.omega = float(self.get_parameter("servo_omega").value)
        self.damping_ratio = float(self.get_parameter("damping_ratio").value)
        self.effort_limit = float(self.get_parameter("effort_limit").value)
        self.command_timeout = float(self.get_parameter("command_timeout").value)
        if not all(math.isfinite(value) for value in (
            self.physics_rate, self.feedback_rate, self.omega,
            self.damping_ratio, self.effort_limit, self.command_timeout,
        )):
            raise ValueError("MuJoCo rate, servo, effort, and timeout parameters must be finite")
        if not 100.0 <= self.physics_rate <= 1000.0:
            raise ValueError("physics_rate must be between 100 and 1000 Hz")
        if not 1.0 <= self.feedback_rate <= self.physics_rate:
            raise ValueError("feedback_rate must be positive and no greater than physics_rate")
        if self.omega <= 0.0 or self.damping_ratio <= 0.0 or self.effort_limit <= 0.0:
            raise ValueError("servo_omega, damping_ratio, and effort_limit must be positive")
        if self.command_timeout <= 0.0:
            raise ValueError("command_timeout must be positive")

        configured_assets = str(self.get_parameter("asset_directory").value).strip()
        asset_directory = Path(configured_assets or Path(__file__).parent / "assets/roarm_m3").resolve()
        if not asset_directory.is_dir():
            raise ValueError(f"RoArm-M3 asset directory does not exist: {asset_directory}")
        description_file = Path(str(self.get_parameter("robot_description_file").value)).resolve()
        if not description_file.is_file():
            raise ValueError(f"generated vendor M3 description is missing: {description_file}")
        description = description_file.read_text(encoding="utf-8")
        self.mujoco, self.model, self.joint_ids = build_m3_model(
            description,
            asset_directory,
            timestep=1.0 / self.physics_rate,
            effort_limit=self.effort_limit,
        )
        self.data = self.mujoco.MjData(self.model)
        self.mujoco.mj_forward(self.model, self.data)
        self.qpos_addresses = [int(self.model.jnt_qposadr[j]) for j in self.joint_ids]
        self.dof_addresses = [int(self.model.jnt_dofadr[j]) for j in self.joint_ids]
        self.actuator_ids = [
            self.mujoco.mj_name2id(
                self.model, self.mujoco.mjtObj.mjOBJ_ACTUATOR, f"servo_{name}"
            )
            for name in ROARM_M3_NAMES
        ]
        self.target = [0.0] * len(ROARM_M3_NAMES)
        self.last_target_time = time.monotonic()
        self.started_at = self.last_target_time
        self.simulation_time = 0.0
        self.command_stale = False
        self.ticks = 0
        self.saturated_ticks = 0
        self.max_tick_seconds = 0.0
        self.last_contacts = 0

        self.joint_pub = self.create_publisher(
            JointState, str(self.get_parameter("joint_states_topic").value), 10
        )
        self.status_pub = self.create_publisher(
            String, str(self.get_parameter("status_topic").value), 10
        )
        self.command_sub = self.create_subscription(
            JointState,
            str(self.get_parameter("command_topic").value),
            self.command_callback,
            10,
        )
        self.steps_per_feedback = max(1, round(self.physics_rate / self.feedback_rate))
        self.timer = self.create_timer(1.0 / self.physics_rate, self.step)
        self.get_logger().info(
            f"MuJoCo M3 ready: {self.model.njnt} joints, {self.model.ngeom} vendor geoms, "
            f"{self.physics_rate:g} Hz physics / {self.feedback_rate:g} Hz feedback. "
            "Vendor geometry/inertias are retained; servo settings are simulator parameters."
        )

    def command_callback(self, message):
        try:
            values = ordered_joint_target(message.name, message.position, ROARM_M3_NAMES)
            self.target = clamp_joint_positions(ROARM_M3_NAMES, values, ROARM_M3_LIMITS)
            self.last_target_time = time.monotonic()
            self.command_stale = False
        except (TypeError, ValueError) as exc:
            self.get_logger().warning(f"Ignored malformed bounded M3 command: {exc}")

    def step(self):
        started = time.perf_counter()
        try:
            if time.monotonic() - self.last_target_time > self.command_timeout and not self.command_stale:
                self.target = [float(self.data.qpos[index]) for index in self.qpos_addresses]
                self.command_stale = True
                self.get_logger().warning("Bounded joint command stale; holding measured MuJoCo pose")
            torque = servo_torque(
                self.mujoco,
                self.model,
                self.data,
                self.target,
                self.qpos_addresses,
                self.dof_addresses,
                omega=self.omega,
                damping_ratio=self.damping_ratio,
                effort_limit=self.effort_limit,
            )
            self.data.ctrl[self.actuator_ids] = torque
            self.mujoco.mj_step(self.model, self.data)
            positions = [float(self.data.qpos[index]) for index in self.qpos_addresses]
            velocities = [float(self.data.qvel[index]) for index in self.dof_addresses]
            if not all(math.isfinite(value) for value in positions + velocities + list(torque)):
                raise FloatingPointError("MuJoCo produced non-finite joint state or effort")
            for name, value in zip(ROARM_M3_NAMES, positions):
                lower, upper = ROARM_M3_LIMITS[name]
                if value < lower - 0.02 or value > upper + 0.02:
                    raise RuntimeError(f"MuJoCo joint {name} exceeded vendor limits: {value}")
            self.ticks += 1
            self.simulation_time += 1.0 / self.physics_rate
            self.last_contacts = int(self.data.ncon)
            tick_seconds = time.perf_counter() - started
            self.max_tick_seconds = max(self.max_tick_seconds, tick_seconds)
            self.saturated_ticks += int(any(abs(value) >= self.effort_limit - 1e-9 for value in torque))

            if self.ticks % self.steps_per_feedback == 0:
                self.publish_feedback(torque)
        except Exception as exc:
            self.get_logger().fatal(f"MuJoCo dynamics failed; stopping the critical simulation process: {exc}")
            raise

    def publish_feedback(self, torque):
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = list(ROARM_M3_NAMES)
        message.position = [float(self.data.qpos[index]) for index in self.qpos_addresses]
        message.velocity = [float(self.data.qvel[index]) for index in self.dof_addresses]
        message.effort = [float(value) for value in self.data.actuator_force[self.actuator_ids]]
        self.joint_pub.publish(message)

        status = String()
        status.data = json.dumps({
            "backend": "mujoco",
            "profile": "roarm_m3",
            "physics_rate": self.physics_rate,
            "feedback_rate": self.feedback_rate,
            "simulated": True,
            "simulation_time_seconds": self.simulation_time,
            "wall_time_seconds": time.monotonic() - self.started_at,
            "real_time_factor": self.simulation_time / max(1e-9, time.monotonic() - self.started_at),
            "joint_positions": list(message.position),
            "joint_velocities": list(message.velocity),
            "joint_efforts": list(message.effort),
            "target": self.target,
            "contact_count": self.last_contacts,
            "torque_saturated": any(abs(value) >= self.effort_limit - 1e-9 for value in torque),
            "max_step_seconds": self.max_tick_seconds,
            "command_age_seconds": max(0.0, time.monotonic() - self.last_target_time),
            "command_stale": self.command_stale,
            "saturated_ticks": self.saturated_ticks,
        }, separators=(",", ":"), allow_nan=False, default=self._json_value)
        self.status_pub.publish(status)

    @staticmethod
    def _json_value(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(f"unsupported physics status value: {type(value).__name__}")


def main(args=None):
    rclpy.init(args=args)
    node = MujocoSimulator()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
