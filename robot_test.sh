#!/bin/bash
cd ~/luxopi-ros
colcon build --packages-select luxo_behaviors
source install/setup.bash