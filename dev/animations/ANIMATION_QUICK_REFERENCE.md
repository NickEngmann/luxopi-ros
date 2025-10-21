# Animation Toolchain - Quick Reference

## Common Commands

### Create New Animation
```bash
python3 animation_recorder.py
# Move robot → 'R' to record → 'F' to finish → Name it → Save
```

### Edit Existing Animation
```bash
# Step 1: Convert to JSON (if from Python)
python3 animation_to_json.py AnimationName

# Step 2: Interactive editing
python3 animation_recorder.py --preview animations/json/animation_NAME_*.json
# [S] Step through → [E] Edit keyframes → [V] Save

# Step 3: Install back
python3 json_to_animation.py animations/json/animation_NAME_*.json --install
```

### Convert All Commented Animations
```bash
python3 animation_to_json.py --all-commented
```

### Deploy to Production
```bash
python3 json_to_animation.py animations/json/animation_NAME.json --install
cd /home/pi/luxopi-ros
colcon build --packages-select luxo_behaviors
source install/setup.bash
```

## Preview Mode Controls

### Main Menu
- `[P]` - Play full animation
- `[S]` - Step through
- `[E]` - Edit keyframe
- `[L]` - List all keyframes
- `[V]` - Save
- `[Q]` - Quit

### Step-Through Mode
- `[N]` - Next keyframe
- `[P]` - Previous keyframe
- `[E]` - Edit current
- `[J]` - Jump to number
- `[M]` - Main menu

## File Locations

```
/home/pi/luxopi-ros/dev/
├── animation_recorder.py       # Main tool
├── json_to_animation.py        # JSON → Python
├── animation_to_json.py        # Python → JSON
└── animations/json/            # All JSON files

/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins/
├── custom_animations.py        # Register here
└── animation_*.py              # Installed animations
```

## JSON Structure
```json
{
  "name": "animation_name",
  "keyframes": [
    {
      "servos": {
        "base": 0.0,        // ±90° base rotation
        "shoulder": 0.2,    // 0-180° shoulder
        "elbow": 1.4,       // 0-180° elbow
        "wrist": 0.8,       // 0-180° wrist
        "hand": 1.5,        // 0.5-2.6 expression
        "roll": -1.5,       // -2.5 to -0.5
        "acc": 13.0         // 10-22.5 acceleration
      },
      "duration": 0.7       // Seconds to reach
    }
  ]
}
```

## Common Workflows

### Fix Jerky Transition
```bash
python3 animation_recorder.py --preview animation.json
[S] Step from keyframe 5
[N] → KF 6 (see problem)
[P] ← KF 5
[E] Edit KF 5 or 6
[N] Test forward
[P] Test backward
[V] Save
```

### Adjust Animation Speed
```bash
# Option 1: Duration calibration
python3 animation_recorder.py --preview animation.json
[P] Play full → Accept calibrated durations → [V] Save

# Option 2: Speed multiplier (ROS only)
ros2 action send_goal /play_animation ... "{..., speed_multiplier: 1.5}"
```

### Batch Convert
```bash
for f in animations/json/*.json; do
    python3 json_to_animation.py "$f" --install
done
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Robot shoots up on start | Normal - DEMA enabled, support robot |
| Keyframe reverts after edit | Fixed - robot stays at edited position |
| Save fails | Fixed - datetime import corrected |
| Animation too fast | Increase durations, reduce acceleration |
| Animation too slow | Decrease durations, increase acceleration |
| Jerky movement | Add intermediate keyframes, smooth durations |

## Tips

- ✅ Always preview before deploying
- ✅ Use step-through to isolate problems
- ✅ Save incrementally (timestamps preserve versions)
- ✅ Test transitions in both directions (N and P)
- ✅ Keep hand position varied for expression
- ✅ Match acceleration to emotion (low=calm, high=energetic)

## Expression Guide

### Hand/Antenna Values
- `0.5-1.0` - Sad, droopy, tired
- `1.0-1.8` - Neutral, normal
- `1.8-2.6` - Excited, alert, surprised

### Acceleration Values
- `10-12` - Smooth, gentle, flowing
- `12-16` - Normal, natural
- `16-22.5` - Snappy, energetic, quick

## Get Help

```bash
python3 animation_recorder.py --help
python3 json_to_animation.py --help
python3 animation_to_json.py --help
```

Full documentation: `ANIMATION_TOOLCHAIN.md`
