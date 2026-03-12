# State Machine Documentation

## Overview
The LuxoPi state machine manages the robot's behavior states and transitions between them. It provides a robust framework for handling complex interactions and state management.

## State Enum (LuxoState)

The `LuxoState` enum defines all possible states for the Luxo robot:

- **IDLE**: Robot is at rest, waiting for input
- **ANIMATING**: Playing a predefined animation sequence
- **VOICE_FOLLOWING**: Following voice commands or tracking audio source
- **COLLISION_AVOIDING**: Reacting to detected obstacles
- **RETURNING_HOME**: Moving back to home position after interruption
- **ESCAPE_MODE**: Emergency state for freeing from entrapment
- **USER_CONTROL**: Dynamic adaptation mode for manual control
- **EMOTION_REACTING**: Responding to emotional stimuli
- **PETTING**: High-priority state for petting interactions
- **ERROR**: Handling error conditions
- **INITIALIZING**: System startup and initialization
- **SHUTDOWN**: Graceful system shutdown

## StateTransition Class

Represents a state transition with conditions and actions:

### Attributes
- `from_state`: The source state for the transition
- `to_state`: The destination state for the transition
- `condition`: Optional function that returns True if transition is allowed
- `action`: Optional function to execute during transition

## LuxoStateMachine Class

The main state machine class that manages state transitions.

### Key Features
- Thread-safe state management
- Priority-based state handling
- Automatic transition validation
- Action execution on state changes

### Methods

#### `__init__`
Initialize the state machine with optional default state.

#### `set_state`
Set the current state, triggering transitions if needed.

#### `get_state`
Return the current state.

#### `add_transition`
Add a new state transition rule.

#### `add_handler`
Register a handler function for a specific state.

#### `is_state`
Check if the current state matches the specified state.

#### `transition_to`
Attempt to transition to a new state, respecting conditions.

## Usage Examples

### Basic State Machine
```python
from luxo_behaviors.state_machine import LuxoStateMachine, LuxoState

# Create state machine
sm = LuxoStateMachine()

# Set initial state
sm.set_state(LuxoState.IDLE)

# Check current state
if sm.is_state(LuxoState.IDLE):
    print("Robot is idle")
```

### Adding Transitions
```python
from luxo_behaviors.state_machine import LuxoStateMachine, LuxoState

def on_collision():
    print("Collision detected!")
    return True

sm = LuxoStateMachine()
sm.add_transition(LuxoState.IDLE, LuxoState.COLLISION_AVOIDING, condition=on_collision)
```

### State Handlers
```python
def idle_handler():
    print("Entering idle state")
    
def animating_handler():
    print("Starting animation")

sm = LuxoStateMachine()
sm.add_handler(LuxoState.IDLE, idle_handler)
sm.add_handler(LuxoState.ANIMATING, animating_handler)
```

## Thread Safety

The state machine is designed to be thread-safe. All state transitions and handlers are protected by locks to prevent race conditions.

## Error Handling

The state machine includes built-in error handling:
- Invalid state transitions are rejected
- Handler errors are caught and logged
- Automatic recovery to safe states

## Best Practices

1. **Define Clear Transitions**: Always specify conditions for state transitions
2. **Use Handlers**: Register handlers for important state changes
3. **Test Transitions**: Verify all state transitions work correctly
4. **Handle Errors**: Implement proper error handling in state transitions
5. **Document States**: Keep documentation updated for all states and transitions

## Integration with Other Components

The state machine integrates with:
- Animation plugins
- Collision detection system
- Voice following system
- Serial communication manager
- Shared utilities

## Future Enhancements

Potential improvements for the state machine:
- State persistence across restarts
- Visual state diagram generation
- State history tracking
- Advanced transition conditions
