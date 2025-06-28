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

class LuxoStateMachine:
    """Simple but expandable finite state machine for Luxo robot."""
    
    def __init__(self, node, initial_state: LuxoState = LuxoState.INITIALIZING):
        self.node = node  # ROS node for logging
        self._current_state = initial_state
        self._previous_state = None
        self._state_lock = threading.RLock()
        
        # State metadata
        self._state_data = {}  # Store arbitrary data for each state
        self._state_start_time = None
        self._state_history = []  # Track state transitions
        self._max_history = 100
        
        # Add timing support for automatic transitions
        self._automatic_transitions = {}  # Dict[LuxoState, Dict] for timed transitions
        
        # Transitions
        self._transitions: Dict[LuxoState, List[StateTransition]] = {
            state: [] for state in LuxoState
        }
        
        # State callbacks
        self._on_enter_callbacks: Dict[LuxoState, List[Callable]] = {
            state: [] for state in LuxoState
        }
        self._on_exit_callbacks: Dict[LuxoState, List[Callable]] = {
            state: [] for state in LuxoState
        }
        self._on_state_callbacks: Dict[LuxoState, List[Callable]] = {
            state: [] for state in LuxoState
        }
        
        
        # Initialize
        self._enter_state(initial_state)
        self._setup_default_transitions()
    
    def _setup_default_transitions(self):
        """Set up default state transitions."""
        # From INITIALIZING
        self.add_transition(LuxoState.INITIALIZING, LuxoState.IDLE)
        self.add_transition(LuxoState.INITIALIZING, LuxoState.ERROR)
        
        # From IDLE
        self.add_transition(LuxoState.IDLE, LuxoState.ANIMATING)
        self.add_transition(LuxoState.IDLE, LuxoState.VOICE_FOLLOWING)
        self.add_transition(LuxoState.IDLE, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.IDLE, LuxoState.USER_CONTROL)
        self.add_transition(LuxoState.IDLE, LuxoState.EMOTION_REACTING)
        self.add_transition(LuxoState.IDLE, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.IDLE, LuxoState.PETTING)
        
        # From ANIMATING
        self.add_transition(LuxoState.ANIMATING, LuxoState.IDLE)
        self.add_transition(LuxoState.ANIMATING, LuxoState.VOICE_FOLLOWING)
        self.add_transition(LuxoState.ANIMATING, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.ANIMATING, LuxoState.ESCAPE_MODE)
        self.add_transition(LuxoState.ANIMATING, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.ANIMATING, LuxoState.PETTING)
        
        # From VOICE_FOLLOWING - can return to any state
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.IDLE)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.ANIMATING)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.PETTING)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.EMOTION_REACTING)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.ESCAPE_MODE)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.RETURNING_HOME)
        
        # From COLLISION_AVOIDING
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.IDLE)
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.ESCAPE_MODE)
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.PETTING)
        # Note: NO transition from COLLISION_AVOIDING to VOICE_FOLLOWING for safety
        
        # From ESCAPE_MODE
        self.add_transition(LuxoState.ESCAPE_MODE, LuxoState.IDLE)
        self.add_transition(LuxoState.ESCAPE_MODE, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.ESCAPE_MODE, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.ESCAPE_MODE, LuxoState.PETTING)
        
        # From RETURNING_HOME
        self.add_transition(LuxoState.RETURNING_HOME, LuxoState.IDLE)
        self.add_transition(LuxoState.RETURNING_HOME, LuxoState.ANIMATING)
        self.add_transition(LuxoState.RETURNING_HOME, LuxoState.PETTING)
        
        # From USER_CONTROL
        self.add_transition(LuxoState.USER_CONTROL, LuxoState.IDLE)
        self.add_transition(LuxoState.USER_CONTROL, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.USER_CONTROL, LuxoState.PETTING)
        
        # From EMOTION_REACTING
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.IDLE)
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.VOICE_FOLLOWING)
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.PETTING)
        
        # From PETTING
        self.add_transition(LuxoState.PETTING, LuxoState.IDLE)
        self.add_transition(LuxoState.PETTING, LuxoState.ANIMATING)
        self.add_transition(LuxoState.PETTING, LuxoState.VOICE_FOLLOWING)
        self.add_transition(LuxoState.PETTING, LuxoState.EMOTION_REACTING)
        self.add_transition(LuxoState.PETTING, LuxoState.COLLISION_AVOIDING)
        
        # From ERROR - can transition to most states for recovery
        self.add_transition(LuxoState.ERROR, LuxoState.IDLE)
        self.add_transition(LuxoState.ERROR, LuxoState.INITIALIZING)
        self.add_transition(LuxoState.ERROR, LuxoState.SHUTDOWN)
        
        # To SHUTDOWN from any state
        for state in LuxoState:
            if state != LuxoState.SHUTDOWN:
                self.add_transition(state, LuxoState.SHUTDOWN)
    
    def add_transition(self, from_state: LuxoState, to_state: LuxoState,
                      condition: Optional[Callable] = None,
                      action: Optional[Callable] = None):
        """Add a valid state transition."""
        transition = StateTransition(from_state, to_state, condition, action)
        self._transitions[from_state].append(transition)
    
    def add_automatic_transition(self, from_state: LuxoState, to_state: LuxoState, 
                               delay_seconds: float, condition: Optional[Callable] = None):
        """
        Add an automatic transition that occurs after a specified time.
        
        Args:
            from_state: State to transition from
            to_state: State to transition to
            delay_seconds: Time to wait before transitioning
            condition: Optional condition that must be true for transition
        """
        if from_state not in self._automatic_transitions:
            self._automatic_transitions[from_state] = []
        
        self._automatic_transitions[from_state].append({
            'to_state': to_state,
            'delay': delay_seconds,
            'condition': condition
        })

    def register_on_enter(self, state: LuxoState, callback: Callable):
        """Register a callback to be called when entering a state."""
        self._on_enter_callbacks[state].append(callback)
    
    def register_on_exit(self, state: LuxoState, callback: Callable):
        """Register a callback to be called when exiting a state."""
        self._on_exit_callbacks[state].append(callback)
    
    def register_on_state(self, state: LuxoState, callback: Callable):
        """Register a callback to be called while in a state."""
        self._on_state_callbacks[state].append(callback)
    
    @property
    def current_state(self) -> LuxoState:
        """Get the current state."""
        with self._state_lock:
            return self._current_state
    
    @property
    def previous_state(self) -> Optional[LuxoState]:
        """Get the previous state."""
        with self._state_lock:
            return self._previous_state
    
    def get_state_duration(self) -> float:
        """Get how long we've been in the current state."""
        with self._state_lock:
            if self._state_start_time:
                return time.time() - self._state_start_time
            return 0.0
    
    def set_state_data(self, key: str, value: Any):
        """Store data associated with the current state."""
        with self._state_lock:
            if self._current_state not in self._state_data:
                self._state_data[self._current_state] = {}
            self._state_data[self._current_state][key] = value
    
    def get_state_data(self, key: str, default: Any = None) -> Any:
        """Get data associated with the current state."""
        with self._state_lock:
            if self._current_state in self._state_data:
                return self._state_data[self._current_state].get(key, default)
            return default
    
    def transition_to(self, new_state: LuxoState, force: bool = False) -> bool:
        """
        Attempt to transition to a new state.
        
        Args:
            new_state: The desired state
            force: If True, bypass transition rules (use carefully!)
            
        Returns:
            bool: True if transition was successful
        """
        with self._state_lock:
            # Check if already in the desired state
            if self._current_state == new_state:
                return True
            
            # If forcing, bypass checks
            if force:
                self._exit_state(self._current_state)
                self._enter_state(new_state)
                return True
            
            # Check if transition is valid
            valid_transition = None
            for transition in self._transitions[self._current_state]:
                if transition.to_state == new_state:
                    # Check condition if one exists
                    if transition.condition is None or transition.condition():
                        valid_transition = transition
                        break
            
            if valid_transition:
                # Execute transition
                self._exit_state(self._current_state)
                
                # Execute transition action if defined
                if valid_transition.action:
                    try:
                        valid_transition.action()
                    except Exception as e:
                        self.node.get_logger().error(f"Error in transition action: {e}")
                
                self._enter_state(new_state)
                return True
            else:
                self.node.get_logger().warn(
                    f"Invalid state transition: {self._current_state.name} -> {new_state.name}"
                )
                return False
    
    def _exit_state(self, state: LuxoState):
        """Handle exiting a state."""
        # Call exit callbacks
        for callback in self._on_exit_callbacks[state]:
            try:
                callback()
            except Exception as e:
                self.node.get_logger().error(f"Error in exit callback for {state.name}: {e}")
        
        # Clear state data
        if state in self._state_data:
            del self._state_data[state]
    
    def _enter_state(self, state: LuxoState):
        """Handle entering a state."""
        # Update state
        self._previous_state = self._current_state
        self._current_state = state
        self._state_start_time = time.time()
        
        # Add to history
        self._state_history.append({
            'state': state,
            'timestamp': self._state_start_time,
            'from_state': self._previous_state
        })
        
        # Trim history if needed
        if len(self._state_history) > self._max_history:
            self._state_history.pop(0)
        
        # Log state change
        if self._previous_state:
            self.node.get_logger().info(
                f"State transition: {self._previous_state.name} -> {state.name}"
            )
        else:
            self.node.get_logger().info(f"Initial state: {state.name}")
        
        # Call enter callbacks
        for callback in self._on_enter_callbacks[state]:
            try:
                callback()
            except Exception as e:
                self.node.get_logger().error(f"Error in enter callback for {state.name}: {e}")
    
    def update(self):
        """Call this periodically to execute state callbacks and check automatic transitions."""
        with self._state_lock:
            current = self._current_state
            current_duration = self.get_state_duration()
        
        
        # Check for automatic transitions
        if current in self._automatic_transitions:
            for auto_transition in self._automatic_transitions[current]:
                if current_duration >= auto_transition['delay']:
                    # Check condition if specified
                    if auto_transition['condition'] is None or auto_transition['condition']():
                        self.transition_to(auto_transition['to_state'])
                        break  # Only execute first valid automatic transition
        
        # Execute callbacks for current state
        for callback in self._on_state_callbacks[current]:
            try:
                callback()
            except Exception as e:
                self.node.get_logger().error(f"Error in state callback for {current.name}: {e}")
    
    def get_state_history(self, limit: int = 10) -> List[Dict]:
        """Get recent state history."""
        with self._state_lock:
            return self._state_history[-limit:]
    
    def is_in_state(self, *states: LuxoState) -> bool:
        """Check if currently in any of the given states."""
        with self._state_lock:
            return self._current_state in states
