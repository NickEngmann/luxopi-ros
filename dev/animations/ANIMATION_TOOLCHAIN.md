# LuxoPi Animation Toolchain

Complete end-to-end solution for creating, editing, refining, and deploying animations for the LuxoPi robot.

## Overview

This toolchain provides a professional workflow for animation development:

1. **Create** - Record new animations from scratch
2. **Convert** - Transform between JSON and Python formats
3. **Edit** - Refine existing animations with interactive preview
4. **Deploy** - Install animations into the ROS2 system

## The Tools

### 1. animation_recorder.py - Creation & Interactive Editing
**Purpose**: Record new animations and interactively edit existing ones

**Modes**:
- **Recording Mode** (default): Create animations from scratch
- **Preview Mode** (`--preview`): Interactive editing and refinement

**Key Features**:
- Full DEMA support for manual positioning
- Auto-calculated durations based on movement distance
- Step-through playback with next/previous navigation
- Inline keyframe editing during playback
- Duration calibration
- Saves to JSON format

### 2. json_to_animation.py - JSON to Python Conversion
**Purpose**: Convert JSON animations to production-ready Python plugins

**Key Features**:
- Auto-suggests hand/antenna variations for expression
- Auto-suggests acceleration variations for natural movement
- Auto-calculates realistic durations
- Normalizes base position with subtle lateral movement
- Can disable any auto-feature if needed
- Direct installation to animation plugins directory

### 3. animation_to_json.py - Python to JSON Conversion
**Purpose**: Extract animations from Python code for editing

**Key Features**:
- Extracts commented-out animation classes
- Handles `base_pos` variable expressions
- Preserves keyframe names and metadata
- Batch converts all commented animations
- Enables editing of existing production animations

## Complete Workflows

### Workflow 1: Create New Animation from Scratch

**Use Case**: You want to create a completely new animation

```bash
# Step 1: Record the animation
cd /home/pi/luxopi-ros/dev
python3 animation_recorder.py

# In the recorder:
# - Robot goes into DEMA (fully limp)
# - Move robot to position, press 'R' to record keyframe
# - Repeat for all keyframes
# - Press 'F' when finished
# - Name your animation (e.g., "waving")
# - Save to JSON

# Step 2: Preview and refine (optional but recommended)
python3 animation_recorder.py --preview animations/json/animation_waving_*.json

# In preview:
# [S] Step through from keyframe 1
# [N] Next, [P] Previous to navigate
# [E] Edit any keyframe that needs adjustment
# [V] Save edited version (new timestamp)

# Step 3: Convert to Python plugin
python3 json_to_animation.py animations/json/animation_waving_*.json --install

# Step 4: Register in animation system
# Edit: src/luxo_behaviors/luxo_behaviors/animation_plugins/custom_animations.py
# Add:
#   from .animation_waving import WavingAnimation
#   # In get_plugins():
#   WavingAnimation(),

# Step 5: Build and deploy
cd /home/pi/luxopi-ros
colcon build --packages-select luxo_behaviors
source install/setup.bash

# Step 6: Test
ros2 action send_goal /play_animation luxo_interfaces/action/PlayAnimation \
    "{animation_name: 'waving'}"
```

### Workflow 2: Edit Existing Production Animation

**Use Case**: An animation exists in production but needs refinement

```bash
# Step 1: Convert Python animation to JSON for editing
cd /home/pi/luxopi-ros/dev
python3 animation_to_json.py StretchingAnimation

# Output: animations/json/animation_stretch_TIMESTAMP.json

# Step 2: Interactive editing
python3 animation_recorder.py --preview animations/json/animation_stretch_*.json

# In preview:
# [P] Play full animation (see what needs work)
# [S] Step through starting at problematic keyframe
# [E] Edit keyframes that need adjustment
# [N]/[P] Navigate to verify transitions
# [V] Save edited version

# Step 3: Convert back to Python
python3 json_to_animation.py animations/json/animation_stretch_NEWTIME.json \
    --install

# This will overwrite the old animation_stretch.py with improved version

# Step 4: Rebuild and test
cd /home/pi/luxopi-ros
colcon build --packages-select luxo_behaviors
source install/setup.bash
```

### Workflow 3: Convert All Commented Animations

**Use Case**: Bring commented-out animations back to life

