#!/usr/bin/env python3
"""
Test script for controlling the RoArm LED light via serial connection.
This script creates a direct serial connection and sends LED control commands.
"""

import serial
import json
import time
import argparse
import sys

def control_led(serial_port, brightness):
    """
    Control the LED brightness via serial command.
    
    Args:
        serial_port: Open serial connection
        brightness: LED brightness value (0-255)
    """
    cmd = {
        'T': 114,  # LED control command
        'led': brightness
    }
    cmd_str = json.dumps(cmd) + '\r\n'
    
    print(f"Sending LED command: {cmd_str.strip()}")
    serial_port.write(cmd_str.encode())
    serial_port.flush()
    
    # Read any response
    time.sleep(0.1)
    if serial_port.in_waiting > 0:
        response = serial_port.readline()
        print(f"Response: {response.decode('utf-8', errors='replace').strip()}")

def main():
    parser = argparse.ArgumentParser(description='Test RoArm LED control via serial')
    parser.add_argument('action', choices=['on', 'off'], 
                        help='Turn LED on or off')
    parser.add_argument('--brightness', type=int, default=255,
                        help='LED brightness when turning on (0-255, default: 255)')
    parser.add_argument('--port', default='/dev/ttyAMA0',
                        help='Serial port (default: /dev/ttyAMA0)')
    parser.add_argument('--baud', type=int, default=115200,
                        help='Baud rate (default: 115200)')
    
    args = parser.parse_args()
    
    # Validate brightness
    if args.brightness < 0 or args.brightness > 255:
        print(f"Error: Brightness must be between 0 and 255 (got {args.brightness})")
        sys.exit(1)
    
    try:
        # Open serial connection
        print(f"Opening serial port {args.port} at {args.baud} baud...")
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            timeout=1.0,
            dsrdtr=None
        )
        
        # Clear any buffered data
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Flow control settings
        ser.setRTS(False)
        ser.setDTR(False)
        
        print("Serial connection established")
        
        # Wait 5 seconds as requested
        print("Waiting 2 seconds for connection to stabilize...")
        for i in range(2, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        
        # Send LED command based on action
        if args.action == 'on':
            brightness = args.brightness
            print(f"Turning LED ON with brightness {brightness}")
        else:
            brightness = 0
            print("Turning LED OFF")
        
        control_led(ser, brightness)
        
        # Wait 5 seconds after command
        print("Waiting 1 seconds after command...")
        for i in range(1, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        
        # Close serial connection
        print("Closing serial connection...")
        ser.close()
        print("Done!")
        
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        if 'ser' in locals() and ser.is_open:
            ser.close()
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        if 'ser' in locals() and ser.is_open:
            ser.close()
        sys.exit(1)

if __name__ == "__main__":
    main()