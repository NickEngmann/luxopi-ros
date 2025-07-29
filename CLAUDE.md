# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Architecture

### Hardware Components
- **Robot**: RoArm-M3 6-DOF arm with RoArm-M3-Tool end effector
- **Computer**: Raspberry Pi 5 (8GB recommended)
- **Camera**: OAK-D depth camera for vision and collision detection
- **Microphone**: ReSpeaker 2-mic array for voice direction
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

# Full system with all features
ros2 launch luxo_behaviors luxo_system.launch.py \
    use_hardware:=true \
    use_camera:=true \
    sense_collision:=true \
    enable_dynamic_adaptation:=true

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

### Silent Failure Mode Recovery
The specific 4+ hour issue where system metrics continue but commands stop is detected by:
1. State updates continuing but no animation commands for 2+ minutes
2. Joint states updating but no serial feedback
3. Automatic recovery via ERROR → IDLE state transition cycle

## Common Issues and Solutions

### Silent Failure Mode (4+ hours)
- **Symptoms**: No idle animations, only system metrics publishing
- **Solution**: Watchdog automatically detects and attempts recovery
- **Manual recovery**: `ros2 service call /luxo/request_state_transition luxo_interfaces/srv/RequestStateTransition "{target_state: 'IDLE'}"`

### Serial Communication
- Permission error: Add user to dialout group: `sudo usermod -a -G dialout $USER`
- Port busy: Check with `lsof /dev/ttyAMA0`, kill process if needed
- Wrong baud rate: Ensure 115200 in launch file

### Camera Issues
- Camera not detected: Check with `ls /dev/video*`
- Permission denied: Add user to video group
- High CPU usage: Reduce resolution or FPS in camera_interaction.py

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

## From the TODO List

Future improvements noted:
1. Gradual wake from sleep animations
2. Recovery from error states
3. Predictive collision avoidance
4. Multi-person tracking
5. Gesture recognition improvements
6. Dynamic safety zones
7. Animation blending/chaining
8. Emotional memory system
9. Performance optimizations
10. Unit test coverage

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

**Display Layout**:
```
┌─────────────────────┐
│ State: IDLE         │
│ CPU: 45% RAM: 62%   │
│ Temp: 55°C          │
├─────────────────────┤
│ Emotion: Happy      │
│ Faces: 1 @ 0.8m    │
├─────────────────────┤
│ Collision:          │
│ F:-- L:W R:-- B:--  │
├─────────────────────┤
│ J1:-15° J2:45°      │
│ J3:90° J4:180°      │
└─────────────────────┘
```

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

### Camera Issues

#### Symptom: "No camera detected"
```bash
# Check USB connection
lsusb | grep Luxonis
# Should show: 03e7:f63b or similar

# Reset USB device
sudo usbreset 03e7:f63b

# Check permissions
ls -la /dev/bus/usb/*/*
```

#### Symptom: "High CPU usage from camera"
1. Reduce resolution in camera_interaction.py:
```python
self.pipeline.setCameraBoardSocket(dai.CameraBoardSocket.RGB)
self.pipeline.setResolution(dai.ColorCameraProperties.SensorResolution.THE_720_P)
self.pipeline.setFps(15)  # Reduce from 30
```

### State Machine Issues

#### Symptom: "Stuck in state"
```bash
# Check current state
ros2 topic echo /luxo/state_info

# Force state transition
ros2 service call /luxo/request_state_transition \
  luxo_interfaces/srv/RequestStateTransition \
  "{target_state: 'IDLE', priority: 10}"
```

#### Symptom: "State transitions ignored"
1. Check state priorities
2. Verify no blocking animations
3. Check for error states:
```bash
ros2 topic echo /diagnostics
```

### Performance Issues

#### High CPU Usage
```bash
# Profile CPU usage by process
top -p $(pgrep -d',' -f "ros2")

# Check ROS2 node CPU usage
ros2 run rqt_top rqt_top

# Common culprits:
# - camera_interaction: Reduce FPS/resolution
# - collision_ros: Increase sensor read interval
# - animation_command: Check for runaway animations
```

#### Memory Leaks
```bash
# Monitor memory usage
watch -n 1 'ps aux | grep ros2 | grep -v grep'

# Use valgrind for detailed analysis
valgrind --leak-check=full ros2 run luxo_behaviors state_manager
```

### Debug Logging

#### Enable verbose logging
```bash
# Set log level for specific node
ros2 run luxo_behaviors state_manager --ros-args --log-level debug

# Set global log level
export RCUTILS_LOG_MIN_SEVERITY=10  # DEBUG level
```

