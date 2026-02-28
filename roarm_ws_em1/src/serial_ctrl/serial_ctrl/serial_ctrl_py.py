import rclpy
from rclpy.node import Node
import array
import math

from sensor_msgs.msg import JointState
from std_msgs.msg import Float64

import json
import serial

# Constants for better maintainability
SERIAL_PORT = "/dev/ttyAMA0"
BAUD_RATE = 115200
PI = math.pi
POSITION_CENTER = 2048

ser = serial.Serial(SERIAL_PORT, BAUD_RATE)

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
            return POSITION_CENTER
        else:
            getPos = int(POSITION_CENTER + (direcInput * radInput / PI * POSITION_CENTER * multiInput) + 0.5)
            return getPos

    def listener_callback(self, msg):
        a = msg.position
        data = json.dumps({'T':102,'base':a[0],'shoulder':a[1],'elbow':a[2],'hand':a[3]+PI,'spd':0,'acc':0}) + "\n"
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
