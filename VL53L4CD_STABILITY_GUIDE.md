# VL53L4CD Stability Detection Guide

## Overview

The VL53L4CD distance sensors (left and right) now use a sophisticated stability check to prevent false collision alerts from erratic readings or sensor noise.

## New Detection Algorithm

### Requirements for Collision Detection

A collision is only detected when **ALL** of the following conditions are met:

1. **5 Consecutive Readings**: Must have 5 valid readings in history
2. **Stability Check**: All 5 readings must be within 0.5cm of each other
3. **Minimum Distance**: The minimum value must be >= 1.6cm
4. **Below Threshold**: The stable distance must be < threshold (default: 7.0cm)

### What Gets Filtered Out

This new logic automatically filters:

- **Erratic Readings**: `4cm, 2cm, 10cm, 5cm, 3cm` - range spread = 8cm (> 0.5cm threshold)
- **Too Close Readings**: `1.5cm, 1.4cm, 1.5cm, 1.5cm, 1.4cm` - min value < 1.6cm
- **Sensor Errors**: `0.0cm` readings are ignored entirely
- **Unstable Readings**: Any set where max - min > 0.5cm

### What Gets Detected

Valid collision scenarios:

- **Stable Approach**: `3.0cm, 2.8cm, 2.9cm, 3.0cm, 2.9cm` - range = 0.2cm ✓
- **Steady Decrease**: `4.0cm, 3.8cm, 3.7cm, 3.6cm, 3.5cm` - range = 0.5cm ✓
- **Close but Stable**: `2.0cm, 1.9cm, 2.0cm, 2.1cm, 2.0cm` - range = 0.2cm ✓

## Technical Implementation

### Configuration Parameters

Located in `collision_ros_node.py`:

```python
# VL53L4CD stability tracking
self.left_distance_history = deque(maxlen=5)
self.right_distance_history = deque(maxlen=5)
self.vl53_stability_threshold = 0.5  # cm - readings must be within 0.5cm
self.vl53_min_valid_distance = 1.6   # cm - minimum distance to consider valid
```

### Stability Check Logic

```python
def is_stable_reading(self, history):
    """
    Check if VL53L4CD readings are stable.
    Requires:
    - 5 consecutive readings
    - All within 0.5cm of each other (even if decreasing)
    - Minimum value >= 1.6cm

    Returns: (is_stable, min_value)
    """
    if len(history) < 5:
        return False, None

    readings = list(history)
    min_value = min(readings)

    # Check minimum threshold
    if min_value < self.vl53_min_valid_distance:
        return False, None

    # Check stability
    max_value = max(readings)
    range_spread = max_value - min_value

    if range_spread <= self.vl53_stability_threshold:
        return True, min_value

    return False, None
```

### Reading Flow

```
Sensor Reading → Add to history (deque) → Check stability
                                           ↓
                                   5 readings? → No → Publish "safe"
                                           ↓ Yes
                                   Range <= 0.5cm? → No → Publish "safe"
                                           ↓ Yes
                                   Min >= 1.6cm? → No → Publish "safe"
                                           ↓ Yes
                                   Distance < threshold? → No → Publish "safe"
                                           ↓ Yes
                                   COLLISION DETECTED ✓
```

## Timing Behavior

- **Collision Timer**: Evaluates every 0.1 seconds (10 Hz)
- **Reading History**: Deque with maxlen=5
- **Detection Latency**: Minimum 0.5 seconds (5 readings × 0.1s)
- **False Positive Immunity**: ~0.5 seconds of stable reading required

## Debugging and Monitoring

### Check Collision Status

```bash
# Monitor left/right collision status
ros2 topic echo /collision/left/status
ros2 topic echo /collision/right/status

# Monitor overall severity
ros2 topic echo /collision/severity

# Monitor raw distance values
ros2 topic echo /i2c/vl53_left/distance
ros2 topic echo /i2c/vl53_right/distance
```

### Enable Debug Logging

The collision node logs debug messages when collisions are detected:

```
[collision_node]: Left collision warning! Stable distance: 3.2 cm (5 readings), Severity: warning
[collision_node]: Right collision warning! Stable distance: 2.8 cm (5 readings), Severity: danger
```

To see these, launch with verbose mode:

```bash
ros2 launch luxo_behaviors luxo_system.launch.py verbose:=true
```

Or set log level for collision_node:

```bash
ros2 run luxo_behaviors collision_ros_node --ros-args --log-level debug
```

## Example Scenarios

### Scenario 1: Robot Movement (Filtered)

```
Reading History: [8.0, 12.0, 6.0, 15.0, 9.0] cm
Range Spread: 15.0 - 6.0 = 9.0 cm
9.0 cm > 0.5 cm threshold → NOT STABLE → No collision
```

**Result**: False positive filtered ✓

### Scenario 2: Approaching Object (Detected)

```
Reading History: [5.5, 5.3, 5.2, 5.1, 5.2] cm
Range Spread: 5.5 - 5.1 = 0.4 cm
Min value: 5.1 cm >= 1.6 cm
0.4 cm <= 0.5 cm threshold → STABLE
5.1 cm < 7.0 cm threshold → COLLISION DETECTED
```

**Result**: Valid collision ✓

### Scenario 3: Too Close (Filtered)

