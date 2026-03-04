# MARISOL.md — Pipeline Context

## Project Overview
This is a ROS2-based control system for the RoArm-M3 robotic arm featuring Luxo Jr-style animations, vision processing, and collision avoidance. The project uses ament_python build system with two main packages: serial_ctrl (serial communication) and roarm (main control logic). It requires ROS2 Jazzy distribution and Python 3.10+.

## Build & Run
- **Language**: Python 3.10+
- **Framework**: ROS2 (ament_python)
- **Docker image**: ros:jazzy-ros-base
- **Install deps**: cd /workspace/repo/roarm_ws_em1 && source /opt/ros/jazzy/setup.bash && pip install -r requirements.txt
- **Run**: No runnable entry point — this is a ROS2 package that requires source setup. Launch with: source install/setup.bash && ros2 launch roarm main.launch.py

## Testing
- **Test framework**: pytest
- **Test command**: cd /workspace/repo/roarm_ws_em1 && source install/setup.bash && python -m pytest tests/ -v
- **Hardware mocks needed**: yes — serial communication requires mocked serial port access
- **Known test issues**: Serial port access requires root privileges or dialout group membership. Tests may fail in containerized environments without proper device passthrough.

## Pipeline History
- 2024-01-15: Initial pipeline setup with ROS2 Jazzy
- 2024-01-20: Added pytest integration for serial_ctrl tests
- 2024-02-01: Updated to use ament_lint_common for code quality checks

## Known Issues
- Serial port permissions require user to be in dialout group
- Hardware-dependent tests cannot run in standard CI without device passthrough
- Some tests require mocked serial interfaces for reliable execution

## Notes
- Workspace location: /workspace/repo/roarm_ws_em1/
- Main entry points defined in setup.py entry_points section
- Requires ROS2 Jazzy environment setup
- Hardware interface node communicates with RoArm-M3 via serial/I2C
- Uses xacro for URDF generation
- Package structure: serial_ctrl (serial communication), roarm (main control), luxo_interfaces (interface definitions)
