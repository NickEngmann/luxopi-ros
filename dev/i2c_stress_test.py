#!/usr/bin/env python3
"""
I2C Stress Test Script
Tests all I2C devices continuously to identify if crashes are hardware-related
or caused by the ROS2 system integration.
"""

import board
import time
import threading
import datetime
from collections import defaultdict
from adafruit_apds9960.apds9960 import APDS9960
import adafruit_vl53l4cd
import adafruit_ads7830.ads7830 as ADC
from adafruit_ads7830.analog_in import AnalogIn
import sys
import signal

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

class I2CStressTest:
    def __init__(self):
        self.running = True
        self.i2c_bus = board.I2C()
        self.i2c_lock = threading.Lock()
        
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
            'global': defaultdict(int)
        }
        
        # Error tracking
        self.consecutive_errors = defaultdict(int)
        self.last_success_time = defaultdict(lambda: None)
        self.last_read_values = {}  # Store last read values for display
        self.start_time = time.time()
        
        # Configuration
        self.poll_interval = 0.2  # 5Hz like the i2c_device_manager
        self.display_interval = 5.0  # Update display every 5 seconds
        self.recovery_interval = 3.0  # Try recovery every 3 seconds
        
        # Setup signal handler for clean exit
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print(ColoredOutput.info("=== I2C Stress Test Starting ==="))
        print(f"Poll rate: {1.0/self.poll_interval:.1f} Hz")
        print(f"Recovery interval: {self.recovery_interval}s")
        print(f"Display update: {self.display_interval}s")
        print(ColoredOutput.info("Press Ctrl+C to stop\n"))
        
    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print(ColoredOutput.warning("\n\nShutting down..."))
        self.running = False
        
    def initialize_devices(self):
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
                self.stats['apds9960']['initialized'] += 1
                print(ColoredOutput.success("✓ APDS9960 initialized"))
            except Exception as e:
                self.stats['apds9960']['init_errors'] += 1
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
                self.stats['vl53_left']['initialized'] += 1
                print(ColoredOutput.success("✓ VL53L4CD Left (0x29) initialized"))
            except Exception as e:
                self.stats['vl53_left']['init_errors'] += 1
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
                self.stats['vl53_right']['initialized'] += 1
                print(ColoredOutput.success("✓ VL53L4CD Right (0x59) initialized"))
            except Exception as e:
                self.stats['vl53_right']['init_errors'] += 1
                print(ColoredOutput.error(f"✗ VL53L4CD Right init failed: {e}"))
                
        # ADS7830
        if not self.ads7830:
            try:
                with self.i2c_lock:
                    self.ads7830 = ADC.ADS7830(self.i2c_bus, 0x38)
                    # Create analog channels
                    self.ads7830_channels = {
                        0: AnalogIn(self.ads7830, 0),  # head_top
                        1: AnalogIn(self.ads7830, 1),  # head_left
                        2: AnalogIn(self.ads7830, 2),  # head_bottom
                        3: AnalogIn(self.ads7830, 3),  # head_right
                    }
                    time.sleep(0.05)
                self.stats['ads7830']['initialized'] += 1
                print(ColoredOutput.success("✓ ADS7830 (0x38) initialized"))
            except Exception as e:
                self.stats['ads7830']['init_errors'] += 1
                print(ColoredOutput.error(f"✗ ADS7830 init failed: {e}"))
                
        print("")
        
        # Quick test read to show initial values
        print(ColoredOutput.info("Testing initial sensor readings..."))
        self._test_initial_readings()
        
    def _test_initial_readings(self):
        """Test read all sensors once to verify they're working"""
        print("")
        
        # Test APDS9960
        if self.apds9960:
            try:
                value = self.read_apds9960()
                if value is not None:
                    print(ColoredOutput.success(f"  APDS9960 proximity: {value} (0-255 range, higher=closer)"))
                else:
                    print(ColoredOutput.warning("  APDS9960: No data"))
            except Exception as e:
                print(ColoredOutput.error(f"  APDS9960 error: {e}"))
                
        # Test VL53 Left
        if self.vl53_left:
            try:
                value = self.read_vl53_left()
                if value is not None:
                    print(ColoredOutput.success(f"  VL53L4CD Left distance: {value:.1f}cm"))
                else:
                    print(ColoredOutput.warning("  VL53L4CD Left: No data (normal on first read)"))
            except Exception as e:
                print(ColoredOutput.error(f"  VL53L4CD Left error: {e}"))
                
        # Test VL53 Right
        if self.vl53_right:
            try:
                value = self.read_vl53_right()
                if value is not None:
                    print(ColoredOutput.success(f"  VL53L4CD Right distance: {value:.1f}cm"))
                else:
                    print(ColoredOutput.warning("  VL53L4CD Right: No data (normal on first read)"))
            except Exception as e:
                print(ColoredOutput.error(f"  VL53L4CD Right error: {e}"))
                
        # Test ADS7830
        if self.ads7830:
            try:
                value = self.read_ads7830()
                if value:
                    formatted = ', '.join([f"{k}:{v}" for k, v in value.items()])
                    print(ColoredOutput.success(f"  ADS7830 touch sensors: {formatted}"))
                    print(ColoredOutput.BLUE + "    (Higher values = less pressure, ~24000 = not touched)" + ColoredOutput.RESET)
                else:
                    print(ColoredOutput.warning("  ADS7830: No data"))
            except Exception as e:
                print(ColoredOutput.error(f"  ADS7830 error: {e}"))
                
        print("")
        
    def poll_device(self, device_name, read_func):
        """Poll a single device and track statistics"""
        try:
            with self.i2c_lock:
                data = read_func()
                time.sleep(0.002)  # 2ms delay like i2c_device_manager
                
            if data is not None:
                self.stats[device_name]['successful_reads'] += 1
                self.stats[device_name]['total_reads'] += 1
                self.consecutive_errors[device_name] = 0
                self.last_success_time[device_name] = time.time()
                self.last_read_values[device_name] = data  # Store the actual value
                return True
            else:
                self.stats[device_name]['null_reads'] += 1
                self.stats[device_name]['total_reads'] += 1
                return False
                
        except Exception as e:
            self.stats[device_name]['read_errors'] += 1
            self.stats[device_name]['total_reads'] += 1
            self.consecutive_errors[device_name] += 1
            
            # Log first error or every 10th consecutive error
            if self.consecutive_errors[device_name] == 1 or self.consecutive_errors[device_name] % 10 == 0:
                timestamp = datetime.datetime.now().strftime('%H:%M:%S')
                print(ColoredOutput.error(f"[{timestamp}] {device_name} error #{self.consecutive_errors[device_name]}: {str(e)[:50]}"))
                
            return False
            
    def read_apds9960(self):
        """Read APDS9960 proximity"""
        if not self.apds9960:
            return None
        return self.apds9960.proximity
        
    def read_vl53_left(self):
        """Read left distance sensor"""
        if not self.vl53_left:
            return None
        if self.vl53_left.data_ready:
            distance = self.vl53_left.distance
            self.vl53_left.clear_interrupt()
            return distance if 0 < distance <= 400 else None
        return None
        
    def read_vl53_right(self):
        """Read right distance sensor"""
        if not self.vl53_right:
            return None
        if self.vl53_right.data_ready:
            distance = self.vl53_right.distance
            self.vl53_right.clear_interrupt()
            return distance if 0 < distance <= 400 else None
        return None
        
    def read_ads7830(self):
        """Read all ADS7830 channels"""
        if not self.ads7830 or not hasattr(self, 'ads7830_channels'):
            return None
        
        channel_names = {0: 'top', 1: 'left', 2: 'bottom', 3: 'right'}
        data = {}
        for channel, analog_in in self.ads7830_channels.items():
            try:
                value = analog_in.value
                name = channel_names.get(channel, f'ch{channel}')
                data[name] = value
            except:
                pass
                
        return data if data else None
        
    def check_bus_health(self):
        """Check if I2C bus appears to be locked up"""
        devices_failed = sum(1 for d in ['apds9960', 'vl53_left', 'vl53_right', 'ads7830'] 
                           if self.consecutive_errors[d] >= 5)
        
        if devices_failed >= 3:
            self.stats['global']['bus_lockups'] += 1
            print(ColoredOutput.error(f"\n!!! I2C BUS LOCKUP DETECTED !!! ({devices_failed}/4 devices failing)"))
            return False
        return True
        
    def attempt_recovery(self, device_name):
        """Attempt to recover a failed device"""
        print(ColoredOutput.warning(f"Attempting recovery for {device_name}..."))
        
        # Mark device as uninitialized to trigger reinitialization
        if device_name == 'apds9960':
            self.apds9960 = None
        elif device_name == 'vl53_left':
            self.vl53_left = None
        elif device_name == 'vl53_right':
            self.vl53_right = None
        elif device_name == 'ads7830':
            self.ads7830 = None
            
        # Reinitialize
        self.initialize_devices()
        
    def display_statistics(self):
        """Display current statistics"""
        runtime = time.time() - self.start_time
        hours = runtime / 3600
        
        print(ColoredOutput.info("\n=== I2C Stress Test Statistics ==="))
        print(f"Runtime: {hours:.2f} hours ({runtime:.0f} seconds)")
        print(f"Bus lockups detected: {self.stats['global']['bus_lockups']}")
        
        for device in ['apds9960', 'vl53_left', 'vl53_right', 'ads7830']:
            total = self.stats[device]['total_reads']
            successful = self.stats[device]['successful_reads']
            errors = self.stats[device]['read_errors']
            null_reads = self.stats[device]['null_reads']
            init_count = self.stats[device]['initialized']
            init_errors = self.stats[device]['init_errors']
            
            if total > 0:
                success_rate = (successful / total) * 100
                error_rate = (errors / total) * 100
            else:
                success_rate = 0
                error_rate = 0
                
            status = "✓" if self.consecutive_errors[device] == 0 else "✗"
            color = ColoredOutput.success if self.consecutive_errors[device] == 0 else ColoredOutput.error
            
            print(f"\n{color(f'{status} {device}:')}")
            print(f"  Reads: {total:,} (Success: {successful:,} [{success_rate:.1f}%], Errors: {errors:,} [{error_rate:.1f}%], Null: {null_reads:,})")
            print(f"  Initializations: {init_count} (Errors: {init_errors})")
            print(f"  Consecutive errors: {self.consecutive_errors[device]}")
            
            if self.last_success_time[device]:
                time_since = time.time() - self.last_success_time[device]
                print(f"  Last success: {time_since:.1f}s ago")
                
            # Display last read values
            if device in self.last_read_values and self.last_read_values[device] is not None:
                value = self.last_read_values[device]
                if device == 'apds9960':
                    print(f"  {ColoredOutput.MAGENTA}Proximity: {value} (0-255 range){ColoredOutput.RESET}")
                elif device.startswith('vl53'):
                    print(f"  {ColoredOutput.MAGENTA}Distance: {value:.1f}cm{ColoredOutput.RESET}")
                elif device == 'ads7830':
                    formatted = ', '.join([f"{k}:{v}" for k, v in value.items()])
                    print(f"  {ColoredOutput.MAGENTA}Touch sensors: {formatted}{ColoredOutput.RESET}")
                    print(f"  {ColoredOutput.BLUE}  (Higher values = less pressure, ~24000=not touched){ColoredOutput.RESET}")
                
    def polling_thread(self):
        """Main polling thread"""
        while self.running:
            # Poll each device
            if self.apds9960:
                self.poll_device('apds9960', self.read_apds9960)
                
            if self.vl53_left:
                self.poll_device('vl53_left', self.read_vl53_left)
                
            if self.vl53_right:
                self.poll_device('vl53_right', self.read_vl53_right)
                
            if self.ads7830:
                self.poll_device('ads7830', self.read_ads7830)
                
            # Check bus health
            self.check_bus_health()
            
            # Sleep for poll interval
            time.sleep(self.poll_interval)
            
    def recovery_thread(self):
        """Recovery thread that attempts to recover failed devices"""
        while self.running:
            time.sleep(self.recovery_interval)
            
            # Check for devices that need recovery
            for device in ['apds9960', 'vl53_left', 'vl53_right', 'ads7830']:
                if self.consecutive_errors[device] >= 5:
                    self.attempt_recovery(device)
                    
    def display_thread(self):
        """Display thread that shows statistics periodically"""
        while self.running:
            time.sleep(self.display_interval)
            if self.running:  # Check again after sleep
                self.display_statistics()
                
    def run(self):
        """Run the stress test"""
        # Initialize devices
        self.initialize_devices()
        
        # Start threads
        threads = [
            threading.Thread(target=self.polling_thread, daemon=True),
            threading.Thread(target=self.recovery_thread, daemon=True),
            threading.Thread(target=self.display_thread, daemon=True)
        ]
        
        for thread in threads:
            thread.start()
            
        # Wait for shutdown
        try:
            while self.running:
                time.sleep(0.1)
        except:
            pass
            
        # Final statistics
        print(ColoredOutput.info("\n\n=== FINAL STATISTICS ==="))
        self.display_statistics()
        
        # Summary
        total_errors = sum(self.stats[d]['read_errors'] for d in ['apds9960', 'vl53_left', 'vl53_right', 'ads7830'])
        total_reads = sum(self.stats[d]['total_reads'] for d in ['apds9960', 'vl53_left', 'vl53_right', 'ads7830'])
        
        if total_reads > 0:
            overall_error_rate = (total_errors / total_reads) * 100
            print(f"\nOverall error rate: {overall_error_rate:.2f}% ({total_errors:,} errors in {total_reads:,} reads)")
            
        print(ColoredOutput.info("\nTest completed."))

if __name__ == "__main__":
    test = I2CStressTest()
    test.run()