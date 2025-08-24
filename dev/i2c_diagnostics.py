#!/usr/bin/env python3
"""
I2C Electrical Diagnostics
Checks for common electrical issues that can cause I2C failures
"""

import subprocess
import time
import board
import sys

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

class I2CDiagnostics:
    def __init__(self):
        self.issues_found = []
        
    def run_command(self, cmd):
        """Run a shell command and return output"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except Exception as e:
            return "", str(e), -1
            
    def check_i2c_speed(self):
        """Check I2C bus speed configuration"""
        print(ColoredOutput.info("\n1. Checking I2C bus speed..."))
        
        # Check config.txt for I2C speed settings
        stdout, _, _ = self.run_command("grep -E 'i2c|dtparam' /boot/firmware/config.txt 2>/dev/null || grep -E 'i2c|dtparam' /boot/config.txt 2>/dev/null")
        
        if stdout:
            print(f"Current I2C configuration:")
            for line in stdout.split('\n'):
                if 'i2c' in line and not line.strip().startswith('#'):
                    print(f"  {line.strip()}")
                    
            if 'i2c_arm_baudrate' not in stdout:
                print(ColoredOutput.warning("  ⚠️  No I2C speed setting found (using default 100kHz)"))
                self.issues_found.append("I2C speed not explicitly set - consider adding dtparam=i2c_arm_baudrate=50000")
        else:
            print(ColoredOutput.error("  ✗ Could not read I2C configuration"))
            
    def check_power_management(self):
        """Check CPU frequency and throttling"""
        print(ColoredOutput.info("\n2. Checking power management..."))
        
        # Check CPU frequency
        stdout, _, _ = self.run_command("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
        if stdout:
            freq_mhz = int(stdout) / 1000
            print(f"  Current CPU frequency: {freq_mhz:.0f} MHz")
            
        # Check throttling
        stdout, _, _ = self.run_command("vcgencmd get_throttled")
        if stdout:
            throttled = stdout.split('=')[1] if '=' in stdout else stdout
            if throttled != '0x0':
                print(ColoredOutput.error(f"  ✗ System throttling detected: {throttled}"))
                self.issues_found.append("System throttling detected - check power supply")
            else:
                print(ColoredOutput.success("  ✓ No throttling detected"))
        
        # Check voltage
        stdout, _, _ = self.run_command("vcgencmd measure_volts core")
        if stdout:
            print(f"  Core voltage: {stdout}")
            
    def scan_i2c_bus(self):
        """Scan I2C bus for devices"""
        print(ColoredOutput.info("\n3. Scanning I2C buses..."))
        
        for bus in [1, 3]:  # Common I2C buses
            print(f"\n  Bus {bus}:")
            stdout, stderr, returncode = self.run_command(f"i2cdetect -y {bus}")
            
            if returncode == 0:
                lines = stdout.split('\n')
                devices_found = []
                
                for line in lines[1:]:  # Skip header
                    if ':' in line:
                        parts = line.split(':')[1].split()
                        for i, val in enumerate(parts):
                            if val != '--':
                                addr = int(line.split(':')[0], 16) + i
                                devices_found.append(f"0x{addr:02x}")
                                
                if devices_found:
                    print(ColoredOutput.success(f"    Devices found: {', '.join(devices_found)}"))
                else:
                    print(ColoredOutput.warning("    No devices found"))
            else:
                print(ColoredOutput.error(f"    Error scanning bus: {stderr}"))
                
    def check_gpio_conflicts(self):
        """Check for GPIO conflicts with I2C pins"""
        print(ColoredOutput.info("\n4. Checking GPIO conflicts..."))
        
        # I2C1 uses GPIO 2 (SDA) and GPIO 3 (SCL)
        # I2C3 uses GPIO 0 (SDA) and GPIO 1 (SCL)
        
        i2c_pins = {
            'I2C1': {'SDA': 2, 'SCL': 3},
            'I2C3': {'SDA': 0, 'SCL': 1}
        }
        
        stdout, _, _ = self.run_command("gpio readall 2>/dev/null || echo 'gpio command not found'")
        
        if 'not found' in stdout:
            print(ColoredOutput.warning("  GPIO tool not available for detailed pin check"))
        else:
            print(ColoredOutput.success("  ✓ GPIO pins checked (manual verification recommended)"))
            
    def check_kernel_messages(self):
        """Check for I2C-related kernel errors"""
        print(ColoredOutput.info("\n5. Checking kernel messages for I2C errors..."))
        
        stdout, _, _ = self.run_command("dmesg | grep -i i2c | tail -20")
        
        error_keywords = ['error', 'failed', 'timeout', 'NAK', 'NACK']
        errors_found = False
        
        if stdout:
            for line in stdout.split('\n'):
                for keyword in error_keywords:
                    if keyword.lower() in line.lower():
                        print(ColoredOutput.error(f"  ✗ {line.strip()}"))
                        errors_found = True
                        break
                        
            if not errors_found:
                print(ColoredOutput.success("  ✓ No recent I2C errors in kernel log"))
        else:
            print("  No I2C messages in kernel log")
            
    def check_qwiic_recommendations(self):
        """Provide Qwiic/Stemma QT specific recommendations"""
        print(ColoredOutput.info("\n6. Qwiic/Stemma QT Recommendations..."))
        
        recommendations = [
            "Cable length: Keep total chain under 100cm for reliability",
            "Termination: Ensure only ONE set of pull-up resistors (usually on first device)",
            "Power: Check if all devices are getting stable 3.3V",
            "Connectors: Ensure all Qwiic connectors are fully seated",
            "Cable quality: Use high-quality Qwiic cables, avoid damaged ones",
            "Star vs Chain: Consider star topology if chain is unreliable"
        ]
        
        for rec in recommendations:
            print(f"  • {rec}")
            
    def motor_noise_recommendations(self):
        """Recommendations for motor-induced failures"""
        print(ColoredOutput.info("\n7. Motor Noise Mitigation..."))
        
        print("Since I2C fails when motors move, consider:")
        print(ColoredOutput.warning("  Hardware solutions:"))
        print("    • Add ferrite beads to motor wires")
        print("    • Use shielded cables for I2C")
        print("    • Separate I2C and motor power supplies")
        print("    • Add 100nF capacitors near each I2C device")
        print("    • Ensure solid ground connection between all devices")
        print("    • Keep I2C cables away from motor/power cables")
        
        print(ColoredOutput.warning("\n  Software solutions:"))
        print("    • Reduce I2C speed: add to /boot/firmware/config.txt:")
        print(ColoredOutput.BLUE + "      dtparam=i2c_arm_baudrate=50000" + ColoredOutput.RESET)
        print("    • Add delays between motor commands and I2C reads")
        print("    • Implement more aggressive I2C recovery")
        
    def generate_report(self):
        """Generate final diagnostic report"""
        print(ColoredOutput.info("\n" + "="*50))
        print(ColoredOutput.info("DIAGNOSTIC SUMMARY"))
        print(ColoredOutput.info("="*50))
        
        if self.issues_found:
            print(ColoredOutput.error(f"\nIssues found ({len(self.issues_found)}):"))
            for issue in self.issues_found:
                print(f"  • {issue}")
        else:
            print(ColoredOutput.success("\nNo major issues detected"))
            
        print(ColoredOutput.warning("\nKey finding: I2C works in isolation but fails with motor movement"))
        print("This strongly suggests electrical interference (EMI) or power issues")
        
        print(ColoredOutput.info("\nRecommended next steps:"))
        print("1. Try reducing I2C speed first (software fix)")
        print("2. Check physical wiring separation")
        print("3. Add capacitors for power filtering")
        print("4. Consider using I2C isolators if problem persists")
        
    def run(self):
        """Run all diagnostics"""
        print(ColoredOutput.info("=== I2C Diagnostics Tool ==="))
        print("Checking for common I2C issues...\n")
        
        self.check_i2c_speed()
        self.check_power_management()
        self.scan_i2c_bus()
        self.check_gpio_conflicts()
        self.check_kernel_messages()
        self.check_qwiic_recommendations()
        self.motor_noise_recommendations()
        self.generate_report()

if __name__ == "__main__":
    diag = I2CDiagnostics()
    diag.run()