#!/usr/bin/env python3
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, LogInfo, ExecuteProcess, RegisterEventHandler, Shutdown
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # Launch arguments with better defaults for simulation
    use_hardware = LaunchConfiguration('use_hardware', default='false')
    
    # Set default values based on hardware or simulation mode
    use_camera = LaunchConfiguration('use_camera')
    sense_collision = LaunchConfiguration('sense_collision')
    enable_depth_collision = LaunchConfiguration('enable_depth_collision')
    test_mode = LaunchConfiguration('test_mode', default='animation')
    
    # Other standard arguments with simplified defaults
    use_gui = LaunchConfiguration('use_gui', default='false')
    use_rviz = LaunchConfiguration('use_rviz', default='true')
    safety_distance = LaunchConfiguration('safety_distance', default='0.3')
    verbose_output = LaunchConfiguration('verbose', default='false')
    
    # Add dynamic adaptation parameters - now defaults based on hardware
    enable_dynamic_adaptation = LaunchConfiguration('enable_dynamic_adaptation')
    
    # Add gesture detection parameter
    enable_gestures = LaunchConfiguration('enable_gestures')
    
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
        default_value=PythonExpression(["'true' if '", use_hardware, "' == 'false' else 'false'"]),
        description='Enable gesture passthrough (simulated inputs in simulation; APDS9960 on hardware)'
    )

    declare_enable_sim_sensors = DeclareLaunchArgument(
        'enable_sim_sensors', default_value='true',
        description='Run ROS-only collision and gesture classification on synthetic sensor topics'
    )
    declare_enable_simulator_dashboard = DeclareLaunchArgument(
        'enable_simulator_dashboard',
        default_value=PythonExpression(["'true' if '", use_hardware, "' == 'false' else 'false'"]),
        description='Enable the browser simulator dashboard (simulation only)'
    )
    declare_enable_sim_vision = DeclareLaunchArgument(
        'enable_sim_vision',
        default_value=PythonExpression(["'true' if '", use_hardware, "' == 'false' else 'false'"]),
        description='Enable the shared-policy simulated camera consumer (simulation only)'
    )
    declare_enable_sim_interactions = DeclareLaunchArgument(
        'enable_sim_interactions',
        default_value=PythonExpression(["'true' if '", use_hardware, "' == 'false' else 'false'"]),
        description='Enable simulation-only voice session and touch/petting state consumers'
    )
    declare_simulator_host = DeclareLaunchArgument(
        'simulator_host', default_value='0.0.0.0', description='Browser simulator bind address'
    )
    declare_simulator_port = DeclareLaunchArgument(
        'simulator_port', default_value='8080', description='Browser simulator HTTP port'
    )
    declare_simulator_audio_directory = DeclareLaunchArgument(
        'simulator_audio_directory', default_value='',
        description='Optional shared directory for bounded WAV upload/ASR testing'
    )
    declare_joint_profile = DeclareLaunchArgument(
        'joint_profile', default_value='urdf4',
        description='Simulation joint profile: checked-in four-axis urdf4 or canonical six-axis roarm_m3'
    )
    declare_simulation_backend = DeclareLaunchArgument(
        'simulation_backend', default_value='kinematic',
        description='Simulation motion transport: kinematic or mujoco'
    )
    declare_robot_description_file = DeclareLaunchArgument(
        'robot_description_file',
        default_value=PathJoinSubstitution([FindPackageShare('roarm'), 'urdf', 'roarm.urdf']),
        description='URDF path for robot_state_publisher; physics launcher supplies generated M3 URDF'
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

    declare_use_rviz = DeclareLaunchArgument(
        name='use_rviz',
        default_value='true',
        description='Whether to launch RViz in simulation mode (disable for headless runs)'
    )
    
    # Fix for joint_state_publisher issue - set a default value that doesn't 
    # require the joint_state_publisher package if not available
    use_joint_state_publisher_arg = DeclareLaunchArgument(
        'use_joint_state_publisher',
        default_value='false',  # Always default to false
        description='Use the joint_state_publisher'
    )
    
    declare_test_mode = DeclareLaunchArgument(
        'test_mode',
        default_value='animation',
        description='Test mode: "position" for position_test or "animation" for animation_command'
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
    
    declare_enable_voice = DeclareLaunchArgument(
        'enable_voice',
        default_value='true',
        description='Enable voice direction detection and following'
    )

    declare_enable_speech_bridge = DeclareLaunchArgument(
        'enable_speech_bridge',
        default_value=PythonExpression(["'true' if '", use_hardware, "' == 'false' else 'false'"]),
        description='Enable silent speech bridge (simulation default; hardware opt-in)'
    )
    declare_speech_backend = DeclareLaunchArgument(
        'speech_backend', default_value='simulation',
        description='Speech backend: deterministic simulation or local JSONL service'
    )
    declare_speech_service_command = DeclareLaunchArgument(
        'speech_service_command', default_value='[]',
        description='Local service command as JSON argv (no shell)'
    )
    declare_speech_service_cwd = DeclareLaunchArgument(
        'speech_service_cwd', default_value='',
        description='Optional local JSONL service working directory'
    )
    declare_speech_service_timeout = DeclareLaunchArgument(
        'speech_service_timeout', default_value='15.0',
        description='Local JSONL service request timeout'
    )
    declare_speech_event_socket = DeclareLaunchArgument(
        'speech_event_socket', default_value='',
        description='Optional same-user Unix datagram live assistant event socket'
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
    
    declare_watchdog = DeclareLaunchArgument(
        'enable_watchdog',
        default_value='true',
        description='Enable watchdog for detecting stuck nodes'
    )
    
    declare_watchdog_state_timeout = DeclareLaunchArgument(
        'watchdog_state_timeout',
        default_value='30.0',
        description='Seconds without state updates before triggering recovery'
    )
    
    declare_watchdog_joint_timeout = DeclareLaunchArgument(
        'watchdog_joint_timeout',
        default_value='25.0',
        description='Seconds without joint updates before triggering recovery'
    )
    # ==========================================================================
    # LOGGING ACTIONS
    # ==========================================================================
    
    # Initial startup banner
    startup_banner = LogInfo(msg=["="*80, 
                                  "\n\n🚀 STARTING LUXOPI ROS SYSTEM\n",
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
                            ])
    
    # Hardware-specific info
    hardware_info = LogInfo(
        msg=["\n🔧 HARDWARE MODE DETAILS:\n",
             "- Serial port: /dev/ttyAMA0 (baud: 115200)\n",
             "- Test mode: ", test_mode, " (position=basic movements, animation=complex behaviors)\n",
             "- I2C sensing: ", PythonExpression(["'enabled' if '", sense_collision, "' == 'true' else 'disabled'"]), "\n",
             "- Hardware joint states enabled\n"],
        condition=IfCondition(use_hardware)
    )
    
    state_manager_info = LogInfo(
        msg=["\n🎯 STATE MANAGER:\n",
            "- Centralized state coordination enabled\n",
            "- Publishing to: /luxo/current_state\n",
            "- Service: /luxo/request_state_transition\n"],
    )

    # Simulation-specific info
    simulation_info = LogInfo(
        msg=["\n🖥️ SIMULATION MODE DETAILS:\n",
             "- Using RoArm simulation backend\n",
             "- GUI enabled: ", use_gui, "\n",
             "- Test mode: animation (using standard animation_command node)\n",
             "- Running with standard joint names\n"],
        condition=UnlessCondition(use_hardware)
    )
    
    # Quick reference for common launch commands
    quick_reference = LogInfo(
        msg=["\n📝 QUICK REFERENCE:\n",
             "- Hardware mode: ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true\n",
             "- Basic simulation: ros2 launch luxo_behaviors luxo_system.launch.py\n",
             "- Simulation with GUI: ros2 launch luxo_behaviors luxo_system.launch.py use_gui:=true\n",
             "- Hardware with collision: ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true enable_depth_collision:=true\n",
             "- Hardware with gestures: ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true enable_gestures:=true\n"],
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
             "- Package not found error? Install the package or disable the feature\n",
             "- View topics with: ros2 topic list\n",
             "- Check node status with: ros2 node list\n",
             "- Monitor joint states: ros2 topic echo /joint_states\n",
             "- View TF tree: ros2 run tf2_tools view_frames\n"],
        condition=IfCondition(verbose_output)
    )
    
    # Show active nodes at end of startup
    show_nodes_cmd = ExecuteProcess(
        cmd=["bash", "-c", "echo '📊 ACTIVE NODES:' && sleep 2 && ros2 node list"],
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
            'use_joint_state_publisher': 'false',
            'use_robot_state_pub': 'false',
            'use_rviz': use_rviz,
        }.items(),
        condition=UnlessCondition(use_hardware)
    )
    
    jsp_killer = ExecuteProcess(
        cmd=["bash", "-c", "sleep 5 && pkill -f \"/opt/ros/jazzy/lib/joint_state_publisher/joint_state_publisher\" || true"],
        output='screen',
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'false' and '", use_gui, "' == 'true'"]))
    )

    # Make sure robot_state_publisher has priority and runs even with camera enabled
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': Command(['cat ', LaunchConfiguration('robot_description_file')]),
            'publish_frequency': 30.0,
            # Ensure this is the root frame
            'frame_prefix': '',
            'use_sim_time': False
        }],
        # Always run this node regardless of other settings
        condition=UnlessCondition(use_hardware)
    )
    
    
    # ==========================================================================
    # NODE DEFINITIONS
    # ==========================================================================
    
    # State Manager node - runs in both hardware and simulation
    state_manager_node = Node(
        package='luxo_behaviors',
        executable='state_manager',
        name='state_manager',
        output='screen',
        parameters=[
            {'ros__parameters': {'log_level': 'info'}},
            {'simulated_lighting': PythonExpression([
                "'true' if '", use_hardware, "' == 'false' else 'false'"
            ])},
        ]
        # No condition - runs in both hardware and simulation modes
    )
    # Hardware interface node (hardware only)
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
            {'enable_dynamic_adaptation': enable_dynamic_adaptation},
            # better values for actually moving the robot
            # {'dynamic_adaptation_base_limit': 60},
            # {'dynamic_adaptation_shoulder_limit': 750},
            # {'dynamic_adaptation_elbow_limit': 50}, 
            # {'dynamic_adaptation_wrist_limit': 50},
            # {'dynamic_adaptation_roll_limit': 50},
            # {'dynamic_adaptation_hand_limit': 50},
            # values for sleep mode
            {'dynamic_adaptation_base_limit': 50},
            {'dynamic_adaptation_shoulder_limit': 50},
            {'dynamic_adaptation_elbow_limit': 50}, 
            {'dynamic_adaptation_wrist_limit': 50},
            {'dynamic_adaptation_roll_limit': 50},
            {'dynamic_adaptation_hand_limit': 50},
            {'enable_movement_source_integration': True},  # Explicitly enable movement source integration
            {'ros__parameters': {'log_level': 'error'}},
            {'enable_voice_following': LaunchConfiguration('enable_voice')},
            {'voice_follow_speed': 0.3},
            {'voice_follow_deadzone': 15.0},
            {'voice_follow_smoothing': 0.3}
        ],
        condition=IfCondition(use_hardware)
    )
    
    # I2C Device Manager node (hardware only, replaces direct APDS9960 node)
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
            {'publish_rate': 10.0}  
        ],
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'true' and '", sense_collision, "' == 'true'"]))
    )
    
    # Watchdog node for monitoring system health
    watchdog_node = Node(
        package='luxo_behaviors',
        executable='watchdog',
        name='watchdog',
        output='screen',
        parameters=[
            {'state_timeout': LaunchConfiguration('watchdog_state_timeout')},
            {'joint_timeout': LaunchConfiguration('watchdog_joint_timeout')},
            {'recovery_delay': 10.0},  # seconds between recovery attempts
            {'max_recovery_attempts': 3},
            {'enable_node_restart': False},
            {'enable_state_recovery': use_hardware},
            {'monitor_only': PythonExpression([
                "'false' if '", use_hardware, "' == 'true' else 'true'"
            ])},
        ],
        condition=IfCondition(LaunchConfiguration('enable_watchdog'))
    )
    
    voice_direction_node = Node(
        package='luxo_behaviors',
        executable='voice_direction_node',
        name='voice_direction_node',
        output='screen',
        parameters=[
            {'sample_rate': 16000},
            {'channels': 4},  # or 8 depending on your ReSpeaker model
            {'vad_aggressiveness': 3},
            {'confidence_threshold': 0.5},
            {'enable_pixel_ring': True},
            {'enable_voice_following': True},
            {'direction_smoothing_window': 5},
            {'min_report_interval': 0.5}
        ],
        condition=IfCondition(PythonExpression([
            "'", use_hardware, "' == 'true' and '", LaunchConfiguration('enable_voice'), "' == 'true'"
        ]))
    )

    sim_direction_node = Node(
        package='luxo_behaviors',
        executable='sim_direction_node',
        name='sim_direction_node',
        output='screen',
        condition=IfCondition(PythonExpression([
            "'", use_hardware, "' == 'false' and '", LaunchConfiguration('enable_voice'), "' == 'true'"
        ]))
    )

    speech_bridge_node = Node(
        package='luxo_behaviors',
        executable='speech_bridge',
        name='speech_bridge',
        output='screen',
        parameters=[{
            'backend': LaunchConfiguration('speech_backend'),
            'service_command': ParameterValue(
                LaunchConfiguration('speech_service_command'), value_type=str
            ),
            'service_cwd': ParameterValue(
                LaunchConfiguration('speech_service_cwd'), value_type=str
            ),
            'service_timeout': LaunchConfiguration('speech_service_timeout'),
            'event_socket': ParameterValue(
                LaunchConfiguration('speech_event_socket'), value_type=str
            ),
            'audio_directory': LaunchConfiguration('simulator_audio_directory'),
        }],
        condition=IfCondition(LaunchConfiguration('enable_speech_bridge'))
    )

    sim_motion_controller_node = Node(
        package='luxo_behaviors',
        executable='sim_motion_controller',
        name='sim_motion_controller',
        output='screen',
        parameters=[
            {'publish_rate': 50.0},
            {'max_joint_velocity': 0.5},
            {'max_joint_acceleration': 1.0},
            {'voice_follow_priority': 75},
            {'joint_profile': LaunchConfiguration('joint_profile')},
            {'publish_joint_states': PythonExpression([
                "'false' if '", LaunchConfiguration('simulation_backend'), "' in ('gazebo', 'mujoco') else 'true'"
            ])},
            {'command_topic': '/sim/bounded_joint_command'},
        ],
        condition=UnlessCondition(use_hardware)
    )

    simulator_dashboard_node = Node(
        package='luxo_behaviors',
        executable='simulator_dashboard',
        name='simulator_dashboard',
        output='screen',
        parameters=[{
            'host': LaunchConfiguration('simulator_host'),
            'port': LaunchConfiguration('simulator_port'),
            'audio_directory': LaunchConfiguration('simulator_audio_directory'),
        }],
        condition=IfCondition(PythonExpression([
            "'", use_hardware, "' == 'false' and '", LaunchConfiguration('enable_simulator_dashboard'), "' == 'true'"
        ]))
    )

    sim_camera_interaction_node = Node(
        package='luxo_behaviors',
        executable='sim_camera_interaction',
        name='sim_camera_interaction',
        output='screen',
        condition=IfCondition(PythonExpression([
            "'", use_hardware, "' == 'false' and '",
            LaunchConfiguration('enable_sim_vision'), "' == 'true'"
        ]))
    )

    sim_interaction_adapter_node = Node(
        package='luxo_behaviors',
        executable='sim_interaction_adapter',
        name='sim_interaction_adapter',
        output='screen',
        parameters=[{'petting_timeout': 5.0}],
        condition=IfCondition(PythonExpression([
            "'", use_hardware, "' == 'false' and '",
            LaunchConfiguration('enable_sim_interactions'), "' == 'true'"
        ]))
    )

    # Collision detection logic node (hardware only, now uses I2C manager data)
    collision_logic_node = Node(
        package='luxo_behaviors',
        executable='collision_ros_node',
        name='collision_node',
        output='screen',
        parameters=[
            {'proximity_threshold': 15},
            {'side_distance_threshold': 8.0},
            {'danger_threshold': 5.0},
            {'warning_threshold': 15.0},
            {'enable_gestures': enable_gestures}
        ],
        condition=IfCondition(PythonExpression([
            "'", use_hardware, "' == 'true' and '", sense_collision,
            "' == 'true' or '", use_hardware, "' == 'false' and '", LaunchConfiguration('enable_sim_sensors'), "' == 'true'"
        ]))
    )

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
    
    # Position test node - basic movement patterns (hardware only)
    position_test_node = Node(
        package='luxo_behaviors',
        executable='position_test',
        name='position_test',
        output='screen',
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'true' and '", test_mode, "' == 'position'"]))
    )
    
    # Animation command node (hardware version)
    hardware_animation_node = Node(
        package='luxo_behaviors',
        executable='animation_command',
        name='animation_command',
        output='screen',
        parameters=[
            {'publish_joint_states_target': True},
            {'use_hardware_joint_names': True},
            {'publish_target_topic': True},  # Hardware should use target topic
            {'enforce_joint_limits': True},   # Enable joint limits enforcement
            {'use_hardware_position_feedback': True}  # Enable hardware position feedback in hardware mode
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
            {'publish_joint_states_target': True},
            {'publish_target_topic': True},
            {'enforce_joint_limits': True},    # Enable joint limits enforcement
            {'joint_profile': LaunchConfiguration('joint_profile')},
            {'enable_collision_warning_inputs': True},
        ],
        condition=UnlessCondition(use_hardware)
    )

    # Collision detection node (depth-based)
    collision_detection_node = Node(
        package='luxo_behaviors',
        executable='collision_detection',
        name='collision_detection',
        output='screen',
        parameters=[
            {'safety_distance': safety_distance},
            {'robot_base_frame': 'base_link'},
            {'point_cloud_topic': '/oak/points'},
            {'joint_states_topic': '/joint_states'},
            {'override_animation': True},
            {'qos_reliability': 0},  # 0=BEST_EFFORT, 1=RELIABLE
            {'qos_durability': 0},   # 0=VOLATILE, 1=TRANSIENT_LOCAL
        ],
        condition=IfCondition(PythonExpression([
            "'", use_hardware, "' == 'true' and '", enable_depth_collision, "' == 'true'"
        ]))
    )
    
    # Camera interaction node (requires camera) - now with emotion detection capability
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
        condition=IfCondition(PythonExpression([
            "'", use_hardware, "' == 'true' and '", use_camera, "' == 'true'"
        ]))
    )
    

    # System completion message
    completion_message = LogInfo(
        msg=["\n✅ SYSTEM LAUNCH COMPLETE\n",
             "- Mode: ", PythonExpression(["'Hardware' if '", use_hardware, "' == 'true' else 'Simulation'"]), "\n",
             "- For help, run with 'verbose:=true'\n",
             "- Common commands: \n",
             "  • View topics: ros2 topic list\n",
             "  • View nodes: ros2 node list\n",
             "  • Monitor I2C health: ros2 topic echo /i2c/sensor_health\n",
             "  • Stop system: Ctrl+C\n"]
    )
    
    # Create and return launch description
    return LaunchDescription([
        # Launch arguments
        declare_use_hardware,
        declare_use_camera,
        declare_enable_emotion_detection,
        declare_use_gui,
        declare_use_rviz,
        use_joint_state_publisher_arg,
        declare_test_mode,
        declare_enable_voice,
        declare_enable_speech_bridge,
        declare_speech_backend,
        declare_speech_service_command,
        declare_speech_service_cwd,
        declare_speech_service_timeout,
        declare_speech_event_socket,
        declare_enable_depth_collision,
        declare_safety_distance,
        declare_sense_collision,
        declare_enable_gestures,
        declare_enable_sim_sensors,
        declare_enable_simulator_dashboard,
        declare_enable_sim_vision,
        declare_enable_sim_interactions,
        declare_simulator_host,
        declare_simulator_port,
        declare_simulator_audio_directory,
        declare_joint_profile,
        declare_simulation_backend,
        declare_robot_description_file,
        declare_verbose,
        declare_camera_rotation,
        declare_enable_dynamic_adaptation,
        declare_system_monitor,
        declare_watchdog,
        declare_watchdog_state_timeout,
        declare_watchdog_joint_timeout,
        
        # Launch info and banners
        startup_banner,
        mode_info,
        hardware_info,
        simulation_info,
        quick_reference,
        camera_info,
        i2c_info,
        troubleshooting_info,
        jsp_killer,
        # A missing motion/state/UI process leaves a misleading, half-live
        # simulator. Shut down the owned graph so Compose can recover it.
        RegisterEventHandler(OnProcessExit(
            target_action=state_manager_node,
            on_exit=[Shutdown(reason='critical state_manager exited')],
        )),
        RegisterEventHandler(OnProcessExit(
            target_action=sim_motion_controller_node,
            on_exit=[Shutdown(reason='critical sim_motion_controller exited')],
        )),
        RegisterEventHandler(OnProcessExit(
            target_action=simulation_animation_node,
            on_exit=[Shutdown(reason='critical animation_command exited')],
        )),
        RegisterEventHandler(OnProcessExit(
            target_action=simulator_dashboard_node,
            on_exit=[Shutdown(reason='critical simulator_dashboard exited')],
        )),
        RegisterEventHandler(OnProcessExit(
            target_action=speech_bridge_node,
            on_exit=[Shutdown(reason='critical speech_bridge exited')],
        )),
        voice_direction_node,
        sim_direction_node,
        speech_bridge_node,
        # Launch files
        roarm_launch,
        
        # Add robot_state_publisher with high priority (add before other nodes)
        robot_state_publisher_node,
        
        # Nodes
        hardware_interface_node,
        state_manager_node,
        position_test_node,
        hardware_animation_node,
        system_monitor_node,
        simulation_animation_node,
        sim_motion_controller_node,
        simulator_dashboard_node,
        sim_camera_interaction_node,
        sim_interaction_adapter_node,
        collision_detection_node,
        i2c_device_manager_node,
        collision_logic_node,
        camera_interaction_node,
        watchdog_node,
        # Final info
        completion_message,
        show_nodes_cmd
    ])
