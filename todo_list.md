# LuxoPi Project Todo List
[] Make joint_states_target be roarm/target
[] Continue fine tuning the different animation commands

## High Priority
- [ ] Consolidate duplicate functionality - merge the two `at_position` functions into one consistent implementation
- [ ] Fix dynamic adaptation mode (DEMA) - increase torque limit for better operation
- [ ] Implement proper error handling in SerialManager class
- [ ] Fix animation system to handle interruptions from collision avoidance more gracefully

## Code Quality Improvements 
- [ ] Reduce code duplication in collision callbacks (left/right/front have nearly identical logic)
- [ ] Add type hints to all Python functions for better code clarity
- [ ] Improve comment quality, especially for complex collision avoidance logic
- [ ] Add unit tests for critical components
- [ ] Create integration tests for full system behavior

## Feature Enhancements
- [ ] Implement smoother transition between animations when interrupted by collisions
- [ ] Add more sophisticated emotion detection response (consider context/history)
- [ ] Improve proactive collision avoidance to avoid obstacles more naturally

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