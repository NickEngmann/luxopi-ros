# RoArm ROS2 Project

This project contains ROS2 packages for controlling and visualizing the RoArm robot arm.

## Requirements

### Operating System
- Ubuntu 22.04 or Raspberry Pi OS
- ROS2 Humble

### Hardware
- Raspberry Pi (recommended: Pi 4 with 4GB+ RAM)
- RoArm robot arm connected to `/dev/ttyAMA0`

### Dependencies
- ROS2 Humble base installation
- Python 3.8+
- Required ROS2 packages:
  - `joint_state_publisher`
  - `robot_state_publisher`
  - `rviz2`
  - `xacro`

## Package Structure
- `roarm`: Core robot arm definitions and visualization (URDF, launch files)
- `luxo_behaviors`: Behavior implementation for the arm controller
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

## Animation Commands

The robot arm supports various pre-defined animation sequences. You can trigger these animations by publishing String messages to the `/roarm/animation_command` topic:

```bash
# Available animation commands:
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: curious"   # Make the arm look around curiously
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: excited"   # Make the arm perform an excited hop
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: sad"       # Make the arm droop sadly
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: sweep"     # Make the arm sweep like a desk lamp searching
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: playful"   # Make the arm do playful bounces
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: startled"  # Make the arm perform a startled jump
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: grab"      # Make the arm grab and release with gripper
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: stop"      # Stop any currently running animation
```

You can launch the animation command node with different modes:
```bash
# Launch hardware system with animation mode
ros2 launch luxo_behaviors hardware_system.launch.py test_mode:=animation
```

## Calibration
The arm requires calibration before first use:
```bash
ros2 run serial_ctrl calibrate_arm
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

### Build Issues
If you need to rebuild after changes:
```bash
colcon build --packages-select <package_name>
source install/setup.bash
```

### RViz Visualization Issues
- Check that the URDF file path is correct in the launch file
- Verify the `rviz_basic_settings.rviz` file is properly configured
- If you see missing meshes, ensure the mesh paths in the URDF files are correct

### Common Error Messages
- "Failed to connect to serial port": Check if your arm is properly connected
- "Joint limits exceeded": Ensure the commanded positions are within the range defined in the URDF

## Contributing
Please read `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## License
This project is licensed under the MIT License - see the `LICENSE` file for details.


## Running with Collision Detection Enabled

Step-by-Step Instructions

```
cd ~/luxopi-ros
colcon build --packages-select luxo_behaviors
source install/setup.bash
```

First terminal: Launch the DepthAI camera with point cloud

`ros2 launch depthai_ros_driver pointcloud.launch.py params_file:=./luxopijr.yaml`

Second terminal: Wait until the camera is fully initialized, then launch your robot control system
`ros2 launch luxo_behaviors hardware_system.launch.py test_mode:=animation enable_collision:=True`

Third terminal: To send animation commands

`ros2 topic pub /roarm/animation_command std_msgs/msg/String "data: 'curious'" --once`

To monitor collision status:
`ros2 topic echo /collision_status`

```bash
colcon build
ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=false verbose:=true use_joint_state_publisher:=false (you can also include run_demo:=true)
```

Sometimes I ran into problems where the there is jitter in the overall animations, and it seems to be happening because there are other publishers that haven't been properly closed
```bash
pkill -f animation_command
pkill -f robot_state_publisher
```

## Dynamic Adaption External Control

```bash
# enable at startup
ros2 run luxo_behaviors hardware_interface --ros-args -p enable_dynamic_adaptation:=true
# Toggle at runtime:
ros2 service call /toggle_dynamic_adaptation std_srvs/srv/SetBool "{data: true}"  # Enable
ros2 service call /toggle_dynamic_adaptation std_srvs/srv/SetBool "{data: false}"  # Disable

# Adjust torque limits:
ros2 run luxo_behaviors hardware_interface --ros-args -p enable_dynamic_adaptation:=true \
  -p dynamic_adaptation_base_limit:=80 -p dynamic_adaptation_shoulder_limit:=120
```