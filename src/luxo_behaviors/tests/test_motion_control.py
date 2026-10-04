"""Regression coverage for per-goal animation cancellation."""

import unittest

from luxo_behaviors.motion_control import AnimationGoalTracker


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


if __name__ == "__main__":
    unittest.main()
