cd ~/ros2_project_ws
colcon build --packages-select luxo_behaviors
source install/setup.bash
sudo chmod 777 /dev/ttyAMA0
ros2 run luxo_behaviors direct_test --ros-args -p reading_throttle:=0.5