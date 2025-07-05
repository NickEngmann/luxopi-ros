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
- **Audio**: Voice command recognition and direction detection

## Core Architecture Principles

1. **Centralized State Management**: `state_manager.py` coordinates all behaviors through a priority-based state machine
2. **Modular Behaviors**: Each behavior (collision, voice, emotion, etc.) is a separate node communicating via ROS2
3. **Hardware Abstraction**: `hardware_interface.py` provides thread-safe robot control with DEMA support
4. **Safety First**: Multi-layer collision detection with graceful degradation
5. **Animation System**: Disney-principles based with frame interpolation and priority handling

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

## Voice Commands (DFRobot)

### Light Control
- "Turn on/off the light", "Dim/Brighten the light", "Adjust brightness to min/max"

### Sleep/Wake
- Wake: "Start oscillating", "Daylight mode", "Color mode"
- Sleep: "Stop oscillating", "Reset", "Stop playing", "Moonlight mode"

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

## Common Issues and Solutions

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
- `state_manager.py`: Central coordinator, state machine
- `hardware_interface.py`: Robot control, safety limits
- `animation_command.py`: Animation engine, interpolation
- `command_behavior.py`: Voice commands, behavior mapping
- `collision_ros_node.py`: Collision logic, escape strategies
- `camera_interaction.py`: Vision, emotion detection
- `voice_direction_node.py`: Voice tracking with motor awareness
- `idle_behavior.py`: Autonomous behavior system
- `i2c_device_manager.py`: Sensor management

## Voice Direction System Details

The voice direction system (`voice_direction_node.py`) includes:
- **Motor awareness**: Compensates for motor noise during movement
- **Parallax correction**: Adjusts for microphone array position (10cm behind, 15cm up)
- **Direction mapping**: Front=-30°, Right=-120°, Back=150°, Left=60°
- **Smooth tracking**: Configurable speed and deadzone
- **Face visibility optimization**: Varies neck position for better detection

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
```

System uses ROS2 Jazzy on Ubuntu 24.04. Python packages require `--break-system-packages` flag.