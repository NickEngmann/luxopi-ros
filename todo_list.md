[] If I get nonstop voice activity or collision detection, the robot can get in a weird stuck state
[] I see the target and current adjustment with the voice activity, but it never reaches target. It just does micro movements
[] Sometimes it doesn't react to the camera/actions (more of a delay in between actions)
[] React to Camera Faster!
[] Simplify Launch Files
[-] When the camera closes also close the framebuffer (show a specific closing state)
[] Continue fine tuning the different animation commands
[] Faster Acceleration when moving away from collisions
[] Move acceleration to msg.velocity and move source to its own message
[] Identify your voice and act differently for different people depending on the voice
[] Fix the 6 channel implementation

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