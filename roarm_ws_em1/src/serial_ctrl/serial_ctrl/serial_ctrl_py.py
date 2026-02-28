import rclpy
from rclpy.node import Node
import array

from sensor_msgs.msg import JointState
from std_msgs.msg import Float64

import json
import serial
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Serial port configuration with defaults
SERIAL_PORT_DEFAULT = "/dev/ttyAMA0"
BAUD_RATE_DEFAULT = 115200

class SerialController(Node):
    """ROS2 node for serial communication with robotic arm."""
    
    def __init__(self, port=SERIAL_PORT_DEFAULT, baudrate=BAUD_RATE_DEFAULT):
        super().__init__('serial_controller')
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connect_serial()
    
    def connect_serial(self):
        """Establish serial connection with error handling."""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.get_logger().info(f'Serial connection established on {self.port}@{self.baudrate}')
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to open serial port {self.port}: {e}')
            raise

#
class MinimalSubscriber(Node):

    def __init__(self):
        super().__init__('serial_ctrl')
        self.position = []
        self.subscription = self.create_subscription(
            JointState,
            'joint_states',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning
    
    def posGet(self, radInput, direcInput, multiInput):
        if radInput == 0:
            return 2047
        else:
            getPos = int(2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput) + 0.5)
            return getPos

    def listener_callback(self, msg):
        a = msg.position
        data = json.dumps({'T':102,'base':a[0],'shoulder':a[1],'elbow':a[2],'hand':a[3]+3.1415926,'spd':0,'acc':0}) + "\n"
        ser.write(data.encode())
        print(data)


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
