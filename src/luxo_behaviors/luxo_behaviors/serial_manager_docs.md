# LuxoPi Serial Manager Documentation

## Overview

The `serial_manager.py` module provides a comprehensive interface for serial communication with the RoArm-M3 robotic arm controller. It handles connection management, command execution, position control, and error recovery.

## Class: SerialManager

### Class Structure

```python
class SerialManager:
    """
    Manages serial communication with the RoArm-M3 controller.
    
    Features:
    - Automatic connection management
    - Thread-safe command execution
    - Position control for all joints
    - Error recovery and logging
    - Reboot capability
    """
```

### Initialization

#### Constructor Parameters

```python
def __init__(self, node, port='/dev/ttyUSB0', baudrate=115200):
    """
    Initialize SerialManager.
    
    Args:
        node: ROS2 node instance for logging
        port (str): Serial port path (default: '/dev/ttyUSB0')
        baudrate (int): Communication speed (default: 115200)
    """
```

### Core Methods

#### Connection Management

##### `connect() -> bool`
Establishes connection to the serial port.

**Returns:**
- `bool`: True if connection successful, False otherwise

**Example:**
```python
if serial_manager.connect():
    self.logger.info("Connected to RoArm controller")
else:
    self.logger.error("Failed to connect to RoArm controller")
```

##### `disconnect() -> None`
Closes the serial connection safely.

**Example:**
```python
serial_manager.disconnect()
self.logger.info("Disconnected from RoArm controller")
```

##### `is_connected() -> bool`
Checks if currently connected.

**Returns:**
- `bool`: True if connected, False otherwise

#### Position Control

##### `control_position(x=235, y=0, z=234, t=0, r=0, g=0, speed=0.25) -> bool`
Moves the arm to a specific position.

**Parameters:**
- `x` (float): X coordinate (default: 235mm)
- `y` (float): Y coordinate (default: 0mm)
- `z` (float): Z coordinate (default: 234mm)
- `t` (float): Twist angle (default: 0 degrees)
- `r` (float): Roll angle (default: 0 degrees)
- `g` (float): Grip angle (default: 0 degrees)
- `speed` (float): Movement speed (default: 0.25)

**Returns:**
- `bool`: True if command executed successfully

**Example:**
```python
success = serial_manager.control_position(
    x=200, y=100, z=150,
    t=45, r=0, g=0,
    speed=0.5
)
```

##### `control_joint(joint_id, position, speed=0.25) -> bool`
Controls a specific joint.

**Parameters:**
- `joint_id` (int): Joint identifier (0-6)
- `position` (float): Target position
- `speed` (float): Movement speed (default: 0.25)

**Returns:**
- `bool`: True if command executed successfully

**Example:**
```python
success = serial_manager.control_joint(0, 45.0, speed=0.3)
```

##### `control_gripper(open_angle=0, close_angle=180, speed=0.25) -> bool`
Controls the gripper.

**Parameters:**
- `open_angle` (float): Open position (default: 0)
- `close_angle` (float): Closed position (default: 180)
- `speed` (float): Movement speed (default: 0.25)

**Returns:**
- `bool`: True if command executed successfully

**Example:**
```python
success = serial_manager.control_gripper(open_angle=100, speed=0.2)
```

#### Command Execution

##### `send_command(command: str) -> str`
Sends a raw command to the controller.

**Parameters:**
- `command` (str): Command string to send

**Returns:**
- `str`: Response from controller

**Example:**
```python
response = serial_manager.send_command("STATUS")
print(f"Controller status: {response}")
```

##### `get_status() -> dict`
Retrieves current controller status.

**Returns:**
- `dict`: Status information including:
  - Connection state
  - Joint positions
  - Error codes
  - System information

**Example:**
```python
status = serial_manager.get_status()
if status.get('error_code') == 0:
    self.logger.info("Controller operating normally")
```

#### Error Handling

##### `handle_error(error_code: int) -> bool`
Handles controller error codes.

**Parameters:**
- `error_code` (int): Error code from controller

**Returns:**
- `bool`: True if error was handled successfully

**Error Codes:**
- `0`: No error
- `1`: Communication error
- `2`: Joint limit exceeded
- `3`: Collision detected
- `4`: Motor overload
- `5`: Sensor failure

**Example:**
```python
if not serial_manager.handle_error(error_code):
    self.logger.error("Failed to handle controller error")
```

##### `clear_errors() -> bool`
Clears all error states.

**Returns:**
- `bool`: True if errors cleared successfully

#### System Management

##### `reboot_controller() -> bool`
Requests a controller reboot.

**Returns:**
- `bool`: True if reboot requested successfully

**Example:**
```python
if serial_manager.reboot_controller():
    self.logger.info("Controller reboot requested")
    time.sleep(2)  # Wait for reboot
```

##### `get_firmware_version() -> str`
Retrieves firmware version information.

**Returns:**
- `str`: Firmware version string

**Example:**
```python
version = serial_manager.get_firmware_version()
self.logger.info(f"Running firmware: {version}")
```

### Thread Safety

The SerialManager uses threading locks to ensure thread-safe operation:

```python
import threading

class SerialManager:
    def __init__(self, node, port='/dev/ttyUSB0', baudrate=115200):
        self._lock = threading.Lock()
        self._serial = None
        # ... rest of initialization
```

All public methods acquire the lock before accessing the serial connection.

### Logging

The SerialManager integrates with ROS2 logging:

```python
# Info logging
self.logger.info("Serial manager initialized")

# Warning logging
self.logger.warning("Connection unstable, retrying...")

# Error logging
self.logger.error("Failed to connect to serial port")

# Debug logging
self.logger.debug(f"Sent command: {command}")
```

### Usage Example

```python
from luxo_behaviors.serial_manager import SerialManager
from std_msgs.msg import String

# Create SerialManager instance
serial_manager = SerialManager(node, port='/dev/ttyUSB0')

# Connect
if serial_manager.connect():
    # Get status
    status = serial_manager.get_status()
    print(f"Controller status: {status}")
    
    # Move to position
    success = serial_manager.control_position(
        x=200, y=100, z=150,
        speed=0.5
    )
    
    # Control gripper
    serial_manager.control_gripper(open_angle=100)
    
    # Disconnect
    serial_manager.disconnect()
else:
    print("Failed to connect")
```

### Error Recovery

The SerialManager implements automatic retry logic:

```python
MAX_RETRIES = 3
RETRY_DELAY = 1.0

def send_command_with_retry(self, command, retries=MAX_RETRIES):
    for i in range(retries):
        try:
            response = self.send_command(command)
            return response
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(RETRY_DELAY)
```

### See Also

- [Shared Utilities Documentation](shared_utils_docs.md)
- [Animation Plugin Base Documentation](animation_plugin_base_docs.md)
- [Animation Plugins Documentation](animation_plugins_docs.md)
- [State Machine Documentation](state_machine_docs.md)
