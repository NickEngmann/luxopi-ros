# MPR121 Calibration Tool - Enhanced Usage Guide

The MPR121.py script has been enhanced with comprehensive argparse functionality for easier sensor calibration.

## Quick Start

```bash
# Basic usage with defaults (5 channels, threshold=5)
python3 MPR121.py

# Show help
python3 MPR121.py --help
```

## Common Use Cases

### 1. Monitor Specific Channels Only

Useful when you want to focus on problematic sensors:

```bash
# Monitor only channels 0, 2, and 4
python3 MPR121.py --channels 0 2 4

# Monitor just one channel
python3 MPR121.py -c 1
```

### 2. Adjust Touch Thresholds

Set thresholds globally or per-channel:

```bash
# Set global threshold for all channels
python3 MPR121.py --touch-threshold 12 --release-threshold 8

# Different threshold for each channel
python3 MPR121.py --channel-thresholds 0:12:8 1:10:6 2:15:9 3:12:8 4:10:6
#                                      ch:touch:release
```

### 3. Quick Baseline Check

Get baseline readings and exit (no monitoring loop):

```bash
# Shows initial baseline and suggests thresholds
python3 MPR121.py --baseline-only
```

### 4. Data Logging

Output to CSV format for analysis in spreadsheet or plotting:

```bash
# Log to CSV file
python3 MPR121.py --csv > calibration_data.csv

# Log specific channels only
python3 MPR121.py --channels 0 1 2 --csv > ch012_data.csv

# Fast sampling rate
python3 MPR121.py --refresh-rate 0.1 --csv > fast_sample.csv
```

### 5. Custom Channel Names

Make output more readable:

```bash
python3 MPR121.py --channel-names "Top-Left" "Top-Right" "Bottom-Left" "Bottom-Right" "Center"
```

### 6. Multiple MPR121 Devices

If you have multiple sensors on different I2C addresses:

```bash
# First sensor at default 0x5A
python3 MPR121.py --i2c-address 0x5A

# Second sensor at 0x5B
python3 MPR121.py --i2c-address 0x5B

# Or use decimal
python3 MPR121.py --i2c-address 90  # Same as 0x5A
```

### 7. Detailed Debugging

Show all raw sensor values:

```bash
python3 MPR121.py --show-raw
```

### 8. Quiet Mode

Minimal output for scripting or clean logs:

```bash
python3 MPR121.py --quiet
```

## Complete Example Workflow

### Step 1: Get Baseline
```bash
python3 MPR121.py --baseline-only
```

**Output will show:**
- Current baseline values for each channel
- Suggested threshold settings based on readings

### Step 2: Test with Suggested Settings
```bash
# Use the recommended settings from Step 1
python3 MPR121.py --channel-thresholds 0:12:8 1:10:6 2:15:9 3:12:8 4:10:6
```

### Step 3: Fine-tune Problematic Channels
```bash
# Focus on channels 2 and 3 that seem inconsistent
python3 MPR121.py --channels 2 3 --show-raw
```

### Step 4: Log Data for Analysis
```bash
# Record 5 minutes of data with fast sampling
timeout 300 python3 MPR121.py --csv --refresh-rate 0.2 > sensor_log.csv
```

### Step 5: Verify Final Settings
```bash
# Run with final configuration
python3 MPR121.py \
  --channel-thresholds 0:12:8 1:10:6 2:15:9 3:12:8 4:10:6 \
  --refresh-rate 0.3 \
  --quiet
```

## All Command-Line Options

### Channel Configuration
| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--channels` | `-c` | Specific channels to monitor (0-11) | `--channels 0 2 4` |
| `--num-channels` | `-n` | Total number of channels (1-12) | `--num-channels 8` |
| `--channel-names` | | Custom names for channels | `--channel-names "Top" "Bottom"` |

### Threshold Configuration
| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--touch-threshold` | `-t` | Global touch threshold (0-255) | `--touch-threshold 12` |
| `--release-threshold` | `-r` | Global release threshold (0-255) | `--release-threshold 8` |
| `--channel-thresholds` | | Per-channel thresholds | `--channel-thresholds 0:12:8 1:10:6` |

