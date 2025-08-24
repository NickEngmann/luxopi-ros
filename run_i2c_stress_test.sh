#!/bin/bash

# I2C Stress Test Runner
# This script runs the I2C stress test to help diagnose bus crashes

echo "Starting I2C Stress Test..."
echo "This will continuously poll all I2C devices to test for stability issues."
echo "Press Ctrl+C to stop the test."
echo ""

# Make sure the script is executable
chmod +x dev/i2c_stress_test.py

# Run the stress test
python3 dev/i2c_stress_test.py