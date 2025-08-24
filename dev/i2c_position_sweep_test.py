#!/usr/bin/env python3
"""
I2C Position Sweep Test
Systematically tests all arm positions within animation constraints
to identify positions that cause I2C failures due to wire strain
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
import math

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
    BOLD = '\033[1m'
    
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
    
    @staticmethod
    def bold(text):
        return f"{ColoredOutput.BOLD}{text}{ColoredOutput.RESET}"

class I2CPositionSweepTest:
    def __init__(self, use_real_motors=False):
        self.running = True
        self.use_real_motors = use_real_motors
        self.i2c_bus = board.I2C()
        self.i2c_lock = threading.Lock()
        self.serial_port = None
        self.serial_lock = threading.Lock()
        
        # Joint constraints from animation guidelines (in degrees)
        self.joint_limits = {
            'base': (-90, 90),       # j1
            'shoulder': (0, 180),    # j2 - but animation prefers (-63 to 17 degrees)
            'elbow': (0, 180),       # j3
            'wrist': (0, 180),       # j4
            'roll': (-90, 90),       # j5 - hand/wrist roll
            'hand': (0, 180)         # j6 - gripper/tool
        }
        
        # Animation-preferred ranges (converted from radians)
        self.animation_limits = {
            'base': (-90, 90),
            'shoulder': (-63, 17),    # -1.1 to 0.3 radians from guidelines
            'elbow': (0, 180),
            'wrist': (57, 172),       # 1.0 to 3.0 radians typical
            'roll': (-129, -43),      # -2.25 to -0.75 radians from guidelines
            'hand': (60, 120)         # Tool/LED control from CLAUDE.md
        }
        
        # Current position
        self.current_position = {'base': 0, 'shoulder': 0, 'elbow': 90, 'wrist': 90, 'roll': -86, 'hand': 90}
        self.position_when_failed = None
        self.failure_detected = False
        
        # Device instances
        self.apds9960 = None
        self.vl53_left = None
        self.vl53_right = None
        self.ads7830 = None
        
        # Last sensor readings
        self.last_readings = {
            'apds9960': {'value': None, 'time': None},
            'vl53_left': {'value': None, 'time': None},
            'vl53_right': {'value': None, 'time': None},
            'ads7830': {'value': None, 'time': None}
        }
        
        # Statistics
        self.stats = {
            'positions_tested': 0,
            'i2c_errors': defaultdict(int),
            'failed_positions': []
        }
        
        # Configuration
        self.poll_interval = 0.05  # 20Hz for faster detection
        self.movement_pause = 0.5  # Pause after each movement
        self.display_interval = 2.0  # Show readings every 2 seconds
        
        # Setup signal handler
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print(ColoredOutput.info("=== I2C Position Sweep Test ==="))
        print(f"Mode: {'REAL MOTORS' if use_real_motors else 'SIMULATED'}")
        print(ColoredOutput.warning("This test will systematically move through all positions"))
        print(ColoredOutput.info("Press Ctrl+C to stop\n"))
        
    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print(ColoredOutput.warning("\n\nShutting down..."))
        self.running = False
        if self.serial_port and self.use_real_motors:
            try:
                # Return to safe position
                self.send_motor_command({"T": 122, "b": 0, "s": 0, "e": 90, "t": 90, "r": -86, "h": 90, "spd": 20, "acc": 10})
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
            time.sleep(2)
            print(ColoredOutput.success("✓ Serial port initialized"))
            
            # Move to initial position (all 6 joints)
            self.send_motor_command({"T": 122, "b": 0, "s": 0, "e": 90, "t": 90, "r": -86, "h": 90, "spd": 20, "acc": 10})
            return True
        except Exception as e:
            print(ColoredOutput.error(f"✗ Serial initialization failed: {e}"))
            return False
            
    def send_motor_command(self, command):
        """Send command to robot motors"""
        self.current_position = {
            'base': command.get('b', self.current_position['base']),
            'shoulder': command.get('s', self.current_position['shoulder']),
            'elbow': command.get('e', self.current_position['elbow']),
            'wrist': command.get('t', self.current_position['wrist']),
            'roll': command.get('r', self.current_position['roll']),
            'hand': command.get('h', self.current_position['hand'])
        }
        
        if not self.use_real_motors:
            time.sleep(0.01)  # Small simulation delay
            return
            
        if not self.serial_port:
            return
            
        try:
            with self.serial_lock:
                json_str = json.dumps(command)
                cmd_with_crlf = json_str + '\r\n'
                self.serial_port.write(cmd_with_crlf.encode())
                self.serial_port.flush()
        except Exception as e:
            print(ColoredOutput.error(f"Motor command error: {e}"))
            
    def initialize_i2c_devices(self):
        """Initialize all I2C devices"""
        print(ColoredOutput.info("Initializing I2C devices..."))
        
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
        
    def poll_i2c_devices(self):
        """Poll all I2C devices and update readings"""
        all_success = True
        current_time = time.time()
        
        # Poll APDS9960
        if self.apds9960:
            try:
                with self.i2c_lock:
                    value = self.apds9960.proximity
                    time.sleep(0.002)
                self.last_readings['apds9960'] = {'value': value, 'time': current_time}
            except Exception as e:
                self.stats['i2c_errors']['apds9960'] += 1
                all_success = False
                if not self.failure_detected:
                    self.log_failure('apds9960', e)
                    
        # Poll VL53 Left
        if self.vl53_left:
            try:
                with self.i2c_lock:
                    if self.vl53_left.data_ready:
                        value = self.vl53_left.distance
                        self.vl53_left.clear_interrupt()
                        if 0 < value <= 400:
                            self.last_readings['vl53_left'] = {'value': value, 'time': current_time}
                    time.sleep(0.002)
            except Exception as e:
                self.stats['i2c_errors']['vl53_left'] += 1
                all_success = False
                if not self.failure_detected:
                    self.log_failure('vl53_left', e)
                    
        # Poll VL53 Right
        if self.vl53_right:
            try:
                with self.i2c_lock:
                    if self.vl53_right.data_ready:
                        value = self.vl53_right.distance
                        self.vl53_right.clear_interrupt()
                        if 0 < value <= 400:
                            self.last_readings['vl53_right'] = {'value': value, 'time': current_time}
                    time.sleep(0.002)
            except Exception as e:
                self.stats['i2c_errors']['vl53_right'] += 1
                all_success = False
                if not self.failure_detected:
                    self.log_failure('vl53_right', e)
                    
        # Poll ADS7830
        if self.ads7830:
            try:
                data = {}
                with self.i2c_lock:
                    for ch, analog in self.ads7830_channels.items():
                        data[f'ch{ch}'] = analog.value
                    time.sleep(0.002)
                self.last_readings['ads7830'] = {'value': data, 'time': current_time}
            except Exception as e:
                self.stats['i2c_errors']['ads7830'] += 1
                all_success = False
                if not self.failure_detected:
                    self.log_failure('ads7830', e)
                    
        return all_success
        
    def log_failure(self, device, error):
        """Log I2C failure with position details"""
        self.failure_detected = True
        self.position_when_failed = self.current_position.copy()
        
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        print(ColoredOutput.bold(ColoredOutput.error(f"\n!!! I2C FAILURE DETECTED at {timestamp} !!!")))
        print(ColoredOutput.error(f"Failed device: {device}"))
        print(ColoredOutput.error(f"Error: {str(error)[:100]}"))
        print(ColoredOutput.error(f"Position when failed:"))
        print(ColoredOutput.error(f"  Base (j1): {self.current_position['base']}°"))
        print(ColoredOutput.error(f"  Shoulder (j2): {self.current_position['shoulder']}°"))
        print(ColoredOutput.error(f"  Elbow (j3): {self.current_position['elbow']}°"))
        print(ColoredOutput.error(f"  Wrist (j4): {self.current_position['wrist']}°"))
        print(ColoredOutput.error(f"  Roll (j5): {self.current_position['roll']}°"))
        print(ColoredOutput.error(f"  Hand (j6): {self.current_position['hand']}°"))
        
        # Log to stats
        self.stats['failed_positions'].append({
            'time': timestamp,
            'device': device,
            'position': self.current_position.copy(),
            'error': str(error)
        })
        
    def display_current_readings(self):
        """Display current sensor readings"""
        print(ColoredOutput.info(f"\n--- Position: B:{self.current_position['base']}° "
                               f"S:{self.current_position['shoulder']}° "
                               f"E:{self.current_position['elbow']}° "
                               f"W:{self.current_position['wrist']}° "
                               f"R:{self.current_position['roll']}° "
                               f"H:{self.current_position['hand']}° ---"))
        
        current_time = time.time()
        
        # APDS9960
        if self.last_readings['apds9960']['value'] is not None:
            age = current_time - self.last_readings['apds9960']['time']
            value = self.last_readings['apds9960']['value']
            print(f"APDS9960 Proximity: {ColoredOutput.MAGENTA}{value}{ColoredOutput.RESET} "
                  f"(age: {age:.1f}s)")
        else:
            print(f"APDS9960: {ColoredOutput.YELLOW}No data{ColoredOutput.RESET}")
            
        # VL53 sensors
        for sensor in ['vl53_left', 'vl53_right']:
            if self.last_readings[sensor]['value'] is not None:
                age = current_time - self.last_readings[sensor]['time']
                value = self.last_readings[sensor]['value']
                print(f"{sensor}: {ColoredOutput.MAGENTA}{value:.1f}cm{ColoredOutput.RESET} "
                      f"(age: {age:.1f}s)")
            else:
                print(f"{sensor}: {ColoredOutput.YELLOW}No data{ColoredOutput.RESET}")
                
        # ADS7830
        if self.last_readings['ads7830']['value'] is not None:
            age = current_time - self.last_readings['ads7830']['time']
            values = self.last_readings['ads7830']['value']
            formatted = ', '.join([f"{k}:{v}" for k, v in values.items()])
            print(f"ADS7830 Touch: {ColoredOutput.MAGENTA}{formatted}{ColoredOutput.RESET} "
                  f"(age: {age:.1f}s)")
        else:
            print(f"ADS7830: {ColoredOutput.YELLOW}No data{ColoredOutput.RESET}")
            
    def position_sweep_thread(self):
        """Thread that moves through all positions systematically"""
        # Wait for initial sensor readings
        time.sleep(2)
        
        # Define test positions (using realistic animation ranges)
        base_positions = [-30, -15, 0, 15, 30]  # Much more limited base rotation
        shoulder_positions = [-60, -45, -30, -15, 0, 15]  # Animation range
        elbow_positions = [30, 60, 90, 120, 150]
        wrist_positions = [60, 90, 120, 150]  # Wrist range (1.0 to 2.6 rad)
        roll_positions = [-120, -100, -86, -70, -50]  # Roll range from animation guidelines
        hand_positions = [70, 90, 110]  # Tool/LED positions (reduced set)
        
        # Calculate total but test in smaller batches to avoid exhaustive combinations
        # Test critical combinations rather than all permutations
        print(ColoredOutput.info("Testing positions with focus on wire stress points..."))
        
        position_count = 0
        
        # Phase 1: Test extremes on each axis individually
        print(ColoredOutput.bold("\nPhase 1: Testing individual axis extremes"))
        
        # Base extremes (limited to realistic range)
        for base in [-30, 0, 30]:
            if not self.running or self.failure_detected:
                break
            position_count += 1
            print(ColoredOutput.info(f"\nTesting base extreme {position_count}: B={base}"))
            self.send_motor_command({
                "T": 122, "b": base, "s": -30, "e": 90, "t": 90, "r": -86, "h": 90,
                "spd": 25, "acc": 15
            })
            time.sleep(self.movement_pause + 0.2)
            
        # Shoulder extremes
        for shoulder in [-60, 0, 15]:
            if not self.running or self.failure_detected:
                break
            position_count += 1
            print(ColoredOutput.info(f"\nTesting shoulder extreme {position_count}: S={shoulder}"))
            self.send_motor_command({
                "T": 122, "b": 0, "s": shoulder, "e": 90, "t": 90, "r": -86, "h": 90,
                "spd": 25, "acc": 15
            })
            time.sleep(self.movement_pause + 0.2)
            
        # Roll extremes (this is j5 - the missing axis!)
        for roll in [-120, -86, -50]:
            if not self.running or self.failure_detected:
                break
            position_count += 1
            print(ColoredOutput.info(f"\nTesting roll extreme {position_count}: R={roll}"))
            self.send_motor_command({
                "T": 122, "b": 0, "s": -30, "e": 90, "t": 90, "r": roll, "h": 90,
                "spd": 25, "acc": 15
            })
            time.sleep(self.movement_pause + 0.2)
            
        # Phase 2: Test combined movements (likely to cause wire stress)
        print(ColoredOutput.bold("\nPhase 2: Testing combined movements"))
        
        test_combinations = [
            # Base + Roll combinations (twisting motions with realistic base range)
            {"b": -30, "s": -30, "e": 90, "t": 90, "r": -120, "h": 90},
            {"b": 30, "s": -30, "e": 90, "t": 90, "r": -50, "h": 90},
            {"b": -30, "s": -30, "e": 90, "t": 90, "r": -50, "h": 90},
            {"b": 30, "s": -30, "e": 90, "t": 90, "r": -120, "h": 90},
            
            # Extreme reach positions
            {"b": 0, "s": 15, "e": 30, "t": 150, "r": -86, "h": 90},
            {"b": 0, "s": -60, "e": 150, "t": 60, "r": -86, "h": 90},
            
            # Complex twisted positions (with limited base)
            {"b": -25, "s": 0, "e": 120, "t": 120, "r": -100, "h": 110},
            {"b": 25, "s": -45, "e": 60, "t": 90, "r": -70, "h": 70},
            
            # Typical animation positions that might stress wires
            {"b": -15, "s": -40, "e": 100, "t": 100, "r": -110, "h": 90},
            {"b": 15, "s": -20, "e": 80, "t": 110, "r": -60, "h": 100},
        ]
        
        for combo in test_combinations:
            if not self.running or self.failure_detected:
                break
            position_count += 1
            print(ColoredOutput.info(f"\nTesting combination {position_count}: "
                                   f"B={combo['b']} S={combo['s']} E={combo['e']} "
                                   f"W={combo['t']} R={combo['r']} H={combo['h']}"))
            combo["T"] = 122
            combo["spd"] = 25
            combo["acc"] = 15
            self.send_motor_command(combo)
            time.sleep(self.movement_pause + 0.2)
            
        # Phase 3: Systematic roll sweep at different base positions
        print(ColoredOutput.bold("\nPhase 3: Roll sweep at different base positions"))
        
        for base in [-20, 0, 20]:  # More realistic base positions
            if not self.running or self.failure_detected:
                break
            for roll in roll_positions:
                if not self.running or self.failure_detected:
                    break
                position_count += 1
                print(ColoredOutput.info(f"\nTesting roll sweep {position_count}: B={base} R={roll}"))
                self.send_motor_command({
                    "T": 122, "b": base, "s": -30, "e": 90, "t": 90, "r": roll, "h": 90,
                    "spd": 20, "acc": 15
                })
                time.sleep(self.movement_pause + 0.2)
                
        self.stats['positions_tested'] = position_count
                        
        if not self.failure_detected:
            print(ColoredOutput.success("\n✓ Completed all positions without I2C failures!"))
            
    def i2c_polling_thread(self):
        """Thread to continuously poll I2C devices"""
        while self.running:
            success = self.poll_i2c_devices()
            
            if not success and not self.failure_detected:
                # Stop movement immediately on first failure
                self.running = False
                
            time.sleep(self.poll_interval)
            
    def display_thread(self):
        """Thread to display current readings periodically"""
        while self.running and not self.failure_detected:
            time.sleep(self.display_interval)
            if self.running and not self.failure_detected:
                self.display_current_readings()
                
    def run(self):
        """Run the position sweep test"""
        # Initialize serial if using real motors
        if self.use_real_motors and not self.initialize_serial():
            print(ColoredOutput.error("Failed to initialize serial, running without motors"))
            self.use_real_motors = False
            
        # Initialize I2C devices
        self.initialize_i2c_devices()
        
        # Take initial readings
        print(ColoredOutput.info("Taking initial sensor readings..."))
        for _ in range(5):
            self.poll_i2c_devices()
            time.sleep(0.1)
        self.display_current_readings()
        
        # Start threads
        threads = [
            threading.Thread(target=self.i2c_polling_thread, daemon=True),
            threading.Thread(target=self.position_sweep_thread, daemon=True),
            threading.Thread(target=self.display_thread, daemon=True)
        ]
        
        for thread in threads:
            thread.start()
            
        # Wait for completion or failure
        try:
            while self.running:
                time.sleep(0.1)
        except:
            pass
            
        # Final report
        print(ColoredOutput.info("\n\n=== TEST RESULTS ==="))
        print(f"Positions tested: {self.stats['positions_tested']}")
        
        if self.stats['i2c_errors']:
            print(ColoredOutput.error(f"\nI2C Errors by device:"))
            for device, count in self.stats['i2c_errors'].items():
                print(f"  {device}: {count} errors")
                
        if self.stats['failed_positions']:
            print(ColoredOutput.error(f"\nFailed at {len(self.stats['failed_positions'])} position(s):"))
            for failure in self.stats['failed_positions']:
                print(f"\n  Time: {failure['time']}")
                print(f"  Device: {failure['device']}")
                print(f"  Position: B:{failure['position']['base']}° "
                      f"S:{failure['position']['shoulder']}° "
                      f"E:{failure['position']['elbow']}° "
                      f"W:{failure['position']['wrist']}° "
                      f"R:{failure['position']['roll']}° "
                      f"H:{failure['position']['hand']}°")
                print(f"  Error: {failure['error'][:80]}")
        else:
            print(ColoredOutput.success("\n✓ No I2C failures detected!"))
            
        # Return to safe position if using motors
        if self.use_real_motors and self.serial_port:
            print(ColoredOutput.info("\nReturning to safe position..."))
            try:
                self.send_motor_command({"T": 122, "b": 0, "s": 0, "e": 90, "t": 90, "r": -86, "h": 90, "spd": 20, "acc": 10})
                time.sleep(1)
            except:
                pass
                
        print(ColoredOutput.info("\nTest completed."))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='I2C Position Sweep Test')
    parser.add_argument('--real-motors', action='store_true', 
                        help='Use real motor commands (WARNING: Robot will move through many positions!)')
    args = parser.parse_args()
    
    test = I2CPositionSweepTest(use_real_motors=args.real_motors)
    test.run()