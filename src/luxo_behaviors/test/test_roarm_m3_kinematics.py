import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from luxo_behaviors.roarm_m3_kinematics import (
    LUXO_TO_M3,
    M3_JOINT_LIMITS,
    M3_JOINT_NAMES,
    compute_m3_fk,
    map_luxo_joints_to_m3,
)


def test_mapping_matches_vendor_driver_order_and_leaves_roll_gripper_at_home():
    mapped = map_luxo_joints_to_m3(
        {
            "base_to_L1": 0.1,
            "L1_to_L2": -0.2,
            "L2_to_L3": 0.3,
            "L3_to_L4": -0.4,
        }
    )
    assert list(mapped) == list(M3_JOINT_NAMES)
    assert tuple(LUXO_TO_M3.values()) == M3_JOINT_NAMES[:4]
    assert [mapped[name] for name in M3_JOINT_NAMES] == pytest.approx(
        [0.1, -0.2, 0.3, -0.4, 0.0, 0.0]
    )


def test_preview_clamps_shared_axes_to_vendor_m3_limits_only():
    mapped = map_luxo_joints_to_m3(
        {"L2_to_L3": 3.1, "L3_to_L4": 2.0}
    )
    assert mapped["link2_to_link3"] == pytest.approx(2.95)
    assert mapped["link3_to_link4"] == pytest.approx(1.5708)
    assert mapped["link4_to_link5"] == 0.0
    assert mapped["link5_to_gripper_link"] == 0.0


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_m3_preview_rejects_nonfinite_shared_joint_values(value):
    with pytest.raises(ValueError, match="finite"):
        map_luxo_joints_to_m3({"L1_to_L2": value})


def test_neutral_fk_matches_official_vendor_joint_origins_and_tcp():
    frames = compute_m3_fk({})
    assert frames["base_link"] == pytest.approx((0, 0, 0.0701))
    assert frames["link2"] == pytest.approx((0, 0, 0.122059))
    assert frames["link4"] == pytest.approx((0.03000113, 0, 0.50346011), abs=2e-6)
    assert frames["hand_tcp"][2] == pytest.approx(0.67254111, abs=2e-6)


def test_m3_fk_base_yaw_rotates_points_about_vendor_base_axis():
    frames = compute_m3_fk({"base_link_to_link1": math.pi / 2})
    assert frames["link4"][0] == pytest.approx(0, abs=2e-6)
    assert frames["link4"][1] == pytest.approx(0.03000113, abs=2e-6)


def test_constants_match_pinned_vendor_xacro_limits_and_six_revolute_joint_names():
    xacro = (
        Path(__file__).parents[1]
        / "luxo_behaviors"
        / "assets"
        / "roarm_m3"
        / "roarm_m3.xacro"
    )
    root = ET.parse(xacro).getroot()
    revolute = {joint.attrib["name"]: joint for joint in root.findall("joint") if joint.attrib["type"] == "revolute"}
    assert set(revolute) == set(M3_JOINT_NAMES)
    for name, (lower, upper) in M3_JOINT_LIMITS.items():
        limit = revolute[name].find("limit")
        assert float(limit.attrib["lower"]) == pytest.approx(lower)
        assert float(limit.attrib["upper"]) == pytest.approx(upper)
