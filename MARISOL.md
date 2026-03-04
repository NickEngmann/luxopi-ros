# MARISOL.md — Pipeline Context

## Project Overview
This is a ROS2-based control system for the RoArm-M3 robotic arm featuring Luxo Jr-style animations, vision processing using DepthAI cameras, and serial communication for arm control. The project uses Python 3.10+ with ROS2 Humble Hawksbill distribution, custom action interfaces, and requires colcon for building ROS2 packages.

## Build & Run
- **Language**: Python 3.10+, C++ (for ROS2 packages)
- **Framework**: ROS2 Humble Hawksbill, colcon build system
- **Docker image**: ros:humble-ros-base (or python:3.12-slim with ROS2 installed)
- **Install deps**: `pip install -r requirements.txt` and `colcon build --packages-select luxo_behaviors luxo_interfaces`
- **Run**: `ros2 run luxo_behaviors behavior_node` (requires ROS2 workspace sourced)

## Testing
- **Test framework**: pytest (Python), ament_cmake (ROS2 packages)
- **Test command**: `pytest` for Python tests, `colcon test --packages-select luxo_behaviors luxo_interfaces` for ROS2 tests
- **Hardware mocks needed**: yes - serial port (RoArm-M3), DepthAI camera device
- **Known test issues**: Tests require actual hardware or proper mocks for serial communication and camera devices

## Pipeline History
- Initial setup: ROS2 Humble environment configured
- Dependencies installed: depthai, pyserial, customtkinter, opencv-python
- Build verified: colcon build successful for luxo_behaviors and luxo_interfaces packages
- Tests passing: pytest tests execute successfully with hardware mocks

## Known Issues
- ROS2 version must be Humble (not Foxy or Jazzy)
- Serial communication requires dialout group permissions
- DepthAI camera requires USB 3.0 connection
- Tests may fail without proper hardware mocks

## Notes
- Main entry points: collision_detection, animation_action_client, watchdog
- ROS2 packages use ament_python and ament_cmake build systems
- Package structure: roarm_ws_em1/src/luxo_behaviors, roarm_ws_em1/src/luxo_interfaces
- Custom action interfaces defined in luxo_interfaces package
- Vision processing uses depthai SDK 2.30.0
- Serial communication uses pyserial 3.5
