#!/usr/bin/env python3
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
    test_mode = LaunchConfiguration('test_mode', default='animation')
    
    # Other standard arguments
    run_demo = LaunchConfiguration('run_demo', default='false')
    use_gui = LaunchConfiguration('use_gui', default='false')
    safety_distance = LaunchConfiguration('safety_distance', default='0.3')
    verbose_output = LaunchConfiguration('verbose', default='false')
    
    # Add dynamic adaptation parameters
    enable_dynamic_adaptation = LaunchConfiguration('enable_dynamic_adaptation', default='false')
    
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
    
    # Emotion detection argument with conditional default (tied to camera availability)
    declare_enable_emotion_detection = DeclareLaunchArgument(
        'enable_emotion_detection',
        default_value=PythonExpression(["'false' if '", use_camera, "' == 'false' else 'true'"]),
        description='Enable emotion detection with camera (default: true when camera is enabled)'
    )
    
    # Proximity sensor argument with conditional default
    declare_sense_collision = DeclareLaunchArgument(
        'sense_collision',
        default_value=PythonExpression(["'false' if '", use_hardware, "' == 'false' else 'true'"]),
        description='Enable APDS9960 proximity sensor (default: true in hardware, false in simulation)'
    )
    
    # Depth collision argument with conditional default
    declare_enable_depth_collision = DeclareLaunchArgument(
        'enable_depth_collision',
        default_value=PythonExpression(["'false'"]),
        description='Enable depth-based collision detection (default: false)'
    )
    
    declare_run_demo = DeclareLaunchArgument(
        'run_demo',
        default_value='false',
        description='Whether to run the demo sequence'
    )
    
    declare_use_gui = DeclareLaunchArgument(
        name='use_gui',
        default_value='false',
        description='Flag to enable joint_state_publisher_gui'
    )
    
    # Fix for joint_state_publisher issue - set a default value that doesn't 
    # require the joint_state_publisher package if not available
    use_joint_state_publisher_arg = DeclareLaunchArgument(
        'use_joint_state_publisher',
        default_value='false',  # Changed from 'true' to 'false' to avoid dependency error
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
    
    # Add a launch argument for camera rotation
    declare_camera_rotation = DeclareLaunchArgument(
        'camera_rotation',
        default_value='false',
        description='Rotate camera image 180 degrees (set to true if camera is mounted upside down)'
    )
    
    # Dynamic adaptation argument
    declare_enable_dynamic_adaptation = DeclareLaunchArgument(
        'enable_dynamic_adaptation',
        default_value='false',
        description='Enable dynamic adaptation mode (external force control)'
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
                            "- Using proximity sensor: ", sense_collision, "\n",
                            "- Demo mode: ", run_demo, "\n"])
    
    # Hardware-specific info
    hardware_info = LogInfo(
        msg=["\n🔧 HARDWARE MODE DETAILS:\n",
             "- Serial port: /dev/ttyAMA0 (baud: 115200)\n",
             "- Test mode: ", test_mode, " (position=basic movements, animation=complex behaviors)\n",
             "- Proximity sensing: ", PythonExpression(["'enabled' if '", sense_collision, "' == 'true' else 'disabled'"]), "\n",
             "- Hardware joint states enabled\n"],
        condition=IfCondition(use_hardware)
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
             "- Hardware with collision: ros2 launch luxo_behaviors luxo_system.launch.py use_hardware:=true enable_depth_collision:=true\n"],
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
    
    # Demo mode info
    demo_info = LogInfo(
        msg=["\n🎬 DEMO MODE ACTIVE:\n",
             "- Running pre-programmed demo sequence\n",
             "- Other manual controls may be overridden\n"],
        condition=IfCondition(run_demo)
    )

    # Troubleshooting tips
    troubleshooting_info = LogInfo(
        msg=["\n🔍 TROUBLESHOOTING TIPS:\n",
             "- If hardware not responding, check serial connection and permissions\n",
             "- For camera issues, verify USB connection and permissions\n",
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
            'use_joint_state_publisher': 'false'  # Fixed value to avoid dependency issues
        }.items(),
        condition=UnlessCondition(use_hardware)
    )
    
    
    # Make sure robot_state_publisher has priority and runs even with camera enabled
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
            {'dynamic_adaptation_base_limit': 60},
            {'dynamic_adaptation_shoulder_limit': 800},
            {'dynamic_adaptation_elbow_limit': 800}, 
            {'dynamic_adaptation_wrist_limit': 800},
            {'dynamic_adaptation_roll_limit': 800},
            {'dynamic_adaptation_hand_limit': 800},
            {'dynamic_adaptation_resume_delay': 5.0},
            {'ros__parameters': {'log_level': 'error'}}
        ],
        condition=IfCondition(use_hardware)
    )
    
    # APDS9960 proximity and gesture sensor node (hardware only)
    apds9960_node = Node(
        package='luxo_behaviors',
        executable='collision_ros_node',
        name='apds9960_node',
        output='screen',
        parameters=[
            {'proximity_threshold': 5}
        ],
        condition=IfCondition(PythonExpression(["'", use_hardware, "' == 'true' and '", sense_collision, "' == 'true'"]))
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
            {'publish_joint_states': True},
            {'use_hardware_joint_names': True},
            {'publish_target_topic': True}  # Hardware should use target topic
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
            {'publish_target_topic': False}  # Simulation should use joint_states topic directly
        ],
        condition=UnlessCondition(use_hardware)
    )
    
    # Collision detection node
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
        condition=IfCondition(enable_depth_collision)
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
    
    # System completion message
    completion_message = LogInfo(
        msg=["\n✅ SYSTEM LAUNCH COMPLETE\n",
             "- Mode: ", PythonExpression(["'Hardware' if '", use_hardware, "' == 'true' else 'Simulation'"]), "\n",
             "- For help, run with 'verbose:=true'\n",
             "- Common commands: \n",
             "  • View topics: ros2 topic list\n",
             "  • View nodes: ros2 node list\n",
             "  • Stop system: Ctrl+C\n"]
    )
    
    # Create and return launch description
    return LaunchDescription([
        # Launch arguments
        declare_use_hardware,
        declare_use_camera,
        declare_enable_emotion_detection,
        declare_run_demo,
        declare_use_gui,
        use_joint_state_publisher_arg,
        declare_test_mode,
        declare_enable_depth_collision,
        declare_safety_distance,
        declare_sense_collision,
        declare_verbose,
        declare_camera_rotation,  # Add the camera rotation argument
       declare_enable_dynamic_adaptation,
        # Launch info and banners
        startup_banner,
        mode_info,
        hardware_info,
        simulation_info,
        quick_reference,
        camera_info,
        demo_info,
        troubleshooting_info,
        
        # Launch files
        roarm_launch,
        
        # Add robot_state_publisher with high priority (add before other nodes)
        robot_state_publisher_node,
        
        # Nodes
        hardware_interface_node,
        position_test_node,
        hardware_animation_node,
        simulation_animation_node,
        collision_detection_node,
        apds9960_node,
        camera_interaction_node,
        demo_node,
        
        # Final info
        completion_message,
        show_nodes_cmd
    ])