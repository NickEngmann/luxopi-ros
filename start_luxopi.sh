#!/bin/bash

# =============================================================================
# LuxoPi Smart Launch Script - Enhanced for Modular Behavior System
# =============================================================================

# Exit on any error
set -e

# Configuration - Set defaults or use environment variables
export LUXOPI_USE_HARDWARE="${LUXOPI_USE_HARDWARE:-true}"
export LUXOPI_USE_CAMERA="${LUXOPI_USE_CAMERA:-false}"
export LUXOPI_ENABLE_EMOTION_DETECTION="${LUXOPI_ENABLE_EMOTION_DETECTION:-true}"
export LUXOPI_ENABLE_VOICE="${LUXOPI_ENABLE_VOICE:-true}"
export LUXOPI_VERBOSE="${LUXOPI_VERBOSE:-true}"
export LUXOPI_SENSE_COLLISION="${LUXOPI_SENSE_COLLISION:-true}"
export LUXOPI_ENABLE_GESTURES="${LUXOPI_ENABLE_GESTURES:-false}"
export LUXOPI_ENABLE_DEPTH_COLLISION="${LUXOPI_ENABLE_DEPTH_COLLISION:-false}"

# Modular Behavior System Configuration
export LUXOPI_TEST_MODE="${LUXOPI_TEST_MODE:-behavior}"  # behavior, animation, or position
export LUXOPI_ENABLE_VOICE_FOLLOWING="${LUXOPI_ENABLE_VOICE_FOLLOWING:-true}"
export LUXOPI_ENABLE_IDLE_BEHAVIORS="${LUXOPI_ENABLE_IDLE_BEHAVIORS:-true}"
export LUXOPI_ENABLE_PETTING_RESPONSE="${LUXOPI_ENABLE_PETTING_RESPONSE:-true}"
export LUXOPI_ENABLE_COLLISION_AVOIDANCE="${LUXOPI_ENABLE_COLLISION_AVOIDANCE:-true}"

# Advanced Configuration
export LUXOPI_ENABLE_DYNAMIC_ADAPTATION="${LUXOPI_ENABLE_DYNAMIC_ADAPTATION:-true}"
export LUXOPI_ENABLE_SYSTEM_MONITOR="${LUXOPI_ENABLE_SYSTEM_MONITOR:-true}"
export LUXOPI_CAMERA_ROTATION="${LUXOPI_CAMERA_ROTATION:-false}"
export LUXOPI_SAFETY_DISTANCE="${LUXOPI_SAFETY_DISTANCE:-0.3}"

# System Configuration
export LUXOPI_RESTART_DELAY="${LUXOPI_RESTART_DELAY:-5}"
export LUXOPI_MAX_RESTARTS="${LUXOPI_MAX_RESTARTS:-3}"  # Changed from 0 to 3 for safety
export LUXOPI_GRACEFUL_SHUTDOWN_TIMEOUT="${LUXOPI_GRACEFUL_SHUTDOWN_TIMEOUT:-15}"

# ROS2 Configuration
export DISPLAY=:0
export ROS_DOMAIN_ID=0

# Paths
LUXOPI_PATH="/home/pi/luxopi-ros"
ROS_SETUP="/opt/ros/jazzy/setup.bash"
LUXOPI_SETUP="${LUXOPI_PATH}/install/setup.bash"

# Logging - Use user-writable location
LOG_DIR="${LUXOPI_LOG_DIR:-${LUXOPI_PATH}/logs}"
LOG_FILE="${LOG_DIR}/luxopi-$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR" 2>/dev/null || true

# PID tracking for graceful shutdown
LAUNCH_PID=""

# =============================================================================
# Functions
# =============================================================================

log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $*" | tee -a "$LOG_FILE"
}

log_error() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

check_dependencies() {
    log "Checking dependencies..."
    
    if [[ ! -f "$ROS_SETUP" ]]; then
        log_error "ROS2 setup file not found at $ROS_SETUP"
        exit 1
    fi
    
    if [[ ! -d "$LUXOPI_PATH" ]]; then
        log_error "LuxoPi directory not found at $LUXOPI_PATH"
        exit 1
    fi
    
    # Check for required hardware permissions (if using hardware)
    if [[ "$LUXOPI_USE_HARDWARE" == "true" ]]; then
        if [[ ! -c "/dev/ttyAMA0" ]] && [[ ! -c "/dev/ttyS0" ]]; then
            log_error "Serial device not found. Check hardware connections."
            exit 1
        fi
        
        # Check I2C permissions
        if [[ "$LUXOPI_SENSE_COLLISION" == "true" ]] && [[ ! -c "/dev/i2c-1" ]]; then
            log_error "I2C device not found. Check I2C is enabled."
            exit 1
        fi
    fi
}

