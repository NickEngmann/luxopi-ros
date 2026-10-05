#!/usr/bin/env python3
from setuptools import setup
import os
from glob import glob

package_name = 'luxo_behaviors'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name, package_name + '.animation_plugins'],
    package_data={package_name: [
        'simulator_ui.html',
        'assets/vendor/*.js',
        'assets/vendor/*.txt',
        'assets/roarm_m3/*',
        'assets/roarm_m3/**/*',
    ]},
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Add the launch files
        (os.path.join('share', package_name, 'launch'), 
         glob(os.path.join('launch', '*.launch.py'))),
        (os.path.join('share', package_name, 'config'),
         glob(os.path.join('config', '*.yaml'))),
        (os.path.join('share', package_name, 'worlds'),
         glob(os.path.join('worlds', '*.sdf'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='cyril',
    maintainer_email='cyril@thegarage.dev',
    description='Luxo Jr-style animations for RoArm-M3',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'voice_direction_node = luxo_behaviors.voice_direction_node:main',
            'i2c_device_manager = luxo_behaviors.i2c_device_manager:main',
            'collision_ros_node = luxo_behaviors.collision_ros_node:main',
            'animation_command = luxo_behaviors.animation_command:main',
            'system_monitor = luxo_behaviors.system_monitor:main',
            'camera_interaction = luxo_behaviors.camera_interaction:main',
            'demo_mode = luxo_behaviors.demo_mode:main',
            'hardware_interface = luxo_behaviors.hardware_interface:main',
            'state_manager = luxo_behaviors.state_manager_node:main',
            'collision_detection = luxo_behaviors.collision_detection:main',
            'animation_action_client = luxo_behaviors.animation_action_client:main',
            'watchdog = luxo_behaviors.watchdog_node:main',
            'speech_bridge = luxo_behaviors.speech_bridge:main',
            'sim_direction_node = luxo_behaviors.sim_direction_node:main',
            'sim_motion_controller = luxo_behaviors.sim_motion_controller:main',
            'physics_command_bridge = luxo_behaviors.physics_command_bridge:main',
            'simulator_dashboard = luxo_behaviors.simulator_dashboard:main',
            'mujoco_simulator = luxo_behaviors.mujoco_simulator:main',
            'sim_world_sensors = luxo_behaviors.sim_world_sensors:main',
            'sim_camera_interaction = luxo_behaviors.sim_camera_interaction:main',
            'sim_interaction_adapter = luxo_behaviors.sim_interaction_adapter:main',
        ],
    },
)
