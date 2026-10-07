"""Optional MuJoCo check that fixture rays follow measured end-effector pose."""

from pathlib import Path

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")
pytest.importorskip("rclpy")

from luxo_behaviors.gazebo_description import build_vendor_description
from luxo_behaviors.joint_profiles import ROARM_M3_NAMES
from luxo_behaviors.mujoco_runtime import build_m3_model
from luxo_behaviors.sim_world_geometry import raycast_fixture, transform_mount
from luxo_behaviors.sim_world_sensors import DEFAULT_MOUNTS
from luxo_behaviors.reactive_avoidance import DEFAULT_RETREATS


ASSETS = Path(__file__).parents[1] / "luxo_behaviors/assets/roarm_m3"


def test_synthetic_end_effector_ray_tracks_actual_m3_base_yaw():
    engine, model, joints = build_m3_model(
        build_vendor_description(ASSETS), ASSETS, timestep=0.002, effort_limit=3.0
    )
    data = engine.MjData(model)
    qpos = [int(model.jnt_qposadr[joint]) for joint in joints]
    body = engine.mj_name2id(model, engine.mjtObj.mjOBJ_BODY, "gripper_link")
    assert body >= 0
    mount = DEFAULT_MOUNTS["front"]

    engine.mj_forward(model, data)
    origin, ray = transform_mount(
        data.xpos[body], data.xmat[body].reshape(3, 3), mount["offset_m"], mount["direction"]
    )
    obstacle = ({
        "name": "ahead_of_initial_end_effector",
        "shape": "sphere",
        "center_m": tuple(np.asarray(origin) + 0.30 * np.asarray(ray)),
        "dimensions_m": (0.04, 0.04, 0.04),
    },)
    assert raycast_fixture(origin, ray, obstacle, 0.5) == pytest.approx(0.26)

    # A real MuJoCo qpos change, not a hand-authored base transform, rotates
    # the distal frame and moves its ray away from the stationary obstacle.
    base_address = int(model.jnt_qposadr[joints[0]])
    data.qpos[base_address] = np.pi / 2
    engine.mj_forward(model, data)
    turned_origin, turned_ray = transform_mount(
        data.xpos[body], data.xmat[body].reshape(3, 3), mount["offset_m"], mount["direction"]
    )
    assert not np.allclose(ray, turned_ray)
    assert raycast_fixture(turned_origin, turned_ray, obstacle, 0.5) is None

    assert len(ROARM_M3_NAMES) == 6


@pytest.mark.parametrize(("side", "obstacle_y", "retreat_sign"), [
    ("left", 1.0, -1), ("right", -1.0, 1),
])
def test_side_warning_retreat_moves_gripper_away_in_robot_frame(side, obstacle_y, retreat_sign):
    engine, model, joints = build_m3_model(
        build_vendor_description(ASSETS), ASSETS, timestep=0.002, effort_limit=3.0
    )
    data = engine.MjData(model)
    body = engine.mj_name2id(model, engine.mjtObj.mjOBJ_BODY, "gripper_link")
    base_address = int(model.jnt_qposadr[joints[0]])
    engine.mj_forward(model, data)
    initial = data.xpos[body].copy()
    # ROS base coordinates: x is forward and y is left. Place a fixed hazard
    # just beyond the side of the distal gripper, independent of the ray test.
    obstacle = initial + np.array([0.0, obstacle_y * 0.14, 0.0])
    initial_distance = float(np.linalg.norm(initial - obstacle))
    data.qpos[base_address] = retreat_sign * 0.08
    engine.mj_forward(model, data)
    retreated = data.xpos[body].copy()
    assert DEFAULT_RETREATS[side]["sign"] == retreat_sign
    assert np.linalg.norm(retreated - obstacle) > initial_distance + 0.005
