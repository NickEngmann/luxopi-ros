# Technical Documentation - LuxoPi ROS2

This document provides detailed technical documentation for the LuxoPi ROS2 system, covering internal architecture, algorithms, and implementation details.

## Table of Contents
- [Serial Control Logic](#serial-control-logic)
- [Behavior Coordinator State Machine](#behavior-coordinator-state-machine)
- [Shared Utilities](#shared-utilities)
- [Animation Command Parsing](#animation-command-parsing)
- [Collision Behavior Logic](#collision-behavior-logic)
- [State Machine Architecture](#state-machine-architecture)

---

## Serial Control Logic

### Overview
The serial control module (`serial_manager.py`) handles low-level communication with the RoArm-M3 robotic arm via serial port. It translates high-level animation commands into joint position commands.

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Animation Cmd  │────▶│  Position Calc   │────▶│  Serial Protocol│
│  (rclpy topic)  │     │  (math transforms)│     │  (JSON messages)│
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │  Serial Port     │
                       │  /dev/ttyAMA0    │
                       └──────────────────┘
```

### Key Components

#### 1. Position Calculation (posGet function)

The `posGet()` function converts angular positions (radians) to servo pulse positions (0-4095 range):

```python
def posGet(radInput, direcInput, multiInput):
    """
    Convert radians to servo position.
    
    Args:
        radInput: Target angle in radians
        direcInput: Direction multiplier (1 or -1)
        multiInput: Multiplier for range scaling
    
    Returns:
        Servo position (0-4095)
    """
    if radInput == 0:
        return 2047  # Neutral position
    else:
        # Formula: 2047 + (direction * angle / π * 2048 * multiplier)
        getPos = int(2047 + (direcInput * radInput / 3.1415926 * 2048 * multiInput) + 0.5)
        return getPos
```

**Mathematical Model:**
- Neutral position: 2047 (center of 0-4095 range)
- Full rotation: ±π radians maps to ±2048 positions
- Direction: `direcInput` determines positive/negative rotation
- Multiplier: `multiInput` scales the range (e.g., 1.0 for full range, 2.5 for extended)

#### 2. Serial Protocol

The serial protocol uses JSON messages with the following structure:

```json
{
  "T": 102,           // Message type identifier
  "base": position,   // Base joint position (0-4095)
  "shoulder": position, // Shoulder joint position
  "elbow": position,  // Elbow joint position
  "hand": position,   // Hand joint position (includes +π offset)
  "spd": 0,           // Speed (0 = default)
  "acc": 0            // Acceleration (0 = default)
}
```

**Key Implementation Details:**
- Hand joint always receives +π (3.1415926) offset to align with default position
- Messages are terminated with newline character (`\n`)
- Serial communication uses 115200 baud rate
- Thread-safe with mutex locks for concurrent access

#### 3. Serial Manager Class

```python
class SerialManager:
    """
    Manages serial communication with RoArm-M3.
    
    Features:
    - Automatic serial port detection
    - Thread-safe command sending
    - Connection state monitoring
    - Error handling and recovery
    """
    
    def __init__(self, port='/dev/ttyAMA0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.send_lock = threading.Lock()
        self.is_connected = False
        
    def connect(self):
        """Establish serial connection with auto-retry."""
        # Implementation details...
        pass
        
    def send_command(self, base, shoulder, elbow, hand):
        """Send joint position command."""
        # Build JSON message
        cmd = build_serial_command(base, shoulder, elbow, hand)
        # Thread-safe send with lock
        with self.send_lock:
            self.serial_conn.write(cmd.encode())
```

### Error Handling

The serial manager implements robust error handling:
- **Connection failures**: Automatic retry with exponential backoff
- **Serial port errors**: Graceful degradation with error logging
- **Timeout handling**: 5-second timeout for serial operations
- **Data validation**: All positions clamped to valid range (0-4095)

---

## Behavior Coordinator State Machine

### Overview
The behavior coordinator (`behavior_coordinator.py`) manages high-level behavior selection and state transitions based on inputs from animation commands, vision system, and collision detection.

### State Machine Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    BEHAVIOR COORDINATOR                      │
├─────────────────────────────────────────────────────────────┤
│  States:                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   IDLE   │──▶│ ANIMATING│◀─│  COLLIDE │──│  ESCAPE  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│       ▲              │              │              │        │
│       │              ▼              ▼              │        │
│       └───────────▶  RECOVERY  ◀──────────────────┘        │
└─────────────────────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
   Emotion Input   Animation Cmd   Collision Event
```

### State Definitions

#### 1. IDLE State
- **Purpose**: Waiting for input (animation command, emotion detection, or collision)
- **Entry Action**: Start idle animation loop
- **Exit Action**: Stop idle animation
- **Transition Conditions**:
  - Animation command received → ANIMATING
  - Emotion detected → ANIMATING (emotion-specific animation)
  - Collision detected → COLLIDE

#### 2. ANIMATING State
- **Purpose**: Executing animation sequence
- **Entry Action**: Initialize animation parameters
- **Exit Action**: Complete animation, return to IDLE
- **Transition Conditions**:
  - Animation complete → IDLE
  - Collision detected → COLLIDE
  - New animation command → RESTART_ANIMATION
  - Emotion change → SWITCH_EMOTION

#### 3. COLLIDE State
- **Purpose**: Responding to collision detection
- **Entry Action**: Trigger collision response animation
- **Exit Action**: Move to ESCAPE or RECOVERY
- **Transition Conditions**:
  - Collision response complete → ESCAPE
  - Safe distance achieved → RECOVERY

#### 4. ESCAPE State
- **Purpose**: Move away from collision
- **Entry Action**: Calculate escape trajectory
- **Exit Action**: Return to IDLE or ANIMATING
- **Transition Conditions**:
  - Safe distance achieved → IDLE
  - New animation command → ANIMATING

#### 5. RECOVERY State
- **Purpose**: Reset to safe state after collision
- **Entry Action**: Reset joint positions
- **Exit Action**: Return to IDLE
- **Transition Conditions**:
  - Recovery complete → IDLE

### State Transition Logic

```python
def transition_to(self, new_state):
    """
    Handle state transitions with proper cleanup.
    
    Args:
        new_state: Target LuxoState enum value
    
    Returns:
        bool: True if transition successful
    """
    # 1. Execute exit action for current state
    self._execute_exit_action(self.current_state)
    
    # 2. Validate transition condition
    if not self._validate_transition(self.current_state, new_state):
        return False
    
    # 3. Execute transition action
    self._execute_transition_action(self.current_state, new_state)
    
    # 4. Update state
    self.current_state = new_state
    
    # 5. Execute entry action for new state
    self._execute_entry_action(new_state)
    
    return True
```

### Priority System

The behavior coordinator implements a priority-based state machine:

1. **Collision Detection** (Priority 1): Highest priority - safety first
2. **Animation Commands** (Priority 2): User-initiated animations
3. **Emotion Detection** (Priority 3): Autonomous behavior
4. **Idle Behavior** (Priority 4): Background state

### Thread Safety

The state machine is thread-safe using:
- **Mutex locks**: Protect state transitions
- **Event flags**: Signal state changes to worker threads
- **Queue-based commands**: Decouple command processing from state execution

---

## Shared Utilities

### Overview
The shared utilities module (`shared_utils.py`) provides common functions used across multiple components.

### Mathematical Functions

#### 1. Angle Normalization

```python
def normalize_angle(angle):
    """
    Normalize angle to [-π, π] range.
    
    Args:
        angle: Input angle in radians
    
    Returns:
        Normalized angle in [-π, π]
    """
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle
```

#### 2. Interpolation

```python
def interpolate(start, end, progress):
    """
    Linear interpolation between two values.
    
    Args:
        start: Starting value
        end: Ending value
        progress: Interpolation factor (0.0 to 1.0)
    
    Returns:
        Interpolated value
    """
    return start + (end - start) * progress
```

#### 3. Smoothing

```python
def smooth_value(current, target, smoothing_factor):
    """
    Smoothly transition from current to target value.
    
    Args:
        current: Current value
        target: Target value
        smoothing_factor: 0.0 (slow) to 1.0 (fast)
    
    Returns:
        Smoothed next value
    """
    diff = target - current
    return current + diff * smoothing_factor
```

### Coordinate Transformations

#### 1. Forward Kinematics

```python
def forward_kinematics(joint_angles):
    """
    Calculate end-effector position from joint angles.
    
    Args:
        joint_angles: [base, shoulder, elbow, hand] in radians
    
    Returns:
        (x, y, z) position in Cartesian coordinates
    """
    # Implementation uses Denavit-Hartenberg parameters
    # for RoArm-M3 kinematic chain
    pass
```

#### 2. Inverse Kinematics

```python
def inverse_kinematics(target_position):
    """
    Calculate joint angles for target end-effector position.
    
    Args:
        target_position: (x, y, z) in Cartesian coordinates
    
    Returns:
        [base, shoulder, elbow, hand] in radians
    """
    # Uses numerical optimization for solution
    pass
```

### Sensor Data Processing

#### 1. Collision Distance Calculation

```python
def calculate_collision_distance(sensor_readings):
    """
    Calculate minimum distance to obstacles from multiple sensors.
    
    Args:
        sensor_readings: Dict of sensor_id -> distance (meters)
    
    Returns:
        Minimum distance and closest sensor ID
    """
    min_distance = float('inf')
    closest_sensor = None
    
    for sensor_id, distance in sensor_readings.items():
        if distance < min_distance:
            min_distance = distance
            closest_sensor = sensor_id
    
    return min_distance, closest_sensor
```

#### 2. Emotion Confidence Thresholding

```python
def apply_emotion_threshold(emotion_scores, threshold=0.6):
    """
    Apply confidence threshold to emotion detection results.
    
    Args:
        emotion_scores: Dict of emotion -> confidence (0.0 to 1.0)
        threshold: Minimum confidence to trigger animation
    
    Returns:
        Triggered emotion or None
    """
    triggered = None
    max_confidence = 0.0
    
    for emotion, confidence in emotion_scores.items():
        if confidence > threshold and confidence > max_confidence:
            max_confidence = confidence
            triggered = emotion
    
    return triggered
```

### Utility Classes

#### 1. Timer

```python
class Timer:
    """Simple timer for performance measurement."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        
    def start(self):
        self.start_time = time.time()
        return self
        
    def stop(self):
        self.end_time = time.time()
        return self
        
    def elapsed(self):
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
```

#### 2. Queue

```python
class CommandQueue:
    """Thread-safe command queue for behavior coordination."""
    
    def __init__(self, max_size=10):
        self.queue = queue.Queue(maxsize=max_size)
        self.lock = threading.Lock()
        
    def put(self, command):
        with self.lock:
            self.queue.put(command)
            
    def get(self, timeout=1.0):
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None
```

---

## Animation Command Parsing

### Overview
The animation command module (`animation_command.py`) handles parsing and execution of animation commands received via ROS2 topics.

### Command Format

Animation commands are received as `std_msgs/String` messages with the following format:

```
<animation_name> [<speed_multiplier>]
```

#### Examples
- `"curious"` - Execute curious animation at default speed
- `"excited 1.5"` - Execute excited animation at 1.5x speed
- `"sad 0.5"` - Execute sad animation at 0.5x speed (half speed)

### Parser Implementation

```python
def parse_animation_command(command_string):
    """
    Parse animation command string into structured data.
    
    Args:
        command_string: Raw command from ROS2 topic
    
    Returns:
        Dict with 'animation' and 'speed' keys
    """
    parts = command_string.strip().split()
    
    animation = parts[0].lower()
    speed = 1.0  # Default speed
    
    if len(parts) > 1:
        try:
            speed = float(parts[1])
            speed = max(0.1, min(5.0, speed))  # Clamp to [0.1, 5.0]
        except ValueError:
            speed = 1.0
    
    return {
        'animation': animation,
        'speed': speed,
        'raw': command_string
    }
```

### Animation Registry

```python
ANIMATION_REGISTRY = {
    'excited': {
        'duration': 3.0,
        'joints': ['base', 'shoulder', 'elbow', 'hand'],
        'pattern': 'rapid_bounce'
    },
    'sad': {
        'duration': 4.0,
        'joints': ['shoulder', 'elbow'],
        'pattern': 'slow_droop'
    },
    'curious': {
        'duration': 2.5,
        'joints': ['base', 'shoulder'],
        'pattern': 'tilt_forward'
    },
    'stretch': {
        'duration': 3.5,
        'joints': ['shoulder', 'elbow'],
        'pattern': 'extend_reach'
    },
    'dance': {
        'duration': 5.0,
        'joints': ['base', 'shoulder', 'elbow'],
        'pattern': 'rhythmic_movement'
    }
}
```

### Animation Execution

```python
def execute_animation(animation_config, speed_multiplier):
    """
    Execute animation with speed scaling.
    
    Args:
        animation_config: Dict from ANIMATION_REGISTRY
        speed_multiplier: Speed scaling factor
    
    Returns:
        Generator yielding joint positions over time
    """
    duration = animation_config['duration'] / speed_multiplier
    steps = int(duration * 30)  # 30 Hz update rate
    
    for step in range(steps):
        progress = step / steps
        
        # Calculate joint positions based on animation pattern
        joint_positions = calculate_animation_progress(
            animation_config['pattern'],
            progress,
            animation_config['joints']
        )
        
        yield joint_positions
        
        # Wait for next frame
        time.sleep(1.0 / 30)
```

### Animation Patterns

The system supports multiple animation patterns:

1. **rapid_bounce**: Quick up-down motion with varying amplitude
2. **slow_droop**: Gradual downward movement with smooth easing
3. **tilt_forward**: Forward tilt with return motion
4. **extend_reach**: Arm extension and retraction cycle
5. **rhythmic_movement**: Periodic oscillating motion

Each pattern uses cubic bezier curves for smooth motion:

```python
def cubic_bezier(t, p0, p1, p2, p3):
    """
    Cubic bezier curve for smooth animation.
    
    Args:
        t: Progress (0.0 to 1.0)
        p0, p1, p2, p3: Control points
    
    Returns:
        Interpolated value
    """
    return (1-t)**3 * p0 + 3*(1-t)**2*t * p1 + 3*(1-t)*t**2 * p2 + t**3 * p3
```

---

## Collision Behavior Logic

### Overview
The collision behavior module (`collision_behavior.py`) implements multi-layer collision detection and response strategies.

### Detection Layers

```
┌─────────────────────────────────────────────────────────┐
│              COLLISION DETECTION LAYERS                 │
├─────────────────────────────────────────────────────────┤
│  Layer 1: Proximity Sensor (APDS9960)                   │
│    - Front-facing detection                             │
│    - Range: 0-10cm                                      │
│    - Response: Immediate stop                           │
│                                                         │
│  Layer 2: Distance Sensors (VL53L4CD)                   │
│    - Side-facing detection                              │
│    - Range: 0-2m                                        │
│    - Response: Avoidance maneuver                       │
│                                                         │
│  Layer 3: Depth Camera (OAK-D)                          │
│    - 3D obstacle detection                              │
│    - Range: 0.2-5m                                      │
│    - Response: Path planning                            │
└─────────────────────────────────────────────────────────┘
```

### Collision Detection Algorithm

```python
def detect_collision(sensor_data, safety_distance=0.3):
    """
    Detect collision based on multiple sensor inputs.
    
    Args:
        sensor_data: Dict of sensor readings
        safety_distance: Minimum safe distance (meters)
    
    Returns:
        Collision status and severity
    """
    collision_detected = False
    severity = 0.0
    closest_sensor = None
    
    # Check proximity sensor (highest priority)
    if 'proximity' in sensor_data:
        proximity_dist = sensor_data['proximity']['distance']
        if proximity_dist < 0.1:  # 10cm threshold
            collision_detected = True
            severity = 1.0  # Critical
            closest_sensor = 'proximity'
    
    # Check distance sensors
    for sensor_id, data in sensor_data.items():
        if sensor_id.startswith('distance_'):
            dist = data['distance']
            if dist < safety_distance:
                collision_detected = True
                severity = max(severity, (safety_distance - dist) / safety_distance)
                closest_sensor = sensor_id
    
    # Check depth camera
    if 'depth' in sensor_data:
        depth_dist = sensor_data['depth']['min_distance']
        if depth_dist < safety_distance:
            collision_detected = True
            severity = max(severity, (safety_distance - depth_dist) / safety_distance)
            closest_sensor = 'depth'
    
    return {
        'collision': collision_detected,
        'severity': severity,
        'closest_sensor': closest_sensor,
        'safety_distance': safety_distance
    }
```

### Collision Response Strategies

#### 1. Immediate Stop
- **Trigger**: Proximity sensor collision (Layer 1)
- **Action**: Halt all motion immediately
- **Recovery**: Wait for obstacle clearance

#### 2. Avoidance Maneuver
- **Trigger**: Distance sensor collision (Layer 2)
- **Action**: Move away from obstacle in opposite direction
- **Parameters**:
  - Distance: 0.5 meters
  - Duration: 2 seconds
  - Speed: 50% of normal

#### 3. Path Rerouting
- **Trigger**: Depth camera detection (Layer 3)
- **Action**: Calculate alternative path around obstacle
- **Algorithm**: A* path planning with obstacle avoidance

### Escape Behavior

```python
def execute_escape(collision_data):
    """
    Execute escape behavior based on collision data.
    
    Args:
        collision_data: Dict from detect_collision()
    
    Returns:
        Escape trajectory commands
    """
    sensor = collision_data['closest_sensor']
    severity = collision_data['severity']
    
    # Determine escape direction based on sensor location
    if sensor == 'proximity_front':
        # Move backward
        direction = 'backward'
        distance = 0.3
    elif sensor.startswith('distance_left'):
        # Move right
        direction = 'right'
        distance = 0.5
    elif sensor.startswith('distance_right'):
        # Move left
        direction = 'left'
        distance = 0.5
    else:
        # Default: move away from obstacle
        direction = 'away'
        distance = 0.5 * (1 + severity)
    
    # Calculate escape trajectory
    trajectory = calculate_escape_trajectory(direction, distance)
    
    return trajectory
```

### Safety Monitoring

```python
class SafetyMonitor:
    """
    Continuous safety monitoring during operation.
    """
    
    def __init__(self, check_interval=0.1):
        self.check_interval = check_interval
        self.last_collision_time = None
        self.collision_count = 0
        self.safety_threshold = 5  # Max collisions before shutdown
        
    def record_collision(self):
        """Record collision event."""
        self.collision_count += 1
        self.last_collision_time = time.time()
        
        if self.collision_count >= self.safety_threshold:
            self.trigger_safety_shutdown()
            
    def trigger_safety_shutdown(self):
        """Emergency shutdown after repeated collisions."""
        # Halt all motion
        # Log incident
        # Request operator intervention
        pass
        
    def reset(self):
        """Reset safety counters."""
        self.collision_count = 0
        self.last_collision_time = None
```

---

## State Machine Architecture

### Overview
The state machine module (`state_machine.py`) provides a generic state machine implementation used by the behavior coordinator.

### State Machine Design

```python
class StateMachine:
    """
    Generic state machine with transitions, conditions, and actions.
    """
    
    def __init__(self, initial_state):
        self.current_state = initial_state
        self.transitions = []  # List of StateTransition objects
        self.state_history = []
        
    def add_transition(self, from_state, to_state, condition, action=None):
        """Add a state transition definition."""
        self.transitions.append(StateTransition(
            from_state=from_state,
            to_state=to_state,
            condition=condition,
            action=action
        ))
        
    def transition(self, to_state):
        """Attempt state transition."""
        # Find matching transition
        for trans in self.transitions:
            if (trans.from_state == self.current_state and 
                trans.to_state == to_state):
                # Check condition
                if trans.condition():
                    # Execute transition action
                    if trans.action:
                        trans.action()
                    # Perform state change
                    self._perform_transition(trans.from_state, to_state)
                    return True
        return False
```

### State Transition Definition

```python
class StateTransition:
    """Defines a single state transition."""
    
    def __init__(self, from_state, to_state, condition, action=None):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition  # Function returning bool
        self.action = action  # Function to execute during transition
```

### State History Tracking

```python
def _perform_transition(self, from_state, to_state):
    """Execute state transition with history tracking."""
    # Record history
    self.state_history.append({
        'from': from_state,
        'to': to_state,
        'timestamp': time.time()
    })
    
    # Limit history size
    if len(self.state_history) > 100:
        self.state_history.pop(0)
    
    # Update current state
    self.current_state = to_state
```

---

## Implementation Notes

### Thread Safety

All modules implement thread-safe operations:
- **Mutex locks**: Protect shared state
- **Queue-based communication**: Decouple components
- **Atomic operations**: Prevent race conditions

### Error Handling

Robust error handling across all modules:
- **Graceful degradation**: Continue operation with reduced functionality
- **Logging**: Comprehensive error logging for debugging
- **Recovery**: Automatic recovery from transient errors

### Performance Optimization

Performance considerations:
- **30 Hz control loop**: Balanced responsiveness and CPU usage
- **Efficient interpolation**: Minimize computational overhead
- **Caching**: Cache frequently used calculations

---

## References

- [RoArm-M3 Documentation](https://github.com/NickEngmann/roarm)
- [ROS2 Documentation](https://docs.ros.org/)
- [DepthAI Documentation](https://docs.luxonis.com/)
- [APDS9960 Sensor Datasheet](https://cdn-learn.adafruit.com/downloads/pdf/adafruit-apds9960-rgb-light-sensor-proximity-interrupt.pdf)
- [VL53L4CD Sensor Datasheet](https://cdn-learn.adafruit.com/downloads/pdf/adafruit-vl53l4cd-time-of-flight-breakout.pdf)

---

*This documentation was generated as part of the LuxoPi ROS2 project. For questions or contributions, please visit the [GitHub repository](https://github.com/NickEngmann/luxopi-ros).*
