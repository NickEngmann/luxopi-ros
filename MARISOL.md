# MARISOL.md — Pipeline Context

---

## Project Overview
LuxoPi ROS2 Project - A ROS2-based control system for the RoArm-M3 robotic arm with Luxo Jr-style animated behavior.

## Build & Run
- **Language**: Python 3.8+
- **Framework**: ROS2 (Jazzy/Foxy), ament_python
- **Docker image**: ros:jazzy-ros-base
- **Install deps**: `rosdep install --from-paths src --ignore-src -r -y`
- **Run**: `colcon build && source install/setup.bash && ros2 launch ...`

## Testing
- **Test framework**: pytest (functional tests), ament_copyright, ament_flake8, ament_pep257 (code style)
- **Test command**: `colcon test` or `python3 -m pytest src/luxo_behaviors/test/`
- **Hardware mocks needed**: No (software testing only)
- **Known test issues**: Serial port permissions may need adjustment

## Pipeline History
- 2024-01-15: Initial project setup with ROS2 Jazzy
- 2024-01-20: Added ament_python build type configuration
- 2024-02-01: Implemented pytest functional tests with mocking
- 2024-02-10: Fixed serial port permission documentation
- 2024-02-15: Updated README with complete installation instructions

## Known Issues
- Serial port access requires user to be in dialout group
- Some tests may fail without hardware connection (mocks available)

## Notes
- Uses ament_python build type for ROS2 packages
- Test dependencies: ament_copyright, ament_flake8, ament_pep257, python3-pytest
- No pytest runs ament tests - ament uses colcon/ament_lint separately
- Hardware mocks available for serial port testing
