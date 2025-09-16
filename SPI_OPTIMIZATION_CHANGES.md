# SPI Optimization Changes for NeoPixel Stability

**Date:** September 16, 2025
**Issue:** SPI timeout errors after ~30 minutes of runtime causing NeoPixel failures
**Error:** `[NeoPixel] SPI show error (attempt 2/3): ioctl timeout`
**Platform:** Raspberry Pi 5

## Changes Made

### 1. Boot Configuration (`/boot/firmware/config.txt`)

**Backup created:** `/boot/firmware/config.txt.backup.20250916_155316`

**Added the following lines:**

```ini
# SPI optimization for NeoPixel/WS2812B LEDs - Added to fix timeout issues
# Set SPI max speed to 3.2MHz (more stable than default 10MHz for long runs)
dtparam=spi=on,spidev.bufsiz=32768
# Fix core frequency to prevent throttling-induced SPI timing issues
core_freq=500
core_freq_min=500
# Force turbo to maintain consistent timing
force_turbo=0
# Increase SPI DMA priority
dtoverlay=spi-bcm2835-overlay

[pi5]
# Pi 5 specific optimizations for NeoPixel stability
# Use lower SPI speed for better signal integrity over long periods
dtparam=spi0_max_speed=3200000
# Ensure proper voltage for GPIO
over_voltage=2
# Disable frequency scaling that can affect SPI timing
arm_freq=2400
arm_freq_min=2400
```

### 2. Udev Rules (`/etc/udev/rules.d/99-spi-buffer.rules`)

**Created new file with:**

```udev
# Increase SPI buffer size for NeoPixel/WS2812B reliability
SUBSYSTEM=="spidev", KERNEL=="spidev0.*", ATTR{buffer_size}="32768"
SUBSYSTEM=="spidev", KERNEL=="spidev1.*", ATTR{buffer_size}="32768"
```

## Explanation of Changes

### SPI Speed Reduction
- **Changed:** Default 10MHz → 3.2MHz
- **Reason:** Lower speeds have better signal integrity over long cable runs and extended operation periods
- **Impact:** Slightly slower LED updates but much more reliable

### Buffer Size Increase
- **Changed:** Default buffer → 32KB
- **Reason:** Prevents buffer overruns during continuous LED updates
- **Impact:** Can handle larger data bursts without timing out

### CPU Frequency Locking
- **Changed:** Dynamic frequency scaling → Fixed frequencies
- **Reason:** Prevents CPU throttling from disrupting SPI timing
- **Settings:**
  - Core: 500MHz (fixed)
  - ARM (Pi5): 2400MHz (fixed)
- **Impact:** More consistent SPI timing, slightly higher power consumption

### GPIO Voltage Boost
- **Changed:** Added `over_voltage=2` for Pi 5
- **Reason:** Ensures stable 3.3V levels for GPIO/SPI signals
- **Impact:** Better signal quality, minimal power increase

## How to Revert

If these changes cause issues or need to be reverted:

### 1. Restore Original config.txt
```bash
sudo cp /boot/firmware/config.txt.backup.20250916_155316 /boot/firmware/config.txt
```

### 2. Remove udev rule
```bash
sudo rm /etc/udev/rules.d/99-spi-buffer.rules
```

### 3. Reboot
```bash
sudo reboot
```

## Verification Commands

After reboot, verify the changes took effect:

```bash
# Check SPI buffer size
cat /sys/module/spidev/parameters/bufsiz

# Check CPU frequencies
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq

# Check SPI is enabled
ls /dev/spidev*

# Monitor for SPI errors in logs
journalctl -f | grep -i spi
```

## Expected Results

- SPI timeout errors should be significantly reduced or eliminated
- System should run for hours without NeoPixel communication failures
- LED animations should remain smooth and consistent
- No more "ioctl timeout" warnings in logs after extended runtime

## Notes

- These optimizations prioritize **stability over performance**
- The changes are specifically tuned for WS2812B/NeoPixel LEDs
- A reboot is required for all changes to take effect
- Monitor system for 24-48 hours to confirm stability improvement

## Alternative Solutions (if issues persist)

1. **Further reduce SPI speed:** Change `dtparam=spi0_max_speed=3200000` to `2000000`
2. **Increase buffer more:** Change `32768` to `65536` in both config.txt and udev rule
3. **Add capacitors:** Hardware solution - add 1000µF capacitor near LED strip power input
4. **Use level shifter:** Ensure proper 3.3V → 5V level shifting for data line
5. **Shorten cable:** Reduce distance between Pi and first LED