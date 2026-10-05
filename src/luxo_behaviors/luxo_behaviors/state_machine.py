#!/usr/bin/env python3
#state_machine.py
import threading
from enum import Enum, auto
from typing import Dict, List, Callable, Optional, Any
import time

class LuxoState(Enum):
    """Define all possible states for the Luxo robot."""
    IDLE = auto()
    ANIMATING = auto()
    VOICE_FOLLOWING = auto()  # Voice following as its own state
    COLLISION_AVOIDING = auto()
    RETURNING_HOME = auto()
    ESCAPE_MODE = auto()
    USER_CONTROL = auto()  # Dynamic adaptation mode
    EMOTION_REACTING = auto()
    PETTING = auto()  # High-priority state for petting interactions
    ERROR = auto()
    INITIALIZING = auto()
    SHUTDOWN = auto()

class StateTransition:
    """Represents a state transition with conditions and actions."""
    def __init__(self, from_state: LuxoState, to_state: LuxoState, 
                 condition: Optional[Callable] = None,
                 action: Optional[Callable] = None):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition  # Function that returns True if transition is allowed
        self.action = action  # Function to execute during transition


def completion_matches_owner(current_requester, requesting_node):
    """Guard completion transitions against stale or foreign action results.

    A completion is valid only while the state still belongs to the requester
    that is completing it.  This prevents a late animation/voice callback from
    returning a newer safety or user session to IDLE.
    """
    return bool(requesting_node) and current_requester == requesting_node


class StateTransitionPolicy:
    """Pure priority, ownership, and interrupted-state policy for the FSM."""

    def __init__(self, priorities, *, idle_state=LuxoState.IDLE,
                 error_state=LuxoState.ERROR, initial_state=LuxoState.INITIALIZING,
                 collision_state=LuxoState.COLLISION_AVOIDING,
                 escape_state=LuxoState.ESCAPE_MODE, shutdown_state=LuxoState.SHUTDOWN):
        self.priorities = dict(priorities)
        self.idle_state = idle_state
        self.error_state = error_state
        self.initial_state = initial_state
        self.collision_state = collision_state
        self.escape_state = escape_state
        self.shutdown_state = shutdown_state

    def decide(self, *, current_state, current_requester, current_priority,
               requested_state, requesting_node, priority=None, force=False,
               completion=False, interrupted_states=None,
               interrupted_requesters=None):
        """Return a transition decision without mutating manager state."""
        effective_priority = (
            self.priorities.get(requesting_node, 50)
            if priority is None else priority
        )
        completing_state = current_state
        restored_requester = None
        if completion:
            if current_state in (self.error_state, self.shutdown_state):
                return {"accepted": False, "reason": "terminal_state_requires_explicit_recovery"}
            if not completion_matches_owner(current_requester, requesting_node):
                suspended = interrupted_requesters or {}
                if any(owner == requesting_node for owner, _ in suspended.values()):
                    # A suspended action may finish while safety/another session owns
                    # the robot. Release its lease without changing that live owner.
                    return {
                        "accepted": True, "target_state": current_state,
                        "requesting_node": current_requester,
                        "priority": current_priority, "release_owner": requesting_node,
                    }
                return {"accepted": False, "reason": "completion_owner_mismatch"}
            interrupted_states = interrupted_states or {}
            interrupted_requesters = interrupted_requesters or {}
            requested_state = interrupted_states.get(current_state, requested_state)
            restored_requester = interrupted_requesters.get(completing_state)
        elif not force and not self._has_priority(
                current_state, requesting_node, effective_priority, current_priority):
            return {"accepted": False, "reason": "insufficient_priority"}

        interrupted = (
            not completion
            and current_state != requested_state
            and requested_state not in (self.error_state, self.shutdown_state)
            and current_state not in (self.idle_state, self.initial_state)
            and effective_priority > current_priority
        )
        owner, owner_priority = restored_requester or (
            requesting_node, effective_priority
        )
        return {
            "accepted": True,
            "target_state": requested_state,
            "completing_state": completing_state,
            "requesting_node": owner,
            "priority": owner_priority,
            "interrupted": interrupted,
            "previous_state": current_state,
            "previous_requester": current_requester,
            "previous_priority": current_priority,
            "completion": completion,
        }

    def commit(self, decision, interrupted_states, interrupted_requesters):
        """Return updated interruption maps after a successful state change."""
        states = dict(interrupted_states)
        requesters = dict(interrupted_requesters)
        released = decision.get("release_owner")
        if released:
            for parent in list(states):
                owner = requesters.get(parent)
                if owner is None or owner[0] != released:
                    continue
                ended_state = states[parent]
                states[parent] = states.pop(ended_state, self.idle_state)
                requesters[parent] = requesters.pop(ended_state, ("idle", 0))
            return states, requesters
        previous = decision["previous_state"]
        target = decision["target_state"]
        if decision["interrupted"]:
            states[target] = previous
            requesters[target] = (
                decision["previous_requester"], decision["previous_priority"]
            )
        elif previous != target:
            states.pop(previous, None)
            requesters.pop(previous, None)
        if decision["completion"]:
            states.pop(decision["completing_state"], None)
            requesters.pop(decision["completing_state"], None)
        return states, requesters

    def _has_priority(self, current_state, requesting_node, priority,
                      current_priority):
        if current_state == self.error_state:
            # Ordinary idle/voice callbacks are not a maintenance recovery.
            return priority >= max(100, current_priority)
        if current_state == self.idle_state:
            return True
        if (requesting_node == "animation_command" and priority in (30, 50)
                and current_state not in (self.collision_state, self.escape_state)):
            return True
        return priority >= current_priority