#### Log locations
```bash
# ROS2 logs
~/.ros/log/latest/

# System logs
journalctl -u luxopi-ros -f

# Application logs (using start_luxopi.sh)
tail -f ~/luxopi-ros/logs/luxopi.log
```

## Performance Tuning Guide

### CPU Optimization

1. **Disable unused features**:
```bash
ros2 launch luxo_behaviors luxo_system.launch.py \
  enable_person_tracking:=false \
  enable_depth_collision:=false
```

2. **Reduce sensor polling rates**:
```python
# In i2c_device_manager.py
self.sensor_timer = self.create_timer(0.1, self.read_sensors)  # 10Hz instead of 20Hz
```

3. **Optimize animation interpolation**:
```python
# Reduce interpolation FPS
self.animation_fps = 15  # From 20
```

### Memory Optimization

1. **Limit animation cache**:
```python
# Only load frequently used animations
CORE_ANIMATIONS = ['idle', 'nod', 'shake', 'excited']
```

2. **Reduce message queue sizes**:
```python
# In node creation
self.create_subscription(JointState, '/joint_states', 
                        self.joint_callback, 1)  # Queue size 1
```

### Network Optimization

1. **Use DDS configuration**:
```xml
<!-- cyclonedds.xml -->
<CycloneDDS>
  <Domain>
    <General>
      <NetworkInterfaceAddress>lo</NetworkInterfaceAddress>
    </General>
  </Domain>
</CycloneDDS>
```

2. **Reduce topic frequency**:
```python
# Throttle non-critical topics
self.throttle_timer = self.create_timer(0.5, self.publish_diagnostics)
```

### Startup Optimization

1. **Lazy loading**:
```python
# Load animations on demand
def get_animation(self, name):
    if name not in self.loaded_animations:
        self.loaded_animations[name] = self.load_animation(name)
    return self.loaded_animations[name]
```

2. **Parallel initialization**:
```python
import concurrent.futures

with concurrent.futures.ThreadPoolExecutor() as executor:
    executor.submit(self.init_sensors)
    executor.submit(self.init_camera)
    executor.submit(self.init_animations)
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

### Emotion Memory System

```python
class EmotionMemory:
    def __init__(self, memory_duration=300):  # 5 minutes
        self.emotion_history = deque(maxlen=100)
        self.person_emotions = {}  # Track per person
        self.memory_duration = memory_duration
        
    def record_emotion(self, person_id, emotion, confidence):
        timestamp = time.time()
        self.emotion_history.append({
            'person_id': person_id,
            'emotion': emotion,
            'confidence': confidence,
            'timestamp': timestamp
        })
        
        # Update person profile
        if person_id not in self.person_emotions:
            self.person_emotions[person_id] = defaultdict(float)
        self.person_emotions[person_id][emotion] += confidence
        
    def get_person_mood(self, person_id):
        """Get overall mood for a person"""
        if person_id not in self.person_emotions:
            return 'neutral'
            
        emotions = self.person_emotions[person_id]
        return max(emotions.items(), key=lambda x: x[1])[0]
