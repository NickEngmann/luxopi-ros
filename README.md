# RoArm ROS2 Project

This project contains ROS2 packages for controlling and visualizing the RoArm robot arm with Luxo Jr-style behaviors.

## Overview

The RoArm-LuxoPi system combines hardware control, animation capabilities, and interactive features to create a desk lamp-like robot with personality. The system includes:

- Hardware interface for RoArm-M3 robotic arm
- Luxo Jr-style animation behaviors
- Camera-based emotion detection and interaction
- Collision detection and avoidance
- Dynamic adaptation for physical positioning

![RoArm Luxo System](docs/images/roarm_luxo_overview.jpg)

## Requirements

### Operating System
- Ubuntu 22.04 or Raspberry Pi OS
- ROS2 Humble

### Hardware
- Raspberry Pi (recommended: Pi 4 with 4GB+ RAM)
- RoArm robot arm connected to `/dev/ttyAMA0`
- OAK-D camera (optional for vision features)
- APDS9960 proximity sensor (optional for collision detection)

### Dependencies
- ROS2 Humble base installation
- Python 3.8+
- Required ROS2 packages:
  - `joint_state_publisher`
  - `robot_state_publisher`
  - `rviz2`
  - `xacro`
- Python libraries:
  - `pyserial`
  - `depthai` (for camera features)
  - `numpy`
  - `cv_bridge` (for camera integration)

## Package Structure
- `roarm`: Core robot arm definitions and visualization (URDF, launch files)
- `luxo_behaviors`: Behavior implementation for the arm controller including:
  - Animation system
  - Camera interaction and emotion detection
  - Collision detection and avoidance
  - Hardware interface
  - Demo behaviors
- `serial_ctrl`: Serial communication with the physical arm hardware

## Setup and Installation

### Clone the repository
```bash
cd ~
git clone https://github.com/yourusername/roarm.git luxopi-ros
cd luxopi-ros
```

### Install Dependencies
```bash
sudo apt update
sudo apt install ros-humble-joint-state-publisher ros-humble-robot-state-publisher ros-humble-rviz2 ros-humble-xacro
pip3 install pyserial
```

### For Camera Features (optional)
```bash
# Install DepthAI library and dependencies
pip3 install depthai opencv-python
pip3 install blobconverter numpy
```

### Build the workspace

Build specific packages:
```bash
colcon build --packages-select luxo_behaviors
colcon build --packages-select roarm
colcon build --packages-select serial_ctrl
```

Or build all packages:
```bash
colcon build
```

### Source the setup script
Do this in every new terminal:
```bash
source install/setup.bash
```

## Running the Applications

### Set proper permissions for serial port
```bash
sudo chmod 777 /dev/ttyAMA0
```

### Run the arm controller
Run with default parameters:
```bash
ros2 run luxo_behaviors direct_test
```

Run with custom parameters:
```bash
ros2 run luxo_behaviors direct_test --ros-args -p reading_throttle:=0.5
```

### Launch the robot visualization with RViz
```bash
ros2 launch roarm roarm.launch.py
```

## Running the Full System

The LuxoPi system comes with a comprehensive launch file that integrates all components:

### Hardware Mode
```bash
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true
```

### Simulation Mode
```bash
ros2 launch luxo_behaviors luxo_system.launch.py
```

### Hardware with Camera Features
```bash
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true use_camera:=true
```

### Hardware with Collision Detection
```bash
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true sense_collision:=true
```

### Hardware with Dynamic Adaptation
```bash
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true enable_dynamic_adaptation:=true
```

### Demo Mode
```bash
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true run_demo:=true
```

### Launch Arguments

The `luxo_system.launch.py` accepts the following arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `use_hardware` | `false` | Use physical hardware (true) or simulation (false) |
| `use_camera` | `true` in hardware, `false` in simulation | Enable camera features |
| `enable_emotion_detection` | `true` when camera enabled | Enable emotion detection and reactions |
| `sense_collision` | `true` in hardware, `false` in simulation | Enable APDS9960 proximity sensor |
| `enable_depth_collision` | `false` | Enable depth-based collision detection |
| `run_demo` | `false` | Run demo sequence |
| `use_gui` | `false` | Enable joint_state_publisher_gui |
| `test_mode` | `animation` | Test mode: "position" for position_test or "animation" for animation_command |
| `safety_distance` | `0.3` | Safety distance in meters |
| `verbose` | `false` | Enable verbose output |
| `camera_rotation` | `false` | Rotate camera image 180 degrees |
| `enable_dynamic_adaptation` | `false` | Enable dynamic adaptation mode |

## Autostarting with systemd

