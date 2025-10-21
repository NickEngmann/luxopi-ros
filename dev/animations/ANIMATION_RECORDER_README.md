# Animation Recorder Tool

Interactive tool for creating RoArm-M3 animations by manually positioning the robot and recording keyframes.

## Overview

This tool enables full DEMA (Dynamic External Motion Adaptation) mode on the robot, making it completely limp so you can physically move it to desired positions. As you move the arm, you can press 'R' to record keyframes at each position.

## Usage

### Basic Usage

```bash
# Make sure the robot is connected to /dev/ttyAMA0
cd /home/pi/luxopi-ros/dev
python3 animation_recorder.py
```

### With Custom Serial Port

```bash
python3 animation_recorder.py --port /dev/ttyUSB0
```

## Workflow

### 1. **Initialization** (10 seconds)
   - Tool connects to robot
   - Waits 10 seconds for initialization
   - Enables full DEMA mode (robot becomes limp)

### 2. **Recording Mode**
   - Move the robot to your desired position
   - Press **'R'** to record the current position as a keyframe
   - Repeat for as many keyframes as needed
   - Press **'F'** when finished recording
   - Press **'Q'** to quit without saving (will prompt for confirmation)

### 3. **Post-Recording Menu**
   After finishing, you can:
   - **[P]** Preview/Replay - Plays back the animation (disables DEMA temporarily)
   - **[E]** Edit - Delete keyframes, adjust timing/duration, reorder
   - **[N]** Name - Set or change the animation name
   - **[S]** Save - Export to JSON file
   - **[D]** Discard - Start over with new recording
   - **[Q]** Quit

### 4. **Editing Options**
   - **Delete keyframe** - Remove unwanted keyframes
   - **Timing** - Adjust duration (seconds) and timing multiplier for each keyframe
   - **Reorder** - Change the sequence of keyframes

## Output Format

Animations are saved as JSON files with this structure:

```json
{
  "name": "my_animation",
  "description": "Animation created with recorder on 2025-01-15 10:30",
  "category": "custom",
  "created": "2025-01-15T10:30:45",
  "keyframes": [
    {
      "servos": {
        "j1": 0.0,
        "j2": 45.0,
        "j3": 90.0,
        "j4": 180.0,
        "j5": 0.0,
        "j6": 90
      },
      "timing": 1.0,
      "duration": 1.0
    }
  ],
  "keyframe_count": 5
}
```

## Joint Mapping

The robot has 5 controllable joints:
- **j1 (base)**: Base rotation (-90° to 90°)
- **j2 (shoulder)**: Shoulder joint (0° to 180°)
- **j3 (elbow)**: Elbow joint (0° to 180°)
- **j4 (wrist)**: Wrist joint (0° to 180°)
- **j5 (hand)**: Hand rotation (-90° to 90°)
- **j6 (LED)**: LED brightness (60-120, default: 90)

## Tips for Creating Great Animations

1. **Plan Your Animation**
   - Sketch out key poses before recording
   - Think about the emotion or action you want to convey

2. **Follow Disney Principles**
   - Add anticipation (small opposite movement before main action)
   - Include follow-through (overshoot and settle back)
   - Use arcs instead of straight-line movements
   - Vary timing for more natural motion

3. **Keyframe Spacing**
   - Use more keyframes for complex movements
   - Use fewer keyframes for simple, smooth motions
   - Default duration is 2 seconds between keyframes during replay

4. **Test and Iterate**
   - Preview frequently to see how it looks
   - Adjust timing to speed up or slow down specific movements
   - Don't be afraid to delete and re-record keyframes

5. **Safety**
   - Keep the robot away from obstacles during DEMA mode
   - The robot will be completely limp - support it if needed
   - Avoid extreme joint positions

## Next Steps: Converting to Animation Plugin

**TODO**: Create a conversion script to transform JSON files into Python animation plugins.

The JSON format needs to be converted to:
```python
class MyCustomAnimation(AnimationPlugin):
    @property
    def name(self) -> str:
        return "my_animation"

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        keyframes = [
            [j1, j2, j3, j4, j5, j6, timing],
            # ... more keyframes
        ]
        durations = [1.0, 1.0, ...]
        return keyframes, durations
```

This conversion script will:
1. Read the JSON file
2. Generate a Python class following the AnimationPlugin interface
3. Save to the appropriate plugin directory
4. Optionally add to the animation registry

## Troubleshooting

### Robot Not Responding
- Check serial connection: `ls -l /dev/ttyAMA0`
- Verify permissions: `sudo usermod -a -G dialout $USER` (logout required)
- Check if port is in use: `lsof /dev/ttyAMA0`

### Robot Stays Stiff
- DEMA mode may not have activated
- Wait a few seconds after seeing "DEMA enabled" message
- Try unplugging and replugging robot power

### Position Not Updating
- Serial feedback (T:1051) may not be working
- Check that robot firmware supports position feedback
- Look for position updates in the console output

### Recording Doesn't Start
- Terminal must support raw input mode
- Try running in a different terminal (not over SSH without TTY)

## File Locations

- **Tool**: `/home/pi/luxopi-ros/dev/animation_recorder.py`
- **Saved animations**: Current directory (where you run the tool)
- **Animation plugins**: `/home/pi/luxopi-ros/src/luxo_behaviors/luxo_behaviors/animation_plugins/`

## Safety Notes

⚠️ **Important Safety Warnings**:
- Robot will be completely limp in DEMA mode
- Ensure adequate workspace clearance
- Don't force joints beyond their limits
- Be prepared to catch the robot if it falls
- Keep fingers clear of joints during playback
- DEMA is disabled during replay - robot will have full torque

## Examples

### Example Session

```
$ python3 animation_recorder.py

==============================================================
LuxoPi Animation Recorder
==============================================================
Connecting to /dev/ttyAMA0 at 115200 baud...
✓ Connected successfully
✓ Serial read thread started

Waiting for robot to initialize (10 seconds)...
  Ready!

Enabling full DEMA mode (robot will be limp)...
✓ Full DEMA enabled - you can now move the robot freely

==============================================================
ANIMATION RECORDING MODE
==============================================================

The robot is now in DEMA mode - you can freely move it.

Controls:
  [R] - Record current position as keyframe
  [F] - Finish recording
  [Q] - Quit without saving

Move the robot to your desired position and press 'R' to record.
==============================================================

[User moves robot and presses R]

✓ Keyframe 1 recorded:
  Base: 15.30°
  Shoulder: 45.20°
  Elbow: 90.50°
  Wrist: 120.00°
  Hand: -10.25°

[User continues recording...]
```

## Advanced Usage

### Batch Animation Creation

You can create multiple animations in one session by selecting "Discard and start over" from the post-recording menu.

### Custom Timing

Each keyframe can have:
- **Duration**: How long to hold/transition to this position (seconds)
- **Timing multiplier**: Speed adjustment for this specific keyframe (1.0 = normal)

### Integration with LuxoPi System

Once converted to a Python plugin, animations can be:
- Triggered by voice commands
- Used as idle behaviors
- Mapped to emotional responses
- Called via ROS actions

## License

Part of the LuxoPi project. See main project LICENSE file.
