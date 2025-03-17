#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import serial
import threading
import json
import time
import os
import subprocess

class SerialManager:
    """
    Manages serial communication with the robot hardware.
    Acts as an abstraction layer between hardware protocols and ROS nodes.
    """
    def __init__(self, node, serial_port='/dev/ttyAMA0', baud_rate=115200, read_throttle=0.1):
        """
        Initialize the serial manager.
        
        Args:
            node: The ROS node that owns this manager (for logging)
            serial_port: Path to the serial device
            baud_rate: Serial communication baud rate
            read_throttle: Delay between serial read attempts to reduce CPU usage
        """
        self.node = node
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.read_throttle = read_throttle
        
        # Connection control
        self.connection_active = False
        self.connection_lock = threading.Lock()
        self.stop_thread = False
        self.read_thread = None
        self.ser = None
        
        # Callback for data received
        self.data_callback = None

        # Track last successful read time to detect connection issues
        self.last_successful_read = 0
        self.connection_timeout = 5.0  # seconds without successful read before reconnection attempt
    
    def set_data_callback(self, callback):
        """Set callback function that will be called when data is received."""
        self.data_callback = callback
    
    def check_fix_permissions(self):
        """Check and fix permissions on the serial port if needed"""
        try:
            self.node.get_logger().info(f"Checking permissions on {self.serial_port}")
            
            # Check if we have read/write access
            if not os.access(self.serial_port, os.R_OK | os.W_OK):
                self.node.get_logger().warn(f"Insufficient permissions on {self.serial_port}, attempting to fix")
                
                try:
                    # Try to fix permissions using sudo chmod
                    cmd = ['sudo', 'chmod', '777', self.serial_port]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        self.node.get_logger().info("Successfully updated port permissions")
                        return True
                    else:
                        self.node.get_logger().error(f"Failed to update permissions: {result.stderr}")
                        return False
                        
                except subprocess.SubprocessError as e:
                    self.node.get_logger().error(f"Failed to run chmod command: {e}")
                    return False
            
            return True  # Permissions are already OK
            
        except Exception as e:
            self.node.get_logger().error(f"Error checking/fixing permissions: {e}")
            return False
    
    def connect(self):
        """Establish connection to the serial port"""
        # Check permissions first
        if not self.check_fix_permissions():
            self.node.get_logger().warn("Continuing without fixing permissions, may fail")
        
        try:
            self.ser = serial.Serial(self.serial_port, baudrate=self.baud_rate, dsrdtr=None, timeout=1)
            self.ser.setRTS(False)
            self.ser.setDTR(False)
            self.node.get_logger().info(f"Serial port {self.serial_port} connected successfully at {self.baud_rate} baud")
            
            # Update connection status
            with self.connection_lock:
                self.connection_active = True
            
            # Start a thread to read responses from the arm
            self.read_thread = threading.Thread(target=self.read_serial)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            return True
            
        except serial.SerialException as e:
            self.node.get_logger().error(f"Failed to open serial port: {e}")
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def is_connected(self):
        """Thread-safe method to check connection status"""
        with self.connection_lock:
            return self.connection_active and hasattr(self, 'ser') and self.ser and self.ser.is_open
    
    def send_command(self, cmd_str, description=""):
        """Send a command to the robot arm."""
        if not self.is_connected():
            self.node.get_logger().error("Cannot send command: Serial connection is not active")
            return False
        
        try:
            # Add description to logs
            if description:
                self.node.get_logger().debug(f"Sending {description}: {cmd_str}")
            
            # Ensure command ends with newline
            if not cmd_str.endswith('\n'):
                cmd_str += '\n'
            
            # Write command to serial port
            self.ser.write(cmd_str.encode())
            self.ser.flush()
            
            # Allow time to process
            time.sleep(0.1)
            
            return True
        except Exception as e:
            self.node.get_logger().error(f"Serial write error: {e}")
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def read_serial(self):
        """Read serial data in a separate thread."""
        self.node.get_logger().info("Serial read thread started")
        
        while not self.stop_thread:
            if self.is_connected():
                try:
                    # Apply throttling to reduce CPU usage
                    time.sleep(self.read_throttle)
                    
                    if self.ser.in_waiting > 0:
                        data = self.ser.readline()
                        
                        # Try to decode as UTF-8 with error handling
                        try:
                            line = data.decode('utf-8', errors='replace').strip()
                            
                            # Only process and log non-empty lines
                            if line:
                                self._process_response(line)
                                
                            # Update last successful read time
                            self.last_successful_read = time.time()
                        except UnicodeDecodeError as e:
                            # Handle decode errors more gracefully
                            self.node.get_logger().debug(f"Received non-UTF8 data: {data.hex()}")
                    
                    # Check for connection timeout - no successful reads for a while
                    if time.time() - self.last_successful_read > self.connection_timeout:
                        self.node.get_logger().warn(f"No data received for {self.connection_timeout}s, checking connection...")
                        self._check_connection()
                        
                except Exception as e:
                    self.node.get_logger().error(f"Error reading from serial: {e}")
                    time.sleep(1.0)  # Sleep longer on error
                
        self.node.get_logger().info("Serial read thread stopped")
    
    def _check_connection(self):
        """Check if connection is still active and attempt to reconnect if needed."""
        try:
            # Try to write a simple ping command
            with self.connection_lock:
                if self.ser:
                    self.ser.write(b'{"T":0}\r\n')
                    self.last_successful_read = time.time()  # Reset timeout
                else:
                    self._attempt_reconnect()
        except Exception as e:
            self.node.get_logger().error(f"Connection check failed: {e}")
            self._attempt_reconnect()
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to the serial port."""
        self.node.get_logger().warn("Attempting to reconnect to serial port")
        self.close()  # Close existing connection
        time.sleep(1.0)  # Wait a bit before reconnecting
        self.connect()  # Attempt to reconnect
    
    def _process_response(self, response):
        """Process a response from the hardware."""
        # For debug purposes, log some responses
        if len(response) > 5:  # Only log meaningful responses
            self.node.get_logger().debug(f"Received: {response}")
            
        # Here you could add more processing of responses if needed
        # For example, parsing status updates or error messages
    
    def close(self):
        """Close the serial connection and clean up resources."""
        self.node.get_logger().info("Closing serial connection")
        self.stop_thread = True
        
        if self.read_thread:
            self.read_thread.join(timeout=1.0)
            
        if hasattr(self, 'ser') and self.ser and self.ser.is_open:
            self.ser.close()
            
        with self.connection_lock:
            self.connection_active = False
            
        self.node.get_logger().info("Serial connection closed")

    def enable_torque(self):
        """Enable torque on the arm."""
        # Send torque lock command (T:210, cmd:1)
        torque_cmd = json.dumps({'T': 210, 'cmd': 1})
        success = self.send_command(torque_cmd, "Enabling torque lock")
        if success:
            self.node.get_logger().info("Torque lock enabled")
        else:
            self.node.get_logger().error("Failed to enable torque")
        return success
    
    def disable_torque(self):
        """Disable torque on the arm."""
        # Send torque unlock command (T:210, cmd:0)
        torque_cmd = json.dumps({'T': 210, 'cmd': 0})
        success = self.send_command(torque_cmd, "Disabling torque lock")
        if success:
            self.node.get_logger().info("Torque lock disabled")
        else:
            self.node.get_logger().error("Failed to disable torque")
        return success
    
    def initialize_arm(self):
        """Initialize the arm by moving to home position."""
        # Send initialization command (T:100)
        init_cmd = json.dumps({'T': 100})
        success = self.send_command(init_cmd, "Initializing arm position")
        if success:
            self.node.get_logger().info("Arm initialized to home position")
        else:
            self.node.get_logger().error("Failed to initialize arm position")
        return success
    
    def emergency_stop(self):
        """Send emergency stop command to immediately halt all movement."""
        stop_cmd = json.dumps({'T': 0})
        success = self.send_command(stop_cmd, "Emergency STOP")
        if success:
            self.node.get_logger().warn("Emergency stop activated")
        else:
            self.node.get_logger().error("Failed to send emergency stop command")
        return success
    
    def reset_emergency(self):
        """Reset emergency stop flag on the arm."""
        reset_cmd = json.dumps({'T': 999})
        success = self.send_command(reset_cmd, "Reset emergency flag")
        if success:
            self.node.get_logger().info("Emergency flag reset")
        else:
            self.node.get_logger().error("Failed to reset emergency flag")
        return success
    
    def control_single_joint(self, joint_id, rad_angle, speed=0, accel=10):
        """
        Control a single joint directly.
        
        Args:
            joint_id (int): Joint identifier (1-BASE, 2-SHOULDER, 3-ELBOW, 4-EOAT)
            rad_angle (float): Target angle in radians
            speed (int): Speed in steps/s
            accel (int): Acceleration in steps/s^2
        """
        cmd = {
            'T': 101,
            'joint': joint_id,
            'rad': rad_angle,
            'spd': speed,
            'acc': accel
        }
        success = self.send_command(json.dumps(cmd), f"Control joint {joint_id}")
        if not success:
            self.node.get_logger().error(f"Failed to control joint {joint_id}")
        return success
    
    def control_all_joints(self, base=0, shoulder=0, elbow=0, wrist=0, roll=0, hand=0, speed=0, accel=10):
        """
        Control all joints simultaneously with angles in radians.
        
        Args:
            base (float): Base joint angle in radians
            shoulder (float): Shoulder joint angle in radians
            elbow (float): Elbow joint angle in radians
            wrist (float): Wrist joint angle in radians
            roll (float): Roll joint angle in radians
            hand (float): Hand joint angle in radians
            speed (int): Speed
            accel (int): Acceleration
        """
        cmd = {
            'T': 102,
            'base': base,
            'shoulder': shoulder,
            'elbow': elbow,
            'wrist': wrist,
            'roll': roll,
            'hand': hand,
            'spd': speed,
            'acc': accel
        }
        success = self.send_command(json.dumps(cmd), "Control all joints")
        if not success:
            self.node.get_logger().error("Failed to control all joints")
        return success
    
    def control_single_axis(self, axis, position, speed=0.25):
        """
        Control a single axis movement.
        
        Args:
            axis (int): Axis identifier (1-x, 2-y, 3-z, 4-t)
            position (float): Target position
            speed (float): Movement speed
        """
        cmd = {
            'T': 103,
            'axis': axis,
            'pos': position,
            'spd': speed
        }
        success = self.send_command(json.dumps(cmd), f"Control axis {axis}")
        if not success:
            self.node.get_logger().error(f"Failed to control axis {axis}")
        return success
    
    def control_position(self, x=235, y=0, z=234, t=0, r=0, g=0, speed=0.25):
        """
        Control arm to move to specific position coordinates.
        
        Args:
            x (float): X coordinate
            y (float): Y coordinate
            z (float): Z coordinate
            t (float): Angle t in radians
            r (float): Angle r in radians
            g (float): Grip angle in radians
            speed (float): Movement speed
        """
        cmd = {
            'T': 104,
            'x': x,
            'y': y,
            'z': z,
            't': t,
            'r': r,
            'g': g,
            'spd': speed
        }
        success = self.send_command(json.dumps(cmd), "Move to position")
        if not success:
            self.node.get_logger().error("Failed to move to position")
        return success
    
    def direct_position_control(self, x=235, y=0, z=234, t=0, r=0, g=0):
        """
        Control arm to move directly to position without interpolation.
        
        Args:
            x (float): X coordinate
            y (float): Y coordinate
            z (float): Z coordinate
            t (float): Angle t in radians
            r (float): Angle r in radians
            g (float): Grip angle in radians
        """
        cmd = {
            'T': 1041,
            'x': x,
            'y': y,
            'z': z,
            't': t,
            'r': r,
            'g': g
        }
        success = self.send_command(json.dumps(cmd), "Direct position control")
        if not success:
            self.node.get_logger().error("Failed direct position control")
        return success
    
    def control_gripper(self, angle, speed=0, accel=0):
        """
        Control the gripper/hand.
        
        Args:
            angle (float): Hand angle in radians (1.57=release, 3.14=grab)
            speed (int): Movement speed
            accel (int): Acceleration
        """
        cmd = {
            'T': 106,
            'cmd': angle,
            'spd': speed,
            'acc': accel
        }
        success = self.send_command(json.dumps(cmd), f"Control gripper: {angle}")
        if not success:
            self.node.get_logger().error("Failed to control gripper")
        return success
    
    def set_gripper_torque(self, torque=200):
        """
        Set the gripper/hand torque.
        
        Args:
            torque (int): Torque limit (default: 200)
        """
        cmd = {
            'T': 107,
            'tor': torque
        }
        success = self.send_command(json.dumps(cmd), f"Set gripper torque: {torque}")
        if not success:
            self.node.get_logger().error("Failed to set gripper torque")
        return success
    
    def set_joint_pid(self, joint_id, p=16, i=0):
        """
        Set PID parameters for a specific joint.
        
        Args:
            joint_id (int): Joint ID (1-BASE, 2-SHOULDER, 3-ELBOW, 4-EOAT)
            p (int): P component (default: 16)
            i (int): I component (default: 0)
        """
        cmd = {
            'T': 108,
            'joint': joint_id,
            'p': p,
            'i': i
        }
        success = self.send_command(json.dumps(cmd), f"Set joint {joint_id} PID: P={p}, I={i}")
        if not success:
            self.node.get_logger().error(f"Failed to set joint {joint_id} PID")
        return success
    
    def reset_pid(self):
        """Reset all PID parameters to default values."""
        cmd = {'T': 109}
        success = self.send_command(json.dumps(cmd), "Reset PID parameters")
        if not success:
            self.node.get_logger().error("Failed to reset PID parameters")
        return success
    
    def set_new_x_axis(self, angle=0):
        """
        Set a new X-axis orientation.
        
        Args:
            angle (float): New X-axis angle in radians
        """
        cmd = {
            'T': 110,
            'xAxisAngle': angle
        }
        success = self.send_command(json.dumps(cmd), f"Set new X-axis: {angle}")
        if not success:
            self.node.get_logger().error("Failed to set new X-axis")
        return success
    
    def set_delay(self, delay_ms=1000):
        """
        Set a delay in milliseconds in the command sequence.
        
        Args:
            delay_ms (int): Delay in milliseconds
        """
        cmd = {
            'T': 111,
            'cmd': delay_ms
        }
        success = self.send_command(json.dumps(cmd), f"Set delay: {delay_ms}ms")
        if not success:
            self.node.get_logger().error("Failed to set delay")
        return success
    
    def set_dynamic_adaptation(self, mode=1, base=60, shoulder=110, elbow=50, wrist=50, roll=50, hand=50):
        """
        Configure dynamic external force adaptation.
        
        Args:
            mode (int): 0=stop adaptation, 1=start adaptation
            base, shoulder, elbow, wrist, roll, hand: Torque limits for each joint
        """
        if mode == 0:
            # Reset all torque limits to 1000 (effectively disabling adaptation)
            b, s, e, t, r, h = 1000, 1000, 1000, 1000, 1000, 1000
        else:
            # Use the provided torque limits
            b, s, e, t, r, h = base, shoulder, elbow, wrist, roll, hand
            
        cmd = {
            'T': 112,
            'mode': mode,
            'b': b,
            's': s,
            'e': e,
            't': t,
            'r': r,
            'h': h
        }
        success = self.send_command(json.dumps(cmd), f"Dynamic adaptation mode: {mode}")
        if not success:
            self.node.get_logger().error("Failed to set dynamic adaptation")
        return success
    
    def control_light(self, brightness=255):
        """
        Control the LED light brightness.
        
        Args:
            brightness (int): Brightness level (0-255)
        """
        if not 0 <= brightness <= 255:
            self.node.get_logger().warn(f"Brightness value {brightness} out of range (0-255), clamping")
            brightness = max(0, min(brightness, 255))
            
        cmd = {
            'T': 114,
            'led': brightness
        }
        success = self.send_command(json.dumps(cmd), f"Control light: {brightness}")
        if not success:
            self.node.get_logger().error("Failed to control light")
        return success
    
    def control_switch(self, pwm_a=0, pwm_b=0):
        """
        Control the 12V switches.
        
        Args:
            pwm_a (int): PWM A value (-255 to +255)
            pwm_b (int): PWM B value (-255 to +255)
        """
        if not -255 <= pwm_a <= 255 or not -255 <= pwm_b <= 255:
            self.node.get_logger().warn("PWM values out of range (-255 to +255), clamping")
            pwm_a = max(-255, min(pwm_a, 255))
            pwm_b = max(-255, min(pwm_b, 255))
            
        cmd = {
            'T': 113,
            'pwm_a': pwm_a,
            'pwm_b': pwm_b
        }
        success = self.send_command(json.dumps(cmd), f"Control switch: A={pwm_a}, B={pwm_b}")
        if not success:
            self.node.get_logger().error("Failed to control switch")
        return success
    
    def switch_off(self):
        """Turn off all switches."""
        cmd = {'T': 115}
        success = self.send_command(json.dumps(cmd), "Switch off")
        if not success:
            self.node.get_logger().error("Failed to switch off")
        return success
    
    def request_position_feedback(self):
        """Request current arm position feedback from servos."""
        cmd = {'T': 105}
        success = self.send_command(json.dumps(cmd), "Request position feedback")
        if not success:
            self.node.get_logger().error("Failed to request position feedback")
        return success
    
    def control_joint_angle_degrees(self, joint_id, angle, speed=10, accel=10):
        """
        Control a single joint using angles in degrees.
        
        Args:
            joint_id (int): Joint identifier (1-BASE, 2-SHOULDER, 3-ELBOW, 4-EOAT)
            angle (float): Target angle in degrees
            speed (float): Speed in degrees/s
            accel (float): Acceleration in degrees/s^2 (max 22.5)
        """
        cmd = {
            'T': 121,
            'joint': joint_id,
            'angle': angle,
            'spd': speed,
            'acc': min(accel, 22.5)  # Cap acceleration at max
        }
        success = self.send_command(json.dumps(cmd), f"Control joint {joint_id} in degrees: {angle}°")
        if not success:
            self.node.get_logger().error(f"Failed to control joint {joint_id} in degrees")
        return success
    
    def control_all_joints_degrees(self, base=0, shoulder=0, elbow=90, wrist=0, roll=0, hand=180, speed=10, accel=10):
        """
        Control all joints simultaneously with angles in degrees.
        
        Args:
            base (float): Base joint angle in degrees
            shoulder (float): Shoulder joint angle in degrees
            elbow (float): Elbow joint angle in degrees
            wrist (float): Wrist joint angle in degrees
            roll (float): Roll joint angle in degrees
            hand (float): Hand joint angle in degrees
            speed (float): Speed in degrees/s
            accel (float): Acceleration in degrees/s^2 (max 22.5)
        """
        cmd = {
            'T': 122,
            'b': base,
            's': shoulder,
            'e': elbow,
            't': wrist,
            'r': roll,
            'h': hand,
            'spd': speed,
            'acc': min(accel, 22.5)  # Cap acceleration at max
        }
        success = self.send_command(json.dumps(cmd), "Control all joints in degrees")
        if not success:
            self.node.get_logger().error("Failed to control all joints in degrees")
        return success
    
    def constant_control(self, mode=0, axis=0, command=0, speed=3):
        """
        Apply constant control (continuous movement) to a joint or axis.
        
        Args:
            mode (int): 0=angle mode, 1=position mode
            axis (int): Joint/axis to control
            command (int): 0=stop, 1=increase, 2=decrease
            speed (float): Movement speed
        """
        cmd = {
            'T': 123,
            'm': mode,
            'axis': axis,
            'cmd': command,
            'spd': speed
        }
        success = self.send_command(json.dumps(cmd), f"Constant control: mode={mode}, axis={axis}, cmd={command}")
        if not success:
            self.node.get_logger().error("Failed to apply constant control")
        return success
    
    def scan_files(self):
        """Scan files in flash memory."""
        cmd = {'T': 200}
        success = self.send_command(json.dumps(cmd), "Scanning files in flash")
        if not success:
            self.node.get_logger().error("Failed to scan files")
        return success
    
    def set_servo_id(self, raw_id, new_id):
        """
        Change a servo's ID.
        
        Args:
            raw_id (int): Current servo ID
            new_id (int): New servo ID to set
        """
        cmd = {
            'T': 501,
            'raw': raw_id,
            'new': new_id
        }
        success = self.send_command(json.dumps(cmd), f"Change servo ID: {raw_id} -> {new_id}")
        if success:
            self.node.get_logger().info(f"Servo ID changed from {raw_id} to {new_id}")
        else:
            self.node.get_logger().error(f"Failed to change servo ID")
        return success
    
    def set_middle_position(self, servo_id):
        """
        Set the current position as the middle position for a servo.
        
        Args:
            servo_id (int): Servo ID
        """
        cmd = {
            'T': 502,
            'id': servo_id
        }
        success = self.send_command(json.dumps(cmd), f"Set middle position for servo {servo_id}")
        if success:
            self.node.get_logger().info(f"Middle position set for servo {servo_id}")
        else:
            self.node.get_logger().error(f"Failed to set middle position for servo {servo_id}")
        return success
    
    def set_servo_pid(self, servo_id, p=16):
        """
        Set the P value of a single servo's PID.
        
        Args:
            servo_id (int): Servo ID
            p (int): P value
        """
        cmd = {
            'T': 503,
            'id': servo_id,
            'p': p
        }
        success = self.send_command(json.dumps(cmd), f"Set P={p} for servo {servo_id}")
        if not success:
            self.node.get_logger().error(f"Failed to set P value for servo {servo_id}")
        return success
    
    def get_free_flash_space(self):
        """Request free flash space information."""
        cmd = {'T': 601}
        success = self.send_command(json.dumps(cmd), "Request free flash space")
        if not success:
            self.node.get_logger().error("Failed to request free flash space")
        return success
    
    def clear_nvs(self):
        """Clear non-volatile storage in case of WiFi issues."""
        cmd = {'T': 604}
        success = self.send_command(json.dumps(cmd), "Clear NVS storage")
        if success:
            self.node.get_logger().info("NVS storage cleared")
        else:
            self.node.get_logger().error("Failed to clear NVS storage")
        return success
    
    def set_info_printing(self, mode=1):
        """
        Configure debug information printing level.
        
        Args:
            mode (int): 0=no debug info, 1=print debug info, 2=flow feedback
        """
        cmd = {
            'T': 605,
            'cmd': mode
        }
        success = self.send_command(json.dumps(cmd), f"Set debug print mode: {mode}")
        if not success:
            self.node.get_logger().error("Failed to set debug print mode")
        return success
    
    def reboot_controller(self):
        """Reboot the arm controller."""
        cmd = {'T': 600}
        success = self.send_command(json.dumps(cmd), "Reboot controller")
        if success:
            self.node.get_logger().info("Controller reboot requested")
        else:
            self.node.get_logger().error("Failed to request controller reboot")
        return success
