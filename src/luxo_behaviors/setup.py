#!/usr/bin/env python3
from setuptools import setup
import os
from glob import glob

package_name = 'luxo_behaviors'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
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
    maintainer='user',
    maintainer_email='user@example.com',
    description='Luxo Jr-style animations for RoArm-M2-S',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'arm_controller = luxo_behaviors.arm_controller:main',
            'animation_command = luxo_behaviors.animation_command:main',
            'camera_interaction = luxo_behaviors.camera_interaction:main',
            'demo_mode = luxo_behaviors.demo_mode:main',
        ],
    },
)