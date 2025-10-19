#!/bin/bash

# Request SHUTDOWN state transition via ROS2 service
# This triggers the complete shutdown sequence:
# 1. Move to sleep position
# 2. Turn off lights and pixel ring
# 3. Enable DEMA mode
# 4. Disable torque

# Source ROS2 setup files
source /opt/ros/jazzy/setup.bash
source /home/pi/luxopi-ros/install/setup.bash

echo "🛑 Requesting SHUTDOWN state transition..."

# Request SHUTDOWN state with high priority and force flag
timeout 10s ros2 service call /luxo/request_state_transition \
    luxo_interfaces/srv/RequestStateTransition \
    "{requested_state: 'SHUTDOWN', requesting_node: 'shutdown_script', priority: 100, force: true}"

# Check if the service call was successful
if [ $? -eq 0 ]; then
    echo "✅ SHUTDOWN state requested successfully"
    echo "⏳ Waiting for shutdown sequence to complete (estimated 8 seconds)..."
    sleep 8
    echo "✅ Shutdown sequence complete"
    exit 0
else
    echo "❌ Failed to request SHUTDOWN state"
    exit 1
fi
