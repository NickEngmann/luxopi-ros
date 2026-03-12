# LuxoPi Shared Utilities Documentation

## Overview

The `shared_utils.py` module contains common utility functions used across collision detection, vision processing, idle behaviors, and other nodes in the LuxoPi system.

## Key Functions

### Collision Detection Utilities

#### `check_collision_safe()`
Determines if a movement is safe based on proximity sensor data.

**Parameters:**
- `proximity_data` (dict): Dictionary containing proximity sensor readings
- `movement_direction` (str): Direction of intended movement
- `collision_threshold` (float): Threshold for collision detection

**Returns:**
- `tuple`: (is_safe: bool, message: str)

**Example:**
```python
is_safe, msg = check_collision_safe(proximity_data, 'forward', 10.0)
if is_safe:
    # Proceed with movement
    pass
```

#### `get_collision_magnitude()`
Calculates the severity magnitude of a detected collision.

**Parameters:**
- `consecutive_count` (int): Number of consecutive collision detections
- `emergency` (bool): Whether this is an emergency situation
- `severity` (str): Severity level ('low', 'medium', 'high', 'danger')

**Returns:**
- `float`: Magnitude value for collision response

**Magnitude Scale:**
- Consecutive count > 5: magnitude = 2.0
- Consecutive count > 3: magnitude = 2.5
- Emergency or 'danger' severity: magnitude = 1.5
- Default: magnitude = 1.0

### Vision Processing Utilities

#### `process_depth_data()`
Processes raw depth camera data for object detection.

**Parameters:**
- `depth_frame` (numpy.ndarray): Raw depth frame from camera
- `object_threshold` (float): Minimum depth for object detection
- `filter_noise` (bool): Apply noise filtering

**Returns:**
- `dict`: Processed depth data with object positions

#### `calculate_object_distance()`
Calculates distance to detected objects from depth data.

**Parameters:**
- `depth_data` (dict): Processed depth information
- `object_id` (int): ID of the object to measure

**Returns:**
- `float`: Distance in millimeters

### State Management Utilities

#### `transition_state()`
Handles state transitions with validation.

**Parameters:**
- `current_state` (str): Current system state
- `target_state` (str): Desired state to transition to
- `transition_conditions` (dict): Conditions that must be met

**Returns:**
- `bool`: Whether transition was successful

#### `validate_state_sequence()`
Validates that state transitions follow allowed sequences.

**Parameters:**
- `state_sequence` (list): List of states in order
- `allowed_transitions` (dict): Dictionary of valid transitions

**Returns:**
- `tuple`: (is_valid: bool, errors: list)

### Sensor Data Utilities

#### `fuse_sensor_data()`
Combines data from multiple sensors for improved accuracy.

**Parameters:**
- `sensor_readings` (dict): Dictionary of sensor data by type
- `weights` (dict): Weights for each sensor type
- `fusion_method` (str): Method to use ('average', 'weighted', 'kalman')

**Returns:**
- `dict`: Fused sensor data

#### `filter_sensor_noise()`
Applies filtering to reduce sensor noise.

**Parameters:**
- `raw_data` (list): Raw sensor readings
- `filter_type` (str): Type of filter ('moving_average', 'low_pass', 'kalman')
- `window_size` (int): Size of filter window

**Returns:**
- `list`: Filtered sensor data

### Error Handling Utilities

#### `handle_sensor_error()`
Manages sensor errors with appropriate recovery actions.

**Parameters:**
- `error_type` (str): Type of sensor error
- `sensor_id` (str): ID of the affected sensor
- `retry_count` (int): Number of retry attempts

**Returns:**
- `dict`: Error handling result with status and recovery info

#### `log_system_error()`
Logs system errors with context information.

**Parameters:**
- `error_message` (str): Error description
- `error_code` (int): Numeric error code
- `context` (dict): Additional context information
- `severity` (str): Error severity ('info', 'warning', 'error', 'critical')

**Returns:**
- `bool`: Whether logging was successful

## Usage Guidelines

1. **Collision Detection**: Always check collision safety before executing movements
2. **Sensor Fusion**: Use weighted fusion for critical operations
3. **Error Handling**: Implement retry logic with exponential backoff
4. **State Transitions**: Validate all state sequences before execution
5. **Logging**: Use appropriate severity levels for different error types

## Dependencies

- `numpy`: For array operations and depth data processing
- `math`: For mathematical calculations
- ROS2 std_msgs: For message types
- ROS2 sensor_msgs: For sensor data messages

## See Also

- [Animation Plugin Base Documentation](animation_plugin_base_docs.md)
- [Animation Plugins Documentation](animation_plugins_docs.md)
- [Serial Manager Documentation](serial_manager_docs.md)
- [State Machine Documentation](state_machine_docs.md)
