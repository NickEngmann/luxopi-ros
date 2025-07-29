# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Architecture

### Hardware Components
- **Robot**: RoArm-M3 6-DOF arm with RoArm-M3-Tool end effector
- **Computer**: Raspberry Pi 5 (8GB recommended)
- **Camera**: OAK-D depth camera for vision and collision detection
- **Microphone**: ReSpeaker 4-mic array for voice direction
- **Sensors**: I2C sensors (APDS9960 proximity, VL53L4CD distance)
- **Display**: Small framebuffer display showing system status
- **LEDs**: NeoPixel for visual feedback

### Software Stack
- **OS**: Ubuntu 24.04
- **ROS2**: Jazzy distribution
- **Communication**: Serial JSON protocol at 115200 baud
- **Vision**: DepthAI for face/emotion detection
- **Audio**: DFRobot DF2301Q voice recognition + ReSpeaker 2-mic array for direction
- **Display**: Framebuffer display with system metrics and state visualization

## Core Architecture Principles

1. **Centralized State Management**: `state_manager.py` coordinates all behaviors through a priority-based state machine
2. **Modular Behaviors**: Each behavior (collision, voice, emotion, etc.) is a separate node communicating via ROS2
3. **Mixin-Based Architecture**: Behaviors are implemented as mixins combined in `behavior_coordinator.py`
4. **Hardware Abstraction**: `hardware_interface.py` provides thread-safe robot control with DEMA support
5. **Safety First**: Multi-layer collision detection with graceful degradation
6. **Animation System**: Disney-principles based with frame interpolation and priority handling
7. **Shared Utilities**: Common functionality in `shared_utils.py` for consistency

## Build and Run Commands

```bash
# Build the workspace
colcon build
source install/setup.bash

# Run in simulation mode
ros2 launch luxo_behaviors luxo_system.launch.py

# Run with hardware
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true


# Use the convenience script (recommended for hardware)
./start_luxopi.sh

# Stop the system
./stop_luxopi.sh
```

## Launch Configuration Options

The main launch file `luxo_system.launch.py` supports these parameters:

### Core Parameters
- `use_hardware` (bool, default: false): Connect to physical robot
- `test_mode` (string, default: 'animation'): Options: 'position', 'animation'
- `verbose` (bool, default: false): Enable debug output

### Feature Toggles
- `use_camera` (bool): Enable OAK-D camera (auto-enabled with hardware)
- `enable_emotion_detection` (bool): React to emotions (auto-enabled with camera)
- `enable_person_tracking` (bool, default: false): Track specific people
- `sense_collision` (bool): Enable collision sensors (auto-enabled with hardware)
- `enable_dynamic_adaptation` (bool): DEMA mode (auto-enabled with hardware)
- `enable_voice` (bool, default: true): Voice command detection
- `enable_petting` (bool, default: true): Touch sensor responses
- `enable_idle_behaviors` (bool, default: true): Autonomous idle animations

### Hardware Configuration
- `serial_port` (string, default: '/dev/ttyAMA0'): Robot serial port
- `i2c_bus` (int, default: 1): I2C bus number
- `camera_device` (string, default: ''): Camera device ID

### Behavior Tuning
- `voice_follow_speed` (float, default: 1.0): Voice tracking speed
- `collision_threshold_warning` (int, default: 300): Warning distance (mm)
- `collision_threshold_danger` (int, default: 150): Danger distance (mm)
- `idle_interval_min` (float, default: 15.0): Min idle animation interval
- `idle_interval_max` (float, default: 45.0): Max idle animation interval

## Animation System

### Animation Guidelines (from animation_guidelines.md)

1. **Disney Animation Principles**:
   - **Anticipation**: 3-5 frames before main action
   - **Follow-through**: 3-5 frames after main action
   - **Ease In/Out**: Never use linear movements
   - **Arcs**: Natural curved motions, not straight lines
   - **Timing**: 20 FPS standard, adjust with timing attribute

2. **Frame Structure**:
   ```python
   frames = [
       {"servos": {"j1": 0, "j2": 45, ...}, "timing": 1.0},  # timing multiplier
       # ... more frames
   ]
   ```

3. **Joint Constraints**:
   - j1 (Base): [-90, 90]
   - j2 (Shoulder): [0, 180]
   - j3 (Elbow): [0, 180]
   - j4 (Wrist): [0, 180]
   - j5 (Hand): [-90, 90]
   - j6 (Tool): [60, 120] for LED

4. **Animation Types**:
   - **Idle**: Long, loopable, energy-conserving
   - **Reaction**: Quick, exaggerated, clear emotion
   - **Transition**: Smooth movement between states
   - **Interactive**: Responsive to stimuli

### Available Animations (47 total)

#### Idle Animations (16)
`gentle_sway`, `curious_exploration`, `breathing`, `attentive_listening`, `playful_bob`, `scanning_watch`, `settling_adjust`, `dreamy_drift`, `neck_stretch`, `sleep`, `yawning_stretch`, `shoulder_shimmy`, `look_around_casual`, `contented_sigh`, `head_bobbing`, `tail_wag`, `pondering`

#### Action Animations (5)
`curious`, `think`, `stretch`, `dance`, `idle`

#### Emotion Animations (4)
`excited`, `sad`, `playful`, `startled`

#### Response Animations (4)
`nod`, `shake`, `close`, `stop`

#### Petting Animations (3)
`folded_wiggle`, `bouncy_wiggle`, `sleepy_melt`

## Voice Command System (DFRobot DF2301Q)

The system uses a DFRobot DF2301Q voice recognition module connected via I2C (bus 3).

### Available Commands (29 total)

#### Wake Word Commands
- Command ID 1: Custom wake word (user-programmed)
- Command ID 2: "Hello robot"

These wake words activate USER_CONTROL mode for 10 seconds (or until the next command), displaying a bouncing white/blue direction indicator on the NeoPixels that moves back and forth by 8 pixels.

#### Basic Light Control Commands
**Turn OFF/ON light:**
- Command ID 103: "Turn on the light"
- Command ID 104: "Turn off the light"

#### Brightness Control Commands
- Command ID 105: "Brighten the light" - Increases brightness by 20%
- Command ID 106: "Dim the light" - Decreases brightness by 20%
- Command ID 107: "Adjust brightness to maximum" - Sets brightness to 100%
- Command ID 108: "Adjust brightness to minimum" - Sets brightness to 10%

#### Color Temperature Commands
- Command ID 109: "Increase color temperature" - Makes light warmer (more red/yellow)
- Command ID 110: "Decrease color temperature" - Makes light cooler (more blue)
- Command ID 111: "Adjust color temperature to maximum" - Sets warmest temperature
- Command ID 112: "Adjust color temperature to minimum" - Sets coolest temperature

