# LuxoPi Animation Plugins Documentation

## Overview

The `animation_plugins` package contains modular animation plugins that can be loaded dynamically by the animation command action server. Each plugin implements the `AnimationPluginBase` interface and belongs to one of several categories.

## Package Structure

### Available Animation Categories

The package exports five main categories of animations:

```python
__all__ = [
    'emotion_animations',      # Expressions of emotions
    'action_animations',       # Physical movements and gestures
    'response_animations',     # Reactions to stimuli
    'idle_animations',         # Default behaviors when idle
    'petting_animations'       # Responses to physical touch
]
```

## Animation Categories

### 1. Emotion Animations

Emotion animations express Luxo Jr's emotional state through movement and expression.

**Examples:**
- `luxo_happy`: Waving and bouncing with joy
- `luxo_sad`: Slow drooping movements
- `luxo_excited`: Rapid, energetic movements
- `luxo_surprised`: Quick head tilt and eye movement

**Characteristics:**
- Short duration (1-3 seconds)
- Expressive joint movements
- Often includes head and eye animations
- May trigger sound effects

**Implementation:**
```python
class HappyAnimation(AnimationPluginBase):
    def get_animation_name(self) -> str:
        return "luxo_happy"
    
    def get_animation_category(self) -> str:
        return "emotion"
    
    def execute(self) -> bool:
        # Happy expression sequence
        self.move_joint(0, 0.2, 0.3)
        self.move_joint(1, 0.1, 0.2)
        return True
```

### 2. Action Animations

Action animations are deliberate movements performed to accomplish tasks.

**Examples:**
- `luxo_wave`: Greeting wave gesture
- `luxo_dance`: Rhythmic movement sequence
- `luxo_point`: Pointing at objects
- `luxo_thumbs_up`: Positive gesture

**Characteristics:**
- Medium duration (2-5 seconds)
- Precise joint positioning
- Often involves multiple joints
- May require collision checking

**Implementation:**
```python
class WaveAnimation(AnimationPluginBase):
    def get_animation_name(self) -> str:
        return "luxo_wave"
    
    def get_animation_category(self) -> str:
        return "action"
    
    def execute(self) -> bool:
        # Wave sequence
        for i in range(5):
            self.move_joint(1, 0.5, 0.1)
            self.move_joint(1, -0.5, 0.1)
        return True
```

### 3. Response Animations

Response animations react to external stimuli or events.

**Examples:**
- `luxo_react_sound`: Response to audio input
- `luxo_react_light`: Response to light detection
- `luxo_react_collision`: Response to obstacle detection
- `luxo_react_voice`: Response to voice commands

**Characteristics:**
- Variable duration (1-4 seconds)
- Context-dependent behavior
- May include sensory feedback
- Often triggers other animations

**Implementation:**
```python
class SoundResponseAnimation(AnimationPluginBase):
    def get_animation_name(self) -> str:
        return "luxo_react_sound"
    
    def get_animation_category(self) -> str:
        return "response"
    
    def execute(self) -> bool:
        # React to sound
        self.move_joint(0, 0.3, 0.2)
        self.move_joint(1, 0.2, 0.2)
        return True
```

### 4. Idle Animations

Idle animations are default behaviors when no interaction is occurring.

**Examples:**
- `luxo_idle_breathe`: Gentle breathing motion
- `luxo_idle_look_around`: Scanning environment
- `luxo_idle_fidget`: Small random movements
- `luxo_idle_wait`: Stationary waiting pose

**Characteristics:**
- Continuous or looping
- Low energy consumption
- Subtle movements
- Maintains alertness

**Implementation:**
```python
class IdleBreatheAnimation(AnimationPluginBase):
    def get_animation_name(self) -> str:
        return "luxo_idle_breathe"
    
    def get_animation_category(self) -> str:
        return "idle"
    
    def execute(self) -> bool:
        # Breathing motion
        self.move_joint(1, 0.1, 0.05)
        self.move_joint(1, -0.1, 0.05)
        return True
```

### 5. Petting Animations

