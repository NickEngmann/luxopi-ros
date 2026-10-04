"""Offline tests for the shared joint position and slew-rate limiter."""

import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from luxo_behaviors.joint_motion import (  # noqa: E402
    JointMotionLimiter,
    clamp_joint_positions,
    format_target_positions,
    ordered_joint_target,
)


class TestJointMotionLimiter(unittest.TestCase):
    def test_clamps_targets_to_joint_limits(self):
        names = ["base_to_L1", "L1_to_L2"]
        self.assertEqual(clamp_joint_positions(names, [9, -9]), [3.14, -1.570796])

    def test_rejects_nan_and_wrong_shape(self):
        with self.assertRaises(ValueError):
            clamp_joint_positions(["base_to_L1"], [math.nan])
        with self.assertRaises(ValueError):
            clamp_joint_positions(["base_to_L1"], [0.0, 1.0])

    def test_named_target_requires_each_joint_once_and_in_finite_values(self):
        names = ["L2_to_L3", "base_to_L1", "L3_to_L4", "L1_to_L2"]
        positions = [0.3, 0.1, -0.2, 0.4]
        self.assertEqual(
            ordered_joint_target(names, positions),
            [0.1, 0.4, 0.3, -0.2],
        )
        with self.assertRaises(ValueError):
            ordered_joint_target(names + ["base_to_L1"], positions + [0.0])
        with self.assertRaises(ValueError):
            ordered_joint_target(names, [0.3, math.nan, -0.2, 0.4])

    def test_sim_joint_state_does_not_include_hardware_acceleration_metadata(self):
        target = [0.1, 0.2, 0.3, 0.4, -1.5, 10.0]
        sim = format_target_positions(
            target,
            ["base_to_L1", "L1_to_L2", "L2_to_L3", "L3_to_L4"],
        )
        hardware = format_target_positions(
            target, ["base", "shoulder", "elbow", "wrist", "hand"], True
        )
        self.assertEqual(sim, [0.1, 0.2, 0.3, 0.4])
        self.assertEqual(hardware, [0.1, 0.2, 0.3, 0.4, -1.5, 10.0])

    def test_applies_acceleration_and_velocity_limits(self):
        limiter = JointMotionLimiter(
            ["base_to_L1"], max_velocity=0.5, max_acceleration=1.0
        )
        previous_velocity = 0.0
        previous_position = 0.0
        for _ in range(20):
            position = limiter.step([2.0], 0.1)[0]
            velocity = limiter.velocities[0]
            self.assertLessEqual(abs(velocity), 0.5 + 1e-9)
            self.assertLessEqual(abs(velocity - previous_velocity), 0.1 + 1e-9)
            self.assertLessEqual(abs(position - previous_position), 0.05 + 1e-9)
            previous_velocity = velocity
            previous_position = position

    def test_slews_back_toward_target_after_reversal(self):
        limiter = JointMotionLimiter(
            ["base_to_L1"], initial_positions=[1.0],
            max_velocity=0.5, max_acceleration=1.0,
        )
        limiter.velocities[0] = 0.5
        first = limiter.step([-1.0], 0.1)[0]
        self.assertGreater(first, 1.0)
        self.assertAlmostEqual(limiter.velocities[0], 0.4)


if __name__ == "__main__":
    unittest.main()
