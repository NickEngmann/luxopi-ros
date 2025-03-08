from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # Launch arguments
    run_demo = LaunchConfiguration('run_demo', default='true')
    
    # Declare launch arguments
    declare_run_demo = DeclareLaunchArgument(
        'run_demo',
        default_value='true',
        description='Whether to run the demo sequence'
    )
    
    # Robot state publisher needed for TF frames
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher'
    )
    
    # Demo mode node (generates animation)
    demo_node = Node(
        package='luxo_behaviors',
        executable='demo_mode', 
        name='demo_mode',
        output='screen',
        condition=IfCondition(run_demo)
    )
    
    # Hardware interface node
    hardware_interface = Node(
        package='luxo_behaviors',
        executable='hardware_interface',
        name='hardware_interface',
        output='screen'
    )
    
    # Create and return launch description
    return LaunchDescription([
        declare_run_demo,
        robot_state_publisher,
        demo_node,
        hardware_interface
    ])