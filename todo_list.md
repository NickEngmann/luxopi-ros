# LuxoPi Project Todo List

## High Priority
- [ ] Consolidate duplicate functionality - merge the two `at_position` functions into one consistent implementation
- [ ] Fix dynamic adaptation mode (DEMA) - increase torque limit for better operation
- [ ] Comprehensive testing of camera interaction with dynamic adaptation feature
- [ ] Implement proper error handling in SerialManager class
- [ ] Fix animation system to handle interruptions from collision avoidance more gracefully

## Code Quality Improvements 
- [ ] Add type hints to all Python functions for better code clarity
- [ ] Standardize logging format across all modules
- [ ] Reduce code duplication in collision callbacks (left/right/front have nearly identical logic)
- [ ] Improve comment quality, especially for complex collision avoidance logic
- [ ] Add unit tests for critical components
- [ ] Create integration tests for full system behavior

## Feature Enhancements
- [ ] Implement smoother transition between animations when interrupted by collisions
- [ ] Add more sophisticated emotion detection response (consider context/history)
- [ ] Improve proactive collision avoidance to avoid obstacles more naturally
- [ ] Add configuration system for easily adjusting behavior parameters without code changes
- [ ] Implement energy-saving mode that reduces servo operations during extended idle periods
- [ ] Create a web interface for remote control and monitoring

## Documentation
- [ ] Document all available ROS parameters with descriptions and default values
- [ ] Create architecture diagram showing component interactions
- [ ] Add troubleshooting section for common failure modes
- [ ] Add setup guide specifically for Raspberry Pi configurations
- [ ] Document all animation behaviors with examples

## Performance & Stability
- [ ] Profile and optimize the safety monitoring timer to prevent crashes
- [ ] Implement proper resource cleanup in all destructors/shutdown paths
- [ ] Add watchdog monitors for critical services
- [ ] Implement proper thread synchronization in SerialManager
- [ ] Reduce unnecessary joint state publications to minimize network traffic
- [ ] Optimize collision detection algorithms to reduce CPU usage

## User Experience
- [ ] Improve LED feedback for system state
- [ ] Create a simple control interface for non-technical users
- [ ] Add voice command capability for triggering animations

## Technical Debt
- [ ] Refactor collision handling code to use a more object-oriented approach
- [ ] Extract configuration from hardcoded values to parameter files
- [ ] Create proper Python package structure with setup.py
- [ ] Migrate from direct node.get_logger() calls to a centralized logging system
- [ ] Review and fix thread safety issues in all multi-threaded components
- [ ] Implement proper ROS2 lifecycle nodes for better state management