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
        self.subscription = self.create_subscription(
            JointState,
            'joint_states',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning
        self.ser = None
        self._init_serial()
    
    def _init_serial(self):
        """Initialize serial connection with error handling."""
        try:
            self.ser = serial.Serial("/dev/ttyAMA0", 115200, timeout=1)
            self.get_logger().info("Serial connection initialized successfully")
        except serial.SerialException as e:
            self.get_logger().error(f"Failed to initialize serial connection: {e}")
            self.ser = None
    
    def posGet(self, radInput, direcInput, multiInput):
        """Calculate position value based on input parameters.
        
        Args:
            radInput: Input angle in radians
            direcInput: Direction multiplier (1 or -1)
            multiInput: Multiplier factor
            
        Returns:
            Calculated position value or 2047 if radInput is 0
        """
        if radInput == 0:
            return 2047
        else:
            # Fixed: removed duplicate radInput in calculation
            getPos = int(2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput) + 0.5)
            return getPos

    def listener_callback(self, msg):
        """Handle incoming joint state messages and send commands to serial device.
        
        Args:
            msg: JointState message containing joint positions
        """
        a = msg.position
        
        # Validate that we have enough joint positions
        if len(a) < 4:
            self.get_logger().warn(f"Insufficient joint positions: {len(a)} < 4")
            return
        
        # Build command dictionary with hand offset
        data_dict = {
            'T': 102,
            'base': a[0],
            'shoulder': a[1],
            'elbow': a[2],
            'hand': a[3] + 3.1415926,
            'spd': 0,
            'acc': 0
        }
        
        data = json.dumps(data_dict) + "\n"
        
        # Send data if serial connection is available
        if self.ser is not None:
            try:
                self.ser.write(data.encode())
                self.get_logger().debug(f"Sent: {data.strip()}")
            except serial.SerialException as e:
                self.get_logger().error(f"Failed to write to serial: {e}")
        else:
            self.get_logger().warn("Serial connection not available, skipping send")

    def destroy_node(self):
        """Override destroy_node to cleanup serial connection."""
        if self.ser is not None:
            try:
                self.ser.close()
                self.get_logger().info("Serial connection closed")
            except Exception as e:
                self.get_logger().error(f"Error closing serial connection: {e}")
        super().destroy_node()


def main(args=None):
    """Main entry point for the serial controller node."""
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