```bash
# Step 1: Extract all commented animations to JSON
cd /home/pi/luxopi-ros/dev
python3 animation_to_json.py --all-commented

# Output shows which animations were converted:
# ✓ stretch (20 keyframes)
# ✓ dance (16 keyframes)
# ✓ excited (18 keyframes)
# ✓ sad (15 keyframes)
# ✓ playful (18 keyframes)

# Step 2: Preview and refine each one
python3 animation_recorder.py --preview animations/json/animation_stretch_*.json
# Edit as needed, save

python3 animation_recorder.py --preview animations/json/animation_dance_*.json
# Edit as needed, save

# ... repeat for all

# Step 3: Batch convert back to Python
for file in animations/json/animation_stretch_*.json \
            animations/json/animation_dance_*.json \
            animations/json/animation_excited_*.json \
            animations/json/animation_sad_*.json \
            animations/json/animation_playful_*.json; do
    python3 json_to_animation.py "$file" --install
done

# Step 4: Register all in custom_animations.py and rebuild
```

### Workflow 4: Fine-Tune Transition Between Two Keyframes

**Use Case**: The transition between keyframes 5 and 6 looks jerky

```bash
# Step 1: Preview with step-through
python3 animation_recorder.py --preview animations/json/animation_NAME.json

# Step 2: In preview menu
[S] Step through from keyframe 5

# Step 3: Navigate to problem area
# At keyframe 5:
[N] Next → moves to keyframe 6
# Watch the transition - looks jerky!

# Step 4: Edit one or both keyframes
[P] Previous → back to keyframe 5
[E] Edit → adjust position slightly
[N] Next → see new transition
[E] Edit keyframe 6 if needed
[P] Previous → verify backward transition
[N] Next → verify forward transition

# Step 5: Test full animation
[M] Main menu
[P] Play full animation → see it in context

# Step 6: Save if satisfied
[V] Save edited animation
```

### Workflow 5: Adjust Animation Timing/Speed

**Use Case**: Animation moves too fast or too slow

```bash
# Option A: Let system recalculate durations
python3 animation_recorder.py --preview animations/json/animation_NAME.json
[P] Play full animation with duration calibration
# System measures actual durations and offers to update
[y] Accept calibrated durations
[V] Save

# Option B: Manual duration editing
# Edit the JSON file directly:
nano animations/json/animation_NAME.json
# Find "duration" fields and adjust values
# Then preview to verify

# Option C: Speed multiplier on playback (ROS2 only)
ros2 action send_goal /play_animation luxo_interfaces/action/PlayAnimation \
    "{animation_name: 'NAME', speed_multiplier: 1.5}"  # 1.5x faster
```

## Tool Usage Reference

### animation_recorder.py

#### Recording Mode (Default)
```bash
python3 animation_recorder.py
```

**Recording Controls**:
- **R** - Record current position as keyframe
- **F** - Finish recording
- **Q** - Quit (prompts to save)

**Post-Recording Menu**:
- **[P]** - Preview/Replay animation
- **[E]** - Edit animation (delete, timing, reorder)
- **[N]** - Name/rename animation
- **[S]** - Save animation to JSON
- **[D]** - Discard and start over
- **[Q]** - Quit

#### Preview Mode
```bash
python3 animation_recorder.py --preview PATH_TO_JSON
```

**Main Menu**:
- **[P]** - Play full animation (with duration calibration)
- **[S]** - Step through from specific keyframe
- **[E]** - Edit a specific keyframe
- **[L]** - List all keyframes
- **[V]** - Save edited animation (new timestamp)
- **[Q]** - Quit

**Step-Through Controls**:
- **[N]** - Next keyframe
- **[P]** - Previous keyframe
- **[E]** - Edit current keyframe
- **[J]** - Jump to specific keyframe number
- **[M]** - Back to main menu

### json_to_animation.py

#### Basic Conversion
```bash
# Convert and preview
python3 json_to_animation.py animations/json/animation_NAME.json

# Convert and save to file
python3 json_to_animation.py animations/json/animation_NAME.json -o output.py

# Convert and install directly
python3 json_to_animation.py animations/json/animation_NAME.json --install
```

