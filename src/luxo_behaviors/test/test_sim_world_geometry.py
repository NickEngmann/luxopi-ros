"""ROS-free tests for the simulator's bounded synthetic obstacle rays."""

import math

import numpy as np
import pytest

from luxo_behaviors.sim_world_geometry import raycast_fixture, transform_mount, validate_obstacles


def test_nearest_box_or_sphere_hit_is_measured_in_metres():
    obstacles = validate_obstacles([
        {"name": "box", "shape": "box", "center_m": [1.0, 0.0, 0.0], "half_extents_m": [0.1, 0.2, 0.2]},
        {"name": "sphere", "shape": "sphere", "center_m": [0.5, 0.0, 0.0], "radius_m": 0.1},
    ])

    assert raycast_fixture([0, 0, 0], [10, 0, 0], obstacles, 2.0) == pytest.approx(0.4)
    assert raycast_fixture([0, 0, 0], [0, 1, 0], obstacles, 2.0) is None


def test_inside_box_is_immediate_hit_and_max_range_clips_distant_hit():
    box = validate_obstacles([
        {"name": "near", "shape": "box", "center_m": [0, 0, 0], "half_extents_m": [0.1, 0.1, 0.1]},
        {"name": "far", "shape": "sphere", "center_m": [1.0, 0, 0], "radius_m": 0.1},
    ])

    assert raycast_fixture([0, 0, 0], [1, 0, 0], box, 2.0) == pytest.approx(0.0)
    assert raycast_fixture([0.2, 0.2, 0], [1, 0, 0], box[1:], 0.5) is None


def test_mount_ray_rotates_and_translates_from_measured_body_pose():
    angle = math.pi / 2
    rotation = np.asarray([
        [math.cos(angle), -math.sin(angle), 0],
        [math.sin(angle), math.cos(angle), 0],
        [0, 0, 1],
    ])
    origin, direction = transform_mount(
        [1, 2, 3], rotation, [0.1, 0, 0], [1, 0, 0]
    )

    assert origin == pytest.approx((1.0, 2.1, 3.0))
    assert direction == pytest.approx((0.0, 1.0, 0.0))


@pytest.mark.parametrize("obstacles", [
    "not a list",
    [{"name": "dup", "shape": "sphere", "center_m": [0, 0, 0], "radius_m": 0.1}] * 2,
    [{"name": "bad", "shape": "box", "center_m": [0, 0, 0], "half_extents_m": [1, 0, 1]}],
    [{"name": "bad", "shape": "sphere", "center_m": [0, 0, float("nan")], "radius_m": 0.1}],
])
def test_invalid_fixture_scene_is_rejected(obstacles):
    with pytest.raises(ValueError):
        validate_obstacles(obstacles)


def test_ray_requires_finite_bounded_geometry_and_nonzero_direction():
    with pytest.raises(ValueError):
        raycast_fixture([0, 0, 0], [0, 0, 0], (), 1.0)
    with pytest.raises(ValueError):
        raycast_fixture([6, 0, 0], [1, 0, 0], (), 1.0)