```

## Complete Topic/Service Reference

### State Management Topics

| Topic | Type | Publisher | Description |
|-------|------|-----------|-------------|
| `/luxo/current_state` | std_msgs/String | state_manager | Current state name |
| `/luxo/state_info` | luxo_interfaces/StateInfo | state_manager | Detailed state info |
| `/luxo/node_heartbeat` | std_msgs/String | all nodes | Node health ping |
| `/luxo/target_override` | sensor_msgs/JointState | behavior_coordinator | Behavior targets |
| `/luxo/movement_source` | std_msgs/String | multiple | Active movement source |
| `/luxo/movement_priority` | std_msgs/Int32 | behavior_coordinator | Movement priority level |

### Joint Control Topics

| Topic | Type | Publisher | Description |
|-------|------|-----------|-------------|
| `/joint_states` | sensor_msgs/JointState | hardware_interface | Current positions |
| `/joint_states_target` | sensor_msgs/JointState | multiple | Target positions |
| `/roarm/position` | std_msgs/String | hardware_interface | JSON position feedback |
| `/roarm/animation_command` | std_msgs/String | external | Animation triggers |
| `/roarm/direct_command` | std_msgs/String | external | Direct JSON commands |
| `/roarm/light` | std_msgs/Int32 | state_manager | LED brightness |

### Sensor Topics

| Topic | Type | Publisher | Description |
|-------|------|-----------|-------------|
| `/touch_sensors/front` | std_msgs/Int32 | i2c_manager | Front touch (0-255) |
| `/touch_sensors/back` | std_msgs/Int32 | i2c_manager | Back touch (0-255) |
| `/touch_sensors/left` | std_msgs/Int32 | i2c_manager | Left touch (0-255) |
| `/touch_sensors/right` | std_msgs/Int32 | i2c_manager | Right touch (0-255) |
| `/proximity` | std_msgs/Int32 | i2c_manager | APDS9960 proximity |
| `/gesture` | std_msgs/String | i2c_manager | Detected gestures |
| `/left_distance` | std_msgs/Int32 | i2c_manager | Left distance (mm) |
| `/right_distance` | std_msgs/Int32 | i2c_manager | Right distance (mm) |
| `/voice/direction` | std_msgs/Float32 | voice_direction | Voice angle (degrees) |
| `/voice/active` | std_msgs/Bool | voice_direction | Voice detected |
| `/voice_command/detected` | std_msgs/Int32 | hardware_interface | Voice command ID |

### Collision Topics

| Topic | Type | Publisher | Description |
|-------|------|-----------|-------------|
| `/collision/front/status` | luxo_interfaces/CollisionStatus | collision_ros | Front collision |
| `/collision/left/status` | luxo_interfaces/CollisionStatus | collision_ros | Left collision |
| `/collision/right/status` | luxo_interfaces/CollisionStatus | collision_ros | Right collision |
| `/collision/severity` | std_msgs/String | collision_ros | Overall severity |
| `/collision_status_for_animation` | std_msgs/String | collision_ros | Animation integration |
| `/collision/petting_events` | std_msgs/Bool | collision_ros | Touch detected |

### Camera Topics

| Topic | Type | Publisher | Description |
|-------|------|-----------|-------------|
| `/camera/emotion` | std_msgs/String | camera_interaction | Detected emotion |
| `/camera/emotion_confidence` | std_msgs/Float32 | camera_interaction | Confidence (0-1) |
| `/camera/face_count` | std_msgs/Int32 | camera_interaction | Number of faces |
| `/camera/face_distance` | std_msgs/Float32 | camera_interaction | Distance (meters) |
| `/camera/person_id` | std_msgs/Int32 | camera_interaction | Person tracking ID |
| `/camera/image_raw` | sensor_msgs/Image | camera_interaction | RGB image |
| `/camera/depth` | sensor_msgs/Image | camera_interaction | Depth map |

### System Monitoring Topics

| Topic | Type | Publisher | Description |
|-------|------|-----------|-------------|
| `/system/cpu_usage` | std_msgs/Float32 | system_monitor | CPU % (0-100) |
| `/system/ram_usage` | std_msgs/Float32 | system_monitor | RAM % (0-100) |
| `/system/temperature` | std_msgs/Float32 | system_monitor | CPU temp (°C) |
| `/system/disk_usage` | std_msgs/Float32 | system_monitor | Disk % (0-100) |
| `/diagnostics` | diagnostic_msgs/DiagnosticArray | multiple | System diagnostics |
| `/watchdog/status` | luxo_interfaces/WatchdogStatus | watchdog | Watchdog health |

### Services

| Service | Type | Provider | Description |
|---------|------|----------|-------------|
| `/luxo/request_state_transition` | RequestStateTransition | state_manager | Change state |
| `/hardware/safe_move` | SafeMove | hardware_interface | Validated movement |
| `/hardware/emergency_stop` | std_srvs/Trigger | hardware_interface | E-stop |
| `/i2c/configure_sensor` | ConfigureI2CSensor | i2c_manager | Sensor setup |
| `/i2c/reset_bus` | std_srvs/Trigger | i2c_manager | Reset I2C bus |
| `/trigger_idle_animation` | std_srvs/Trigger | behavior_coordinator | Force idle animation |

### Actions

| Action | Type | Server | Description |
|--------|------|--------|-------------|
| `/animation_action` | PlayAnimation | animation_command | Play animation |
| `/follow_person_action` | FollowPerson | camera_interaction | Track person |
| `/voice_follow_action` | VoiceFollow | voice_behavior | Follow voice |

## Development Environment Setup

### VSCode Configuration

`.vscode/settings.json`:
```json
{
    "python.autoComplete.extraPaths": [
        "/opt/ros/jazzy/lib/python3.12/site-packages",
        "${workspaceFolder}/install/luxo_behaviors/lib/python3.12/site-packages",
        "${workspaceFolder}/install/luxo_interfaces/lib/python3.12/site-packages"
    ],
    "python.analysis.extraPaths": [
        "/opt/ros/jazzy/lib/python3.12/site-packages",
        "${workspaceFolder}/install/luxo_behaviors/lib/python3.12/site-packages",
        "${workspaceFolder}/install/luxo_interfaces/lib/python3.12/site-packages"
    ],
    "ros.distro": "jazzy",
    "files.associations": {
        "*.launch.py": "python",
        "*.urdf": "xml",
        "*.xacro": "xml"
    }
}
```

`.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "ROS2: Launch",
            "type": "ros",
            "request": "launch",
            "target": "${workspaceFolder}/src/luxo_behaviors/launch/luxo_system.launch.py",
            "arguments": ["use_hardware:=false"]
        },
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}/install/luxo_behaviors/lib/python3.12/site-packages:${env:PYTHONPATH}"
            }
        }
    ]
}
```

### Debugging Tips

1. **Enable ROS2 debug logging**:
```bash
export RCUTILS_CONSOLE_OUTPUT_FORMAT="[{severity} {time}] [{name}]: {message}"
export RCUTILS_COLORIZED_OUTPUT=1
export RCUTILS_LOG_MIN_SEVERITY=DEBUG
```

2. **Use ROS2 CLI for debugging**:
```bash
# List all active nodes
ros2 node list

