# VL53L4CD Distance Sensor Toggle Guide

This guide explains how to enable/disable the VL53L4CD distance sensors for troubleshooting.

## Quick Start

### Disable Both VL53L4CD Sensors
```bash
# Set environment variables before starting
export LUXOPI_ENABLE_VL53_LEFT=false
export LUXOPI_ENABLE_VL53_RIGHT=false
./start_luxopi.sh
```

### Disable Only Left Sensor
```bash
export LUXOPI_ENABLE_VL53_LEFT=false
./start_luxopi.sh
```

### Disable Only Right Sensor
```bash
export LUXOPI_ENABLE_VL53_RIGHT=false
./start_luxopi.sh
```

## Using ros2 launch Directly

You can also pass these as launch arguments:

```bash
# Source the workspace
cd ~/luxopi-ros
source install/setup.bash

# Disable both sensors
ros2 launch luxo_behaviors luxo_system.launch.py \
    use_hardware:=true \
    enable_vl53_left:=false \
    enable_vl53_right:=false

# Disable only left
ros2 launch luxo_behaviors luxo_system.launch.py \
    use_hardware:=true \
    enable_vl53_left:=false

# Disable only right
ros2 launch luxo_behaviors luxo_system.launch.py \
    use_hardware:=true \
    enable_vl53_right:=false
```

## What Gets Disabled?

When you disable a VL53L4CD sensor:
- The sensor will NOT be initialized on the I2C bus
- No distance readings will be published for that sensor
- Collision detection will only use:
  - MPR121 capacitive touch sensors (if enabled)
  - The other VL53L4CD sensor (if enabled)
  - OAK-D camera depth sensing (if enabled)

## Important Notes

1. **MPR121 Still Works**: Disabling VL53L4CD sensors does NOT affect the MPR121 touch sensors. They will continue to work normally.

2. **Collision Behavior**: The robot will still do collision avoidance, but only using the remaining active sensors.

3. **I2C Bus Load**: Disabling VL53L4CD sensors reduces I2C bus traffic, which may help if you're experiencing I2C communication issues.

4. **Default Behavior**: By default, both sensors are enabled (`true`). You must explicitly set them to `false` to disable.

## Troubleshooting Scenarios

### Scenario 1: Testing if VL53L4CD causes false collision alerts
```bash
# Disable both distance sensors, keep MPR121 active
export LUXOPI_ENABLE_VL53_LEFT=false
export LUXOPI_ENABLE_VL53_RIGHT=false
./start_luxopi.sh
```

### Scenario 2: Testing I2C bus stability
```bash
# Disable distance sensors to reduce I2C traffic
export LUXOPI_ENABLE_VL53_LEFT=false
export LUXOPI_ENABLE_VL53_RIGHT=false
./start_luxopi.sh
```

### Scenario 3: One sensor appears faulty
```bash
# Disable the suspected faulty sensor (e.g., left)
export LUXOPI_ENABLE_VL53_LEFT=false
./start_luxopi.sh
```

## Verifying Sensor Status

### Check I2C Bus
```bash
# Before starting robot
i2cdetect -y 1
```

Expected addresses:
- `0x29` - VL53L4CD left (only if enabled)
- `0x2A` - VL53L4CD right (only if enabled, reprogrammed address)
- `0x39` - APDS9960 (MPR121 has same address)

### Check ROS Topics
```bash
# After starting robot
ros2 topic list | grep distance

# Should show (if enabled):
# /left_distance
# /right_distance
```

### Check Sensor Health
```bash
ros2 topic echo /i2c/sensor_health
```

You should see status for enabled sensors only.

## Monitoring Collision Detection

Even with VL53L4CD disabled, collision detection still works:

```bash
# Monitor collision status
ros2 topic echo /collision/front/status
ros2 topic echo /collision/left/status
ros2 topic echo /collision/right/status

# Monitor overall severity
ros2 topic echo /collision/severity
```

## Re-enabling Sensors

To re-enable sensors, simply unset the environment variables or set them back to `true`:

```bash
export LUXOPI_ENABLE_VL53_LEFT=true
export LUXOPI_ENABLE_VL53_RIGHT=true
./start_luxopi.sh
```

Or just remove the export lines entirely (defaults to `true`):
```bash
./start_luxopi.sh
```

## Technical Details

### Launch File Parameters
- `enable_vl53_left` (bool, default: true) - Enable VL53L4CD left distance sensor
- `enable_vl53_right` (bool, default: true) - Enable VL53L4CD right distance sensor

### Environment Variables
- `LUXOPI_ENABLE_VL53_LEFT` - Controls left sensor (default: true)
- `LUXOPI_ENABLE_VL53_RIGHT` - Controls right sensor (default: true)

### Modified Files
- `luxo_system.launch.py` - Added launch arguments
- `start_luxopi.sh` - Added environment variable support
- `i2c_device_manager.py` - Respects enable flags (no changes needed)

## Example Workflows

### Baseline Test (Everything Enabled)
```bash
./start_luxopi.sh
# Observe behavior, note any issues
```

### Test Without VL53L4CD
```bash
export LUXOPI_ENABLE_VL53_LEFT=false
export LUXOPI_ENABLE_VL53_RIGHT=false
./start_luxopi.sh
# Compare behavior - are issues resolved?
```

### Isolate Specific Sensor
```bash
# Test left only
export LUXOPI_ENABLE_VL53_RIGHT=false
./start_luxopi.sh

# Stop and test right only
export LUXOPI_ENABLE_VL53_LEFT=false
export LUXOPI_ENABLE_VL53_RIGHT=true
./start_luxopi.sh
```

## Log Messages

You'll see these in the startup logs when sensors are disabled:

```
[YYYY-MM-DD HH:MM:SS] VL53L4CD Left Distance Sensor: false
[YYYY-MM-DD HH:MM:SS] VL53L4CD Right Distance Sensor: false
```

And in the i2c_device_manager node:
```
[i2c_device_manager]: VL53L4CD left sensor disabled by parameter
[i2c_device_manager]: VL53L4CD right sensor disabled by parameter
```
