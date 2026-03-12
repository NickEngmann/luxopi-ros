# LuxoPi Animation Plugin Base Documentation

## Overview

The `animation_plugin_base.py` module provides the base class for all animation plugins in the LuxoPi system. Each animation should inherit from this base class and implement the required methods to be dynamically loaded and executed.

## Base Class: AnimationPluginBase

### Class Structure

```python
class AnimationPluginBase(ABC):
    """
    Abstract base class for all animation plugins.
    
    Each animation plugin must inherit from this class and implement:
    - get_animation_name()
    - get_animation_category()
    - execute()
    - get_animation_duration()
    """
```

### Required Methods

#### `get_animation_name() -> str`
Returns the unique identifier for this animation.

**Returns:**
- `str`: Animation name (e.g., "luxo_wave", "luxo_dance")

**Example:**
```python
def get_animation_name(self) -> str:
    return "luxo_greeting"
```

#### `get_animation_category() -> str`
Returns the category classification for this animation.

**Returns:**
- `str`: Category string (e.g., "emotion", "action", "response", "idle", "petting")

**Categories:**
- `emotion`: Expressions of emotions (happy, sad, excited)
- `action`: Physical movements and gestures
- `response`: Reactions to stimuli
- `idle`: Default behaviors when no interaction
- `petting`: Responses to physical touch

**Example:**
```python
def get_animation_category(self) -> str:
    return "emotion"
```

#### `execute() -> bool`
Executes the animation sequence.

**Returns:**
- `bool`: True if animation completed successfully, False otherwise

**Parameters:**
- No required parameters (uses internal state)

**Example:**
```python
def execute(self) -> bool:
    try:
        # Execute animation sequence
        self.move_joint(0, 45, 0.5)
        self.move_joint(1, 30, 0.3)
        return True
    except Exception as e:
        self.logger.error(f"Animation failed: {e}")
        return False
```

#### `get_animation_duration() -> float`
Returns the expected duration of the animation in seconds.

**Returns:**
- `float`: Duration in seconds

**Example:**
```python
def get_animation_duration(self) -> float:
    return 2.5
```

### Optional Methods

#### `get_animation_description() -> str`
Returns a human-readable description of the animation.

**Returns:**
- `str`: Description of animation behavior

#### `get_animation_requirements() -> dict`
Returns any special requirements for this animation.

**Returns:**
- `dict`: Requirements including:
  - `requires_collision_check`: bool
  - `requires_sensor_data`: bool
  - `minimum_battery`: float

#### `cleanup() -> None`
Performs cleanup after animation execution.

**Returns:**
- `None`

## Animation Plugin Architecture

### Plugin Discovery

Animation plugins are discovered through the `__init__.py` file in the animation_plugins package:

```python
__all__ = [
    'emotion_animations',
    'action_animations',
    'response_animations',
    'idle_animations',
    'petting_animations'
]
```

### Dynamic Loading

Plugins are loaded dynamically using Python's import system:

```python
import importlib

plugin_module = importlib.import_module(f"luxo_behaviors.animation_plugins.{module_name}")
plugin_class = getattr(plugin_module, plugin_class_name)
plugin = plugin_class()
```

### Plugin Registration

Each plugin must register itself with the animation system:

```python
class GreetingAnimation(AnimationPluginBase):
    _registered = True
    
    def __init__(self):
        self.name = "luxo_greeting"
        self.category = "emotion"
```

## Implementation Guidelines

### 1. Inheritance
Always inherit from `AnimationPluginBase`:

```python
from luxo_behaviors.animation_plugin_base import AnimationPluginBase

class MyAnimation(AnimationPluginBase):
    pass
```

### 2. Abstract Methods
Implement all required abstract methods:

```python
class MyAnimation(AnimationPluginBase):
    def get_animation_name(self) -> str:
        return "my_custom_animation"
    
    def get_animation_category(self) -> str:
        return "action"
    
    def execute(self) -> bool:
        # Animation logic
        return True
    
    def get_animation_duration(self) -> float:
        return 1.0
```

### 3. Error Handling
Always handle exceptions in the execute method:

```python
def execute(self) -> bool:
    try:
        # Animation logic
        return True
    except Exception as e:
        self.logger.error(f"Animation failed: {e}")
        return False
```

### 4. Logging
Use the logger for debugging and monitoring:

```python
self.logger.info(f"Starting {self.get_animation_name()}")
self.logger.warning(f"Animation took longer than expected")
```

### 5. State Management
Maintain animation state for complex sequences:

```python
self._state = "initializing"
self._progress = 0
self._completed = False
```

## Safety Considerations

### Joint Limits
Always respect joint limits defined in animation guidelines:
- Shoulder (Joint 2): -1.1 to 0.4 radians
- Elbow (Joint 3): -2.5 to 0.5 radians
- Wrist (Joint 4): -3.0 to 3.0 radians

### Collision Avoidance
Check for collisions before executing animations:
```python
if not self.check_collision_safe():
    self.logger.warning("Skipping animation due to collision risk")
    return False
```

### Emergency Stop
Implement emergency stop capability:
```python
def execute(self) -> bool:
    try:
        # Animation logic
        if self.should_stop():
            self.emergency_stop()
            return False
        return True
    except Exception as e:
        self.emergency_stop()
        raise
```

## Testing Animation Plugins

### Unit Testing
Test individual animation components:
```python
def test_animation_name(self):
    assert self.get_animation_name() == "test_animation"

def test_animation_category(self):
    assert self.get_animation_category() == "emotion"
```

### Integration Testing
Test animation execution in context:
```python
def test_animation_execution(self):
    result = self.execute()
    assert result is True
```

### Performance Testing
Test animation timing:
```python
def test_animation_duration(self):
    duration = self.get_animation_duration()
    assert duration > 0 and duration < 10.0
```

## See Also

- [Shared Utilities Documentation](shared_utils_docs.md)
- [Animation Plugins Documentation](animation_plugins_docs.md)
- [Serial Manager Documentation](serial_manager_docs.md)
- [State Machine Documentation](state_machine_docs.md)
- [Animation Guidelines](animation_plugins/animation_guidelines.md)
