# LuxoPi ROS2 Project

![Tests](https://github.com/NickEngmann/luxopi-ros/actions/workflows/test.yml/badge.svg)

A ROS2-based control system for the RoArm-M3 robotic arm with Luxo Jr-style animated behavior, vision processing, and collision avoidance.

## Overview

This project provides:
- Serial communication control for RoArm-M3 robotic arm
- Luxo Jr-style animated behaviors and expressions
- Vision processing for object detection
- Collision avoidance system
- ROS2 interface definitions for custom messages

## Requirements

- **OS**: Ubuntu 22.04 or 24.04
- **ROS2**: Jazzy Jalisco (recommended) or Humble Hawksbill
- **Python**: 3.10+
- **Hardware**: RoArm-M3 robotic arm with serial connection

## Installation

### 1. Clone the repository

```bash
cd ~/ros2_ws/src
git clone https://github.com/NickEngmann/luxopi-ros.git
```

### 2. Install dependencies

```bash
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
pip install -r src/luxopi-ros/requirements.txt
```

### 3. Build the workspace

```bash
colcon build --packages-select roarm serial_ctrl luxo_interfaces
```

### 4. Source the workspace

```bash
source install/setup.bash
```

## Quick Start

### Launch the main system

```bash
ros2 launch roarm main.launch.py
```

### Run serial controller node

```bash
ros2 run serial_ctrl serial_ctrl
```

### Test vision processing

```bash
ros2 run roarm vision_node
```

## Launch Options

### Main launch file options

- `--use-simulation` - Run in simulation mode without hardware
- `--vision-enabled` - Enable vision processing node
- `--collision-avoidance` - Enable collision avoidance system
- `--debug` - Enable debug logging

### Serial controller options

- `--port /dev/ttyUSB0` - Specify serial port (default: /dev/ttyUSB0)
- `--baudrate 115200` - Set baud rate (default: 115200)
- `--timeout 1.0` - Set communication timeout in seconds

## Set Permissions

```bash
sudo chmod -R 777 /dev/ttyUSB0
```

Ensure the user has permission to access the serial port. On Ubuntu, you may need to add your user to the dialout group:

```bash
sudo usermod -aG dialout $USER
```

Log out and back in for changes to take effect.

## Project Structure

```
roarm_ws_em1/
├── src/
│   ├── serial_ctrl/          # Serial communication node
│   ├── roarm/                # Main control logic
│   └── luxo_interfaces/     # Custom ROS2 interfaces
├── build/
├── devel/
└── install/
```

## Running Tests

```bash
cd roarm_ws_em1
source install/setup.bash
pytest tests/ -v
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for our code of conduct and submission process.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.