setup_environment() {
    log "Setting up ROS2 environment..."
    source "$ROS_SETUP"
    
    if [[ -f "$LUXOPI_SETUP" ]]; then
        source "$LUXOPI_SETUP"
    else
        log "WARNING: LuxoPi setup file not found, will build first"
    fi
}

build_workspace() {
    log "Building LuxoPi workspace..."
    cd "$LUXOPI_PATH"
    
    if ! colcon build --packages-select luxo_behaviors luxo_interfaces; then
        log_error "Failed to build workspace"
        exit 1
    fi
    
    # Source the newly built setup
    source "${LUXOPI_PATH}/install/setup.bash"
    log "Workspace built successfully"
}

get_launch_args() {
    local args=""
    
    # Basic system arguments
    args+="use_hardware:=$LUXOPI_USE_HARDWARE "
    args+="use_camera:=$LUXOPI_USE_CAMERA "
    args+="enable_emotion_detection:=$LUXOPI_ENABLE_EMOTION_DETECTION "
    args+="enable_voice:=$LUXOPI_ENABLE_VOICE "
    args+="verbose:=$LUXOPI_VERBOSE "
    args+="sense_collision:=$LUXOPI_SENSE_COLLISION "
    args+="enable_gestures:=$LUXOPI_ENABLE_GESTURES "
    args+="enable_depth_collision:=$LUXOPI_ENABLE_DEPTH_COLLISION "
    
    # Modular behavior system arguments
    args+="test_mode:=$LUXOPI_TEST_MODE "
    args+="enable_voice_following:=$LUXOPI_ENABLE_VOICE_FOLLOWING "
    args+="enable_idle_behaviors:=$LUXOPI_ENABLE_IDLE_BEHAVIORS "
    args+="enable_petting_response:=$LUXOPI_ENABLE_PETTING_RESPONSE "
    args+="enable_collision_avoidance:=$LUXOPI_ENABLE_COLLISION_AVOIDANCE "
    
    # Advanced configuration
    args+="enable_dynamic_adaptation:=$LUXOPI_ENABLE_DYNAMIC_ADAPTATION "
    args+="enable_system_monitor:=$LUXOPI_ENABLE_SYSTEM_MONITOR "
    args+="camera_rotation:=$LUXOPI_CAMERA_ROTATION "
    args+="safety_distance:=$LUXOPI_SAFETY_DISTANCE "
    
    echo "$args"
}

print_configuration() {
    log "=== LuxoPi Modular Behavior System Configuration ==="
    log "System Mode:"
    log "  Hardware: $LUXOPI_USE_HARDWARE"
    log "  Test Mode: $LUXOPI_TEST_MODE"
    log "  Camera: $LUXOPI_USE_CAMERA"
    log "  Verbose: $LUXOPI_VERBOSE"
    log ""
    log "Sensors:"
    log "  Collision Sensing: $LUXOPI_SENSE_COLLISION"
    log "  Gesture Detection: $LUXOPI_ENABLE_GESTURES"
    log "  Depth Collision: $LUXOPI_ENABLE_DEPTH_COLLISION"
    log "  Emotion Detection: $LUXOPI_ENABLE_EMOTION_DETECTION"
    log "  Voice Detection: $LUXOPI_ENABLE_VOICE"
    log ""
    log "Behavior Modules:"
    log "  Voice Following: $LUXOPI_ENABLE_VOICE_FOLLOWING"
    log "  Idle Behaviors: $LUXOPI_ENABLE_IDLE_BEHAVIORS"
    log "  Petting Response: $LUXOPI_ENABLE_PETTING_RESPONSE"
    log "  Collision Avoidance: $LUXOPI_ENABLE_COLLISION_AVOIDANCE"
    log ""
    log "Advanced:"
    log "  Dynamic Adaptation: $LUXOPI_ENABLE_DYNAMIC_ADAPTATION"
    log "  System Monitor: $LUXOPI_ENABLE_SYSTEM_MONITOR"
    log "  Safety Distance: $LUXOPI_SAFETY_DISTANCE m"
    log "  Camera Rotation: $LUXOPI_CAMERA_ROTATION"
    log "=============================================="
}

check_ros_nodes() {
    log "Checking for existing ROS2 nodes..."
    if ros2 node list 2>/dev/null | grep -q luxo; then
        log "WARNING: Existing LuxoPi nodes detected. Consider stopping them first."
        ros2 node list | grep luxo | while read node; do
            log "  Found: $node"
        done
    fi
}

