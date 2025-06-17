#!/usr/bin/env python3
"""
Modular Luxo System Launch File - Using the new behavior node architecture.

This launch file starts the modular behavior system with:
- SafetyCoordinatorNode (central arbitration)
- CollisionMonitorNode (collision detection and immediate responses) 
- VoiceFollowingNode (voice direction tracking)
- IdleBehaviorNode (idle animations and behaviors)
- PettingResponseNode (petting detection and responses)
- Plus all the existing hardware interface and sensor nodes
"""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, LogInfo, ExecuteProcess
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression, Command
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # Launch arguments with better defaults for simulation
    use_hardware = LaunchConfiguration('use_hardware', default='false')
    
    # Set default values based on hardware or simulation mode
    use_camera = LaunchConfiguration('use_camera')
    sense_collision = LaunchConfiguration('sense_collision')
    enable_depth_collision = LaunchConfiguration('enable_depth_collision')
    test_mode = LaunchConfiguration('test_mode', default='behavior')  # Changed default to 'behavior'
    
    # Other standard arguments with simplified defaults
    use_gui = LaunchConfiguration('use_gui', default='false')
    safety_distance = LaunchConfiguration('safety_distance', default='0.3')
    verbose_output = LaunchConfiguration('verbose', default='false')
    
    # Add dynamic adaptation parameters - now defaults based on hardware
    enable_dynamic_adaptation = LaunchConfiguration('enable_dynamic_adaptation')
    
    # Add gesture detection parameter
    enable_gestures = LaunchConfiguration('enable_gestures')
    
    # Behavior system parameters
    enable_voice_following = LaunchConfiguration('enable_voice_following')
    enable_idle_behaviors = LaunchConfiguration('enable_idle_behaviors')
    enable_petting_response = LaunchConfiguration('enable_petting_response')
    enable_collision_avoidance = LaunchConfiguration('enable_collision_avoidance')
    
    # Main hardware/simulation mode selector
    declare_use_hardware = DeclareLaunchArgument(
        'use_hardware',
        default_value='false',
        description='Whether to launch with physical hardware or in simulation'
    )
    
    # Camera argument with conditional default
    declare_use_camera = DeclareLaunchArgument(
        'use_camera',
        default_value=PythonExpression(["'false' if '", use_hardware, "' == 'false' else 'true'"]),
        description='Whether to launch the depth camera (default: true in hardware, false in simulation)'
    )
    
    # Emotion detection argument - now defaults to true when camera is enabled
    declare_enable_emotion_detection = DeclareLaunchArgument(
        'enable_emotion_detection',
        default_value=PythonExpression(["'", use_camera, "'"]),  # Directly match use_camera value
        description='Enable emotion detection with camera (default: same as use_camera)'
    )
    
    # Proximity sensor argument with conditional default
    declare_sense_collision = DeclareLaunchArgument(
        'sense_collision',
        default_value=PythonExpression(["'false' if '", use_hardware, "' == 'false' else 'true'"]),
        description='Enable I2C proximity and distance sensors (default: true in hardware, false in simulation)'
    )
    
    # Gesture detection argument
    declare_enable_gestures = DeclareLaunchArgument(
        'enable_gestures',
        default_value='false',
        description='Enable gesture detection with APDS9960 (default: false)'
    )
    
    # Depth collision argument with conditional default
    declare_enable_depth_collision = DeclareLaunchArgument(
        'enable_depth_collision',
        default_value=PythonExpression(["'false'"]),
        description='Enable depth-based collision detection (default: false)'
    )
    
    declare_use_gui = DeclareLaunchArgument(
        name='use_gui',
        default_value='false',
        description='Flag to enable joint_state_publisher_gui'
    )
    
    # Fix for joint_state_publisher issue
    use_joint_state_publisher_arg = DeclareLaunchArgument(
        'use_joint_state_publisher',
        default_value='false',  # Always default to false
        description='Use the joint_state_publisher'
    )
    
    # Updated test mode - now includes 'behavior' option
    declare_test_mode = DeclareLaunchArgument(
        'test_mode',
        default_value='behavior',
        description='Test mode: "position" for position_test, "animation" for animation_command, or "behavior" for full behavior system'
    )
    
    declare_safety_distance = DeclareLaunchArgument(
        'safety_distance',
        default_value='0.3',
        description='Safety distance in meters'
    )
    
    declare_verbose = DeclareLaunchArgument(
        'verbose',
        default_value='false',
        description='Enable verbose output and additional debugging information'
    )
    
    # Voice following arguments
    declare_enable_voice = DeclareLaunchArgument(
        'enable_voice',
        default_value='true',
        description='Enable voice direction detection'
    )
    
    declare_enable_voice_following = DeclareLaunchArgument(
        'enable_voice_following',
        default_value='true',
        description='Enable voice following behavior node'
    )

    # Add a launch argument for camera rotation
    declare_camera_rotation = DeclareLaunchArgument(
        'camera_rotation',
        default_value='false',
        description='Rotate camera image 180 degrees (set to true if camera is mounted upside down)'
    )
    
    # Dynamic adaptation argument - now defaults to true when hardware is enabled
    declare_enable_dynamic_adaptation = DeclareLaunchArgument(
        'enable_dynamic_adaptation',
        default_value=PythonExpression(["'", use_hardware, "'"]),  # Directly match use_hardware value
        description='Enable dynamic adaptation mode (default: same as use_hardware)'
    )
    
    declare_system_monitor = DeclareLaunchArgument(
        'enable_system_monitor',
        default_value='true',
        description='Enable system monitoring (CPU, RAM, temperature)'
    )
    
    # Behavior system arguments
    declare_enable_idle_behaviors = DeclareLaunchArgument(
        'enable_idle_behaviors',
        default_value='true',
        description='Enable idle behavior system (animations, head variations, home positions)'
    )
    
    declare_enable_petting_response = DeclareLaunchArgument(
        'enable_petting_response',
        default_value=PythonExpression(["'", sense_collision, "'"]),  # Default to same as collision sensing
        description='Enable petting detection and response behaviors'
    )
    
    declare_enable_collision_avoidance = DeclareLaunchArgument(
        'enable_collision_avoidance',
        default_value=PythonExpression(["'", sense_collision, "'"]),  # Default to same as collision sensing
        description='Enable collision monitoring and avoidance behaviors'
    )
    
    # ==========================================================================
    # LOGGING ACTIONS
    # ==========================================================================
    
    # Initial startup banner
    startup_banner = LogInfo(msg=["="*80, 
                                  "\n\n🚀 STARTING LUXOPI MODULAR BEHAVIOR SYSTEM\n",
                                  "="*80])
    
    # Mode selection info
    mode_info = LogInfo(msg=["\n📋 SYSTEM CONFIGURATION:\n",
                            "- Mode: ", PythonExpression(["'🔧 HARDWARE' if '", use_hardware, "' == 'true' else '🖥️  SIMULATION'"]), "\n",
                            "- Test mode: ", test_mode, "\n",
                            "- Camera enabled: ", use_camera, "\n",
                            "- Emotion detection: ", LaunchConfiguration('enable_emotion_detection'), "\n",
                            "- Collision detection: ", enable_depth_collision, "\n",
                            "- Using I2C sensors: ", sense_collision, "\n",
                            "- Gesture detection: ", enable_gestures, "\n",
                            "- Voice following: ", enable_voice_following, "\n",
                            "- Idle behaviors: ", enable_idle_behaviors, "\n",
                            "- Petting response: ", enable_petting_response, "\n",
                            "- Collision avoidance: ", enable_collision_avoidance, "\n",
                            ])
    
    # Behavior system info
    behavior_system_info = LogInfo(
        msg=["\n🤖 MODULAR BEHAVIOR SYSTEM:\n",
             "- SafetyCoordinator: Central arbitration and safety\n",
             "- CollisionMonitor: ", PythonExpression(["'enabled' if '", enable_collision_avoidance, "' == 'true' else 'disabled'"]), "\n",
             "- VoiceFollowing: ", PythonExpression(["'enabled' if '", enable_voice_following, "' == 'true' else 'disabled'"]), "\n",
             "- IdleBehavior: ", PythonExpression(["'enabled' if '", enable_idle_behaviors, "' == 'true' else 'disabled'"]), "\n",
             "- PettingResponse: ", PythonExpression(["'enabled' if '", enable_petting_response, "' == 'true' else 'disabled'"]), "\n"],
        condition=IfCondition(PythonExpression(["'", test_mode, "' == 'behavior'"]))
    )
    
    # Hardware-specific info
    hardware_info = LogInfo(
        msg=["\n🔧 HARDWARE MODE DETAILS:\n",
             "- Serial port: /dev/ttyAMA0 (baud: 115200)\n",
             "- Test mode: ", test_mode, " (position=basic movements, animation=complex behaviors, behavior=full system)\n",
             "- I2C sensing: ", PythonExpression(["'enabled' if '", sense_collision, "' == 'true' else 'disabled'"]), "\n",
             "- Hardware joint states enabled\n"],
        condition=IfCondition(use_hardware)
    )
    
    # Simulation-specific info
    simulation_info = LogInfo(
        msg=["\n🖥️ SIMULATION MODE DETAILS:\n",
             "- Using RoArm simulation backend\n",
             "- GUI enabled: ", use_gui, "\n",
             "- Test mode: ", test_mode, "\n",
             "- Running with standard joint names\n"],
        condition=UnlessCondition(use_hardware)
    )
    
    # Quick reference for common launch commands
    quick_reference = LogInfo(
        msg=["\n📝 QUICK REFERENCE:\n",
             "- Full hardware system: ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true\n",
             "- Basic simulation: ros2 launch luxo_behaviors luxo_system.launch.py\n",
             "- Simulation with behaviors: ros2 launch luxo_behaviors luxo_system.launch.py test_mode:=behavior\n",
             "- Hardware behavior system: ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true test_mode:=behavior\n",
             "- Hardware with collision: ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true enable_depth_collision:=true\n",
             "- Disable specific behaviors: ros2 launch luxo_behaviors luxo_system.launch.py enable_idle_behaviors:=false\n"],
        condition=IfCondition(verbose_output)
    )
    
    # Camera info
    camera_info = LogInfo(
        msg=["\n📷 CAMERA SUBSYSTEM:\n",
             "- Using DepthAI OAK camera\n",
             "- Emotion detection: ", PythonExpression(["'enabled' if '", LaunchConfiguration('enable_emotion_detection'), "' == 'true' else 'disabled'"]), "\n",
             "- Depth collision detection: ", PythonExpression(["'enabled' if '", enable_depth_collision, "' == 'true' else 'disabled'"]), "\n",
             "- Safety distance: ", safety_distance, " meters\n"],
        condition=IfCondition(use_camera)
    )
    
    # I2C sensor info
    i2c_info = LogInfo(
        msg=["\n🔌 I2C SENSOR SUBSYSTEM:\n",
             "- I2C Device Manager: ", PythonExpression(["'enabled' if '", sense_collision, "' == 'true' else 'disabled'"]), "\n",
             "- APDS9960 proximity sensor: enabled\n",
             "- VL53L4CD distance sensors (left/right): enabled\n",
             "- Gesture detection: ", PythonExpression(["'enabled' if '", enable_gestures, "' == 'true' else 'disabled'"]), "\n",
             "- Petting detection: ", PythonExpression(["'enabled' if '", enable_petting_response, "' == 'true' else 'disabled'"]), "\n",
             "- Bus protection: active\n",
             "- Auto-recovery: enabled\n"],
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'true' and '", sense_collision, "' == 'true'"]))
    )

    # Troubleshooting tips
    troubleshooting_info = LogInfo(
        msg=["\n🔍 TROUBLESHOOTING TIPS:\n",
             "- If hardware not responding, check serial connection and permissions\n",
             "- For camera issues, verify USB connection and permissions\n",
             "- For I2C sensor issues, check: ros2 topic echo /i2c/sensor_health\n",
             "- Monitor behavior coordination: ros2 topic echo /safety/system_status\n",
             "- Check collision status: ros2 topic echo /collision/status\n",
             "- View voice following: ros2 topic echo /voice/status\n",
             "- Monitor idle behavior: ros2 topic echo /idle/status\n",
             "- Check petting status: ros2 topic echo /petting/status\n",
             "- View topics with: ros2 topic list\n",
             "- Check node status with: ros2 node list\n"],
        condition=IfCondition(verbose_output)
    )
    
    # Show active nodes at end of startup
    show_nodes_cmd = ExecuteProcess(
        cmd=["bash", "-c", "echo '📊 ACTIVE NODES:' && sleep 3 && ros2 node list | grep -E '(safety|collision|voice|idle|petting)' || echo 'No behavior nodes detected yet'"],
        output='screen',
        condition=IfCondition(verbose_output)
    )
    
    # ==========================================================================
    # LAUNCH FILES
    # ==========================================================================
    
    # Include RoArm launch file (simulation only)
    roarm_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('roarm'),
                'launch/roarm.launch.py'
            ])
        ]),
        launch_arguments={
            'gui': LaunchConfiguration('use_gui'),
            'use_joint_state_publisher': 'true'
        }.items(),
        condition=UnlessCondition(use_hardware)
    )
    
    jsp_killer = ExecuteProcess(
        cmd=["bash", "-c", "sleep 5 && pkill -f \"/opt/ros/jazzy/lib/joint_state_publisher/joint_state_publisher\" || true"],
        output='screen',
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'false' and '", use_gui, "' == 'true'"]))
    )

    # Robot state publisher for simulation
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': Command([
                'cat ',
                PathJoinSubstitution([
                    FindPackageShare('roarm'),
                    'urdf/roarm.urdf'
                ])
            ]),
            'publish_frequency': 30.0,
            'frame_prefix': '',
            'use_sim_time': False
        }],
        condition=UnlessCondition(use_hardware)
    )
    
    # ==========================================================================
    # HARDWARE INTERFACE AND SENSOR NODES
    # ==========================================================================
    
    # Hardware interface node (hardware only) - FIXED: Removed error log level
    hardware_interface_node = Node(
        package='luxo_behaviors',
        executable='hardware_interface',
        name='hardware_interface_main',  # Changed name to avoid conflicts
        output='screen',
        parameters=[
            {'serial_port': '/dev/ttyAMA0'},
            {'baud_rate': 115200},
            {'enable_torque': True},
            {'read_throttle': 0.1},
            {'behavior_mode': PythonExpression(["'", test_mode, "' == 'behavior'"])},
            {'enable_dynamic_adaptation': enable_dynamic_adaptation},
            {'dynamic_adaptation_base_limit': 1},
            {'dynamic_adaptation_shoulder_limit': 1},
            {'dynamic_adaptation_elbow_limit': 1}, 
            {'dynamic_adaptation_wrist_limit': 1},
            {'dynamic_adaptation_roll_limit': 1},
            {'dynamic_adaptation_hand_limit': 0},
            {'dynamic_adaptation_resume_delay': 10.0},
            {'enable_movement_source_integration': True}
        ],
        condition=IfCondition(use_hardware)
    )
    
    # I2C Device Manager node (hardware only)
    i2c_device_manager_node = Node(
        package='luxo_behaviors',
        executable='i2c_device_manager',
        name='i2c_device_manager',
        output='screen',
        parameters=[
            {'enable_gestures': enable_gestures},
            {'enable_apds9960': True},
            {'enable_vl53_left': True},
            {'enable_vl53_right': True},
            {'publish_rate': 10.0}  # Increased to 10Hz for better responsiveness
        ],
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'true' and '", sense_collision, "' == 'true'"]))
    )
    
    # Voice direction detection node (low-level audio processing)
    voice_direction_node = Node(
        package='luxo_behaviors',
        executable='voice_direction_node',
        name='voice_direction_node',
        output='screen',
        parameters=[
            {'sample_rate': 16000},
            {'channels': 4},
            {'vad_aggressiveness': 3},
            {'confidence_threshold': 0.5},
            {'enable_pixel_ring': True},
            {'direction_smoothing_window': 5},
            {'min_report_interval': 0.5}
        ],
        condition=IfCondition(LaunchConfiguration('enable_voice'))
    )

    # Legacy collision detection logic node (hardware only, now mainly for sensor processing)
    collision_logic_node = Node(
        package='luxo_behaviors',
        executable='collision_ros_node',
        name='collision_sensor_processor',  # Renamed to reflect new role
        output='screen',
        parameters=[
            {'proximity_threshold': 15},
            {'side_distance_threshold': 8.0},
            {'danger_threshold': 5.0},
            {'warning_threshold': 15.0},
            {'enable_gestures': enable_gestures},
            {'publish_petting_events': True}  # Enable petting event publishing
        ],
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'true' and '", sense_collision, "' == 'true'"]))
    )

    # System monitor node
    system_monitor_node = Node(
        package='luxo_behaviors',
        executable='system_monitor',
        name='system_monitor',
        output='screen',
        parameters=[
            {'publish_rate': 2.0},
            {'temperature_source': '/sys/class/thermal/thermal_zone0/temp'},
            {'cpu_average_window': 5.0}
        ],
        condition=IfCondition(LaunchConfiguration('enable_system_monitor'))
    )
    
    # Depth-based collision detection node (optional)
    collision_detection_node = Node(
        package='luxo_behaviors',
        executable='collision_detection',
        name='depth_collision_detection',
        output='screen',
        parameters=[
            {'safety_distance': safety_distance},
            {'robot_base_frame': 'base_link'},
            {'point_cloud_topic': '/oak/points'},
            {'joint_states_topic': '/joint_states'},
            {'override_animation': False},  # Let SafetyCoordinator handle this
            {'qos_reliability': 0},
            {'qos_durability': 0},
        ],
        condition=IfCondition(enable_depth_collision)
    )
    
    # Camera interaction node (requires camera)
    camera_interaction_node = Node(
        package='luxo_behaviors',
        executable='camera_interaction',
        name='camera_interaction',
        output='screen',
        parameters=[
            {'publish_camera_feed': False},
            {'verbose': LaunchConfiguration('verbose')},
            {'react_to_emotions': LaunchConfiguration('enable_emotion_detection')},
            {'camera_rotation': LaunchConfiguration('camera_rotation')}
        ],
        condition=IfCondition(use_camera)
    )
    
    # ==========================================================================
    # TEST MODE NODES (Legacy support)
    # ==========================================================================
    
    # Position test node - basic movement patterns (hardware only)
    position_test_node = Node(
        package='luxo_behaviors',
        executable='position_test',
        name='position_test',
        output='screen',
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'true' and '", test_mode, "' == 'position'"]))
    )
    
    # Animation command node (hardware version) - DISABLED in behavior mode to prevent conflicts
    hardware_animation_node = Node(
        package='luxo_behaviors',
        executable='animation_command',
        name='animation_command',
        output='screen',
        parameters=[
            {'publish_joint_states_target': True},
            {'use_hardware_joint_names': True},
            {'publish_target_topic': True},
            {'enforce_joint_limits': True},
            {'use_hardware_position_feedback': True}
        ],
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'true' and '", test_mode, "' == 'animation'"]))
    )
    
    # Animation command node (simulation version)
    simulation_animation_node = Node(
        package='luxo_behaviors',
        executable='animation_command',
        name='animation_command',
        output='screen',
        parameters=[
            {'publish_joint_states_target': False},
            {'publish_target_topic': True},
            {'enforce_joint_limits': True},
        ],
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'false' and '", test_mode, "' == 'animation'"]))
    )

    # ==========================================================================
    # MODULAR BEHAVIOR SYSTEM NODES
    # ==========================================================================
    
    # SafetyCoordinatorNode - Central arbitration and safety (ALWAYS runs in behavior mode)
    safety_coordinator_node = Node(
        package='luxo_behaviors',
        executable='safety_coordinator_node',
        name='safety_coordinator',
        output='screen',
        parameters=[
            # Safety limits
            {'soft_limit_distance': 15.0},
            {'hard_limit_distance': 8.0},
            {'max_deceleration': 22.5},
            
            # Override management
            {'default_override_timeout': 10.0},
            {'max_override_duration': 30.0},
            {'blend_transition_time': 2.0},
            
            # Base rotation limits
            {'base_min_limit': -260.0},
            {'base_max_limit': 135.0},
            {'enable_base_wraparound': True},
            
            # Coordination
            {'enable_voice_coordination': enable_voice_following},
            {'enable_collision_coordination': enable_collision_avoidance},
            {'enable_movement_source_integration': True},
            {'command_rate_limit': 50.0},
            
            # Hardware interface - FIXED: Use consistent topic
            {'joint_command_topic': '/roarm/joint_command'},
            {'joint_names': ['base', 'shoulder', 'elbow', 'wrist', 'hand']},
            
            # Debug logging
            {'enable_debug_logging': verbose_output}
        ],
        condition=IfCondition(PythonExpression(["'", test_mode, "' == 'behavior'"]))
    )
    
    # CollisionMonitorNode - Collision detection and immediate safety responses
    collision_monitor_node = Node(
        package='luxo_behaviors',
        executable='collision_monitor_node',
        name='collision_monitor',
        output='screen',
        parameters=[
            # Basic collision parameters
            {'enable_collision_avoidance': enable_collision_avoidance},
            {'soft_limit_distance': 15.0},
            {'hard_limit_distance': 8.0},
            {'max_deceleration': 22.5},
            
            # Collision tracking
            {'consecutive_collision_threshold': 5},
            {'escape_threshold': 8},
            {'max_escape_attempts': 3},
            {'adjustment_cooldown': 1.0},
            
            # Escape mode
            {'escape_mode_duration': 5.0},
            {'max_retreat_angle': 1.0},
            {'side_avoidance_magnitude': 0.4},
            
            # Timeouts
            {'collision_recovery_timeout': 2.0},
            {'short_collision_timeout': 1.25},
            {'extended_collision_timeout': 8.0},
            {'max_collision_timeout': 15.0},
            
            # Base limits
            {'base_min_limit': -260.0},
            {'base_max_limit': 135.0},
            {'enable_base_wraparound': True}
        ],
        condition=IfCondition(PythonExpression(["'", test_mode, "' == 'behavior' and '", enable_collision_avoidance, "' == 'true'"]))
    )
    
    # VoiceFollowingNode - Voice direction following and head tracking
    voice_following_node = Node(
        package='luxo_behaviors',
        executable='voice_following_node',
        name='voice_following',
        output='screen',
        parameters=[
            # Main voice following parameters
            {'enable_voice_following': enable_voice_following},
            {'voice_follow_speed': 0.3},
            {'voice_follow_deadzone': 15.0},
            {'voice_follow_smoothing': 0.3},
            
            # Voice variation parameters
            {'voice_variation_enabled': True},
            {'voice_direction_tolerance': 5.0},
            {'voice_variation_interval': 2.0},
            {'voice_look_up_range': 1.0},
            {'voice_look_down_range': 0.2},
            {'voice_on_target_threshold': 3.0},
            
            # Base rotation limits
            {'base_min_limit': -260.0},
            {'base_max_limit': 135.0},
            {'enable_base_wraparound': True},
            
            # Timing
            {'voice_timeout': 2.0},
            {'voice_influence_decay_rate': 0.8},
            {'voice_influence_gain': 0.8}
        ],
        condition=IfCondition(PythonExpression(["'", test_mode, "' == 'behavior' and '", enable_voice_following, "' == 'true'"]))
    )
    
    # IdleBehaviorNode - Idle animations and behaviors
    idle_behavior_node = Node(
        package='luxo_behaviors',
        executable='idle_behavior_node',
        name='idle_behavior',
        output='screen',
        parameters=[
            # Idle animation parameters
            {'idle_animations_enabled': True},
            {'min_idle_time_before_animation': 5.0},
            {'idle_animation_interval_min': 10.0},
            {'idle_animation_interval_max': 60.0},
            {'extended_idle_timeout': 120.0},
            
            # Idle head variation parameters
            {'idle_head_variation_enabled': True},
            {'idle_head_variation_interval_min': 3.5},
            {'idle_head_variation_interval_max': 10.0},
            {'idle_head_base_rotation_range': 0.3},
            {'idle_head_look_up_range': 0.4},
            {'idle_head_look_down_range': 0.1},
            {'idle_head_variation_speed': 4.0},
            
            # Home position parameters
            {'enable_home_position': True},
            {'home_position_timeout': 30.0},
            
            # Rest position parameters
            {'enable_rest_position': True},
            {'rest_variation_range': 0.05},
            
            # Activity tracking
            {'activity_timeout_min': 45.0},
            {'activity_timeout_max': 90.0}
        ],
        condition=IfCondition(PythonExpression(["'", test_mode, "' == 'behavior' and '", enable_idle_behaviors, "' == 'true'"]))
    )
    
    # PettingResponseNode - Petting detection and response behaviors
    petting_response_node = Node(
        package='luxo_behaviors',
        executable='petting_response_node',
        name='petting_response',
        output='screen',
        parameters=[
            # Petting response parameters
            {'petting_message_timeout': 5.0},
            {'petting_animation_cooldown': 8.0},
            {'startup_grace_period': 10.0},
            {'petting_animations': ['folded_wiggle']},
            {'enable_petting_response': enable_petting_response},
            {'max_petting_intensity': 100},
            {'min_petting_pressure': 2}
        ],
        condition=IfCondition(PythonExpression(["'", test_mode, "' == 'behavior' and '", enable_petting_response, "' == 'true'"]))
    )

    # System completion message
    completion_message = LogInfo(
        msg=["\n✅ MODULAR BEHAVIOR SYSTEM LAUNCH COMPLETE\n",
             "- Mode: ", PythonExpression(["'Hardware' if '", use_hardware, "' == 'true' else 'Simulation'"]), "\n",
             "- Test mode: ", test_mode, "\n",
             "- Behavior nodes: ", PythonExpression(["'Active' if '", test_mode, "' == 'behavior' else 'Inactive'"]), "\n",
             "- For help, run with 'verbose:=true'\n",
             "- Monitor system: ros2 topic echo /safety/system_status\n",
             "- Stop system: Ctrl+C\n"]
    )
    
    # Create and return launch description
    return LaunchDescription([
        # Launch arguments
        declare_use_hardware,
        declare_use_camera,
        declare_enable_emotion_detection,
        declare_use_gui,
        use_joint_state_publisher_arg,
        declare_test_mode,
        declare_enable_voice,
        declare_enable_voice_following,
        declare_enable_depth_collision,
        declare_safety_distance,
        declare_sense_collision,
        declare_enable_gestures,
        declare_verbose,
        declare_camera_rotation,
        declare_enable_dynamic_adaptation,
        declare_system_monitor,
        declare_enable_idle_behaviors,
        declare_enable_petting_response,
        declare_enable_collision_avoidance,
        
        # Launch info and banners
        startup_banner,
        mode_info,
        behavior_system_info,
        hardware_info,
        simulation_info,
        quick_reference,
        camera_info,
        i2c_info,
        troubleshooting_info,
        
        # Launch files
        roarm_launch,
        robot_state_publisher_node,
        jsp_killer,
        
        # Hardware interface and sensor nodes
        hardware_interface_node,
        i2c_device_manager_node,
        voice_direction_node,
        collision_logic_node,
        system_monitor_node,
        collision_detection_node,
        camera_interaction_node,
        
        # Test mode nodes (legacy support)
        position_test_node,
        hardware_animation_node,
        simulation_animation_node,
        
        # Modular behavior system nodes
        safety_coordinator_node,
        collision_monitor_node,
        voice_following_node,
        idle_behavior_node,
        petting_response_node,
        
        # Final info
        completion_message,
        show_nodes_cmd
    ])