# MARISOL.md — Pipeline Context

## Project Overview
This is a ROS2-based control system for the RoArm-M3 robotic arm featuring Luxo Jr-style animation, vision processing with DepthAI cameras, and customtkinter GUI. The project uses ROS2 Humble distribution with colcon build system and Python dependencies for depthai, opencv, and customtkinter.

## Build & Run
- **Language**: Python 3.x, C++ (ROS2 packages)
- **Framework**: ROS2 Humble, colcon
- **Docker image**: python:3.12-slim (base), ros:humble-ros-base (ROS2)
- **Install deps**: 
  1. `pip install -r requirements.txt` (Python dependencies)
  2. `cd /workspace/repo/roarm_ws_em1 && colcon build --packages-select luxo_behaviors` (ROS2 package build)
- **Run**: 
  - `ros2 launch luxo_behaviors <launch_file>.py` (launch files in luxo_behaviors/launch/)
  - Note: colcon build does not accept launch file arguments; use ros2 launch for execution

## Testing
- **Test framework**: pytest (Python), colcon test (ROS2 C++/Python)
- **Test command**: 
  - `pytest` (Python tests in tests/ directory)
  - `colcon test --packages-select luxo_behaviors` (ROS2 package tests)
- **Hardware mocks needed**: yes (DepthAI camera, robotic arm hardware)
- **Known test issues**: Hardware-dependent tests require mock implementations for CI

## Pipeline History
- No automated pipeline history available in current repository state
- Manual testing required for hardware integration

## Known Issues
- ROS2 launch command syntax error in previous documentation (colcon build does not accept .py launch files)
- Hardware dependencies require mocking for automated testing
- DepthAI SDK version compatibility (2.30.0)

## Notes
- Workspace structure: /workspace/repo/roarm_ws_em1/src/ contains ROS2 packages
- Launch files located in luxo_behaviors/launch/ directory
- Customtkinter GUI for visualization and control
- Uses DepthAI for vision processing and collision avoidance
- ROS2 Humble distribution required
- Python dependencies in requirements.txt include depthai, customtkinter, opencv-python
