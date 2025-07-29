
# Later Priorities
## High Priority
- [ ] Update to DepthAI 3.0 (update model as well for more interactions)
- [ ] have a voice to speak back to me with
- [ ] CAMERA FOLLOWING

## Feature Enhancements
- [ ] Fix dynamic adaptation mode (DEMA) - increase torque limit for better operation
- [ ] Fix DEMA Adaptation Mode and Integrate with Touch
- [ ] Implement smoother transition between animations when interrupted by collisions
- [ ] Add more sophisticated emotion detection response (consider context/history)
- [ ] Improve proactive collision avoidance to avoid obstacles more naturally
- [ ] Convert to lifecycle nodes
- [ ] Add parameter namespacing
- [ ] Identify voices and act differently for different people depending on the voice

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
- [ ] Add unit tests for critical components
- [ ] Create integration tests for full system behavior
- [ ] Move acceleration to msg.velocity and move source to its own message
- [ ] Simplify Launch Files