# MARISOL.md — Pipeline Context

## Project Overview
LuxoPi is a ROS2-based control system for the RoArm-M3 robotic arm featuring Luxo Jr-style animated behaviors, vision processing with depthai cameras, and serial communication for motor control. Built with Python 3.11/3.12 and ROS2 Humble, it provides a modular architecture for robotic behavior development.

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

### 2024-01-25
- Initial pipeline setup for ROS2-based robotic arm control system
- Basic test infrastructure configured with pytest and ament linters
- All 5 tests pass: copyright, flake8, pep257, mypy, and unit tests

### 2024-02-15
- Added hardware mock support for depthai camera and serial port testing
- Updated test documentation to reflect ROS2 package structure

## Known Issues
- No known issues at this time

## Notes
- CustomTkinter used for GUI components (not tested in unit tests)
- Hardware dependencies: depthai camera, serial port for motor control
- ROS2 packages: luxo_behaviors, luxo_interfaces, serial_ctrl
- Test structure: Python tests in tests/ directory, ROS2 tests in src/*/test/
- Serial communication mocked using serialio library for unit testing
- DepthAI camera data mocked with test fixtures for vision processing tests
