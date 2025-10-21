# Animation Creation Workflow

Complete workflow for creating expressive animations for LuxoPi.

## Overview

The animation system now supports:
- **Auto-calculated durations** based on movement distance
- **Hand/antenna variations** for emotional expression (eyebrows)
- **Acceleration variations** for natural movement dynamics

## Workflow

### 1. Record Animation

Use the animation recorder to manually position and record keyframes:

```bash
cd /home/pi/luxopi-ros/dev
python3 animation_recorder.py
```

**Features:**
- Robot enters DEMA mode (fully limp)
- Move robot to positions and press **R** to record
- Durations auto-calculated based on movement distance
- Saves to `animations/json/`

**Example Output:**
```
✓ Keyframe 1 recorded (duration: 0.50s):
  Base:        -3.45° (-0.0602 rad)
  Shoulder:   -87.65° (-1.5297 rad)
  ...

✓ Keyframe 2 recorded (duration: 0.82s):
  ...
```

Durations are calculated based on:
- Angular distance between keyframes
- Base speed of 2.0 radians/second
- Minimum duration of 0.3s

### 2. Convert to Python Plugin

Convert JSON to Python animation plugin with auto-variations:

```bash
# Preview conversion
python3 json_to_animation.py animations/json/animation_hopping_20251020.json

# Save to file
python3 json_to_animation.py animations/json/animation_hopping_20251020.json \
    -o hopping_animation.py

# Install directly to plugins directory
python3 json_to_animation.py animations/json/animation_hopping_20251020.json --install
```

**Auto-Variations:**

**Hand/Antenna (Eyebrows):**
- Range: 0.5 to 2.6 radians
- Low (0.5-1.0): Droopy, sad, relaxed
- Mid (1.0-1.8): Neutral, normal
- High (1.8-2.6): Alert, excited, surprised
- Based on shoulder position and sequence

**Acceleration:**
- Range: 10.0 to 22.5
- Low (10.0-12.0): Smooth, gentle, flowing
- Mid (12.0-16.0): Normal, natural
- High (16.0-22.5): Snappy, quick, energetic
- Based on movement distance

**Disable Auto-Variations:**
```bash
# Use original values from JSON
python3 json_to_animation.py animation.json \
    --no-auto-hand \
    --no-auto-acc \
    --no-auto-durations
```

### 3. Register Animation

After installing, register in the animation system:

**Edit:** `/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins/custom_animations.py`

```python
# Import your animation
from .animation_hopping import HoppingAnimation

# Add to get_plugins()
def get_plugins():
    return [
        # ... existing animations
        HoppingAnimation(),
    ]
```

### 4. Build and Test

```bash
cd /home/pi/luxopi-ros
colcon build --packages-select luxo_behaviors
source install/setup.bash

# Test the animation
ros2 action send_goal /play_animation luxo_interfaces/action/PlayAnimation \
    "{animation_name: 'hopping'}"
```

## Animation Format

### JSON Format (Recorder Output)

```json
{
  "name": "hopping",
  "description": "Animation created with recorder on 2025-10-20 20:50",
  "category": "custom",
  "created": "2025-10-20T20:50:43",
  "keyframes": [
    {
      "servos": {
        "base": -0.0602,
        "shoulder": -1.5297,
        "elbow": 2.3449,
        "wrist": 0.5724,
        "hand": 1.0937,
        "roll": -1.5,
        "spd": 0,
        "acc": 10.0
      },
      "timing": 1.0,
      "duration": 0.31
    }
  ],
  "keyframe_count": 12
}
```

### Python Format (Plugin Output)

```python
keyframes = [
    [base, shoulder, elbow, wrist, roll, acceleration, hand/antenna],
    [-0.06, -1.53, 2.34, 0.57, -1.50, 12.6, 1.45],
    [-0.06, -1.43, 1.84, 0.56, -1.50, 12.7, 1.40],
    ...
]

durations = [0.31, 0.35, 0.71, 0.57, ...]
```

## Understanding Hand/Antenna Position

The hand joint controls the "eyebrows" (antenna position) for emotional expression:

```
2.6 rad (149°) ━━━━━━━  Very alert, surprised, excited
2.0 rad (115°) ━━━━━    Alert, attentive
1.5 rad ( 86°) ━━━      Neutral, normal
1.0 rad ( 57°) ━        Relaxed, calm
0.5 rad ( 29°) _        Droopy, sad, sleepy
```