#### Color Setting Commands
- Command ID 116: "Set to red"
- Command ID 117: "Set to orange"
- Command ID 118: "Set to yellow"
- Command ID 119: "Set to green"
- Command ID 120: "Set to cyan"
- Command ID 121: "Set to blue"
- Command ID 122: "Set to purple"
- Command ID 123: "Set to white" - Returns to default white with current temperature

#### Wake Up Commands
- Command ID 80: "Start oscillating"
- Command ID 113: "Daylight mode"
- Command ID 115: "Color mode"

#### Go to Sleep Commands
- Command ID 81: "Stop oscillating"
- Command ID 82: "Reset"
- Command ID 93: "Stop playing"
- Command ID 114: "Moonlight mode"

### Command Execution Flow
1. Voice command detected by DFRobot sensor
2. Command ID mapped to action (wake_word, light control, brightness, color temp, color, wake_up, go_to_sleep)
3. State machine transitions to USER_CONTROL state
4. Command executed with appropriate actions:
   - Wake words: Enter listening mode for 10 seconds with bouncing direction indicator visual
   - Basic light commands: Turn NeoPixel LEDs on/off (exits USER_CONTROL immediately if wake word initiated)
   - Brightness commands: Adjust global LED brightness (0.1 to 1.0 range)
   - Color temperature: Adjust white color from cool blue-white to warm yellow-white
   - Color commands: Set specific colors, overriding state-based colors (except ERROR state)
   - Wake up: Disable DEMA mode, enable torque, turn on lights
   - Sleep: Play sleep animation, enable DEMA mode, turn off lights
5. Confirmation sound played
6. Return to IDLE state after completion (timeout or next command for wake words)

### Light Control Details
- **Brightness**: Ranges from 0.1 (10%) to 1.0 (100%), adjustable in 20% steps
- **Color Temperature**: 0.0 = coolest (blue-white), 1.0 = warmest (yellow-white)
- **Color Modes**: When a specific color is set, it overrides state-based colors
- **Smart Transitions**: When adjusting temperature while in color mode, system returns to white first
- **State Priority**: ERROR state always displays red regardless of color settings

### Configuration
- Default volume: 7/20
- Wake time: 20 seconds
- Command check interval: 100ms
- Cooldown between commands: 2 seconds

## State Machine

States and their responsibilities:
- `IDLE`: Default state, can trigger idle animations
- `ANIMATING`: Playing animations, blocks other actions
- `COLLISION_AVOIDING`: Active obstacle avoidance
- `RETURNING_HOME`: Moving to safe position
- `USER_CONTROL`: Direct user commands
- `PETTING`: Responding to touch sensors
- `VOICE_FOLLOWING`: Tracking voice direction
- `ESCAPE_MODE`: Emergency collision response
- `EMOTION_REACTING`: Responding to detected emotions
- `ERROR`: Error recovery state

## Key Configuration Files

1. **ROBOT_ARM_API.md**: JSON protocol for robot control
   - Movement commands: `{"T":1,"x":100,"y":100,"z":100}`
   - Joint control: `{"T":11,"j1":0,"j2":90,...}`
   - Speed control: `{"T":11,"cmd":3000}` (1-3000)
   - DEMA mode: `{"T":30,"cmd":1}` (0=off, 1=on)

2. **animation_guidelines.md**: Disney principles and best practices

3. **architecture_diagram.svg**: Visual system architecture

## Development Workflows

### Testing Animations
```bash
# Test specific animation
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: excited"

# Test with speed modifier
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: dance 1.5"

# Trigger idle animation
ros2 service call /trigger_idle_animation std_srvs/srv/Trigger
```

### Monitoring System
```bash
# View state
ros2 topic echo /luxo/current_state

# Monitor joint positions
ros2 topic echo /joint_states

# Check collision status
ros2 topic echo /collision/front/status
ros2 topic echo /collision/left/status
ros2 topic echo /collision/right/status

# View detected emotions
ros2 topic echo /camera/emotion

# Monitor voice direction
ros2 topic echo /voice/direction

# Check sensor health
ros2 topic echo /i2c/sensor_health
```

### Service Management
```bash
# Enable autostart service
sudo cp luxopi.service /etc/systemd/system/
sudo systemctl enable luxopi.service
sudo systemctl start luxopi.service

# View service logs
sudo journalctl -u luxopi.service -f

# Application logs (when using start_luxopi.sh)
tail -f ~/luxopi-ros/logs/luxopi.log
```

## Important Code Patterns

### State Transitions
```python
# Request state change
ros2 service call /luxo/request_state_transition \
    luxo_interfaces/srv/RequestStateTransition \
    "{target_state: 'IDLE', wait_for_completion: true}"
```

### Movement Publishing
```python
# Always publish movement source for DEMA
self.movement_source_pub.publish(String(data="voice_following"))
```

### Animation Action Client
```python
# Send animation goal
goal = PlayAnimation.Goal()
goal.animation_name = "excited"
goal.speed = 1.0
future = animation_client.send_goal_async(goal)
```

### Safe Joint Commands
```python
# Use hardware interface methods
self.hardware.safe_move_joints({"j1": 45, "j2": 90})
self.hardware.move_to_position(x=150, y=0, z=150)
```

## Watchdog System

The system includes a comprehensive watchdog node to detect and recover from the "silent failure mode" where nodes stop publishing after prolonged usage (4+ hours).

### Topics Monitored
- **Core Topics**: 
  - `/luxo/current_state` (30s timeout)
  - `/joint_states` (25s timeout)
- **Animation System**:
  - `/roarm/animation_command` (60s timeout)
  - `/animation_action/_action/status`
- **Serial Communication**:
  - `/roarm/position` (5s timeout for feedback)
- **Movement Coordination**:
  - `/luxo/movement_source` (30s timeout)

### Detection Mechanisms
1. **Timeout Detection**: Topics not publishing within expected intervals
2. **Content Validation**: 
   - Stuck state detection (5 minutes in same non-IDLE state)
   - Stuck joints detection (2 minutes without movement in active states)
3. **Cross-Topic Correlation**:
   - Silent failure: System metrics update but no animation commands
   - Correlation failures: Joint updates without serial feedback

### Recovery Mechanisms
1. **Self-recovery in nodes**: 
   - State manager: Health checks every 30s with auto-recovery
   - Hardware interface: Joint publish health monitoring
2. **Watchdog recovery strategies**:
   - State timeout → Request IDLE transition
   - Joint timeout → Request RETURNING_HOME
   - Animation timeout → Trigger idle animation
   - Serial timeout → Force RETURNING_HOME
   - Stuck system → ERROR → IDLE cycle
   - Silent failure → ERROR → wait 2s → IDLE
3. **Node restart**: Optional (disabled by default for safety)

