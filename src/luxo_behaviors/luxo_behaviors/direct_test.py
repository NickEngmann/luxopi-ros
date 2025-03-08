#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import json
import serial
import threading
import time
import subprocess
import os

class DirectTestNode(Node):
    def __init__(self):
        super().__init__('direct_test')
        
        # Serial port settings
        self.serial_port = "/dev/ttyAMA0"
        self.baud_rate = 115200
        
        # Connection status flag
        self.connection_active = False
        self.connection_lock = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5  # Increased attempts
        
        # Serial reading control
        self.enable_serial_reading = True  # Flag to enable/disable serial reading
        self.reading_throttle = 0.1  # Time in seconds between reading attempts (throttle)
        self.print_received_data = False  # Disable printing all received data
        self.print_data_count = 0
        self.print_data_interval = 20  # Only print every Nth data packet
        
        # Declare parameters
        self.declare_parameter('enable_serial_reading', True)
        self.declare_parameter('reading_throttle', 0.1)
        self.declare_parameter('print_received_data', False)
        
        # Get parameters
        self.enable_serial_reading = self.get_parameter('enable_serial_reading').value
        self.reading_throttle = self.get_parameter('reading_throttle').value
        self.print_received_data = self.get_parameter('print_received_data').value
        
        if not self.enable_serial_reading:
            self.get_logger().info("Serial reading is disabled")
        else:
            self.get_logger().info(f"Serial reading enabled with throttle: {self.reading_throttle}s")
        
        # Open serial port
        self.connect_serial()
        
        # Wait for system to stabilize
        time.sleep(1)
        
        # Run test sequences only if connection is active
        if self.is_connected():
            self.run_tests()
    
    def check_fix_permissions(self):
        """Check and fix permissions on the serial port if needed"""
        try:
            self.get_logger().info(f"Checking permissions on {self.serial_port}")
            
            # Check if we have read/write access
            if not os.access(self.serial_port, os.R_OK | os.W_OK):
                self.get_logger().warn(f"Insufficient permissions on {self.serial_port}, attempting to fix")
                
                try:
                    # Try to fix permissions using sudo chmod
                    cmd = ['sudo', 'chmod', '777', self.serial_port]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        self.get_logger().info("Successfully updated port permissions")
                        return True
                    else:
                        self.get_logger().error(f"Failed to update permissions: {result.stderr}")
                        return False
                        
                except subprocess.SubprocessError as e:
                    self.get_logger().error(f"Failed to run chmod command: {e}")
                    return False
            
            return True  # Permissions are already OK
            
        except Exception as e:
            self.get_logger().error(f"Error checking/fixing permissions: {e}")
            return False
    
    def connect_serial(self):
        """Establish connection to the serial port"""
        # Check permissions first
        if not self.check_fix_permissions():
            self.get_logger().warn("Continuing without fixing permissions, may fail")
        
        try:
            self.ser = serial.Serial(self.serial_port, baudrate=self.baud_rate, dsrdtr=None, timeout=1)
            self.ser.setRTS(False)
            self.ser.setDTR(False)
            self.get_logger().info("Serial port connected successfully")
            
            # Update connection status
            with self.connection_lock:
                self.connection_active = True
                self.reconnect_attempts = 0
            
            # Create read thread
            self.read_thread = threading.Thread(target=self.read_serial)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            return True
            
        except serial.SerialException as e:
            err_msg = str(e)
            self.get_logger().error(f"Failed to open serial port: {err_msg}")
            
            # Check for permission errors specifically
            if "permission" in err_msg.lower() or "access" in err_msg.lower():
                self.get_logger().error("This appears to be a permission issue")
                if self.check_fix_permissions():
                    self.get_logger().info("Permissions fixed, trying connection again")
                    time.sleep(1)
                    return self.connect_serial()  # Recursive call after fixing permissions
            
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def is_connected(self):
        """Thread-safe method to check connection status"""
        with self.connection_lock:
            return self.connection_active and hasattr(self, 'ser') and self.ser and self.ser.is_open
    
    def read_serial(self):
        """Read from serial port in separate thread."""
        consecutive_errors = 0
        max_consecutive_errors = 3
        permission_error_detected = False
        
        while True:
            if not self.enable_serial_reading:
                # If reading is disabled, just sleep and check flag periodically
                time.sleep(1.0)
                continue
                
            if hasattr(self, 'ser') and self.ser and self.ser.is_open:
                try:
                    # Apply throttling to reduce load
                    time.sleep(self.reading_throttle)
                    
                    if self.ser.in_waiting > 0:
                        data = self.ser.readline().decode('utf-8').strip()
                        if data:
                            # Only print messages occasionally to reduce console spam
                            self.print_data_count += 1
                            if self.print_received_data or self.print_data_count % self.print_data_interval == 0:
                                self.get_logger().info(f"Received: {data}")
                            consecutive_errors = 0  # Reset error counter on success
                    else:
                        # Small sleep to prevent CPU hogging when no data
                        time.sleep(0.01)
                        
                except serial.SerialException as e:
                    consecutive_errors += 1
                    err_msg = str(e)
                    self.get_logger().error(f"Serial error: {err_msg}")
                    
                    # Try to clear the buffer to reset the state
                    try:
                        self.ser.reset_input_buffer()
                        self.ser.reset_output_buffer()
                    except:
                        pass
                        
                    # Check for permission issues
                    if "permission" in err_msg.lower() or "access" in err_msg.lower():
                        permission_error_detected = True
                    
                    if consecutive_errors >= max_consecutive_errors:
                        self.get_logger().error(f"Multiple serial errors, connection might be lost")
                        with self.connection_lock:
                            self.connection_active = False
                        self.attempt_reconnect(permission_error=permission_error_detected)
                        break
                        
                except Exception as e:
                    consecutive_errors += 1
                    err_msg = str(e)
                    self.get_logger().error(f"Error reading serial: {err_msg}")
                    
                    # Try to clear the buffer to reset the state
                    try:
                        self.ser.reset_input_buffer()
                        self.ser.reset_output_buffer()
                    except:
                        pass
                    
                    # Check for input/output errors that might be permission related
                    if "input/output error" in err_msg.lower() or "errno 5" in err_msg.lower():
                        permission_error_detected = True
                    
                    if consecutive_errors >= max_consecutive_errors:
                        self.get_logger().error(f"Multiple errors reading serial, connection lost")
                        with self.connection_lock:
                            self.connection_active = False
                        self.attempt_reconnect(permission_error=permission_error_detected)
                        break
            else:
                self.get_logger().error("Serial port not available")
                with self.connection_lock:
                    self.connection_active = False
                break
    
    def attempt_reconnect(self, permission_error=False):
        """Attempt to reconnect to the serial port"""
        with self.connection_lock:
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                self.get_logger().error("Max reconnection attempts reached, giving up")
                return False
            
            self.reconnect_attempts += 1
        
        self.get_logger().info(f"Attempting to reconnect (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        
        # Close previous connection if it exists
        if hasattr(self, 'ser') and self.ser:
            try:
                self.ser.close()
            except:
                pass
        
        # Wait longer before reconnecting if we had permission errors
        if permission_error:
            self.get_logger().info("Permission issues detected, attempting to fix...")
            self.check_fix_permissions()
            time.sleep(3)  # Longer wait after permission fix
        else:
            time.sleep(2)
        
        # Try to reconnect
        return self.connect_serial()
    
    def send_command(self, cmd_dict=None, cmd_str=None, description=""):
        """Send a command to the robot arm."""
        if not self.is_connected():
            self.get_logger().error("Cannot send command: Serial connection is not active")
            return False
            
        if cmd_dict is not None:
            cmd_str = json.dumps(cmd_dict)
        
        if not cmd_str:
            self.get_logger().error("No command provided")
            return False
            
        self.get_logger().info(f"Sending {description}: {cmd_str}")
        
        try:
            # Temporarily disable serial reading during command sending to avoid conflicts
            old_reading_state = self.enable_serial_reading
            self.enable_serial_reading = False
            
            # Clear input buffer before sending to avoid buffer overflow
            self.ser.reset_input_buffer()
            
            # Add newline to ensure command is properly terminated
            self.ser.write((cmd_str + '\n').encode())
            # Clear output buffer
            self.ser.flush()
            
            # Brief pause before re-enabling reading
            time.sleep(0.2)
            
            # Restore original reading state
            self.enable_serial_reading = old_reading_state
            
            # Wait for command to be processed
            time.sleep(1.0)
            return True
        except Exception as e:
            self.get_logger().error(f"Error sending command: {e}")
            # Restore reading state even on error
            self.enable_serial_reading = old_reading_state
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def toggle_serial_reading(self, enable=None):
        """Toggle or set the serial reading state"""
        if enable is not None:
            self.enable_serial_reading = enable
        else:
            self.enable_serial_reading = not self.enable_serial_reading
            
        state = "enabled" if self.enable_serial_reading else "disabled"
        self.get_logger().info(f"Serial reading is now {state}")
    
    def set_reading_throttle(self, throttle_seconds):
        """Set the throttle time between serial read attempts"""
        if throttle_seconds >= 0:
            self.reading_throttle = throttle_seconds
            self.get_logger().info(f"Serial reading throttle set to {throttle_seconds}s")
    
    def run_tests(self):
        """Run a sequence of tests with proper initialization and command format."""
        self.get_logger().info("Starting tests in 2 seconds...")
        time.sleep(2)
        
        # STEP 1: Initial setup
        self.get_logger().info("--- INITIALIZATION SEQUENCE ---")
        
        # Stop any current movement and disable torque first
        self.send_command(cmd_dict={"T": 100}, description="Go to Initial Position")
        time.sleep(1)
        
        # Enable torque
        self.send_command(cmd_dict={"T": 210, "cmd": 1}, description="Enable torque")
        time.sleep(1)
        
        # Initialize movement system - CRITICAL FIRST STEP
        self.send_command(cmd_dict={"T": 100}, description="Initialize movement system")
        time.sleep(2)  # Give it time to initialize
        
        # STEP 2: Basic system check
        self.get_logger().info("--- BASIC SYSTEM CHECK ---")
        
        # Get current servo positions
        self.send_command(cmd_dict={"T": 105}, description="Get servo positions")
        time.sleep(1)
        
        # STEP 3: Joint movement tests
        self.get_logger().info("--- JOINT MOVEMENT TESTS ---")
        
        # Test each joint individually
        joints = ["base", "shoulder", "elbow", "wrist", "roll", "hand"]
        
        for i, joint in enumerate(joints):
            # Skip arm rotation for now to keep test simpler
            if joint == "roll":
                continue
                
            # Single joint test with proper command format
            self.get_logger().info(f"Testing {joint} joint...")
            cmd = {
                "T": 101,
                "joint": i,
                "rad": 0.3,  # Small movement
                "spd": 0,
                "acc": 2
            }
            self.send_command(cmd_dict=cmd, description=f"Move {joint} joint")
            time.sleep(2)
            
            # Return to neutral
            cmd["rad"] = 0.0
            self.send_command(cmd_dict=cmd, description=f"Reset {joint} joint")
            time.sleep(1.5)
        
        # STEP 4: Hand/gripper test
        self.get_logger().info("--- GRIPPER TEST ---")
        
        # Open gripper
        self.send_command(cmd_dict={"T": 106, "cmd": 1.57, "spd": 0, "acc": 2}, 
                          description="Open gripper")
        time.sleep(2)
        
        # Close gripper
        self.send_command(cmd_dict={"T": 106, "cmd": 3.14, "spd": 0, "acc": 2}, 
                          description="Close gripper")
        time.sleep(2)
        
        # STEP 5: Full arm movement
        self.get_logger().info("--- FULL ARM MOVEMENT ---")
        
        # Move all joints simultaneously
        cmd = {
            "T": 102,
            "base": 0.3,
            "shoulder": 0.3,
            "elbow": 0.3,
            "wrist": 0.3,
            "roll": 0,
            "hand": 3.14,
            "spd": 0,
            "acc": 2
        }
        self.send_command(cmd_dict=cmd, description="Move all joints")
        time.sleep(3)
        
        # Return to home position
        cmd = {
            "T": 102,
            "base": 0,
            "shoulder": 0,
            "elbow": 0,
            "wrist": 0,
            "roll": 0,
            "hand": 3.14,
            "spd": 0,
            "acc": 2
        }
        self.send_command(cmd_dict=cmd, description="Return to home position")
        time.sleep(3)
        
        # STEP 6: Position-based control
        self.get_logger().info("--- POSITION-BASED CONTROL ---")
        
        # Move to specific XYZ coordinates - example position
        cmd = {
            "T": 104,
            "x": 235,
            "y": 0,
            "z": 200,
            "t": 0,
            "r": 0,
            "g": 3.14,
            "spd": 0.25
        }
        self.send_command(cmd_dict=cmd, description="Move to XYZ position")
        time.sleep(6)  # This movement can take longer
        
        # STEP 7: Direct XYZ control
        cmd = {
            "T": 1041,
            "x": 235,
            "y": 50,
            "z": 200,
            "t": 0,
            "r": 0,
            "g": 3.14
        }
        self.send_command(cmd_dict=cmd, description="Direct XYZ control")
        time.sleep(5)
        
        # Return to neutral position using angle control
        self.get_logger().info("--- RETURNING TO NEUTRAL ---")
        cmd = {
            "T": 122,
            "b": 0,
            "s": 0,
            "e": 0,
            "t": 0,
            "r": 0,
            "h": 180,  # Hand at 180 degrees
            "spd": 0,
            "acc": 2
        }
        self.send_command(cmd_dict=cmd, description="Return to neutral using angles")
        time.sleep(3)
        
        # STEP 8: Get final position data
        self.send_command(cmd_dict={"T": 105}, description="Get final servo positions")
        
        self.get_logger().info("Test sequence completed!")
    
    def close(self):
        """Close the serial connection."""
        if hasattr(self, 'ser') and self.ser and self.ser.is_open:
            # Disable torque before closing
            if self.is_connected():
                self.send_command(cmd_dict={"T": 210, "cmd": 0}, description="Disable torque")
                time.sleep(0.5)
            
            self.ser.close()
            self.get_logger().info("Serial port closed")
        
        with self.connection_lock:
            self.connection_active = False

def main(args=None):
    rclpy.init(args=args)
    node = DirectTestNode()
    
    # Allow time for the test sequence to complete
    try:
        # Run with serial reading initially enabled just long enough to establish connection,
        # then disable it for the main part of the tests
        time.sleep(3)  # Give time to establish connection
        
        # Disable serial reading for the main part of the tests
        # This should reduce errors
        node.toggle_serial_reading(False)
        
        # Modified to spin multiple times with timeouts to be more responsive
        end_time = time.time() + 60.0  # 60 second timeout total
        while time.time() < end_time and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=1.0)
            if not node.is_connected() and node.reconnect_attempts >= node.max_reconnect_attempts:
                node.get_logger().error("Connection permanently lost, terminating")
                break
    except KeyboardInterrupt:
        pass
    
    node.close()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()