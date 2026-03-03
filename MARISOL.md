# MARISOL.md — Pipeline Context

## Project Overview
This is a ROS2-based control system for the RoArm-M3 robotic arm featuring Luxo Jr-style animation, vision processing with DepthAI, and collision avoidance. The project consists of multiple ROS2 packages (serial_ctrl, roarm, luxo_behaviors) that interface with the physical robot arm through serial communication, process camera feeds for vision tasks, and execute animated behaviors.

## Build & Run
- **Language**: Python 3.x, C++ (ROS2 packages)
- **Framework**: ROS2 Humble/Jazzy, rclpy
- **Docker image**: ros:humble-ros-base
- **Install deps**: 
  - `source /opt/ros/humble/setup.bash` (or `/opt/ros/jazzy/setup.bash` for Jazzy)
  - `pip install -r requirements.txt`
  - `pip install pytest`
  - `sudo apt install python3-pip python3-venv git`
- **Run**: `colcon build --symlink-install` then `source install/setup.bash` and run individual nodes (e.g., `ros2 run serial_ctrl serial_ctrl_py`)

## Testing
- **Test framework**: pytest, flake8, pep257 (Python pep257 style)
- **Test command**: `pytest tests/ -v` for unit tests, `colcon test` for ROS2 package tests
- **Hardware mocks needed**: yes — serial communication, ROS2 rclpy, sensor_msgs, std_msgs, depthai SDK, and hardware interfaces are mocked in tests
- **Known test issues**: Tests mock all external dependencies (ROS2, serial, depthai) to enable unit testing of pure logic components without hardware

## Pipeline History
- Initial project setup with ROS2 workspace structure (supports both Humble and Jazzy)
- Dependencies installed: depthai-sdk, depthai, pyserial, opencv-python, customtkinter, smbus
- Test suite created for serial_ctrl_py logic with mocked dependencies
- Build verified with colcon build --symlink-install
- INSTALL.sh provides complete setup script for Ubuntu 24.04 with Tailscale support

## Known Issues
- Hardware-dependent tests require mocked serial/ROS2 interfaces
- Vision processing requires DepthAI camera hardware for full testing
- Some packages depend on physical robot arm for integration testing
- Requires ROS2 environment setup (source /opt/ros/<distro>/setup.bash)

## Notes
- Project structure: ROS2 workspace with serial_ctrl, roarm, and luxo_behaviors packages
- Pure logic tests extract and test functions independently of ROS2 dependencies
- Requirements include depthai SDK for vision, pyserial for robot communication, customtkinter for UI
- Tests use conftest.py for shared fixtures and mocking strategies
- INSTALL.sh provides complete setup including X11 forwarding, Tailscale, and ROS2 GUI tools
- Uses ROS_DOMAIN_ID=42 for multi-machine ROS2 communication over Tailscale
