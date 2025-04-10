# LuxoPi Project Todo List

[] Fix the Home Position Movement
-  Maybe try moving one joint at a time?
[] Make joint_states_target be roarm/target
[] Get rid of return_to_home inside animation_command, it does nothing
[] I'm under the impression that there is a lot of code that doesn't do much within collision_avoidance. We may want to get rid of it
[] Change shutdown procedures, to be a safe approach to self.close_position
[] Continue fine tuning the different animation commands
[] More permanent solution for the I2C power cable
[] Cleanup wiring
[] Reprint head with 5% infill, and transparent. As well as more holes (trying to get rid of half the weight)

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