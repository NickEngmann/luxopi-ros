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


class StateMachine:
    """Finite state machine for managing Luxo robot behavior states."""
    
    def __init__(self, node, initial_state: LuxoState = LuxoState.INITIALIZING):
        """
        Initialize the state machine.
        
        Args:
            node: ROS2 node for logging and service creation
            initial_state: Starting state for the machine
        """
        self.node = node
        self._current_state = initial_state
        self._state_history: List[tuple] = []  # (timestamp, state)
        self._transition_lock = threading.Lock()
        self._state_callbacks: Dict[LuxoState, List[Callable]] = {}
        self._transition_callbacks: List[Callable] = []
        self._state_enter_time: Dict[LuxoState, float] = {}
        self._state_exit_time: Dict[LuxoState, float] = {}
        self._state_durations: Dict[LuxoState, List[float]] = {}
        
        # Define state transitions with priorities
        self._transitions = self._build_transition_table()
        
        # Track state entry/exit for statistics
        self._state_entry_counts: Dict[LuxoState, int] = {}
        self._total_time_in_state: Dict[LuxoState, float] = {}
        
        # Initialize tracking dictionaries
        for state in LuxoState:
            self._state_entry_counts[state] = 0
            self._total_time_in_state[state] = 0.0
            self._state_durations[state] = []
    
    def _build_transition_table(self) -> Dict[LuxoState, List[StateTransition]]:
        """
        Build the state transition table with priorities.
        
        Returns:
            Dictionary mapping states to their possible transitions
        """
        transitions = {}
        
        # IDLE state transitions
        transitions[LuxoState.IDLE] = [
            StateTransition(LuxoState.IDLE, LuxoState.PETTING, 
                          condition=lambda self: self._petting_detected(),
                          action=lambda self: self._on_petting_enter()),
            StateTransition(LuxoState.IDLE, LuxoState.COLLISION_AVOIDING,
                          condition=lambda self: self._collision_detected(),
                          action=lambda self: self._on_collision_enter()),
            StateTransition(LuxoState.IDLE, LuxoState.ANIMATING,
                          condition=lambda self: self._animation_requested(),
                          action=lambda self: self._on_animation_enter()),
            StateTransition(LuxoState.IDLE, LuxoState.VOICE_FOLLOWING,
                          condition=lambda self: self._voice_command_active(),
                          action=lambda self: self._on_voice_following_enter()),
            StateTransition(LuxoState.IDLE, LuxoState.USER_CONTROL,
                          condition=lambda self: self._user_control_active(),
                          action=lambda self: self._on_user_control_enter()),
            StateTransition(LuxoState.IDLE, LuxoState.RETURNING_HOME,
                          condition=lambda self: self._should_return_home(),
                          action=lambda self: self._on_returning_home_enter()),
        ]
        
        # PETTING state transitions (high priority)
        transitions[LuxoState.PETTING] = [
            StateTransition(LuxoState.PETTING, LuxoState.IDLE,
                          condition=lambda self: self._petting_ended(),
                          action=lambda self: self._on_petting_exit()),
        ]
        
        # COLLISION_AVOIDING state transitions
        transitions[LuxoState.COLLISION_AVOIDING] = [
            StateTransition(LuxoState.COLLISION_AVOIDING, LuxoState.ESCAPE_MODE,
                          condition=lambda self: self._escape_required(),
                          action=lambda self: self._on_escape_enter()),
            StateTransition(LuxoState.COLLISION_AVOIDING, LuxoState.RETURNING_HOME,
                          condition=lambda self: self._safe_to_return_home(),
                          action=lambda self: self._on_returning_home_enter()),
            StateTransition(LuxoState.COLLISION_AVOIDING, LuxoState.IDLE,
                          condition=lambda self: self._collision_cleared(),
                          action=lambda self: self._on_collision_exit()),
        ]
        
        # ANIMATING state transitions
        transitions[LuxoState.ANIMATING] = [
            StateTransition(LuxoState.ANIMATING, LuxoState.IDLE,
                          condition=lambda self: self._animation_complete(),
                          action=lambda self: self._on_animation_exit()),
            StateTransition(LuxoState.ANIMATING, LuxoState.COLLISION_AVOIDING,
                          condition=lambda self: self._collision_during_animation(),
                          action=lambda self: self._on_collision_enter()),
        ]
        
        # VOICE_FOLLOWING state transitions
        transitions[LuxoState.VOICE_FOLLOWING] = [
            StateTransition(LuxoState.VOICE_FOLLOWING, LuxoState.IDLE,
                          condition=lambda self: self._voice_command_ended(),
                          action=lambda self: self._on_voice_following_exit()),
        ]
        
        # USER_CONTROL state transitions
        transitions[LuxoState.USER_CONTROL] = [
            StateTransition(LuxoState.USER_CONTROL, LuxoState.IDLE,
                          condition=lambda self: self._user_control_ended(),
                          action=lambda self: self._on_user_control_exit()),
        ]
        
        # ESCAPE_MODE state transitions
        transitions[LuxoState.ESCAPE_MODE] = [
            StateTransition(LuxoState.ESCAPE_MODE, LuxoState.RETURNING_HOME,
                          condition=lambda self: self._escape_complete(),
                          action=lambda self: self._on_escape_exit()),
            StateTransition(LuxoState.ESCAPE_MODE, LuxoState.IDLE,
                          condition=lambda self: self._safe_after_escape(),
                          action=lambda self: self._on_escape_exit()),
        ]
        
        # RETURNING_HOME state transitions
        transitions[LuxoState.RETURNING_HOME] = [
            StateTransition(LuxoState.RETURNING_HOME, LuxoState.IDLE,
                          condition=lambda self: self._home_reached(),
                          action=lambda self: self._on_returning_home_exit()),
        ]
        
        # ERROR state transitions
        transitions[LuxoState.ERROR] = [
            StateTransition(LuxoState.ERROR, LuxoState.IDLE,
                          condition=lambda self: self._error_resolved(),
                          action=lambda self: self._on_error_exit()),
        ]
        
        # INITIALIZING state transitions
        transitions[LuxoState.INITIALIZING] = [
            StateTransition(LuxoState.INITIALIZING, LuxoState.IDLE,
                          condition=lambda self: self._initialization_complete(),
                          action=lambda self: self._on_initialization_exit()),
        ]
        
        return transitions
    
    def _petting_detected(self) -> bool:
        """Check if petting interaction is detected."""
        return hasattr(self, '_petting_behavior') and self._petting_behavior.is_petting_detected
    
    def _collision_detected(self) -> bool:
        """Check if collision is detected."""
        return hasattr(self, '_collision_tracker') and self._collision_tracker.has_collision
    
    def _animation_requested(self) -> bool:
        """Check if animation is requested."""
        return hasattr(self, '_animation_tracker') and self._animation_tracker.has_pending_animation
    
    def _voice_command_active(self) -> bool:
        """Check if voice command is active."""
        return hasattr(self, '_voice_behavior') and self._voice_behavior.is_voice_following
    
    def _user_control_active(self) -> bool:
        """Check if user control is active."""
        return hasattr(self, '_command_behavior') and self._command_behavior.is_user_control
    
    def _should_return_home(self) -> bool:
        """Check if robot should return to home position."""
        return hasattr(self, '_collision_tracker') and self._collision_tracker.should_return_home
    
    def _petting_ended(self) -> bool:
        """Check if petting interaction has ended."""
        return hasattr(self, '_petting_behavior') and not self._petting_behavior.is_petting_detected
    
    def _escape_required(self) -> bool:
        """Check if escape mode is required."""
        return hasattr(self, '_collision_tracker') and self._collision_tracker.escape_required
    
    def _safe_to_return_home(self) -> bool:
        """Check if it's safe to return home."""
        return hasattr(self, '_collision_tracker') and self._collision_tracker.safe_to_return_home
    
    def _collision_cleared(self) -> bool:
        """Check if collision has been cleared."""
        return hasattr(self, '_collision_tracker') and not self._collision_tracker.has_collision
    
    def _animation_complete(self) -> bool:
        """Check if animation is complete."""
        return hasattr(self, '_animation_tracker') and self._animation_tracker.is_animation_complete
    
    def _collision_during_animation(self) -> bool:
        """Check if collision occurred during animation."""
        return hasattr(self, '_collision_tracker') and self._collision_tracker.has_collision
    
    def _voice_command_ended(self) -> bool:
        """Check if voice command has ended."""
        return hasattr(self, '_voice_behavior') and not self._voice_behavior.is_voice_following
    
    def _user_control_ended(self) -> bool:
        """Check if user control has ended."""
        return hasattr(self, '_command_behavior') and not self._command_behavior.is_user_control
    
    def _escape_complete(self) -> bool:
        """Check if escape maneuver is complete."""
        return hasattr(self, '_collision_tracker') and self._collision_tracker.escape_complete
    
    def _safe_after_escape(self) -> bool:
        """Check if safe after escape."""
        return hasattr(self, '_collision_tracker') and self._collision_tracker.safe_after_escape
    
    def _home_reached(self) -> bool:
        """Check if home position has been reached."""
        return hasattr(self, '_collision_tracker') and self._collision_tracker.home_reached
    
    def _error_resolved(self) -> bool:
        """Check if error has been resolved."""
        return hasattr(self, '_error_handler') and self._error_handler.error_resolved
    
    def _initialization_complete(self) -> bool:
        """Check if initialization is complete."""
        return hasattr(self, '_init_status') and self._init_status.initialized
    
    def _on_petting_enter(self):
        """Action to perform when entering PETTING state."""
        self.node.get_logger().info("Entering PETTING state")
        if hasattr(self, '_petting_behavior'):
            self._petting_behavior.on_state_enter()
    
    def _on_petting_exit(self):
        """Action to perform when exiting PETTING state."""
        self.node.get_logger().info("Exiting PETTING state")
        if hasattr(self, '_petting_behavior'):
            self._petting_behavior.on_state_exit()
    
    def _on_collision_enter(self):
        """Action to perform when entering COLLISION_AVOIDING state."""
        self.node.get_logger().warn("Entering COLLISION_AVOIDING state")
        if hasattr(self, '_collision_behavior'):
            self._collision_behavior.on_state_enter()
    
    def _on_collision_exit(self):
        """Action to perform when exiting COLLISION_AVOIDING state."""
        self.node.get_logger().info("Exiting COLLISION_AVOIDING state")
        if hasattr(self, '_collision_behavior'):
            self._collision_behavior.on_state_exit()
    
    def _on_animation_enter(self):
        """Action to perform when entering ANIMATING state."""
        self.node.get_logger().info("Entering ANIMATING state")
        if hasattr(self, '_animation_tracker'):
            self._animation_tracker.on_state_enter()
    
    def _on_animation_exit(self):
        """Action to perform when exiting ANIMATING state."""
        self.node.get_logger().info("Exiting ANIMATING state")
        if hasattr(self, '_animation_tracker'):
            self._animation_tracker.on_state_exit()
    
    def _on_voice_following_enter(self):
        """Action to perform when entering VOICE_FOLLOWING state."""
        self.node.get_logger().info("Entering VOICE_FOLLOWING state")
        if hasattr(self, '_voice_behavior'):
            self._voice_behavior.on_state_enter()
    
    def _on_voice_following_exit(self):
        """Action to perform when exiting VOICE_FOLLOWING state."""
        self.node.get_logger().info("Exiting VOICE_FOLLOWING state")
        if hasattr(self, '_voice_behavior'):
            self._voice_behavior.on_state_exit()
    
    def _on_user_control_enter(self):
        """Action to perform when entering USER_CONTROL state."""
        self.node.get_logger().info("Entering USER_CONTROL state")
        if hasattr(self, '_command_behavior'):
            self._command_behavior.on_state_enter()
    
    def _on_user_control_exit(self):
        """Action to perform when exiting USER_CONTROL state."""
        self.node.get_logger().info("Exiting USER_CONTROL state")
        if hasattr(self, '_command_behavior'):
            self._command_behavior.on_state_exit()
    
    def _on_escape_enter(self):
        """Action to perform when entering ESCAPE_MODE state."""
        self.node.get_logger().warn("Entering ESCAPE_MODE state")
        if hasattr(self, '_collision_behavior'):
            self._collision_behavior.on_escape_enter()
    
    def _on_escape_exit(self):
        """Action to perform when exiting ESCAPE_MODE state."""
        self.node.get_logger().info("Exiting ESCAPE_MODE state")
        if hasattr(self, '_collision_behavior'):
            self._collision_behavior.on_escape_exit()
    
    def _on_returning_home_enter(self):
        """Action to perform when entering RETURNING_HOME state."""
        self.node.get_logger().info("Entering RETURNING_HOME state")
        if hasattr(self, '_collision_behavior'):
            self._collision_behavior.on_returning_home_enter()
    
    def _on_returning_home_exit(self):
        """Action to perform when exiting RETURNING_HOME state."""
        self.node.get_logger().info("Exiting RETURNING_HOME state")
        if hasattr(self, '_collision_behavior'):
            self._collision_behavior.on_returning_home_exit()
    
    def _on_error_exit(self):
        """Action to perform when exiting ERROR state."""
        self.node.get_logger().info("Exiting ERROR state")
        if hasattr(self, '_error_handler'):
            self._error_handler.on_error_exit()
    
    def _on_initialization_exit(self):
        """Action to perform when exiting INITIALIZING state."""
        self.node.get_logger().info("Exiting INITIALIZING state")
        if hasattr(self, '_init_status'):
            self._init_status.on_initialization_exit()
    
    def get_current_state(self) -> LuxoState:
        """Get the current state of the machine."""
        with self._transition_lock:
            return self._current_state
    
    def get_state_history(self, limit: int = 10) -> List[tuple]:
        """
        Get the state transition history.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            List of (timestamp, state) tuples
        """
        with self._transition_lock:
            return self._state_history[-limit:]
    
    def get_state_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about state usage.
        
        Returns:
            Dictionary containing state statistics
        """
        with self._transition_lock:
            return {
                'current_state': self._current_state.name,
                'entry_counts': {state.name: count for state, count in self._state_entry_counts.items()},
                'total_time_in_state': {state.name: duration for state, duration in self._total_time_in_state.items()},
                'state_durations': {state.name: durations for state, durations in self._state_durations.items()},
            }
    
    def transition_to(self, new_state: LuxoState) -> bool:
        """
        Attempt to transition to a new state.
        
        Args:
            new_state: The target state to transition to
            
        Returns:
            True if transition was successful, False otherwise
        """
        with self._transition_lock:
            if new_state == self._current_state:
                return True
            
            # Check if transition is allowed
            allowed_transitions = self._transitions.get(self._current_state, [])
            target_transition = None
            
            for transition in allowed_transitions:
                if transition.to_state == new_state:
                    target_transition = transition
                    break
            
            if target_transition is None:
                # Try to find any valid transition to this state
                for state, transitions in self._transitions.items():
                    for transition in transitions:
                        if transition.to_state == new_state:
                            target_transition = transition
                            break
                    if target_transition:
                        break
            
            if target_transition is None:
                self.node.get_logger().error(f"No valid transition to {new_state.name}")
                return False
            
            # Check condition
            if target_transition.condition and not target_transition.condition(self):
                self.node.get_logger().debug(f"Transition condition not met for {new_state.name}")
                return False
            
            # Record exit time for current state
            exit_time = time.time()
            self._state_exit_time[self._current_state] = exit_time
            
            # Calculate time spent in current state
            if self._current_state in self._state_entry_time:
                entry_time = self._state_entry_time[self._current_state]
                duration = exit_time - entry_time
                self._total_time_in_state[self._current_state] += duration
                self._state_durations[self._current_state].append(duration)
            
            # Perform transition
            old_state = self._current_state
            self._current_state = new_state
            self._state_entry_time[new_state] = exit_time
            self._state_entry_counts[new_state] += 1
            
            # Record history
            self._state_history.append((exit_time, new_state))
            
            # Log transition
            self.node.get_logger().info(f"State transition: {old_state.name} -> {new_state.name}")
            
            # Execute transition action
            if target_transition.action:
                try:
                    target_transition.action(self)
                except Exception as e:
                    self.node.get_logger().error(f"Error executing transition action: {e}")
            
            # Notify callbacks
            for callback in self._transition_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    self.node.get_logger().error(f"Error in transition callback: {e}")
            
            # Notify state-specific callbacks
            if new_state in self._state_callbacks:
                for callback in self._state_callbacks[new_state]:
                    try:
                        callback()
                    except Exception as e:
                        self.node.get_logger().error(f"Error in state callback: {e}")
            
            return True
    
    def add_transition_callback(self, callback: Callable[[LuxoState, LuxoState], None]):
        """
        Add a callback to be called on every state transition.
        
        Args:
            callback: Function that takes (old_state, new_state) as arguments
        """
        self._transition_callbacks.append(callback)
    
    def add_state_callback(self, state: LuxoState, callback: Callable[[], None]):
        """
        Add a callback to be called when entering a specific state.
        
        Args:
            state: The state to add the callback for
            callback: Function to call when entering the state
        """
        if state not in self._state_callbacks:
            self._state_callbacks[state] = []
        self._state_callbacks[state].append(callback)
    
    def reset_statistics(self):
        """Reset all state statistics."""
        with self._transition_lock:
            for state in LuxoState:
                self._state_entry_counts[state] = 0
                self._total_time_in_state[state] = 0.0
                self._state_durations[state] = []
            self._state_history.clear()
    
    def is_in_state(self, state: LuxoState) -> bool:
        """
        Check if the machine is currently in a specific state.
        
        Args:
            state: The state to check
            
        Returns:
            True if in the specified state, False otherwise
        """
        with self._transition_lock:
            return self._current_state == state
    
    def get_state_duration(self, state: LuxoState) -> float:
        """
        Get the duration the machine has been in the current state.
        
        Args:
            state: The state to get duration for (should be current state)
            
        Returns:
            Duration in seconds, or 0 if not in the state
        """
        with self._transition_lock:
            if self._current_state != state:
                return 0.0
            if state not in self._state_entry_time:
                return 0.0
            return time.time() - self._state_entry_time[state]
    
    def get_average_state_duration(self, state: LuxoState) -> float:
        """
        Get the average duration spent in a state across all visits.
        
        Args:
            state: The state to calculate average for
            
        Returns:
            Average duration in seconds, or 0 if never visited
        """
        with self._transition_lock:
            durations = self._state_durations.get(state, [])
            if not durations:
                return 0.0
            return sum(durations) / len(durations)
    
    def get_most_frequent_state(self) -> Optional[LuxoState]:
        """
        Get the state that has been entered most frequently.
        
        Returns:
            The most frequently entered state, or None if no states visited
        """
        with self._transition_lock:
            if not self._state_entry_counts:
                return None
            return max(self._state_entry_counts.keys(), 
                      key=lambda s: self._state_entry_counts[s])
    
    def get_longest_state_duration(self) -> Optional[LuxoState]:
        """
        Get the state with the longest total time spent.
        
        Returns:
            The state with longest total duration, or None if no states visited
        """
        with self._transition_lock:
            if not self._total_time_in_state:
                return None
            return max(self._total_time_in_state.keys(),
                      key=lambda s: self._total_time_in_state[s])


class StateManager:
    """High-level state management for the Luxo robot system."""
    
    def __init__(self, node, state_machine: StateMachine):
        """
        Initialize the state manager.
        
        Args:
            node: ROS2 node for logging and service creation
            state_machine: The StateMachine instance to manage
        """
        self.node = node
        self._state_machine = state_machine
        self._state_pub = None
        self._state_sub = None
        self._request_transition_client = None
        self._state_info_subscribers: List[Callable] = []
        
        # Initialize service clients
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize ROS2 services and publishers."""
        # Create publisher for state info
        self._state_pub = self.node.create_publisher(
            StateInfo, '/luxo/state_info', 10
        )
        
        # Create client for state transition requests
        self._request_transition_client = self.node.create_client(
            RequestStateTransition, '/luxo/request_state_transition'
        )
        
        # Wait for services to be available
        while not self._request_transition_client.service_is_ready():
            time.sleep(0.1)
        
        self.node.get_logger().info("StateManager services initialized")
    
    def publish_state_info(self):
        """Publish current state information to ROS2."""
        current_state = self._state_machine.get_current_state()
        state_info = StateInfo()
        state_info.state = current_state.name
        state_info.timestamp = self.node.get_clock().now().nanoseconds
        state_info.entry_time = self._state_machine._state_entry_time.get(
            current_state, 0.0
        )
        state_info.duration = self._state_machine.get_state_duration(current_state)
        
        self._state_pub.publish(state_info)
    
    def request_state_transition(self, new_state: LuxoState) -> bool:
        """
        Request a state transition via ROS2 service.
        
        Args:
            new_state: The state to transition to
            
        Returns:
            True if transition was successful, False otherwise
        """
        # Call the state machine directly
        return self._state_machine.transition_to(new_state)
    
    def add_state_info_subscriber(self, callback: Callable[[StateInfo], None]):
        """
        Add a subscriber for state information.
        
        Args:
            callback: Function to call when state info is received
        """
        self._state_info_subscribers.append(callback)
    
    def get_state_info(self) -> StateInfo:
        """
        Get current state information.
        
        Returns:
            StateInfo message with current state data
        """
        current_state = self._state_machine.get_current_state()
        state_info = StateInfo()
        state_info.state = current_state.name
        state_info.timestamp = self.node.get_clock().now().nanoseconds
        state_info.entry_time = self._state_machine._state_entry_time.get(
            current_state, 0.0
        )
        state_info.duration = self._state_machine.get_state_duration(current_state)
        state_info.is_error = current_state == LuxoState.ERROR
        
        return state_info
    
    def handle_state_transition_request(self, request, response):
        """
        Handle incoming state transition requests.
        
        Args:
            request: The state transition request
            response: The response to fill
            
        Returns:
            Response with success status
        """
        try:
            new_state = LuxoState[request.new_state]
            success = self.request_state_transition(new_state)
            response.success = success
            response.message = "State transition successful" if success else "State transition failed"
        except KeyError:
            response.success = False
            response.message = f"Invalid state: {request.new_state}"
        
        return response
    
    def shutdown(self):
        """Clean up resources on shutdown."""
        if self._state_pub:
            self._state_pub.destroy()
        if self._request_transition_client:
            self._request_transition_client.destroy()
        self.node.get_logger().info("StateManager shutdown complete")
