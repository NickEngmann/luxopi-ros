"""Run the standard ROS behavior graph with MuJoCo as its M3 dynamics owner."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, IncludeLaunchDescription, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression, EnvironmentVariable
from launch_ros.actions import Node
from launch.conditions import IfCondition
from launch_ros.parameter_descriptions import ParameterValue
import luxo_behaviors
from luxo_behaviors.launch_options import continuous_timing_default


def generate_launch_description():
    package = Path(get_package_share_directory("luxo_behaviors"))
    assets = Path(luxo_behaviors.__file__).parent / "assets/roarm_m3"
    system_launch = package / "launch/luxo_system.launch.py"
    robot_description_file = LaunchConfiguration("robot_description_file")

    system = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(system_launch)),
        launch_arguments={
            "use_hardware": LaunchConfiguration("use_hardware"),
            "use_camera": LaunchConfiguration("use_camera"),
            "use_gui": LaunchConfiguration("use_gui"),
            "use_rviz": LaunchConfiguration("use_rviz"),
            "enable_system_monitor": LaunchConfiguration("enable_system_monitor"),
            "enable_watchdog": LaunchConfiguration("enable_watchdog"),
            "enable_voice": LaunchConfiguration("enable_voice"),
            "enable_speech_bridge": LaunchConfiguration("enable_speech_bridge"),
            "enable_smart_home_bridge": LaunchConfiguration("enable_smart_home_bridge"),
            "enable_sim_sensors": LaunchConfiguration("enable_sim_sensors"),
            "enable_sim_vision": LaunchConfiguration("enable_sim_vision"),
            "enable_gestures": LaunchConfiguration("enable_gestures"),
            # Forward the synthetic activity driver controls into the shared
            # behavior graph. These were declared at this launch layer but
            # never reached luxo_system, so physics simulators stayed static
            # and the dashboard always reported autonomy disabled.
            "enable_sim_autonomy": LaunchConfiguration("enable_sim_autonomy"),
            "sim_idle_after": LaunchConfiguration("sim_idle_after"),
            "sim_idle_interval": LaunchConfiguration("sim_idle_interval"),
            "sim_emotion_interval": LaunchConfiguration("sim_emotion_interval"),
            "joint_profile": LaunchConfiguration("joint_profile"),
            "continuous_animation_timing": LaunchConfiguration("continuous_animation_timing"),
            "simulation_backend": "mujoco",
            "robot_description_file": robot_description_file,
            "enable_simulator_dashboard": LaunchConfiguration("enable_simulator_dashboard"),
            "simulator_host": LaunchConfiguration("simulator_host"),
            "simulator_port": LaunchConfiguration("simulator_port"),
            "required_sensor_directions": LaunchConfiguration("required_sensor_directions"),
            "speech_synthesize": LaunchConfiguration("speech_synthesize"),
            "speech_backend": LaunchConfiguration("speech_backend"),
            "speech_service_command": LaunchConfiguration("speech_service_command"),
            "speech_service_cwd": LaunchConfiguration("speech_service_cwd"),
            "simulator_audio_directory": LaunchConfiguration("simulator_audio_directory"),
        }.items(),
    )
    physics = Node(
        package="luxo_behaviors",
        executable="mujoco_simulator",
        name="mujoco_simulator",
        output="screen",
        parameters=[
            {"robot_description_file": robot_description_file},
            {"asset_directory": str(assets)},
            {"physics_rate": LaunchConfiguration("physics_rate")},
            {"servo_omega": LaunchConfiguration("servo_omega")},
            {"damping_ratio": LaunchConfiguration("damping_ratio")},
            {"effort_limit": LaunchConfiguration("effort_limit")},
        ],
    )
    virtual_sensors = Node(
        package="luxo_behaviors",
        executable="sim_world_sensors",
        name="sim_world_sensors",
        output="screen",
        condition=IfCondition(LaunchConfiguration("enable_world_sensor_fixture")),
        parameters=[{
            "robot_description_file": robot_description_file,
            "asset_directory": str(assets),
            "obstacles_json": ParameterValue(LaunchConfiguration("world_obstacles_json"), value_type=str),
            "sensor_mounts_json": ParameterValue(LaunchConfiguration("sensor_mounts_json"), value_type=str),
        }],
    )
    critical_exit = RegisterEventHandler(
        OnProcessExit(
            target_action=physics,
            on_exit=[EmitEvent(event=Shutdown(reason="critical MuJoCo dynamics process exited"))],
        )
    )
    sensor_exit = RegisterEventHandler(
        OnProcessExit(
            target_action=virtual_sensors,
            on_exit=[EmitEvent(event=Shutdown(reason="critical synthetic collision sensor process exited"))],
        )
    )

    return LaunchDescription([
        DeclareLaunchArgument("robot_description_file", default_value="/tmp/luxopi-m3.urdf"),
        DeclareLaunchArgument("use_hardware", default_value="false"),
        DeclareLaunchArgument("use_camera", default_value="false"),
        DeclareLaunchArgument("use_gui", default_value="false"),
        DeclareLaunchArgument("use_rviz", default_value="false"),
        DeclareLaunchArgument("enable_system_monitor", default_value="false"),
        DeclareLaunchArgument("enable_watchdog", default_value="true"),
        DeclareLaunchArgument("enable_voice", default_value="true"),
        DeclareLaunchArgument("enable_speech_bridge", default_value="true"),
        DeclareLaunchArgument("enable_smart_home_bridge", default_value="false"),
        DeclareLaunchArgument("enable_sim_sensors", default_value="true"),
        DeclareLaunchArgument("enable_sim_autonomy", default_value=EnvironmentVariable("LUXOPI_SIM_AUTONOMY", default_value="false")),
        DeclareLaunchArgument("sim_idle_after", default_value=EnvironmentVariable("LUXOPI_SIM_IDLE_AFTER", default_value="7.0")),
        DeclareLaunchArgument("sim_idle_interval", default_value=EnvironmentVariable("LUXOPI_SIM_IDLE_INTERVAL", default_value="20.0")),
        DeclareLaunchArgument("sim_emotion_interval", default_value=EnvironmentVariable("LUXOPI_SIM_EMOTION_INTERVAL", default_value="75.0")),
        DeclareLaunchArgument("enable_world_sensor_fixture", default_value="false"),
        DeclareLaunchArgument(
            "required_sensor_directions",
            default_value=PythonExpression([
                "'front,left,right' if '",
                LaunchConfiguration("enable_world_sensor_fixture"),
                "' == 'true' else ''",
            ]),
            description=(
                "Required fresh collision sensor directions; world sensor fixtures "
                "require front,left,right by default, while sensorless scenes are optional"
            ),
        ),
        DeclareLaunchArgument("enable_sim_vision", default_value="true"),
        DeclareLaunchArgument("enable_gestures", default_value="true"),
        DeclareLaunchArgument("joint_profile", default_value="roarm_m3"),
        DeclareLaunchArgument(
            "continuous_animation_timing",
            default_value=continuous_timing_default(LaunchConfiguration("use_hardware")),
            description="Use settled continuous bounded trajectories; hardware stays on its independent path",
        ),
        DeclareLaunchArgument("enable_simulator_dashboard", default_value="true"),
        DeclareLaunchArgument("simulator_host", default_value="0.0.0.0"),
        DeclareLaunchArgument("simulator_port", default_value="8080"),
        DeclareLaunchArgument("speech_synthesize", default_value=EnvironmentVariable("LUXOPI_SYNTHESIZE_SPEECH", default_value="false")),
        DeclareLaunchArgument("speech_backend", default_value="simulation"),
        DeclareLaunchArgument("speech_service_command", default_value="[]"),
        DeclareLaunchArgument("speech_service_cwd", default_value=""),
        DeclareLaunchArgument("simulator_audio_directory", default_value=""),
        DeclareLaunchArgument("physics_rate", default_value="500.0"),
        DeclareLaunchArgument("servo_omega", default_value="25.0"),
        DeclareLaunchArgument("damping_ratio", default_value="1.0"),
        DeclareLaunchArgument("effort_limit", default_value="3.0"),
        DeclareLaunchArgument("world_obstacles_json", default_value="[]"),
        DeclareLaunchArgument(
            "sensor_mounts_json",
            default_value='{"front":{"frame":"gripper_link","offset_m":[0,0,0.02],"direction":[0,0,1],"max_range_m":0.25},"left":{"frame":"gripper_link","offset_m":[0,0.02,0.02],"direction":[0,-1,0],"max_range_m":0.8},"right":{"frame":"gripper_link","offset_m":[0,-0.02,0.02],"direction":[0,1,0],"max_range_m":0.8}}',
        ),
        system,
        critical_exit,
        sensor_exit,
        physics,
        virtual_sensors,
    ])
