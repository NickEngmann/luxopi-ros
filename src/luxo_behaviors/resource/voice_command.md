# DFRobot AI Offline Language Learner API Documentation

## Overview

The DFRobot AI Offline Language Learner provides voice command recognition capabilities with predefined command words and IDs. This documentation outlines all available commands, their corresponding IDs, and categories.

## Command Categories

### 1. Wake-up Words

Wake-up words are used to activate the device and prepare it for receiving commands.

| Command | ID | Description |
|---------|-----|-------------|
| Wake-up words for learning | 1 | Activates learning mode | becomes custom wake word
| Hello robot | 2 | General wake-up phrase |

### 2. Custom Commands

The system supports up to 17 custom commands that can be programmed for specific actions.

| Command Slot | ID | 
|--------------|-----|
| The first custom command | 5 |
| The second custom command | 6 |
| The third custom command | 7 |
| The fourth custom command | 8 |
| The fifth custom command | 9 |
| The sixth custom command | 10 |
| The seventh custom command | 11 |
| The eighth custom command | 12 |
| The ninth custom command | 13 |
| The tenth custom command | 14 |
| The eleventh custom command | 15 |
| The twelfth custom command | 16 |
| The thirteenth custom command | 17 |
| The fourteenth custom command | 18 |
| The fifteenth custom command | 19 |
| The sixteenth custom command | 20 |
| The seventeenth custom command | 21 |

### 3. Movement Commands

Commands for controlling robot movement and navigation.

| Command | ID | Description |
|---------|-----|-------------|
| Go forward | 22 | Move the robot forward |
| Retreat | 23 | Move the robot backward |
| Park a car | 24 | Execute parking sequence |
| Turn left ninety degrees | 25 | Rotate left 90° |
| Turn left forty-five degrees | 26 | Rotate left 45° |
| Turn left thirty degrees | 27 | Rotate left 30° |
| Turn right forty-five degrees | 29 | Rotate right 45° |
| Turn right thirty degrees | 30 | Rotate right 30° |
| Shift down a gear | 31 | Reduce movement speed |

### 4. Operating Modes

Commands for switching between different operational modes.

| Command | ID | Description |
|---------|-----|-------------|
| Line tracking mode | 32 | Follow line patterns |
| Light tracking mode | 33 | Follow light sources |
| Bluetooth mode | 34 | Enable Bluetooth connectivity |
| Obstacle avoidance mode | 35 | Navigate around obstacles |
| Face recognition | 36 | Enable face detection |
| Object tracking | 37 | Track specific objects |
| Object recognition | 38 | Identify objects |
| Line tracking | 39 | Alternative line following |
| Color recognition | 40 | Identify colors |
| Tag recognition | 41 | Detect and read tags |
| Object sorting | 42 | Sort objects by criteria |
| Qr code recognition | 43 | Read QR codes |

### 5. System Settings

General system configuration and control commands.

| Command | ID | Description |
|---------|-----|-------------|
| General settings | 44 | Access settings menu |
| Clear screen | 45 | Clear display output |
| Learn once | 46 | Single learning iteration |
| Forget | 47 | Clear learned data |
| Load model | 48 | Load AI model |
| Save model | 49 | Save current model |
| Take photos and save them | 50 | Capture and store images |
| Save and return | 51 | Save settings and exit |

### 6. Display Commands

#### Numeric Display (IDs 52-61)

| Command | ID |
|---------|-----|
| Display number zero | 52 |
| Display number one | 53 |
| Display number two | 54 |
| Display number three | 55 |
| Display number four | 56 |
| Display number five | 57 |
| Display number six | 58 |
| Display number seven | 59 |
| Display number eight | 60 |
| Display number nine | 61 |

#### Emoji/Pattern Display

| Command | ID | Description |
|---------|-----|-------------|
| Display smiley face | 62 | Show happy emoji |
| Display crying face | 63 | Show sad emoji |
| Display heart | 64 | Show heart symbol |
| Turn off dot matrix | 65 | Disable display |

### 7. Sensor Commands

Commands for reading various sensor data.

| Command | ID | Description |
|---------|-----|-------------|
| Read current posture | 66 | Get orientation data |
| Read ambient light | 67 | Measure light levels |
| Read compass | 68 | Get compass bearing |
| Read temperature | 69 | Measure temperature |
| Read acceleration | 70 | Get accelerometer data |
| Reading sound intensity | 71 | Measure sound levels |
| Calibrate electronic gyroscope | 72 | Calibrate gyro sensor |

### 8. Device Control

#### Camera Control

| Command | ID |
|---------|-----|
| Turn on the camera | 73 |
| Turn off the camera | 74 |

#### Fan Control

| Command | ID | Description |
|---------|-----|-------------|
| Turn on the fan | 75 | Activate fan |
| Turn off the fan | 76 | Deactivate fan |
| Turn fan speed to gear one | 77 | Low speed |
| Turn fan speed to gear two | 78 | Medium speed |
| Turn fan speed to gear three | 79 | High speed |
| Start oscillating | 80 | Enable oscillation |
| Stop oscillating | 81 | Disable oscillation |

