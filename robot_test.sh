#!/bin/bash
cd ~/ros2_project_ws
colcon build --packages-select luxo_behaviors
source install/setup.bash