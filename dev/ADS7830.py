# SPDX-FileCopyrightText: 2023 Liz Clark for Adafruit Industries
# SPDX-License-Identifier: MIT

# Demo to read analog input on all 8 channels with FSR pressure detection

import time
import board
import adafruit_ads7830.ads7830 as ADC
from adafruit_ads7830.analog_in import AnalogIn

i2c = board.I2C()

# Initialize ADS7830
adc = ADC.ADS7830(i2c, 0x38)

# Create analog input objects for all 8 channels
channels = []
for i in range(8):
    channels.append(AnalogIn(adc, i))

def get_pressure_state(value):
    """
    Map ADC value to pressure state
    Returns: (state_number, state_name, state_symbol)
    """
    if value >= 24000:  # Not pressed (allowing for some noise)
        return (0, "Not Pressed", "-")
    elif value >= 20000:  # Very light touch
        return (1, "Light Touch", "1")
    elif value >= 17500:  # Light press
        return (2, "Light Press", "2")
    elif value >= 15000:  # Medium press
        return (3, "Medium Press", "3")
    elif value >= 8000:   # Hard press
        return (4, "Hard Press", "4")
    elif value >= 4000:   # Very hard press
        return (5, "Very Hard", "5")
    else:                 # Maximum press
        return (6, "Maximum", "!")

def format_channel_output(channel_num, value):
    """Format output for a single channel"""
    state_num, state_name, symbol = get_pressure_state(value)
    
    # Only show detailed info if pressed
    if state_num > 0:
        return f"a{channel_num}:{symbol}[{state_num}]"
    else:
        return f"a{channel_num}:-"

while True:
    # Build output string
    output_parts = []
    active_channels = []
    
    for i in range(8):
        value = channels[i].value
        state_num, state_name, symbol = get_pressure_state(value)
        
        # Track active channels
        if state_num > 0:
            active_channels.append((i, value, state_num, state_name))
        
        output_parts.append(format_channel_output(i, value))
    
    # Print compact status line
    print(" ".join(output_parts))
    
    # If any channels are active, show detailed info on next line
    if active_channels:
        details = []
        for ch, val, state, name in active_channels:
            details.append(f"  Ch{ch}: {name} ({val})")
        print("\n".join(details))
        print()  # Extra line for readability
    
    time.sleep(0.25)