Petting animations respond to physical touch or interaction.

**Examples:**
- `luxo_pet_head`: Response to head pat
- `luxo_pet_back`: Response to back rub
- `luxo_pet_belly`: Response to belly touch
- `luxo_pet_paw`: Response to paw grab

**Characteristics:**
- Positive reinforcement
- Affectionate movements
- May include vocalization
- Often triggers happy emotion

**Implementation:**
```python
class HeadPetAnimation(AnimationPluginBase):
    def get_animation_name(self) -> str:
        return "luxo_pet_head"
    
    def get_animation_category(self) -> str:
        return "petting"
    
    def execute(self) -> bool:
        # Enjoy petting
        self.move_joint(0, -0.2, 0.1)
        self.move_joint(1, 0.1, 0.1)
        return True
```

## Animation Plugin Discovery

### Plugin Registration

Plugins are automatically discovered through the package's `__init__.py`:

```python
# In animation_plugins/__init__.py
__all__ = [
    'emotion_animations',
    'action_animations',
    'response_animations',
    'idle_animations',
    'petting_animations'
]
```

### Dynamic Loading

The animation command action server loads plugins dynamically:

```python
import importlib

def load_animation_plugin(module_name, class_name):
    plugin_module = importlib.import_module(
        f"luxo_behaviors.animation_plugins.{module_name}"
    )
    plugin_class = getattr(plugin_module, class_name)
    return plugin_class()
```

## Animation Execution Flow

### 1. Request Reception

Animation requests come through the ROS2 action server:

```python
# Animation command action
action = AnimationCommandAction()
action.execute(request)
```

### 2. Plugin Selection

The system selects the appropriate plugin based on:
- Animation name
- Category
- Current state
- Environmental conditions

### 3. Execution

The plugin executes its animation sequence:

```python
plugin = load_animation_plugin("emotion_animations", "HappyAnimation")
success = plugin.execute()
```

### 4. Completion

The system reports completion status:

```python
if success:
    action.send_feedback("Animation completed")
else:
    action.send_feedback("Animation failed")
```

## Animation Guidelines

### Joint Limits

Always respect joint limits to prevent damage:

| Joint | Name | Min (rad) | Max (rad) |
|-------|------|-----------|-----------|
| 0 | Base | -3.14 | 3.14 |
| 1 | Shoulder | -1.1 | 0.4 |
| 2 | Elbow | -2.5 | 0.5 |
| 3 | Wrist | -3.0 | 3.0 |

### Safety Constraints

1. **Never exceed joint limits** even for brief moments
2. **Consider momentum** when planning fast movements
3. **Test new animations** at lower speeds first
4. **Always include proper return home sequence**

### Performance Considerations

1. **Keep animations short** (under 5 seconds when possible)
2. **Use smooth transitions** between joint positions
3. **Avoid rapid direction changes**
4. **Monitor battery levels** during execution

## Animation State Machine Integration

Animations work with the state machine to ensure proper sequencing:

```python
# State machine checks animation requirements
if state_machine.can_transition("ANIMATING"):
    plugin = load_animation_plugin("action_animations", "WaveAnimation")
    if plugin.execute():
        state_machine.transition("IDLE")
```

## Testing Animation Plugins

### Unit Tests

Test individual animation components:

```python
def test_animation_name():
    plugin = HappyAnimation()
    assert plugin.get_animation_name() == "luxo_happy"

def test_animation_category():
    plugin = HappyAnimation()
    assert plugin.get_animation_category() == "emotion"
```

### Integration Tests

Test animation execution in context:

```python
def test_animation_execution():
    plugin = HappyAnimation()
    result = plugin.execute()
    assert result is True
```

## See Also

- [Animation Plugin Base Documentation](animation_plugin_base_docs.md)
- [Shared Utilities Documentation](shared_utils_docs.md)
- [Serial Manager Documentation](serial_manager_docs.md)
- [State Machine Documentation](state_machine_docs.md)
- [Animation Guidelines](animation_plugins/animation_guidelines.md)
