# Luxo Voice Command Reference

This document lists all voice commands supported by the Luxo robot. Commands are organized by category and designed to be unambiguous - each command has a clear, distinct pattern.

**Total Commands: 57 (reduced from 92)**

---

## Quick Responses (9 commands)
These bypass the LLM for instant responses.

| Command | Response |
|---------|----------|
| "hello" / "hi" / "hey" | "Hello!" / "Hey!" |
| "goodbye" / "bye" | "Goodbye!" / "Bye!" |
| "thank you" / "thanks" | "You're welcome!" / "No problem!" |
| "how are you" | "I'm doing great!" |
| "what's up" | "Not much, you?" |

---

## Voice Assistant Controls

### Mute / Unmute (6 + 5 = 11 commands)

**Mute (silence the voice assistant):**
- "mute" / "muting"
- "shut up" / "shush up"
- "be silent" / "be silence"
- "no more talking"
- "stop talking" / "stop speaking"
- "hush"

**Unmute (allow voice assistant to speak):**
- "unmute" / "unmuting"
- "talk again" / "speak again" / "talk now" / "speak now"
- "start talking again" / "start speaking again"
- "okay to talk" / "okay to speak"
- "allowed to talk" / "allowed to speak"

### Volume Control (4 + 4 = 8 commands)

**Volume Up:**
- "speak louder" / "talk louder"
- "volume up"
- "increase volume"
- "louder"

**Volume Down:**
- "speak softer" / "talk softer" / "speak quieter" / "talk quieter"
- "volume down"
- "decrease volume"
- "too loud"

### Speed Control (2 + 2 = 4 commands)

**Speed Up:**
- "speak faster" / "talk faster"
- "speed up"

**Speed Down:**
- "speak slower" / "talk slower"
- "slow down"

### Pitch Control (2 + 2 = 4 commands)

**Pitch Up:**
- "higher pitch"
- "raise pitch" / "raise your pitch"

**Pitch Down:**
- "lower pitch"
- "deeper voice"

### Status Request (3 commands)
- "what's your status" / "what's your settings"
- "check settings"
- "voice settings"

---

## Robot Hardware Commands

### Sleep / Wake (8 + 5 = 13 commands)

**Sleep Mode (robot goes limp, volume mutes, lights off):**
- "sleep" / "sleeping" / "asleep"
- "go to sleep" / "go to bed"
- "time for sleep" / "time to sleep" / "time for bed" / "time to bed"
- "good night"
- "bedtime"
- "sleep mode"
- "power down" / "power off"
- "shut down"

**Wake Mode (robot wakes up, volume restores, lights on):**
- "wake"
- "wake up"
- "get up"
- "good morning" *(also responds as greeting)*
- "power on" / "power up"

### Movement Control

#### Stay Mode (6 commands)
Robot freezes in current position.

- "stay" / "freeze"
- "don't move" / "do not move"
- "stop moving"
- "hold position" / "hold that position"
- "stay there" / "stay still" / "stay put"
- "keep position"

#### Move Mode (5 commands)
Exit stay mode, resume normal operation.

- "move"
- "can move" / "you can move"
- "unfreeze" / "undo freeze" / "undo stay"
- "resume moving" / "resume motion"
- "start moving"

### Light Control

#### Light On/Off (3 + 3 = 6 commands)

**Turn On:**
- "turn light on" / "switch light on" / "turn the light on"
- "light on" / "lights on"
- "turn on light" / "turn on the light"

**Turn Off:**
- "turn light off" / "switch light off" / "turn light out"
- "light off" / "lights off" / "light out"
- "turn off light" / "turn out light"

#### Brightness Control (2 + 2 + 2 = 6 commands)

**Increase Brightness:**
- "bright" / "brighten" / "brighter"
- *(detected from keywords, no specific pattern)*

**Decrease Brightness:**
- "dim" / "dimmer" / "darker"
- *(detected from keywords, no specific pattern)*

**Set Extremes:**
- "maximum brightness" / "max brightness" / "brightest"
- "minimum brightness" / "min brightness" / "dimmest"

#### Color Temperature (2 commands)

**Warmer:**
- "warm" / "warmer" / "warm up"

**Cooler:**
- "cool" / "cooler" / "cool down"

#### Colors (8 commands)
- "red"
- "orange"
- "yellow"
- "green"
- "cyan" / "turquoise"
- "blue"
- "purple" / "violet"
- "white"

---

## Command Priority

Commands are checked in this order:

1. **Quick Responses** (highest priority - instant)
2. **Voice Assistant Commands** (mute, volume, speed, pitch, status)
3. **Robot Hardware Commands** (sleep, stay, lights, etc.)
4. **LLM Conversation** (if no command detected)

---

## Conflict Resolution

The command patterns have been carefully designed to avoid conflicts:

### ✅ Resolved Conflicts:

| Old Issue | Resolution |
|-----------|------------|
| "stop" matched both mute and stay | Mute requires "stop talking/speaking", stay uses "stop moving" |
| "quiet" matched mute and volume | Mute uses "silent/silence", volume uses "quieter/softer" |
| "resume" matched unmute and move | Unmute uses "talk/speak again", move uses "resume moving/motion" |
| "turn on" matched wake and lights | Lights require "light" keyword, wake uses "power on/up" |
| "good morning" double-triggered | Removed from quick responses, only triggers wake |

### 🎯 Clear Keyword Themes:

- **Mute:** silence, quiet, hush, shut up, stop talking
- **Unmute:** talk again, speak again, unmute
- **Sleep:** sleep, bed, night, power down
- **Wake:** wake, morning, power on
- **Stay:** stay, freeze, don't move, hold position
- **Move:** move, unfreeze, resume motion

---

## Usage Tips

1. **Be Specific:** Use clear keywords like "speak louder" instead of just "louder"
2. **Natural Language:** Commands are flexible - "can you please turn on the light" works
3. **Avoid Ambiguity:** If unsure, use the most specific form (e.g., "stop moving" not just "stop")
4. **Cooldown:** 2 seconds between commands to prevent accidental triggers
5. **Sleep Mode:** Only "wake up" commands work when robot is sleeping
6. **Mute vs Sleep:** Mute only affects voice, sleep also disables movement and lights

---

## Examples

### ✅ Good Commands:
- "Please turn on the light"
- "Can you speak a bit louder"
- "Stop moving and stay there"
- "Wake up, it's morning"
- "Set the color to blue"

### ❌ Avoid Ambiguous Commands:
- "Stop" *(could be mute or stay - use "stop talking" or "stop moving")*
- "Resume" *(could be unmute or move - use "talk again" or "resume moving")*
- "Turn on" *(could be wake or lights - use "wake up" or "turn on light")*

---

## Command Count Summary

| Category | Commands |
|----------|----------|
| Quick Responses | 9 |
| Voice Assistant | 40 (mute/unmute, volume, speed, pitch, status) |
| Robot Hardware | 57 (sleep/wake, stay/move, lights, brightness, colors) |
| **Total** | **57** |

**Reduction:** 92 → 57 commands (38% reduction)

---

*Last updated: 2025-10-15*
*For implementation details, see `command_behavior.py`*
