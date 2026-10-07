"""Optional MuJoCo model and measured-feedback servo tests."""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("mujoco")

from luxo_behaviors.gazebo_description import build_vendor_description
from luxo_behaviors.joint_profiles import ROARM_M3_NAMES
from luxo_behaviors.mujoco_runtime import (
    build_m3_model,
    servo_torque,
    set_virtual_obstacle_contacts,
)


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
    assert model.ngeom == 22
    geom_names = {
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, index)
        for index in range(model.ngeom)
    }
    assert {
        "desk_top",
        "desk_leg_front_left",
        "desk_leg_front_right",
        "desk_leg_back_left",
        "desk_leg_back_right",
        "virtual_obstacle_front",
        "virtual_obstacle_left",
        "virtual_obstacle_right",
    } <= geom_names
    assert [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint) for joint in joints] == list(ROARM_M3_NAMES)
    assert np.count_nonzero(model.geom_contype) >= 6
    assert np.all(model.body_mass[1:] > 0.0)
    assert data.ncon == 0
    for side in ("front", "left", "right"):
        geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"virtual_obstacle_{side}")
        assert model.geom_contype[geom] == model.geom_conaffinity[geom] == 0


def test_virtual_obstacle_stimulus_enables_and_releases_matching_physics_collider():
    mujoco, model, _joints = make_model()
    set_virtual_obstacle_contacts(mujoco, model, {"front": True, "left": False, "right": False})
    for side in ("front", "left", "right"):
        geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"virtual_obstacle_{side}")
        expected = int(side == "front")
        assert model.geom_contype[geom] == expected
        assert model.geom_conaffinity[geom] == expected

    set_virtual_obstacle_contacts(mujoco, model, {"front": False, "left": True, "right": False})
    left = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "virtual_obstacle_left")
    assert model.geom_contype[left] == model.geom_conaffinity[left] == 1
    set_virtual_obstacle_contacts(mujoco, model, {"front": False, "left": False, "right": False})

    with pytest.raises(ValueError):
        set_virtual_obstacle_contacts(mujoco, model, {"front": 1})
    with pytest.raises(ValueError):
        set_virtual_obstacle_contacts(mujoco, model, {"unknown": True})


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
