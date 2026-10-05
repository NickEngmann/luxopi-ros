"""MuJoCo model setup and torque control for the optional RoArm-M3 simulator.

The model geometry, inertias and joint bounds come from the pinned Waveshare
description. The servo gains and effort limits are simulator settings; they
are not claims about calibrated motor properties.
"""

from pathlib import Path
import math
import tempfile
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import numpy as np

from luxo_behaviors.joint_profiles import ROARM_M3_NAMES


def _mujoco_urdf(description_xml, asset_directory):
    """Rewrite only mesh paths and add MuJoCo compiler options to vendor URDF."""
    assets = Path(asset_directory).resolve()
    root = ET.fromstring(description_xml)
    for mesh in root.iter("mesh"):
        filename = mesh.get("filename", "")
        parsed = urlparse(filename)
        mesh_path = Path(parsed.path if parsed.scheme == "file" else filename)
        if mesh_path.is_absolute() and mesh_path.is_file():
            resolved = mesh_path.resolve()
        else:
            # The generated URDF may have been produced on another host/path;
            # resolve its known vendor mesh basename within this pinned asset set.
            resolved = (assets / mesh_path.name).resolve()
        if resolved.parent != assets or not resolved.is_file():
            raise ValueError(f"vendor mesh is missing or outside the model directory: {filename}")
        mesh.set("filename", resolved.name)

    compiler = root.find("mujoco/compiler")
    if compiler is None:
        mujoco = root.find("mujoco")
        if mujoco is None:
            mujoco = ET.SubElement(root, "mujoco")
        compiler = ET.SubElement(mujoco, "compiler")
    compiler.set("meshdir", str(assets))
    compiler.set("angle", "radian")
    compiler.set("balanceinertia", "true")
    compiler.set("discardvisual", "false")
    return ET.tostring(root, encoding="unicode")


def build_m3_model(description_xml, asset_directory, *, timestep=0.002, effort_limit=3.0):
    """Build authentic M3 geometry/inertias with bounded simulator-only motors."""
    if not math.isfinite(timestep) or not math.isfinite(effort_limit) or timestep <= 0 or effort_limit <= 0:
        raise ValueError("timestep and effort_limit must be positive")
    import mujoco

    # MjSpec selects URDF parsing by file extension, so keep the short-lived
    # normalized description in a .urdf file while compiling the model.
    with tempfile.TemporaryDirectory(prefix="luxopi-mujoco-") as temporary:
        description_path = Path(temporary) / "roarm_m3.urdf"
        description_path.write_text(
            _mujoco_urdf(description_xml, asset_directory), encoding="utf-8"
        )
        spec = mujoco.MjSpec.from_file(str(description_path))
        joints = {joint.name: joint for joint in spec.joints}
        if not set(ROARM_M3_NAMES).issubset(joints):
            raise ValueError("model is missing one or more canonical RoArm-M3 joints")

        # The vendor visual/collision meshes overlap at this fixed base mount.
        # Exclude that rigidly connected pair while retaining every other contact.
        spec.add_exclude(
            name="fixed_base_mount",
            bodyname1="world",
            bodyname2="link1",
            info="adjacent fixed vendor mount meshes overlap at their shared interface",
        )
        for name in ROARM_M3_NAMES:
            actuator = spec.add_actuator()
            actuator.name = f"servo_{name}"
            actuator.trntype = mujoco.mjtTrn.mjTRN_JOINT
            actuator.target = name
            actuator.gear = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            actuator.ctrllimited = True
            actuator.ctrlrange = [-effort_limit, effort_limit]
            actuator.forcelimited = True
            actuator.forcerange = [-effort_limit, effort_limit]

        model = mujoco.MjModel.from_xml_string(spec.to_xml())
    model.opt.timestep = float(timestep)
    model.opt.gravity[:] = (0.0, 0.0, -9.81)
    joint_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in ROARM_M3_NAMES]
    if any(joint_id < 0 for joint_id in joint_ids):
        raise ValueError("compiled model does not contain all six M3 joints")
    return mujoco, model, joint_ids


def servo_torque(mujoco, model, data, target, qpos_addresses, dof_addresses,
                 *, omega=25.0, damping_ratio=1.0, effort_limit=3.0):
    """Return clipped full-mass-matrix inverse-dynamics servo torques."""
    target = np.asarray(target, dtype=np.float64)
    qpos_addresses = np.asarray(qpos_addresses, dtype=np.int32)
    dof_addresses = np.asarray(dof_addresses, dtype=np.int32)
    if target.shape != qpos_addresses.shape or target.shape != dof_addresses.shape:
        raise ValueError("target and joint address arrays must have matching shapes")
    if (
        not np.isfinite(target).all()
        or not all(math.isfinite(value) and value > 0 for value in (omega, damping_ratio, effort_limit))
    ):
        raise ValueError("servo inputs must be finite and positive")

    mass_matrix = np.zeros((model.nv, model.nv), dtype=np.float64)
    mujoco.mj_fullM(model, data, mass_matrix)
    joint_mass = mass_matrix[np.ix_(dof_addresses, dof_addresses)]
    desired_acceleration = (
        omega * omega * (target - data.qpos[qpos_addresses])
        - 2.0 * damping_ratio * omega * data.qvel[dof_addresses]
    )
    torque = joint_mass @ desired_acceleration + data.qfrc_bias[dof_addresses]
    return np.clip(torque, -effort_limit, effort_limit)
