#!/usr/bin/env python3
#state_machine.py
"""
State machine implementation for Luxo robot behavior management.
Provides robust state transitions with conditions, actions, and error handling.
"""

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


class StateMachineError(Exception):
    """Exception raised for state machine errors."""
    pass


class StateMachine:
    """
    A state machine for managing Luxo robot behaviors.
    
    Features:
    - Thread-safe state transitions
    - Conditional transitions with validation
    - Actions executed during transitions
    - State history tracking
    - Error handling for invalid transitions
    """
    
    def __init__(self, initial_state: LuxoState = LuxoState.IDLE):
        """
        Initialize the state machine.
        
        Args:
            initial_state: The starting state for the machine
        """
        self._current_state: LuxoState = initial_state
        self._lock = threading.RLock()
        self._transitions: Dict[LuxoState, List[StateTransition]] = {}
        self._state_history: List[Dict[str, Any]] = []
        self._transition_callbacks: Dict[str, List[Callable]] = {
            'on_enter': {},
            'on_exit': {},
            'on_transition': {}
        }
        self._initialized = True
        
        # Register initial state
        self._log_transition(None, initial_state, "initialization")
    
    def _log_transition(self, from_state: Optional[LuxoState], 
                       to_state: LuxoState, reason: str):
        """Log a state transition to history."""
        self._state_history.append({
            'from_state': from_state.name if from_state else None,
            'to_state': to_state.name,
            'reason': reason,
            'timestamp': time.time()
        })
    
    def add_transition(self, transition: StateTransition) -> 'StateMachine':
        """
        Add a state transition to the machine.
        
        Args:
            transition: The StateTransition to add
            
        Returns:
            self for method chaining
        """
        with self._lock:
            if transition.from_state not in self._transitions:
                self._transitions[transition.from_state] = []
            self._transitions[transition.from_state].append(transition)
        return self
    
    def add_transitions(self, transitions: List[StateTransition]) -> 'StateMachine':
        """
        Add multiple transitions at once.
        
        Args:
            transitions: List of StateTransition objects
            
        Returns:
            self for method chaining
        """
        for transition in transitions:
            self.add_transition(transition)
        return self
    
    def get_valid_transitions(self, from_state: Optional[LuxoState] = None) -> List[StateTransition]:
        """
        Get all valid transitions from a state.
        
        Args:
            from_state: The source state (defaults to current state)
            
        Returns:
            List of valid StateTransition objects
        """
        with self._lock:
            source = from_state or self._current_state
            return self._transitions.get(source, [])
    
    def can_transition(self, to_state: LuxoState, from_state: Optional[LuxoState] = None) -> bool:
        """
        Check if a transition to the specified state is valid.
        
        Args:
            to_state: The target state to check
            from_state: The source state (defaults to current state)
            
        Returns:
            True if transition is valid, False otherwise
        """
        with self._lock:
            source = from_state or self._current_state
            transitions = self._transitions.get(source, [])
            return any(t.to_state == to_state for t in transitions)
    
    def transition(self, to_state: LuxoState, context: Optional[Dict] = None) -> bool:
        """
        Attempt to transition to a new state.
        
        Args:
            to_state: The target state to transition to
            context: Optional context data for condition/action evaluation
            
        Returns:
            True if transition succeeded, False otherwise
            
        Raises:
            StateMachineError: If transition is invalid
        """
        if context is None:
            context = {}
            
        with self._lock:
            from_state = self._current_state
            
            # Check if already in target state
            if from_state == to_state:
                return True
            
            # Find valid transition
            transitions = self._transitions.get(from_state, [])
            target_transition = None
            
            for t in transitions:
                if t.to_state == to_state:
                    target_transition = t
                    break
            
            if target_transition is None:
                raise StateMachineError(
                    f"No valid transition from {from_state.name} to {to_state.name}"
                )
            
            # Check condition
            if target_transition.condition:
                try:
                    if not target_transition.condition(context):
                        raise StateMachineError(
                            f"Transition condition failed: {from_state.name} -> {to_state.name}"
                        )
                except Exception as e:
                    raise StateMachineError(f"Condition evaluation error: {e}")
            
            # Execute exit callback for current state
            self._execute_callbacks('on_exit', from_state, context)
            
            # Execute transition action if provided
            if target_transition.action:
                try:
                    target_transition.action(context)
                except Exception as e:
                    raise StateMachineError(f"Transition action error: {e}")
            
            # Update state
            self._current_state = to_state
            self._log_transition(from_state, to_state, "explicit_transition")
            
            # Execute enter callback for new state
            self._execute_callbacks('on_enter', to_state, context)
            
            # Execute transition callback
            self._execute_callbacks('on_transition', to_state, context)
            
            return True
    
    def _execute_callbacks(self, callback_type: str, state: LuxoState, 
                          context: Dict):
        """Execute callbacks for a specific state and callback type."""
        callbacks = self._transition_callbacks.get(callback_type, {})
        state_callbacks = callbacks.get(state.name, [])
        
        for callback in state_callbacks:
            try:
                callback(context)
            except Exception as e:
                # Log error but don't fail the transition
                print(f"Callback error for {state.name} ({callback_type}): {e}")
    
    def set_callback(self, callback_type: str, state: LuxoState, 
                    callback: Callable[[Dict], None]):
        """
        Register a callback for a specific state and callback type.
        
        Args:
            callback_type: One of 'on_enter', 'on_exit', 'on_transition'
            state: The state to register the callback for
            callback: Function to execute (receives context dict)
        """
        with self._lock:
            if callback_type not in self._transition_callbacks:
                raise ValueError(f"Unknown callback type: {callback_type}")
            
            if state.name not in self._transition_callbacks[callback_type]:
                self._transition_callbacks[callback_type][state.name] = []
            
            self._transition_callbacks[callback_type][state.name].append(callback)
    
    @property
    def current_state(self) -> LuxoState:
        """Get the current state of the machine."""
        with self._lock:
            return self._current_state
    
    @property
    def state_history(self) -> List[Dict[str, Any]]:
        """Get the history of state transitions."""
        with self._lock:
            return self._state_history.copy()
    
    def reset(self, new_initial_state: LuxoState = LuxoState.IDLE) -> None:
        """
        Reset the state machine to an initial state.
        
        Args:
            new_initial_state: The state to reset to (defaults to IDLE)
        """
        with self._lock:
            from_state = self._current_state
            self._current_state = new_initial_state
            self._state_history.clear()
            self._log_transition(from_state, new_initial_state, "reset")
    
    def get_state_description(self, state: LuxoState) -> str:
        """
        Get a human-readable description of a state.
        
        Args:
            state: The state to describe
            
        Returns:
            Description string
        """
        descriptions = {
            LuxoState.IDLE: "Robot is idle, waiting for input",
            LuxoState.ANIMATING: "Robot is performing an animation",
            LuxoState.VOICE_FOLLOWING: "Robot is following voice commands",
            LuxoState.COLLISION_AVOIDING: "Robot is avoiding obstacles",
            LuxoState.RETURNING_HOME: "Robot is returning to home position",
            LuxoState.ESCAPE_MODE: "Robot is in escape mode",
            LuxoState.USER_CONTROL: "Robot is in user control mode",
            LuxoState.EMOTION_REACTING: "Robot is reacting emotionally",
            LuxoState.PETTING: "Robot is being petted",
            LuxoState.ERROR: "Robot is in error state",
            LuxoState.INITIALIZING: "Robot is initializing",
            LuxoState.SHUTDOWN: "Robot is shutting down"
        }
        return descriptions.get(state, f"Unknown state: {state.name}")
    
    def __repr__(self) -> str:
        """String representation of the state machine."""
        with self._lock:
            return f"StateMachine(state={self._current_state.name}, transitions={len(self._state_history)})"
