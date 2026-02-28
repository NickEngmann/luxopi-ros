#!/usr/bin/env python3
#state_machine.py
import threading
from enum import Enum, auto
from typing import Dict, List, Callable, Optional, Any
import time

class LuxoState(Enum):
    """Define all possible states for the Luxo robot."""
    IDLE = auto()
    BEHAVIOR = auto()
    COLLISION = auto()
    PETTING = auto()
    VOICE = auto()
    CAMERA = auto()
    ANIMATING = auto()
    RETURNING_HOME = auto()
    ESCAPE_MODE = auto()
    USER_CONTROL = auto()  # Dynamic adaptation mode
    EMOTION_REACTING = auto()
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


class StateMachine:
    """Manages state transitions for the Luxo robot."""
    
    def __init__(self, initial_state: LuxoState):
        self.current_state = initial_state
        self.transitions: List[StateTransition] = []
    
    def add_transition(self, transition: StateTransition) -> None:
        """Add a transition to the state machine."""
        self.transitions.append(transition)
    
    def can_transition(self, from_state: LuxoState, to_state: LuxoState) -> bool:
        """Check if a transition is possible from current state."""
        for transition in self.transitions:
            if (transition.from_state == from_state and 
                transition.to_state == to_state):
                if transition.condition is None:
                    return True
                return transition.condition()
        return False
    
    def perform_transition(self, new_state: LuxoState) -> bool:
        """Attempt to perform a transition to the new state."""
        for transition in self.transitions:
            if (transition.from_state == self.current_state and 
                transition.to_state == new_state):
                if transition.condition is None or transition.condition():
                    if transition.action is not None:
                        transition.action()
                    self.current_state = new_state
                    return True
        return False
    
    def change_state(self, new_state: LuxoState) -> None:
        """Directly change the state without checking transitions."""
        self.current_state = new_state
    
    def get_current_state(self) -> LuxoState:
        """Get the current state."""
        return self.current_state
