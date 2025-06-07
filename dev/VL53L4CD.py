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
# Parse command line arguments
parser = argparse.ArgumentParser(description='VL53L4CD Sensor Test')
parser.add_argument('--sensor', choices=['left', 'right', 'both'], default='both',
                    help='Which sensor(s) to run: left, right, or both (default: both)')
args = parser.parse_args()

i2c = board.I2C()  # uses board.SCL and board.SDA
# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

# Create sensor instances based on arguments
sensors = {}
if args.sensor in ['left', 'both']:
    sensors['left'] = adafruit_vl53l4cd.VL53L4CD(i2c, 0x59)  # using custom address
if args.sensor in ['right', 'both']:
    sensors['right'] = adafruit_vl53l4cd.VL53L4CD(i2c, 0x29)  # using default address

# Set the same configuration for all active sensors
for sensor in sensors.values():
    sensor.inter_measurement = 50
    sensor.timing_budget = 50

print(f"VL53L4CD Sensor Test - Running: {args.sensor}")
print("-------------------------")

# Display info for active sensors
for name, sensor in sensors.items():
    model_id, module_type = sensor.model_info
    address = "0x59" if name == "left" else "default"
    print(f"{name.capitalize()} Sensor ({address}) - Model ID: 0x{model_id:0X}, Module Type: 0x{module_type:0X}")
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
    time.sleep(0.5)