# Get node info
ros2 node info /state_manager

# List node parameters
ros2 param list /state_manager

# Get parameter value
ros2 param get /state_manager idle_timeout

# Set parameter dynamically
ros2 param set /state_manager idle_timeout 30.0
```

3. **Python debugging with pdb**:
```python
import pdb

def problematic_function():
    pdb.set_trace()  # Debugger will stop here
    # Your code
```

4. **GDB for C++ nodes**:
```bash
# Launch with GDB
ros2 run --prefix 'gdb -ex run' package_name node_name
```

## Contributing Guidelines

### Code Style

1. **Python**: Follow PEP 8
```python
# Good
def calculate_joint_angle(current_pos, target_pos, speed=1.0):
    """Calculate interpolated joint angle.
    
    Args:
        current_pos: Current position in radians
        target_pos: Target position in radians
        speed: Movement speed multiplier
        
    Returns:
        Next position in radians
    """
    delta = target_pos - current_pos
    return current_pos + (delta * speed * 0.1)
```

2. **Node naming**: Use descriptive names
```python
super().__init__('behavior_coordinator_node')
```

3. **Topic naming**: Use namespaces
```python
self.create_publisher(String, '/luxo/current_state', 10)
```

### Git Workflow

1. **Branch naming**:
   - `feature/description` - New features
   - `bugfix/description` - Bug fixes
   - `refactor/description` - Code refactoring
   - `docs/description` - Documentation

2. **Commit messages**:
```
type: subject

Detailed description of changes

Closes #123
```

3. **Pull request template**:
```markdown
## Description
Brief description of changes

## Testing
- [ ] Tested in simulation
- [ ] Tested on hardware
- [ ] Added unit tests

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No hardcoded values
```

### Testing Requirements

1. **Unit tests**: For critical functions
```python
import unittest
from luxo_behaviors.shared_utils import PositionUtils

class TestPositionUtils(unittest.TestCase):
    def test_degrees_to_radians(self):
        self.assertAlmostEqual(
            PositionUtils.degrees_to_radians(90),
            1.5708,
            places=4
        )
```

2. **Integration tests**: For node communication
```python
import rclpy
from rclpy.node import Node
import pytest

@pytest.mark.timeout(10)
def test_state_transition():
    # Test state manager transitions
    pass
```

3. **Hardware tests**: Document manual test procedures

## Hardware Calibration Guide

### Joint Calibration

1. **Home position calibration**:
```bash
# Move to mechanical home
ros2 topic pub --once /roarm/direct_command std_msgs/String \
  '{"data": "{\"T\":100}"}'

# Record encoder values
ros2 topic echo /roarm/position
```

2. **Joint limit calibration**:
```python
# Test each joint's range
for angle in range(-90, 91, 10):
    cmd = {"T": 121, "joint": 1, "angle": angle, "spd": 10}
    # Send command and verify movement
```

### Sensor Calibration

#### Touch Sensor Calibration
```python
# Read baseline values
baseline_values = {
    'front': [],
    'back': [],
    'left': [],
    'right': []
}

# Collect 100 samples
for _ in range(100):
    for sensor in baseline_values:
        value = read_sensor(sensor)
        baseline_values[sensor].append(value)
        
# Calculate thresholds
for sensor, values in baseline_values.items():
    mean = np.mean(values)
    std = np.std(values)
    threshold = mean + (3 * std)  # 3 sigma
    print(f"{sensor}: baseline={mean:.1f}, threshold={threshold:.1f}")
