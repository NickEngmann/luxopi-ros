# Animation Tools Summary

## Completed Tasks

### 1. ✅ animation_to_json.py Script
Created a Python script to convert Python animation classes to JSON format.

**Features:**
- Extracts commented-out animation classes from animation plugin files
- Converts Python keyframe format to JSON format
- Handles `base_pos` variable expressions
- Converts all 7 keyframe values (base, shoulder, elbow, wrist, roll, acc, hand)
- Preserves keyframe names if available
- Auto-generates timestamps

**Usage:**
```bash
# Convert a specific animation
python3 animation_to_json.py StretchingAnimation

# Convert all commented animations
python3 animation_to_json.py --all-commented

# Convert from specific file
python3 animation_to_json.py --file action_animations.py DancingAnimation

# Specify output directory
python3 animation_to_json.py --output /custom/path StretchingAnimation
```

### 2. ✅ Converted All Commented Animations
Successfully converted 5 commented animations to JSON:

| Animation | Class Name | Category | Keyframes | File |
|-----------|------------|----------|-----------|------|
| stretch | StretchingAnimation | action | 20 | animation_stretch_*.json |
| dance | DancingAnimation | action | 16 | animation_dance_*.json |
| excited | ExcitedHopAnimation | emotion | 18 | animation_excited_*.json |
| sad | SadDroopAnimation | emotion | 15 | animation_sad_*.json |
| playful | PlayfulBounceAnimation | emotion | 18 | animation_playful_*.json |

All animations are now available in:
`/home/pi/luxopi-ros/dev/animations/json/`

### 3. ✅ Enhanced Preview Mode with Keyframe Editing
Added comprehensive editing functionality to the preview mode in `animation_recorder.py`.

**New Features:**

#### Preview Edit Menu
After previewing an animation, you now get a menu with these options:
- **[E] - Edit a specific keyframe** - Select and edit individual keyframes
- **[P] - Re-preview animation** - Play the animation again with changes
- **[L] - List all keyframes** - View all keyframe positions
- **[S] - Save edited animation** - Save with new timestamp
- **[Q] - Quit without saving** - Discard changes

#### Keyframe Editing Workflow
1. **Select keyframe** - Choose which keyframe to edit (1-N)
2. **View current position** - See current joint angles
3. **Move to position** - Robot moves to current keyframe position
4. **Enable DEMA** - Robot becomes limp for manual positioning
5. **Manually position** - Move robot to new desired position
6. **Record new position** - Press ENTER to capture new position
7. **Continue editing** - Edit more keyframes or re-preview

#### Save Options
- Optional rename before saving
- Automatically generates new timestamp
- Saves to `animations/json/animation_NAME_TIMESTAMP.json`
- Preserves original animation metadata (description, category)

**Usage:**
```bash
# Preview and edit an animation
python3 animation_recorder.py --preview animations/json/animation_stretch_20251020_213612.json
```

## Animation Workflow

### Complete End-to-End Workflow

1. **Record New Animation**
   ```bash
   python3 animation_recorder.py
   # Move robot, press 'R' to record keyframes, 'F' to finish
   ```

2. **Convert Commented Animation to JSON**
   ```bash
   python3 animation_to_json.py --all-commented
   # Or convert specific animation:
   python3 animation_to_json.py StretchingAnimation
   ```

3. **Preview and Edit**
   ```bash
   python3 animation_recorder.py --preview animations/json/animation_stretch_*.json
   # In preview menu:
   # - [E] to edit keyframes
   # - [P] to re-preview
   # - [S] to save edited version
   ```

4. **Convert to Python Plugin**
   ```bash
   python3 json_to_animation.py animations/json/animation_stretch_*.json --install
   # Or save to file first:
   python3 json_to_animation.py animations/json/animation_stretch_*.json -o stretch.py
   ```

5. **Register in Animation System**
   - Edit `custom_animations.py`
   - Import the new animation class
   - Add to `get_plugins()` list
   - Rebuild: `colcon build --packages-select luxo_behaviors`

## File Locations

```
/home/pi/luxopi-ros/dev/
├── animation_recorder.py          # Record & preview animations
├── animation_to_json.py          # Python → JSON converter
├── json_to_animation.py          # JSON → Python converter
├── animations/
│   └── json/                     # All JSON animations
│       ├── animation_bowing_*.json
│       ├── animation_hopping_*.json
│       ├── animation_stretch_*.json
│       ├── animation_dance_*.json
│       ├── animation_excited_*.json
│       ├── animation_sad_*.json
│       └── animation_playful_*.json
└── ANIMATION_WORKFLOW.md         # Detailed workflow guide
```

## JSON Format

### Structure
```json
{
  "name": "animation_name",
  "description": "Animation description",
  "category": "action|emotion|custom",
  "created": "2025-10-20T21:36:12.859269",
  "keyframes": [
    {
      "servos": {
        "base": 0.0,
        "shoulder": 0.2,
        "elbow": 1.4,
        "wrist": 0.8,
        "hand": 1.5,
        "roll": -1.5,
        "spd": 0,
        "acc": 13.0
      },
      "timing": 1.0,
      "duration": 0.7
    }
  ],
  "keyframe_count": 20
}
```

### Field Meanings
- **base, shoulder, elbow, wrist, hand**: Joint positions in RADIANS
- **roll**: Roll joint position (typically -1.5)
- **spd**: Speed parameter (typically 0)
- **acc**: Acceleration (10.0-22.5, affects movement feel)
- **timing**: Timing multiplier (typically 1.0)
- **duration**: Time to reach this keyframe from previous (seconds)

## Available Animations (JSON)

Current JSON animations ready for editing/testing:

1. **bowing** - Custom animation (6 keyframes)
2. **hopping** - Custom animation (12 keyframes)
3. **stretch** - Full-body stretch motion (20 keyframes) ⭐ NEW
4. **dance** - Rhythmic dance movements (16 keyframes) ⭐ NEW
5. **excited** - Energetic bouncy hop (18 keyframes) ⭐ NEW
6. **sad** - Slow drooping motion (15 keyframes) ⭐ NEW
7. **playful** - Playful bouncing (18 keyframes) ⭐ NEW

## Next Steps

To use these animations in the LuxoPi system:

1. **Test in Preview Mode** - Make sure they work correctly
2. **Edit as needed** - Use preview edit mode to refine keyframes
3. **Convert to Python** - Use `json_to_animation.py --install`
4. **Register** - Add to `custom_animations.py`
5. **Rebuild** - `colcon build --packages-select luxo_behaviors`
6. **Test in ROS** - `ros2 action send_goal /play_animation ...`

## Tips for Editing

### When to Edit
- Animation moves too fast/slow → Adjust durations
- Position doesn't look right → Edit specific keyframe
- Robot hits limits → Edit problematic keyframes
- Animation needs more expression → Adjust hand positions

### Editing Best Practices
1. **Preview first** - Always preview before editing
2. **Edit one keyframe at a time** - Don't change too much at once
3. **Re-preview after edits** - Verify changes work
4. **Save incrementally** - Save versions as you make improvements
5. **Use descriptive names** - e.g., "stretch_v2_smoother"

## Troubleshooting

### Animation conversion issues
- Check that class inherits from `AnimationPlugin`
- Verify `get_keyframes()` returns `(keyframes, durations)`
- Ensure proper indentation in commented code

### Preview/edit issues
- Make sure robot is connected on `/dev/ttyAMA0`
- DEMA must be working for manual positioning
- Check that JSON format is valid

### Keyframe editing not recording
- Wait for DEMA to fully enable before moving robot
- Disable DEMA before recording position
- Check serial connection is receiving feedback