### Status Information
The watchdog publishes detailed status to `/watchdog/status`:
- Topic ages (State, Joint, Anim, Serial)
- Current state and duration
- Joint stillness duration
- Active failures (STATE, JOINT, ANIM, SERIAL, STUCK_STATE, STUCK_JOINT, SILENT_FAIL)
- Recovery attempt counts
- Watchdog self-health

### Launch Parameters
```bash
# Monitor watchdog status
./monitor_watchdog.sh

# Disable watchdog
ros2 launch luxo_behaviors luxo_system.launch.py enable_watchdog:=false

# Adjust timeouts (defaults shown)
ros2 launch luxo_behaviors luxo_system.launch.py \
    watchdog_state_timeout:=30.0 \
    watchdog_joint_timeout:=25.0 \
    watchdog_animation_timeout:=60.0 \
    watchdog_serial_timeout:=5.0
```

## Common Issues and Solutions

### Silent Failure Mode (4+ hours)
- **Symptoms**: No idle animations, only system metrics publishing
- **Solution**: Watchdog automatically detects and attempts recovery
- **Manual recovery**: `ros2 service call /luxo/request_state_transition luxo_interfaces/srv/RequestStateTransition "{target_state: 'IDLE'}"`

### Serial Communication
- Permission error: Add user to dialout group: `sudo usermod -a -G dialout $USER`
- Port busy: Check with `lsof /dev/ttyAMA0`, kill process if needed
- Wrong baud rate: Ensure 115200 in launch file

### I2C Sensors
- Not detected: Run `i2cdetect -y 1`
- Wrong addresses: Check APDS9960 (0x39), VL53L4CD (0x29)
- Intermittent readings: Check wiring and pull-up resistors

### Animation Problems
- Jerky movements: Increase timing values between frames
- Not playing: Check state machine isn't blocking
- Wrong position: Verify joint constraints in animation

## Code Organization

### Package Structure
```
luxo_behaviors/
├── animations/          # All animation classes
│   ├── idle/           # 16 idle animations
│   ├── actions/        # 5 action animations
│   ├── emotions/       # 4 emotion animations
│   ├── responses/      # 4 response animations
│   └── petting/        # 3 petting animations
├── launch/             # Launch configurations
├── config/             # Parameter files
└── luxo_behaviors/     # Main Python modules
```

### Key Modules

#### Core System
- `state_manager.py`: Central coordinator, state machine
- `hardware_interface.py`: Robot control, safety limits
- `animation_command.py`: Animation engine, interpolation
- `behavior_coordinator.py`: Combines all behavior mixins

#### Behavior Modules (Mixins)
- `command_behavior.py`: Voice commands, behavior mapping
- `petting_behavior.py`: Touch sensor responses (3 animations)
- `collision_behavior.py`: Three-layer collision detection and avoidance
- `voice_behavior.py`: Voice direction tracking with face visibility optimization
- `idle_behavior.py`: Autonomous idle animations and head variations

#### Hardware Communication
- `serial_manager.py`: Thread-safe serial communication with heartbeat
- `i2c_device_manager.py`: I2C sensor management (APDS9960, VL53L4CD)
- `DFRobot_DF2301Q.py`: Voice recognition hardware driver

#### Vision & Audio
- `camera_interaction.py`: Vision, emotion detection
- `voice_direction_node.py`: Voice tracking with motor awareness
- `mic_array.py`: ReSpeaker microphone array interface
- `gcc_phat.py`: Audio localization algorithm
- `pixel_ring.py`: LED ring control for ReSpeaker

#### Display & Monitoring
- `framebuffer_display.py`: System status display with state visualization
- `system_monitor.py`: CPU, RAM, temperature monitoring

#### Utilities
- `shared_utils.py`: Central utility classes:
  - PositionUtils: Joint manipulation
  - StateUtils: State transitions
  - MovementSourcePublisher: DEMA coordination
  - CollisionStatusTracker: Multi-directional tracking
  - TimeUtils: ROS time operations
  - SafetyLimits: Joint boundaries
  - AnimationTracker: Animation state
  - CollisionMath: Collision calculations
  - MovementValidator: Safety validation

## Behavior System Details

### Voice Direction System (`voice_direction_node.py`)
- **Motor awareness**: Compensates for motor noise during movement
- **Parallax correction**: Adjusts for microphone array position (10cm behind, 15cm up)
- **Direction mapping**: Front=-30°, Right=-120°, Back=150°, Left=60°
- **Smooth tracking**: Configurable speed and deadzone
- **Face visibility optimization**: Varies neck position for better detection

### Petting Behavior (`petting_behavior.py`)
- **Touch Detection**: Via `/collision/petting_events` topic
- **Animations**: folded_wiggle, bouncy_wiggle, sleepy_melt
- **Cooldown**: 8 seconds between animations
- **Timeout**: 5 seconds to detect petting cessation
- **State Integration**: Only from IDLE, ANIMATING, or VOICE_FOLLOWING

### Collision Behavior (`collision_behavior.py`)
- **Three-Layer Response**:
  1. Path adjustment (warning: <15cm)
  2. Avoidance maneuvers (danger: <10cm)
  3. Escape mode (persistent collisions)
- **Escape Threshold**: 10 consecutive collisions
- **Base Rotation Awareness**: Handles -90° to 90° limits with wraparound
- **Safe Zone Recording**: Avoids known obstacles

### Idle Behavior (`idle_behavior.py`)
- **Animation Timing**: Random 10-60 second intervals
- **Head Variations**: Subtle movements every 1-5 seconds
- **Extended Idle**: Returns home after prolonged inactivity
- **16 Idle Animations**: From gentle_sway to pondering

### Behavior Coordinator (`behavior_coordinator.py`)
- **Priority System**: Collision > Petting > Voice > Idle
- **Target Arbitration**: Resolves conflicts between behaviors
- **Two-Stage Home**: Safe return sequence
- **Animation Validation**: Ensures keyframe safety

## Additional Infrastructure

### Display System (`framebuffer_display.py`)
- Direct framebuffer access for small screen
- System metrics: CPU, RAM, temperature
- State visualization with friendly descriptions
- Emotion and face detection overlays
- Touch sensor visualization
- Collision sensor status
- Joint position display
- Special effects: Pink filter for petting, red for anger

### Audio Processing
- **ReSpeaker 4-mic array**: Direction of Arrival calculation
- **GCC-PHAT algorithm**: Time delay estimation for localization
- **LED ring animations**: Listen, speak, think, spin patterns

### Scripts and Tools
- `start_luxopi.sh`: Smart launch with health monitoring
- `stop_luxopi.sh`: Graceful shutdown with close animation
- `INSTALL.sh`: System setup and dependencies
- `diagnostic_checker.py`: System health monitoring

### Message Types
- `StateInfo.msg`: State machine information
- `ConfigureI2CSensor.srv`: Sensor configuration
- `RequestStateTransition.srv`: State transitions
- `PlayAnimation.action`: Animation control with progress