#### Advanced Options
```bash
# Disable auto-features
python3 json_to_animation.py animation.json \
    --no-auto-hand \        # Don't auto-suggest hand variations
    --no-auto-acc \         # Don't auto-suggest acceleration
    --no-auto-durations     # Use durations from JSON

# Custom output location
python3 json_to_animation.py animation.json --output /custom/path/

# Custom class name
python3 json_to_animation.py animation.json --class-name MyCustomName
```

#### Auto-Variation Features

**Hand/Antenna (Eyebrows) - Range: 0.5 to 2.6 radians**:
- **Low (0.5-1.0)**: Droopy, sad, relaxed
- **Mid (1.0-1.8)**: Neutral, normal
- **High (1.8-2.6)**: Alert, excited, surprised
- Based on shoulder position and sequence patterns

**Acceleration - Range: 10.0 to 22.5**:
- **Low (10.0-12.0)**: Smooth, gentle, flowing movements
- **Mid (12.0-16.0)**: Normal, natural speed
- **High (16.0-22.5)**: Snappy, quick, energetic movements
- Based on angular distance between keyframes

**Duration Calculation**:
```python
duration = max(0.3, angular_distance / 2.0)  # 2.0 rad/s base speed
```

### animation_to_json.py

#### Convert Specific Animation
```bash
# Search all files for animation class
python3 animation_to_json.py StretchingAnimation

# Convert from specific file
python3 animation_to_json.py --file action_animations.py DancingAnimation

# Custom output directory
python3 animation_to_json.py StretchingAnimation --output /custom/path/
```

#### Batch Convert All Commented Animations
```bash
python3 animation_to_json.py --all-commented

# Output:
# Found 5 commented animation(s):
#   - ExcitedHopAnimation in emotion_animations.py
#   - SadDroopAnimation in emotion_animations.py
#   - PlayfulBounceAnimation in emotion_animations.py
#   - StretchingAnimation in action_animations.py
#   - DancingAnimation in action_animations.py
#
# Converting each...
# ✓ Converted 5/5 animations
```

## File Organization

```
/home/pi/luxopi-ros/dev/
├── animation_recorder.py              # Record & edit tool
├── animation_to_json.py              # Python → JSON converter
├── json_to_animation.py              # JSON → Python converter
├── animations/
│   └── json/                         # All JSON animations
│       ├── animation_waving_20251020_143022.json
│       ├── animation_stretch_20251020_213612.json
│       └── ...
└── ANIMATION_TOOLCHAIN.md           # This file

/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/
├── animation_plugins/
│   ├── action_animations.py         # Production action animations
│   ├── emotion_animations.py        # Production emotion animations
│   ├── idle_animations.py           # Production idle animations
│   ├── custom_animations.py         # Custom animation registry
│   ├── animation_waving.py          # Installed custom animation
│   └── ...
└── animation_command.py             # Animation playback engine
```

## JSON Format Reference

### Complete Structure
```json
{
  "name": "animation_name",
  "description": "Human-readable description",
  "category": "action|emotion|idle|custom",
  "created": "2025-10-20T21:36:12.859269",
  "keyframes": [
    {
      "servos": {
        "base": 0.0,          // Base rotation (radians)
        "shoulder": 0.2,      // Shoulder joint (radians)
        "elbow": 1.4,         // Elbow joint (radians)
        "wrist": 0.8,         // Wrist joint (radians)
        "hand": 1.5,          // Hand/antenna (radians)
        "roll": -1.5,         // Roll joint (radians)
        "spd": 0,             // Speed parameter
        "acc": 13.0           // Acceleration (10.0-22.5)
      },
      "timing": 1.0,          // Timing multiplier
      "duration": 0.7,        // Time to reach this keyframe (seconds)
      "name": "Keyframe 1"    // Optional keyframe name
    }
  ],
  "keyframe_count": 20
}
```

### Joint Ranges
- **base**: -90° to 90° (-1.57 to 1.57 rad)
- **shoulder**: 0° to 180° (0 to 3.14 rad)
- **elbow**: 0° to 180° (0 to 3.14 rad)
- **wrist**: 0° to 180° (0 to 3.14 rad)
- **hand**: 0.5 to 2.6 rad (eyebrow/antenna expression)
- **roll**: -2.5 to -0.5 rad (typically -1.5)
- **acc**: 10.0 to 22.5 (movement feel)

## Python Plugin Format Reference

