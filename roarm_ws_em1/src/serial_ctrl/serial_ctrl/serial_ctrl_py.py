import rclpy
from rclpy.node import Node
import array

from sensor_msgs.msg import JointState
from std_msgs.msg import Float64

import json
import serial


class MinimalSubscriber(Node):

    def __init__(self):
        super().__init__('serial_ctrl')
        self.position = []
        self.serial_port = None
        
        # Initialize serial port with error handling
        try:
            self.serial_port = serial.Serial("/dev/ttyAMA0", 115200, timeout=1)
            self.get_logger().info("Serial port initialized successfully")
        except serial.SerialException as e:
            self.get_logger().warn(f"Failed to open serial port: {e}. Running in simulation mode.")
            self.serial_port = None
        
        self.subscription = self.create_subscription(
            JointState,
            'joint_states',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning
    
    def posGet(self, radInput, direcInput, multiInput):
        """Convert joint position to serial command value."""
        if radInput == 0:
            return 2047
        else:
            getPos = int(2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput) + 0.5)
            return getPos

    def listener_callback(self, msg):
        """Handle joint state messages and send commands to serial port."""
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
            
            if self.serial_port:
                self.serial_port.write(data.encode())
                self.get_logger().debug(f"Sent: {data.strip()}")
            else:
                self.get_logger().warn(f"Serial port not available, would send: {data.strip()}")
        except serial.SerialException as e:
            self.get_logger().error(f"Serial communication error: {e}")
        except Exception as e:
            self.get_logger().error(f"Unexpected error in listener callback: {e}")

    def destroy_node(self):
        """Cleanup serial port on node destruction."""
        if self.serial_port:
            try:
                self.serial_port.close()
                self.get_logger().info("Serial port closed")
            except Exception as e:
                self.get_logger().error(f"Error closing serial port: {e}")
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    minimal_subscriber = MinimalSubscriber()
    rclpy.spin(minimal_subscriber)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    minimal_subscriber.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
