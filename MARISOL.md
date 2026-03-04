# MARISOL.md — Pipeline Context for luxopi-ros

## Project Overview
ROS2-based control system for RoArm-M3 robotic arm with Luxo Jr-style animations, vision processing, and collision avoidance.

## Build & Run
- **Language**: python
- **Framework**: ros2
- **Docker image**: ros:humble-ros-base
- **Install deps**: `pip install --no-cache-dir --break-system-packages pytest 2>&1 | tail -3; echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc; . /opt/ros/humble/setup.bash && cd /workspace/repo && colcon build --symlink-install 2>&1 | tail -10 || true; cd /workspace/repo && pip install  -r requirements.txt 2>&1 | tail -5 || true; pip install  pytest 2>&1 | tail -3`
- **Run**: (see source code)

## Testing
- **Test framework**: pytest
- **Test command**: (auto-detected)
- **Hardware mocks needed**: yes (ros2)
- **Last result**: 36/36 passed