#### Servo Control

| Command | ID | Description |
|---------|-----|-------------|
| Reset | 82 | Reset servo position |
| Set servo to ten degrees | 83 | 10° position |
| Set servo to thirty degrees | 84 | 30° position |
| Set servo to forty-five degrees | 85 | 45° position |
| Set servo to sixty degrees | 86 | 60° position |
| Set servo to ninety degrees | 87 | 90° position |

#### Audio Control

| Command | ID | Description |
|---------|-----|-------------|
| Turn on the buzzer | 88 | Enable buzzer |
| Turn off the buzzer | 89 | Disable buzzer |
| Turn on the speaker | 90 | Enable speaker |
| Turn off the speaker | 91 | Disable speaker |
| Play music | 92 | Start playback |
| Stop playing | 93 | Stop playback |
| The last track | 94 | Previous track |
| The next track | 95 | Next track |
| Repeat this track | 96 | Loop current track |
| Volume up | 97 | Increase volume |
| Volume down | 98 | Decrease volume |
| Change volume to maximum | 99 | Set max volume |
| Change volume to minimum | 100 | Set min volume |
| Change volume to medium | 101 | Set medium volume |
| Play poem | 102 | Play poetry content |

### 9. Lighting Control

Commands for controlling connected lighting systems.

| Command | ID | Description |
|---------|-----|-------------|
| Turn on the light | 103 | Enable lighting |
| Turn off the light | 104 | Disable lighting |
| Brighten the light | 105 | Increase brightness |
| Dim the light | 106 | Decrease brightness |
| Adjust brightness to maximum | 107 | Set max brightness |
| Adjust brightness to minimum | 108 | Set min brightness |
| Increase color temperature | 109 | Warmer light |
| Decrease color temperature | 110 | Cooler light |
| Adjust color temperature to maximum | 111 | Warmest setting |
| Adjust color temperature to minimum | 112 | Coolest setting |
| Daylight mode | 113 | Natural daylight |
| Moonlight mode | 114 | Soft night light |
| Color mode | 115 | Enable color changing |

#### Color Settings

| Command | ID |
|---------|-----|
| Set to red | 116 |
| Set to orange | 117 |
| Set to yellow | 118 |
| Set to green | 119 |
| Set to cyan | 120 |
| Set to blue | 121 |
| Set to purple | 122 |
| Set to white | 123 |

### 10. Climate Control

Commands for controlling air conditioning systems.

| Command | ID | Description |
|---------|-----|-------------|
| Turn on ac | 124 | Enable AC |
| Turn off ac | 125 | Disable AC |
| Increase temperature | 126 | Raise temperature |
| Decrease temperature | 127 | Lower temperature |
| Cool mode | 128 | Cooling mode |
| Heat mode | 129 | Heating mode |
| Auto mode | 130 | Automatic mode |
| Dry mode | 131 | Dehumidify mode |
| Fan mode | 132 | Fan only mode |
| Enable blowing up & down | 133 | Vertical air flow |
| Disable blowing up & down | 134 | Stop vertical flow |
| Enable blowing right & left | 135 | Horizontal air flow |
| Disable blowing right & left | 136 | Stop horizontal flow |

### 11. Home Automation

Commands for controlling windows, doors, and curtains.

| Command | ID |
|---------|-----|
| Open the window | 137 |
| Close the window | 138 |
| Open curtain | 139 |
| Close curtain | 140 |
| Open the door | 141 |
| Close the door | 142 |

### 12. Learning System Commands

Special commands for managing the learning functionality.

| Command | ID | Description |
|---------|-----|-------------|
| Learning wake word | 200 | Train new wake word |
| Learning command word | 201 | Train new command |
| Re-learn | 202 | Repeat learning process |
| Exit learning | 203 | Exit learning mode |
| I want to delete | 204 | Enter delete mode |
| Delete wake word | 205 | Remove wake word |
| Delete command word | 206 | Remove command |
| Exit deleting | 207 | Exit delete mode |
| Delete all | 208 | Clear all learned data |

## Usage Notes

1. **Command Recognition**: Commands must be spoken clearly after the device has been activated with a wake-up word.

2. **Custom Commands**: IDs 5-21 are reserved for user-defined custom commands that can be programmed through the learning system.

3. **Learning Mode**: Use commands with IDs 200-208 to manage the learning functionality and train new voice commands.

4. **Response Time**: The device typically responds to commands within 1-2 seconds after recognition.

## Error Handling

If a command is not recognized:
- The device may request repetition
- Ensure proper wake-up word activation
- Check ambient noise levels
- Verify command pronunciation

## Version Information

This documentation covers the DFRobot AI Offline Language Learner firmware version that supports command IDs 1-208.

---