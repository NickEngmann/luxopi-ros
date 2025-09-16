# Motor Resistance Detection System

## Overview
The motor resistance detection system monitors the difference between commanded joint positions and actual positions reported by the motors. When the robot encounters physical resistance (hitting an obstacle, being held, etc.), this system detects the blockage and triggers appropriate safety responses.

## How It Works

1. **Position Monitoring**: The system continuously compares `target_joints` (commanded positions) with `current_joints` (actual feedback from motors)

2. **Resistance Detection**: When the difference exceeds a threshold (default: 0.15 radians ≈ 8.6°) for a sustained period (default: 1 second), resistance is detected

3. **Progressive Response**:
   - **Light resistance** (1-4 detections): Reduce movement speed
   - **Moderate resistance** (5-14 detections): Back off and trigger COLLISION_AVOIDING state
   - **Severe resistance** (15+ detections): Trigger ESCAPE_MODE for emergency avoidance

## Configuration

Launch parameters:
```bash
ros2 launch luxo_behaviors luxo_system.launch.py \
    enable_motor_resistance_detection:=true \
    motor_resistance_threshold:=0.15 \
    motor_resistance_time_threshold:=1.0
```

## Monitoring

### Check resistance status:
```bash
ros2 topic echo /motor_resistance/status
```

### Test resistance detection:
```bash
ros2 run luxo_behaviors test_motor_resistance.py
```

## Integration with Collision System

The motor resistance detection works alongside the existing proximity-based collision system:

- **Proximity sensors**: Detect obstacles before contact
- **Motor resistance**: Detects actual physical contact or blockage
- **Combined protection**: Multi-layer safety system

## Benefits

1. **Hardware Protection**: Prevents motor damage from prolonged stalling
2. **Safety**: Detects unexpected collisions not seen by proximity sensors
3. **User Interaction**: Allows detection of gentle physical guidance
4. **Fallback Protection**: Works even if proximity sensors fail

## Status Messages

The system publishes to `/motor_resistance/status`:
- `NO_RESISTANCE`: Normal operation
- `RESISTANCE_DETECTED: joints=[...], detections=[...]`: Active resistance with details

## Testing

1. Start the robot system
2. Run the test monitor: `ros2 run luxo_behaviors test_motor_resistance.py`
3. Command the robot to move (animation or manual control)
4. Gently hold or block the arm during movement
5. Observe resistance detection and automatic response

## Safety Notes

- The system automatically clears resistance tracking when:
  - New movement commands are issued
  - State changes occur (except collision states)
  - Target positions are reached

- Resistance detection is disabled during:
  - INITIALIZING state
  - ERROR state
  - When motor resistance detection is disabled via parameter