```
Reading History: [1.5, 1.4, 1.5, 1.5, 1.4] cm
Range Spread: 0.1 cm (stable)
Min value: 1.4 cm < 1.6 cm → TOO CLOSE
```

**Result**: Invalid distance filtered ✓

### Scenario 4: Decreasing Distance (Detected)

```
Reading History: [4.5, 4.2, 4.0, 3.9, 3.8] cm
Range Spread: 4.5 - 3.8 = 0.7 cm
0.7 cm > 0.5 cm threshold → NOT STABLE
```

**Result**: Not stable yet, wait for more readings

**After 2 more readings:**
```
Reading History: [4.0, 3.9, 3.8, 3.7, 3.7] cm
Range Spread: 4.0 - 3.7 = 0.3 cm
0.3 cm <= 0.5 cm threshold → STABLE
3.7 cm < 7.0 cm threshold → COLLISION DETECTED
```

**Result**: Valid collision after stabilization ✓

## Tuning Parameters

If you need to adjust sensitivity:

### Make More Sensitive (Detect Sooner)

```python
# In collision_ros_node.py __init__:
self.vl53_stability_threshold = 0.8  # Allow larger variations (default: 0.5)
self.vl53_min_valid_distance = 1.0   # Accept closer readings (default: 1.6)
```

**Trade-off**: More false positives from noise

### Make Less Sensitive (Fewer False Positives)

```python
# In collision_ros_node.py __init__:
self.vl53_stability_threshold = 0.3  # Require tighter grouping (default: 0.5)
self.vl53_min_valid_distance = 2.0   # Ignore very close readings (default: 1.6)
```

**Trade-off**: May miss valid collisions

## Comparison: Old vs New

### Old Logic (2 Consecutive Readings)

```python
if (current_left_distance < threshold and
    prev_left_distance < threshold):
    COLLISION_DETECTED
```

**Problems**:
- False positives from brief noise spikes
- No stability validation
- Reacted to single erratic readings
- Example: [8cm, 2cm] → Collision (WRONG)

### New Logic (5 Stable Readings)

```python
if is_stable_reading(last_5_readings):
    if stable_distance < threshold:
        COLLISION_DETECTED
```

**Improvements**:
- Filters noise and erratic readings
- Requires sustained proximity
- Validates minimum distance
- Example: [8cm, 2cm, 10cm, 5cm, 3cm] → No Collision (CORRECT)

## Testing Procedure

### Test 1: Erratic Motion (Should NOT Trigger)

```bash
# Move your hand rapidly near the sensor
# Expected: No collision alerts (readings too unstable)
```

### Test 2: Steady Approach (Should Trigger)

```bash
# Slowly move object toward sensor
# Expected: Collision alert after ~0.5 seconds of stable proximity
```

### Test 3: Very Close (Should NOT Trigger)

```bash
# Place object at 1.0-1.5 cm
# Expected: No collision alerts (below minimum threshold)
```

### Test 4: Monitor Stability

```bash
# Terminal 1: Watch raw readings
ros2 topic echo /i2c/vl53_left/distance

# Terminal 2: Watch collision status
ros2 topic echo /collision/left/status

# Move object smoothly from 10cm → 3cm
# Expected: Collision triggers when readings stabilize below threshold
```

## Integration with Other Systems

### Behavior Coordinator

The behavior coordinator receives collision status via:
- `/collision/left/status` (Bool)
- `/collision/right/status` (Bool)
- `/collision/severity` (String)

The new stability logic doesn't change these topics, only improves accuracy.

### Animation System

Collision detection triggers:
- Collision avoidance behaviors
- Escape mode (if persistent)
- State transitions

The new logic prevents false triggers that could interrupt normal operation.

## Troubleshooting

### Issue: No Collisions Detected

**Possible Causes**:
1. Readings not stable enough (vary > 0.5cm)
2. Distance below 1.6cm threshold
3. VL53L4CD sensors disabled

**Solutions**:
```bash
# Check if sensors are enabled
ros2 param get /i2c_device_manager enable_vl53_left
ros2 param get /i2c_device_manager enable_vl53_right

# Monitor raw readings for stability
ros2 topic echo /i2c/vl53_left/distance

# Check sensor health
ros2 topic echo /i2c/sensor_health
```

### Issue: False Positives Still Occurring

**Possible Causes**:
1. Stability threshold too loose (0.5cm may be too large)
2. Minimum distance too low
3. Environmental interference

**Solutions**:
- Tighten stability threshold to 0.3cm
- Increase minimum distance to 2.0cm
- Check for vibration or electrical noise

### Issue: Delayed Detection

**Expected Behavior**: 0.5-second latency is normal (5 readings required)

If delay is longer:
- Check collision_timer frequency (should be 0.1s)
- Verify sensor publish rate (should be 10+ Hz)

## Related Documentation

- `VL53L4CD_TOGGLE_GUIDE.md` - Enable/disable sensors
- `CLAUDE.md` - Full system architecture
- `collision_ros_node.py` - Source code

## Key Takeaways

1. **5 stable readings required** - prevents false positives
2. **0.5cm stability window** - filters erratic data
3. **1.6cm minimum** - ignores very close/invalid readings
4. **~0.5s latency** - necessary trade-off for accuracy
5. **Backward compatible** - same topics, better accuracy
