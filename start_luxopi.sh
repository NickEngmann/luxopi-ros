#!/bin/bash

# Source ROS2 setup files
source /opt/ros/jazzy/setup.bash
source /home/pi/luxopi-ros/install/setup.bash

# Export any additional environment variables needed by ROS2
export DISPLAY=:0
export ROS_DOMAIN_ID=0

# Start the luxopi system
cd /home/pi/luxopi-ros
colcon build
ros2 launch luxo_behaviors luxo_system.launch.py \
  use_hardware:=true \
  use_camera:=true \
  enable_emotion_detection:=true \
  verbose:=true \
  enable_dynamic_adaptation:=false \
  sense_collision:=true

# Keep the script running 
while true; do
  echo "LuxoPi service exited with code $?. Restarting in 5 seconds..."
  sleep 5
  ros2 launch luxo_behaviors luxo_system.launch.py \
    use_hardware:=true \
    use_camera:=true \
    enable_emotion_detection:=true \
    verbose:=true \
    enable_dynamic_adaptation:=true \
    sense_collision:=true
done
