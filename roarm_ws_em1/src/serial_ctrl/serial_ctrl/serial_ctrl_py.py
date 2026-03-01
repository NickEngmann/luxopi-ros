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

# Serial port configuration
SERIAL_PORT = "/dev/ttyAMA0"
BAUD_RATE = 115200
ser = None


def posGet(radInput, direcInput, multiInput):
    """
    Calculate position value from radius input.
    
    Args:
        radInput: Radius value in radians
        direcInput: Direction multiplier (1 or -1)
        multiInput: Multiplier factor
    
    Returns:
        int: Position value (2047 when radInput is 0)
    """
    if radInput == 0:
        return 2047
    else:
        getPos = int(2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput) + 0.5)
        return getPos


def build_serial_command(base, shoulder, elbow, hand):
    """
    Build a JSON serial command for the robot.
    
    Args:
        base: Base joint position
        shoulder: Shoulder joint position
        elbow: Elbow joint position
        hand: Hand joint position (will have offset added)
    
    Returns:
        str: JSON formatted command string with newline
    """
    # hand offset: +3.1415926 (as in original code)
    data_dict = {
        'T': 102,
        'base': base,
        'shoulder': shoulder,
        'elbow': elbow,
        'hand': hand + 3.1415926,
        'spd': 0,
        'acc': 0
    }
    return json.dumps(data_dict) + "\n"


def open_serial_port():
    """
    Open the serial port for communication.
    
    Returns:
        serial.Serial: Serial port object
    """
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
        logger.info(f"Serial port {SERIAL_PORT} opened at {BAUD_RATE} baud")
        return ser
    except serial.SerialException as e:
        logger.error(f"Failed to open serial port {SERIAL_PORT}: {e}")
        raise


def close_serial_port():
    """
    Close the serial port if it's open.
    """
    global ser
    if ser and ser.is_open:
        ser.close()
        logger.info("Serial port closed")


def send_command(data):
    """
    Send a command string to the serial port.
    
    Args:
        data: Command string to send
    
    Returns:
        bool: True if successful, False otherwise
    """
    global ser
    try:
        if ser and ser.is_open:
            ser.write(data.encode())
            logger.debug(f"Sent: {data.strip()}")
            return True
        else:
            logger.warning("Serial port not open")
            return False
    except serial.SerialException as e:
        logger.error(f"Failed to send command: {e}")
        return False


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
    
    def listener_callback(self, msg):
        """
        Callback for joint state messages.
        
        Args:
            msg: JointState message containing joint positions
        """
        try:
            a = msg.position
            data = build_serial_command(a[0], a[1], a[2], a[3])
            send_command(data)
            logger.info(f"Command sent: {data.strip()}")
        except IndexError as e:
            logger.error(f"Invalid joint positions in message: {e}")
        except Exception as e:
            logger.error(f"Error in listener_callback: {e}")


def main(args=None):
    """
    Main function to run the serial controller node.
    
    Args:
        args: Command line arguments
    """
    global ser
    rclpy.init(args=args)
    
    # Open serial port
    try:
        open_serial_port()
    except serial.SerialException as e:
        logger.error(f"Cannot proceed without serial port: {e}")
        return
    
    minimal_subscriber = MinimalSubscriber()
    
    try:
        rclpy.spin(minimal_subscriber)
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error during spin: {e}")
    finally:
        # Destroy the node explicitly
        # (optional - otherwise it will be done automatically
        # when the garbage collector destroys the node object)
        minimal_subscriber.destroy_node()
        close_serial_port()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
