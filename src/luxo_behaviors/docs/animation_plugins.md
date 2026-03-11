# Animation Plugins Module

## Overview
The `animation_plugins` module provides reusable animation plugins that can be composed to create complex Luxo Jr-style behaviors.

## Plugin Architecture

Plugins are modular components that can be stacked and combined to create custom animations. Each plugin implements a standard interface:

```python
class AnimationPlugin:
    def __init__(self, duration=1.0):
        self.duration = duration
        self.start_time = None
        self.current_time = 0.0
    
    def start(self):
        self.start_time = time.time()
    
    def update(self, dt):
        self.current_time += dt
        return self.current_time < self.duration
    
    def reset(self):
        self.current_time = 0.0
        self.start_time = None
```

## Built-in Plugins

### `BreathePlugin`
Simulates breathing motion by oscillating the arm position.

**Parameters:**
- `amplitude`: Maximum displacement in meters (default: 0.01)
- `frequency`: Breathing rate in Hz (default: 0.2)
- `offset`: Base position offset

**Implementation:**
```python
class BreathePlugin(AnimationPlugin):
    def __init__(self, amplitude=0.01, frequency=0.2, offset=(0, 0, 0)):
        super().__init__(duration=1.0)
        self.amplitude = amplitude
        self.frequency = frequency
        self.offset = offset
        self.phase = 0.0
    
    def update(self, dt):
        super().update(dt)
        self.phase += self.frequency * dt * 2 * math.pi
        return self.current_time < self.duration
    
    def get_breath_offset(self):
        return self.amplitude * math.sin(self.phase)
```

### `LookAtPlugin`
Animates the arm to look at a target point.

**Parameters:**
- `target`: Target position as (x, y, z)
- `speed`: Look speed in rad/s
- `smooth`: Whether to smooth the rotation

**Implementation:**
```python
class LookAtPlugin(AnimationPlugin):
    def __init__(self, target, speed=1.0, smooth=True):
        super().__init__(duration=1.0)
        self.target = target
        self.speed = speed
        self.smooth = smooth
        self.current_rotation = (1.0, 0.0, 0.0, 0.0)
    
    def update(self, dt):
        super().update(dt)
        if self.smooth:
            # Use spherical linear interpolation for smooth rotation
            target_rotation = self._calculate_rotation_to_target()
            self.current_rotation = self._slerp(self.current_rotation, target_rotation, self.speed * dt)
        else:
            self.current_rotation = self._calculate_rotation_to_target()
        return self.current_time < self.duration
    
    def get_rotation(self):
        return self.current_rotation
```

### `WanderPlugin`
Creates a wandering/random movement pattern.

**Parameters:**
- `max_speed`: Maximum movement speed
- `change_interval`: How often to change direction
- `range`: Maximum distance from origin

**Implementation:**
```python
class WanderPlugin(AnimationPlugin):
    def __init__(self, max_speed=0.1, change_interval=2.0, range=0.5):
        super().__init__(duration=10.0)
        self.max_speed = max_speed
        self.change_interval = change_interval
        self.range = range
        self.direction = (0, 0, 0)
        self.last_change = 0.0
    
    def update(self, dt):
        super().update(dt)
        if self.current_time - self.last_change > self.change_interval:
            self._randomize_direction()
            self.last_change = self.current_time
        return self.current_time < self.duration
    
    def get_position(self):
        base = (0, 0, 0)
        offset = (self.direction[0] * self.range, 
                  self.direction[1] * self.range, 
                  self.direction[2] * self.range)
        return tuple(a + b for a, b in zip(base, offset))
```

### `IdlePlugin`
Creates natural idle movements for the arm.

**Parameters:**
- `variation`: Movement variation level
- `rest_duration`: Duration of rest periods