You can configure the LuxoPi system to start automatically at boot using systemd.

### Setup Instructions

1. **Copy the systemd service file**:

```bash
sudo cp luxopi-ros.service /etc/systemd/system/luxopi-ros.service
```

2. **Make the startup script executable**:

```bash
chmod +x /home/pi/luxopi-ros/start_luxopi.sh
```

3. **Enable and start the service**:

```bash
sudo systemctl daemon-reload
sudo systemctl enable luxopi-ros.service
sudo systemctl start luxopi-ros.service
```

### Managing the Service

**Check status**:
```bash
sudo systemctl status luxopi-ros.service
```

**View logs**:
```bash
journalctl -u luxopi-ros.service -f
```

**Stop the service**:
```bash
sudo systemctl stop luxopi-ros.service
```

**Restart the service**:
```bash
sudo systemctl restart luxopi-ros.service
```

**Disable autostart**:
```bash
sudo systemctl disable luxopi-ros.service
```

## Animation System

The robot arm supports various pre-defined animation sequences that bring the Luxo character to life. These animations are implemented using Disney animation principles for more natural movement.

### Available Animations

| Animation | Description |
|-----------|-------------|
| `curious` | Make the arm look around with curiosity |
| `excited` | Make the arm perform an enthusiastic hop |
| `sad` | Make the arm droop sadly |
| `playful` | Make the arm do playful bounces |
| `dance` | Make the arm perform a rhythmic dance sequence |
| `think` | Make the arm appear to ponder a question |
| `idle` | Return to idle state with subtle movements |
| `stretch` | Make the arm perform a satisfying stretch |
| `nod` | Make the arm nod yes |
| `shake` | Make the arm shake no |
| `startled` | Make the arm perform a startled jump |
| `stop` | Stop any currently running animation |

### Triggering Animations via Command Line

You can trigger animations by publishing messages to the `/roarm/animation_command` topic:

```bash
# Basic animation command
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: curious"

# Animation with speed control (0.5 = half speed, 2.0 = double speed)
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: excited 1.5"
```

### Animation Architecture

The animation system uses keyframe interpolation with easing functions to create smooth, natural movements. Features include:

- Squash and stretch effects
- Anticipation and follow-through
- Secondary actions and overlapping motion
- Ease-in and ease-out timing
- Random subtle variations to prevent mechanical appearance

### Using in Code

To trigger animations programmatically:
```python
from std_msgs.msg import String
# Create publisher
animation_publisher = node.create_publisher(String, '/roarm/animation_command', 10)
# Send animation command
msg = String()
msg.data = "curious"
animation_publisher.publish(msg)
```

## Camera Interaction System

The camera interaction system detects human emotions and triggers corresponding animations, creating an interactive experience.

### Features

- Real-time face detection
- Emotion recognition (happy, sad, surprised, angry, neutral)
- Distance detection (with OAK-D camera)
- Automatic animation responses to emotions

### Running with Camera Only

```bash
ros2 run luxo_behaviors camera_interaction
```

### Emotion to Animation Mapping

| Detected Emotion | Possible Animations |
|------------------|---------------------|
| Happy | excited, playful, dance |
| Sad | sad, droop |
| Surprised | startled, curious |
| Angry | shake, think, startled |
| Neutral | idle, curious, stretch, nod |

### Camera Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/camera/emotion` | `std_msgs/String` | Current detected emotion |
| `/camera/person_distance` | `std_msgs/Float32` | Distance to person in meters |
| `/camera/image_raw` | `sensor_msgs/Image` | Camera image (if enabled) |

## Collision Detection and Avoidance

The system includes sophisticated collision detection and avoidance capabilities to prevent damage to the robot and its surroundings.

### Collision Sources

1. **APDS9960 Proximity Sensor** - Front-facing proximity detection
2. **OAK-D Depth Camera** - Multi-directional collision detection using depth data

### Collision Response Behaviors

The robot will:
1. Slow down when approaching obstacles
2. Stop before collision
3. Generate alternative motion paths
4. Retreat from persistent obstacles
5. Execute escape maneuvers when necessary

### Collision Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/head_collision_warning` | `std_msgs/Bool` | Front collision warning |
| `/left_collision_warning` | `std_msgs/Bool` | Left side collision warning |
| `/right_collision_warning` | `std_msgs/Bool` | Right side collision warning |
| `/proximity` | `std_msgs/Float32` | Raw proximity sensor value |
| `/front_collision_severity` | `std_msgs/String` | Collision severity (safe, warning, danger) |

### Running with Point Cloud Collision Detection

