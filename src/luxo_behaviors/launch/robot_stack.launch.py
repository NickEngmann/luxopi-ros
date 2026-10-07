"""Hardware launch preset connecting the local AI process to ROS behaviors."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    event_socket = LaunchConfiguration("speech_event_socket")
    enable_smart_home = LaunchConfiguration("enable_smart_home_bridge")
    system_launch = PathJoinSubstitution([
        FindPackageShare("luxo_behaviors"), "launch", "luxo_system.launch.py",
    ])
    return LaunchDescription([
        DeclareLaunchArgument(
            "speech_event_socket",
            default_value=EnvironmentVariable(
                "LUXOPI_ROS_EVENT_SOCKET", default_value="/tmp/luxopi-voice.sock"
            ),
            description="Same-user Unix socket shared with luxopi-ai",
        ),
        DeclareLaunchArgument(
            "enable_smart_home_bridge",
            default_value=EnvironmentVariable(
                "LUXOPI_ENABLE_SMART_HOME_BRIDGE", default_value="true"
            ),
            description="Enable configured Home Assistant and Music Assistant adapters",
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(system_launch),
            launch_arguments={
                "use_hardware": "true",
                "enable_speech_bridge": "true",
                # The bridge consumes AI events and does not load a second model.
                "speech_backend": "simulation",
                "speech_event_socket": event_socket,
                "enable_smart_home_bridge": enable_smart_home,
                "enable_simulator_dashboard": "false",
                "enable_sim_sensors": "false",
                "enable_sim_vision": "false",
                "enable_sim_interactions": "false",
                "enable_sim_autonomy": "false",
            }.items(),
        ),
    ])
