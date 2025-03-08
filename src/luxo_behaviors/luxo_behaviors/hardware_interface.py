#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import json
import serial
import threading
import math
import time
import os
import subprocess

class RoArmHardwareInterface(Node):
    def __init__(self):
        super().__init__('roarm_hardware_interface')
        
        # Declare parameters
        self.declare_parameter('serial_port', '/dev/ttyAMA0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('enable_torque', True)
        self.declare_parameter('read_throttle', 0.1)
        
        # Get parameters
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.enable_torque_on_start = self.get_parameter('enable_torque').value
        self.read_throttle = self.get_parameter('read_throttle').value
        
        # Connection control
        self.connection_active = False
        self.connection_lock = threading.Lock()
        self.stop_thread = False
        
        # Serial port setup
        self.connect_serial()
        
        if self.connection_active:
            # Create subscription to joint_states
            self.subscription = self.create_subscription(
                JointState,
                'joint_states',
                self.joint_states_callback,
                10)
            
            self.get_logger().info("RoArm hardware interface initialized")
        else:
            self.get_logger().error("Failed to initialize hardware interface")
    
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
            self.get_logger().info(f"Serial port {self.serial_port} connected successfully at {self.baud_rate} baud")
            
            # Update connection status
            with self.connection_lock:
                self.connection_active = True
            
            # Start a thread to read responses from the arm
            self.read_thread = threading.Thread(target=self.read_serial)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            # Initialize the arm by enabling torque if configured
            if self.enable_torque_on_start:
                self.enable_torque()
                time.sleep(0.5)
                self.initialize_arm()
            
            return True
            
        except serial.SerialException as e:
            self.get_logger().error(f"Failed to open serial port: {e}")
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def enable_torque(self):
        """Enable torque on the arm."""
        # Send torque lock command (T:210, cmd:1)
        torque_cmd = json.dumps({'T': 210, 'cmd': 1})
        success = self.send_command(torque_cmd, "Enabling torque lock")
        if success:
            self.get_logger().info("Torque lock enabled")
        else:
            self.get_logger().error("Failed to enable torque")
        return success
    
    def disable_torque(self):
        """Disable torque on the arm."""
        # Send torque unlock command (T:210, cmd:0)
        torque_cmd = json.dumps({'T': 210, 'cmd': 0})
        success = self.send_command(torque_cmd, "Disabling torque lock")
        if success:
            self.get_logger().info("Torque lock disabled")
        else:
            self.get_logger().error("Failed to disable torque")
        return success
    
    def initialize_arm(self):
        """Initialize the arm by moving to home position."""
        # Send initialization command (T:100)
        init_cmd = json.dumps({'T': 100})
        success = self.send_command(init_cmd, "Initializing arm position")
        if success:
            self.get_logger().info("Arm initialized to home position")
        else:
            self.get_logger().error("Failed to initialize arm position")
        return success
    
    def send_command(self, cmd_str, description=""):
        """Send a command to the robot arm."""
        if not self.is_connected():
            self.get_logger().error("Cannot send command: Serial connection is not active")
            return False
        
        try:
            # Add description to logs
            if description:
                self.get_logger().debug(f"Sending {description}: {cmd_str}")
            
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
            self.get_logger().error(f"Serial write error: {e}")
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def is_connected(self):
        """Thread-safe method to check connection status"""
        with self.connection_lock:
            return self.connection_active and hasattr(self, 'ser') and self.ser and self.ser.is_open
    
    def read_serial(self):
        """Read serial data in a separate thread."""
        while not self.stop_thread:
            if self.is_connected():
                try:
                    # Apply throttling to reduce CPU usage
                    time.sleep(self.read_throttle)
                    
                    if self.ser.in_waiting > 0:
                        data = self.ser.readline().decode('utf-8').strip()
                        if data:
                            # Try to parse as JSON for better logging
                            try:
                                json_data = json.loads(data)
                                self.get_logger().debug(f"Received: {json.dumps(json_data)}")
                            except json.JSONDecodeError:
                                # Not JSON, just log as text
                                self.get_logger().debug(f"Received: {data}")
                except Exception as e:
                    self.get_logger().error(f"Error reading from serial: {e}")
            else:
                # Exit thread if connection is lost
                break
    
    def joint_states_callback(self, msg):
        """Handle joint states and send to hardware."""
        if not self.is_connected():
            return
        
        # Extract joint positions (in radians)
        names = msg.name
        positions = msg.position
        
        # Find indices for our joints (RoArm naming convention)
        indices = {}
        for i, name in enumerate(names):
            if name in self.get_joint_mappings().keys():
                indices[self.get_joint_mappings()[name]] = i
        
        # Make sure we have at least the main joints
        required_joints = ['base', 'shoulder', 'elbow', 'hand']
        if not all(joint in indices for joint in required_joints):
            missing = [j for j in required_joints if j not in indices]
            self.get_logger().warn(f"Missing required joints: {missing}")
            return
        
        try:
            # Use T:102 command for joint control in radians
            # From API: {"T":102,"base":0,"shoulder":0,"elbow":1.57,"hand":3.14,"spd":0,"acc":10}
            joint_cmd = {
                'T': 102,
                'base': positions[indices['base']],
                'shoulder': positions[indices['shoulder']],
                'elbow': positions[indices['elbow']],
                'hand': positions[indices['hand']] if 'hand' in indices else 3.14,  # Default closed gripper if not specified
                'spd': 0,  # Max speed
                'acc': 10  # Gentle acceleration
            }
            
            # Add wrist joint if present
            if 'wrist' in indices:
                joint_cmd['wrist'] = positions[indices['wrist']]
            
            # Send command as JSON
            cmd_str = json.dumps(joint_cmd)
            self.send_command(cmd_str, "Joint control")
            
        except Exception as e:
            self.get_logger().error(f"Error sending joint commands: {e}")
    
    def get_joint_mappings(self):
        """Return mappings between ROS joint names and RoArm joint names."""
        return {
            'base': 'base',
            'shoulder': 'shoulder',
            'elbow': 'elbow',
            'wrist': 'wrist',
            'hand': 'hand',
            # Add alternative mappings from your system if needed
            'base_to_L1': 'base',
            'L1_to_L2': 'shoulder',
            'L2_to_L3': 'elbow',
            'L3_to_L4': 'wrist'
        }
    
    def destroy_node(self):
        """Clean up when node is destroyed."""
        self.get_logger().info("Shutting down hardware interface")
        self.stop_thread = True
        
        # Disable torque before closing
        if self.is_connected():
            self.disable_torque()
        
        if self.read_thread:
            self.read_thread.join(timeout=1.0)
            
        if hasattr(self, 'ser') and self.ser and self.ser.is_open:
            self.ser.close()
            
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    
    # Create and run the node
    hardware_interface = RoArmHardwareInterface()
    
    if hardware_interface.is_connected():
        rclpy.spin(hardware_interface)
    
    # Clean up is handled in destroy_node
    hardware_interface.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()