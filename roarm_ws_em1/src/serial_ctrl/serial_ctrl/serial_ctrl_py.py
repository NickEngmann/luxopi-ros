import rclpy
from rclpy.node import Node
import array

from sensor_msgs.msg import JointState
from std_msgs.msg import Float64

import json
import serial

# Constants for serial communication
DEFAULT_SERIAL_PORT = "/dev/ttyAMA0"
DEFAULT_BAUD_RATE = 115200
MAGIC_NUMBER = 102
PI = 3.1415926
MAX_POSITION = 2047
POSITION_MULTIPLIER = 2048

# Serial port will be initialized in the node constructor
_serial_port = None


def get_serial_port():
    """Get or create the serial port instance."""
    global _serial_port
    if _serial_port is None:
        _serial_port = serial.Serial(DEFAULT_SERIAL_PORT, DEFAULT_BAUD_RATE)
    return _serial_port


def close_serial_port():
    """Close the serial port connection."""
    global _serial_port
    if _serial_port is not None:
        try:
            _serial_port.close()
        except Exception:
            pass
        _serial_port = None

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