launch_luxopi() {
    local args=$(get_launch_args)
    log "Launching LuxoPi with args: $args"
    
    # Start the launch in background to capture PID
    ros2 launch luxo_behaviors luxo_system.launch.py $args &
    LAUNCH_PID=$!
    
    log "LuxoPi launched with PID: $LAUNCH_PID"
    
    # Wait for the process
    wait $LAUNCH_PID
    local exit_code=$?
    
    LAUNCH_PID=""
    return $exit_code
}

setup_i2c() {
    if [[ "$LUXOPI_SENSE_COLLISION" == "true" ]]; then
        log "Configuring I2C for optimal performance..."
        # Ensure I2C is properly configured
        if command -v modprobe >/dev/null 2>&1; then
            # sudo modprobe i2c_bcm2708 baudrate=100000  # Standard 100kHz
            log "I2C configuration completed"
        fi
    fi
}

graceful_shutdown() {
    log "Initiating graceful shutdown..."
    
    if [[ -n "$LAUNCH_PID" ]]; then
        log "Sending shutdown signal to LuxoPi (PID: $LAUNCH_PID)"
        
        # Send close animation if in behavior mode
        if [[ "$LUXOPI_TEST_MODE" == "behavior" ]]; then
            log "Sending close animation..."
            timeout 5 ros2 topic pub --once /safety/system_command std_msgs/String "data: go_home" 2>/dev/null || true
            sleep 3
        fi
        
        # Send SIGTERM first for graceful shutdown
        kill -TERM "$LAUNCH_PID" 2>/dev/null || true
        
        # Wait for graceful shutdown
        local count=0
        while [[ $count -lt $LUXOPI_GRACEFUL_SHUTDOWN_TIMEOUT ]] && kill -0 "$LAUNCH_PID" 2>/dev/null; do
            sleep 1
            count=$((count + 1))
        done
        
        # Force kill if still running
        if kill -0 "$LAUNCH_PID" 2>/dev/null; then
            log "Force killing LuxoPi process..."
            kill -KILL "$LAUNCH_PID" 2>/dev/null || true
        fi
    fi
    
    # Clean up any remaining ROS nodes
    log "Cleaning up ROS2 nodes..."
    ros2 daemon stop 2>/dev/null || true
    
    log "Shutdown complete"
    exit 0
}

emergency_stop() {
    log "EMERGENCY STOP TRIGGERED!"
    
    # Send emergency stop command
    timeout 2 ros2 topic pub --once /safety/system_command std_msgs/String "data: emergency_stop" 2>/dev/null || true
    
    graceful_shutdown
}

# =============================================================================
# Signal Handlers
# =============================================================================

# Handle signals for graceful shutdown
trap graceful_shutdown SIGTERM SIGINT
trap emergency_stop SIGUSR1  # Custom emergency stop signal

# =============================================================================
# Main Script
# =============================================================================

log "Starting LuxoPi Modular Behavior System (PID: $$)"
print_configuration

# Pre-flight checks
check_dependencies
check_ros_nodes

# Setup environment
setup_environment

# Optional I2C setup
setup_i2c

# Build workspace
build_workspace

# Validate behavior mode configuration
if [[ "$LUXOPI_TEST_MODE" == "behavior" ]]; then
    log "Behavior mode enabled - all modular components will be available"
    if [[ "$LUXOPI_ENABLE_VOICE_FOLLOWING" == "false" ]] && 
       [[ "$LUXOPI_ENABLE_IDLE_BEHAVIORS" == "false" ]] && 
       [[ "$LUXOPI_ENABLE_PETTING_RESPONSE" == "false" ]] && 
       [[ "$LUXOPI_ENABLE_COLLISION_AVOIDANCE" == "false" ]]; then
        log "WARNING: All behavior modules disabled in behavior mode"
    fi
fi

# Main execution loop with restart capability
restart_count=0
while true; do
    if [[ $LUXOPI_MAX_RESTARTS -gt 0 ]] && [[ $restart_count -ge $LUXOPI_MAX_RESTARTS ]]; then
        log_error "Maximum restart limit ($LUXOPI_MAX_RESTARTS) reached. Exiting."
        exit 1
    fi
    
    if [[ $restart_count -gt 0 ]]; then
        log "Restart attempt #$restart_count"
        # Brief delay for system cleanup
        sleep 2
    fi
    
    # Launch the system
    if launch_luxopi; then
        log "LuxoPi exited normally"
        break
    else
        exit_code=$?
        log "LuxoPi exited with code $exit_code"
        
        if [[ $exit_code -eq 130 ]] || [[ $exit_code -eq 2 ]]; then  # SIGINT (Ctrl+C)
            log "Received interrupt signal, exiting..."
            break
        fi
        
        restart_count=$((restart_count + 1))
        log "Restarting in $LUXOPI_RESTART_DELAY seconds..."
        sleep "$LUXOPI_RESTART_DELAY"
    fi
done

log "LuxoPi launch script finished"