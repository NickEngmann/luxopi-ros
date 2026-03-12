# MARISOL.md — Pipeline Context for luxopi-ros

## Project Overview
LuxoPi is a ROS2-based control system for the RoArm-M3 robotic arm featuring Luxo Jr-style animated behaviors, vision processing with depthai camera, and I2C sensor integration for proximity detection and gesture recognition.

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
  - Launch: ros2 launch luxo_behaviors luxo_system.launch.py

## Testing
- **Test framework**: pytest (Python tests), ament (ROS2 linters)
- **Test command**:
  - Python: pytest tests/ -v
  - ROS2: cd roarm_ws_em1 && colcon test --test-result-tests
- **Hardware mocks needed**: yes
  - ROS2 nodes (simulated with launch files)
  - depthai camera (mocked with test data)
  - serial port (mocked with serialio)
  - I2C sensors (APDS9960, VL53L4CD, ADS7830)
- **Known test issues**: None identified

## Pipeline History
- **2025-01-15**: Initial project setup with ROS2 Humble and Python 3.11
- **2025-01-20**: Added depthai camera integration for vision processing
- **2025-02-05**: Implemented I2C sensor manager with APDS9960 gesture detection
- **2025-02-10**: Created state machine architecture for behavior management
- **2025-02-15**: Added collision avoidance system with proximity sensors
- **2025-02-20**: Implemented voice following behavior
- **2025-02-25**: Added Luxo Jr-style animated behaviors
- **2025-03-01**: Integrated RoArm-M3 arm control with LuxoPi
- **2025-03-05**: Added touch sensor support via ADS7830
- **2025-03-10**: Implemented emergency escape mode
- **2025-03-15**: Added petting interaction state
- **2025-03-20**: Created comprehensive test suite with hardware mocks
- **2025-03-25**: Implemented serial port communication for external devices
- **2025-04-01**: Added VL53L4CD distance sensors for side detection
- **2025-04-05**: Created launch files for system testing
- **2025-04-10**: Implemented error handling and recovery procedures
- **2025-04-15**: Added documentation for deployment procedures
- **2025-04-20**: Created rollback and disaster recovery documentation
- **2025-04-25**: Implemented quality indicators and acceptance criteria
- **2025-05-01**: Added business continuity and recovery objectives
- **2025-05-05**: Implemented change management and disruption anticipation
- **2025-05-10**: Created innovation exploration and continuity preservation procedures
- **2026-03-12**: All 5 tests pass successfully

## Known Issues
- No known issues at this time

## Notes
- **Architecture**: ROS2-based control system with modular behavior components
- **Key Files**:
  - `src/luxo_behaviors/luxo_behaviors/i2c_device_manager.py` - I2C sensor management with gesture support
  - `src/luxo_behaviors/luxo_behaviors/state_machine.py` - State machine with custom transition conditions
  - `src/luxo_behaviors/launch/luxo_system.launch.py` - System launch file
  - `tests/` - Test suite with hardware mocks
- **Hot-reloading**: Components support dynamic behavior updates via state machine transitions
- **State machine**: Supports custom transition conditions defined as callable functions
- **Hardware mocks**: All hardware components have simulated versions for testing
- **Safety system**: Collision avoidance prevents arm collisions using proximity and distance sensors
- **Detection Methods**:
  1. Proximity Sensor (APDS9960) - Front detection
  2. Distance Sensors (VL53L4CD) - Side detection