**Implementation:**
```python
class IdlePlugin(AnimationPlugin):
    def __init__(self, variation=0.5, rest_duration=2.0):
        super().__init__(duration=rest_duration)
        self.variation = variation
        self.rest_duration = rest_duration
        self.state = 'moving'
        self.move_time = 0.0
    
    def update(self, dt):
        super().update(dt)
        if self.state == 'moving':
            self.move_time += dt
            if self.move_time > self.rest_duration * 0.7:
                self.state = 'resting'
                self.move_time = 0.0
        elif self.state == 'resting':
            self.move_time += dt
            if self.move_time > self.rest_duration * 0.3:
                self.state = 'moving'
                self.move_time = 0.0
        return self.current_time < self.duration
    
    def get_idle_offset(self):
        if self.state == 'moving':
            return self._calculate_idle_motion()
        return (0, 0, 0)
```

### `EmotionPlugin`
Applies emotional expression to animations.

**Parameters:**
- `emotion`: Emotion type (happy, sad, angry, excited, calm)
- `intensity`: Emotion intensity (0.0 to 1.0)

**Implementation:**
```python
class EmotionPlugin(AnimationPlugin):
    EMOTION_PATTERNS = {
        'happy': {
            'amplitude': 0.05,
            'frequency': 2.0,
            'direction': (0, 0, 1)
        },
        'sad': {
            'amplitude': 0.03,
            'frequency': 0.5,
            'direction': (0, 0, -1)
        },
        'angry': {
            'amplitude': 0.08,
            'frequency': 3.0,
            'direction': (1, 0, 0)
        },
        'excited': {
            'amplitude': 0.1,
            'frequency': 4.0,
            'direction': (0, 1, 0)
        },
        'calm': {
            'amplitude': 0.02,
            'frequency': 0.3,
            'direction': (0, 0, 0)
        }
    }
    
    def __init__(self, emotion='calm', intensity=1.0):
        super().__init__(duration=5.0)
        self.emotion = emotion
        self.intensity = intensity
        self.pattern = self.EMOTION_PATTERNS.get(emotion, self.EMOTION_PATTERNS['calm'])
        self.phase = 0.0
    
    def update(self, dt):
        super().update(dt)
        self.phase += self.pattern['frequency'] * dt * 2 * math.pi
        return self.current_time < self.duration
    
    def get_emotion_offset(self):
        base_offset = self.pattern['amplitude'] * math.sin(self.phase)
        return tuple(c * base_offset * self.intensity for c in self.pattern['direction'])
```

## Plugin Composition

Plugins can be composed to create complex behaviors:

```python
class CompositePlugin(AnimationPlugin):
    def __init__(self, plugins, duration=5.0):
        super().__init__(duration=duration)
        self.plugins = plugins
        self.active_plugin_index = 0
    
    def update(self, dt):
        super().update(dt)
        if self.plugins[self.active_plugin_index].update(dt):
            return True
        else:
            self.active_plugin_index += 1
            if self.active_plugin_index >= len(self.plugins):
                return False
            self.plugins[self.active_plugin_index].start()
            return self.update(dt)
    
    def get_combined_offset(self):
        return tuple(
            sum(p.get_offset() for p in self.plugins)
        )
```

## Usage Example

```python
from animation_plugins import BreathePlugin, LookAtPlugin, EmotionPlugin
from animation_plugins import CompositePlugin

# Create individual plugins
breathe = BreathePlugin(amplitude=0.01, frequency=0.2)
look = LookAtPlugin(target=(0.5, 0.0, 0.3), speed=0.5)
emotion = EmotionPlugin(emotion='happy', intensity=0.8)

# Compose plugins
composite = CompositePlugin([breathe, look, emotion], duration=10.0)

# Use in animation loop
composite.start()
while composite.update(0.016):
    # Apply combined effects to arm
    offset = breathe.get_breath_offset() + emotion.get_emotion_offset()
    rotation = look.get_rotation()
    arm_controller.set_pose_with_offset(offset, rotation)
```
