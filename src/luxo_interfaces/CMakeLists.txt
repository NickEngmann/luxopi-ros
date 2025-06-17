cmake_minimum_required(VERSION 3.8)
project(luxo_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

# Generate interfaces (actions, services, and messages)
rosidl_generate_interfaces(${PROJECT_NAME}
  "action/PlayAnimation.action"
  "srv/ConfigureI2CSensor.srv"
  
  # New message definitions for modular behavior system
  "msg/CollisionStatus.msg"
  "msg/EmergencyAction.msg"
  "msg/PositionRequest.msg"
  "msg/ActivityUpdate.msg"
  "msg/VoiceTarget.msg"
  "msg/SafetyOverride.msg"
  "msg/SystemStatus.msg"
  "msg/IdleRequest.msg"
  "msg/CollisionDetails.msg"
  "msg/PettingStatus.msg"
  
  DEPENDENCIES
  std_msgs
  geometry_msgs
  sensor_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()