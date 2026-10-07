"""Tests for reporting real asynchronous state-service results."""

import pathlib
import sys
import threading
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from luxo_behaviors.transition_requests import watch_transition_result  # noqa: E402

sys.modules.setdefault("rclpy", MagicMock())
sys.modules.setdefault("rclpy.action", MagicMock())
sys.modules.setdefault("std_msgs", MagicMock())
sys.modules.setdefault("std_msgs.msg", MagicMock())
sys.modules.setdefault("luxo_interfaces", MagicMock())
sys.modules.setdefault("luxo_interfaces.action", MagicMock())
sys.modules.setdefault("luxo_interfaces.srv", MagicMock())
from luxo_behaviors.command_behavior import CommandBehavior  # noqa: E402
from luxo_behaviors.state_machine import LuxoState  # noqa: E402


class FakeFuture:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.callback = None

    def add_done_callback(self, callback):
        self.callback = callback

    def result(self):
        if self._error:
            raise self._error
        return self._result

    def finish(self):
        self.callback(self)


class TestTransitionRequestResult(unittest.TestCase):
    def test_returns_pending_future_and_logs_acceptance_when_completed(self):
        future = FakeFuture(MagicMock(success=True, current_state="IDLE"))
        logger = MagicMock()
        outcome = MagicMock()

        returned = watch_transition_result(future, "IDLE", logger, on_result=outcome)
        self.assertIs(returned, future)
        logger.debug.assert_not_called()
        outcome.assert_not_called()
        future.finish()
        logger.debug.assert_called_once()
        outcome.assert_called_once_with(True)

    def test_logs_denial_instead_of_reporting_queued_request_as_success(self):
        future = FakeFuture(MagicMock(success=False, message="safety priority"))
        logger = MagicMock()
        outcome = MagicMock()

        watch_transition_result(future, "ANIMATING", logger, on_result=outcome)
        future.finish()

        logger.warning.assert_called_once()
        self.assertIn("safety priority", logger.warning.call_args.args[0])
        outcome.assert_called_once_with(False)


class TestAsyncBehaviorGate(unittest.TestCase):
    def make_behavior(self):
        behavior = CommandBehavior.__new__(CommandBehavior)
        behavior.node = MagicMock()
        behavior.command_in_progress = False
        behavior._get_current_state = lambda: LuxoState.IDLE
        return behavior

    def test_user_command_waits_for_actual_service_acceptance(self):
        behavior = self.make_behavior()
        transition_callbacks = []
        behavior._transition_to_state = lambda state, on_result: transition_callbacks.append(
            (state, on_result)
        )
        outcomes = []

        CommandBehavior._request_user_control_state(behavior, outcomes.append)

        self.assertEqual(transition_callbacks[0][0], LuxoState.USER_CONTROL)
        self.assertFalse(behavior.command_in_progress)
        self.assertEqual(outcomes, [])

        transition_callbacks[0][1](False)
        self.assertFalse(behavior.command_in_progress)
        self.assertEqual(outcomes, [False])

        CommandBehavior._request_user_control_state(behavior, outcomes.append)
        transition_callbacks[-1][1](True)
        self.assertTrue(behavior.command_in_progress)
        self.assertEqual(outcomes, [False, True])

    def test_logs_async_service_failure(self):
        future = FakeFuture(error=RuntimeError("service unavailable"))
        logger = MagicMock()
        outcome = MagicMock()

        watch_transition_result(future, "IDLE", logger, on_result=outcome)
        future.finish()

        logger.error.assert_called_once()
        self.assertIn("service unavailable", logger.error.call_args.args[0])
        outcome.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