### Display Configuration
| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--refresh-rate` | | Update interval in seconds | `--refresh-rate 0.2` |
| `--quiet` | `-q` | Minimal output | `--quiet` |
| `--show-raw` | | Show baseline and filtered values | `--show-raw` |
| `--csv` | | CSV output format | `--csv` |

### Hardware Configuration
| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--i2c-address` | | I2C address (hex or decimal) | `--i2c-address 0x5B` |
| `--baseline-only` | | Show baseline and exit | `--baseline-only` |

## Interpreting Delta Values

The **Delta** is the key metric for calibration:

- **Delta = Baseline - Filtered**
- When touched, capacitance increases → Filtered decreases → Delta increases
- **Touch detected when: Delta > Touch Threshold**

### Typical Delta Ranges

| Condition | Delta Range | Action |
|-----------|-------------|--------|
| No touch | 0-5 | Normal baseline noise |
| Near touch | 6-10 | Approaching threshold |
| Light touch | 10-15 | Good for sensitive detection |
| Firm touch | 15-30 | Ideal range |
| Heavy touch | 30+ | May indicate good contact |

### Threshold Guidelines

| Touch Delta Observed | Recommended Touch Threshold | Release Threshold |
|-----------------------|----------------------------|-------------------|
| 5-10 | 6-8 | 4-6 |
| 10-15 | 8-12 | 6-8 |
| 15-25 | 12-18 | 8-12 |
| 25+ | 15-20 | 10-15 |

**Release threshold should be lower than touch threshold** to provide hysteresis (prevents flickering).

## CSV Output Format

When using `--csv`, output format is:

```csv
timestamp,ch0_baseline,ch0_filtered,ch0_delta,ch0_touched,ch1_baseline,ch1_filtered,...
0.000,145,143,2,0,152,150,2,0,...
0.500,145,142,3,0,152,148,4,0,...
1.000,145,130,15,1,152,140,12,1,...
```

Import into spreadsheet or use with plotting tools:

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('sensor_log.csv')
df.plot(x='timestamp', y=['ch0_delta', 'ch1_delta', 'ch2_delta'])
plt.show()
```

## Tips for Effective Calibration

1. **Start with baseline-only mode** to get initial readings
2. **Test one channel at a time** using `--channels`
3. **Use CSV logging** for patterns over time
4. **Adjust thresholds per-channel** - each sensor may vary
5. **Watch for noise** - if Delta fluctuates >3 without touch, increase threshold
6. **Test different touch pressures** - ensure consistent detection
7. **Check for false triggers** - make sure no touches when not touching
8. **Verify release** - sensor should clear quickly after touch removed

## Troubleshooting

### "No module named 'board'" error
```bash
pip3 install --break-system-packages adafruit-circuitpython-mpr121
```

### "Failed to initialize MPR121" error
```bash
# Check I2C connection
i2cdetect -y 1

# Should show device at 0x5A (or your configured address)
```

### Delta values are always 0
- Check electrode connections
- Verify sensor power (3.3V or 5V depending on module)
- Try different I2C address: `--i2c-address 0x5B`

### Too many false triggers
- Increase touch threshold: `--touch-threshold 15`
- Check for electrical noise sources
- Ensure proper grounding
- Increase spacing between electrodes

### Touches not detected consistently
- Reduce touch threshold: `--touch-threshold 6`
- Check wire connections (loose connections)
- Verify electrode contact area (larger is better)
- Test with --show-raw to see if filtered values change

## Integration with ROS2

After calibrating, you can use the determined thresholds in your ROS2 configuration:

```python
# In your ROS2 node or config file
MPR121_CHANNEL_THRESHOLDS = {
    0: (12, 8),   # (touch, release)
    1: (10, 6),
    2: (15, 9),
    3: (12, 8),
    4: (10, 6)
}
```

Or update the `i2c_device_manager_node.py` configuration directly.

## Quick Reference Card

```bash
# Most common calibration commands:

# 1. Initial check
python3 MPR121.py --baseline-only

# 2. Monitor all with custom threshold
python3 MPR121.py -t 12 -r 8

# 3. Focus on one channel
python3 MPR121.py -c 2 --show-raw

# 4. Per-channel tuning
python3 MPR121.py --channel-thresholds 0:12:8 1:10:6

# 5. Log data for analysis
python3 MPR121.py --csv > log.csv

# 6. Different I2C address
python3 MPR121.py --i2c-address 0x5B
```

---

**Note:** Remember to run with `python3` and ensure the sensor is connected before running. You can press Ctrl+C at any time to exit and see the calibration summary.
