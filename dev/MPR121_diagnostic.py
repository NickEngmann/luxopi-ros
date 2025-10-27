#!/usr/bin/env python3
"""
MPR121 Full Diagnostic - ALL CHANNELS
This will help identify which electrodes work best for touch detection.

Instructions:
1. Let it stabilize for 5 seconds (hands away)
2. Touch each electrode area one at a time
3. Watch which channels show the STRONGEST positive deltas
4. Those are your best touch sensors!
"""

import time
import board
import busio
import adafruit_mpr121

# Initialize
i2c = busio.I2C(board.SCL, board.SDA)
mpr121 = adafruit_mpr121.MPR121(i2c)

NAMES = {
    0: "Bottom",
    1: "Front-Right",
    2: "Front-Left",
    3: "Top-Front",
    4: "Antenna"
}

print("=" * 80)
print("MPR121 FULL DIAGNOSTIC - ALL CHANNELS")
print("=" * 80)
print("\nConfiguring all 5 channels with low threshold (5)...")
print("This will be VERY sensitive to help identify working electrodes.\n")

# Set very low threshold to catch weak signals
for i in range(5):
    mpr121[i].threshold = 5
    mpr121[i].release_threshold = 3

print("Waiting for sensor to stabilize (5 seconds)...")
print(">>> KEEP YOUR HANDS AWAY <<<\n")
time.sleep(5)

# Record baseline
baselines = {}
for i in range(5):
    baselines[i] = mpr121.baseline_data(i)
    print(f"Channel {i} ({NAMES[i]}): Baseline = {baselines[i]}")

print("\n" + "=" * 80)
print("START TESTING NOW!")
print("=" * 80)
print("\nTouch each area slowly and firmly:")
print("  1. Bottom area (channel 0)")
print("  2. Front-Right area (channel 1)")
print("  3. Front-Left area (channel 2)")
print("  4. Top-Front area (channel 3)")
print("  5. Near the antenna (channel 4)")
print("\nWatch for positive deltas > +5")
print("Press Ctrl+C when done\n")

try:
    max_deltas = {i: 0 for i in range(5)}
    iteration = 0

    while True:
        if iteration % 10 == 0:
            print("\n" + "-" * 80)
            print(f"{'Channel':<20} {'Delta':<10} {'Max Seen':<12} {'Status':<20}")
            print("-" * 80)

        for i in range(5):
            baseline = mpr121.baseline_data(i)
            filtered = mpr121[i].raw_value
            delta = baseline - filtered
            is_touched = mpr121[i].value

            # Track maximum positive delta
            if delta > max_deltas[i]:
                max_deltas[i] = delta

            # Format output
            name = f"Ch{i} ({NAMES[i]})"

            if is_touched:
                status = "🎯 TOUCHED!"
                delta_str = f"*+{delta:3d}*" if delta > 0 else f"*{delta:4d}*"
            elif delta > 5:
                status = "approaching..."
                delta_str = f"*+{delta:3d}*" if delta > 0 else f"*{delta:4d}*"
            elif delta < -15:
                status = "RELEASE!"
                delta_str = f"*{delta:4d}*"
            else:
                status = ""
                delta_str = f"{delta:5d}"

            print(f"{name:<20} {delta_str:<10} {max_deltas[i]:>5}      {status:<20}")

        time.sleep(0.1)
        iteration += 1

except KeyboardInterrupt:
    print("\n\n" + "=" * 80)
    print("DIAGNOSTIC RESULTS")
    print("=" * 80)
    print("\nMaximum positive deltas achieved per channel:")
    print("(Higher = better touch sensitivity)\n")

    # Sort by best performance
    sorted_channels = sorted(max_deltas.items(), key=lambda x: x[1], reverse=True)

    for i, (ch, max_delta) in enumerate(sorted_channels, 1):
        rating = ""
        if max_delta > 20:
            rating = "⭐⭐⭐ EXCELLENT - Use this!"
        elif max_delta > 10:
            rating = "⭐⭐ GOOD - Usable"
        elif max_delta > 5:
            rating = "⭐ WEAK - Marginal"
        else:
            rating = "❌ POOR - Not usable"

        print(f"{i}. Channel {ch} ({NAMES[ch]}): +{max_delta} {rating}")

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print("\nBased on your results:\n")

    best_channels = [ch for ch, delta in sorted_channels if delta > 10]
    weak_channels = [ch for ch, delta in sorted_channels if 5 < delta <= 10]
    poor_channels = [ch for ch, delta in sorted_channels if delta <= 5]

    if best_channels:
        print(f"✓ USE these channels: {best_channels}")
        print(f"  Configure with: --channels {' '.join(map(str, best_channels))}")
        print(f"  Threshold suggestion: 8-12")
    else:
        print("⚠ NO channels showed strong touch signals!")
        print("  This suggests:")
        print("    - PLA may be too thick for capacitive coupling")
        print("    - Electrodes may not be properly connected")
        print("    - You may need to redesign the touch sensing")

    if weak_channels:
        print(f"\n⚠ WEAK channels: {weak_channels}")
        print(f"  These might work with: --channel-thresholds ", end="")
        print(" ".join([f"{ch}:5:3" for ch in weak_channels]))

    if poor_channels:
        print(f"\n❌ AVOID these channels: {poor_channels}")
        print("   They showed no significant touch response")

    print("\n" + "=" * 80)
    print("Next Steps:")
    print("  1. If no channels work well, consider thinner PLA or larger electrodes")
    print("  2. If only antenna works, use inverted detection (MPR121_inverted.py)")
    print("  3. If some channels work, focus on those for your petting detection")
    print("\nGoodbye! 👋\n")
