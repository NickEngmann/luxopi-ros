#!/usr/bin/env python3
#command_behavior.py
"""
Command behavior module for Luxo robot.
Handles DFRobot voice recognition commands for lighting and robot control.
"""

import threading
import time
from typing import Optional, Dict, Set
from std_msgs.msg import Bool, String
from luxo_behaviors.state_machine import LuxoState
from rclpy.action import ActionClient
from luxo_interfaces.action import PlayAnimation
import sys
import os

# Try to import from local directory first, then fallback to dev directory
try:
    # Import from local directory (same as command_behavior.py)
    from .DFRobot_DF2301Q import DFRobot_DF2301Q_I2C, DF2301Q_I2C_ADDR
    DFROBOT_AVAILABLE = True
except ImportError:
    print("DFRobot_DF2301Q not found in local directory, trying dev directory...")
    DFROBOT_AVAILABLE = False


class CommandBehavior:
    """Mixin class for DFRobot voice command functionality."""
    
    def setup_command_behavior(self):
        """Initialize command behavior attributes and hardware."""
        # Command parameters - check before declaring
        if not self.node.has_parameter('enable_voice_commands'):
            self.node.declare_parameter('enable_voice_commands', True)
        if not self.node.has_parameter('command_check_interval'):
            self.node.declare_parameter('command_check_interval', 0.1)  # 100ms check interval
        if not self.node.has_parameter('dfrobot_i2c_bus'):
            self.node.declare_parameter('dfrobot_i2c_bus', 3)
        if not self.node.has_parameter('dfrobot_volume'):
            self.node.declare_parameter('dfrobot_volume', 7)
        if not self.node.has_parameter('dfrobot_wake_time'):
            self.node.declare_parameter('dfrobot_wake_time', 20)
        
        # Load parameters
        self.voice_commands_enabled = self.node.get_parameter('enable_voice_commands').value
        self.command_check_interval = self.node.get_parameter('command_check_interval').value
        self.dfrobot_i2c_bus = self.node.get_parameter('dfrobot_i2c_bus').value
        self.dfrobot_volume = self.node.get_parameter('dfrobot_volume').value
        self.dfrobot_wake_time = self.node.get_parameter('dfrobot_wake_time').value
        
        # Command state tracking
        self.last_command_time = self.node.get_clock().now()
        self.command_cooldown = 2.0  # seconds between commands
        self.current_command_id = None
        self.command_in_progress = False
        self.command_completion_time = None
        self.last_processed_command_id = None  # Track last command to avoid re-processing
        
        # Command mapping
        self.command_mappings = {
            # Wake word commands
            1: 'wake_word',  # Custom wake word
            2: 'wake_word',  # "Hello robot"
            
            # Turn off light commands
            104: 'turn_off_light', # "Turn off the light"
            
            # Turn on light commands
            103: 'turn_on_light',  # "Turn on the light"
            
            # Brightness control commands
            105: 'increase_brightness',  # "Brighten the light"
            106: 'decrease_brightness',  # "Dim the light"
            107: 'set_brightness_max',   # "Adjust brightness to maximum"
            108: 'set_brightness_min',   # "Adjust brightness to minimum"
            
            # Color temperature commands
            109: 'increase_color_temp',  # "Increase color temperature" (warmer)
            110: 'decrease_color_temp',  # "Decrease color temperature" (cooler)
            111: 'set_color_temp_max',   # "Adjust color temperature to maximum" (warmest)
            112: 'set_color_temp_min',   # "Adjust color temperature to minimum" (coolest)
            
            # Color setting commands
            116: 'set_color_red',     # "Set to red"
            117: 'set_color_orange',  # "Set to orange"
            118: 'set_color_yellow',  # "Set to yellow"
            119: 'set_color_green',   # "Set to green"
            120: 'set_color_cyan',    # "Set to cyan"
            121: 'set_color_blue',    # "Set to blue"
            122: 'set_color_purple',  # "Set to purple"
            123: 'set_color_white',   # "Set to white"
            
            # Wake up commands
            80: 'wake_up', # "Start oscillating"
            113: 'wake_up', # "Daylight mode"
            115: 'wake_up', # "Color mode"
            
            # Go to sleep commands
            81: 'go_to_sleep', # "Stop oscillating"
            82: 'go_to_sleep', # "Reset"
            93: 'go_to_sleep', # "Stop playing"
            114: 'go_to_sleep', # "Moonlight mode"
        }
        
        # Light state tracking
        self.light_state = True  # Assume lights start on
        self.sleep_state = False  # Track if robot is sleeping
        self.sleep_start_time = None
        
        # Brightness and color tracking
        self.current_brightness = 0.8  # Track current brightness level (0.0-1.0)
        self.current_color_temp = 0.5  # Track color temperature (0.0=coolest, 1.0=warmest)
        self.color_mode = None  # Track if we're in a specific color mode
        
        # Wake word state tracking
        self.wake_word_active = False
        self.wake_word_time = None
        self.wake_word_timeout = 10.0  # Seconds to stay in USER_CONTROL after wake word
        self.light_state_before_wake = None  # Track light state before wake word
        
        # Threading for sensor polling
        self.command_thread = None
        self.command_thread_running = False
        self.command_lock = threading.Lock()
        
        # Initialize DFRobot hardware
        self.dfrobot_sensor = None
        self._initialize_dfrobot()
        
        # Create publishers for light control
        self.light_control_publisher = self.node.create_publisher(
            Bool,
            '/luxo/light_control',
            10
        )
        
        # Create publishers for advanced light control
        self.brightness_control_publisher = self.node.create_publisher(
            String,
            '/luxo/brightness_control',
            10
        )
        
        self.color_temp_control_publisher = self.node.create_publisher(
            String,
            '/luxo/color_temp_control',
            10
        )
        
        self.color_control_publisher = self.node.create_publisher(
            String,
            '/luxo/color_control',
            10
        )
        
        # Start command monitoring if enabled
        if self.voice_commands_enabled and self.dfrobot_sensor:
            self._start_command_monitoring()
        
        self.node.get_logger().info(f"Voice commands enabled: {self.voice_commands_enabled}")
    
    def _initialize_dfrobot(self):
        """Initialize DFRobot voice recognition sensor."""
        if not DFROBOT_AVAILABLE:
            self.node.get_logger().warn("DFRobot library not available - voice commands disabled")
            return
        else:
            self.node.get_logger().info("DFRobot library available - initializing sensor")
        try:
            # Initialize I2C communication
            self.dfrobot_sensor = DFRobot_DF2301Q_I2C(
                i2c_addr=DF2301Q_I2C_ADDR, 
                bus=self.dfrobot_i2c_bus
            )
            
            # Configure sensor settings
            self.dfrobot_sensor.set_volume(self.dfrobot_volume)
            self.dfrobot_sensor.set_mute_mode(0)  # 0 = unmute
            self.dfrobot_sensor.set_wake_time(self.dfrobot_wake_time)
            
            # Test sensor communication
            wake_time = self.dfrobot_sensor.get_wake_time()
            if wake_time == self.dfrobot_wake_time:
                self.node.get_logger().info(f"DFRobot sensor initialized successfully (wake_time: {wake_time})")
            else:
                self.node.get_logger().warn(f"DFRobot sensor communication issue (expected wake_time: {self.dfrobot_wake_time}, got: {wake_time})")
                
        except Exception as e:
            self.node.get_logger().error(f"Failed to initialize DFRobot sensor: {e}")
            self.dfrobot_sensor = None
    
    def _start_command_monitoring(self):
        """Start the command monitoring thread."""
        if self.command_thread is not None and self.command_thread_running:
            return
        
        self.command_thread_running = True
        self.command_thread = threading.Thread(target=self._command_monitoring_loop, daemon=True)
        self.command_thread.start()
        self.node.get_logger().info("Command monitoring thread started")
    
    def _stop_command_monitoring(self):
        """Stop the command monitoring thread."""
        self.command_thread_running = False
        if self.command_thread and self.command_thread.is_alive():
            self.command_thread.join(timeout=1.0)
        self.node.get_logger().info("Command monitoring thread stopped")
    
    def _command_monitoring_loop(self):
        """Main loop for monitoring voice commands."""
        while self.command_thread_running:
            try:
                if self.dfrobot_sensor and self.voice_commands_enabled:
                    # Check for new commands
                    command_id = self.dfrobot_sensor.get_CMDID()
                    
                    if command_id != 0:  # 0 means no command
                        # Only process if it's a new command (not the same as last processed)
                        if command_id != self.last_processed_command_id:
                            self._handle_voice_command(command_id)
                            self.last_processed_command_id = command_id
                    else:
                        # Reset when no command is detected
                        self.last_processed_command_id = None
                
                # Sleep for the check interval
                time.sleep(self.command_check_interval)
                
            except Exception as e:
                self.node.get_logger().error(f"Error in command monitoring loop: {e}")
                time.sleep(1.0)  # Longer sleep on error
    
    def _handle_voice_command(self, command_id: int):
        """Handle received voice command."""
        with self.command_lock:
            current_time = self.node.get_clock().now()
            
            # Check cooldown (but allow wake words through)
            time_since_last = (current_time - self.last_command_time).nanoseconds / 1e9
            if time_since_last < self.command_cooldown and command_id not in [1, 2]:
                self.node.get_logger().info(f"Command {command_id} ignored due to cooldown")
                return
            
            # Check if command is in our mapping
            if command_id not in self.command_mappings:
                self.node.get_logger().info(f"Unknown command ID: {command_id}")
                return
            
            command_name = self.command_mappings[command_id]
            self.node.get_logger().info(f"Voice command received: {command_name} (ID: {command_id})")
            
            # Update timing
            self.last_command_time = current_time
            self.current_command_id = command_id
            
            # Request USER_CONTROL state for command execution
            if self._request_user_control_state():
                # Execute the command
                self._execute_command(command_name, command_id)
            else:
                self.node.get_logger().warn(f"Failed to request USER_CONTROL state for command: {command_name}")
    
    def _request_user_control_state(self) -> bool:
        """Request transition to USER_CONTROL state for command execution."""
        try:
            current_state = self._get_current_state()
            
            # Don't interrupt certain critical states
            if current_state in [LuxoState.ESCAPE_MODE, LuxoState.ERROR]:
                self.node.get_logger().warn(f"Cannot execute command in {current_state.name} state")
                return False
            
            # If already in USER_CONTROL, just mark command in progress
            if current_state == LuxoState.USER_CONTROL:
                self.command_in_progress = True
                self.node.get_logger().info("Already in USER_CONTROL state")
                return True
            
            # Request transition with high priority
            success = self._transition_to_state(LuxoState.USER_CONTROL)
            if success:
                self.command_in_progress = True
                self.node.get_logger().info("Transitioned to USER_CONTROL state for voice command")
                return True
            else:
                self.node.get_logger().warn("Failed to transition to USER_CONTROL state")
                return False
                
        except Exception as e:
            self.node.get_logger().error(f"Error requesting USER_CONTROL state: {e}")
            return False
    
    def _execute_command(self, command_name: str, command_id: int):
        """Execute the specified command."""
        try:
            if command_name == 'wake_word':
                self.node.get_logger().info("Wake word detected! Entering USER_CONTROL mode")
                self._handle_wake_word()
            elif command_name == 'turn_on_light':
                if self.light_state:
                    self.node.get_logger().info("Lights are already ON")
                    return
                self.node.get_logger().info("Executing command: Turn ON light")
                self._turn_on_light()
            elif command_name == 'turn_off_light':
                if not self.light_state:
                    self.node.get_logger().info("Lights are already OFF")
                    return
                self.node.get_logger().info("Executing command: Turn OFF light")
                self._turn_off_light()
            elif command_name == 'wake_up':
                if not self.sleep_state:
                    self.node.get_logger().info("Robot is already awake")
                    return
                self.node.get_logger().info("Executing command: Wake up robot")
                self._wake_up()
            elif command_name == 'go_to_sleep':
                if self.sleep_state:
                    self.node.get_logger().info("Robot is already asleep")
                    return
                self.node.get_logger().info("Executing command: Go to sleep")
                self._go_to_sleep()
            # Brightness control commands
            elif command_name == 'increase_brightness':
                self.node.get_logger().info("Executing command: Increase brightness")
                self._adjust_brightness(increase=True)
            elif command_name == 'decrease_brightness':
                self.node.get_logger().info("Executing command: Decrease brightness")
                self._adjust_brightness(increase=False)
            elif command_name == 'set_brightness_max':
                self.node.get_logger().info("Executing command: Set brightness to maximum")
                self._set_brightness(1.0)
            elif command_name == 'set_brightness_min':
                self.node.get_logger().info("Executing command: Set brightness to minimum")
                self._set_brightness(0.1)
            # Color temperature commands
            elif command_name == 'increase_color_temp':
                self.node.get_logger().info("Executing command: Increase color temperature (warmer)")
                self._adjust_color_temperature(increase=True)
            elif command_name == 'decrease_color_temp':
                self.node.get_logger().info("Executing command: Decrease color temperature (cooler)")
                self._adjust_color_temperature(increase=False)
            elif command_name == 'set_color_temp_max':
                self.node.get_logger().info("Executing command: Set color temperature to maximum (warmest)")
                self._set_color_temperature(1.0)
            elif command_name == 'set_color_temp_min':
                self.node.get_logger().info("Executing command: Set color temperature to minimum (coolest)")
                self._set_color_temperature(0.0)
            # Color setting commands
            elif command_name == 'set_color_red':
                self.node.get_logger().info("Executing command: Set color to red")
                self._set_color('red')
            elif command_name == 'set_color_orange':
                self.node.get_logger().info("Executing command: Set color to orange")
                self._set_color('orange')
            elif command_name == 'set_color_yellow':
                self.node.get_logger().info("Executing command: Set color to yellow")
                self._set_color('yellow')
            elif command_name == 'set_color_green':
                self.node.get_logger().info("Executing command: Set color to green")
                self._set_color('green')
            elif command_name == 'set_color_cyan':
                self.node.get_logger().info("Executing command: Set color to cyan")
                self._set_color('cyan')
            elif command_name == 'set_color_blue':
                self.node.get_logger().info("Executing command: Set color to blue")
                self._set_color('blue')
            elif command_name == 'set_color_purple':
                self.node.get_logger().info("Executing command: Set color to purple")
                self._set_color('purple')
            elif command_name == 'set_color_white':
                self.node.get_logger().info("Executing command: Set color to white")
                self._set_color('white')
            else:
                self.node.get_logger().warn(f"Unknown command: {command_name}")
                return
            
            # Play confirmation sound using the command ID
            if self.dfrobot_sensor:
                try:
                    self.dfrobot_sensor.play_by_CMDID(command_id)
                except Exception as e:
                    self.node.get_logger().info(f"Error playing confirmation sound: {e}")
            
            # Schedule command completion
            self.command_completion_time = self.node.get_clock().now()
            
        except Exception as e:
            self.node.get_logger().error(f"Error executing command {command_name}: {e}")
            self._complete_command()
    
    def _handle_wake_word(self):
        """Handle wake word detection - enter USER_CONTROL state with visual feedback."""
        # Reset wake word timer even if already active (to extend timeout)
        was_already_active = self.wake_word_active
        self.wake_word_active = True
        self.wake_word_time = self.node.get_clock().now()
        # Make sure command_in_progress is True for proper tracking
        self.command_in_progress = True
        
        # Store previous light state and turn on lights for wake word visual feedback
        self.light_state_before_wake = self.light_state
        if not self.light_state:
            self.node.get_logger().info("Temporarily turning on lights for wake word LED animation")
            self.light_state = True
            self._publish_light_state(True)
            # Give time for light state to propagate
            time.sleep(0.1)
        
        if was_already_active:
            self.node.get_logger().info(f"Wake word timeout reset to {self.wake_word_timeout} seconds")
        else:
            # The state transition has already been done in _request_user_control_state
            # We just need to set up the timeout
            self.node.get_logger().info(f"Wake word active - will remain in USER_CONTROL for {self.wake_word_timeout} seconds")
    
    def _turn_on_light(self):
        """Turn on the lights."""
        self.light_state = True
        self._publish_light_state(self.light_state)
        self.node.get_logger().info("Lights turned ON")
        
        # If this was during wake word, update the before state so we don't turn them off later
        if self.wake_word_active:
            self.light_state_before_wake = True
        
        # If robot was sleeping, wake it up too
        if self.sleep_state:
            self.sleep_state = False
            self.sleep_start_time = None
            self.node.get_logger().info("Robot waking up due to light command")
        
        # If wake word is active, complete immediately to exit USER_CONTROL
        if self.wake_word_active:
            self.node.get_logger().info("Exiting USER_CONTROL after light command")
            self._schedule_command_completion(0.5)
        else:
            # Normal completion for non-wake-word initiated commands
            self._schedule_command_completion(1.0)
    
    def _turn_off_light(self):
        """Turn off the lights."""
        self.light_state = False
        self._publish_light_state(self.light_state)
        self.node.get_logger().info("Lights turned OFF")
        
        # If this was during wake word, update the before state so we don't turn them on later
        if self.wake_word_active:
            self.light_state_before_wake = False
        
        # If wake word is active, complete immediately to exit USER_CONTROL
        if self.wake_word_active:
            self.node.get_logger().info("Exiting USER_CONTROL after light command")
            self._schedule_command_completion(0.5)
        else:
            # Normal completion for non-wake-word initiated commands
            self._schedule_command_completion(1.0)
    
    def _wake_up(self):
        """Wake up the robot."""
        if self.sleep_state:
            self.node.get_logger().info("Robot waking up - disabling DEMA and turning on lights")
            
            # Disable DEMA mode to allow movement
            if hasattr(self.node, 'disable_dynamic_adaptation_mode'):
                success = self.node.disable_dynamic_adaptation_mode()
                if success:
                    time.sleep(0.2)  # Allow time for DEMA to disable
                    self.node.enable_torque()
                    self.node.get_logger().info("Torque enabled for wake up")
                    self.node.get_logger().info("DEMA disabled - robot can now move")
                    # Set up for re-enabling DEMA after wake-up completes
                    if hasattr(self.node, 'enable_dynamic_adaptation') and self.node.enable_dynamic_adaptation:
                        self.node.dynamic_adaptation_pending_resume = True
                        self.node.get_logger().info("DEMA will be re-enabled after wake-up movement completes")
                else:
                    self.node.get_logger().warn("Failed to disable DEMA for wake up")
            
            # Update sleep state
            self.sleep_state = False
            self.sleep_start_time = None
            
            # Turn on lights
            self.light_state = True
            self._publish_light_state(self.light_state)
            
            # If this was during wake word, update the before state
            if self.wake_word_active:
                self.light_state_before_wake = True
            
            # Move to a neutral/home position if available
            if hasattr(self, 'go_to_home_position'):
                self.go_to_home_position("Wake up command")
                self._schedule_command_completion(3.0)  # Wait for movement
            else:
                self._schedule_command_completion(1.0)
        else:
            self.node.get_logger().info("Robot already awake")
            self._schedule_command_completion(1.0)
    
    def _go_to_sleep(self):
        """Put the robot to sleep with sleep animation."""
        self.sleep_state = True
        self.sleep_start_time = self.node.get_clock().now()
        self.node.get_logger().info("Robot going to sleep - starting sleep animation")
        
        # Turn off lights
        self.light_state = False
        self._publish_light_state(self.light_state)

        time.sleep(0.3)  # Short delay before starting animation
        # First transition to ANIMATING state for the sleep animation
        if self._transition_to_state(LuxoState.ANIMATING):
            self.node.get_logger().info("Transitioned to ANIMATING state for sleep animation")
            
            # Now start the sleep animation
            if hasattr(self, '_play_sleep_animation'):
                success = self._play_sleep_animation()
                if success:
                    # Animation will handle completion and DEMA enabling
                    self._schedule_command_completion(10.0)  # Sleep animation is typically long
                else:
                    # If animation fails, proceed with immediate sleep
                    self._complete_sleep_sequence()
            else:
                # No animation capability, proceed with immediate sleep
                self._complete_sleep_sequence()
        else:
            self.node.get_logger().warn("Failed to transition to ANIMATING state for sleep")
            # Proceed with immediate sleep sequence
            self._complete_sleep_sequence()
    
    def _play_sleep_animation(self):
        """Play the sleep animation and set up completion callback."""
        try:
            # Create action client if it doesn't exist
            if not hasattr(self, '_animation_client'):
                self._animation_client = ActionClient(
                    self.node, 
                    PlayAnimation, 
                    'play_animation'
                )
            
            if not self._animation_client.wait_for_server(timeout_sec=2.0):
                self.node.get_logger().warn("Animation server not available for sleep command")
                return False
            
            # Create goal for sleep animation
            goal_msg = PlayAnimation.Goal()
            goal_msg.animation_name = 'sleep'
            goal_msg.allow_interruption = False  # Don't allow interruption during sleep
            
            # Send goal with completion callback
            future = self._animation_client.send_goal_async(goal_msg)
            future.add_done_callback(self._sleep_animation_goal_callback)
            
            self.node.get_logger().info("Sleep animation requested")
            return True
            
        except Exception as e:
            self.node.get_logger().error(f"Error playing sleep animation: {e}")
            return False
    
    def _sleep_animation_goal_callback(self, future):
        """Handle sleep animation goal response."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.sleep_state = False
                self.node.get_logger().warn("Sleep animation goal rejected")
                self._schedule_command_completion(1.0)
                return
            
            self.node.get_logger().info("Sleep animation goal accepted")
            
            # Wait for animation completion
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(self._sleep_animation_result_callback)
            
        except Exception as e:
            self.node.get_logger().error(f"Error in sleep animation goal callback: {e}")
            self._complete_sleep_sequence()
    
    def _sleep_animation_result_callback(self, future):
        """Handle sleep animation completion."""
        try:
            result = future.result()
            if result.result.success:
                self.node.get_logger().info("Sleep animation completed successfully")
            else:
                self.node.get_logger().warn(f"Sleep animation failed: {result.result.message}")
            
            # Complete the sleep sequence regardless of animation success
            self._complete_sleep_sequence()
            
        except Exception as e:
            self.node.get_logger().error(f"Error in sleep animation result callback: {e}")
            self._complete_sleep_sequence()
    
    def _complete_sleep_sequence(self):
        """Complete the sleep sequence: enable DEMA and turn off lights."""
        try:
            self.node.get_logger().info("Completing sleep sequence - enabling DEMA and turning off lights")
            
            # Enable DEMA mode to prevent movement
            if hasattr(self.node, 'enable_dynamic_adaptation_mode'):
                success = self.node.enable_dynamic_adaptation_mode()
                if success:
                    self.node.get_logger().info("DEMA enabled - robot is now immobilized for sleep")
                    self.node.disable_torque()  # Disable torque to prevent movement
                    self.node.get_logger().info("Torque disabled for sleep mode")
                else:
                    self.node.get_logger().warn("Failed to enable DEMA for sleep mode")
            
            # Schedule command completion
            self._schedule_command_completion(1.0)
            
        except Exception as e:
            self.node.get_logger().error(f"Error completing sleep sequence: {e}")
            self._schedule_command_completion(1.0)
    
    def _publish_light_state(self, state: bool):
        """Publish light control command."""
        try:
            msg = Bool()
            msg.data = state
            self.light_control_publisher.publish(msg)
            self.node.get_logger().info(f"Published light state: {state}")
        except Exception as e:
            self.node.get_logger().error(f"Error publishing light state: {e}")
    
    def _schedule_command_completion(self, delay_seconds: float):
        """Schedule command completion after a delay."""
        # Create a timer for completion
        def complete_after_delay():
            time.sleep(delay_seconds)
            self._complete_command()
        
        completion_thread = threading.Thread(target=complete_after_delay, daemon=True)
        completion_thread.start()
    
    def _complete_command(self):
        """Complete the current command and return to previous state."""
        with self.command_lock:
            if not self.command_in_progress:
                self.node.get_logger().debug("_complete_command called but no command in progress")
                return
            
            self.node.get_logger().info("Completing voice command - clearing state")
            
            # If wake word was active and lights were turned on temporarily, restore previous state
            if self.wake_word_active and self.light_state_before_wake is not None:
                if not self.light_state_before_wake and self.light_state:
                    # Only turn off if we turned them on for wake word and they haven't been explicitly turned on
                    # Check if robot is still sleeping (no wake up command was given)
                    if self.sleep_state:
                        self.node.get_logger().info("Wake word timeout - restoring lights OFF state")
                        self.light_state = False
                        self._publish_light_state(False)
                self.light_state_before_wake = None
            
            self.command_in_progress = False
            self.current_command_id = None
            self.command_completion_time = None
            self.wake_word_active = False
            self.wake_word_time = None
            
        # Release lock before transition to avoid deadlock
        self.node.get_logger().info("Requesting transition to IDLE state")
        # Try requesting with higher priority and force
        try:
            # Use the node's request method directly if available
            if hasattr(self.node, 'request_state_transition'):
                success = self.node.request_state_transition(LuxoState.IDLE, priority=150, force=True)
                if success:
                    self.node.get_logger().info("Voice command completed - transition to IDLE requested via node method")
                else:
                    self.node.get_logger().error("Failed to request transition to IDLE state via node method")
            else:
                # Fall back to the mixin method
                success = self._transition_to_state(LuxoState.IDLE)
                if success:
                    self.node.get_logger().info("Voice command completed - transition to IDLE requested via mixin method")
                else:
                    self.node.get_logger().error("Failed to request transition to IDLE state via mixin method")
        except Exception as e:
            self.node.get_logger().error(f"Exception requesting transition to IDLE: {e}")
    
    def check_command_completion(self, current_time):
        """Check if command should be completed (called from safety monitor)."""
        should_complete = False
        
        with self.command_lock:
            # Handle wake word timeout differently
            if self.wake_word_active and self._is_in_state(LuxoState.USER_CONTROL):
                time_since_wake = (current_time - self.wake_word_time).nanoseconds / 1e9
                if time_since_wake > self.wake_word_timeout:
                    self.node.get_logger().info("Wake word timeout - exiting USER_CONTROL")
                    should_complete = True
                    # Don't clear wake_word_active here - let _complete_command do it
            elif (self.command_in_progress and 
                  self.command_completion_time and 
                  self._is_in_state(LuxoState.USER_CONTROL)):
                # Normal command completion
                time_since_completion = (current_time - self.command_completion_time).nanoseconds / 1e9
                if time_since_completion > 0.5:  # 500ms grace period
                    should_complete = True
        
        # Call _complete_command outside the lock to avoid deadlock
        if should_complete:
            self.node.get_logger().info("Calling _complete_command from check_command_completion")
            try:
                self._complete_command()
                self.node.get_logger().info("_complete_command returned successfully")
                return True
            except Exception as e:
                self.node.get_logger().error(f"Exception in _complete_command: {e}")
                return False
        
        return False
    
    def is_sleeping(self) -> bool:
        """Check if robot is in sleep state."""
        return self.sleep_state
    
    def get_light_state(self) -> bool:
        """Get current light state."""
        return self.light_state
    
    def get_command_status(self) -> Dict:
        """Get current command status for debugging."""
        with self.command_lock:
            return {
                'enabled': self.voice_commands_enabled,
                'sensor_available': self.dfrobot_sensor is not None,
                'command_in_progress': self.command_in_progress,
                'current_command_id': self.current_command_id,
                'light_state': self.light_state,
                'sleep_state': self.sleep_state,
                'last_command_time': self.last_command_time
            }
    
    def _adjust_brightness(self, increase: bool):
        """Adjust brightness up or down by steps."""
        step = 0.2  # 20% steps
        if increase:
            self.current_brightness = min(1.0, self.current_brightness + step)
        else:
            self.current_brightness = max(0.1, self.current_brightness - step)  # Min 0.1 to keep some light
        
        self._publish_brightness_control(self.current_brightness)
        self.node.get_logger().info(f"Brightness adjusted to {self.current_brightness:.1%}")
        self._schedule_command_completion(0.5)
    
    def _set_brightness(self, level: float):
        """Set brightness to a specific level."""
        self.current_brightness = max(0.0, min(1.0, level))  # Clamp between 0.0 and 1.0
        self._publish_brightness_control(self.current_brightness)
        self.node.get_logger().info(f"Brightness set to {self.current_brightness:.1%}")
        self._schedule_command_completion(0.5)
    
    def _adjust_color_temperature(self, increase: bool):
        """Adjust color temperature warmer or cooler."""
        step = 0.2  # 20% steps
        if increase:  # Warmer
            self.current_color_temp = min(1.0, self.current_color_temp + step)
        else:  # Cooler
            self.current_color_temp = max(0.0, self.current_color_temp - step)
        
        # If we're in a color mode, transition back to white first
        if self.color_mode is not None:
            self.color_mode = None
            self._publish_color_control('white')
            time.sleep(0.1)  # Brief pause for color change
        
        self._publish_color_temperature(self.current_color_temp)
        self.node.get_logger().info(f"Color temperature adjusted to {self.current_color_temp:.1%} (0=cool, 1=warm)")
        self._schedule_command_completion(0.5)
    
    def _set_color_temperature(self, level: float):
        """Set color temperature to a specific level."""
        self.current_color_temp = max(0.0, min(1.0, level))  # Clamp between 0.0 and 1.0
        
        # If we're in a color mode, transition back to white first
        if self.color_mode is not None:
            self.color_mode = None
            self._publish_color_control('white')
            time.sleep(0.1)  # Brief pause for color change
        
        self._publish_color_temperature(self.current_color_temp)
        self.node.get_logger().info(f"Color temperature set to {self.current_color_temp:.1%} (0=cool, 1=warm)")
        self._schedule_command_completion(0.5)
    
    def _set_color(self, color: str):
        """Set the LED color."""
        if color == 'white':
            # Return to white mode with current color temperature
            self.color_mode = None
            self._publish_color_control('white')
            # Re-apply current color temperature
            self._publish_color_temperature(self.current_color_temp)
        else:
            self.color_mode = color
            self._publish_color_control(color)
        
        self.node.get_logger().info(f"Color set to {color}")
        self._schedule_command_completion(0.5)
    
    def _publish_brightness_control(self, brightness: float):
        """Publish brightness control message."""
        try:
            msg = String()
            msg.data = f"brightness:{brightness}"
            self.brightness_control_publisher.publish(msg)
            self.node.get_logger().info(f"Published brightness control: {brightness}")
        except Exception as e:
            self.node.get_logger().error(f"Error publishing brightness: {e}")
    
    def _publish_color_temperature(self, temp: float):
        """Publish color temperature control message."""
        try:
            msg = String()
            msg.data = f"color_temp:{temp}"
            self.color_temp_control_publisher.publish(msg)
            self.node.get_logger().info(f"Published color temperature control: {temp}")
        except Exception as e:
            self.node.get_logger().error(f"Error publishing color temperature: {e}")
    
    def _publish_color_control(self, color: str):
        """Publish color control message."""
        try:
            msg = String()
            msg.data = f"color:{color}"
            self.color_control_publisher.publish(msg)
            self.node.get_logger().info(f"Published color control: {color}")
        except Exception as e:
            self.node.get_logger().error(f"Error publishing color: {e}")
    
    def cleanup_command_behavior(self):
        """Clean up command behavior resources."""
        self._stop_command_monitoring()
        with self.command_lock:
            self.dfrobot_sensor = None
            self.command_in_progress = False