```

#### Distance Sensor Calibration
```bash
# Place object at known distances
for distance in [100, 200, 300, 500, 1000]:  # mm
    input(f"Place object at {distance}mm and press Enter")
    # Read sensor values
    ros2 topic echo -n 1 /left_distance
    ros2 topic echo -n 1 /right_distance
```

#### Camera Calibration
```python
# Use OpenCV calibration
import cv2
import numpy as np

# Checkerboard calibration
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
pattern_size = (9, 6)

# Capture calibration images
# Process with cv2.calibrateCamera()
```

### Voice Array Calibration

1. **Test DOA accuracy**:
```bash
# Play test tone from known angles
for angle in [0, 45, 90, 135, 180, -135, -90, -45]:
    print(f"Play sound from {angle} degrees")
    # Monitor detected angle
    ros2 topic echo /voice/direction
```

2. **Adjust parallax correction**:
```python
# In voice_direction_node.py
PARALLAX_OFFSET_X = 10  # cm behind
PARALLAX_OFFSET_Z = 15  # cm up
# Fine-tune based on testing
```

## Network Architecture

### DDS Configuration

Create `cyclonedds.xml`:
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDDS xmlns="https://cdds.io/config" 
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="https://cdds.io/config 
            https://raw.githubusercontent.com/eclipse-cyclonedds/cyclonedds/master/etc/cyclonedds.xsd">
    <Domain id="any">
        <General>
            <NetworkInterfaceAddress>auto</NetworkInterfaceAddress>
            <EnableMulticastLoopback>true</EnableMulticastLoopback>
        </General>
        <Tracing>
            <Verbosity>warning</Verbosity>
            <OutputFile>stdout</OutputFile>
        </Tracing>
        <Internal>
            <MinimumSocketReceiveBufferSize>2MB</MinimumSocketReceiveBufferSize>
        </Internal>
    </Domain>
</CycloneDDS>
```

Set environment:
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://$HOME/luxopi-ros/cyclonedds.xml
```

### Multi-Machine Setup

1. **On Robot (Pi)**:
```bash
# Set ROS domain
export ROS_DOMAIN_ID=42

# Configure DDS for network
export CYCLONEDDS_URI='<General><NetworkInterfaceAddress>wlan0</NetworkInterfaceAddress></General>'
```

2. **On Remote Machine**:
```bash
# Same domain ID
export ROS_DOMAIN_ID=42

# Discover robot
ros2 daemon stop
ros2 daemon start
ros2 node list
```

3. **Bandwidth optimization**:
```xml
<!-- Reduce discovery traffic -->
<Discovery>
    <ParticipantIndex>auto</ParticipantIndex>
    <MaxAutoParticipantIndex>100</MaxAutoParticipantIndex>
    <PeerAddressingMode>unicast</PeerAddressingMode>
    <Peers>
        <Peer address="192.168.1.100"/>  <!-- Robot IP -->
    </Peers>
</Discovery>
```

## Security Considerations

### ROS2 Security

1. **Enable security**:
```bash
# Generate security artifacts
ros2 security create_keystore ~/luxopi_keystore
ros2 security create_enclave ~/luxopi_keystore /luxopi_enclave

# Set environment
export ROS_SECURITY_KEYSTORE=~/luxopi_keystore
export ROS_SECURITY_ENABLE=true
export ROS_SECURITY_STRATEGY=Enforce
```

2. **Node permissions** (`permissions.xml`):
```xml
<permissions>
  <grant name="/state_manager">
    <publish>ALLOW</publish>
    <subscribe>ALLOW</subscribe>
  </grant>
  <grant name="/camera_interaction">
    <publish>
      <topics>
        <topic>/camera/emotion</topic>
        <topic>/camera/face_count</topic>
      </topics>
    </publish>
  </grant>
</permissions>
```

### Network Security

1. **Firewall rules**:
```bash
# Allow ROS2 DDS
sudo ufw allow 7400:7500/udp  # Discovery
sudo ufw allow 7501:7600/udp  # User traffic

# SSH access
sudo ufw allow from 192.168.1.0/24 to any port 22
```

2. **Service isolation**:
```yaml
# docker-compose.yml for containerized deployment
version: '3.8'
services:
  luxopi:
    image: luxopi-ros:latest
    network_mode: host
    privileged: true
    devices:
      - /dev/ttyAMA0:/dev/ttyAMA0
      - /dev/i2c-1:/dev/i2c-1
      - /dev/fb0:/dev/fb0
    volumes:
      - /dev/bus/usb:/dev/bus/usb
    environment:
      - ROS_DOMAIN_ID=42
