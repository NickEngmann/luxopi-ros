#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash
set -u
if [[ "${ROS_DOMAIN_ID}" != 73 || "${ROS_LOCALHOST_ONLY}" != 1 ]]; then
  echo 'Simulator requires isolated ROS domain 73 and localhost discovery.' >&2
  exit 2
fi
exec ros2 launch luxo_behaviors luxo_system.launch.py \
  use_hardware:=false use_camera:=false use_gui:=false use_rviz:=false \
  enable_system_monitor:=false enable_watchdog:=false \
  enable_voice:=true enable_speech_bridge:=true enable_sim_sensors:=true \
  enable_simulator_dashboard:=true simulator_host:=0.0.0.0 simulator_port:=8080
