#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import json
import serial
import threading
import math
import time

class RoArmHardwareInterface(Node):
    def __init__(self):
        super().__init__('roarm_hardware_interface')
        
        # Serial port setup
        try:
            self.ser = serial.Serial("/dev/ttyUSB0", baudrate=115200, dsrdtr=None)
            self.ser.setRTS(False)
            self.ser.setDTR(False)
            self.get_logger().info("Serial port connected successfully")
            
            # Start a thread to read responses from the arm
            self.stop_thread = False
            self.read_thread = threading.Thread(target=self.read_serial)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            # Initialize the arm by enabling torque
            self.enable_torque()
            
        except serial.SerialException as e:
            self.get_logger().error(f"Failed to open serial port: {e}")
            self.ser = None
            return
        
        # Create subscription to joint_states
        self.subscription = self.create_subscription(
            JointState,
            'joint_states',
            self.joint_states_callback,
            10)
        
        self.get_logger().info("RoArm hardware interface initialized")
    
    def enable_torque(self):
        """Enable torque on the arm."""
        # Send torque lock command (T:210, cmd:1)
        torque_cmd = json.dumps({'T': 210, 'cmd': 1})
        self.ser.write(torque_cmd.encode() + b'\n')
        self.get_logger().info("Enabling torque lock")
        time.sleep(0.5)  # Give time for arm to process
    
    def read_serial(self):
        """Read serial data in a separate thread."""
        while not self.stop_thread:
            if self.ser and self.ser.is_open:
                try:
                    data = self.ser.readline().decode('utf-8')
                    if data:
                        self.get_logger().info(f"Received: {data.strip()}")
                except Exception as e:
                    self.get_logger().error(f"Error reading from serial: {e}")
    
    def joint_states_callback(self, msg):
        """Handle joint states and send to hardware."""
        if not self.ser or not self.ser.is_open:
            return
        
        # Extract joint positions (in radians)
        names = msg.name
        positions = msg.position
        
        # Find indices for our joints
        indices = {}
        for i, name in enumerate(names):
            if name in ['base_to_L1', 'L1_to_L2', 'L2_to_L3', 'L3_to_L4']:
                indices[name] = i
        
        # Make sure all joints are present
        if len(indices) != 4:
            return
        
        # Try different control commands:
        
        # 1. Joint control (T:102) as per documentation
        joint_cmd = json.dumps({
            'T': 102,
            'base': positions[indices['base_to_L1']],
            'shoulder': positions[indices['L1_to_L2']],
            'elbow': positions[indices['L2_to_L3']],
            'hand': positions[indices['L3_to_L4']] + 3.1415926,
            'spd': 1,  # Try with a non-zero speed value
            'acc': 0
        })
        
        # Send joint command
        try:
            self.ser.write(joint_cmd.encode() + b'\n')
            self.get_logger().info(f"Sent joint command: {joint_cmd}")
            
            # Allow a small delay for processing
            time.sleep(0.1)
            
            # Also try with direct angle control (T:1001)
            direct_cmd = json.dumps({
                'T': 1001,
                'b': positions[indices['base_to_L1']],
                's': positions[indices['L1_to_L2']],
                'e': positions[indices['L2_to_L3']],
                't': positions[indices['L3_to_L4']]
            })
            
            self.ser.write(direct_cmd.encode() + b'\n')
            self.get_logger().info(f"Sent direct angle command: {direct_cmd}")
            
        except Exception as e:
            self.get_logger().error(f"Serial write error: {e}")
    
    def destroy_node(self):
        """Clean up when node is destroyed."""
        self.get_logger().info("Shutting down hardware interface")
        self.stop_thread = True
        if self.read_thread:
            self.read_thread.join(timeout=1.0)
        if self.ser and self.ser.is_open:
            self.ser.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    
    # Create and run the node
    hardware_interface = RoArmHardwareInterface()
    
    if hardware_interface.ser:
        rclpy.spin(hardware_interface)
    
    # Clean up is handled in destroy_node
    hardware_interface.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()