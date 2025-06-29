#!/usr/bin/env python3
#command_behavior.py
"""
Command behavior module for Luxo robot.
Handles DFRobot voice recognition commands for lighting and robot control.
"""

import threading
import time
from typing import Optional, Dict, Set
from std_msgs.msg import Bool
from luxo_behaviors.state_machine import LuxoState
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
        
        # Command mapping
        self.command_mappings = {
            # Turn off light commands
            104: 'turn_off_light',
            106: 'turn_off_light', 
            108: 'turn_off_light',
            
            # Turn on light commands
            107: 'turn_on_light',
            103: 'turn_on_light',
            
            # Wake up commands
            113: 'wake_up',
            115: 'wake_up',
            128: 'wake_up',
            80: 'wake_up',
            
            # Go to sleep commands
            114: 'go_to_sleep',
            81: 'go_to_sleep',
            82: 'go_to_sleep',
            93: 'go_to_sleep'
        }
        
        # Light state tracking
        self.light_state = True  # Assume lights start on
        self.sleep_state = False  # Track if robot is sleeping
        self.sleep_start_time = None
        
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
                        self._handle_voice_command(command_id)
                
                # Sleep for the check interval
                time.sleep(self.command_check_interval)
                
            except Exception as e:
                self.node.get_logger().error(f"Error in command monitoring loop: {e}")
                time.sleep(1.0)  # Longer sleep on error
    
    def _handle_voice_command(self, command_id: int):
        """Handle received voice command."""
        with self.command_lock:
            current_time = self.node.get_clock().now()
            
            # Check cooldown
            time_since_last = (current_time - self.last_command_time).nanoseconds / 1e9
            if time_since_last < self.command_cooldown:
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
            if command_name == 'turn_on_light':
                self._turn_on_light()
            elif command_name == 'turn_off_light':
                self._turn_off_light()
            elif command_name == 'wake_up':
                self._wake_up()
            elif command_name == 'go_to_sleep':
                self._go_to_sleep()
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
    
    def _turn_on_light(self):
        """Turn on the lights."""
        self.light_state = True
        self._publish_light_state(True)
        self.node.get_logger().info("Lights turned ON")
        
        # If robot was sleeping, wake it up too
        if self.sleep_state:
            self.sleep_state = False
            self.sleep_start_time = None
            self.node.get_logger().info("Robot waking up due to light command")
        
        # Schedule completion after a short delay
        self._schedule_command_completion(1.0)
    
    def _turn_off_light(self):
        """Turn off the lights."""
        self.light_state = False
        self._publish_light_state(False)
        self.node.get_logger().info("Lights turned OFF")
        
        # Schedule completion after a short delay
        self._schedule_command_completion(1.0)
    
    def _wake_up(self):
        """Wake up the robot."""
        if self.sleep_state:
            self.sleep_state = False
            self.sleep_start_time = None
            self.light_state = True
            self._publish_light_state(True)
            self.node.get_logger().info("Robot waking up - lights ON")
            
            # Move to a neutral position if we have the functionality
            if hasattr(self, 'go_to_home_position'):
                self.go_to_home_position("Wake up command")
            
            # Schedule completion after movement
            self._schedule_command_completion(3.0)
        else:
            self.node.get_logger().info("Robot already awake")
            self._schedule_command_completion(1.0)
    
    def _go_to_sleep(self):
        """Put the robot to sleep."""
        self.sleep_state = True
        self.sleep_start_time = self.node.get_clock().now()
        self.light_state = False
        self._publish_light_state(False)
        self.node.get_logger().info("Robot going to sleep - lights OFF")
        
        # Move to rest position if we have the functionality
        if hasattr(self, 'go_to_rest_position'):
            success = self.go_to_rest_position("Sleep command")
            if success:
                self._schedule_command_completion(3.0)  # Wait for movement
            else:
                self._schedule_command_completion(1.0)  # Quick completion if movement failed
        else:
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
                return
            
            self.command_in_progress = False
            self.current_command_id = None
            self.command_completion_time = None
            
            # Return to IDLE state
            self._transition_to_state(LuxoState.IDLE)
            self.node.get_logger().info("Voice command completed - returned to IDLE")
    
    def check_command_completion(self, current_time):
        """Check if command should be completed (called from safety monitor)."""
        with self.command_lock:
            if (self.command_in_progress and 
                self.command_completion_time and 
                self._is_in_state(LuxoState.USER_CONTROL)):
                
                # Check if enough time has passed
                time_since_completion = (current_time - self.command_completion_time).nanoseconds / 1e9
                if time_since_completion > 0.5:  # 500ms grace period
                    self._complete_command()
                    return True
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
    
    def cleanup_command_behavior(self):
        """Clean up command behavior resources."""
        self._stop_command_monitoring()
        with self.command_lock:
            self.dfrobot_sensor = None
            self.command_in_progress = False
