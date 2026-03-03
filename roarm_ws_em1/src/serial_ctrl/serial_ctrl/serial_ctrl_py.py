import rclpy
from rclpy.node import Node
import array

from sensor_msgs.msg import JointState
from std_msgs.msg import Float64

import json
import serial
import serial.serialutil


class MinimalSubscriber(Node):

    def __init__(self, port: str = "/dev/ttyAMA0", baudrate: int = 115200):
        super().__init__('serial_ctrl')
        self.position = []
        self.serial_port = port
        self.baudrate = baudrate
        self.ser = None
        
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            self.get_logger().info(f"Serial port opened: {port}")
        except serial.serialutil.SerialException as e:
            self.get_logger().warning(f"Failed to open serial port {port}: {e}")
            self.ser = None
        
        self.subscription = self.create_subscription(
            JointState,
            'joint_states',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning
    
    def posGet(self, radInput: float, direcInput: int, multiInput: float) -> int:
        """Calculate position value from radius input.
        
        Args:
            radInput: Radius in radians
            direcInput: Direction multiplier (1 or -1)
            multiInput: Additional multiplier
            
        Returns:
            Calculated position value (0-4095 range)
        """
        if radInput == 0:
            return 2047
        else:
            getPos = int(2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput) + 0.5)
            return getPos

    def listener_callback(self, msg: JointState) -> None:
        """Callback for joint state messages.
        
        Args:
            msg: JointState message containing joint positions
        """
        if self.ser is None or not self.ser.is_open:
            self.get_logger().warning("Serial port not available, skipping message")
            return
            
        try:
            a = msg.position
            data = json.dumps({
                'T': 102,
                'base': a[0],
                'shoulder': a[1],
                'elbow': a[2],
                'hand': a[3] + 3.1415926,
                'spd': 0,
                'acc': 0
            }) + "\n"
            self.ser.write(data.encode())
            self.get_logger().debug(f"Sent: {data.strip()}")
        except serial.serialutil.SerialException as e:
            self.get_logger().error(f"Serial write error: {e}")

    def on_shutdown(self) -> None:
        """Clean up serial port connection."""
        if self.ser is not None and self.ser.is_open:
            try:
                self.ser.close()
                self.get_logger().info("Serial port closed")
            except serial.serialutil.SerialException as e:
                self.get_logger().error(f"Error closing serial port: {e}")


def main(args=None):
    rclpy.init(args=args)
    minimal_subscriber = MinimalSubscriber()
    
    # Register cleanup on shutdown
    minimal_subscriber.add_on_shutdown(minimal_subscriber.on_shutdown)
    
    try:
        rclpy.spin(minimal_subscriber)
    except KeyboardInterrupt:
        pass
    finally:
        minimal_subscriber.on_shutdown()
        minimal_subscriber.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
