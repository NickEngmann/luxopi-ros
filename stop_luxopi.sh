#!/bin/bash

# Source ROS2 setup files
source /opt/ros/humble/setup.bash
source /home/pi/luxopi-ros/install/setup.bash

# Send the close animation command
echo "Sending close animation command..."
ros2 topic pub --once /roarm/animation_command std_msgs/String "data: close"

# Wait for animation to complete
echo "Waiting 10 seconds for animation to complete..."
sleep 10

echo "Shutdown complete"
exit 0