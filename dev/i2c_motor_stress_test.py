#!/usr/bin/env python3
"""
I2C + Motor Stress Test
Tests I2C devices while sending motor commands to identify if motor operation
causes I2C failures (EMI, power drops, vibration, etc.)
"""

import board
import time
import threading
import datetime
import serial
import json
from collections import defaultdict
from adafruit_apds9960.apds9960 import APDS9960
import adafruit_vl53l4cd
import adafruit_ads7830.ads7830 as ADC
from adafruit_ads7830.analog_in import AnalogIn
import sys
import signal
import random

class ColoredOutput:
    """Simple colored terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    
    @staticmethod
    def error(text):
        return f"{ColoredOutput.RED}{text}{ColoredOutput.RESET}"
    
    @staticmethod
    def success(text):
        return f"{ColoredOutput.GREEN}{text}{ColoredOutput.RESET}"
    
    @staticmethod
    def warning(text):
        return f"{ColoredOutput.YELLOW}{text}{ColoredOutput.RESET}"
    
    @staticmethod
    def info(text):
        return f"{ColoredOutput.CYAN}{text}{ColoredOutput.RESET}"

class I2CMotorStressTest:
    def __init__(self, use_real_motors=False):
        self.running = True
        self.use_real_motors = use_real_motors
        self.i2c_bus = board.I2C()
        self.i2c_lock = threading.Lock()
        self.serial_port = None
        self.serial_lock = threading.Lock()
        
        # Motor movement patterns
        self.movement_patterns = {
            'idle': {'duration': 2.0, 'intensity': 'low'},
            'small_moves': {'duration': 5.0, 'intensity': 'medium'},
            'large_moves': {'duration': 3.0, 'intensity': 'high'},
            'rapid_changes': {'duration': 2.0, 'intensity': 'very_high'},
            'all_motors': {'duration': 4.0, 'intensity': 'high'}
        }
        self.current_pattern = 'idle'
        self.pattern_start_time = time.time()
        
        # Device instances
        self.apds9960 = None
        self.vl53_left = None
        self.vl53_right = None
        self.ads7830 = None
        
        # Statistics
        self.stats = {
            'apds9960': defaultdict(int),
            'vl53_left': defaultdict(int),
            'vl53_right': defaultdict(int),
            'ads7830': defaultdict(int),
            'motor': defaultdict(int),
            'correlation': defaultdict(list)
        }
        
        # Error tracking
        self.consecutive_errors = defaultdict(int)
        self.last_motor_command_time = 0
        self.errors_after_motor = []  # Track timing of errors relative to motor commands
        self.start_time = time.time()
        
        # Configuration
        self.poll_interval = 0.1  # 10Hz - faster to catch issues
        self.display_interval = 5.0
        self.motor_command_interval = 0.5  # Send motor commands every 0.5s
        
        # Setup signal handler
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print(ColoredOutput.info("=== I2C + Motor Stress Test Starting ==="))
        print(f"Mode: {'REAL MOTORS' if use_real_motors else 'SIMULATED'}")
        print(f"I2C poll rate: {1.0/self.poll_interval:.1f} Hz")
        print(f"Motor command rate: {1.0/self.motor_command_interval:.1f} Hz")
        print(ColoredOutput.warning("WARNING: This test will move the robot!") if use_real_motors else "")
        print(ColoredOutput.info("Press Ctrl+C to stop\n"))
        
    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print(ColoredOutput.warning("\n\nShutting down..."))
        self.running = False
        if self.serial_port:
            try:
                # Send stop command - return to rest position
                self.send_motor_command({"T": 122, "b": 0, "s": 0, "e": 90, "h": 180, "spd": 20, "acc": 10})
                time.sleep(0.5)
            except:
                pass
                
    def initialize_serial(self):
        """Initialize serial connection for motor control"""
        if not self.use_real_motors:
            print(ColoredOutput.info("Running in simulation mode - no serial connection"))
            return True
            
        try:
            self.serial_port = serial.Serial(
                port='/dev/ttyAMA0',
                baudrate=115200,
                timeout=0.1
            )
            time.sleep(2)  # Wait for connection
            print(ColoredOutput.success("✓ Serial port initialized"))
            
            # Send initial position using correct command format (T:122 for degrees)
            self.send_motor_command({"T": 122, "b": 0, "s": 0, "e": 90, "h": 180, "spd": 20, "acc": 10})
            return True
        except Exception as e:
            print(ColoredOutput.error(f"✗ Serial initialization failed: {e}"))
            return False
            
    def send_motor_command(self, command):
        """Send command to robot motors"""
        self.stats['motor']['commands_sent'] += 1
        self.last_motor_command_time = time.time()
        
        if not self.use_real_motors:
            # Simulate motor command
            time.sleep(0.001)  # Minimal delay
            return
            
        if not self.serial_port:
            return
            
        try:
            with self.serial_lock:
                json_str = json.dumps(command)
                # Add CRLF as required by the robot
                cmd_with_crlf = json_str + '\r\n'
                self.serial_port.write(cmd_with_crlf.encode())
                self.serial_port.flush()
                
                # Debug output
                print(ColoredOutput.BLUE + f"Sent: {json_str}" + ColoredOutput.RESET)
        except Exception as e:
            self.stats['motor']['command_errors'] += 1
            print(ColoredOutput.error(f"Motor command error: {e}"))
            
    def initialize_i2c_devices(self):
        """Initialize all I2C devices"""
        print(ColoredOutput.info("Initializing I2C devices..."))
        
        # Same initialization as before
        # APDS9960
        if not self.apds9960:
            try:
                with self.i2c_lock:
                    self.apds9960 = APDS9960(self.i2c_bus)
                    self.apds9960.enable_proximity = True
                    self.apds9960.proximity_gain = 1
                    time.sleep(0.05)
                print(ColoredOutput.success("✓ APDS9960 initialized"))
            except Exception as e:
                print(ColoredOutput.error(f"✗ APDS9960 init failed: {e}"))
                
        # VL53L4CD Left
        if not self.vl53_left:
            try:
                with self.i2c_lock:
                    time.sleep(0.1)
                    self.vl53_left = adafruit_vl53l4cd.VL53L4CD(self.i2c_bus, 0x29)
                    self.vl53_left.inter_measurement = 100
                    self.vl53_left.timing_budget = 100
                    time.sleep(0.05)
                    self.vl53_left.start_ranging()
                print(ColoredOutput.success("✓ VL53L4CD Left initialized"))
            except Exception as e:
                print(ColoredOutput.error(f"✗ VL53L4CD Left init failed: {e}"))
                
        # VL53L4CD Right
        if not self.vl53_right:
            try:
                with self.i2c_lock:
                    time.sleep(0.1)
                    self.vl53_right = adafruit_vl53l4cd.VL53L4CD(self.i2c_bus, 0x59)
                    self.vl53_right.inter_measurement = 100
                    self.vl53_right.timing_budget = 100
                    time.sleep(0.05)
                    self.vl53_right.start_ranging()
                print(ColoredOutput.success("✓ VL53L4CD Right initialized"))
            except Exception as e:
                print(ColoredOutput.error(f"✗ VL53L4CD Right init failed: {e}"))
                
        # ADS7830
        if not self.ads7830:
            try:
                with self.i2c_lock:
                    self.ads7830 = ADC.ADS7830(self.i2c_bus, 0x38)
                    self.ads7830_channels = {
                        0: AnalogIn(self.ads7830, 0),
                        1: AnalogIn(self.ads7830, 1),
                        2: AnalogIn(self.ads7830, 2),
                        3: AnalogIn(self.ads7830, 3),
                    }
                    time.sleep(0.05)
                print(ColoredOutput.success("✓ ADS7830 initialized"))
            except Exception as e:
                print(ColoredOutput.error(f"✗ ADS7830 init failed: {e}"))
                
        print("")
        
    def poll_i2c_device(self, device_name, read_func):
        """Poll a single I2C device and track correlation with motor commands"""
        try:
            with self.i2c_lock:
                data = read_func()
                time.sleep(0.002)
                
            if data is not None:
                self.stats[device_name]['successful_reads'] += 1
                self.consecutive_errors[device_name] = 0
                return True
            else:
                self.stats[device_name]['null_reads'] += 1
                return False
                
        except Exception as e:
            self.stats[device_name]['read_errors'] += 1
            self.consecutive_errors[device_name] += 1
            
            # Track correlation with motor commands
            time_since_motor = time.time() - self.last_motor_command_time
            self.errors_after_motor.append({
                'device': device_name,
                'time_after_motor': time_since_motor,
                'pattern': self.current_pattern,
                'error': str(e)[:50]
            })
            
            # Log correlation
            if time_since_motor < 0.5:  # Error within 500ms of motor command
                self.stats['correlation']['errors_near_motor'] += 1
                
            # Log first error
            if self.consecutive_errors[device_name] == 1:
                timestamp = datetime.datetime.now().strftime('%H:%M:%S')
                print(ColoredOutput.error(
                    f"[{timestamp}] {device_name} error "
                    f"({time_since_motor:.2f}s after motor cmd, pattern: {self.current_pattern}): "
                    f"{str(e)[:50]}"
                ))
                
            return False
            
    def generate_motor_pattern(self):
        """Generate motor commands based on current pattern"""
        pattern = self.movement_patterns[self.current_pattern]
        
        if self.current_pattern == 'idle':
            # No movement
            return None
            
        elif self.current_pattern == 'small_moves':
            # Small oscillations on shoulder joint
            angle = 0 + (random.random() * 40 - 20)  # -20 to +20 degrees
            return {"T": 122, "b": 0, "s": angle, "e": 90, "h": 180, "spd": 30, "acc": 20}
            
        elif self.current_pattern == 'large_moves':
            # Large movements on multiple joints
            return {
                "T": 122,
                "b": random.randint(-45, 45),      # Base rotation
                "s": random.randint(-30, 30),       # Shoulder
                "e": random.randint(60, 120),       # Elbow
                "h": 180,                           # Hand/tool
                "spd": 20,
                "acc": 15
            }
            
        elif self.current_pattern == 'rapid_changes':
            # Rapid direction changes with higher speed
            return {
                "T": 122,
                "b": random.choice([-30, 0, 30]),
                "s": random.choice([-20, 0, 20]),
                "e": random.choice([60, 90, 120]),
                "h": 180,
                "spd": 50,  # Fast speed
                "acc": 30   # Fast acceleration
            }
            
        elif self.current_pattern == 'all_motors':
            # Move all motors simultaneously
            return {
                "T": 122,
                "b": random.randint(-45, 45),      # Base
                "s": random.randint(-30, 30),       # Shoulder
                "e": random.randint(45, 135),       # Elbow
                "h": random.randint(90, 180),       # Hand/tool
                "spd": 25,
                "acc": 20
            }
            
    def motor_control_thread(self):
        """Thread to send motor commands"""
        pattern_index = 0
        pattern_keys = list(self.movement_patterns.keys())
        
        while self.running:
            # Check if pattern duration expired
            elapsed = time.time() - self.pattern_start_time
            current_duration = self.movement_patterns[self.current_pattern]['duration']
            
            if elapsed > current_duration:
                # Move to next pattern
                pattern_index = (pattern_index + 1) % len(pattern_keys)
                self.current_pattern = pattern_keys[pattern_index]
                self.pattern_start_time = time.time()
                print(ColoredOutput.info(f"\nSwitching to pattern: {self.current_pattern}"))
                
            # Generate and send motor command
            command = self.generate_motor_pattern()
            if command:
                self.send_motor_command(command)
                
            time.sleep(self.motor_command_interval)
            
    def i2c_polling_thread(self):
        """Thread to poll I2C devices"""
        while self.running:
            # Poll each device
            if self.apds9960:
                self.poll_i2c_device('apds9960', lambda: self.apds9960.proximity)
                
            if self.vl53_left:
                def read_vl53_left():
                    if self.vl53_left.data_ready:
                        dist = self.vl53_left.distance
                        self.vl53_left.clear_interrupt()
                        return dist
                    return None
                self.poll_i2c_device('vl53_left', read_vl53_left)
                
            if self.vl53_right:
                def read_vl53_right():
                    if self.vl53_right.data_ready:
                        dist = self.vl53_right.distance
                        self.vl53_right.clear_interrupt()
                        return dist
                    return None
                self.poll_i2c_device('vl53_right', read_vl53_right)
                
            if self.ads7830:
                def read_ads7830():
                    data = {}
                    for ch, analog in self.ads7830_channels.items():
                        try:
                            data[f'ch{ch}'] = analog.value
                        except:
                            pass
                    return data if data else None
                self.poll_i2c_device('ads7830', read_ads7830)
                
            time.sleep(self.poll_interval)
            
    def display_statistics(self):
        """Display statistics with motor correlation analysis"""
        runtime = time.time() - self.start_time
        
        print(ColoredOutput.info("\n=== I2C + Motor Stress Test Statistics ==="))
        print(f"Runtime: {runtime/60:.1f} minutes")
        print(f"Current pattern: {self.current_pattern}")
        print(f"Motor commands sent: {self.stats['motor']['commands_sent']}")
        
        # I2C device statistics
        total_errors = 0
        for device in ['apds9960', 'vl53_left', 'vl53_right', 'ads7830']:
            errors = self.stats[device]['read_errors']
            reads = self.stats[device]['successful_reads'] + errors
            total_errors += errors
            
            if reads > 0:
                error_rate = (errors / reads) * 100
                status = "✓" if self.consecutive_errors[device] == 0 else "✗"
                color = ColoredOutput.success if self.consecutive_errors[device] == 0 else ColoredOutput.error
                
                print(f"\n{color(f'{status} {device}:')}")
                print(f"  Error rate: {error_rate:.2f}% ({errors} errors in {reads} reads)")
                print(f"  Consecutive errors: {self.consecutive_errors[device]}")
                
        # Correlation analysis
        if self.errors_after_motor:
            print(ColoredOutput.warning("\n=== Motor Correlation Analysis ==="))
            
            # Group errors by time after motor command
            time_buckets = {
                '0-100ms': 0,
                '100-500ms': 0,
                '500ms-1s': 0,
                '1s+': 0
            }
            
            pattern_errors = defaultdict(int)
            
            for error in self.errors_after_motor:
                time_after = error['time_after_motor']
                pattern_errors[error['pattern']] += 1
                
                if time_after < 0.1:
                    time_buckets['0-100ms'] += 1
                elif time_after < 0.5:
                    time_buckets['100-500ms'] += 1
                elif time_after < 1.0:
                    time_buckets['500ms-1s'] += 1
                else:
                    time_buckets['1s+'] += 1
                    
            print("Errors by time after motor command:")
            for bucket, count in time_buckets.items():
                percentage = (count / len(self.errors_after_motor)) * 100 if self.errors_after_motor else 0
                print(f"  {bucket}: {count} ({percentage:.1f}%)")
                
            print("\nErrors by movement pattern:")
            for pattern, count in pattern_errors.items():
                print(f"  {pattern}: {count} errors")
                
            # Check if errors cluster around motor commands
            if time_buckets['0-100ms'] + time_buckets['100-500ms'] > len(self.errors_after_motor) * 0.7:
                print(ColoredOutput.error("\n⚠️  STRONG CORRELATION: Most errors occur within 500ms of motor commands!"))
                print("Possible causes: EMI, power supply issues, ground loops")
                
    def run(self):
        """Run the test"""
        # Initialize serial if using real motors
        if self.use_real_motors and not self.initialize_serial():
            print(ColoredOutput.error("Failed to initialize serial, running without motors"))
            self.use_real_motors = False
            
        # Initialize I2C devices
        self.initialize_i2c_devices()
        
        # Start threads
        threads = [
            threading.Thread(target=self.i2c_polling_thread, daemon=True),
            threading.Thread(target=self.motor_control_thread, daemon=True),
        ]
        
        for thread in threads:
            thread.start()
            
        # Display loop
        try:
            while self.running:
                time.sleep(self.display_interval)
                if self.running:
                    self.display_statistics()
        except:
            pass
            
        # Final report
        print(ColoredOutput.info("\n\n=== FINAL ANALYSIS ==="))
        self.display_statistics()
        
        if self.errors_after_motor:
            avg_time = sum(e['time_after_motor'] for e in self.errors_after_motor) / len(self.errors_after_motor)
            print(f"\nAverage time between motor command and I2C error: {avg_time:.3f}s")
            
        print(ColoredOutput.info("\nTest completed."))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='I2C + Motor Stress Test')
    parser.add_argument('--real-motors', action='store_true', 
                        help='Use real motor commands (WARNING: Robot will move!)')
    args = parser.parse_args()
    
    test = I2CMotorStressTest(use_real_motors=args.real_motors)
    test.run()