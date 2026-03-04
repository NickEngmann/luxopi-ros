import rclpy
from rclpy.node import Node
import array

from sensor_msgs.msg import JointState
from std_msgs.msg import Float64

import json
import serial
import logging
from typing import List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SerialControllerNode(Node):
    """ROS2 node for controlling serial communication with robotic arm."""
    
    DEFAULT_SERIAL_PORT = "/dev/ttyAMA0"
    DEFAULT_BAUDRATE = 115200
    HAND_OFFSET = 3.1415926
    
    def __init__(self, port: str = None, baudrate: int = None):
        """Initialize the serial controller node.
        
        Args:
            port: Serial port path. Defaults to DEFAULT_SERIAL_PORT.
            baudrate: Serial baudrate. Defaults to DEFAULT_BAUDRATE.
        """
        super().__init__('serial_ctrl')
        
        self.port = port or self.DEFAULT_SERIAL_PORT
        self.baudrate = baudrate or self.DEFAULT_BAUDRATE
        self.serial_port = None
        self.position: List[float] = []
        
        # Initialize serial connection
        self._init_serial()
        
        # Create subscription
        self.subscription = self.create_subscription(
            JointState,
            'joint_states',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning
        
        self.get_logger().info('Serial controller node initialized')
    
    def _init_serial(self):
        """Initialize serial connection with error handling."""
        try:
            self.serial_port = serial.Serial(self.port, self.baudrate, timeout=1)
            self.get_logger().info(f'Serial port {self.port} opened successfully')
        except serial.SerialException as e:
            self.get_logger().warning(f'Failed to open serial port {self.port}: {e}')
            self.get_logger().warning('Running without serial connection')
            self.serial_port = None
    
    def posGet(self, radInput: float, direcInput: int, multiInput: float) -> int:
        """Calculate position value from radius input.
        
        Args:
            radInput: Radius input in radians.
            direcInput: Direction input (-1 or 1).
            multiInput: Multiplier input.
            
        Returns:
            Calculated position value.
        """
        if radInput == 0:
            return 2047
        else:
            getPos = int(2047 + (direcInput * radInput / self.HAND_OFFSET * 2048 * multiInput) + 0.5)
            return getPos
    
    def listener_callback(self, msg: JointState):
        """Handle incoming joint state messages.
        
        Args:
            msg: JointState message containing position data.
        """
        if not self.serial_port:
            self.get_logger().warning('Serial port not available, skipping command transmission')
            return
        
        try:
            a = msg.position
            
            # Validate input data
            if len(a) < 4:
                self.get_logger().error(f'Invalid joint state: expected 4 joints, got {len(a)}')
                return
            
            # Build and send command
            data = json.dumps({
                'T': 102,
                'base': a[0],
                'shoulder': a[1],
                'elbow': a[2],
                'hand': a[3] + self.HAND_OFFSET,
                'spd': 0,
                'acc': 0
            }) + "\n"
            
            self.serial_port.write(data.encode())
            self.get_logger().debug(f'Sent command: {data.strip()}')
            
        except Exception as e:
            self.get_logger().error(f'Error processing joint state: {e}')
    
    def destroy_node(self):
        """Override destroy_node to clean up serial connection."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.get_logger().info('Serial port closed')
        super().destroy_node()


def main(args=None):
    """Main entry point for the serial controller node."""
    rclpy.init(args=args)
    node = SerialControllerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
