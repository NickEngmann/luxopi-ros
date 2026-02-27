import os
import subprocess
import sys

# Source ROS2 setup before tests run
def pytest_configure(config):
    """Source ROS2 setup file before running tests."""
    ros_setup = "/opt/ros/humble/setup.bash"
    if os.path.exists(ros_setup):
        # Source the setup file in a subprocess to get environment variables
        cmd = f"bash -c 'source {ros_setup} && env'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() not in ['PWD', '_', 'SHLVL', 'OLDPWD']:
                        os.environ[key.strip()] = value.strip()
