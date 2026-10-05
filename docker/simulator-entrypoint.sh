#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash
set -u
if [[ "${ROS_DOMAIN_ID}" != 73 || "${ROS_LOCALHOST_ONLY}" != 1 ]]; then
  echo 'Simulator requires isolated ROS domain 73 and localhost discovery.' >&2
  exit 2
fi
if [[ "${LUXOPI_SIM_BACKEND:-kinematic}" == gazebo ]]; then
  exec ros2 launch luxo_behaviors physics_simulator.launch.py
fi
optional_args=()
joint_profile="${LUXOPI_JOINT_PROFILE:-urdf4}"
if [[ "$joint_profile" == roarm_m3 ]]; then
  python3 - <<'MODEL'
from pathlib import Path
import luxo_behaviors
from luxo_behaviors.gazebo_description import build_vendor_description
assets = Path(luxo_behaviors.__file__).parent / 'assets/roarm_m3'
Path('/tmp/luxopi-m3.urdf').write_text(build_vendor_description(assets))
MODEL
  optional_args+=("robot_description_file:=/tmp/luxopi-m3.urdf")
fi
[[ -z "${LUXOPI_SPEECH_CWD:-}" ]] || optional_args+=("speech_service_cwd:=${LUXOPI_SPEECH_CWD}")
[[ -z "${LUXOPI_SIM_AUDIO_DIRECTORY:-}" ]] || optional_args+=("simulator_audio_directory:=${LUXOPI_SIM_AUDIO_DIRECTORY}")
exec ros2 launch luxo_behaviors luxo_system.launch.py \
  use_hardware:=false use_camera:=false use_gui:=false use_rviz:=false \
  enable_system_monitor:=false enable_watchdog:=true \
  enable_voice:=true enable_speech_bridge:=true enable_sim_sensors:=true enable_gestures:=true \
  "speech_backend:=${LUXOPI_SPEECH_BACKEND:-simulation}" \
  "speech_service_command:=${LUXOPI_SPEECH_COMMAND:-[]}" \
  "joint_profile:=$joint_profile" \
  "${optional_args[@]}" \
  enable_simulator_dashboard:=true simulator_host:=0.0.0.0 simulator_port:=8080
