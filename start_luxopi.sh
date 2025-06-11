#!/bin/bash

# Source ROS2 setup files
source /opt/ros/jazzy/setup.bash
source /home/pi/luxopi-ros/install/setup.bash

# Export any additional environment variables needed by ROS2
export DISPLAY=:0
export ROS_DOMAIN_ID=0

# Start the luxopi system
# adjust modprobe for i2c devices to 10kHz for noise
# sudo modprobe i2c_bcm2708 baudrate=10000

cd /home/pi/luxopi-ros
colcon build
ros2 launch luxo_behaviors luxo_system.launch.py \
  use_hardware:=true \
  use_camera:=true \
  enable_emotion_detection:=true \
  enable_voice:=true \
  enable_ads7830:=true \
  verbose:=true \
  enable_idle_animations:=true \
  enable_dynamic_adaptation:=false \
  enable_framebuffer_display:=true \
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
