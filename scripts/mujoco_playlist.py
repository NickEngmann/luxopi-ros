#!/usr/bin/env python3
"""Offline full-animation physics test for the pinned RoArm-M3 model.

Run inside the optional physics image. This uses the same animation registry,
profile mapping, and JointMotionLimiter as the live ROS graph, with no audio or
hardware. Output is evidence for the configured simulation servo, not motor
calibration data.
"""

import json
import math
import argparse
from pathlib import Path

import mujoco
import numpy as np

from luxo_behaviors.animation_capabilities import ANIMATION_CLASSES
from luxo_behaviors.gazebo_description import build_vendor_description
from luxo_behaviors.joint_motion import JointMotionLimiter
from luxo_behaviors.joint_profiles import (
    ROARM_M3_LIMITS,
    ROARM_M3_NAMES,
    animation_pose_for_profile,
    pose_to_animation_positions,
)
from luxo_behaviors.animation_plan import validate_animation_plan
from luxo_behaviors.mujoco_runtime import build_m3_model, servo_torque
from luxo_behaviors.trajectory_timing import retime_cubic_plan
from luxo_behaviors.continuous_trajectory import ContinuousTrajectory


class _QuietLogger:
    def debug(self, _message):
        pass


class _PluginNode:
    def get_logger(self):
        return _QuietLogger()