```

### Data Privacy

1. **Camera data**: No recording by default
2. **Voice data**: Local processing only
3. **Logs**: Rotate and limit retention:

```bash
# /etc/logrotate.d/luxopi
/home/pi/luxopi-ros/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 pi pi
}
```

## Backup and Recovery

### System Backup

1. **Configuration backup**:
```bash
#!/bin/bash
# backup_config.sh
BACKUP_DIR="/home/pi/luxopi_backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup source code
rsync -av --exclude='build' --exclude='install' --exclude='log' \
  /home/pi/luxopi-ros/ "$BACKUP_DIR/luxopi-ros/"

# Backup configs
cp /boot/firmware/config.txt "$BACKUP_DIR/"
cp ~/.bashrc "$BACKUP_DIR/"
cp -r ~/.ros "$BACKUP_DIR/"

# Create restore script
cat > "$BACKUP_DIR/restore.sh" << 'EOF'
#!/bin/bash
echo "Restoring LuxoPi configuration..."
rsync -av ./luxopi-ros/ /home/pi/luxopi-ros/
cp config.txt /boot/firmware/
cp .bashrc ~/
cp -r .ros ~/
echo "Restore complete. Please reboot."
EOF

chmod +x "$BACKUP_DIR/restore.sh"
echo "Backup saved to $BACKUP_DIR"
```

2. **Full system image**:
```bash
# Create SD card image
sudo dd if=/dev/mmcblk0 of=luxopi_backup.img bs=4M status=progress

# Compress image
gzip -c luxopi_backup.img > luxopi_backup.img.gz
```

### Calibration Data Backup

```python
# Save calibration to JSON
import json

calibration_data = {
    'joint_offsets': {
        'j1': 0.0,
        'j2': -0.05,
        'j3': 0.02,
        'j4': 0.0,
        'j5': 0.0,
        'j6': 0.0
    },
    'sensor_thresholds': {
        'touch_front': 220,
        'touch_back': 215,
        'touch_left': 225,
        'touch_right': 218
    },
    'camera_matrix': camera_matrix.tolist(),
    'distortion_coeffs': dist_coeffs.tolist()
}

with open('calibration_backup.json', 'w') as f:
    json.dump(calibration_data, f, indent=2)
```

### Recovery Procedures

1. **State machine stuck**:
```bash
# Force reset to IDLE
ros2 service call /luxo/request_state_transition \
  luxo_interfaces/srv/RequestStateTransition \
  "{target_state: 'IDLE', priority: 100, force: true}"
```

2. **Serial communication lost**:
```bash
# Reset serial port
sudo systemctl stop luxopi-ros
sudo fuser -k /dev/ttyAMA0
sudo systemctl start luxopi-ros
```

3. **Complete system recovery**:
```bash
# Emergency recovery mode
cd ~/luxopi-ros
./stop_luxopi.sh

# Reset all configs
rm -rf build install log
colcon build --symlink-install
source install/setup.bash

# Test basic functionality
ros2 launch luxo_behaviors luxo_system.launch.py test_mode:=position
```

## Monitoring and Logging

### Log Management

1. **Centralized logging**:
```python
# Configure Python logging
import logging
from rclpy.logging import LoggingSeverity

class LuxoLogger:
    def __init__(self, node_name):
        self.logger = logging.getLogger(node_name)
        
        # File handler
        fh = logging.FileHandler(f'/home/pi/luxopi-ros/logs/{node_name}.log')
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
```

2. **Log analysis tools**:
```bash
# Parse ROS2 logs
#!/bin/bash
# analyze_logs.sh

