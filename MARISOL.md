# MARISOL.md — Pipeline Context for luxopi-ros

## Project Overview
LuxoPi is a ROS2-based control system for the RoArm-M3 robotic arm featuring Luxo Jr-style animated behaviors, vision processing with depthAI cameras, and serial communication for motor control. The project combines Python logic with ROS2 nodes for real-time robotic operation.

## Build & Run
- **Language**: Python 3.11/3.12
- **Framework**: ROS2 (Humble)
- **Docker image**: python:3.12-slim
- **Install deps**:
  - Python: pip install -r requirements.txt
  - ROS2: source /opt/ros/humble/setup.bash && rosdep install --from-paths src --ignore-src -r -y
- **Run**:
  - Build: cd roarm_ws_em1 && colcon build
  - Source: source install/setup.bash
  - Launch: ros2 launch luxo_behaviors launch/luxo_behaviors.launch.py

## Testing
- **Test framework**: pytest (Python tests), ament (ROS2 linters)
- **Test command**:
  - Python: pytest tests/ -v
  - ROS2: cd roarm_ws_em1 && colcon test --test-result-tests
- **Hardware mocks needed**: yes
  - ROS2 nodes (simulated with launch files)
  - depthai camera (mocked with test data)
  - serial port (mocked with serialio)
- **Known test issues**: None identified

## Pipeline History
- 2024-03-15: Initial project setup with ROS2 Humble and Python 3.11
- 2024-04-20: Added depthAI camera integration for vision processing
- 2024-05-10: Implemented serial communication mocking for unit tests
- 2024-06-05: Added pytest test suite for pure logic components
- 2024-07-18: Integrated customtkinter for GUI controls
- 2024-08-22: Updated depthai SDK to version 1.15.1
- 2024-09-30: Added collision detection behavior logic
- 2024-10-15: Implemented Luxo Jr-style animated behaviors
- 2024-11-20: Added serialio library for serial port mocking
- 2024-12-05: Updated requirements.txt with dependency versions

## Known Issues
- No known issues at this time

## Notes
- Project structure: Python logic in src/ directory, ROS2 tests in src/*/test/
- Serial communication mocked using serialio library for unit testing
- DepthAI camera data mocked with test fixtures for vision processing tests
- Pure logic functions extracted from ROS2 nodes for unit testing
- Test fixtures in tests/conftest.py provide common mocking utilities
- CMakeLists.txt files in src/ and roarm_ws_em1/src/ for ROS2 build system
