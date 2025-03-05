#!/usr/bin/env python3
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # Launch arguments
    use_camera = LaunchConfiguration('use_camera', default='true')
    run_demo = LaunchConfiguration('run_demo', default='false')
    use_gui = LaunchConfiguration('use_gui', default='false')
    
    # Declare launch arguments
    declare_use_camera = DeclareLaunchArgument(
        'use_camera',
        default_value='true',
        description='Whether to launch the depth camera'
    )
    
    declare_run_demo = DeclareLaunchArgument(
        'run_demo',
        default_value='false',
        description='Whether to run the demo sequence'
    )
    
    declare_use_gui = DeclareLaunchArgument(
        name='use_gui',
        default_value='false',  # Set default to false to disable the GUI publisher
        description='Flag to enable joint_state_publisher_gui'
    )
    
    # Include RoArm launch file
    roarm_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('roarm'),
                'launch/roarm.launch.py'
            ])
        ]),
        launch_arguments={
            'gui': LaunchConfiguration('use_gui')
        }.items()
    )
    
    # Include DepthAI camera launch file
    depthai_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('depthai_ros_driver'),
                'launch/camera.launch.py'
            ])
        ]),
        condition=IfCondition(use_camera)
    )
    
    # Animation command interface node
    animation_command_node = Node(
        package='luxo_behaviors',
        executable='animation_command',
        name='animation_command',
        output='screen'
    )
    
    # Camera interaction node (requires camera)
    camera_node = Node(
        package='luxo_behaviors',
        executable='camera_interaction',
        name='camera_interaction',
        output='screen',
        condition=IfCondition(use_camera)
    )
    
    # Demo mode node (optional)
    demo_node = Node(
        package='luxo_behaviors',
        executable='demo_mode',
        name='demo_mode',
        output='screen',
        condition=IfCondition(run_demo)
    )
    
    # Create and return launch description
    return LaunchDescription([
        declare_use_camera,
        declare_run_demo,
        declare_use_gui,
        roarm_launch,
        depthai_launch,
        animation_command_node,
        camera_node,
        demo_node
    ])