### Template Structure
```python
#!/usr/bin/env python3
from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin

class MyAnimation(AnimationPlugin):
    """Animation description"""

    @property
    def name(self) -> str:
        return "my_animation"

    @property
    def description(self) -> str:
        return "Description of what this animation does"

    def get_category(self) -> str:
        return "action"  # or "emotion", "idle", "custom"

    def get_keyframe_names(self) -> Optional[List[str]]:
        """Optional descriptive names for each keyframe"""
        return [
            "Starting position",
            "Wind up",
            "Main action",
            "Follow through",
            "Return home"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        """
        Return keyframes and durations.

        Keyframe format: [base, shoulder, elbow, wrist, roll, acceleration, hand]
        """
        base_pos = 0.0  # Normalized base position

        keyframes = [
            # [base, shoulder, elbow, wrist, roll, acc, hand]
            [base_pos +0.05, -0.20, 0.80, 0.90, -1.5, 16.0, 1.50],
            [base_pos -0.03, -0.10, 0.50, 0.30, -1.5, 19.0, 1.80],
            [base_pos +0.02, -0.60, 0.80, 0.80, -1.5, 17.0, 2.10],
            # ... more keyframes
        ]

        durations = [0.4, 0.6, 0.5]  # Time to reach each keyframe

        return keyframes, durations
```

## Best Practices

### Recording New Animations

1. **Plan First**: Sketch or visualize key poses before recording
2. **Start Simple**: Record major keyframes first, add detail later
3. **Use References**: Look at Disney animation principles (anticipation, follow-through, etc.)
4. **Support the Robot**: DEMA makes it limp - be ready to support it
5. **Record Deliberately**: Move slowly between positions for better accuracy
6. **Preview Often**: Use [P] to see how it plays back
7. **Name Descriptively**: Use clear names like "curious_peek" not "anim1"

### Editing Existing Animations

1. **Preview First**: Always play full animation before editing
2. **Step Through Problem Areas**: Use [S] to focus on specific transitions
3. **Edit One at a Time**: Don't change multiple keyframes before testing
4. **Test Transitions**: Use [N] and [P] to verify changes work in both directions
5. **Save Incrementally**: Use [V] to save versions as you improve (timestamps preserve history)
6. **Keep Originals**: JSON files with timestamps let you revert if needed

### Animation Design

1. **Anticipation**: Add 1-2 keyframes of opposite movement before main action
2. **Follow-Through**: Add 1-2 keyframes of settling/overshooting after main action
3. **Arcs**: Natural movements follow curved paths, not straight lines
4. **Timing**: Vary durations - fast for snappy, slow for smooth
5. **Expression**: Change hand/antenna position to show emotion
6. **Acceleration**: Match to mood (low=gentle, high=energetic)

### Production Deployment

1. **Test in Preview**: Thoroughly test before converting to Python
2. **Duration Calibration**: Use [P] Play Full Animation to measure actual times
3. **Verify Joint Limits**: Ensure no positions are impossible to reach
4. **Add Keyframe Names**: Makes debugging easier later
5. **Document Purpose**: Add clear description of what animation is for
6. **Test in ROS**: Always test with `ros2 action send_goal` before production use

## Troubleshooting

### Recording Issues

**Robot shoots up violently when starting**:
- This is normal - DEMA enables and robot goes limp
- Support the robot before starting recording mode
- Wait for "robot is limp" message before letting go

**Position not recording accurately**:
- Make sure DEMA is fully enabled (robot is limp)
- Wait for robot to settle before pressing 'R'
- Check serial connection is getting position feedback

**Robot doesn't move during preview**:
- DEMA may still be enabled - check output messages
- Verify serial connection is active
- Check tolerance settings (default ±12° should work)

### Editing Issues

**Keyframe reverts to old position**:
- ✅ Fixed in latest version - robot stays at edited position
- If still occurring, make sure you're using updated animation_recorder.py

**Robot moves when I just edited**:
- This is intentional when navigating to new keyframe
- After editing, robot should show "✓ Already at keyframe X (just edited)"

**Save fails with datetime error**:
- ✅ Fixed in latest version - using correct datetime import
- If still occurring, verify `from datetime import datetime` at top of file

### Conversion Issues

