"""Optional MuJoCo model and measured-feedback servo tests."""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("mujoco")

from luxo_behaviors.gazebo_description import build_vendor_description
from luxo_behaviors.joint_profiles import ROARM_M3_NAMES
from luxo_behaviors.mujoco_runtime import build_m3_model, servo_torque


ASSETS = Path(__file__).parents[1] / "luxo_behaviors/assets/roarm_m3"


def make_model():
    return build_m3_model(
        build_vendor_description(ASSETS), ASSETS, timestep=0.002, effort_limit=3.0
    )


def test_vendor_m3_geometry_and_inertias_load_with_only_mount_contact_excluded():
    mujoco, model, joints = make_model()
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    assert model.nq == model.nv == len(ROARM_M3_NAMES) == 6
    assert model.ngeom == 14
    assert [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint) for joint in joints] == list(ROARM_M3_NAMES)
    assert np.count_nonzero(model.geom_contype) >= 6
    assert np.all(model.body_mass[1:] > 0.0)
    assert data.ncon == 0


def test_gravity_compensated_full_mass_matrix_servo_tracks_six_measured_axes():
    mujoco, model, joints = make_model()
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    qpos = [int(model.jnt_qposadr[joint]) for joint in joints]
    dofs = [int(model.jnt_dofadr[joint]) for joint in joints]
    actuators = [
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, f"servo_{name}")
        for name in ROARM_M3_NAMES
    ]
    target = np.asarray([0.2, 0.2, 0.2, -0.1, -0.3, 0.2])

    for _ in range(500):
        data.ctrl[actuators] = servo_torque(
            mujoco, model, data, target, qpos, dofs,
            omega=25.0, damping_ratio=1.0, effort_limit=3.0,
        )
        mujoco.mj_step(model, data)

    measured = np.asarray([data.qpos[index] for index in qpos])
    assert np.isfinite(measured).all()
    assert np.max(np.abs(measured - target)) < 0.003
    assert data.ncon == 0


def test_servo_rejects_nonfinite_or_invalid_controller_parameters():
    mujoco, model, joints = make_model()
    data = mujoco.MjData(model)
    qpos = [int(model.jnt_qposadr[joint]) for joint in joints]
    dofs = [int(model.jnt_dofadr[joint]) for joint in joints]

    with pytest.raises(ValueError):
        servo_torque(mujoco, model, data, [float("nan")] * 6, qpos, dofs)
    with pytest.raises(ValueError):
        servo_torque(mujoco, model, data, [0.0] * 6, qpos, dofs, omega=float("nan"))
