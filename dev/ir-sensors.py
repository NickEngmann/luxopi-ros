#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time

# Set up GPIO pins
LEFT_IR_PIN = 23
RIGHT_IR_PIN = 24

# Set GPIO mode to BCM
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Set up pins as inputs with pull-up resistors
# IR sensors typically output LOW when detecting an object
GPIO.setup(LEFT_IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(RIGHT_IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("IR Proximity Sensor Monitoring Started")
print("Press CTRL+C to exit")

try:
    while True:
        # Read sensor values (LOW/0 means detected, HIGH/1 means nothing detected)
        left_sensor = not GPIO.input(LEFT_IR_PIN)  # Invert for more intuitive logic
        right_sensor = not GPIO.input(RIGHT_IR_PIN)

        # Display status
        if left_sensor and right_sensor:
            print("Both sensors detecting objects!")
        elif left_sensor:
            print("Left sensor detecting object!")
        elif right_sensor:
            print("Right sensor detecting object!")
        else:
            print("No objects detected")
        
        # Sleep to avoid flooding the console and CPU
        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nProgram stopped by user")
finally:
    # Clean up GPIO settings
    GPIO.cleanup()