**Tips:**
- Vary hand position throughout animation for liveliness
- Higher positions = more energetic/alert
- Lower positions = more relaxed/tired
- Quick changes = surprised/startled
- Slow changes = mood shifts

## Understanding Acceleration

Acceleration affects movement feel:

```
22.5 ━━━━━  Very snappy, jerky, robotic
16.0 ━━━━   Quick, energetic, playful
12.0 ━━     Normal, natural
10.0 ━      Smooth, gentle, flowing
```

**Tips:**
- Large movements: Use lower acceleration (10-12) for smoothness
- Small movements: Can use higher acceleration (14-18) for snap
- Emotional states:
  - Happy/Excited: Higher acceleration (14-18)
  - Sad/Tired: Lower acceleration (10-12)
  - Surprised: Mix of high and low

## Duration Calculation

Durations are auto-calculated using:

```python
# Calculate angular distance
distance = sum of absolute differences for all joints

# Calculate time
duration = max(0.3, distance / base_speed)
# where base_speed = 2.0 rad/s
```

**Examples:**
- Small movement (0.5 rad): 0.30s (minimum)
- Medium movement (1.5 rad): 0.75s
- Large movement (3.0 rad): 1.50s

## File Locations

```
/home/pi/luxopi-ros/dev/
├── animation_recorder.py          # Record animations
├── json_to_animation.py          # Convert JSON to Python
├── animations/
│   └── json/                     # Saved JSON animations
│       ├── animation_hopping_20251020.json
│       └── animation_bowing_20251020.json
└── ANIMATION_WORKFLOW.md         # This file

/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins/
├── animation_hopping.py          # Installed animations
├── custom_animations.py          # Registration file
└── ...
```

## Tips for Great Animations

### Recording
1. **Plan ahead**: Sketch key poses before recording
2. **Use DEMA**: Robot is limp - support it if needed
3. **Record deliberately**: Move slowly between positions
4. **Check duration**: First keyframe shows calculated duration to next
5. **Preview often**: Use [P] in menu to see how it looks

### Expression
1. **Hand variations**: Change antenna/eyebrow position frequently
2. **Acceleration**: Vary for emotional impact
3. **Timing**: Let auto-calculation guide you, but edit if needed
4. **Disney principles**:
   - Anticipation: Small opposite movement first
   - Follow-through: Overshoot and settle
   - Arcs: Natural curved motions

### Editing
1. **Duration**: Edit in JSON or let conversion script recalculate
2. **Hand**: Use auto-suggest or manually set per keyframe
3. **Acceleration**: Use auto-suggest based on movement type
4. **Reorder**: Use [E] menu to reorganize keyframes

## Troubleshooting

### Animation looks jerky
- Durations too short - increase in JSON
- Acceleration too high - reduce to 10-12
- Missing intermediate keyframes - record more poses

### Animation looks slow/boring
- Durations too long - let auto-calculate or reduce
- Acceleration too low - increase to 14-18
- Hand not varying - add more expression

### Robot doesn't move smoothly
- Check joint limits aren't being hit
- Verify positions are reachable
- Increase tolerance in playback (currently ±12°)

### Conversion script issues
- Verify JSON format is correct
- Check keyframes have all required fields
- Use `--no-auto-*` flags to disable features

## Examples

### Recording a "Happy Hop"
1. Record: Compress down, spring up, settle
2. Auto-durations: 0.5s down, 0.3s up, 0.8s settle
3. Convert with auto-variations
4. Result: High antenna on up, lower on down, smooth transitions

### Recording a "Tired Yawn"
1. Record: Stretch up slowly, hold, droop down
2. Auto-durations: 1.2s up, 0.5s hold, 1.0s down
3. Convert with auto-variations
4. Result: Low antenna throughout, gentle acceleration

### Recording a "Surprised Look"
1. Record: Quick recoil, peek forward
2. Auto-durations: 0.3s recoil, 0.6s peek
3. Convert with auto-variations
4. Result: High antenna on recoil, varied acceleration

## Future Enhancements

Ideas for improvement:
- [ ] Manual hand/acceleration editing in recorder
- [ ] Visual preview of keyframes
- [ ] Import existing animations for editing
- [ ] Batch conversion of multiple JSONs
- [ ] Animation blending/merging
- [ ] Emotion presets for auto-variations
- [ ] Speed multiplier adjustment
