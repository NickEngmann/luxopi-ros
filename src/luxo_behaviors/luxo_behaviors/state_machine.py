"""State machine definitions for luxo_behaviors."""

from enum import Enum


class LuxoState(Enum):
    """States for the Luxo robot."""
    IDLE = "idle"
    ANIMATING = "animating"
    VOICE_FOLLOWING = "voice_following"
    COLLISION_AVOIDING = "collision_avoiding"
    RETURNING_HOME = "returning_home"
    ESCAPE_MODE = "escape_mode"
    USER_CONTROL = "user_control"
    EMOTION_REACTING = "emotion_reacting"
    PETTING = "petting"
    ERROR = "error"
    INITIALIZING = "initializing"
    SHUTDOWN = "shutdown"


class StateTransition:
    """Represents a state transition in the Luxo state machine."""
    
    def __init__(self, from_state: LuxoState, to_state: LuxoState, condition=None, action=None):
        """Initialize a state transition.
        
        Args:
            from_state: The source state
            to_state: The destination state
            condition: The condition function that triggers the transition (optional)
            action: The action function to execute on transition (optional)
        """
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition
        self.action = action
    
    def __repr__(self):
        return f"StateTransition({self.from_state.value} -> {self.to_state.value}, condition={self.condition}, action={self.action})"
