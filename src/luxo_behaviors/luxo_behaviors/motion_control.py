"""Small, ROS-independent helpers for coordinating animation goals."""

import threading


class AnimationGoalTracker:
    """Keep cancellation state separate for every accepted action goal.

    ROS can run action executions concurrently. A shared boolean cancellation
    flag is unsafe: accepting a replacement goal can clear the flag before the
    previous execution observes it. Per-goal events prevent that reset race.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._events = {}
        self._active_goal = None

    def accept(self, goal_handle):
        """Register a goal and cancel the previous goal, if one is active."""
        with self._lock:
            previous = self._active_goal
            if previous is not None:
                previous_event = self._events.get(id(previous))
                if previous_event is not None:
                    previous_event.set()

            event = threading.Event()
            self._events[id(goal_handle)] = event
            self._active_goal = goal_handle
            return event

    def event_for(self, goal_handle):
        """Return the cancellation event associated with a goal."""
        with self._lock:
            return self._events.setdefault(id(goal_handle), threading.Event())

    def cancel(self, goal_handle):
        """Request cancellation for one specific goal."""
        with self._lock:
            event = self._events.get(id(goal_handle))
            if event is None:
                return False
            event.set()
            return True

    def finish(self, goal_handle):
        """Forget a completed goal without affecting a newer accepted goal."""
        with self._lock:
            self._events.pop(id(goal_handle), None)
            if self._active_goal is goal_handle:
                self._active_goal = None

