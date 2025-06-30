# LuxoPi Animation Constraints and Guidelines

## Joint Limits and Safety Constraints

### Shoulder (Joint 2) - Index 1
- **Hard limits**: -1.1 to 0.4
- **Preferred range**: -1.1 to -0.1 (tends to lean back/away from user)
- **Maximum forward**: 0.3 (use sparingly for special effects)
- **Neutral position**: Around -0.55 to -0.65

### Hand/Wrist Roll (Joint 5) - Index 4
- **Hard limits**: -2.25 to -0.75
- **Neutral position**: -1.5
- **Safe operating range**: -2.2 to -0.8

### Acceleration (Index 5)
- **Minimum**: 7 (very slow, deliberate movements)
- **Maximum**: 22.5 (fastest possible)
- **Typical ranges**:
  - Slow/deliberate: 8-12
  - Normal: 13-17
  - Fast: 18-22

## Duration Guidelines

### Minimum Duration
- **Absolute minimum**: 0.35 seconds
- Only use 0.35s when acceleration is 18+ AND movement distance is small

### Duration/Acceleration/Distance Relationships

#### High Acceleration (18-22.5)
- Small movements (< 0.3 total joint change): 0.35-0.45s
- Medium movements (0.3-0.8 total change): 0.4-0.6s
- Large movements (> 0.8 total change): 0.5-0.65s

#### Medium Acceleration (14-17)
- Small movements: 0.45-0.6s
- Medium movements: 0.55-0.7s
- Large movements: 0.6-0.85s

#### Low Acceleration (10-13)
- Small movements: 0.55-0.7s
- Medium movements: 0.7-0.85s
- Large movements: 0.8-1.2s

#### Very Low Acceleration (8-9)
- Use for slow, deliberate movements: 0.95-1.8s
- Good for stretches, sad movements, or holds

## Return Home Positions

### Return Home 1
- Position: `[base_pos, 0.2, 1.3, 1.5, -1.5, 15.0]`
- Used as intermediate position before home 2

### Return Home 2 (Final Home)
- Position: `[base_pos, -0.65, 1.2, 1.0, -1.5, 10.0]`
- Always end animations here

## Animation Design Principles

### Shoulder Position Preference
- **General mood**: Keep shoulder below -0.1 (leaning back/away)
- Forward movements (> -0.1) should be intentional and brief
- Use forward lean sparingly for:
  - Curious inspection
  - Deep thought/pondering
  - Specific expressive moments

### Special Position Rules

#### Full Slouch (Sad)
- Maximum slouch: `[base, 0.3, 2.5, 0, hand, acceleration]`
- Always approach from home 1-like position
- When recovering: Move shoulder back first (lean back before extending)

#### Full Stretch (Peak Vertical)
- Maximum stretch: `[base, 0, 0, 0, -1.45, 8]` (straight up)
- Use slow acceleration for dramatic effect

#### Maximum Compact
- Most compact: `[0, -1.5, 2.0, 1.0, -1.45, acceleration]`
- Good for spring-loading before jumps

### Movement Flow
1. Consider current position before large movements
2. Use shoulder-first movement when recovering from extreme positions
3. Balance left/right base movements within an animation
4. Return to neutral hand position (-1.5) regularly

## Disney Animation Principles Applied

### Anticipation
- Small opposite movement before main action
- Compress before jumping
- Pull back before forward motion

### Follow-through
- Don't stop abruptly at target position
- Add small overshoot and settle
- Use varying accelerations for natural movement

### Exaggeration
- Make movements clear and readable
- Use full range when appropriate
- But respect safety constraints

## Common Animation Patterns

### Nodding
- Use wrist oscillation: 0 to 1.35
- Keep at home 2 position
- Fast timing: 0.35-0.45s per nod

### Swaying/Breathing
- Subtle base movement: ±0.5 max
- Coordinate with shoulder/elbow
- Slower timing: 0.6-0.95s per sway

### Jumping/Bouncing
- Compress first (high positive shoulder)
- Launch with negative shoulder
- Land with compression
- Timing: 0.5-0.65s for large jumps

### Idle Movements
- Small variations around home 2
- Shoulder: -0.7 to -0.6
- Elbow: 1.1 to 1.3
- Wrist: 0.9 to 1.1

## Safety Notes
- Never exceed joint limits even for brief moments
- Consider momentum when planning fast movements
- Test new animations at lower speeds first
- Always include proper return home sequence