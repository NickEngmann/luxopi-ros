#!/usr/bin/env python3
"""
I2C Monitor Log Analyzer
Analyzes stress test output to identify patterns in I2C failures
"""

import sys
import re
from collections import defaultdict
import datetime

class LogAnalyzer:
    def __init__(self):
        self.error_patterns = defaultdict(list)
        self.error_timeline = []
        self.device_errors = defaultdict(int)
        self.error_types = defaultdict(int)
        
    def parse_log_file(self, filename):
        """Parse a log file for I2C errors and statistics"""
        print(f"Analyzing log file: {filename}")
        
        with open(filename, 'r') as f:
            for line in f:
                self.parse_line(line.strip())
                
    def parse_line(self, line):
        """Parse a single log line"""
        # Extract timestamp if present
        timestamp_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', line)
        timestamp = timestamp_match.group(1) if timestamp_match else None
        
        # Check for error patterns
        if "error" in line.lower():
            # Extract device name
            for device in ['apds9960', 'vl53_left', 'vl53_right', 'ads7830']:
                if device in line.lower():
                    self.device_errors[device] += 1
                    
                    # Extract error type
                    if "errno 121" in line.lower():
                        error_type = "I2C No ACK (121)"
                    elif "errno 110" in line.lower():
                        error_type = "I2C Timeout (110)"
                    elif "errno 5" in line.lower():
                        error_type = "I/O Error (5)"
                    elif "init failed" in line.lower():
                        error_type = "Initialization Failed"
                    elif "read failed" in line.lower():
                        error_type = "Read Failed"
                    else:
                        error_type = "Unknown Error"
                        
                    self.error_types[error_type] += 1
                    
                    if timestamp:
                        self.error_timeline.append({
                            'time': timestamp,
                            'device': device,
                            'error': error_type,
                            'line': line
                        })
                        
        # Check for bus lockup
        if "BUS LOCKUP DETECTED" in line:
            self.error_types["Bus Lockup"] += 1
            if timestamp:
                self.error_timeline.append({
                    'time': timestamp,
                    'device': 'bus',
                    'error': 'Bus Lockup',
                    'line': line
                })
                
    def analyze_patterns(self):
        """Analyze error patterns and correlations"""
        print("\n=== ERROR ANALYSIS ===")
        
        # Device error summary
        print("\nDevice Error Counts:")
        for device, count in sorted(self.device_errors.items()):
            print(f"  {device}: {count} errors")
            
        # Error type summary
        print("\nError Type Distribution:")
        for error_type, count in sorted(self.error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type}: {count} occurrences")
            
        # Time-based analysis
        if self.error_timeline:
            print("\nTemporal Analysis:")
            
            # Group errors by minute
            errors_by_minute = defaultdict(list)
            for error in self.error_timeline:
                minute = error['time'][:5]  # HH:MM
                errors_by_minute[minute].append(error)
                
            # Find minutes with most errors
            worst_minutes = sorted(errors_by_minute.items(), 
                                 key=lambda x: len(x[1]), 
                                 reverse=True)[:5]
            
            print("  Minutes with most errors:")
            for minute, errors in worst_minutes:
                print(f"    {minute}: {len(errors)} errors")
                
            # Check for cascading failures
            print("\nCascading Failure Detection:")
            cascade_threshold = 5  # errors within 10 seconds
            cascades = []
            
            for i in range(len(self.error_timeline) - cascade_threshold):
                window = self.error_timeline[i:i+cascade_threshold]
                devices = set(e['device'] for e in window)
                if len(devices) >= 3:  # Multiple devices failing
                    cascades.append({
                        'start': window[0]['time'],
                        'devices': devices,
                        'errors': [e['error'] for e in window]
                    })
                    
            if cascades:
                print(f"  Found {len(cascades)} potential cascade events")
                for cascade in cascades[:3]:  # Show first 3
                    print(f"    {cascade['start']}: {', '.join(cascade['devices'])} failed together")
            else:
                print("  No cascade patterns detected")
                
        # Recommendations
        print("\n=== RECOMMENDATIONS ===")
        
        if self.error_types.get("I2C No ACK (121)", 0) > 10:
            print("- High number of 'No ACK' errors suggests:")
            print("  * Check I2C pull-up resistors (should be 4.7kΩ)")
            print("  * Verify power supply stability")
            print("  * Check for loose connections")
            
        if self.error_types.get("I2C Timeout (110)", 0) > 10:
            print("- High number of timeout errors suggests:")
            print("  * I2C bus speed may be too high")
            print("  * Cable length issues")
            print("  * Interference from nearby devices")
            
        if self.error_types.get("Bus Lockup", 0) > 0:
            print("- Bus lockups detected:")
            print("  * Consider adding I2C bus recovery mechanism")
            print("  * Check for devices holding SDA/SCL low")
            print("  * May need to reduce polling frequency")
            
        # Device-specific recommendations
        worst_device = max(self.device_errors.items(), key=lambda x: x[1])[0] if self.device_errors else None
        if worst_device:
            print(f"\n- {worst_device} has the most errors:")
            if worst_device.startswith('vl53'):
                print("  * VL53L4CD sensors are sensitive to timing")
                print("  * Try increasing inter_measurement and timing_budget")
            elif worst_device == 'apds9960':
                print("  * APDS9960 may need gesture mode disabled")
                print("  * Check proximity gain settings")
            elif worst_device == 'ads7830':
                print("  * ADC may be affected by analog noise")
                print("  * Check sensor wiring and shielding")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 i2c_monitor_log_analyzer.py <logfile>")
        print("Example: python3 i2c_monitor_log_analyzer.py stress_test.log")
        sys.exit(1)
        
    analyzer = LogAnalyzer()
    analyzer.parse_log_file(sys.argv[1])
    analyzer.analyze_patterns()

if __name__ == "__main__":
    main()