def run(asset_directory, *, physics_rate=500.0, command_rate=50.0,
        omega=25.0, damping_ratio=1.0, effort_limit=3.0,
        settling_timeout=4.0, settle_tolerance=0.02, settle_dwell=0.06,
        continuous=False):
    if physics_rate % command_rate:
        raise ValueError("physics_rate must be an integer multiple of command_rate")
    dt = 1.0 / physics_rate
    command_steps = round(physics_rate / command_rate)
    description = build_vendor_description(asset_directory)
    mj, model, joint_ids = build_m3_model(
        description, asset_directory, timestep=dt, effort_limit=effort_limit
    )
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    qpos = [int(model.jnt_qposadr[joint]) for joint in joint_ids]
    dofs = [int(model.jnt_dofadr[joint]) for joint in joint_ids]
    actuators = [
        mj.mj_name2id(model, mj.mjtObj.mjOBJ_ACTUATOR, f"servo_{name}")
        for name in ROARM_M3_NAMES
    ]
    limiter = JointMotionLimiter(
        ROARM_M3_NAMES,
        initial_positions=[float(data.qpos[index]) for index in qpos],
        limits=ROARM_M3_LIMITS,
        max_velocity=0.5,
        max_acceleration=1.0,
    )
    peaks = {
        "velocity": np.zeros(6),
        "torque": np.zeros(6),
        "servo_error": np.zeros(6),
        "command_lag": np.zeros(6),
        "settle_error": np.zeros(6),
    }
    saturated_ticks = 0
    contacts_peak = 0
    physics_ticks = 0
    action_durations = {}
    endpoint_error = np.zeros(6)
    target = [float(data.qpos[index]) for index in qpos]

    def advance(command):
        nonlocal saturated_ticks, contacts_peak, physics_ticks
        command_vector = np.asarray(command, dtype=np.float64)
        for _ in range(command_steps):
            torque = servo_torque(
                mj, model, data, command_vector, qpos, dofs,
                omega=omega, damping_ratio=damping_ratio, effort_limit=effort_limit,
            )
            data.ctrl[actuators] = torque
            mj.mj_step(model, data)
            physics_ticks += 1
            positions = np.asarray([data.qpos[index] for index in qpos])
            velocities = np.asarray([data.qvel[index] for index in dofs])
            if not np.isfinite(positions).all() or not np.isfinite(velocities).all():
                raise RuntimeError("MuJoCo produced non-finite joint feedback")
            for name, value in zip(ROARM_M3_NAMES, positions):
                low, high = ROARM_M3_LIMITS[name]
                if value < low - 0.02 or value > high + 0.02:
                    raise RuntimeError(f"{name} exceeded profile bounds: {value}")
            peaks["velocity"] = np.maximum(peaks["velocity"], np.abs(velocities))
            peaks["torque"] = np.maximum(peaks["torque"], np.abs(data.actuator_force[actuators]))
            peaks["servo_error"] = np.maximum(peaks["servo_error"], np.abs(command_vector - positions))
            saturated_ticks += int(np.any(np.abs(torque) >= effort_limit - 1e-9))
            contacts_peak = max(contacts_peak, int(data.ncon))

    def wait_for_settle(expected):
        deadline = physics_ticks * dt + settling_timeout
        stable_since = None
        while physics_ticks * dt < deadline:
            advance(limiter.step(expected, 1.0 / command_rate))
            measured = np.asarray([data.qpos[index] for index in qpos])
            velocity = np.asarray([data.qvel[index] for index in dofs])
            error = np.abs(np.asarray(expected) - measured)
            peaks["settle_error"] = np.maximum(peaks["settle_error"], error)
            settled = max(error) <= settle_tolerance and max(np.abs(velocity)) <= 0.02
            if settled:
                stable_since = physics_ticks * dt if stable_since is None else stable_since
                if physics_ticks * dt - stable_since >= settle_dwell:
                    return
            else:
                stable_since = None
        raise RuntimeError(
            f"six-axis pose failed to settle within {settling_timeout:g}s: "
            f"expected={list(expected)}, actual={[float(data.qpos[index]) for index in qpos]}"
        )

    for name, plugin_class in ANIMATION_CLASSES.items():
        action_started = physics_ticks * dt
        plugin = plugin_class(None)
        plugin.node = _PluginNode()
        frames, durations = validate_animation_plan(
            *plugin.get_keyframes(), keyframe_names=plugin.get_keyframe_names()
        )
        current = [float(data.qpos[index]) for index in qpos]
        current_animation = pose_to_animation_positions(ROARM_M3_NAMES, current)
        if not hasattr(plugin, "preserve_base_position") or plugin.preserve_base_position:
            frames = plugin.adjust_keyframes_to_current_base(frames, current_animation[0])
        frames = plugin.prepare_for_current_position(current_animation, frames)

        # Mirror AnimationCommandActionServer's actual M3 map and feasible cubic
        # retiming. The animation's sixth number is metadata, never a joint.
        bounded_frames = []
        for frame in frames:
            _, mapped = animation_pose_for_profile(
                frame, "roarm_m3", gripper_position=current[5]
            )
            bounded = list(frame)
            bounded[:5] = mapped[:5]
            bounded_frames.append(bounded)
        planner = ContinuousTrajectory if continuous else retime_cubic_plan
        plan = planner(
            current_animation,
            bounded_frames,
            durations,
            speed_multiplier=1.0,
            max_velocity=0.5,
            max_acceleration=1.0,
            axes=5,
        )
        durations = plan.durations if continuous else plan
        start = current
        for stage, (frame, duration) in enumerate(zip(bounded_frames, durations)):
            _, destination = animation_pose_for_profile(
                frame, "roarm_m3", gripper_position=current[5]
            )
            duration = float(duration)
            command_count = max(1, math.ceil(duration * command_rate))
            for index in range(command_count):
                progress = min(1.0, (index + 1) / command_count)
                eased = 4 * progress**3 if progress < 0.5 else 1 - (-2 * progress + 2) ** 3 / 2
                if continuous:
                    _, requested = animation_pose_for_profile(
                        plan.segment(stage, progress), 'roarm_m3', gripper_position=current[5],
                        enforce_animation_roll=False)
                else:
                    requested = [a + eased * (b - a) for a, b in zip(start, destination)]
                # Match sim_motion_controller: command trajectory is persistent.
                # Physics feedback is measured independently below and must not
                # reset the limiter on each timer tick, or the acceleration
                # ramp repeatedly restarts and motion becomes nearly stationary.
                bounded = limiter.step(requested, 1.0 / command_rate)
                peaks["command_lag"] = np.maximum(
                    peaks["command_lag"], np.abs(np.asarray(requested) - np.asarray(bounded))
                )
                advance(bounded)
            start = list(destination)
            if not continuous or stage == len(bounded_frames)-1:
                wait_for_settle(destination)
                endpoint_error = np.maximum(endpoint_error, np.abs(
                    np.asarray(destination) - np.asarray([data.qpos[index] for index in qpos])))
            current = [float(data.qpos[index]) for index in qpos]

        target = [float(data.qpos[index]) for index in qpos]
        action_durations[name] = round(physics_ticks * dt - action_started, 4)

    # Observe gravity hold and tracking after the authored playlist ends.
    for _ in range(round(command_rate * 2)):
        advance(target)

    return {
        "backend": "mujoco",
        "mujoco_version": mj.__version__,
        "animation_count": len(ANIMATION_CLASSES),
        "keyframe_count": sum(len(plugin_class(None).get_keyframes()[0]) for plugin_class in ANIMATION_CLASSES.values()),
        "physics_rate_hz": physics_rate,
        "command_rate_hz": command_rate,
        "simulation_duration_seconds": physics_ticks * dt,
        "feasible_retiming": ('continuous_trajectory.ContinuousTrajectory' if continuous else 'trajectory_timing.retime_cubic_plan'),
        "settlement_scope": 'final pose of each animation' if continuous else 'every waypoint',
        "action_durations_seconds": action_durations,
        "max_velocity_each_joint_rad_s": peaks["velocity"].tolist(),
        "max_effort_each_joint_nm": peaks["torque"].tolist(),
        "max_servo_tracking_error_each_joint_rad": peaks["servo_error"].tolist(),
        "max_animation_lag_after_shared_limiter_each_joint_rad": peaks["command_lag"].tolist(),
        "max_keyframe_settle_error_each_joint_rad": peaks["settle_error"].tolist(),
        "max_settled_endpoint_error_each_joint_rad": endpoint_error.tolist(),
        "effort_saturated_steps": saturated_ticks,
        "max_contacts": contacts_peak,
        "final_joint_positions": [float(data.qpos[index]) for index in qpos],
        "final_command": target,
    }


if __name__ == "__main__":
    import luxo_behaviors

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--assets",
        default=str(Path(luxo_behaviors.__file__).parent / "assets/roarm_m3"),
    )
    parser.add_argument("--output", default="-")
    parser.add_argument("--continuous", action='store_true')
    args = parser.parse_args()
    result = json.dumps(run(Path(args.assets), continuous=args.continuous), indent=2)
    if args.output == "-":
        print(result)
    else:
        Path(args.output).write_text(result + "\n", encoding="utf-8")