## Testing and Development

### Running Tests
```bash
# Lint tests
colcon test --packages-select luxo_behaviors
colcon test-result --all

# Hardware test mode
ros2 launch luxo_behaviors luxo_system.launch.py test_mode:=position

# Animation test mode
ros2 launch luxo_behaviors luxo_system.launch.py test_mode:=animation
```

### Development Tools
```bash
# View ROS graph
ros2 run rqt_graph rqt_graph

# Parameter tuning
ros2 run rqt_reconfigure rqt_reconfigure

# Message introspection
ros2 interface show luxo_interfaces/msg/CollisionStatus

# Service testing
ros2 service list
ros2 service type /luxo/request_state_transition
```

## Safety Considerations

1. **Hardware Limits**: Enforced at multiple levels
2. **Collision Detection**: Three-layer system with escalating responses
3. **DEMA Mode**: Motor compliance for safe interaction
4. **Emergency Stop**: Always available via stop animation
5. **Thermal Protection**: CPU temperature monitoring
6. **Current Limiting**: Prevents motor damage

## Performance Optimization

1. **Frame Skipping**: Display updates at 10 FPS
2. **Sensor Throttling**: I2C reads limited to prevent bus saturation
3. **Animation Caching**: Preloaded animations for instant playback
4. **Selective Processing**: Features can be disabled to reduce load
5. **Efficient State Checks**: Minimal overhead in state machine

## Best Practices

1. **Always test in simulation first** before hardware
2. **Use state transitions** rather than direct control when possible
3. **Monitor logs** during development (verbose mode)
4. **Follow animation guidelines** for natural movement
5. **Check sensor health** before relying on readings
6. **Respect state machine** - don't bypass safety features
7. **Test edge cases** - especially collision scenarios
8. **Document new animations** with purpose and inspiration

## Debugging Tips

```bash
# Enable all debug output
ros2 launch luxo_behaviors luxo_system.launch.py verbose:=true

# Check specific node output
ros2 run luxo_behaviors state_manager --ros-args -p verbose:=true

# Monitor all topics
ros2 topic list | xargs -I {} ros2 topic echo {} --once

# Debug serial communication
screen /dev/ttyAMA0 115200

# Test I2C devices
i2cdetect -y 1

# Monitor system metrics
ros2 topic echo /system/cpu_usage
ros2 topic echo /system/ram_usage
ros2 topic echo /system/temperature

# Check voice command detection
ros2 topic echo /voice_command/detected

# Monitor behavior coordination
ros2 topic echo /luxo/target_override
ros2 topic echo /luxo/movement_source
```

## Error Recovery

1. **Serial Connection Lost**: Automatic reconnection with heartbeat
2. **I2C Sensor Failure**: Health monitoring and re-initialization
3. **State Machine Error**: ERROR state with recovery mechanisms
4. **Collision Persistence**: Escape mode with multiple strategies
5. **Animation Failures**: Preemption and safety validation

## Resource Locations

- **Voice Commands Documentation**: `src/luxo_behaviors/resource/voice_command.md`
- **Animation Guidelines**: `animation_guidelines.md`
- **Robot API**: `ROBOT_ARM_API.md`
- **Architecture Diagram**: `architecture_diagram.svg`
- **Service Files**: `luxopi.service`, `luxopi-ros.service`

System uses ROS2 Jazzy on Ubuntu 24.04. Python packages require `--break-system-packages` flag.

## Hardware Specifications and Pinouts

### RoArm-M3 Robot Arm
- **Degrees of Freedom**: 6 (j1-j6)
- **Communication**: Serial UART at 115200 baud
- **Power**: 12V DC, 3A peak
- **Reach**: ~300mm radius
- **Payload**: 500g maximum
- **Joint Types**:
  - j1 (Base): Rotational, ±90°
  - j2 (Shoulder): Rotational, 0-180°
  - j3 (Elbow): Rotational, 0-180°
  - j4 (Wrist): Rotational, 0-180°
  - j5 (Hand): Rotational, ±90°
  - j6 (Tool/LED): Control only, 60-120 range

### Raspberry Pi 5 Connections
```
GPIO Pinout (40-pin header):
- Pin 2,4: 5V Power (for sensors)
- Pin 6,9,14,20,25,30,34,39: Ground
- Pin 8 (GPIO14): TX to Robot (via level shifter)
- Pin 10 (GPIO15): RX from Robot (via level shifter)
- Pin 3 (GPIO2): I2C1 SDA
- Pin 5 (GPIO3): I2C1 SCL
- Pin 27 (GPIO0): I2C3 SDA (DFRobot voice module)
- Pin 28 (GPIO1): I2C3 SCL (DFRobot voice module)
- Pin 12 (GPIO18): NeoPixel data (via level shifter)
```

### I2C Device Addresses
- **0x39**: APDS9960 (proximity/gesture sensor)
- **0x29**: VL53L4CD (left distance sensor)
- **0x2A**: VL53L4CD (right distance sensor) - reprogrammed
- **0x64**: DFRobot DF2301Q (voice recognition) on I2C bus 3

### NeoPixel LED Ring
- **Model**: WS2812B RGB LED ring
- **Count**: 76 LEDs
- **Power**: 5V, up to 4.5A at full white
- **Data**: Single-wire protocol at 800kHz
- **Connection**: GPIO18 through 3.3V→5V level shifter

### OAK-D Depth Camera
- **Connection**: USB 3.0 Type-C
- **Power**: USB powered (900mA typical)
- **Resolution**: 1920x1080 RGB, 640x480 depth
- **FPS**: 30 FPS RGB, 30 FPS depth
- **FOV**: 69° HFOV, 55° VFOV
- **Depth Range**: 0.2m - 10m

### ReSpeaker Mic Array
- **Model**: 2-mic or 4-mic array
- **Connection**: USB 2.0
- **Sampling**: 48kHz, 16-bit
- **Features**: Hardware AEC, DOA, VAD
- **LED Ring**: 12 APA102 RGB LEDs (SPI control)

### Touch Sensors (APDS9960)
- **Count**: 4 sensors (front, back, left, right)
- **Range**: 0-255 proximity units
- **Touch Threshold**: >200 units
- **Gesture Support**: Up, down, left, right swipes

### Distance Sensors (VL53L4CD)
- **Count**: 2 sensors (left, right)
- **Range**: 1mm - 1300mm
- **Accuracy**: ±7mm
- **FOV**: 18° cone
- **Update Rate**: 50Hz maximum

### Framebuffer Display
- **Device**: /dev/fb0
- **Resolution**: Varies (typically 320x240 or 480x320)
- **Color Depth**: 16-bit RGB565
- **Update Rate**: 10 FPS (throttled)

