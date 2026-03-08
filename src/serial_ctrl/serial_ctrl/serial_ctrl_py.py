"""
ROS2 Serial Controller Node.

Subscribes to joint_states and sends commands to serial device with
adaptive speed and acceleration based on joint positions.
"""

import rclpy
from rclpy.node import Node
import json
import serial

from sensor_msgs.msg import JointState

from .adaptation_logic import AdaptationEngine


class MinimalSubscriber(Node):
    """
    ROS2 node that subscribes to joint states and controls serial device.
    Implements dynamic speed/acceleration adaptation based on joint positions.
    """
    
    def __init__(self):
        super().__init__('serial_ctrl')
        
        # Initialize the adaptation engine with default parameters
        self.adaptation = AdaptationEngine()
        
        # Serial port configuration - can be overridden via parameter
        self.declare_parameter('serial_port', '/dev/ttyAMA0')
        self.declare_parameter('baud_rate', 115200)
        
        # Get serial configuration
        self.serial_port = self.get_parameter('serial_port').get_parameter_value().string_value
        self.baud_rate = int(self.get_parameter('baud_rate').get_parameter_value().integer_value)
        
        # Initialize serial connection
        try:
            self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            self.get_logger().info(f'Serial port opened: {self.serial_port} at {self.baud_rate} baud')
        except serial.SerialException as e:
            self.get_logger().warning(f'Could not open serial port {self.serial_port}: {e}')
            self.ser = None
        
        # Track previous joint positions for velocity calculation
        self.previous_positions: list = []
        self.last_update_time: float = 0.0
        
        # Subscribe to joint states
        self.subscription = self.create_subscription(
            JointState,
            'joint_states',
            self.listener_callback,
            10)
        self.subscription  # Prevent unused variable warning
    
    def posGet(self, radInput: float, direcInput: int, multiInput: float) -> int:
        """
        Calculate position value for serial command.
        
        Args:
            radInput: Input angle in radians
            direcInput: Direction multiplier (-1 or 1)
            multiInput: Multiplier factor
            
        Returns:
            Position value (0-4095 range)
        """
        if radInput == 0:
            return 2047
        else:
            getPos = int(2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput) + 0.5)
            return getPos
    
    def listener_callback(self, msg: JointState):
        """
        Callback for joint state messages.
        Calculates adaptive speed/acceleration and sends serial command.
        """
        if self.ser is None:
            self.get_logger().warning('Serial port not available, skipping command')
            return
        
        current_positions = list(msg.position)
        
        # Initialize previous positions if needed
        if not self.previous_positions:
            self.previous_positions = current_positions.copy()
            self.last_update_time = self.get_clock().now().nanoseconds / 1e9
            return
        
        # Calculate time delta
        current_time = self.get_clock().now().nanoseconds / 1e9
        time_delta = current_time - self.last_update_time
        
        # Update previous positions
        self.previous_positions = current_positions.copy()
        self.last_update_time = current_time
        
        # Calculate adaptive speed and acceleration
        speed, accel = self.adaptation.calculate_adaptive_values(
            current_positions,
            self.previous_positions,
            time_delta
        )
        
        # Build serial command with adaptive values
        # Apply 3.1415926 offset to hand joint as per original implementation
        data = json.dumps({
            'T': 102,
            'base': current_positions[0],
            'shoulder': current_positions[1],
            'elbow': current_positions[2],
            'hand': current_positions[3] + 3.1415926,
            'spd': speed,
            'acc': accel
        }) + "\n"
        
        # Send command to serial device
        try:
            self.ser.write(data.encode())
            self.get_logger().debug(f'Sent: {data.strip()}')
        except serial.SerialException as e:
            self.get_logger().error(f'Serial write error: {e}')


def main(args=None):
    """Main entry point for the ROS2 node."""
    rclpy.init(args=args)
    minimal_subscriber = MinimalSubscriber()
    rclpy.spin(minimal_subscriber)
    
    minimal_subscriber.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
