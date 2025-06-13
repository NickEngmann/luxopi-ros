#!/bin/bash

# =============================================================================
# LuxoPi Smart Launch Script
# =============================================================================

# Exit on any error
set -e

# Configuration - Set defaults or use environment variables
export LUXOPI_USE_HARDWARE="${LUXOPI_USE_HARDWARE:-true}"
export LUXOPI_USE_CAMERA="${LUXOPI_USE_CAMERA:-true}"
export LUXOPI_ENABLE_EMOTION_DETECTION="${LUXOPI_ENABLE_EMOTION_DETECTION:-false}"
export LUXOPI_ENABLE_VOICE="${LUXOPI_ENABLE_VOICE:-false}"
export LUXOPI_ENABLE_ADS7830="${LUXOPI_ENABLE_ADS7830:-true}"
export LUXOPI_VERBOSE="${LUXOPI_VERBOSE:-true}"
export LUXOPI_ENABLE_IDLE_ANIMATIONS="${LUXOPI_ENABLE_IDLE_ANIMATIONS:-true}"
export LUXOPI_ENABLE_DYNAMIC_ADAPTATION="${LUXOPI_ENABLE_DYNAMIC_ADAPTATION:-false}"
export LUXOPI_ENABLE_FRAMEBUFFER_DISPLAY="${LUXOPI_ENABLE_FRAMEBUFFER_DISPLAY:-true}"
export LUXOPI_SENSE_COLLISION="${LUXOPI_SENSE_COLLISION:-true}"
export LUXOPI_RESTART_DELAY="${LUXOPI_RESTART_DELAY:-5}"
export LUXOPI_MAX_RESTARTS="${LUXOPI_MAX_RESTARTS:-0}"  # 0 = unlimited

# ROS2 Configuration
export DISPLAY=:0
export ROS_DOMAIN_ID=0

# Paths
LUXOPI_PATH="/home/pi/luxopi-ros"
ROS_SETUP="/opt/ros/jazzy/setup.bash"
LUXOPI_SETUP="${LUXOPI_PATH}/install/setup.bash"

# Logging - Use user-writable location
LOG_DIR="${LUXOPI_LOG_DIR:-${LUXOPI_PATH}/logs}"
LOG_FILE="${LOG_DIR}/luxopi.log"
mkdir -p "$LOG_DIR" 2>/dev/null || true

# =============================================================================
# Functions
# =============================================================================

log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $*" | tee -a "$LOG_FILE"
}

check_dependencies() {
    log "Checking dependencies..."
    
    if [[ ! -f "$ROS_SETUP" ]]; then
        log "ERROR: ROS2 setup file not found at $ROS_SETUP"
        exit 1
    fi
    
    if [[ ! -d "$LUXOPI_PATH" ]]; then
        log "ERROR: LuxoPi directory not found at $LUXOPI_PATH"
        exit 1
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
    
    if ! colcon build; then
        log "ERROR: Failed to build workspace"
        exit 1
    fi
    
    # Source the newly built setup
    source "${LUXOPI_PATH}/install/setup.bash"
}

get_launch_args() {
    echo "use_hardware:=$LUXOPI_USE_HARDWARE" \
         "use_camera:=$LUXOPI_USE_CAMERA" \
         "enable_emotion_detection:=$LUXOPI_ENABLE_EMOTION_DETECTION" \
         "enable_voice:=$LUXOPI_ENABLE_VOICE" \
         "enable_ads7830:=$LUXOPI_ENABLE_ADS7830" \
         "verbose:=$LUXOPI_VERBOSE" \
         "enable_idle_animations:=$LUXOPI_ENABLE_IDLE_ANIMATIONS" \
         "enable_dynamic_adaptation:=$LUXOPI_ENABLE_DYNAMIC_ADAPTATION" \
         "enable_framebuffer_display:=$LUXOPI_ENABLE_FRAMEBUFFER_DISPLAY" \
         "sense_collision:=$LUXOPI_SENSE_COLLISION"
}

print_configuration() {
    log "=== LuxoPi Configuration ==="
    log "Hardware: $LUXOPI_USE_HARDWARE"
    log "Camera: $LUXOPI_USE_CAMERA" 
    log "Emotion Detection: $LUXOPI_ENABLE_EMOTION_DETECTION"
    log "Voice: $LUXOPI_ENABLE_VOICE"
    log "ADS7830: $LUXOPI_ENABLE_ADS7830"
    log "Verbose: $LUXOPI_VERBOSE"
    log "Idle Animations: $LUXOPI_ENABLE_IDLE_ANIMATIONS"
    log "Dynamic Adaptation: $LUXOPI_ENABLE_DYNAMIC_ADAPTATION"
    log "Framebuffer Display: $LUXOPI_ENABLE_FRAMEBUFFER_DISPLAY"
    log "Collision Sensing: $LUXOPI_SENSE_COLLISION"
    log "=========================="
}

launch_luxopi() {
    local args=$(get_launch_args)
    log "Launching LuxoPi with args: $args"
    
    ros2 launch luxo_behaviors luxo_system.launch.py $args
}

setup_i2c() {
    # Adjust modprobe for i2c devices to 10kHz for noise reduction
    if command -v modprobe >/dev/null 2>&1; then
        log "Configuring I2C for noise reduction..."
        # sudo modprobe i2c_bcm2708 baudrate=10000
    fi
}

cleanup() {
    log "Shutting down LuxoPi..."
    # Add any cleanup commands here
    exit 0
}

# =============================================================================
# Main Script
# =============================================================================

# Handle signals for graceful shutdown
trap cleanup SIGTERM SIGINT

log "Starting LuxoPi Smart Launch Script (PID: $$)"
print_configuration

# Dependency checks
check_dependencies

# Setup environment
setup_environment

# Optional I2C setup
setup_i2c

# Build workspace
build_workspace

# Main execution loop
restart_count=0
while true; do
    if [[ $LUXOPI_MAX_RESTARTS -gt 0 ]] && [[ $restart_count -ge $LUXOPI_MAX_RESTARTS ]]; then
        log "Maximum restart limit ($LUXOPI_MAX_RESTARTS) reached. Exiting."
        exit 1
    fi
    
    if [[ $restart_count -gt 0 ]]; then
        log "Restart attempt #$restart_count"
    fi
    
    # Launch the system
    if launch_luxopi; then
        log "LuxoPi exited normally"
        break
    else
        exit_code=$?
        log "LuxoPi exited with code $exit_code"
        
        if [[ $exit_code -eq 130 ]]; then  # SIGINT (Ctrl+C)
            log "Received interrupt signal, exiting..."
            break
        fi
        
        restart_count=$((restart_count + 1))
        log "Restarting in $LUXOPI_RESTART_DELAY seconds..."
        sleep "$LUXOPI_RESTART_DELAY"
    fi
done

log "LuxoPi launch script finished"