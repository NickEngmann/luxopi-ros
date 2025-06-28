# Issues (Needs Stabability)
- [] Minimize hardware_interface.py by using shared_utils.py

- [] Print a protective case for APDS-9960 (all 3 of them?)
- [] Remove the small LED ring (max out at 60 LEDs)
- [] Fix Wraparound Logic
[hardware_interface-2] [INFO] [1751133255.983744664] [hardware_interface]: Voice at -188.13833618164062° beyond max limit - using wraparound to -188.1°
[hardware_interface-2] [INFO] [1751133255.984738354] [hardware_interface]: Sending voice command: base to -188.1° with position: [-3.28, -0.55, 1.2, 1.0, 2.0]


- [] Camera back on and cleanup its interactions (make it farrr less annoying)

# New Features
- [] Update to DepthAI 3.0 (update model as well for more interactions)
- [] Audio Commands
-- Turn on/off light
-- go to rest position (sleep with LEDs off)
-- wake up - move around and stretch

# Later Priorities
## High Priority
- [ ] have a voice to speak back to me with
- [ ] Fix dynamic adaptation mode (DEMA) - increase torque limit for better operation
- [ ] Fix animation system to handle interruptions from collision avoidance more gracefully
- [ ] Fix DEMA Adaptation Mode and Integrate with Touch
- [ ] CAMERA FOLLOWING

## Feature Enhancements
- [ ] Audio device recovery
- [ ] Implement smoother transition between animations when interrupted by collisions
- [ ] Add more sophisticated emotion detection response (consider context/history)
- [ ] Improve proactive collision avoidance to avoid obstacles more naturally
- [ ] Convert to lifecycle nodes
- [ ] Add parameter namespacing
- [ ] Identify your voice and act differently for different people depending on the voice

## Performance & Stability
- [ ] Profile and optimize the safety monitoring timer to prevent crashes
- [ ] Implement proper resource cleanup in all destructors/shutdown paths
- [ ] Add watchdog monitors for critical services
- [ ] Implement proper thread synchronization in SerialManager
- [ ] Reduce unnecessary joint state publications to minimize network traffic
- [ ] Optimize collision detection algorithms to reduce CPU usage

## Technical Debt
- [ ] Refactor collision handling code to use a more object-oriented approach
- [ ] Extract configuration from hardcoded values to parameter files
- [ ] Implement proper ROS2 lifecycle nodes for better state management
- [ ] Split large nodes into smaller, focused components
- [ ] Add unit tests for critical components
- [ ] Create integration tests for full system behavior
- [ ] Move acceleration to msg.velocity and move source to its own message
- [ ] Simplify Launch Files