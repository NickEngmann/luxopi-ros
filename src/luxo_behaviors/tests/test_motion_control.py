"""Regression coverage for per-goal animation cancellation."""

import unittest

from luxo_behaviors.motion_control import (
    AnimationGoalTracker, collision_status_from_warnings,
)


class TestCollisionStatusBridge(unittest.TestCase):
    def test_boolean_warning_does_not_invent_danger_severity(self):
        self.assertEqual(
            collision_status_from_warnings("safe", [False, True, False]),
            "safe",
        )

    def test_cleared_sensor_warnings_restore_legacy_status(self):
        self.assertEqual(
            collision_status_from_warnings("safe", [False, False, False]),
            "safe",
        )
        self.assertEqual(
            collision_status_from_warnings("danger", [False, False, False]),
            "danger",
        )


class FakeGoal:
    is_active = True


class TestAnimationGoalTracker(unittest.TestCase):
    def test_replacement_cancels_old_goal_without_clearing_new_goal(self):
        tracker = AnimationGoalTracker()
        first = FakeGoal()
        second = FakeGoal()

        first_event = tracker.accept(first)
        second_event = tracker.accept(second)

        self.assertTrue(first_event.is_set())
        self.assertFalse(second_event.is_set())

    def test_client_cancel_is_scoped_to_requested_goal(self):
        tracker = AnimationGoalTracker()
        first = FakeGoal()
        second = FakeGoal()
        first_event = tracker.accept(first)
        second_event = tracker.event_for(second)

        self.assertTrue(tracker.cancel(second))
        self.assertFalse(first_event.is_set())
        self.assertTrue(second_event.is_set())
        self.assertFalse(tracker.cancel(FakeGoal()))

    def test_finishing_old_goal_does_not_clear_current_goal(self):
        tracker = AnimationGoalTracker()
        first = FakeGoal()
        second = FakeGoal()
        tracker.accept(first)
        second_event = tracker.accept(second)

        tracker.finish(first)

        self.assertIs(tracker.event_for(second), second_event)
        self.assertFalse(second_event.is_set())

    def test_only_latest_goal_owns_shared_animation_state(self):
        tracker = AnimationGoalTracker()
        first = FakeGoal()
        second = FakeGoal()
        tracker.accept(first)
        self.assertTrue(tracker.is_current(first))
        tracker.accept(second)
        self.assertFalse(tracker.is_current(first))
        self.assertTrue(tracker.is_current(second))
        tracker.finish(first)
        self.assertTrue(tracker.is_current(second))


if __name__ == "__main__":
    unittest.main()
