[] If I get nonstop voice activity or collision detection, the robot can get in a weird stuck state
[] Touch Circuit
[] Touch Capabilities - Animations
[] Touch Capabilities - Collision Detection
[] Fix DEMA Adaptation Mode and Integrate with Touch

[] Move acceleration to msg.velocity and move source to its own message
[] Identify your voice and act differently for different people depending on the voice
[] Fix the 6 channel implementation
[] Simplify Launch Files
[] Continue fine tuning the different animation commands

# Later Priorities
## High Priority
- [ ] Fix dynamic adaptation mode (DEMA) - increase torque limit for better operation
- [ ] Fix animation system to handle interruptions from collision avoidance more gracefully

## Code Quality Improvements 
- [ ] Add unit tests for critical components
- [ ] Create integration tests for full system behavior

## Feature Enhancements
- [ ] Implement smoother transition between animations when interrupted by collisions
- [ ] Add more sophisticated emotion detection response (consider context/history)
- [ ] Improve proactive collision avoidance to avoid obstacles more naturally
- [ ] Convert to lifecycle nodes
- [ ] Add parameter namespacing

## Documentation
- [ ] Document all available ROS parameters with descriptions and default values

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
- [ ] Review and fix thread safety issues in all multi-threaded components
- [ ] Implement proper ROS2 lifecycle nodes for better state management
- [ ] Split large nodes into smaller, focused components