**Animation not found in Python files**:
- Check spelling of class name exactly
- Verify it's commented out with `# class AnimationName`
- Use `--file` to specify exact file if needed

**Base position not normalizing correctly**:
- Manually check base values in JSON
- If variation >0.3 rad, script won't use base_pos variable
- This is intentional for animations with large base movement

**Hand/acceleration suggestions seem wrong**:
- Use `--no-auto-hand` or `--no-auto-acc` to disable
- Edit JSON file manually for precise control
- Auto-suggestions are guidelines, not requirements

### Playback Issues

**Animation looks jerky**:
- Increase durations in JSON
- Reduce acceleration values (10-12 range)
- Add intermediate keyframes for smoother transitions
- Use duration calibration ([P] Play Full)

**Animation too slow**:
- Decrease durations in JSON
- Increase acceleration values (16-22 range)
- Use speed multiplier in ROS: `speed_multiplier: 1.5`

**Robot doesn't reach position**:
- Check tolerance (default ±12° should work)
- Hand joint is now excluded from tolerance checking
- Verify target position is physically reachable
- Reduce movement distance between keyframes

## Advanced Topics

### Custom Duration Calculation

Edit `json_to_animation.py` to change base speed:

```python
def calculate_duration(kf1: Dict, kf2: Dict, base_speed: float = 2.0):
    # Change base_speed (default 2.0 rad/s) to adjust global timing
    # Higher = faster animations, Lower = slower animations
```

### Batch Processing

Create script to process multiple animations:

```bash
#!/bin/bash
# refine_all_animations.sh

for json in animations/json/animation_*.json; do
    echo "Processing $json..."
    python3 json_to_animation.py "$json" --install
done

cd /home/pi/luxopi-ros
colcon build --packages-select luxo_behaviors
```

### Custom Expression Patterns

Edit JSON to create complex expression sequences:

```json
{
  "keyframes": [
    {"servos": {"hand": 0.5, ...}},  // Sad
    {"servos": {"hand": 1.5, ...}},  // Neutral
    {"servos": {"hand": 2.6, ...}},  // Excited!
    {"servos": {"hand": 1.8, ...}},  // Settling
  ]
}
```

### Animation Blending (Future)

While not currently supported, you can manually blend animations:

1. Export both animations to JSON
2. Manually merge keyframes in JSON
3. Preview and refine transitions
4. Convert back to Python

## Tips and Tricks

### Quick Iteration
```bash
# Keep three terminals open:
# Terminal 1: Preview/edit
python3 animation_recorder.py --preview animations/json/animation_NAME.json

# Terminal 2: Convert
python3 json_to_animation.py animations/json/animation_NAME_*.json --install

# Terminal 3: Build and test
cd /home/pi/luxopi-ros && colcon build --packages-select luxo_behaviors && \
ros2 action send_goal /play_animation luxo_interfaces/action/PlayAnimation \
    "{animation_name: 'NAME'}"
```

### Version Control
```bash
# JSON files include timestamps - keep multiple versions
animations/json/
├── animation_waving_20251020_140000.json  # Original
├── animation_waving_20251020_143000.json  # First edit
└── animation_waving_20251020_145000.json  # Final version
```

### Finding Good Keyframe Counts
- **Simple gestures**: 5-8 keyframes
- **Complex movements**: 12-20 keyframes
- **Idle animations**: 6-10 keyframes (should loop)
- **Emotional expressions**: 15-25 keyframes (with build-up and release)

### Debugging Specific Transitions
```bash
# Use step-through to isolate problem
python3 animation_recorder.py --preview animation.json
[S] Step through from keyframe 5
[N] → keyframe 6  # Watch transition
[P] ← keyframe 5  # Watch reverse
[E] Edit keyframe 6 if needed
[N] Test again
```

## Summary

This toolchain provides everything needed for professional animation development:

✅ **Create** - Record animations manually with full DEMA support
✅ **Preview** - Interactive step-through playback with live editing
✅ **Refine** - Edit individual keyframes inline during playback
✅ **Convert** - Bidirectional JSON ↔ Python transformation
✅ **Enhance** - Auto-suggest hand, acceleration, and duration values
✅ **Deploy** - One-command installation to ROS2 system
✅ **Iterate** - Fast edit-preview-save workflow

The combination of these tools enables rapid iteration and high-quality animation development for the LuxoPi robot.
