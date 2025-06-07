#!/bin/bash
# Demo script for enhanced robot arm animations

# Print header
echo "=========================================="
echo "  Robot Arm Enhanced Animation Demo"
echo "=========================================="
echo ""
echo "This script demonstrates all the enhanced animations,"
echo "including varied speeds. Press Ctrl+C to stop at any time."
echo ""

# Function to run an animation and wait
run_animation() {
    local name=$1
    local speed=${2:-1.0}
    local wait_time=${3:-4}
    
    echo "► Running animation: $name (speed: $speed)"
    ros2 topic pub --once /roarm/animation_command std_msgs/String "data: $name $speed"
    sleep $wait_time
}

# Function to display section header
section() {
    echo ""
    echo "----------------------------------------"
    echo "  $1"
    echo "----------------------------------------"
    echo ""
}

# Start the demo
section "Basic Emotions"
run_animation "curious"
run_animation "excited"
run_animation "sad"
run_animation "startled"

section "Functional Movements"
run_animation "grab"
run_animation "sweep"
run_animation "nod"
run_animation "shake"

section "Playful Behaviors"
run_animation "playful"
run_animation "dance"
run_animation "stretch"
run_animation "wave"

section "Thoughtful Actions"
run_animation "think"
run_animation "write"

section "Speed Variations Demo"
echo "Demonstrating the same animation at different speeds..."
run_animation "curious" 0.5 6
echo "↑ Slow version (0.5x)"
run_animation "curious" 1.0 4
echo "↑ Normal speed (1.0x)"
run_animation "curious" 2.0 2
echo "↑ Fast version (2.0x)"

section "Random Animation"
run_animation "random"
run_animation "random"
run_animation "random"

echo ""
echo "Demo complete! Here's a reference of all available animations:"
echo ""
echo "# Standard animations:"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: curious\"   # Make the arm look around curiously"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: excited\"   # Make the arm perform an excited hop"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: sad\"       # Make the arm droop sadly"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: sweep\"     # Make the arm sweep like searching"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: playful\"   # Make the arm do playful bounces"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: startled\"  # Make the arm perform a startled jump"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: grab\"      # Make the arm grab and release with gripper"
echo ""
echo "# New animations:"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: think\"     # Make the arm appear to be thinking"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: wave\"      # Make the arm wave hello/goodbye"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: dance\"     # Make the arm perform a dance routine"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: stretch\"   # Make the arm do a satisfying stretch"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: nod\"       # Make the arm nod yes"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: shake\"     # Make the arm shake no"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: write\"     # Make the arm mimic writing"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: random\"    # Play a random animation"
echo ""
echo "# Control commands:"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: stop\"      # Stop any currently running animation"
echo ""
echo "# Speed control (add a number after any animation name to control speed):"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: curious 0.5\"  # Run at half speed"
echo "ros2 topic pub --once /roarm/animation_command std_msgs/String \"data: excited 2.0\"  # Run at double speed"