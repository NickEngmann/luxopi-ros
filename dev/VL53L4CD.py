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

i2c = board.I2C()  # uses board.SCL and board.SDA
# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

# Create two sensor instances - left with custom address, right with default address
vl53_right = adafruit_vl53l4cd.VL53L4CD(i2c, 0x29)  # using default address
vl53_left = adafruit_vl53l4cd.VL53L4CD(i2c, 0x59)

# Set the same configuration for both sensors
for vl53 in (vl53_left, vl53_right):
    vl53.inter_measurement = 0
    vl53.timing_budget = 200

print("VL53L4CD Dual Sensor Test.")
print("-------------------------")
# Display info for left sensor
model_id, module_type = vl53_left.model_info
print("Left Sensor (0x59) - Model ID: 0x{:0X}, Module Type: 0x{:0X}".format(model_id, module_type))
print("Left Sensor - Timing Budget: {}, Inter-Measurement: {}".format(vl53_left.timing_budget, vl53_left.inter_measurement))

# Display info for right sensor
model_id, module_type = vl53_right.model_info
print("Right Sensor (default) - Model ID: 0x{:0X}, Module Type: 0x{:0X}".format(model_id, module_type))
print("Right Sensor - Timing Budget: {}, Inter-Measurement: {}".format(vl53_right.timing_budget, vl53_right.inter_measurement))
print("-------------------------")

# Start ranging on both sensors
vl53_left.start_ranging()
vl53_right.start_ranging()

while True:
    # Wait for both sensors to have data
    left_ready = False
    right_ready = False
    
    while not (left_ready and right_ready):
        if not left_ready and vl53_left.data_ready:
            left_ready = True
            vl53_left.clear_interrupt()
        if not right_ready and vl53_right.data_ready:
            right_ready = True
            vl53_right.clear_interrupt()

    # Display distances from both sensors
    print("Left Distance: {} cm, Right Distance: {} cm".format(vl53_left.distance, vl53_right.distance))