## Complete JSON Protocol Reference

### Movement Commands

#### Cartesian Position Control
```json
// Move to XYZ position
{"T":1,"x":150,"y":0,"z":150,"spd":2000}
// T=1: Cartesian move command
// x,y,z: Position in mm
// spd: Speed (1-3000)

// Move single axis
{"T":103,"axis":1,"pos":200,"spd":0.25}
// axis: 1=X, 2=Y, 3=Z, 4=T(tool angle)
```

#### Joint Angle Control
```json
// Control all joints (degrees)
{"T":122,"b":0,"s":45,"e":90,"h":180,"spd":20,"acc":15}
// b: base, s: shoulder, e: elbow, h: hand
// spd: degrees/second
// acc: degrees/second²

// Control single joint
{"T":121,"joint":2,"angle":45,"spd":10,"acc":10}
// joint: 1=BASE, 2=SHOULDER, 3=ELBOW, 4=HAND
```

#### Speed and Acceleration
```json
// Set global speed
{"T":11,"cmd":2000}
// cmd: 1-3000 (1=slowest, 3000=fastest)

// Set acceleration profile
{"T":12,"acc":20}
// acc: 0-254 (0=max acceleration)
```

#### Tool Control
```json
// Control tool/LED
{"T":106,"cmd":90,"spd":0,"acc":0}
// cmd: angle in radians (60-120 for LED brightness)

// LED brightness shortcut
{"T":13,"brightness":100}
// brightness: 0-100%
```

#### DEMA Mode (Dynamic Adaptation)
```json
// Enable/disable DEMA
{"T":30,"cmd":1}
// cmd: 0=disable, 1=enable

// Set DEMA parameters
{"T":31,"threshold":50,"factor":0.8}
// threshold: force threshold
// factor: compliance factor
```

#### Status Queries
```json
// Get current position
{"T":200}
// Returns: {"x":150,"y":0,"z":150,"joints":[0,45,90,180,0,90]}

// Get servo status
{"T":201}
// Returns: {"servos":[1,1,1,1,1,1],"torque":[50,60,40,30,20,10]}
```

### Error Codes
- **E001**: Invalid command format
- **E002**: Joint limit exceeded
- **E003**: Inverse kinematics failure
- **E004**: Communication timeout
- **E005**: Servo error/overload
- **E006**: Invalid parameter value

## Detailed Node Documentation

### Core System Nodes

#### state_manager_node
**Purpose**: Central state coordination and priority management

**Publishers**:
- `/luxo/current_state` (String): Current state name
- `/luxo/state_info` (StateInfo): Detailed state information
- `/roarm/light` (Int32): NeoPixel brightness
- `/diagnostics` (DiagnosticArray): Node health

**Subscribers**:
- `/luxo/node_heartbeat` (String): Node health monitoring
- `/animation_action/_action/status` (GoalStatusArray): Animation status
- `/joint_states` (JointState): Joint positions for state validation

**Services**:
- `/luxo/request_state_transition` (RequestStateTransition): State changes
- `/luxo/get_current_state` (GetState): Query current state

**Parameters**:
- `state_timeout`: Max time in any state (default: 300s)
- `idle_timeout`: Time before auto-idle (default: 60s)
- `priority_levels`: State priority configuration
- `neopixel_brightness`: Global LED brightness (0-100)

**State Priority Levels**:
1. ERROR (highest)
2. ESCAPE_MODE
3. COLLISION_AVOIDING
4. USER_CONTROL
5. PETTING
6. VOICE_FOLLOWING
7. EMOTION_REACTING
8. ANIMATING
9. RETURNING_HOME
10. IDLE (lowest)

#### hardware_interface_node
**Purpose**: Safe robot control with movement coordination

**Publishers**:
- `/joint_states` (JointState): Current joint positions
- `/roarm/position` (String): Position feedback
- `/luxo/movement_source` (String): Active movement source
- `/hardware/status` (HardwareStatus): Hardware health

**Subscribers**:
- `/joint_states_target` (JointState): Target positions
- `/roarm/direct_command` (String): Direct JSON commands
- `/dynamic_adaptation_toggle` (Bool): DEMA control
- `/luxo/current_state` (String): State awareness

**Services**:
- `/hardware/safe_move` (SafeMove): Validated movement
- `/hardware/get_limits` (GetLimits): Joint limit query
- `/hardware/emergency_stop` (Trigger): E-stop

**Safety Features**:
- Joint limit enforcement
- Velocity limiting
- Acceleration limiting
- Collision integration
- Base wraparound handling (-90° to 90°)
- Movement source tracking for DEMA

#### behavior_coordinator_node
**Purpose**: Combine behavior mixins for complex actions

**Mixins**:
- CollisionBehaviorMixin: Obstacle avoidance
- IdleBehaviorMixin: Autonomous animations
- VoiceBehaviorMixin: Voice following
- PettingBehaviorMixin: Touch responses
- CommandBehaviorMixin: Voice commands

**Publishers**:
- `/luxo/target_override` (JointState): Behavior targets
- `/behavior/active` (String): Active behavior
- `/luxo/movement_priority` (Int32): Movement priority

**Subscribers**:
- All sensor topics for behavior triggers
- `/luxo/current_state`: State-aware behavior

**Behavior Arbitration**:
1. Collision avoidance (highest priority)
2. User commands
3. Petting responses
4. Voice following
5. Idle animations (lowest priority)

### Sensor Processing Nodes

#### i2c_device_manager_node
**Purpose**: Manage all I2C sensors with error recovery

**Publishers**:
- `/touch_sensors/front` (Int32): Front proximity
- `/touch_sensors/back` (Int32): Back proximity
- `/touch_sensors/left` (Int32): Left proximity
- `/touch_sensors/right` (Int32): Right proximity
- `/proximity` (Int32): APDS9960 proximity
- `/gesture` (String): Detected gestures
- `/left_distance` (Int32): Left distance (mm)
- `/right_distance` (Int32): Right distance (mm)
- `/i2c/sensor_health` (SensorHealth): Sensor status

**Services**:
- `/i2c/configure_sensor` (ConfigureI2CSensor): Sensor setup
- `/i2c/reset_bus` (Trigger): Bus recovery

**Error Handling**:
- Automatic sensor reinitialization
- Bus reset on communication errors
- Configurable retry counts
- Health monitoring and reporting

#### collision_ros_node
**Purpose**: Multi-sensor collision detection and classification

**Publishers**:
- `/collision/front/status` (CollisionStatus): Front status
- `/collision/left/status` (CollisionStatus): Left status
- `/collision/right/status` (CollisionStatus): Right status
- `/collision/severity` (String): Overall severity
- `/collision_status_for_animation` (String): Animation integration
- `/collision/petting_events` (Bool): Touch detection

