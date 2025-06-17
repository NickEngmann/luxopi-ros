#!/bin/bash

# =============================================================================
# LuxoPi Graceful Shutdown Script - Enhanced for Modular Behavior System
# =============================================================================

# Configuration
SHUTDOWN_TIMEOUT=15
ANIMATION_TIMEOUT=10
EMERGENCY_MODE=false
VERBOSE=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--emergency)
            EMERGENCY_MODE=true
            shift
            ;;
        -t|--timeout)
            SHUTDOWN_TIMEOUT="$2"
            shift 2
            ;;
        -q|--quiet)
            VERBOSE=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -e, --emergency    Emergency stop (no animations)"
            echo "  -t, --timeout SEC  Shutdown timeout (default: 15)"
            echo "  -q, --quiet        Quiet mode"
            echo "  -h, --help         Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging function
log() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    fi
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

# Check if ROS2 is available
check_ros_environment() {
    if ! command -v ros2 >/dev/null 2>&1; then
        log_error "ROS2 not found in PATH"
        return 1
    fi
    
    # Source ROS2 setup files
    if [[ -f "/opt/ros/jazzy/setup.bash" ]]; then
        source /opt/ros/jazzy/setup.bash
    else
        log_error "ROS2 jazzy setup file not found"
        return 1
    fi
    
    if [[ -f "/home/pi/luxopi-ros/install/setup.bash" ]]; then
        source /home/pi/luxopi-ros/install/setup.bash
    else
        log "Warning: LuxoPi setup file not found"
    fi
    
    return 0
}

# Check if LuxoPi nodes are running
check_luxopi_status() {
    local nodes
    nodes=$(ros2 node list 2>/dev/null | grep -E "(luxo|safety|collision|voice|idle|petting)" || true)
    
    if [[ -n "$nodes" ]]; then
        log "Found active LuxoPi nodes:"
        echo "$nodes" | while read -r node; do
            log "  - $node"
        done
        return 0
    else
        log "No LuxoPi nodes found running"
        return 1
    fi
}

# Send system command via ROS2 topic
send_system_command() {
    local command="$1"
    local timeout="${2:-5}"
    
    log "Sending system command: $command"
    
    if timeout "$timeout" ros2 topic pub --once /safety/system_command std_msgs/String "data: $command" 2>/dev/null; then
        log "Command sent successfully"
        return 0
    else
        log_error "Failed to send command: $command"
        return 1
    fi
}

# Check if SafetyCoordinator is responding
check_safety_coordinator() {
    log "Checking SafetyCoordinator status..."
    
    if ros2 node list 2>/dev/null | grep -q "safety_coordinator"; then
        log "SafetyCoordinator is running"
        
        # Try to get system status
        if timeout 3 ros2 topic echo --once /safety/system_status >/dev/null 2>&1; then
            log "SafetyCoordinator is responsive"
            return 0
        else
            log "SafetyCoordinator not responding to status requests"
            return 1
        fi
    else
        log "SafetyCoordinator not found"
        return 1
    fi
}

# Send close animation through behavior system
send_close_animation() {
    log "Initiating close animation sequence..."
    
    # Send go_home command to SafetyCoordinator
    if send_system_command "go_home" 5; then
        log "Waiting for robot to reach home position..."
        sleep 3
        
        # Try to trigger a close animation via animation system
        if ros2 node list 2>/dev/null | grep -q "animation_command"; then
            log "Sending close animation..."
            if timeout 5 ros2 topic pub --once /roarm/animation_command std_msgs/String "data: close" 2>/dev/null; then
                log "Close animation sent, waiting for completion..."
                sleep "$ANIMATION_TIMEOUT"
                return 0
            else
                log "Failed to send close animation, proceeding with shutdown"
                return 1
            fi
        else
            log "Animation system not available, skipping close animation"
            return 1
        fi
    else
        log_error "Failed to send home position command"
        return 1
    fi
}

