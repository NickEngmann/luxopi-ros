# Collision Behavior Module

## Overview
The `collision_behavior` module handles collision detection, response, and safety mechanisms for the Luxo robotic arm.

## Collision Detection System

The collision detection system uses multiple sensors and algorithms:

```python
class CollisionDetector:
    def __init__(self, arm_config, sensor_config):
        self.arm_config = arm_config
        self.sensor_config = sensor_config
        self.joint_positions = [0.0] * 6
        self.velocity_threshold = sensor_config.velocity_threshold
        self.torque_threshold = sensor_config.torque_threshold
        self.distance_threshold = sensor_config.distance_threshold
    
    def update(self, joint_positions, joint_velocities, joint_torques):
        self.joint_positions = joint_positions
        return self.detect_collision(joint_velocities, joint_torques)
    
    def detect_collision(self, velocities, torques):
        # Check for sudden velocity changes
        for i, (curr, prev) in enumerate(zip(self.joint_positions, self.prev_positions)):
            delta = abs(curr - prev)
            if delta > self.distance_threshold:
                return CollisionEvent(
                    type='position_sudden_change',
                    joint=i,
                    severity=delta / self.distance_threshold
                )
        
        # Check for torque spikes
        for i, torque in enumerate(torques):
            if abs(torque) > self.torque_threshold:
                return CollisionEvent(
                    type='torque_spike',
                    joint=i,
                    severity=abs(torque) / self.torque_threshold
                )
        
        return None
```

## Collision Response Strategies

### `StopResponse`
Immediate stop on collision detection.

```python
class StopResponse(CollisionResponse):
    def __init__(self, arm_controller):
        self.arm_controller = arm_controller
    
    def execute(self, collision_event):
        self.arm_controller.emergency_stop()
        self.arm_controller.hold_position()
```

### `RetractResponse`
Retract arm along last trajectory.

```python
class RetractResponse(CollisionResponse):
    def __init__(self, arm_controller, retract_speed=0.1):
        self.arm_controller = arm_controller
        self.retract_speed = retract_speed
    
    def execute(self, collision_event):
        # Calculate reverse trajectory
        trajectory = self.arm_controller.get_recent_trajectory()
        for point in reversed(trajectory):
            self.arm_controller.move_to(point, speed=self.retract_speed)
            if self.arm_controller.is_stopped():
                break
```

### `EscapeResponse`
Move away from collision direction.

```python
class EscapeResponse(CollisionResponse):
    def __init__(self, arm_controller, escape_distance=0.1):
        self.arm_controller = arm_controller
        self.escape_distance = escape_distance
    
    def execute(self, collision_event):
        # Calculate escape direction
        escape_vector = self._calculate_escape_vector(collision_event)
        current_position = self.arm_controller.get_end_effector_position()
        escape_position = current_position + escape_vector
        
        self.arm_controller.move_to(escape_position, speed=0.2)
    
    def _calculate_escape_vector(self, collision_event):
        # Use joint torque direction to determine escape vector
        max_torque_joint = max(enumerate(collision_event.torques), key=lambda x: abs(x[1]))
        direction = -1 if max_torque_joint[1] > 0 else 1
        return np.array([direction * self.escape_distance] * 3)
```

## Collision Event System

```python
class CollisionEvent:
    def __init__(self, event_type, joint=None, severity=1.0, position=None, torque=None):
        self.event_type = event_type
        self.joint = joint
        self.severity = severity
        self.position = position
        self.torque = torque
        self.timestamp = time.time()
    
    def is_critical(self):
        return self.severity > 2.0
    
    def is_warning(self):
        return 1.0 <= self.severity <= 2.0
    
    def __repr__(self):
        return f"CollisionEvent({self.event_type}, joint={self.joint}, severity={self.severity})"
```

## Collision Handler

```python
class CollisionHandler:
    def __init__(self, arm_controller, detector, response_strategy='stop'):
        self.arm_controller = arm_controller
        self.detector = detector
        self.response_strategy = self._get_response_strategy(response_strategy)
        self.last_collision = None
        self.collision_count = 0
        self.enabled = True
    
    def _get_response_strategy(self, strategy):
        strategies = {
            'stop': StopResponse,
            'retract': RetractResponse,
            'escape': EscapeResponse
        }
        return strategies.get(strategy, StopResponse)
    
    def update(self, joint_positions, joint_velocities, joint_torques):
        if not self.enabled:
            return None
        
        collision = self.detector.update(joint_positions, joint_velocities, joint_torques)
        if collision:
            self.last_collision = collision
            self.collision_count += 1
            self.response_strategy.execute(collision)
        
        return collision
    
    def is_resolved(self):
        return self.last_collision is None or not self.last_collision.is_critical()
    
    def is_critical(self):
        return self.last_collision and self.last_collision.is_critical()
    
    def reset(self):
        self.last_collision = None
        self.collision_count = 0
```

## Safety Monitoring

```python
class SafetyMonitor:
    def __init__(self, config):
        self.config = config
        self.joint_limits = config.joint_limits
        self.velocity_limits = config.velocity_limits
        self.acceleration_limits = config.acceleration_limits
        self.workspace_bounds = config.workspace_bounds
    
    def check_joint_limits(self, joint_positions):
        for i, (pos, limit) in enumerate(zip(joint_positions, self.joint_limits)):
            if pos < limit[0] or pos > limit[1]:
                return SafetyViolation(
                    type='joint_limit',
                    joint=i,
                    value=pos,
                    limit=limit
                )
        return None
    
    def check_workspace_bounds(self, end_effector_position):
        for i, bound in enumerate(self.workspace_bounds):
            if end_effector_position[i] < bound[0] or end_effector_position[i] > bound[1]:
                return SafetyViolation(
                    type='workspace_bound',
                    axis=i,
                    value=end_effector_position[i],
                    limit=bound
                )
        return None
    
    def continuous_check(self, joint_positions, velocities, accelerations, ee_position):
        violations = []
        
        violation = self.check_joint_limits(joint_positions)
        if violation:
            violations.append(violation)
        
        violation = self.check_workspace_bounds(ee_position)
        if violation:
            violations.append(violation)
        
        return violations if violations else None
```

## Usage Example

```python
from collision_behavior import CollisionHandler, SafetyMonitor

# Initialize handler
config = CollisionConfig(
    velocity_threshold=0.5,
    torque_threshold=10.0,
    distance_threshold=0.01
)

detector = CollisionDetector(arm_config, config)
safety_monitor = SafetyMonitor(safety_config)
handler = CollisionHandler(arm_controller, detector, response_strategy='escape')

# Main loop
while True:
    joint_positions = arm_controller.get_joint_positions()
    joint_velocities = arm_controller.get_joint_velocities()
    joint_torques = arm_controller.get_joint_torques()
    
    collision = handler.update(joint_positions, joint_velocities, joint_torques)
    
    if collision:
        print(f"Collision detected: {collision}")
    
    time.sleep(0.01)
```