**Subscribers**:
- All proximity and distance sensor topics
- `/luxo/current_state`: State-aware processing
- `/joint_states`: Position-aware detection

**Collision Levels**:
- **NONE**: No obstacles detected
- **WARNING**: 150-300mm, slow down
- **DANGER**: <150mm, stop and avoid
- **COLLISION**: Contact detected

**Petting Detection**:
- Threshold: >200 proximity units
- Duration: >0.5s continuous
- Location awareness: Which sensor triggered

#### voice_direction_node
**Purpose**: Audio localization with motor noise compensation

**Publishers**:
- `/voice/direction` (Float32): Angle in degrees
- `/voice/active` (Bool): Voice activity detected
- `/voice/confidence` (Float32): Detection confidence
- `/voice/motor_compensated` (Bool): Compensation active

**Subscribers**:
- `/mic_array/audio` (AudioData): Raw audio
- `/joint_states`: Motor position for noise compensation
- `/joint_states_target`: Movement prediction

**Processing Pipeline**:
1. GCC-PHAT cross-correlation
2. VAD (Voice Activity Detection)
3. Motor noise compensation
4. Parallax correction (10cm back, 15cm up)
5. Direction smoothing
6. Confidence estimation

**Direction Mapping**:
- 0° = Front
- 90° = Right
- 180° = Back
- -90° = Left

### Vision Nodes

#### camera_interaction_node
**Purpose**: Emotion and face detection with behavior triggers

**Publishers**:
- `/camera/emotion` (String): Detected emotion
- `/camera/emotion_confidence` (Float32): Detection confidence
- `/camera/face_count` (Int32): Number of faces
- `/camera/face_distance` (Float32): Distance to nearest face
- `/camera/person_id` (Int32): Person tracking ID
- `/camera/image_annotated` (Image): Debug visualization

**Subscribers**:
- `/camera/image_raw` (Image): Camera feed
- `/camera/depth` (Image): Depth data
- `/luxo/current_state`: State-aware processing

**Emotion Mappings**:
```python
emotion_animations = {
    'happy': ['excited', 'playful', 'dance'],
    'sad': ['sad', 'droop'],
    'angry': ['shake', 'think'],
    'surprised': ['startled', 'curious'],
    'neutral': ['idle', 'curious']
}
```

**Processing Parameters**:
- Face detection threshold: 0.7 confidence
- Emotion detection threshold: 0.6 confidence
- Tracking persistence: 2 seconds
- Maximum faces: 5

### Animation System Nodes

#### animation_command_node
**Purpose**: Animation playback with interpolation

**Action Server**:
- `/animation_action` (PlayAnimation): Animation requests

**Publishers**:
- `/joint_states_target` (JointState): Animation frames
- `/animation/current` (String): Playing animation
- `/animation/progress` (Float32): Playback progress
- `/luxo/movement_source` (String): "animation"

**Subscribers**:
- `/roarm/animation_command` (String): Simple commands
- `/collision_status_for_animation` (String): Collision integration
- `/luxo/current_state`: State validation

**Animation Format**:
```python
{
    "name": "animation_name",
    "frames": [
        {
            "servos": {"j1": 0, "j2": 45, "j3": 90, "j4": 180, "j5": 0, "j6": 90},
            "timing": 1.0,  # Speed multiplier
            "duration": 0.5  # Frame duration
        }
    ],
    "loop": false,
    "priority": 5
}
```

**Interpolation**:
- Cubic spline for smooth transitions
- Configurable FPS (default: 20)
- Collision-aware frame skipping
- State-based validation

### System Monitoring Nodes

#### system_monitor_node
**Purpose**: System health and performance monitoring

**Publishers**:
- `/system/cpu_usage` (Float32): CPU percentage
- `/system/ram_usage` (Float32): RAM percentage
- `/system/temperature` (Float32): CPU temperature
- `/system/disk_usage` (Float32): Disk percentage
- `/system/network_stats` (NetworkStats): Network I/O
- `/diagnostics` (DiagnosticArray): System diagnostics

**Monitoring Intervals**:
- CPU/RAM: Every 1 second
- Temperature: Every 5 seconds
- Disk: Every 30 seconds
- Network: Every 1 second

**Thermal Protection**:
- Warning: >70°C
- Throttle: >80°C
- Shutdown: >85°C

#### watchdog_node
**Purpose**: Detect and recover from system failures

**Publishers**:
- `/watchdog/status` (WatchdogStatus): Health report
- `/watchdog/failures` (StringArray): Active failures
- `/diagnostics` (DiagnosticArray): Watchdog health

**Monitored Topics**:
```yaml
monitored_topics:
  - name: "/luxo/current_state"
    timeout: 30.0
    critical: true
  - name: "/joint_states"
    timeout: 25.0
    critical: true
  - name: "/roarm/animation_command"
    timeout: 60.0
    critical: false
  - name: "/roarm/position"
    timeout: 5.0
    critical: false
```

**Recovery Actions**:
1. Topic timeout → Request safe state
2. State stuck → Force IDLE transition
3. Joint freeze → RETURNING_HOME
4. Silent failure → ERROR → IDLE cycle
5. System hang → Node restart (optional)

### Display Node

#### framebuffer_display_node
**Purpose**: Visual system status on physical display

**Subscribers**:
- `/luxo/current_state`: State visualization
- `/system/*`: System metrics
- `/camera/emotion`: Emotion overlay
- `/collision/*`: Sensor visualization
- `/joint_states`: Joint positions


**Special Effects**:
- Pink overlay: Petting active
- Red overlay: Collision/angry
- Blue pulse: Voice following
- Green fade: Happy emotion

## Animation Creation Guide

### Step 1: Understanding Joint Constraints
```python
# Safe operating ranges (degrees)
JOINT_LIMITS = {
    'j1': (-90, 90),      # Base rotation
    'j2': (0, 180),       # Shoulder
    'j3': (0, 180),       # Elbow
    'j4': (0, 180),       # Wrist
    'j5': (-90, 90),      # Hand roll
    'j6': (60, 120)       # Tool/LED
}

# Preferred ranges for natural movement
PREFERRED_RANGES = {
    'j1': (-60, 60),      # Avoid extremes
    'j2': (30, 150),      # Keep some elevation
    'j3': (45, 135),      # Natural elbow bend
    'j4': (90, 180),      # Neutral wrist
    'j5': (-45, 45),      # Limited roll
    'j6': (80, 100)       # Normal brightness
}
```

### Step 2: Planning Your Animation

1. **Sketch keyframes**: Draw or visualize main positions
2. **Consider transitions**: How to move between keyframes
3. **Apply Disney principles**:
   - Anticipation: Small opposite movement first
   - Follow-through: Overshoot and settle
   - Ease in/out: No linear movements
   - Arcs: Natural curved paths

### Step 3: Creating Keyframes