```bash
# First terminal: Launch the camera
ros2 launch depthai_ros_driver pointcloud.launch.py params_file:=./luxopijr.yaml

# Second terminal: Launch robot with collision detection
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true enable_depth_collision:=true
```

## Dynamic Adaptation Mode

Dynamic Adaptation allows the robot arm to respond to external forces by reducing servo torque limits. This feature makes the arm more compliant, allowing it to be physically moved and positioned by hand.

### Enabling Dynamic Adaptation

Enable via launch:
```bash
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true enable_dynamic_adaptation:=true
```

Enable via topic:
```bash
ros2 topic pub --once /dynamic_adaptation_toggle std_msgs/msg/Bool "data: true"
```

Disable via topic:
```bash
ros2 topic pub --once /dynamic_adaptation_toggle std_msgs/msg/Bool "data: false"
```

### How Dynamic Adaptation Works

1. When enabled, the system reduces servo torque limits to make the arm compliant
2. The arm can be physically positioned by hand
3. The system continues to track the arm's position
4. The adaptation mode automatically times out after 10 seconds (configurable)
5. After timeout, the arm resumes normal operation with the new position

### Use Cases

- Physical teaching of positions
- Manual adjustments to fine-tune positioning
- Interactive demonstrations
- Recovery from collisions or stuck positions

## Demo Mode

The system includes a demo mode that will showcase the arm's animations and capabilities automatically.

```bash
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true run_demo:=true
```

The demo will cycle through various behaviors including:
- Curious investigation
- Excited movements
- Sad drooping
- Playful interactions
- Stretching and dancing

## Running Tests

Run tests for a specific package:
```bash
colcon test --packages-select luxo_behaviors
colcon test --packages-select roarm
colcon test --packages-select serial_ctrl
```

View test results:
```bash
colcon test-result --all --verbose
```

## Working with the Robot Arm
See the `ROBOT_ARM_API.md` file for details about the robot arm API and command reference.

## Calibration
The arm requires calibration before first use:
```bash
ros2 run serial_ctrl calibrate_arm
```

## Development Workflow

### Building After Changes

After making changes to the source code:
```bash
colcon build --packages-select luxo_behaviors
source install/setup.bash
```

### Adding New Animations

1. Edit `/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_command.py`
2. Add a new method for your animation
3. Register the animation in the `command_callback` method
4. Build and test:
   ```bash
   colcon build --packages-select luxo_behaviors
   source install/setup.bash
   ros2 launch luxo_behaviors luxo_system.launch.py
   ```
5. Trigger your new animation:
   ```bash
   ros2 topic pub --once /roarm/animation_command std_msgs/String "data: your_new_animation"
   ```

### Monitoring Node Performance

```bash
# List all running nodes
ros2 node list

# Get information about a specific node
ros2 node info /animation_command

# List all topics
ros2 topic list

# Monitor a specific topic
ros2 topic echo /roarm/animation_command
```

## Troubleshooting

### Serial Port Issues
If you encounter errors related to permissions:
```bash
sudo chmod 777 /dev/ttyAMA0
```

If the device is not found at `/dev/ttyAMA0`, check your connections and run:
```bash
ls -l /dev/tty*
```

### Animation Jitter Issues
If there is jitter in animations, it may be due to conflicting publishers:
```bash
pkill -f animation_command
pkill -f robot_state_publisher
```

### Camera Connection Issues

For OAK-D camera connection errors:
```bash
# Check if camera is detected
lsusb | grep Luxonis

# Reset the USB connection
sudo usbreset 03e7:f63b
```

For camera permission issues:
```bash
sudo usermod -aG plugdev $USER
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### RViz Visualization Issues
- Check that the URDF file path is correct in the launch file
- Verify the `rviz_basic_settings.rviz` file is properly configured
- If you see missing meshes, ensure the mesh paths in the URDF files are correct

### Common Error Messages
- "Failed to connect to serial port": Check if your arm is properly connected
- "Joint limits exceeded": Ensure the commanded positions are within the range defined in the URDF
- "No depth camera found": Check camera connections and permissions

### Resetting the System

To completely reset the system:
```bash
# Close all ROS nodes
pkill -f ros

# Restart the robot
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true
```

## Using with WSL2

For development on Windows with WSL2:

```bash
# Connect the main Luxonis bootloader
usbipd attach --wsl Ubuntu-22.04 --hardware-id "03e7:f63c" --auto-attach

# Connect the actual Luxonis camera
usbipd attach --wsl Ubuntu-22.04 --hardware-id "03e7:f63b" --auto-attach
```

## Contributing
Please read `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## License
This project is licensed under the MIT License - see the `LICENSE` file for details.