#!/usr/bin/env python3
#state_manager_node.py

import threading
from typing import Dict, List, Callable, Optional, Any, Tuple
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

# Import core state machine components from state_machine.py
from luxo_behaviors.state_machine import LuxoState, StateTransition

# ROS2 message imports
from std_msgs.msg import Bool, String, Header
from geometry_msgs.msg import Twist
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

# Import custom messages/services
from luxo_interfaces.msg import StateInfo
from luxo_interfaces.srv import RequestStateTransition

class StateManagerNode(Node):
    """Central state management node for Luxo robot with ROS2 integration."""
    
    def __init__(self):
        super().__init__('state_manager')
        
        # Initialize state machine components
        self._current_state = LuxoState.INITIALIZING
        self._previous_state = None
        self._state_lock = threading.RLock()
        
        # State metadata
        self._state_data = {}
        self._state_start_time = None
        self._state_history = []
        self._max_history = 100
        self._last_state_requester = "system"
        self._return_state_stack = []  # Stack to track states to return to
        self._interrupted_states = {}  # Map of state -> what it interrupted
        
        # Priority management for state requests
        self._node_priorities = {
            'behavior_coordinator': 100,  # Highest priority - safety first
            'escape_mode': 90,
            'user_control': 80,
            'voice_following': 75,  # High priority for voice commands
            'petting': 60,
            'emotion': 50,
            'animation': 40,
            'idle': 30,  # Lowest priority
            'system': 50  # Default system priority
        }
        
        # Track active nodes and their requested states
        self._active_node_states = {}  # Dict[str, Tuple[LuxoState, int, float]]
        # Format: {node_name: (requested_state, priority, timestamp)}
        
        # Automatic transitions
        self._automatic_transitions = {}
        
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
        
        # Light control state
        self._lights_enabled = True  # Track light state
        
        # Initialize NeoPixel controller
        self._neopixel_controller = None
        self._neopixel_override_active = False
        self._neopixel_animation_start_time = None
        self._neopixel_min_animation_duration = 3
        self._neopixel_last_visual_state = None
        self._neopixel_pending_state = None
        self._current_animation_duration = None
        
        self._initialize_neopixel()
        
        # State color mappings - Updated to use different white modes strategically
        self._state_colors = {
            LuxoState.IDLE: (0, 0, 0, 200),                    # Pure white LED (lowest power)
            LuxoState.INITIALIZING: (0, 100, 255, 0),          # Blue
            LuxoState.ANIMATING: (50, 50, 50, 200),           # RGB white (vibrant for animations)
            LuxoState.VOICE_FOLLOWING: (80, 80, 80, 120),      # Warm white (welcoming RGB + W)
            LuxoState.COLLISION_AVOIDING: (255, 128, 0, 0),    # Orange (warning)
            LuxoState.RETURNING_HOME: (200, 255, 100, 100),    # Light green with white
            LuxoState.ESCAPE_MODE: (255, 0, 0, 0),             # Red (danger)
            LuxoState.USER_CONTROL: (255, 255, 0, 0),          # Yellow (user input)
            LuxoState.EMOTION_REACTING: (255, 100, 255, 0),    # Purple (emotional)
            LuxoState.PETTING: (255, 0, 180, 0),               # Pink (affection)
            LuxoState.ERROR: (255, 0, 0, 0),                   # Red (error)
            LuxoState.SHUTDOWN: (50, 50, 50, 0)                # Dim gray
        }
        
        # ROS2 Publishers
        self.state_publisher = self.create_publisher(
            String,
            '/luxo/current_state',
            QoSProfile(
                reliability=QoSReliabilityPolicy.RELIABLE,
                history=QoSHistoryPolicy.KEEP_LAST,
                depth=1
            )
        )
        
        # Publish detailed state info for debugging
        self.state_info_publisher = self.create_publisher(
            StateInfo,
            '/luxo/state_info',
            10
        )
        
        # Diagnostics publisher
        self.diagnostics_publisher = self.create_publisher(
            DiagnosticArray,
            '/diagnostics',
            10
        )
        
        # ROS2 Services
        self.transition_service = self.create_service(
            RequestStateTransition,
            '/luxo/request_state_transition',
            self.handle_transition_request
        )
        
        # Heartbeat subscription to track active nodes
        self.heartbeat_sub = self.create_subscription(
            String,
            '/luxo/node_heartbeat',
            self.handle_heartbeat,
            10
        )
        
        # Add subscription for light control
        self.light_control_sub = self.create_subscription(
            Bool,
            '/luxo/light_control',
            self.light_control_callback,
            10
        )

        # Timers
        self.update_timer = self.create_timer(0.1, self.update)  # 10Hz update
        self.publish_timer = self.create_timer(0.25, self.publish_state)  # 4Hz state publishing
        self.diagnostics_timer = self.create_timer(1.0, self.publish_diagnostics)  # 1Hz diagnostics
        self.cleanup_timer = self.create_timer(5.0, self.cleanup_inactive_nodes)  # Cleanup every 5s
        
        # Initialize state machine
        self._setup_default_transitions()
        self._enter_state(self._current_state)
        
        # Add automatic transition from INITIALIZING to IDLE after X seconds
        self.add_automatic_transition(
            LuxoState.INITIALIZING, 
            LuxoState.IDLE, 
            delay_seconds=15.0
        )
        
        self.get_logger().info("State Manager Node initialized")
    
    def _initialize_neopixel(self):
        """Initialize NeoPixel controller for state visualization"""
        try:
            from luxo_behaviors.neopixel_control import NeoPixelController
            self._neopixel_controller = NeoPixelController(
                pixel_count=60,
                brightness=0.5,
                logger=self.get_logger()
            )
            if self._neopixel_controller.is_initialized():
                self.get_logger().info("NeoPixel desk lamp state visualization enabled")
            else:
                self._neopixel_controller = None
                self.get_logger().warn("NeoPixel initialization failed - continuing without visual state")
        except Exception as e:
            self.get_logger().warn(f"NeoPixel not available: {e}")
            self._neopixel_controller = None
    
    def handle_transition_request(self, request, response):
        """Handle state transition requests via service"""
        try:
            # Convert string to LuxoState
            try:
                requested_state = LuxoState[request.requested_state.upper()]
            except KeyError:
                response.success = False
                response.current_state = self._current_state.name
                response.message = f"Invalid state requested: {request.requested_state}"
                return response
            
            # Check if this request has a completion flag (if the field exists)
            is_completion = getattr(request, 'completion', False)
            
            # Process the transition request
            success = self.request_state_transition(
                requested_state, 
                request.requesting_node, 
                request.priority,
                request.force,
                is_completion  # Pass completion flag
            )
            
            response.success = success
            response.current_state = self._current_state.name
            
            if success:
                response.message = f"Transition to {request.requested_state} granted"
                self.get_logger().info(f"State transition granted: {request.requested_state} (requested by {request.requesting_node})")
            else:
                response.message = f"Transition to {request.requested_state} denied - insufficient priority or invalid transition"
                self.get_logger().info(f"State transition denied: {request.requested_state} (requested by {request.requesting_node})")
                
        except Exception as e:
            self.get_logger().error(f"Error handling transition request: {e}")
            response.success = False
            response.current_state = self._current_state.name
            response.message = f"Error: {str(e)}"
            
        return response
    
    def handle_heartbeat(self, msg):
        """Handle heartbeat messages from behavior nodes"""
        try:
            # Format: "node_name:state:priority"
            parts = msg.data.split(':')
            if len(parts) >= 1:
                node_name = parts[0]
                state = parts[1] if len(parts) > 1 else None
                priority = int(parts[2]) if len(parts) > 2 else self._node_priorities.get(node_name, 50)
                
                # Update active nodes tracking
                if state:
                    try:
                        state_enum = LuxoState[state.upper()]
                        with self._state_lock:
                            self._active_node_states[node_name] = (state_enum, priority, time.time())
                    except KeyError:
                        pass
                        
        except Exception as e:
            self.get_logger().error(f"Error handling heartbeat: {e}")
    
    def cleanup_inactive_nodes(self):
        """Remove nodes that haven't sent heartbeat recently"""
        current_time = time.time()
        timeout = 10.0  # 10 seconds
        
        with self._state_lock:
            inactive_nodes = []
            for node_name, (state, priority, timestamp) in self._active_node_states.items():
                if current_time - timestamp > timeout:
                    inactive_nodes.append(node_name)
            
            for node_name in inactive_nodes:
                del self._active_node_states[node_name]
                self.get_logger().debug(f"Removed inactive node: {node_name}")
    
    def request_state_transition(self, requested_state: LuxoState, requesting_node: str, 
                               priority: int = None, force: bool = False, 
                               is_completion: bool = False) -> bool:
        """
        Process a state transition request with priority-based resolution.
        
        Args:
            requested_state: The desired state
            requesting_node: Name of the node making the request
            priority: Priority level (higher = more important)
            force: If True, bypass priority checks (use carefully!)
            is_completion: If True, this is a completion transition (bypass priority)
            
        Returns:
            bool: True if transition was successful
        """
        with self._state_lock:
            # Use default priority if not specified
            if priority is None:
                priority = self._node_priorities.get(requesting_node, 50)
            
            # For completion transitions, check if we should return to a saved state
            if is_completion and self._return_state_stack:
                # Check if current state had interrupted something
                if self._current_state in self._interrupted_states:
                    # Return to what we interrupted
                    requested_state = self._interrupted_states[self._current_state]
                    del self._interrupted_states[self._current_state]
                    self.get_logger().info(f"Completion transition: returning to {requested_state.name}")
            
            # Check if this request has high enough priority (skip for completions)
            if not force and not is_completion and not self._has_transition_priority(requesting_node, priority):
                self.get_logger().info(
                    f"State transition request from {requesting_node} (priority {priority}) "
                    f"denied due to insufficient priority"
                )
                return False
            
            # Track what state we're interrupting (if not a completion)
            if not is_completion and self._current_state != requested_state:
                # This is an interruption - save the current state for potential return
                if priority > self._get_current_priority():
                    self._interrupted_states[requested_state] = self._current_state
                    self.get_logger().info(f"{requested_state.name} interrupted {self._current_state.name}")
            
            # Attempt the transition
            success = self.transition_to(requested_state, force)
            
            if success:
                self._last_state_requester = requesting_node
                # Update active node states
                self._active_node_states[requesting_node] = (requested_state, priority, time.time())
            
            return success

    def _get_current_priority(self) -> int:
        """Get the priority of the current state requester"""
        if self._last_state_requester in self._active_node_states:
            _, current_priority, _ = self._active_node_states[self._last_state_requester]
            return current_priority
        return 0

    def _has_transition_priority(self, requesting_node: str, priority: int) -> bool:
        """Check if a node has sufficient priority to change state"""
        # Always allow transitions from ERROR or COLLISION_AVOIDING states
        if self._current_state in [LuxoState.ERROR, LuxoState.COLLISION_AVOIDING]:
            return True
        
        # Always allow IDLE transitions (they're returns, not interruptions)
        if self._current_state == LuxoState.IDLE:
            return True

        if requesting_node == "animation_command" and (priority == 30 or priority == 50):
            return True
        # Check against current state requester's priority
        current_priority = self._get_current_priority()
        
        # Higher or equal priority can transition
        return priority >= current_priority
    
    def publish_state(self):
        """Publish current state information"""
        try:
            # Simple state name publication
            state_msg = String()
            state_msg.data = self._current_state.name
            self.state_publisher.publish(state_msg)
            
            # Detailed state info using custom message
            info_msg = StateInfo()
            info_msg.current_state = self._current_state.name
            info_msg.previous_state = self._previous_state.name if self._previous_state else 'None'
            info_msg.state_duration = self.get_state_duration()
            info_msg.requested_by = self._last_state_requester
            info_msg.priority = self._active_node_states.get(self._last_state_requester, (None, 0, 0))[1]
            info_msg.available_transitions = [t.to_state.name for t in self._transitions[self._current_state]]
            
            self.state_info_publisher.publish(info_msg)
            
        except Exception as e:
            self.get_logger().error(f"Error publishing state: {e}")
    
    def publish_diagnostics(self):
        """Publish diagnostics information"""
        try:
            diag_array = DiagnosticArray()
            diag_array.header.stamp = self.get_clock().now().to_msg()
            
            # State machine status
            status = DiagnosticStatus()
            status.name = "state_manager"
            status.level = DiagnosticStatus.OK
            status.message = f"Current state: {self._current_state.name}"
            
            # Add key-value pairs
            status.values.append(KeyValue(key="current_state", value=self._current_state.name))
            status.values.append(KeyValue(key="state_duration", value=f"{self.get_state_duration():.1f}"))
            status.values.append(KeyValue(key="active_nodes", value=str(len(self._active_node_states))))
            status.values.append(KeyValue(key="last_requester", value=self._last_state_requester))
            
            # Check for stuck states
            if self.get_state_duration() > 300.0:  # 5 minutes
                status.level = DiagnosticStatus.WARN
                status.message += " (Long duration in current state)"
            
            diag_array.status.append(status)
            self.diagnostics_publisher.publish(diag_array)
            
        except Exception as e:
            self.get_logger().error(f"Error publishing diagnostics: {e}")
    
    # ===== Original State Machine Methods (preserved) =====
    
    def _get_min_animation_duration_for_state(self, state: LuxoState) -> float:
        """Get the minimum animation duration for a specific state"""
        if state == LuxoState.PETTING:
            return 12.0
        else:
            return self._neopixel_min_animation_duration
    
    def _is_neopixel_animation_running(self) -> bool:
        """Check if a NeoPixel animation is still in its minimum duration period"""
        if self._neopixel_animation_start_time is None:
            return False
        
        elapsed = time.time() - self._neopixel_animation_start_time
        min_duration = getattr(self, '_current_animation_duration', self._neopixel_min_animation_duration)
        return elapsed < min_duration
    
    def _start_neopixel_animation_timer(self, state: LuxoState):
        """Start the timer for NeoPixel animation minimum duration"""
        self._neopixel_animation_start_time = time.time()
        duration = self._get_min_animation_duration_for_state(state)
        self._current_animation_duration = duration
        self.get_logger().debug(f"NeoPixel animation timer started - {duration} second minimum duration for {state.name}")
    
    def light_control_callback(self, msg):
        """Handle light control commands from voice commands."""
        try:
            previous_state = self._lights_enabled
            self._lights_enabled = msg.data
            
            state = "ON" if msg.data else "OFF"
            self.get_logger().info(f"Light control command received: {state}")
            
            if not self._lights_enabled:
                # Lights turned OFF - forcefully stop animations and clear NeoPixels
                if self._neopixel_controller:
                    self.get_logger().info("Lights OFF - stopping animations and clearing NeoPixels")
                    
                    # Force stop any running animations/effects
                    # self._neopixel_controller.stop_effect()
                    # time.sleep(0.25)  # Allow time for effects to stop
                    # Clear all pixels immediately
                    self._neopixel_controller.clear_all()
                    time.sleep(0.25)
                    
                    # Set override to prevent any new updates
                    self._neopixel_override_active = True
                    
                    # Clear all timing variables to prevent pending updates
                    self._neopixel_animation_start_time = None
                    self._neopixel_pending_state = None
                    self._current_animation_duration = None
                    self._neopixel_last_visual_state = None
                    
                    # Force another clear after a brief delay to ensure animation threads are stopped
                    import threading
                    def delayed_clear():
                        time.sleep(0.25)  # Wait for animation threads to stop
                        if not self._lights_enabled:  # Check again in case lights were turned back on
                            self._neopixel_controller.clear_all()
                            self.get_logger().debug("Secondary clear completed")
                    
                    clear_thread = threading.Thread(target=delayed_clear, daemon=True)
                    clear_thread.start()
                    
            elif previous_state != self._lights_enabled:
                # Lights turned ON - re-enable NeoPixel updates
                if self._neopixel_controller:
                    self.get_logger().info("Lights ON - re-enabling NeoPixel updates")
                    self._neopixel_override_active = False
                    
                    # Force update to current state
                    self._neopixel_last_visual_state = None  # Reset to force update
                    self._update_neopixel_for_state(self._current_state)
                    
        except Exception as e:
            self.get_logger().error(f"Error in light control callback: {e}")

    def _update_neopixel_for_state(self, state: LuxoState):
        """Update NeoPixel display based on current state"""
        if not self._neopixel_controller:
            return
            
        # Check if lights are disabled - if so, don't update NeoPixels and force clear
        if not self._lights_enabled:
            if not self._neopixel_override_active:
                # First time lights are off, clear and set override
                self.get_logger().debug("Lights disabled - stopping effects and clearing NeoPixels")
                # self._neopixel_controller.stop_effect()
                # time.sleep(0.25)  # Allow time for any effects to stop
                self._neopixel_controller.clear_all()
                time.sleep(0.1)  # Allow time for effects to stop
                self._neopixel_override_active = True
            else:
                # Lights are off and override is active - force clear again to override any running animations
                self._neopixel_controller.stop_effect()
                self._neopixel_controller.clear_all()
            return
        
        # If override was active but lights are now on, clear it
        if self._neopixel_override_active and self._lights_enabled:
            self._neopixel_override_active = False
            self.get_logger().debug("Lights re-enabled - clearing NeoPixel override")

        # Normal override check for animations
        if self._neopixel_override_active:
            return

        if self._is_neopixel_animation_running():
            self._neopixel_pending_state = state
            self.get_logger().debug(f"NeoPixel animation still running, queuing state {state.name}")
            return
        
        if self._neopixel_last_visual_state == state:
            self.get_logger().debug(f"NeoPixel already showing {state.name}, skipping update")
            return
        
        try:
            # if self._neopixel_last_visual_state is not None:
            #     pass
                # self._neopixel_controller.clear_all()
                # time.sleep(0.1)
                # self.get_logger().debug(f"Cleared pixels for state switch: {self._neopixel_last_visual_state.name} -> {state.name}")
            
            self._neopixel_controller.stop_effect()
            
            # Get RGBW color for state
            color = self._state_colors.get(state, (0, 0, 0, 255))  # Default to pure white
            needs_animation_timer = False
            
            if state == LuxoState.ERROR:
                self.get_logger().debug("NeoPixel: Red flashing for ERROR state")
                self._neopixel_controller.breathing_effect(color, cycles=3, blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.COLLISION_AVOIDING:
                self.get_logger().debug("NeoPixel: Orange spinning group for COLLISION_AVOIDING state")
                self._neopixel_controller.spinning_group(color, group_size=36, cycles=1, 
                                                       delay_first_60=0.03, delay_last_16=0.06, 
                                                       blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.INITIALIZING:
                self.get_logger().debug("NeoPixel: Blue spinning dot for INITIALIZING state")
                self._neopixel_controller.spinning_dot(color, cycles=3, delay=0.05, blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.ANIMATING:
                self.get_logger().debug("NeoPixel: Warm white spinning group for ANIMATING state")
                self._neopixel_controller.spinning_group(color, group_size=48, cycles=1, 
                                                       delay_first_60=0.03, delay_last_16=0.06, 
                                                       blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.PETTING:
                self.get_logger().debug("NeoPixel: Pink spinning group for PETTING state")
                self._neopixel_controller.spinning_group(color, group_size=48, cycles=1, 
                                                       delay_first_60=0.03, delay_last_16=0.06, 
                                                       blocking=False)
                needs_animation_timer = True
            elif state == LuxoState.SHUTDOWN:
                self.get_logger().debug("NeoPixel: Fading to black for SHUTDOWN state")
                self._neopixel_controller.breathing_effect((0, 0, 0, 0), cycles=1, blocking=True)
                needs_animation_timer = True
            else:
                # For static states, use the RGBW color directly
                r, g, b, w = color
                self.get_logger().debug(f"NeoPixel: RGBW({r}, {g}, {b}, {w}) solid for {state.name} state")
                self._neopixel_controller.set_solid_color(r, g, b, w)
                needs_animation_timer = False
            
            if needs_animation_timer:
                self._start_neopixel_animation_timer(state)
            else:
                self._neopixel_animation_start_time = None
                self._current_animation_duration = None
            
            self._neopixel_last_visual_state = state
            
        except Exception as e:
            self.get_logger().error(f"Error updating NeoPixel state: {e}")
    
    def _check_pending_neopixel_update(self):
        """Check if we have a pending NeoPixel update that can now be processed"""
        if (self._neopixel_pending_state is not None and 
            not self._is_neopixel_animation_running()):
            
            pending_state = self._neopixel_pending_state
            self._neopixel_pending_state = None
            
            self.get_logger().debug(f"Processing pending NeoPixel state: {pending_state.name}")
            self._update_neopixel_for_state(pending_state)
    
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
        
        # From VOICE_FOLLOWING
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.IDLE)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.ANIMATING)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.ESCAPE_MODE)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.PETTING)
        self.add_transition(LuxoState.VOICE_FOLLOWING, LuxoState.USER_CONTROL)
        
        # From COLLISION_AVOIDING
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.IDLE)
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.ESCAPE_MODE)
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.RETURNING_HOME)
        self.add_transition(LuxoState.COLLISION_AVOIDING, LuxoState.PETTING)
        
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
        self.add_transition(LuxoState.USER_CONTROL, LuxoState.ANIMATING)
        self.add_transition(LuxoState.USER_CONTROL, LuxoState.VOICE_FOLLOWING)
        self.add_transition(LuxoState.USER_CONTROL, LuxoState.RETURNING_HOME)
        
        # From EMOTION_REACTING
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.IDLE)
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.ANIMATING)
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.VOICE_FOLLOWING)
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.COLLISION_AVOIDING)
        self.add_transition(LuxoState.EMOTION_REACTING, LuxoState.PETTING)
        
        # From PETTING
        self.add_transition(LuxoState.PETTING, LuxoState.IDLE)
        self.add_transition(LuxoState.PETTING, LuxoState.ANIMATING)
        self.add_transition(LuxoState.PETTING, LuxoState.VOICE_FOLLOWING)
        self.add_transition(LuxoState.PETTING, LuxoState.EMOTION_REACTING)
        self.add_transition(LuxoState.PETTING, LuxoState.COLLISION_AVOIDING)
        
        # From ERROR
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
        """Add an automatic transition that occurs after a specified time."""
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
        """Attempt to transition to a new state."""
        with self._state_lock:
            if self._current_state == new_state:
                return True
            
            if force:
                self._exit_state(self._current_state)
                self._enter_state(new_state)
                return True
            
            valid_transition = None
            for transition in self._transitions[self._current_state]:
                if transition.to_state == new_state:
                    if transition.condition is None or transition.condition():
                        valid_transition = transition
                        break
            
            if valid_transition:
                self._exit_state(self._current_state)
                
                if valid_transition.action:
                    try:
                        valid_transition.action()
                    except Exception as e:
                        self.get_logger().error(f"Error in transition action: {e}")
                
                self._enter_state(new_state)
                return True
            else:
                self.get_logger().warn(
                    f"Invalid state transition: {self._current_state.name} -> {new_state.name}"
                )
                return False
    
    def _exit_state(self, state: LuxoState):
        """Handle exiting a state."""
        for callback in self._on_exit_callbacks[state]:
            try:
                callback()
            except Exception as e:
                self.get_logger().error(f"Error in exit callback for {state.name}: {e}")
        
        if state in self._state_data:
            del self._state_data[state]
    
    def _enter_state(self, state: LuxoState):
        """Handle entering a state."""
        self._previous_state = self._current_state
        self._current_state = state
        self._state_start_time = time.time()
        
        self._state_history.append({
            'state': state,
            'timestamp': self._state_start_time,
            'from_state': self._previous_state
        })
        
        if len(self._state_history) > self._max_history:
            self._state_history.pop(0)
        
        if self._previous_state:
            self.get_logger().info(
                f"State transition: {self._previous_state.name} -> {state.name}"
            )
        else:
            self.get_logger().info(f"Initial state: {state.name}")
        
        for callback in self._on_enter_callbacks[state]:
            try:
                callback()
            except Exception as e:
                self.get_logger().error(f"Error in enter callback for {state.name}: {e}")
        
        self._update_neopixel_for_state(state)
    
    def update(self):
        """Call this periodically to execute state callbacks and check automatic transitions."""
        with self._state_lock:
            current = self._current_state
            current_duration = self.get_state_duration()
        
        self._check_pending_neopixel_update()
        
        if current in self._automatic_transitions:
            for auto_transition in self._automatic_transitions[current]:
                if current_duration >= auto_transition['delay']:
                    if auto_transition['condition'] is None or auto_transition['condition']():
                        self.transition_to(auto_transition['to_state'])
                        break
        
        for callback in self._on_state_callbacks[current]:
            try:
                callback()
            except Exception as e:
                self.get_logger().error(f"Error in state callback for {current.name}: {e}")
    
    def get_state_history(self, limit: int = 10) -> List[Dict]:
        """Get recent state history."""
        with self._state_lock:
            return self._state_history[-limit:]
    
    def is_in_state(self, *states: LuxoState) -> bool:
        """Check if currently in any of the given states."""
        with self._state_lock:
            return self._current_state in states
    
    def cleanup(self):
        """Clean up resources"""
        if self._neopixel_controller:
            self._neopixel_controller.cleanup()


def main(args=None):
    rclpy.init(args=args)
    
    state_manager = StateManagerNode()
    
    try:
        rclpy.spin(state_manager)
    except KeyboardInterrupt:
        pass
    finally:
        state_manager.cleanup()
        state_manager.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()