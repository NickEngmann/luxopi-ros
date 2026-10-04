import math

import pytest

from luxo_behaviors.robot_kinematics import compute_urdf_fk


def test_neutral_fk_matches_urdf_joint_origins_and_l4_visual_extent():
    frames = compute_urdf_fk({})
    assert frames["shoulder"] == pytest.approx((0.0, 0.0, 0.03796))
    assert frames["elbow"] == pytest.approx((0.03, 0.0, 0.27478))
    assert frames["wrist"] == pytest.approx((0.03, 0.0, 0.49077))
    assert frames["tip"] == pytest.approx((0.03, 0.0, 0.5586206))


def test_base_yaw_rotates_the_robot_in_xy_plane():
    frames = compute_urdf_fk({"base_to_L1": math.pi / 2})
    assert frames["elbow"][0] == pytest.approx(0.0, abs=1e-9)
    assert frames["elbow"][1] == pytest.approx(0.03)
    assert frames["elbow"][2] == pytest.approx(0.27478)


def test_shoulder_pitch_moves_downstream_frames_from_urdf_axis():
    frames = compute_urdf_fk({"L1_to_L2": math.pi / 2})
    assert frames["elbow"] == pytest.approx((0.23682, 0.0, 0.00796))
    assert frames["wrist"][2] == pytest.approx(frames["elbow"][2])


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_nonfinite_joint_values_are_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        compute_urdf_fk({"L1_to_L2": value})
