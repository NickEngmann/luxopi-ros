# LuxoPi ROS2 Project

A ROS2-based control system for the RoArm-M3 robotic arm with Luxo Jr-style animated behaviors, vision processing using DepthAI cameras, and serial communication for arm control.

## Overview

This project provides:
- ROS2 packages for RoArm-M3 robotic arm control
- Luxo Jr-style animation behaviors
- Vision processing with DepthAI cameras
- Collision detection and watchdog systems
- Custom action interfaces for behavior control

## Prerequisites

- **ROS2**: Humble Hawksbill (Ubuntu 22.04)
- **Python**: 3.10+
- **Hardware**: RoArm-M3 robotic arm, DepthAI camera (optional)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/NickEngmann/luxopi-ros.git
```

### 2. Setup ROS2 Environment

```bash
# Source ROS2 setup
source /opt/ros/humble/setup.bash

# Add to your ~/.bashrc for persistence
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

### 3. Install Dependencies

```bash
cd luxopi-ros
pip install -r requirements.txt
```

### 4. Build ROS2 Packages

```bash
# Navigate to workspace
cd roarm_ws_em1

# Build all packages
colcon build --packages-select luxo_behaviors luxo_interfaces

# Source the workspace
source install/setup.bash
```

### 5. Set Permissions

```bash
# Grant necessary permissions for serial access
sudo usermod -aG dialout $USER

# Grant permissions for camera access
sudo chmod 666 /dev/bus/usb/*
```

## Quick Start

### Launch the System

```bash
# Source the workspace
source install/setup.bash

# Run the main behavior node
ros2 run luxo_behaviors behavior_node
```

### Available Actions

- **animation_action_client**: Launch Luxo Jr-style animations
- **collision_detection**: Enable collision avoidance
- **watchdog**: Monitor system health

## Usage Examples

### Run Animations

```bash
ros2 action send_goal /luxo_animation luxo_interfaces/action/LuxoAnimation "{command: 'wave', duration: 2.0}"
```

### Vision Processing

```bash
ros2 run luxo_behaviors vision_node
```

### Serial Communication

```bash
ros2 run luxo_behaviors serial_controller
```

## Testing

```bash
# Run pytest tests
pytest

# Run ROS2 tests
colcon test --packages-select luxo_behaviors luxo_interfaces
```

## Project Structure

```
luxopi-ros/
├── roarm_ws_em1/          # ROS2 workspace
│   ├── src/
│   │   ├── luxo_behaviors/ # Main behavior nodes
│   │   └── luxo_interfaces/ # Custom action/message definitions
│   └── install/           # Built packages
├── requirements.txt       # Python dependencies
└── README.md
```

## Dependencies

- **ROS2**: Humble Hawksbill
- **Python**: 3.10+
- **depthai**: 2.30.0 (vision processing)
- **pyserial**: 3.5 (serial communication)
- **customtkinter**: 5.2.0 (GUI)

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for our code of conduct and submission process.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Running Tests

```bash
pytest
```

## Known Issues

- Requires ROS2 Humble environment (not compatible with Foxy or Jazzy)
- Serial communication requires proper permissions (dialout group)
- DepthAI camera requires USB 3.0 connection for optimal performance

## Support

For issues and questions, please open an issue on GitHub or contact the maintainers.
