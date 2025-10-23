#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2022 Carter Nelson for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2021 Carter Nelson for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

# Simple demo of the VL53L4CD distance sensor.
# Will print the sensed range/distance every second.

import board
import adafruit_vl53l4cd
import argparse
import time
import sys
import os

# Add the luxo_behaviors module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'luxo_behaviors'))
from luxo_behaviors.i2c_bus_wrapper import I2CBusWrapper

# Parse command line arguments
parser = argparse.ArgumentParser(description='VL53L4CD Sensor Test')
parser.add_argument('--sensor', choices=['left', 'right', 'both'], default='both',
                    help='Which sensor(s) to run: left, right, or both (default: both)')
args = parser.parse_args()

# Initialize I2C buses
i2c_bus_1 = board.I2C()  # Primary I2C bus (bus 1)

# Try to initialize I2C bus 3 for left sensor
# Bus 3 uses GPIO 6 (SCL) and GPIO 5 (SDA) via dtoverlay=i2c-gpio,bus=3
# Accessed via /dev/i2c-3
i2c_bus_3 = None
try:
    i2c_bus_3 = I2CBusWrapper(3)  # Software I2C bus 3
    print("I2C bus 3 initialized successfully (/dev/i2c-3, GPIO 6/SCL, GPIO 5/SDA)")
except Exception as e:
    print(f"Warning: I2C bus 3 not available: {e}")
    if args.sensor in ['left', 'both']:
        print("Error: Cannot run left sensor without I2C bus 3")
        exit(1)

# Create sensor instances based on arguments
sensors = {}
if args.sensor in ['left', 'both']:
    # Left sensor on I2C bus 3 at address 0x29
    if i2c_bus_3 is not None:
        sensors['left'] = adafruit_vl53l4cd.VL53L4CD(i2c_bus_3, 0x29)
if args.sensor in ['right', 'both']:
    # Right sensor on I2C bus 1 at address 0x29 (changed from 0x59)
    sensors['right'] = adafruit_vl53l4cd.VL53L4CD(i2c_bus_1, 0x29)

# Set the same configuration for all active sensors
for sensor in sensors.values():
    sensor.inter_measurement = 50
    sensor.timing_budget = 50

print(f"VL53L4CD Sensor Test - Running: {args.sensor}")
print("-------------------------")

# Display info for active sensors
for name, sensor in sensors.items():
    model_id, module_type = sensor.model_info
    if name == "left":
        address_info = "0x29 on bus 3"
    else:
        address_info = "0x29 on bus 1"
    print(f"{name.capitalize()} Sensor ({address_info}) - Model ID: 0x{model_id:0X}, Module Type: 0x{module_type:0X}")
    print(f"{name.capitalize()} Sensor - Timing Budget: {sensor.timing_budget}, Inter-Measurement: {sensor.inter_measurement}")

print("-------------------------")

# Start ranging on all active sensors
for sensor in sensors.values():
    sensor.start_ranging()

while True:
    # Wait for all active sensors to have data
    ready_sensors = {}
    
    while len(ready_sensors) < len(sensors):
        for name, sensor in sensors.items():
            if name not in ready_sensors and sensor.data_ready:
                ready_sensors[name] = True
                sensor.clear_interrupt()

    # Display distances from active sensors
    distance_msgs = []
    for name, sensor in sensors.items():
        distance_msgs.append(f"{name.capitalize()} Distance: {sensor.distance} cm")
    print(", ".join(distance_msgs))
    time.sleep(0.1)