# Extract errors
grep -E "ERROR|FATAL" ~/.ros/log/latest/*.log > errors.txt

# Count occurrences by node
awk -F']' '{print $2}' errors.txt | sort | uniq -c | sort -rn

# Timeline of events
grep -h "state_transition" ~/.ros/log/latest/*.log | sort -k1,2
```

3. **Real-time monitoring**:
```python
# Monitoring dashboard
import dash
import plotly.graph_objs as go
from dash import dcc, html

class LuxoMonitor:
    def __init__(self):
        self.app = dash.Dash(__name__)
        self.setup_layout()
        
    def setup_layout(self):
        self.app.layout = html.Div([
            html.H1('LuxoPi System Monitor'),
            dcc.Graph(id='cpu-usage'),
            dcc.Graph(id='joint-positions'),
            dcc.Graph(id='sensor-readings'),
            dcc.Interval(id='interval', interval=1000)
        ])
```

### Performance Metrics

1. **System metrics collection**:
```python
class MetricsCollector:
    def __init__(self):
        self.metrics = {
            'cpu_samples': deque(maxlen=300),
            'ram_samples': deque(maxlen=300),
            'topic_latencies': {},
            'node_frequencies': {}
        }
        
    def record_latency(self, topic, latency_ms):
        if topic not in self.metrics['topic_latencies']:
            self.metrics['topic_latencies'][topic] = deque(maxlen=100)
        self.metrics['topic_latencies'][topic].append(latency_ms)
        
    def get_statistics(self):
        stats = {}
        for topic, samples in self.metrics['topic_latencies'].items():
            if samples:
                stats[topic] = {
                    'mean': np.mean(samples),
                    'std': np.std(samples),
                    'max': max(samples),
                    'min': min(samples)
                }
        return stats
```

2. **Prometheus integration**:
```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
state_transitions = Counter('luxo_state_transitions_total', 
                          'Total state transitions',
                          ['from_state', 'to_state'])
                          
animation_duration = Histogram('luxo_animation_duration_seconds',
                             'Animation playback duration',
                             ['animation_name'])
                             
cpu_usage = Gauge('luxo_cpu_usage_percent', 'CPU usage percentage')

# Record metrics
state_transitions.labels(from_state='IDLE', to_state='ANIMATING').inc()
animation_duration.labels(animation_name='wave').observe(2.5)
cpu_usage.set(45.2)

# Start metrics server
start_http_server(8000)
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "LuxoPi Monitoring",
    "panels": [
      {
        "title": "CPU Usage",
        "targets": [
          {
            "expr": "luxo_cpu_usage_percent"
          }
        ]
      },
      {
        "title": "State Transitions",
        "targets": [
          {
            "expr": "rate(luxo_state_transitions_total[5m])"
          }
        ]
      },
      {
        "title": "Animation Performance",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, luxo_animation_duration_seconds)"
          }
        ]
      }
    ]
  }
}
```

## API Examples

### State Management API

```python
# Example: Request state transition with priority
import rclpy
from rclpy.node import Node
from luxo_interfaces.srv import RequestStateTransition

class StateController(Node):
    def __init__(self):
        super().__init__('state_controller')
        self.state_client = self.create_client(
            RequestStateTransition,
            '/luxo/request_state_transition'
        )
        
    async def change_state(self, target_state, priority=5, wait=True):
        request = RequestStateTransition.Request()
        request.target_state = target_state
        request.priority = priority
        request.wait_for_completion = wait
        
        future = self.state_client.call_async(request)
        response = await future
        
        if response.success:
            self.get_logger().info(f"Transitioned to {target_state}")
        else:
            self.get_logger().error(f"Failed: {response.message}")
        
        return response.success

# Usage
controller = StateController()
await controller.change_state('VOICE_FOLLOWING', priority=7)
```

### Animation API

```python
# Example: Play animation with progress tracking
from rclpy.action import ActionClient
from luxo_interfaces.action import PlayAnimation

class AnimationController(Node):
    def __init__(self):
        super().__init__('animation_controller')
        self.animation_client = ActionClient(
            self,
            PlayAnimation,
            '/animation_action'
        )
        
    async def play_animation(self, name, speed=1.0):
        goal = PlayAnimation.Goal()
        goal.animation_name = name
        goal.speed = speed
        
        # Send goal
        future = self.animation_client.send_goal_async(
            goal,
            feedback_callback=self.feedback_callback
        )
        goal_handle = await future
        
        if not goal_handle.accepted:
            self.get_logger().error('Animation rejected')
            return False
            
        # Wait for result
        result_future = goal_handle.get_result_async()
        result = await result_future
        
        return result.result.success
        
    def feedback_callback(self, feedback_msg):
        progress = feedback_msg.feedback.progress
        self.get_logger().info(f"Animation progress: {progress:.1%}")

# Usage
controller = AnimationController()
await controller.play_animation('excited', speed=1.5)
```

### Sensor API

```python
# Example: Monitor collision sensors
class CollisionMonitor(Node):
    def __init__(self):
        super().__init__('collision_monitor')
        
        # Subscribe to all collision topics
        self.collision_subs = {}
        for direction in ['front', 'left', 'right']:
            self.collision_subs[direction] = self.create_subscription(
                CollisionStatus,
                f'/collision/{direction}/status',
                lambda msg, d=direction: self.collision_callback(msg, d),
                10
            )
            
        self.collision_states = {
            'front': 'NONE',
            'left': 'NONE',
            'right': 'NONE'
        }
        
    def collision_callback(self, msg, direction):
        old_state = self.collision_states[direction]
        new_state = msg.severity
        
        if old_state != new_state:
            self.get_logger().warn(
                f"Collision {direction}: {old_state} → {new_state}"
            )
            self.collision_states[direction] = new_state
            
            # React to collisions
            if new_state == 'DANGER':
                self.request_avoidance(direction)
                
    def request_avoidance(self, direction):
        # Request collision avoidance behavior
        pass
```

### Hardware Control API

```python
# Example: Direct hardware control
class HardwareController(Node):
    def __init__(self):
        super().__init__('hardware_controller')
        
        # Publishers
        self.joint_pub = self.create_publisher(
            JointState,
            '/joint_states_target',
            10
        )
        self.cmd_pub = self.create_publisher(
            String,
            '/roarm/direct_command',
            10
        )
        
    def move_to_position(self, x, y, z, speed=2000):
        """Move to Cartesian position"""
        cmd = {
            "T": 1,
            "x": x,
            "y": y,
            "z": z,
            "spd": speed
        }
        msg = String()
        msg.data = json.dumps(cmd)
        self.cmd_pub.publish(msg)
        
    def move_joints(self, joints, speed=1.0):
        """Move joints to specific angles"""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ['j1', 'j2', 'j3', 'j4', 'j5', 'j6']
        msg.position = [
            math.radians(joints.get('j1', 0)),
            math.radians(joints.get('j2', 45)),
            math.radians(joints.get('j3', 90)),
            math.radians(joints.get('j4', 180)),
            math.radians(joints.get('j5', 0)),
            math.radians(joints.get('j6', 90))
        ]
        msg.velocity = [speed] * 6
        self.joint_pub.publish(msg)
        
    def enable_dema(self, enabled=True):
        """Enable/disable dynamic adaptation"""
        cmd = {
            "T": 30,
            "cmd": 1 if enabled else 0
        }
        msg = String()
        msg.data = json.dumps(cmd)
        self.cmd_pub.publish(msg)
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

## System Metrics Reference

### Performance Benchmarks

| Metric | Target | Typical | Warning | Critical |
|--------|--------|---------|---------|----------|
| CPU Usage | <60% | 40-50% | >70% | >85% |
| RAM Usage | <70% | 50-60% | >80% | >90% |
| CPU Temperature | <60°C | 50-55°C | >70°C | >80°C |
| Topic Latency | <10ms | 5-8ms | >20ms | >50ms |
| Animation FPS | 20 | 18-20 | <15 | <10 |
| Sensor Read Rate | 20Hz | 18-20Hz | <15Hz | <10Hz |
| State Transition | <100ms | 50-80ms | >200ms | >500ms |

### Resource Usage by Component

| Component | CPU % | RAM MB | Priority |
|-----------|-------|--------|----------|
| state_manager | 2-5 | 50-60 | Critical |
| hardware_interface | 5-8 | 40-50 | Critical |
| animation_command | 8-12 | 60-80 | High |
| camera_interaction | 15-25 | 150-200 | Medium |
| collision_ros | 3-5 | 30-40 | High |
| voice_direction | 5-10 | 40-60 | Medium |
| behavior_coordinator | 5-8 | 50-70 | High |
| system_monitor | 1-2 | 20-30 | Low |
| framebuffer_display | 2-3 | 30-40 | Low |

### Diagnostic Status Codes

| Code | Level | Description | Action |
|------|-------|-------------|--------|
| 0x0000 | OK | System healthy | None |
| 0x0001 | WARN | High CPU usage | Monitor |
| 0x0002 | WARN | High temperature | Improve cooling |
| 0x0004 | ERROR | State timeout | Check state machine |
| 0x0008 | ERROR | Serial timeout | Check connection |
| 0x0010 | ERROR | Sensor failure | Check I2C |
| 0x0020 | ERROR | Camera failure | Check USB |
| 0x0040 | WARN | Low memory | Restart if needed |
| 0x0080 | ERROR | Watchdog triggered | Investigate logs |

### Topic Publishing Rates

| Topic | Expected Hz | Tolerance |
|-------|-------------|----------|
| /joint_states | 20 | ±2 |
| /luxo/current_state | 10 | ±1 |
| /system/cpu_usage | 1 | ±0.1 |
| /collision/*/status | 10 | ±2 |
| /camera/emotion | 5 | ±1 |
| /voice/direction | 10 | ±2 |
| /diagnostics | 1 | ±0.1 |

## Conclusion

This enhanced CLAUDE.md now provides comprehensive documentation for the LuxoPi ROS2 system, including:

- Complete hardware specifications and pinouts
- Full JSON protocol reference
- Detailed node documentation
- Step-by-step animation creation guide
- Extensive troubleshooting procedures
- Performance optimization techniques
- Integration examples and templates
- Network architecture and security
- Monitoring and logging setup
- Complete API references
- System metrics and benchmarks

The documentation serves as both a technical reference and practical guide for developers working with the LuxoPi system.