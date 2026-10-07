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
        candidate = mesh_path.resolve() if mesh_path.is_absolute() else None
        if candidate is not None and candidate.parent == assets and candidate.is_file():
            resolved = candidate
        else:
            # Generated URDFs may contain another checkout's absolute install
            # path. Rebase by basename inside this explicitly selected model set.
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
        # Shared tabletop scene for collision and reach-envelope testing.  The
        # desk is fixed in world coordinates, below the M3 mounting plate, so
        # the same physics scene can be compared with the browser preview.
        desk = (
            ("desk_top", (0.0, 0.0, -0.026), (0.62, 0.46, 0.025)),
            ("desk_leg_front_left", (0.56, 0.40, -0.376), (0.035, 0.035, 0.325)),
            ("desk_leg_front_right", (0.56, -0.40, -0.376), (0.035, 0.035, 0.325)),
            ("desk_leg_back_left", (-0.56, 0.40, -0.376), (0.035, 0.035, 0.325)),
            ("desk_leg_back_right", (-0.56, -0.40, -0.376), (0.035, 0.035, 0.325)),
        )
        for name, position, half_extents in desk:
            spec.worldbody.add_geom(
                name=name,
                type=mujoco.mjtGeom.mjGEOM_BOX,
                pos=position,
                size=half_extents,
                rgba=[0.30, 0.19, 0.11, 1.0],
                contype=1,
                conaffinity=1,
            )
        # Conservative box colliders beneath the randomized STL props shown in
        # the browser. They are disabled until the matching virtual sensor is
        # activated by the dashboard.
        obstacle_colliders = (
            ("front", (0.34, 0.0, 0.074), (0.08, 0.08, 0.075)),
            ("left", (0.0, 0.31, 0.074), (0.08, 0.08, 0.075)),
            ("right", (0.0, -0.31, 0.074), (0.08, 0.08, 0.075)),
        )
        for side, position, half_extents in obstacle_colliders:
            spec.worldbody.add_geom(
                name=f"virtual_obstacle_{side}",
                type=mujoco.mjtGeom.mjGEOM_BOX,
                pos=position,
                size=half_extents,
                rgba=[1.0, 0.42, 0.12, 0.0],
                contype=0,
                conaffinity=0,
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


def set_virtual_obstacle_contacts(mujoco, model, active):
    """Enable the MuJoCo proxy collider for each active virtual STL obstacle."""
    sides = ("front", "left", "right")
    if not isinstance(active, dict) or set(active) - set(sides):
        raise ValueError("virtual obstacles must be a front/left/right mapping")
    if any(type(value) is not bool for value in active.values()):
        raise ValueError("virtual obstacle values must be booleans")
    for side in sides:
        geom_id = mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_GEOM, f"virtual_obstacle_{side}"
        )
        if geom_id < 0:
            raise ValueError(f"model is missing virtual {side} obstacle collider")
        enabled = int(active.get(side, False))
        model.geom_contype[geom_id] = enabled
        model.geom_conaffinity[geom_id] = enabled


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
