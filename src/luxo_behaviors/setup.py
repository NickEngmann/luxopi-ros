#!/usr/bin/env python3
from setuptools import setup
import os
from glob import glob

package_name = 'luxo_behaviors'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name, package_name + '.animation_plugins'],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Add the launch files
        (os.path.join('share', package_name, 'launch'), 
         glob(os.path.join('launch', '*.launch.py'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='cyril',
    maintainer_email='cyril@thegarage.dev',
    description='Luxo Jr-style animations for RoArm-M3',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'voice_direction_node = luxo_behaviors.voice_direction_node:main',
            'i2c_device_manager = luxo_behaviors.i2c_device_manager:main',
            'collision_ros_node = luxo_behaviors.collision_ros_node:main',
            'animation_command = luxo_behaviors.animation_command:main',
            'camera_interaction = luxo_behaviors.camera_interaction:main',
            'demo_mode = luxo_behaviors.demo_mode:main',
            'hardware_interface = luxo_behaviors.hardware_interface:main',
            'collision_detection = luxo_behaviors.collision_detection:main',
            'animation_action_client = luxo_behaviors.animation_action_client:main',
        ],
    },
)