# Emergency stop all systems
emergency_stop() {
    log "INITIATING EMERGENCY STOP"
    
    # Send emergency stop command
    send_system_command "emergency_stop" 2
    
    # Force kill all LuxoPi-related processes
    log "Force stopping all LuxoPi processes..."
    
    # Kill ROS2 nodes by name pattern
    pkill -f "safety_coordinator" 2>/dev/null || true
    pkill -f "collision_monitor" 2>/dev/null || true
    pkill -f "voice_following" 2>/dev/null || true
    pkill -f "idle_behavior" 2>/dev/null || true
    pkill -f "petting_response" 2>/dev/null || true
    pkill -f "hardware_interface" 2>/dev/null || true
    pkill -f "animation_command" 2>/dev/null || true
    pkill -f "luxo_system.launch.py" 2>/dev/null || true
    
    sleep 2
    
    log "Emergency stop completed"
}

# Graceful shutdown sequence
graceful_shutdown() {
    log "Starting graceful shutdown sequence..."
    
    # Check if SafetyCoordinator is available for coordinated shutdown
    if check_safety_coordinator; then
        # Send close animation if not in emergency mode
        if [[ "$EMERGENCY_MODE" == "false" ]]; then
            send_close_animation
        fi
        
        # Clear all overrides and prepare for shutdown
        log "Clearing all behavior overrides..."
        send_system_command "clear_overrides" 3
        sleep 1
        
        # Disable safety systems for clean shutdown
        log "Disabling safety systems for shutdown..."
        send_system_command "disable_safety" 2
        sleep 1
    fi
    
    # Send shutdown signal to main launch process
    log "Sending shutdown signal to LuxoPi processes..."
    
    # Try to find and stop the main launch process gracefully
    local launch_pids
    launch_pids=$(pgrep -f "luxo_system.launch.py" 2>/dev/null || true)
    
    if [[ -n "$launch_pids" ]]; then
        log "Found launch processes: $launch_pids"
        echo "$launch_pids" | while read -r pid; do
            log "Sending SIGTERM to PID $pid"
            kill -TERM "$pid" 2>/dev/null || true
        done
        
        # Wait for graceful shutdown
        local count=0
        while [[ $count -lt $SHUTDOWN_TIMEOUT ]]; do
            if ! pgrep -f "luxo_system.launch.py" >/dev/null 2>&1; then
                log "Graceful shutdown completed"
                break
            fi
            sleep 1
            count=$((count + 1))
        done
        
        # Force kill if still running
        if pgrep -f "luxo_system.launch.py" >/dev/null 2>&1; then
            log "Force killing remaining processes..."
            pkill -KILL -f "luxo_system.launch.py" 2>/dev/null || true
            sleep 2
        fi
    else
        log "No launch processes found"
    fi
}

# Clean up ROS2 environment
cleanup_ros_environment() {
    log "Cleaning up ROS2 environment..."
    
    # Stop ROS2 daemon
    ros2 daemon stop 2>/dev/null || true
    
    # Kill any remaining ROS2 processes
    pkill -f "_ros2_daemon" 2>/dev/null || true
    
    log "ROS2 cleanup completed"
}

# Verify shutdown completion
verify_shutdown() {
    log "Verifying shutdown completion..."
    
    # Check for remaining LuxoPi nodes
    local remaining_nodes
    remaining_nodes=$(ros2 node list 2>/dev/null | grep -E "(luxo|safety|collision|voice|idle|petting)" || true)
    
    if [[ -n "$remaining_nodes" ]]; then
        log_error "Some nodes are still running:"
        echo "$remaining_nodes" | while read -r node; do
            log_error "  - $node"
        done
        return 1
    else
        log "All LuxoPi nodes have been stopped"
        return 0
    fi
}

# Main execution
main() {
    log "LuxoPi Shutdown Script Starting"
    
    if [[ "$EMERGENCY_MODE" == "true" ]]; then
        log "EMERGENCY MODE ENABLED"
    fi
    
    # Check ROS2 environment
    if ! check_ros_environment; then
        log_error "ROS2 environment check failed"
        exit 1
    fi
    
    # Check if LuxoPi is running
    if ! check_luxopi_status; then
        log "LuxoPi doesn't appear to be running"
        exit 0
    fi
    
    # Execute shutdown sequence
    if [[ "$EMERGENCY_MODE" == "true" ]]; then
        emergency_stop
    else
        graceful_shutdown
    fi
    
    # Clean up ROS2 environment
    cleanup_ros_environment
    
    # Verify shutdown
    sleep 2
    if verify_shutdown; then
        log "LuxoPi shutdown completed successfully"
        exit 0
    else
        log_error "Shutdown verification failed - some components may still be running"
        exit 1
    fi
}

# Run main function
main "$@"