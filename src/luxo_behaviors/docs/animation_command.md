# Animation Command Module

## Overview
The `animation_command` module handles the creation and execution of animation commands for Luxo Jr-style behaviors on the RoArm-M3 robotic arm.

## Classes

### `AnimationCommand`
Base class for all animation commands.

**Attributes:**
- `command_id`: Unique identifier for the command
- `duration`: Animation duration in seconds
- `easing`: Easing function name (linear, ease_in, ease_out, ease_in_out)
- `priority`: Command priority (0-10, higher = more important)

**Methods:**
- `execute()`: Executes the animation command
- `cancel()`: Cancels the command execution
- `is_complete()`: Returns True if animation is finished

### `PoseAnimationCommand`
Animates the arm to a specific pose.

**Parameters:**
- `target_pose`: Target position as (x, y, z) tuple
- `target_orientation`: Target orientation as quaternion (w, x, y, z)
- `duration`: Animation duration in seconds
- `easing`: Easing function to use

**Implementation:**
```python
class PoseAnimationCommand(AnimationCommand):
    def __init__(self, target_pose, target_orientation, duration=1.0, easing='linear'):
        self.target_pose = target_pose
        self.target_orientation = target_orientation
        self.current_pose = (0.0, 0.0, 0.0)
        self.current_orientation = (1.0, 0.0, 0.0, 0.0)
        self.start_time = time.time()
        self.easing_func = self._get_easing_function(easing)
    
    def execute(self):
        elapsed = time.time() - self.start_time
        t = min(elapsed / self.duration, 1.0)
        t = self.easing_func(t)
        self.current_pose = self._lerp_tuple(self.start_pose, self.target_pose, t)
        self.current_orientation = self._slerp(self.start_orientation, self.target_orientation, t)
        self.arm_controller.set_pose(self.current_pose, self.current_orientation)
        return self.is_complete()
```

### `TrajectoryAnimationCommand`
Animates the arm along a series of waypoints.

**Parameters:**
- `waypoints`: List of (pose, orientation) tuples
- `speed`: Movement speed in m/s
- `easing`: Easing function for each segment

**Implementation:**
```python
class TrajectoryAnimationCommand(AnimationCommand):
    def __init__(self, waypoints, speed=0.5, easing='linear'):
        self.waypoints = waypoints
        self.speed = speed
        self.current_segment = 0
        self.segment_progress = 0.0
        self.easing_func = self._get_easing_function(easing)
    
    def execute(self):
        if self.current_segment >= len(self.waypoints) - 1:
            return True
        
        start_pose, start_orient = self.waypoints[self.current_segment]
        end_pose, end_orient = self.waypoints[self.current_segment + 1]
        
        segment_duration = self._calculate_segment_duration(start_pose, end_pose)
        self.segment_progress += self.dt / segment_duration
        
        t = self.easing_func(min(self.segment_progress, 1.0))
        current_pose = self._lerp_tuple(start_pose, end_pose, t)
        current_orient = self._slerp(start_orient, end_orient, t)
        
        self.arm_controller.set_pose(current_pose, current_orient)
        
        if self.segment_progress >= 1.0:
            self.current_segment += 1
            self.segment_progress = 0.0
        
        return self.current_segment >= len(self.waypoints) - 1
```

### `EasingFunctions`
Provides various easing functions for smooth animations.

**Available Functions:**
- `linear(t)`: t
- `ease_in(t)`: t^2
- `ease_out(t)`: 1 - (1-t)^2
- `ease_in_out(t)`: 4t(1-t) for t < 0.5, 1 - 4(t-1)^2 for t >= 0.5
- `ease_in_back(t)`: t^2 * ((back_scale + 1) * t - back_scale)
- `ease_out_back(t)`: 1 - ((1-t)^2 * ((back_scale + 1) * (1-t) - back_scale))
- `ease_in_elastic(t)`: -2^(10*(t-1)) * sin(2π(t-1)/0.3)
- `ease_out_elastic(t)`: 2^(-10*t) * sin(2π*t/0.3) + 1
- `ease_in_bounce(t)`: 1 - ease_out_bounce(1-t)
- `ease_out_bounce(t)`: Various bounce calculations

## Command Queue

The module maintains a command queue for sequential animation execution:

```python
class AnimationCommandQueue:
    def __init__(self):
        self.commands = []
        self.current_command = None
        self.is_playing = False
    
    def add_command(self, command):
        self.commands.append(command)
    
    def play_next(self):
        if self.commands:
            self.current_command = self.commands.pop(0)
            self.is_playing = True
    
    def update(self):
        if self.current_command and self.is_playing:
            if self.current_command.execute():
                self.is_playing = False
                self.current_command = None
                self.play_next()
```

## Usage Example

```python
from animation_command import PoseAnimationCommand, AnimationCommandQueue
from animation_plugins import linear, ease_out_bounce

# Create a command queue
queue = AnimationCommandQueue()

# Create a pose animation command
command = PoseAnimationCommand(
    target_pose=(0.3, 0.0, 0.2),
    target_orientation=(1.0, 0.0, 0.0, 0.0),
    duration=2.0,
    easing='ease_out_bounce'
)

# Add to queue and play
queue.add_command(command)
queue.play_next()

# Update loop
while queue.is_playing:
    queue.update()
    time.sleep(0.016)  # ~60 FPS
```
