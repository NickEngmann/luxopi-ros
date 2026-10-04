"""Tests for reporting real asynchronous state-service results."""

import pathlib
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

from luxo_behaviors.transition_requests import watch_transition_result  # noqa: E402


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

        returned = watch_transition_result(future, "IDLE", logger)
        self.assertIs(returned, future)
        logger.debug.assert_not_called()
        future.finish()
        logger.debug.assert_called_once()

    def test_logs_denial_instead_of_reporting_queued_request_as_success(self):
        future = FakeFuture(MagicMock(success=False, message="safety priority"))
        logger = MagicMock()

        watch_transition_result(future, "ANIMATING", logger)
        future.finish()

        logger.warning.assert_called_once()
        self.assertIn("safety priority", logger.warning.call_args.args[0])

    def test_logs_async_service_failure(self):
        future = FakeFuture(error=RuntimeError("service unavailable"))
        logger = MagicMock()

        watch_transition_result(future, "IDLE", logger)
        future.finish()

        logger.error.assert_called_once()
        self.assertIn("service unavailable", logger.error.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
