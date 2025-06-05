#!/usr/bin/env python3

import board
from adafruit_apds9960.apds9960 import APDS9960
import time
import threading
import queue

# Initialize I2C and sensor
i2c = board.I2C()  # uses board.SCL and board.SDA
# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

apds = APDS9960(i2c)  # Address is 0x49
apds.enable_proximity = True
apds.proximity_gain = 1
apds.enable_gesture = True

# Uncomment and set the rotation if depending on how your sensor is mounted.
# apds.rotation = 270 # 270 for CLUE

# Create a queue for thread communication
gesture_queue = queue.Queue()

# Gesture detection function to run in a separate thread
def gesture_detection():
    while True:
        try:
            # Call gesture() in its own thread
            gesture = apds.gesture()
            if gesture:  # Only put on queue if there's a valid gesture
                if gesture == 0x01:
                    gesture_queue.put("up")
                elif gesture == 0x02:
                    gesture_queue.put("down")
                elif gesture == 0x03:
                    gesture_queue.put("left")
                elif gesture == 0x04:
                    gesture_queue.put("right")
            time.sleep(0.01)  # Small sleep to prevent CPU overload
        except Exception as e:
            print(f"Gesture thread error: {e}")
            time.sleep(1)

# Start gesture detection in its own thread
gesture_thread = threading.Thread(target=gesture_detection, daemon=True)
gesture_thread.start()

# Main loop for proximity readings
while True:
    try:
        # Display proximity
        proximity = apds.proximity
        print(f"proximity: {proximity}")
        
        # Check if there are any gestures in the queue
        while not gesture_queue.empty():
            gesture = gesture_queue.get_nowait()
            print(f"Gesture detected: {gesture}")
        time.sleep(1.0)
    except Exception as e:
        print(f"Main thread error: {e}")
        time.sleep(1)