```python
def create_wave_animation():
    """Example: Simple wave gesture"""
    # Start from home position
    home = {"j1": 0, "j2": 45, "j3": 90, "j4": 180, "j5": 0, "j6": 90}
    
    # Anticipation - pull back slightly
    anticipate = {"j1": -10, "j2": 50, "j3": 95, "j4": 180, "j5": 0, "j6": 90}
    
    # Wave positions
    wave_left = {"j1": -30, "j2": 60, "j3": 120, "j4": 150, "j5": -30, "j6": 100}
    wave_right = {"j1": 30, "j2": 60, "j3": 120, "j4": 150, "j5": 30, "j6": 100}
    
    # Return with follow-through
    overshoot = {"j1": 5, "j2": 43, "j3": 88, "j4": 182, "j5": 0, "j6": 90}
    
    frames = [
        {"servos": home, "timing": 1.0},
        {"servos": anticipate, "timing": 0.8},
        {"servos": wave_left, "timing": 1.2},
        {"servos": wave_right, "timing": 1.0},
        {"servos": wave_left, "timing": 1.0},
        {"servos": wave_right, "timing": 1.0},
        {"servos": overshoot, "timing": 0.8},
        {"servos": home, "timing": 1.0}
    ]
    
    return frames
```

### Step 4: Testing Your Animation

```bash
# Test in simulation first
ros2 launch luxo_behaviors luxo_system.launch.py

# Send animation command
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: wave"

# Monitor joint states
ros2 topic echo /joint_states

# Check for collisions
ros2 topic echo /collision/severity
```

### Step 5: Integration

1. Add to animation plugin file:
```python
# src/luxo_behaviors/luxo_behaviors/animation_plugins/custom_animations.py
class CustomAnimations:
    @staticmethod
    def wave():
        return create_wave_animation()
```

2. Register in animation command:
```python
# In animation_command.py
self.animations['wave'] = CustomAnimations.wave
```

3. Add emotion mapping if applicable:
```python
# In camera_interaction.py
self.emotion_animations['greeting'] = ['wave', 'nod']
```

### Animation Best Practices

1. **Start and end at home position**
2. **Keep movements under 2 seconds per segment**
3. **Test collision boundaries**
4. **Add personality through timing variations**
5. **Consider sound effects or LED patterns**
6. **Document inspiration and purpose**

## Troubleshooting Deep Dive

### Serial Communication Issues

#### Symptom: "Serial port busy"
```bash
# Find process using port
sudo lsof /dev/ttyAMA0
# Kill the process
sudo kill -9 [PID]

# Alternative: Release port
sudo fuser -k /dev/ttyAMA0
```

#### Symptom: "Permission denied"
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Logout and login again

# Temporary fix
sudo chmod 666 /dev/ttyAMA0
```

#### Symptom: "No response from robot"
1. Check physical connection
2. Verify baud rate: 115200
3. Test with screen:
```bash
screen /dev/ttyAMA0 115200
# Send: {"T":100}
# Should move to home position
```

### I2C Sensor Issues

#### Symptom: "No I2C devices found"
```bash
# Check I2C is enabled
sudo raspi-config
# Interface Options → I2C → Enable

# Scan for devices
i2cdetect -y 1
# Should show devices at 0x39, 0x29, etc.
```

#### Symptom: "Intermittent sensor readings"
1. Check wiring and pull-up resistors (4.7kΩ)
2. Reduce I2C speed:
```bash
# Edit /boot/firmware/config.txt
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=50000  # 50kHz instead of 100kHz
```


## Integration Examples

### Custom Behavior Integration

```python
# Create new behavior mixin
class DanceBehaviorMixin:
    def __init__(self):
        self.dance_timer = None
        self.dance_patterns = ['sway', 'bob', 'spin']
        
    def start_dance_mode(self):
        """Start autonomous dancing"""
        self.dance_timer = self.create_timer(5.0, self.next_dance_move)
        
    def next_dance_move(self):
        if self.state_machine.current_state != 'DANCING':
            return
            
        move = random.choice(self.dance_patterns)
        self.animation_client.send_goal(move)
        
# Add to behavior coordinator
class BehaviorCoordinator(Node, DanceBehaviorMixin, ...):
    def __init__(self):
        super().__init__('behavior_coordinator')
        DanceBehaviorMixin.__init__(self)
```

### Custom Sensor Integration

```python
# Add new I2C sensor
class TemperatureSensor:
    def __init__(self, i2c, address=0x48):
        self.i2c = i2c
        self.address = address
        
    def read_temperature(self):
        # Read two bytes from sensor
        data = self.i2c.readfrom(self.address, 2)
        # Convert to temperature
        temp = (data[0] << 8 | data[1]) / 256.0
        return temp
        
# Add to I2C device manager
self.temp_sensor = TemperatureSensor(self.i2c)
self.temp_pub = self.create_publisher(Float32, '/sensors/temperature', 10)
```

### Voice Command Extension

```python
# Add custom voice commands
CUSTOM_COMMANDS = {
    5: 'dance_mode',      # "Start dancing"
    6: 'sleep_mode',      # "Go to sleep"
    7: 'wake_up',         # "Wake up"
    8: 'follow_me',       # "Follow my voice"
    9: 'stop_following'   # "Stop following"
}

def handle_custom_command(self, cmd_id):
    if cmd_id == 5:
        self.request_state('DANCING')
    elif cmd_id == 6:
        self.animation_client.send_goal('sleep')
        self.request_state('IDLE')
    # ... etc
```



## State Machine Diagrams

### State Transition Diagram
```
                          ┌─────────────┐
                          │ INITIALIZING│
                          └──────┬──────┘
                                 │
                                 ▼
                          ┌─────────────┐
               ┌──────────│    IDLE     │◄─────────┐
               │          └─────────────┘          │
               │            │ │ │ │ │              │
               ▼            │ │ │ │ │              │
        ┌──────────┐        │ │ │ │ │         ┌───────────┐
        │ANIMATING │◄───────┘ │ │ │ └────────►│   ERROR   │
        └────┬─────┘          │ │ │           └─────┬─────┘
             │                │ │ │                 │
             │      ┌─────────┘ │ └─────────┐       │
             │      ▼           ▼           ▼       │
             │ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
             │ │ PETTING │ │  VOICE  │ │COLLISION│ │
             │ └────┬────┘ │FOLLOWING│ │AVOIDING │ │
             │      │      └────┬────┘ └────┬────┘ │
             │      │           │           │      │
             │      │           │           ▼      │
             │      │           │     ┌──────────┐ │
             │      │           │     │  ESCAPE  │ │
             │      │           │     │   MODE   │ │
             │      │           │     └─────┬────┘ │
             │      │           │           │      │
             │      ▼           ▼           ▼      │
             │ ┌────────────────────────────────┐  │
             └►│        RETURNING_HOME          │◄─┘
               └────────────────┬───────────────┘
                                │
                                └──────────────────┘
