#!/usr/bin/env python3
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.conditions import IfCondition
from launch_ros.actions import Node

def generate_launch_description():
    # Launch arguments
    test_mode = LaunchConfiguration('test_mode')
    enable_depth_collision = LaunchConfiguration('enable_depth_collision')
    safety_distance = LaunchConfiguration('safety_distance')
    sense_collision = LaunchConfiguration('sense_collision')
    
    # Declare launch arguments
    declare_test_mode = DeclareLaunchArgument(
        'test_mode',
        default_value='animation',
        description='Test mode: "position" for position_test or "animation" for animation_command'
    )
    
    declare_enable_depth_collision = DeclareLaunchArgument(
        'enable_depth_collision',
        default_value='False',
        description='Enable collision detection'
    )
    
    declare_safety_distance = DeclareLaunchArgument(
        'safety_distance',
        default_value='0.3',
        description='Safety distance in meters'
    )
    
    declare_sense_collision = DeclareLaunchArgument(
        'sense_collision',
        default_value='True',
        description='Enable APDS9960 proximity and gesture sensor'
    )
    
    # Hardware interface node
    hardware_interface_node = Node(
        package='luxo_behaviors',
        executable='hardware_interface',
        name='hardware_interface',
        output='screen',
        parameters=[
            {'serial_port': '/dev/ttyAMA0'},
            {'baud_rate': 115200},
            {'enable_torque': True},
            {'read_throttle': 0.1},
            # Reduce logging to avoid cluttering the console
            {'ros__parameters': {'log_level': 'error'}}
        ]
    )
    
    # APDS9960 proximity and gesture sensor node
    apds9960_node = Node(
        package='luxo_behaviors',
        executable='collision_ros_node',  # Remove the .py extension
        name='apds9960_node',
        output='screen',
        parameters=[
            {'proximity_threshold': 5}
        ],
        condition=IfCondition(sense_collision)
    )
    
    # Position test node - basic movement patterns
    position_test_node = Node(
        package='luxo_behaviors',
        executable='position_test',
        name='position_test',
        output='screen',
        condition=IfCondition(PythonExpression(["'", test_mode, "' == 'position'"]))
    )
    
    # Animation command node - more complex movements
    animation_command_node = Node(
        package='luxo_behaviors',
        executable='animation_command',
        name='animation_command',
        output='screen',
        parameters=[
            {'publish_joint_states': True},
            {'use_hardware_joint_names': True}  # This parameter is important for hardware
        ],
        condition=IfCondition(PythonExpression(["'", test_mode, "' == 'animation'"]))
    )
    
    # Collision detection node
    collision_detection_node = Node(
        package='luxo_behaviors',
        executable='collision_detection',
        name='collision_detection',
        output='screen',
        parameters=[
            {'safety_distance': safety_distance},
            {'robot_base_frame': 'oak'},
            {'point_cloud_topic': '/oak/points'},
            {'joint_states_topic': '/joint_states'},
            {'override_animation': True},
            # QoS settings for point cloud
            {'qos_reliability': 0},  # 0=BEST_EFFORT, 1=RELIABLE
            {'qos_durability': 0},   # 0=VOLATILE, 1=TRANSIENT_LOCAL
        ],
        condition=IfCondition(enable_depth_collision)
    )
    
    # Create and return launch description
    return LaunchDescription([
        # Launch arguments
        declare_test_mode,
        declare_enable_depth_collision,
        declare_safety_distance,
        declare_sense_collision,
        
        # Launch info
        LogInfo(msg=["Starting hardware system with test_mode=", test_mode, 
                    ", collision=", enable_depth_collision, ", apds9960=", sense_collision]),
        
        # Nodes
        hardware_interface_node,
        position_test_node,
        animation_command_node,
        collision_detection_node,
        apds9960_node
    ])