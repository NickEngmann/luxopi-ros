# State Machine Module

## Overview
The `state_machine` module implements a finite state machine (FSM) for managing Luxo behaviors and transitions between different animation states.

## State Machine Architecture

The state machine uses a hierarchical approach to manage complex behavior states:

```python
class State:
    def __init__(self, name):
        self.name = name
        self.transitions = {}
        self.enter_callbacks = []
        self.exit_callbacks = []
        self.update_callbacks = []
    
    def on_enter(self, context):
        for callback in self.enter_callbacks:
            callback(context)
    
    def on_exit(self, context):
        for callback in self.exit_callbacks:
            callback(context)
    
    def on_update(self, context, dt):
        for callback in self.update_callbacks:
            callback(context, dt)
    
    def add_transition(self, event, target_state):
        self.transitions[event] = target_state
    
    def handle_event(self, context, event):
        if event in self.transitions:
            return self.transitions[event]
        return None

class StateMachine:
    def __init__(self, initial_state=None):
        self.states = {}
        self.current_state = initial_state
        self.context = {}
    
    def add_state(self, state):
        self.states[state.name] = state
    
    def set_initial_state(self, state_name):
        if state_name in self.states:
            self.current_state = self.states[state_name]
            self.current_state.on_enter(self.context)
    
    def update(self, dt):
        if self.current_state:
            self.current_state.on_update(self.context, dt)
    
    def send(self, event):
        if self.current_state:
            next_state = self.current_state.handle_event(self.context, event)
            if next_state:
                self.current_state.on_exit(self.context)
                self.current_state = self.states[next_state]
                self.current_state.on_enter(self.context)
```

## Built-in States

### `IdleState`
Default state when no specific behavior is active.

**Transitions:**
- `start_animation` -> `AnimationState`
- `detect_collision` -> `CollisionState`
- `start_vision` -> `VisionState`

**Implementation:**
```python
class IdleState(State):
    def __init__(self):
        super().__init__('idle')
        self.add_transition('start_animation', 'animation')
        self.add_transition('detect_collision', 'collision')
        self.add_transition('start_vision', 'vision')
    
    def on_enter(self, context):
        context['behavior'] = 'idle'
        context['animation_queue'].clear()
    
    def on_update(self, context, dt):
        # Monitor for triggers
        if context.get('trigger_animation'):
            context['pending_event'] = 'start_animation'
        if context.get('collision_detected'):
            context['pending_event'] = 'detect_collision'
```

### `AnimationState`
Handles active animation playback.

**Transitions:**
- `animation_complete` -> `IdleState`
- `interrupt` -> `CollisionState`
- `pause` -> `PausedState`

**Implementation:**
```python
class AnimationState(State):
    def __init__(self):
        super().__init__('animation')
        self.add_transition('animation_complete', 'idle')
        self.add_transition('interrupt', 'collision')
        self.add_transition('pause', 'paused')
    
    def on_enter(self, context):
        context['behavior'] = 'animation'
        context['animation_queue'].play_next()
    
    def on_update(self, context, dt):
        if context['animation_queue'].is_playing:
            context['animation_queue'].update()
            if context['animation_queue'].current_command and \
               context['animation_queue'].current_command.is_complete():
                context['pending_event'] = 'animation_complete'
        else:
            context['pending_event'] = 'animation_complete'
```

### `CollisionState`
Handles collision detection and response.

**Transitions:**
- `collision_resolved` -> `IdleState`
- `emergency_stop` -> `EmergencyState`

**Implementation:**
```python
class CollisionState(State):
    def __init__(self):
        super().__init__('collision')
        self.add_transition('collision_resolved', 'idle')
        self.add_transition('emergency_stop', 'emergency')
    
    def on_enter(self, context):
        context['behavior'] = 'collision'
        context['collision_handler'].trigger_response()
    
    def on_update(self, context, dt):
        if context['collision_handler'].is_resolved():
            context['pending_event'] = 'collision_resolved'
        elif context['collision_handler'].is_critical():
            context['pending_event'] = 'emergency_stop'
```

### `PausedState`
Handles paused animation state.

**Transitions:**
- `resume` -> `AnimationState`
- `cancel` -> `IdleState`

**Implementation:**
```python
class PausedState(State):
    def __init__(self):
        super().__init__('paused')
        self.add_transition('resume', 'animation')
        self.add_transition('cancel', 'idle')
    
    def on_enter(self, context):
        context['behavior'] = 'paused'
        context['animation_queue'].pause()
    
    def on_update(self, context, dt):
        # Paused state doesn't update animation
        pass
```

### `EmergencyState`
Handles emergency stop conditions.

**Transitions:**
- `emergency_cleared` -> `IdleState`

**Implementation:**
```python
class EmergencyState(State):
    def __init__(self):
        super().__init__('emergency')
        self.add_transition('emergency_cleared', 'idle')
    
    def on_enter(self, context):
        context['behavior'] = 'emergency'
        context['arm_controller'].emergency_stop()
    
    def on_update(self, context, dt):
        if context['emergency_handler'].is_cleared():
            context['pending_event'] = 'emergency_cleared'
```

## State Machine Manager

The `StateMachineManager` coordinates multiple state machines:

```python
class StateMachineManager:
    def __init__(self):
        self.main_machine = StateMachine()
        self.submachines = {}
        self.context = {}
        self._setup_states()
    
    def _setup_states(self):
        idle = IdleState()
        animation = AnimationState()
        collision = CollisionState()
        paused = PausedState()
        emergency = EmergencyState()
        
        self.main_machine.add_state(idle)
        self.main_machine.add_state(animation)
        self.main_machine.add_state(collision)
        self.main_machine.add_state(paused)
        self.main_machine.add_state(emergency)
        
        self.main_machine.set_initial_state('idle')
    
    def update(self, dt):
        self.main_machine.update(dt)
        for machine in self.submachines.values():
            machine.update(dt)
        
        # Process pending events
        if self.main_machine.context.get('pending_event'):
            event = self.main_machine.context.pop('pending_event')
            self.main_machine.send(event)
    
    def get_current_state(self):
        return self.main_machine.current_state.name if self.main_machine.current_state else None
```

## Usage Example

```python
from state_machine import StateMachineManager

# Create manager
manager = StateMachineManager()

# Update loop
while True:
    manager.update(0.016)  # 60 FPS
    print(f"Current state: {manager.get_current_state()}")
    time.sleep(0.016)
```