```

### Priority Resolution Flow
```
┌─────────────────────────────────────────────────┐
│              State Priority System               │
├─────────────────────────────────────────────────┤
│  Priority │ State              │ Can Override   │
├───────────┼────────────────────┼────────────────┤
│     1     │ ERROR              │ All states     │
│     2     │ ESCAPE_MODE        │ All except 1   │
│     3     │ COLLISION_AVOIDING │ All except 1-2 │
│     4     │ USER_CONTROL       │ All except 1-3 │
│     5     │ PETTING            │ 6-10           │
│     6     │ VOICE_FOLLOWING    │ 7-10           │
│     7     │ EMOTION_REACTING   │ 8-10           │
│     8     │ ANIMATING          │ 9-10           │
│     9     │ RETURNING_HOME     │ 10             │
│    10     │ IDLE               │ None           │
└─────────────────────────────────────────────────┘
```

## Sensor Data Processing Pipeline

### Touch Sensor Pipeline
```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  I2C Bus │───►│  APDS9960│───►│ Threshold│───►│  Event   │
│  Read    │    │  Driver  │    │  Filter  │    │  Detect  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │   Debounce   │
                              │   (100ms)    │
                              └──────┬───────┘
                                     │
        ┌────────────────────────────┼────────────────────┐
        ▼                            ▼                    ▼
┌──────────────┐           ┌──────────────┐     ┌──────────────┐
│Touch Duration│           │   Gesture    │     │  Proximity   │
│   Tracking   │           │ Recognition  │     │   Warning    │
└──────┬───────┘           └──────┬───────┘     └──────┬───────┘
       │                          │                     │
       ▼                          ▼                     ▼
┌──────────────┐           ┌──────────────┐     ┌──────────────┐
│   Petting    │           │   Command    │     │  Collision   │
│   Events     │           │   Trigger    │     │  Detection   │
└──────────────┘           └──────────────┘     └──────────────┘
```

### Voice Processing Pipeline
```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│Microphone│───►│   Audio  │───►│ GCC-PHAT │───►│   DOA    │
│  Array   │    │ Capture  │    │Algorithm │    │Estimation│
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                      │                              │
                      ▼                              ▼
              ┌──────────────┐              ┌──────────────┐
              │     VAD      │              │   Parallax   │
              │  Detection   │              │ Correction   │
              └──────┬───────┘              └──────┬───────┘
                     │                             │
                     └──────────┬──────────────────┘
                                ▼
                        ┌──────────────┐
                        │Motor Noise   │
                        │Compensation  │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Direction   │
                        │  Smoothing   │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │Voice Following│
                        │   Behavior   │
                        └──────────────┘
```

## Custom Behavior Creation

### Template for New Behavior

```python
# File: src/luxo_behaviors/luxo_behaviors/custom_behavior.py

from rclpy.node import Node
from std_msgs.msg import String, Bool
from sensor_msgs.msg import JointState

class CustomBehaviorMixin:
    """Template for creating new behaviors."""
    
    def __init__(self):
        # Initialize behavior-specific variables
        self.behavior_active = False
        self.behavior_timer = None
        self.behavior_state = 'idle'
        
        # Create subscribers for triggers
        self.trigger_sub = self.create_subscription(
            Bool,
            '/custom/trigger',
            self.trigger_callback,
            10
        )
        
        # Create publishers for behavior output
        self.behavior_pub = self.create_publisher(
            JointState,
            '/custom/target',
            10
        )
        
    def trigger_callback(self, msg):
        """Handle behavior trigger."""
        if msg.data and not self.behavior_active:
            self.start_behavior()
        elif not msg.data and self.behavior_active:
            self.stop_behavior()
            
    def start_behavior(self):
        """Initialize and start the behavior."""
        self.get_logger().info("Starting custom behavior")
        
        # Request appropriate state
        self.request_state_transition('CUSTOM_STATE', priority=6)
        
        # Set movement source for DEMA
        self.publish_movement_source('custom_behavior')
        
        # Start behavior loop
        self.behavior_active = True
        self.behavior_timer = self.create_timer(0.1, self.behavior_loop)
        
    def behavior_loop(self):
        """Main behavior execution loop."""
        if not self.behavior_active:
            return
            
        # Check if we're in the right state
        if self.current_state not in ['CUSTOM_STATE', 'IDLE']:
            self.get_logger().warn("Wrong state for custom behavior")
            self.stop_behavior()
            return
            
        # Implement behavior logic
        if self.behavior_state == 'idle':
            # Do something
            self.behavior_state = 'moving'
            self.publish_movement_target()
            
        elif self.behavior_state == 'moving':
            # Check if movement complete
            if self.is_movement_complete():
                self.behavior_state = 'idle'
                
    def publish_movement_target(self):
        """Publish joint targets for the behavior."""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ['j1', 'j2', 'j3', 'j4', 'j5', 'j6']
        
        # Calculate target positions
        msg.position = self.calculate_targets()
        
        self.behavior_pub.publish(msg)
        
    def calculate_targets(self):
        """Calculate joint targets based on behavior logic."""
        # Implement your behavior algorithm
        return [0.0, 0.785, 1.57, 3.14, 0.0, 1.57]
        
    def stop_behavior(self):
        """Clean up and stop the behavior."""
        self.get_logger().info("Stopping custom behavior")
        
        self.behavior_active = False
        if self.behavior_timer:
            self.behavior_timer.cancel()
            self.behavior_timer = None
            
        # Return to idle if we initiated the state
        if self.current_state == 'CUSTOM_STATE':
            self.request_state_transition('IDLE')
```

### Integration Steps

1. **Add to behavior coordinator**:
```python
# In behavior_coordinator.py
from luxo_behaviors.custom_behavior import CustomBehaviorMixin

class BehaviorCoordinator(Node, 
                         CustomBehaviorMixin,
                         CollisionBehaviorMixin,
                         # ... other mixins
                         ):
    def __init__(self):
        super().__init__('behavior_coordinator')
        
        # Initialize all mixins
        CustomBehaviorMixin.__init__(self)
        # ...
```

2. **Add state to state machine**:
```python
# In state_manager.py
self.states = [
    'INITIALIZING', 'IDLE', 'ANIMATING',
    # ...
    'CUSTOM_STATE'  # Add your state
]

self.state_priorities = {
    'ERROR': 1,
    'ESCAPE_MODE': 2,
    # ...
    'CUSTOM_STATE': 6,  # Set appropriate priority
    # ...
}
```

3. **Create launch parameter**:
```python
# In luxo_system.launch.py
DeclareLaunchArgument(
    'enable_custom_behavior',
    default_value='true',
    description='Enable custom behavior'
)
```