#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_srvs.srv import SetBool
import json
import serial
import time

class DynamicAdaptationToggle(Node):
    """
    A simple service node to toggle the dynamic adaptation mode
    of the RoArm hardware.
    """
    
    def __init__(self):
        super().__init__('dynamic_adaptation_toggle')
        
        # Declare parameters
        self.declare_parameter('serial_port', '/dev/ttyAMA0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('base_limit', 60)
        self.declare_parameter('shoulder_limit', 110)
        self.declare_parameter('elbow_limit', 50)
        self.declare_parameter('wrist_limit', 50)
        self.declare_parameter('roll_limit', 50)
        self.declare_parameter('hand_limit', 50)
        
        # Get parameters
        self.serial_port = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.base_limit = self.get_parameter('base_limit').value
        self.shoulder_limit = self.get_parameter('shoulder_limit').value
        self.elbow_limit = self.get_parameter('elbow_limit').value
        self.wrist_limit = self.get_parameter('wrist_limit').value
        self.roll_limit = self.get_parameter('roll_limit').value
        self.hand_limit = self.get_parameter('hand_limit').value
        
        # Create the service
        self.srv = self.create_service(
            SetBool,
            'toggle_dynamic_adaptation',
            self.toggle_callback
        )
        
        # Initialize serial connection
        self.ser = None
        try:
            self.ser = serial.Serial(
                self.serial_port,
                self.baud_rate,
                timeout=1
            )
            self.get_logger().info(f"Connected to {self.serial_port} at {self.baud_rate} baud")
        except Exception as e:
            self.get_logger().error(f"Failed to connect to serial port: {e}")
        
        self.get_logger().info("Dynamic adaptation toggle service started")
    
    def toggle_callback(self, request, response):
        """Handle service requests to toggle dynamic adaptation mode"""
        if self.ser is None or not self.ser.is_open:
            response.success = False
            response.message = "Serial port not connected"
            return response
        
        try:
            if request.data:  # Enable dynamic adaptation
                cmd = {
                    'T': 112,
                    'mode': 1,
                    'b': self.base_limit,
                    's': self.shoulder_limit,
                    'e': self.elbow_limit,
                    't': self.wrist_limit,
                    'r': self.roll_limit,
                    'h': self.hand_limit
                }
                cmd_str = json.dumps(cmd)
                self.get_logger().info(f"Enabling dynamic adaptation mode with command: {cmd_str}")
                self.ser.write((cmd_str + '\n').encode())
                time.sleep(0.1)  # Give device time to process
                
                response.success = True
                response.message = "Dynamic adaptation mode enabled"
            else:  # Disable dynamic adaptation
                cmd = {
                    'T': 112,
                    'mode': 0,
                    'b': 1000,
                    's': 1000,
                    'e': 1000,
                    't': 1000,
                    'r': 1000,
                    'h': 1000
                }
                cmd_str = json.dumps(cmd)
                self.get_logger().info(f"Disabling dynamic adaptation mode with command: {cmd_str}")
                self.ser.write((cmd_str + '\n').encode())
                time.sleep(0.1)  # Give device time to process
                
                response.success = True
                response.message = "Dynamic adaptation mode disabled"
            
            return response
            
        except Exception as e:
            self.get_logger().error(f"Error toggling dynamic adaptation mode: {e}")
            response.success = False
            response.message = f"Error: {str(e)}"
            return response
    
    def destroy_node(self):
        """Clean up resources when the node is destroyed"""
        if self.ser and self.ser.is_open:
            # Make sure we disable dynamic adaptation before closing
            try:
                cmd = {
                    'T': 112,
                    'mode': 0,
                    'b': 1000,
                    's': 1000,
                    'e': 1000,
                    't': 1000,
                    'r': 1000,
                    'h': 1000
                }
                cmd_str = json.dumps(cmd)
                self.ser.write((cmd_str + '\n').encode())
                time.sleep(0.1)  # Give device time to process
            except Exception:
                pass
            
            self.ser.close()
        
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = DynamicAdaptationToggle()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
