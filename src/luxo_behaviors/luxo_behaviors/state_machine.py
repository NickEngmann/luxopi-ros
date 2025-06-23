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
        
        # Initialize NeoPixel controller for state visualization
        self._neopixel_controller = None
        self._neopixel_override_active = False  # Track if override is active
        
        # NeoPixel animation timing control
        self._neopixel_animation_start_time = None
        self._neopixel_min_animation_duration = 2.0  # Minimum 2 seconds for animations
        self._neopixel_last_visual_state = None  # Track last visual state to avoid redundant updates
        self._neopixel_pending_state = None  # Queue next state if animation is still running
        
        self._initialize_neopixel()
        
        # Desk lamp optimized state color mappings
        self._state_colors = {
            LuxoState.IDLE: (255, 255, 255),        # White - main desk lamp color
            LuxoState.INITIALIZING: (0, 100, 255),  # Blue - starting up
            LuxoState.ANIMATING: (255, 255, 255),   # White - keep lamp function during animations
            LuxoState.VOICE_FOLLOWING: (255, 255, 255), # White - keep lamp function
            LuxoState.COLLISION_AVOIDING: (255, 128, 0), # Orange - caution
            LuxoState.RETURNING_HOME: (255, 255, 255),   # White - keep lamp function
            LuxoState.ESCAPE_MODE: (255, 0, 0),  # Red - keep lamp function
            LuxoState.USER_CONTROL: (255, 255, 255), # White - keep lamp function
            LuxoState.EMOTION_REACTING: (255, 255, 255), # White - keep lamp function
            LuxoState.PETTING: (255, 230, 240),     # Slightly pink - more white than red
            LuxoState.ERROR: (255, 0, 0),           # Red - error (flashing)
            LuxoState.SHUTDOWN: (128, 128, 128)     # Dim gray - shutting down
        }
        
        # Initialize
        self._enter_state(initial_state)
        self._setup_default_transitions()
    
    def _initialize_neopixel(self):
        """Initialize NeoPixel controller for state visualization"""
        try:
            from luxo_behaviors.neopixel_control import NeoPixelController
            self._neopixel_controller = NeoPixelController(
                pixel_count=76,
                brightness=0.8,  # Brighter for desk lamp use
                logger=self.node.get_logger()
            )
            if self._neopixel_controller.is_initialized():
                self.node.get_logger().info("NeoPixel desk lamp state visualization enabled")
            else:
                self._neopixel_controller = None
                self.node.get_logger().warn("NeoPixel initialization failed - continuing without visual state")
        except Exception as e:
            self.node.get_logger().warn(f"NeoPixel not available: {e}")
            self._neopixel_controller = None
    
    def _is_neopixel_animation_running(self) -> bool:
        """Check if a NeoPixel animation is still in its minimum duration period"""
        if self._neopixel_animation_start_time is None:
            return False
        
        elapsed = time.time() - self._neopixel_animation_start_time
        return elapsed < self._neopixel_min_animation_duration
    
    def _start_neopixel_animation_timer(self):
        """Start the timer for NeoPixel animation minimum duration"""
        self._neopixel_animation_start_time = time.time()
        self.node.get_logger().debug("NeoPixel animation timer started - 2 second minimum duration")
    
    def _update_neopixel_for_state(self, state: LuxoState):
        """Update NeoPixel display based on current state - optimized for desk lamp"""
        if not self._neopixel_controller or self._neopixel_override_active:
            return
        
        # Check if we should update visual state
        if self._is_neopixel_animation_running():
            # Animation is still running, queue this state for later
            self._neopixel_pending_state = state
            self.node.get_logger().debug(f"NeoPixel animation still running, queuing state {state.name}")
            return
        
        # Check if this is the same visual state we're already showing
        if self._neopixel_last_visual_state == state:
            self.node.get_logger().debug(f"NeoPixel already showing {state.name}, skipping update")
            return
        
        try:
            # Always stop any running effect first before starting new one
            self._neopixel_controller.stop_effect()
            
            color = self._state_colors.get(state, (255, 255, 255))  # Default to white
            
            # Determine if this state needs animation (and thus timing control)
            needs_animation_timer = False
            
            if state == LuxoState.ERROR:
                # Red flashing for error
                self.node.get_logger().debug("NeoPixel: Red flashing for ERROR state")
                self._neopixel_controller.breathing_effect(color, cycles=3, blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.COLLISION_AVOIDING:
                # Orange spinning dot for collision avoidance  
                self.node.get_logger().debug("NeoPixel: Orange spinning dot for COLLISION_AVOIDING state")
                self._neopixel_controller.spinning_group(color, group_size=36, cycles=1, 
                                                       delay_first_60=0.03, delay_last_16=0.06, 
                                                       blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.INITIALIZING:
                # Blue spinning dot for initialization
                self.node.get_logger().debug("NeoPixel: Blue spinning dot for INITIALIZING state")
                self._neopixel_controller.spinning_dot(color, cycles=3, delay=0.05, blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.ANIMATING:
                # White spinning group for animations
                self.node.get_logger().debug("NeoPixel: White spinning group for ANIMATING state")
                self._neopixel_controller.spinning_group(color, group_size=48, cycles=1, 
                                                       delay_first_60=0.03, delay_last_16=0.06, 
                                                       blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.PETTING:
                # White spinning group for animations
                self.node.get_logger().debug("NeoPixel: White spinning group for PETTING state")
                self._neopixel_controller.spinning_group(color, group_size=48, cycles=1, 
                                                       delay_first_60=0.03, delay_last_16=0.06, 
                                                       blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.SHUTDOWN:
                # Fade to black for shutdown
                self.node.get_logger().debug("NeoPixel: Fading to black for SHUTDOWN state")
                self._neopixel_controller.breathing_effect((0, 0, 0), cycles=1, blocking=True)
                needs_animation_timer = True
            else:
                # White solid for all other states (desk lamp mode) - no animation timer needed
                self.node.get_logger().debug(f"NeoPixel: White solid for {state.name} state")
                self._neopixel_controller.set_solid_color(*color)
                needs_animation_timer = False
            
            # Start animation timer if this state has animations
            if needs_animation_timer:
                self._start_neopixel_animation_timer()
            else:
                # Clear animation timer for non-animated states
                self._neopixel_animation_start_time = None
            
            # Update last visual state
            self._neopixel_last_visual_state = state
            
        except Exception as e:
            self.node.get_logger().error(f"Error updating NeoPixel state: {e}")
    
    def _check_pending_neopixel_update(self):
        """Check if we have a pending NeoPixel update that can now be processed"""
        if (self._neopixel_pending_state is not None and 
            not self._is_neopixel_animation_running()):
            
            # Process the pending state
            pending_state = self._neopixel_pending_state
            self._neopixel_pending_state = None
            
            self.node.get_logger().debug(f"Processing pending NeoPixel state: {pending_state.name}")
            self._update_neopixel_for_state(pending_state)
    
    def _setup_default_transitions(self):
        """Set up default state transitions."""
        # From INITIALIZING
        self.add_transition(LuxoState.INITIALIZING, LuxoState.IDLE)
        self.add_transition(LuxoState.INITIALIZING, LuxoState.ERROR)
        
        # From IDLE
        self.add_transition(LuxoState.IDLE, LuxoState.ANIMATING)
        self.add_transition(LuxoState.IDLE, LuxoState.VOICE_FOLLOWING)  # New: Can follow voice from idle
        self.add_transition(LuxoState.IDLE, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.IDLE, LuxoState.USER_CONTROL)
        self.add_transition(LuxoState.IDLE, LuxoState.EMOTION_REACTING)
        self.add_transition(LuxoState.IDLE, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.IDLE, LuxoState.PETTING)
        
        # From ANIMATING
        self.add_transition(LuxoState.ANIMATING, LuxoState.IDLE)
        self.add_transition(LuxoState.ANIMATING, LuxoState.VOICE_FOLLOWING)  # New: Can follow voice during animation
        self.add_transition(LuxoState.ANIMATING, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.ANIMATING, LuxoState.ESCAPE_MODE)
        self.add_transition(LuxoState.ANIMATING, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.ANIMATING, LuxoState.PETTING)
        
        # New: From VOICE_FOLLOWING
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.IDLE)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.ANIMATING)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.COLLISION_AVOIDING)  # Voice following can be interrupted by collision
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.ESCAPE_MODE)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.PETTING)
        
        # From COLLISION_AVOIDING
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.IDLE)
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.ESCAPE_MODE)
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.PETTING)
        # Note: NO transition from COLLISION_AVOIDING to VOICE_FOLLOWING
        
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
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.VOICE_FOLLOWING)  # New: Can follow voice during emotion
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.PETTING)
        
        # From PETTING - Can return to most states or continue petting
        self.add_transition(LuxoState.PETTING, LuxoState.IDLE)
        self.add_transition(LuxoState.PETTING, LuxoState.ANIMATING)
        self.add_transition(LuxoState.PETTING, LuxoState.VOICE_FOLLOWING)
        self.add_transition(LuxoState.PETTING, LuxoState.EMOTION_REACTING)
        self.add_transition(LuxoState.PETTING, LuxoState.COLLISION_AVOIDING)  # Safety still takes priority
        
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
        
        # Update NeoPixel display
        self._update_neopixel_for_state(state)
    
    def update(self):
        """Call this periodically to execute state callbacks and check automatic transitions."""
        with self._state_lock:
            current = self._current_state
            current_duration = self.get_state_duration()
        
        # Check for pending NeoPixel updates
        self._check_pending_neopixel_update()
        
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
    
    def can_transition_to(self, state: LuxoState) -> bool:
        """Check if a transition to the given state is valid."""
        with self._state_lock:
            for transition in self._transitions[self._current_state]:
                if transition.to_state == state:
                    if transition.condition is None or transition.condition():
                        return True
        return False
    
    def set_neopixel_brightness(self, brightness: float):
        """Adjust NeoPixel brightness for desk lamp use"""
        if self._neopixel_controller:
            self._neopixel_controller.set_brightness(brightness)
            self.node.get_logger().info(f"Desk lamp brightness set to {brightness * 100:.0f}%")
    
    def disable_neopixel_state_indication(self):
        """Temporarily disable state indication (for other NeoPixel uses)"""
        if self._neopixel_controller:
            self._neopixel_override_active = True
            self._neopixel_controller.clear_all()
            self.node.get_logger().debug("NeoPixel state indication disabled for override")
    
    def enable_neopixel_state_indication(self):
        """Re-enable state indication"""
        if self._neopixel_controller:
            self._neopixel_override_active = False
            self._update_neopixel_for_state(self._current_state)
            self.node.get_logger().debug("NeoPixel state indication re-enabled")
    
    def get_neopixel_controller(self):
        """Get direct access to NeoPixel controller for other uses"""
        return self._neopixel_controller
    
    def cleanup_neopixel(self):
        """Clean up NeoPixel resources"""
        if self._neopixel_controller:
            self._neopixel_controller.cleanup()
    
    def set_neopixel_min_animation_duration(self, duration: float):
        """Set the minimum duration for NeoPixel animations"""
        self._neopixel_min_animation_duration = duration
        self.node.get_logger().info(f"NeoPixel minimum animation duration set to {duration} seconds")
    
    def get_neopixel_animation_status(self) -> Dict[str, Any]:
        """Get current NeoPixel animation status for debugging"""
        return {
            'is_running': self._is_neopixel_animation_running(),
            'start_time': self._neopixel_animation_start_time,
            'min_duration': self._neopixel_min_animation_duration,
            'last_visual_state': self._neopixel_last_visual_state.name if self._neopixel_last_visual_state else None,
            'pending_state': self._neopixel_pending_state.name if self._neopixel_pending_state else None
        }