#!/usr/bin/env python3
"""
Animation Recording Tool for LuxoPi RoArm-M3

This tool allows you to manually position the robot arm and record keyframes
for creating new animations. It operates in DEMA (full compliance) mode so you
can physically move the arm to desired positions.

Usage:
    python3 animation_recorder.py [--port /dev/ttyAMA0]
    python3 animation_recorder.py --preview animation.json
    python3 animation_recorder.py --preview animation.py
"""

import serial
import json
import time
import threading
import sys
import select
import termios
import tty
import argparse
import math
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Import speed adjustment functionality
from adjust_animation_speed import (
    PRESETS,
    parse_acceleration_range,
    adjust_animation_speed as apply_speed_adjustment
)


class AnimationRecorder:
    """Interactive animation recording tool for RoArm-M3."""

    def __init__(self, port: str = '/dev/ttyAMA0', baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.running = False
        self.read_thread: Optional[threading.Thread] = None

        # Current robot position (updated from serial feedback)
        self.current_position = {
            'base': 0.0,
            'shoulder': 0.0,
            'elbow': 0.0,
            'wrist': 0.0,
            'hand': 0.0
        }
        self.position_lock = threading.Lock()
        self.position_updated = False

        # Animation recording
        self.keyframes: List[Dict] = []
        self.animation_name = ""
        self.recording_mode = False

        # Terminal settings
        self.old_settings = None

    def connect(self) -> bool:
        """Connect to the robot via serial."""
        try:
            print(f"Connecting to {self.port} at {self.baudrate} baud...")
            self.ser = serial.Serial(
                self.port,
                baudrate=self.baudrate,
                timeout=0.1,
                dsrdtr=None
            )
            self.ser.setRTS(False)
            self.ser.setDTR(False)

            print("✓ Connected successfully")
            return True

        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def start_read_thread(self):
        """Start background thread to read serial data."""
        self.running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        print("✓ Serial read thread started")

    def _read_loop(self):
        """Background thread to read and process serial data."""
        while self.running:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        self._process_response(line)
                else:
                    time.sleep(0.01)  # Small delay to prevent CPU spinning

            except Exception as e:
                print(f"\nError reading serial: {e}")
                time.sleep(0.1)

    def _process_response(self, response: str):
        """Process JSON response from robot."""
        try:
            data = json.loads(response)

            # Check for position feedback (T:1051) - positions are in RADIANS
            if isinstance(data, dict) and data.get('T') == 1051:
                with self.position_lock:
                    # Store positions in RADIANS (as received from robot)
                    self.current_position['base'] = data.get('b', 0.0)
                    self.current_position['shoulder'] = data.get('s', 0.0)
                    self.current_position['elbow'] = data.get('e', 0.0)
                    self.current_position['wrist'] = data.get('t', 0.0)
                    self.current_position['hand'] = data.get('g', 0.0)
                    self.position_updated = True

            # Debug: print other responses
            elif isinstance(data, dict):
                print(f"\nReceived: {response}")

        except json.JSONDecodeError:
            # Not JSON, might be status message
            if response.strip():
                print(f"\nStatus: {response}")

    def send_command(self, cmd: Dict) -> bool:
        """Send JSON command to robot."""
        try:
            cmd_str = json.dumps(cmd) + '\n'
            self.ser.write(cmd_str.encode('utf-8'))
            return True
        except Exception as e:
            print(f"Error sending command: {e}")
            return False

    def enable_full_dema(self):
        """Enable full DEMA mode (all joints fully compliant)."""
        print("\nEnabling full DEMA mode (robot will be limp)...")
        cmd = {
            'T': 112,
            'mode': 1,
            'b': 0,     # base - full compliance
            's': 0,     # shoulder - full compliance
            'e': 0,     # elbow - full compliance
            't': 0,     # wrist - full compliance
            'r': 0,     # roll - full compliance
            'h': 0      # hand - full compliance
        }

        if self.send_command(cmd):
            print("✓ Full DEMA enabled - you can now move the robot freely")
            return True
        return False

    def disable_dema(self):
        """Disable DEMA mode (restore normal torque)."""
        print("\nDisabling DEMA mode (restoring normal torque)...")
        cmd = {
            'T': 112,
            'mode': 1,
            'b': 1000,
            's': 1000,
            'e': 1000,
            't': 1000,
            'r': 1000,
            'h': 1000
        }

        if self.send_command(cmd):
            print("✓ DEMA disabled - robot has normal torque")
            return True
        return False

    def get_current_position(self) -> Dict:
        """Get current robot position (thread-safe) in RADIANS."""
        with self.position_lock:
            return self.current_position.copy()

    def wait_for_fresh_position(self, timeout: float = 5.0) -> Dict:
        """
        Wait for a fresh position update from the robot.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Fresh position dict, or current position if timeout
        """
        # Clear the position_updated flag
        with self.position_lock:
            self.position_updated = False

        start_time = time.time()
        print("  Waiting for fresh position update", end='', flush=True)

        # Wait for new position
        while (time.time() - start_time) < timeout:
            with self.position_lock:
                if self.position_updated:
                    print(" ✓")
                    return self.current_position.copy()

            # Print progress dots
            if int((time.time() - start_time) * 2) % 2 == 0:
                print(".", end='', flush=True)
            time.sleep(0.1)

        # Timeout - return current position anyway
        print(" (timeout, using current)")
        with self.position_lock:
            return self.current_position.copy()

    @staticmethod
    def rad_to_deg(radians: float) -> float:
        """Convert radians to degrees."""
        return radians * 180.0 / math.pi

    @staticmethod
    def deg_to_rad(degrees: float) -> float:
        """Convert degrees to radians."""
        return degrees * math.pi / 180.0

    def calculate_duration_from_previous(self, new_position: Dict, base_speed: float = 2.0) -> float:
        """
        Calculate realistic duration based on movement from previous keyframe.

        Args:
            new_position: New position dict
            base_speed: Base speed in radians/second (default: 2.0)

        Returns:
            Estimated duration in seconds
        """
        if not self.keyframes:
            return 0.5  # First keyframe - no previous movement

        prev_servos = self.keyframes[-1]['servos']

        # Calculate total angular distance
        distance = 0.0
        distance += abs(new_position['base'] - prev_servos.get('base', 0))
        distance += abs(new_position['shoulder'] - prev_servos.get('shoulder', 0))
        distance += abs(new_position['elbow'] - prev_servos.get('elbow', 0))
        distance += abs(new_position['wrist'] - prev_servos.get('wrist', 0))
        distance += abs(new_position['hand'] - prev_servos.get('hand', 0))

        # Calculate time based on distance and speed
        # Minimum duration of 0.3s for very small movements
        duration = max(0.3, distance / base_speed)

        return round(duration, 2)

    def record_keyframe(self):
        """Record current position as a keyframe (stored in RADIANS)."""
        # Wait for fresh position to ensure we capture the actual current position
        position = self.wait_for_fresh_position(timeout=3.0)

        # Calculate realistic duration based on movement from previous keyframe
        duration = self.calculate_duration_from_previous(position)

        # Store keyframe in RADIANS (as received from robot)
        keyframe = {
            'servos': {
                'base': position['base'],
                'shoulder': position['shoulder'],
                'elbow': position['elbow'],
                'wrist': position['wrist'],
                'hand': position['hand'],
                'roll': -1.5,  # Default roll value
                'spd': 0,      # Speed (0 for default)
                'acc': 10.0    # Acceleration
            },
            'timing': 1.0,  # Default timing multiplier
            'duration': duration  # Calculated based on movement
        }

        self.keyframes.append(keyframe)

        # Display in degrees for readability
        # Note: Terminal should be in normal mode when this is called
        print(f"✓ Keyframe {len(self.keyframes)} recorded (duration: {duration:.2f}s):")
        print(f"  Base:     {self.rad_to_deg(position['base']):7.2f}° ({position['base']:.4f} rad)")
        print(f"  Shoulder: {self.rad_to_deg(position['shoulder']):7.2f}° ({position['shoulder']:.4f} rad)")
        print(f"  Elbow:    {self.rad_to_deg(position['elbow']):7.2f}° ({position['elbow']:.4f} rad)")
        print(f"  Wrist:    {self.rad_to_deg(position['wrist']):7.2f}° ({position['wrist']:.4f} rad)")
        print(f"  Hand:     {self.rad_to_deg(position['hand']):7.2f}° ({position['hand']:.4f} rad)")
        sys.stdout.flush()  # Force flush output

    def move_to_position(self, keyframe: Dict):
        """Move robot to a specific keyframe position using T:102 format."""
        servos = keyframe['servos']

        # Use T:102 command format (same as hardware_interface.py)
        # All positions must be in RADIANS
        cmd = {
            'T': 102,
            'base': servos.get('base', 0.0),
            'shoulder': servos.get('shoulder', 0.0),
            'elbow': servos.get('elbow', 0.0),
            'wrist': servos.get('wrist', 0.0),
            'roll': servos.get('roll', -1.5),
            'hand': servos.get('hand', 0.0),
            'spd': servos.get('spd', 0),
            'acc': servos.get('acc', 10.0)
        }

        return self.send_command(cmd)

    def wait_for_position(self, target_keyframe: Dict, tolerance_deg: float = 7.5, timeout: float = 8.0) -> tuple:
        """
        Wait until robot reaches target position within tolerance.

        Args:
            target_keyframe: Target keyframe with servos dict (in RADIANS)
            tolerance_deg: Acceptable position error in degrees (default: 7.5)
            timeout: Maximum time to wait in seconds (default: 30.0)

        Returns:
            Tuple of (success: bool, current_position: Dict)
            - success: True if position reached within tolerance, False if timeout
            - current_position: Actual robot position at end of wait
        """
        target = target_keyframe['servos']
        tolerance_rad = self.deg_to_rad(tolerance_deg)
        start_time = time.time()

        # Print target positions
        print(f"\n    Target position:")
        print(f"      Base:     {self.rad_to_deg(target.get('base', 0)):7.2f}° ({target.get('base', 0):.4f} rad)")
        print(f"      Shoulder: {self.rad_to_deg(target.get('shoulder', 0)):7.2f}° ({target.get('shoulder', 0):.4f} rad)")
        print(f"      Elbow:    {self.rad_to_deg(target.get('elbow', 0)):7.2f}° ({target.get('elbow', 0):.4f} rad)")
        print(f"      Wrist:    {self.rad_to_deg(target.get('wrist', 0)):7.2f}° ({target.get('wrist', 0):.4f} rad)")
        print(f"      Hand:     {self.rad_to_deg(target.get('hand', 0)):7.2f}° ({target.get('hand', 0):.4f} rad)")

        print(f"\n    Waiting for position (tolerance: ±{tolerance_deg:.1f}°)...", end='', flush=True)

        while (time.time() - start_time) < timeout:
            with self.position_lock:
                current = self.current_position.copy()

            # Calculate errors in radians
            errors_rad = {
                'base': abs(current['base'] - target.get('base', 0)),
                'shoulder': abs(current['shoulder'] - target.get('shoulder', 0)),
                'elbow': abs(current['elbow'] - target.get('elbow', 0)),
                'wrist': abs(current['wrist'] - target.get('wrist', 0)),
                'hand': abs(current['hand'] - target.get('hand', 0))
            }

            # Convert to degrees for display
            errors_deg = {k: self.rad_to_deg(v) for k, v in errors_rad.items()}

            # Calculate max error EXCLUDING hand (hand doesn't need to be exact)
            structural_joints = ['base', 'shoulder', 'elbow', 'wrist']
            max_error_rad = max(errors_rad[joint] for joint in structural_joints)
            max_error_deg = self.rad_to_deg(max_error_rad)

            if max_error_rad <= tolerance_rad:
                print(f" ✓ Reached (max error: {max_error_deg:.2f}°)")
                print(f"\n    Current position:")
                print(f"      Base:     {self.rad_to_deg(current['base']):7.2f}° ({current['base']:.4f} rad)")
                print(f"      Shoulder: {self.rad_to_deg(current['shoulder']):7.2f}° ({current['shoulder']:.4f} rad)")
                print(f"      Elbow:    {self.rad_to_deg(current['elbow']):7.2f}° ({current['elbow']:.4f} rad)")
                print(f"      Wrist:    {self.rad_to_deg(current['wrist']):7.2f}° ({current['wrist']:.4f} rad)")
                print(f"      Hand:     {self.rad_to_deg(current['hand']):7.2f}° ({current['hand']:.4f} rad)")
                return (True, current)

            # Small delay before checking again
            time.sleep(0.1)

        # Timeout - print final errors and current position
        print(f" ✗ Timeout (max error: {max_error_deg:.2f}°)")
        print(f"\n    Current position:")
        print(f"      Base:     {self.rad_to_deg(current['base']):7.2f}° ({current['base']:.4f} rad) [error: {errors_deg['base']:6.2f}°]")
        print(f"      Shoulder: {self.rad_to_deg(current['shoulder']):7.2f}° ({current['shoulder']:.4f} rad) [error: {errors_deg['shoulder']:6.2f}°]")
        print(f"      Elbow:    {self.rad_to_deg(current['elbow']):7.2f}° ({current['elbow']:.4f} rad) [error: {errors_deg['elbow']:6.2f}°]")
        print(f"      Wrist:    {self.rad_to_deg(current['wrist']):7.2f}° ({current['wrist']:.4f} rad) [error: {errors_deg['wrist']:6.2f}°]")
        print(f"      Hand:     {self.rad_to_deg(current['hand']):7.2f}° ({current['hand']:.4f} rad) [error: {errors_deg['hand']:6.2f}°]")
        return (False, current)

    def replay_animation(self, skip_dema_prompt: bool = False):
        """
        Replay the recorded animation.

        Args:
            skip_dema_prompt: If True, don't ask about re-enabling DEMA at the end
        """
        if not self.keyframes:
            print("\n✗ No keyframes to replay")
            return

        print(f"▶ Replaying animation with {len(self.keyframes)} keyframes...")

        # Disable DEMA for controlled playback
        print("\n  Disabling DEMA for playback...")
        self.disable_dema()
        time.sleep(1)

        # Play through keyframes
        print("\n  Playing keyframes...")
        for i, keyframe in enumerate(self.keyframes):
            print(f"\n  → Keyframe {i+1}/{len(self.keyframes)}")

            # Send movement command
            self.move_to_position(keyframe)

            # Wait for robot to reach position
            success, actual_position = self.wait_for_position(keyframe, tolerance_deg=7.5, timeout=8.0)

            if not success:
                # Robot didn't reach target - update keyframe with actual position
                print("    ⚙️  Updating keyframe with actual reached position...")
                keyframe['servos']['base'] = actual_position['base']
                keyframe['servos']['shoulder'] = actual_position['shoulder']
                keyframe['servos']['elbow'] = actual_position['elbow']
                keyframe['servos']['wrist'] = actual_position['wrist']
                keyframe['servos']['hand'] = actual_position['hand']
                print(f"    ✓ Keyframe {i+1} updated to actual position")

            # Wait for keyframe duration
            duration = keyframe.get('duration', 0.5)
            if duration > 0:
                print(f"    Holding for {duration:.1f}s...")
                time.sleep(duration)

        print("\n✓ Playback complete")

        # Ask if user wants to re-enable DEMA (unless skipped)
        if not skip_dema_prompt:
            print("\nRe-enable DEMA mode? (y/n): ", end='', flush=True)
            response = input().strip().lower()
            if response == 'y':
                self.enable_full_dema()

    def edit_animation(self):
        """Edit animation keyframes."""
        if not self.keyframes:
            print("\n✗ No keyframes to edit")
            return

        while True:
            print("\n" + "="*60)
            print("EDIT ANIMATION")
            print("="*60)

            # List keyframes
            for i, kf in enumerate(self.keyframes):
                servos = kf['servos']
                print(f"\n{i+1}. Keyframe {i+1}:")
                print(f"   Base={self.rad_to_deg(servos.get('base', 0)):7.2f}° "
                      f"Shoulder={self.rad_to_deg(servos.get('shoulder', 0)):7.2f}° "
                      f"Elbow={self.rad_to_deg(servos.get('elbow', 0)):7.2f}°")
                print(f"   Wrist={self.rad_to_deg(servos.get('wrist', 0)):7.2f}° "
                      f"Hand={self.rad_to_deg(servos.get('hand', 0)):7.2f}°")
                print(f"   Duration: {kf['duration']:.1f}s  Timing: {kf['timing']:.1f}x")

            print("\nOptions:")
            print("  [D]elete keyframe")
            print("  [T]iming - adjust duration/timing")
            print("  [R]eorder keyframes")
            print("  [B]ack to main menu")
            print("\nChoice: ", end='', flush=True)

            choice = input().strip().upper()

            if choice == 'D':
                self._delete_keyframe()
            elif choice == 'T':
                self._edit_timing()
            elif choice == 'R':
                self._reorder_keyframes()
            elif choice == 'B':
                break

    def _delete_keyframe(self):
        """Delete a keyframe by index."""
        try:
            idx = int(input("Enter keyframe number to delete: ")) - 1
            if 0 <= idx < len(self.keyframes):
                deleted = self.keyframes.pop(idx)
                print(f"✓ Deleted keyframe {idx+1}")
            else:
                print("✗ Invalid keyframe number")
        except ValueError:
            print("✗ Invalid input")

    def _edit_timing(self):
        """Edit timing for a keyframe."""
        try:
            idx = int(input("Enter keyframe number: ")) - 1
            if 0 <= idx < len(self.keyframes):
                print(f"\nCurrent duration: {self.keyframes[idx]['duration']:.1f}s")
                duration = float(input("New duration (seconds): "))
                self.keyframes[idx]['duration'] = duration

                print(f"Current timing multiplier: {self.keyframes[idx]['timing']:.1f}x")
                timing = float(input("New timing multiplier: "))
                self.keyframes[idx]['timing'] = timing

                print("✓ Timing updated")
            else:
                print("✗ Invalid keyframe number")
        except ValueError:
            print("✗ Invalid input")

    def _reorder_keyframes(self):
        """Reorder keyframes."""
        try:
            from_idx = int(input("Move keyframe number: ")) - 1
            to_idx = int(input("To position: ")) - 1

            if 0 <= from_idx < len(self.keyframes) and 0 <= to_idx < len(self.keyframes):
                kf = self.keyframes.pop(from_idx)
                self.keyframes.insert(to_idx, kf)
                print("✓ Keyframes reordered")
            else:
                print("✗ Invalid keyframe numbers")
        except ValueError:
            print("✗ Invalid input")

    def convert_json_to_python(self, json_filepath: Path) -> bool:
        """
        Convert JSON animation to Python using json_to_animation.py script.

        Args:
            json_filepath: Path to the JSON file to convert

        Returns:
            True if conversion successful, False otherwise
        """
        try:
            # Create python output directory
            python_dir = Path('./python')
            python_dir.mkdir(parents=True, exist_ok=True)

            # Get the json_to_animation.py script path (same directory as this script)
            script_dir = Path(__file__).parent
            converter_script = script_dir / 'json_to_animation.py'

            if not converter_script.exists():
                print(f"  ⚠ Warning: Converter script not found at {converter_script}")
                return False

            # Run the converter script
            print(f"\n  Converting to Python animation...")
            python_filename = f"{json_filepath.stem}.py"
            result = subprocess.run(
                [sys.executable, str(converter_script), str(json_filepath), '-o', str(python_dir / python_filename)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Extract output filename from the converter's output
                for line in result.stdout.split('\n'):
                    if 'written to:' in line:
                        print(f"  ✓ {line.strip()}")
                        return True
                print(f"  ✓ Python animation generated in {python_dir}")
                return True
            else:
                print(f"  ⚠ Conversion failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print(f"  ⚠ Conversion timed out")
            return False
        except Exception as e:
            print(f"  ⚠ Error during conversion: {e}")
            return False

    def save_animation(self):
        """Save animation to JSON file in animations/json/ folder and convert to Python."""
        if not self.keyframes:
            print("\n✗ No keyframes to save")
            return

        if not self.animation_name:
            print("\nEnter animation name: ", end='', flush=True)
            self.animation_name = input().strip()

        if not self.animation_name:
            print("✗ Animation name required")
            return

        # Create animation data structure
        animation_data = {
            'name': self.animation_name,
            'description': f'Animation created with recorder on {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            'category': 'custom',
            'created': datetime.now().isoformat(),
            'keyframes': self.keyframes,
            'keyframe_count': len(self.keyframes)
        }

        # Create animations/json directory if it doesn't exist
        output_dir = Path('./json')
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = f"animation_{self.animation_name.lower().replace(' ', '_')}.json"
        filepath = output_dir / filename

        # Save to file
        try:
            with open(filepath, 'w') as f:
                json.dump(animation_data, f, indent=2)
            print(f"\n✓ Animation saved to: {filepath}")

            # Automatically convert to Python
            self.convert_json_to_python(filepath)

        except Exception as e:
            print(f"\n✗ Error saving animation: {e}")

    def print_instructions(self):
        """Print recording instructions."""
        print("\n" + "="*60)
        print("ANIMATION RECORDING MODE")
        print("="*60)
        print("\nThe robot is now in DEMA mode - you can freely move it.")
        print("\nControls:")
        print("  [R] - Record current position as keyframe")
        print("  [F] - Finish recording")
        print("  [Q] - Quit without saving")
        print("\nMove the robot to your desired position and press 'R' to record.")
        print("="*60 + "\n")

    def recording_loop(self):
        """Main recording loop with single-key input."""
        self.recording_mode = True
        self.print_instructions()

        # Set terminal to raw mode for single-key input
        fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)

            while self.recording_mode:
                # Check for key press with timeout
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1).upper()

                    if key == 'R':
                        # Restore terminal temporarily for clean output
                        termios.tcsetattr(fd, termios.TCSADRAIN, self.old_settings)
                        # Clear the current line and start fresh
                        sys.stdout.write('\r' + ' ' * 80 + '\r\n')
                        sys.stdout.flush()
                        self.record_keyframe()
                        print("\nPress [R] to record, [F] to finish, [Q] to quit: ", end='', flush=True)
                        # Return to raw mode
                        tty.setraw(fd)

                    elif key == 'F':
                        # Restore terminal for clean output
                        termios.tcsetattr(fd, termios.TCSADRAIN, self.old_settings)
                        sys.stdout.write('\r' + ' ' * 80 + '\r\n')
                        sys.stdout.flush()
                        self.recording_mode = False
                        print("✓ Recording finished")

                    elif key == 'Q':
                        # Restore terminal for clean output
                        termios.tcsetattr(fd, termios.TCSADRAIN, self.old_settings)
                        sys.stdout.write('\r' + ' ' * 80 + '\r\n')
                        sys.stdout.flush()
                        if len(self.keyframes) > 0:
                            print("Quit without saving? This will discard all keyframes! (y/n): ", end='', flush=True)
                            response = input().strip().lower()

                            if response == 'y':
                                self.keyframes = []
                                self.recording_mode = False
                                print("✗ Recording cancelled")
                        else:
                            self.recording_mode = False
                            print("✗ Recording cancelled")

        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, self.old_settings)

    def post_recording_menu(self):
        """Menu after recording is finished."""
        while True:
            print("\n" + "="*60)
            print(f"ANIMATION: {len(self.keyframes)} keyframes recorded")
            print("="*60)
            print("\nWhat would you like to do?")
            print("  [P] - Preview/Replay animation")
            print("  [E] - Edit animation (step-through mode)")
            print("  [T] - Timing/Speed adjustments")
            print("  [N] - Name/rename animation")
            print("  [S] - Save animation")
            print("  [D] - Discard and start over")
            print("  [Q] - Quit")
            print("\nChoice: ", end='', flush=True)

            choice = input().strip().upper()

            if choice == 'P':
                self.replay_animation()
            elif choice == 'E':
                # Use full step-through editing mode
                self._step_through_editing_mode()
            elif choice == 'T':
                # Timing/Speed submenu
                print("\n" + "-"*60)
                print("TIMING/SPEED OPTIONS:")
                print("-"*60)
                print("  [1] - Edit individual keyframe durations")
                print("  [2] - Adjust overall animation speed (presets)")
                print("  [0] - Cancel")
                print("\nChoice: ", end='', flush=True)
                timing_choice = input().strip()
                if timing_choice == '1':
                    self.edit_animation()
                elif timing_choice == '2':
                    self._adjust_animation_speed()
            elif choice == 'N':
                print(f"\nCurrent name: '{self.animation_name}'" if self.animation_name else "\nNo name set")
                print("Enter new name: ", end='', flush=True)
                self.animation_name = input().strip()
                print(f"✓ Animation named: {self.animation_name}")
            elif choice == 'S':
                self.save_animation()
                print("\nSave another copy with different name? (y/n): ", end='', flush=True)
                if input().strip().lower() != 'y':
                    break
            elif choice == 'D':
                print("\nDiscard all keyframes? (y/n): ", end='', flush=True)
                if input().strip().lower() == 'y':
                    self.keyframes = []
                    self.animation_name = ""
                    print("✓ Animation discarded")
                    return 'restart'
            elif choice == 'Q':
                if self.keyframes and not self.animation_name:
                    print("\n⚠ Animation not saved! Quit anyway? (y/n): ", end='', flush=True)
                    if input().strip().lower() != 'y':
                        continue
                break

        return 'quit'

    def _convert_python_to_json_data(self, py_file: str) -> Optional[Dict]:
        """Convert a Python animation file to JSON data format."""
        import importlib.util
        import inspect

        py_path = Path(py_file)
        if not py_path.exists():
            print(f"✗ File not found: {py_file}")
            return None

        # Load the Python module
        try:
            spec = importlib.util.spec_from_file_location("temp_animation", py_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            print(f"✗ Error loading Python file: {e}")
            return None

        # Find the animation class
        animation_class = None
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and
                name.endswith('Animation') and
                hasattr(obj, 'get_keyframes')):
                animation_class = obj
                break

        if not animation_class:
            print(f"✗ No animation class found in {py_file}")
            return None

        # Create a mock node object for AnimationPlugin
        class MockLogger:
            def info(self, msg): pass
            def error(self, msg): pass
            def warn(self, msg): pass
            def debug(self, msg): pass

        class MockNode:
            def get_logger(self):
                return MockLogger()

        # Instantiate and extract data
        try:
            mock_node = MockNode()
            anim = animation_class(mock_node)
            keyframes_data, durations = anim.get_keyframes()

            # Convert to JSON format
            json_keyframes = []
            for i, kf in enumerate(keyframes_data):
                # Keyframe format: [base, shoulder, elbow, wrist, roll, acc, hand]
                json_kf = {
                    'servos': {
                        'base': kf[0],
                        'shoulder': kf[1],
                        'elbow': kf[2],
                        'wrist': kf[3],
                        'roll': kf[4],
                        'acc': kf[5],
                        'hand': kf[6]
                    },
                    'duration': durations[i] if i < len(durations) else 1.0
                }
                json_keyframes.append(json_kf)

            data = {
                'name': anim.name,
                'description': anim.description,
                'category': anim.get_category(),
                'keyframes': json_keyframes
            }

            return data

        except Exception as e:
            print(f"✗ Error extracting animation data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def preview_animation(self, animation_file: str):
        """Interactive preview/editing mode for animations from JSON or Python files."""
        print("\n" + "="*60)
        print("LuxoPi Animation Preview")
        print("="*60)

        # Detect file type and load appropriately
        file_path = Path(animation_file)
        print(f"\nLoading animation from: {animation_file}")

        if file_path.suffix == '.py':
            # Convert Python file to JSON data in memory
            print("  (Converting Python animation to JSON format...)")
            data = self._convert_python_to_json_data(animation_file)
            if not data:
                return
            # Use a temporary JSON path for save operations
            json_file = str(file_path.with_suffix('.json'))
        elif file_path.suffix == '.json':
            # Load JSON file directly
            try:
                with open(animation_file, 'r') as f:
                    data = json.load(f)
                json_file = animation_file
            except FileNotFoundError:
                print(f"✗ File not found: {animation_file}")
                return
            except json.JSONDecodeError as e:
                print(f"✗ Invalid JSON: {e}")
                return
        else:
            print(f"✗ Unsupported file type: {file_path.suffix}")
            print("  Supported formats: .json, .py")
            return

        animation_name = data.get('name', 'unknown')
        self.animation_name = animation_name
        self.keyframes = data.get('keyframes', [])

        if not self.keyframes:
            print("✗ No keyframes found in animation")
            return

        print(f"✓ Loaded animation: {animation_name}")
        print(f"  Keyframes: {len(self.keyframes)}")
        print(f"  Category: {data.get('category', 'unknown')}")

        # Connect to robot
        if not self.connect():
            return

        # Start serial read thread
        self.start_read_thread()

        # Wait for initial connection
        print("\nWaiting for robot to initialize (3 seconds)...")
        for i in range(3, 0, -1):
            print(f"\r  {i} seconds remaining...", end='', flush=True)
            time.sleep(1)
        print("\r  Ready!                    ")

        print("\nWaiting 2 seconds for robot to stabilize...")
        time.sleep(2)

        # Main preview menu (interactive mode)
        self._preview_main_menu(json_file, data)

        # Cleanup
        print("\nPreview complete!")
        self.running = False
        if self.ser:
            self.ser.close()

        print("✓ Goodbye!")

    def _preview_main_menu(self, json_file: str, original_data: Dict):
        """Main interactive preview menu."""
        while True:
            print("\n" + "="*60)
            print("PREVIEW MAIN MENU")
            print("="*60)
            print(f"\nAnimation: {self.animation_name}")
            print(f"Keyframes: {len(self.keyframes)}")
            print("\nWhat would you like to do?")
            print("  [P] - Play full animation (with duration calibration)")
            print("  [T] - Adjust animation speed (presets or custom)")
            print("  [S] - Step through from specific keyframe (full editing)")
            print("  [E] - Edit a specific keyframe position")
            print("  [A] - Add new keyframe at end")
            print("  [I] - Insert keyframe at specific position")
            print("  [X] - Delete a keyframe")
            print("  [L] - List all keyframes")
            print("  [V] - Save edited animation")
            print("  [Q] - Quit")
            print("\nChoice: ", end='', flush=True)

            choice = input().strip().upper()

            if choice == 'P':
                self._play_full_animation(json_file, original_data)
            elif choice == 'T':
                self._adjust_animation_speed()
            elif choice == 'S':
                self._step_through_mode()
            elif choice == 'E':
                self._edit_keyframe_position()
            elif choice == 'A':
                self._add_keyframe_at_end()
            elif choice == 'I':
                self._insert_keyframe_at_position()
            elif choice == 'X':
                self._delete_keyframe_from_menu()
            elif choice == 'L':
                self._list_keyframes()
            elif choice == 'V':
                self._save_edited_animation(json_file, original_data)
            elif choice == 'Q':
                print("\nQuit preview? (y/n): ", end='', flush=True)
                if input().strip().lower() == 'y':
                    break

    def _play_full_animation(self, json_file: str, original_data: Dict):
        """Play the full animation and offer duration calibration."""
        print("\n" + "="*60)
        print("PLAY FULL ANIMATION")
        print("="*60)

        # Disable DEMA for playback
        print("\nDisabling DEMA for playback...")
        self.disable_dema()
        time.sleep(1)

        # Play and measure
        print(f"\nPlaying animation '{self.animation_name}'...\n")
        actual_durations = self._replay_and_measure(skip_dema_prompt=True)

        # Turn on DEMA
        print("\nTurning on DEMA...")
        self.enable_full_dema()
        time.sleep(1)

        # Compare actual vs prescribed durations
        if actual_durations:
            self._check_duration_calibration(json_file, original_data, actual_durations)

    def _step_through_editing_mode(self):
        """
        Step-through editing mode for post-recording workflow.
        Wrapper that sets up environment and calls _step_through_mode.
        """
        if not self.keyframes:
            print("\n✗ No keyframes to edit")
            return

        # Already in DEMA mode from recording, so disable it for editing
        print("\nDisabling DEMA for step-through editing...")
        self.disable_dema()
        time.sleep(1)

        # Call the main step-through mode
        self._step_through_mode(start_at_first=True, auto_disable_dema=False)

        # Re-enable DEMA after editing
        print("\nRe-enabling DEMA...")
        self.enable_full_dema()
        time.sleep(1)

    def _step_through_mode(self, start_at_first: bool = False, auto_disable_dema: bool = True):
        """
        Step through animation keyframe by keyframe.

        Args:
            start_at_first: If True, start at first keyframe without asking
            auto_disable_dema: If True, disable DEMA at start (for preview mode)
        """
        print("\n" + "="*60)
        print("STEP-THROUGH MODE")
        print("="*60)

        # Ask which keyframe to start at (unless start_at_first is True)
        if start_at_first:
            start_kf = 1
            print(f"\nAnimation has {len(self.keyframes)} keyframes")
            print(f"Starting at keyframe 1...")
        else:
            print(f"\nAnimation has {len(self.keyframes)} keyframes")
            print(f"Start at keyframe number (1-{len(self.keyframes)}): ", end='', flush=True)

            try:
                start_kf = int(input().strip())
                if start_kf < 1 or start_kf > len(self.keyframes):
                    print("✗ Invalid keyframe number")
                    return
            except ValueError:
                print("✗ Invalid input")
                return

        # Start step-through at specified keyframe
        current_kf_idx = start_kf - 1

        # Disable DEMA for controlled movement (if requested)
        if auto_disable_dema:
            print("\nDisabling DEMA for step-through...")
            self.disable_dema()
            time.sleep(1)

        # Flag to track if we just edited (so we can skip moving to position)
        just_edited = False

        while True:
            print("\n" + "="*60)
            print(f"KEYFRAME {current_kf_idx + 1} / {len(self.keyframes)}")
            print("="*60)

            keyframe = self.keyframes[current_kf_idx]
            servos = keyframe['servos']

            # Show keyframe info
            print(f"\nPosition:")
            print(f"  Base={self.rad_to_deg(servos.get('base', 0)):7.2f}° "
                  f"Shoulder={self.rad_to_deg(servos.get('shoulder', 0)):7.2f}° "
                  f"Elbow={self.rad_to_deg(servos.get('elbow', 0)):7.2f}°")
            print(f"  Wrist={self.rad_to_deg(servos.get('wrist', 0)):7.2f}° "
                  f"Hand={self.rad_to_deg(servos.get('hand', 0)):7.2f}°")
            print(f"  Duration: {keyframe['duration']:.2f}s")

            # Move to this keyframe (unless we just edited it - robot is already there!)
            if just_edited:
                print(f"\n✓ Already at keyframe {current_kf_idx + 1} (just edited)")
                just_edited = False  # Reset flag
            else:
                print(f"\nMoving to keyframe {current_kf_idx + 1}...")
                self.move_to_position(keyframe)
                success, actual_position = self.wait_for_position(keyframe, tolerance_deg=7.5, timeout=8.0)

                if not success:
                    # Robot didn't reach target - update keyframe with actual position
                    print("    ⚙️  Updating keyframe with actual reached position...")
                    keyframe['servos']['base'] = actual_position['base']
                    keyframe['servos']['shoulder'] = actual_position['shoulder']
                    keyframe['servos']['elbow'] = actual_position['elbow']
                    keyframe['servos']['wrist'] = actual_position['wrist']
                    keyframe['servos']['hand'] = actual_position['hand']
                    print(f"    ✓ Keyframe {current_kf_idx + 1} updated to actual position")

            # Step-through menu
            print("\n" + "-"*60)
            print("What next?")
            print("  [N] - Next keyframe")
            print("  [P] - Previous keyframe")
            print("  [E] - Edit this keyframe")
            print("  [A] - Add new keyframe after this one")
            print("  [I] - Insert new keyframe before this one")
            print("  [X] - Delete this keyframe")
            print("  [J] - Jump to specific keyframe")
            print("  [M] - Back to main menu")
            print("\nChoice: ", end='', flush=True)

            choice = input().strip().upper()

            if choice == 'N':
                if current_kf_idx < len(self.keyframes) - 1:
                    current_kf_idx += 1
                    just_edited = False  # Moving to different keyframe
                else:
                    print("✓ Already at last keyframe")
                    time.sleep(1)
            elif choice == 'P':
                if current_kf_idx > 0:
                    current_kf_idx -= 1
                    just_edited = False  # Moving to different keyframe
                else:
                    print("✓ Already at first keyframe")
                    time.sleep(1)
            elif choice == 'E':
                # Edit current keyframe
                self._edit_specific_keyframe(current_kf_idx)
                # After edit, DEMA is disabled, perfect for continuing step-through
                just_edited = True  # Skip moving to position on next loop
            elif choice == 'A':
                # Add new keyframe after current
                new_idx = self._insert_new_keyframe(current_kf_idx, insert_after=True)
                if new_idx is not None:
                    current_kf_idx = new_idx
                    just_edited = True  # Already at new position
            elif choice == 'I':
                # Insert new keyframe before current
                new_idx = self._insert_new_keyframe(current_kf_idx, insert_after=False)
                if new_idx is not None:
                    current_kf_idx = new_idx
                    just_edited = True  # Already at new position
            elif choice == 'X':
                # Delete current keyframe
                new_idx = self._delete_current_keyframe(current_kf_idx)
                if new_idx == -1:
                    # All keyframes deleted, exit to main menu
                    print("\n⚠ No keyframes remaining, returning to main menu...")
                    # Only re-enable DEMA if we disabled it (preview mode)
                    if auto_disable_dema:
                        self.enable_full_dema()
                        time.sleep(1)
                    break
                elif new_idx is not None:
                    current_kf_idx = new_idx
                    just_edited = False  # Need to move to new position
            elif choice == 'J':
                # Jump to specific keyframe
                print(f"\nJump to keyframe (1-{len(self.keyframes)}): ", end='', flush=True)
                try:
                    jump_to = int(input().strip())
                    if 1 <= jump_to <= len(self.keyframes):
                        current_kf_idx = jump_to - 1
                        just_edited = False  # Moving to different keyframe
                    else:
                        print("✗ Invalid keyframe number")
                        time.sleep(1)
                except ValueError:
                    print("✗ Invalid input")
                    time.sleep(1)
            elif choice == 'M':
                # Return to main menu
                print("\nReturning to main menu...")
                # Only re-enable DEMA if we disabled it (preview mode)
                if auto_disable_dema:
                    print("Enabling DEMA...")
                    self.enable_full_dema()
                    time.sleep(1)
                break

    def _insert_new_keyframe(self, current_kf_idx: int, insert_after: bool = True) -> Optional[int]:
        """
        Insert a new keyframe before or after the current keyframe.

        Args:
            current_kf_idx: Index of current keyframe
            insert_after: If True, insert after current; if False, insert before

        Returns:
            Index of newly inserted keyframe, or None if cancelled
        """
        insert_position = "after" if insert_after else "before"
        insert_idx = current_kf_idx + 1 if insert_after else current_kf_idx

        print("\n" + "="*60)
        print(f"INSERT NEW KEYFRAME {insert_position.upper()} KEYFRAME {current_kf_idx + 1}")
        print("="*60)

        # Enable DEMA for manual positioning
        print(f"\nEnabling DEMA to position new keyframe...")
        self.enable_full_dema()
        time.sleep(1.5)

        # Wait for user to position robot
        print("\n" + "="*60)
        print("MANUAL POSITIONING")
        print("="*60)
        print("\n✓ DEMA enabled - robot is now limp")
        print(f"\nMove the robot to the desired position for the new keyframe.")
        print(f"This will be inserted {insert_position} keyframe {current_kf_idx + 1}.")
        print("\nPress ENTER when ready to record position (or 'c' to cancel)...", end='', flush=True)

        response = input().strip().lower()
        if response == 'c':
            print("✗ Insert cancelled")
            # Disable DEMA to return to controlled mode
            self.disable_dema()
            time.sleep(0.5)
            return None

        # Read position WHILE DEMA is still active (before servos re-engage)
        print("\nReading position while in DEMA mode...")
        new_position = self.wait_for_fresh_position(timeout=5.0)

        # NOW disable DEMA (after we have the position)
        print("Disabling DEMA to lock position...")
        self.disable_dema()
        time.sleep(0.5)

        # Calculate duration based on movement from previous keyframe
        if insert_idx > 0:
            # Calculate duration from previous keyframe
            prev_kf = self.keyframes[insert_idx - 1]
            prev_servos = prev_kf['servos']

            # Calculate total angular distance
            distance = 0.0
            distance += abs(new_position['base'] - prev_servos.get('base', 0))
            distance += abs(new_position['shoulder'] - prev_servos.get('shoulder', 0))
            distance += abs(new_position['elbow'] - prev_servos.get('elbow', 0))
            distance += abs(new_position['wrist'] - prev_servos.get('wrist', 0))
            distance += abs(new_position['hand'] - prev_servos.get('hand', 0))

            # Calculate time based on distance and speed (base_speed = 2.0 rad/s)
            duration = max(0.3, distance / 2.0)
            duration = round(duration, 2)
        else:
            # First keyframe
            duration = 0.5

        # Create new keyframe
        new_keyframe = {
            'servos': {
                'base': new_position['base'],
                'shoulder': new_position['shoulder'],
                'elbow': new_position['elbow'],
                'wrist': new_position['wrist'],
                'hand': new_position['hand'],
                'roll': -1.5,
                'spd': 0,
                'acc': 10.0
            },
            'timing': 1.0,
            'duration': duration
        }

        # Insert into keyframes list
        self.keyframes.insert(insert_idx, new_keyframe)

        print(f"\n✓ New keyframe inserted at position {insert_idx + 1}!")
        print(f"  Total keyframes: {len(self.keyframes)}")
        print(f"  New position:")
        print(f"    Base:     {self.rad_to_deg(new_position['base']):7.2f}° ({new_position['base']:.4f} rad)")
        print(f"    Shoulder: {self.rad_to_deg(new_position['shoulder']):7.2f}° ({new_position['shoulder']:.4f} rad)")
        print(f"    Elbow:    {self.rad_to_deg(new_position['elbow']):7.2f}° ({new_position['elbow']:.4f} rad)")
        print(f"    Wrist:    {self.rad_to_deg(new_position['wrist']):7.2f}° ({new_position['wrist']:.4f} rad)")
        print(f"    Hand:     {self.rad_to_deg(new_position['hand']):7.2f}° ({new_position['hand']:.4f} rad)")
        print(f"    Duration: {duration:.2f}s")

        # Return index of new keyframe
        return insert_idx

    def _delete_current_keyframe(self, current_kf_idx: int) -> Optional[int]:
        """
        Delete the current keyframe.

        Args:
            current_kf_idx: Index of keyframe to delete

        Returns:
            Index to navigate to after deletion, -1 if no keyframes remain, or None if cancelled
        """
        if len(self.keyframes) <= 1:
            print("\n⚠ Cannot delete the only remaining keyframe!")
            print("Animation must have at least 1 keyframe.")
            time.sleep(2)
            return None

        kf_num = current_kf_idx + 1
        keyframe = self.keyframes[current_kf_idx]
        servos = keyframe['servos']

        print("\n" + "="*60)
        print(f"DELETE KEYFRAME {kf_num}")
        print("="*60)

        # Show keyframe details
        print(f"\nKeyframe {kf_num} details:")
        print(f"  Base:     {self.rad_to_deg(servos.get('base', 0)):7.2f}°")
        print(f"  Shoulder: {self.rad_to_deg(servos.get('shoulder', 0)):7.2f}°")
        print(f"  Elbow:    {self.rad_to_deg(servos.get('elbow', 0)):7.2f}°")
        print(f"  Wrist:    {self.rad_to_deg(servos.get('wrist', 0)):7.2f}°")
        print(f"  Hand:     {self.rad_to_deg(servos.get('hand', 0)):7.2f}°")
        print(f"  Duration: {keyframe['duration']:.2f}s")

        # Confirm deletion
        print(f"\nDelete keyframe {kf_num}? This cannot be undone! (y/n): ", end='', flush=True)
        response = input().strip().lower()

        if response != 'y':
            print("✗ Deletion cancelled")
            return None

        # Delete the keyframe
        deleted = self.keyframes.pop(current_kf_idx)

        print(f"\n✓ Keyframe {kf_num} deleted")
        print(f"  Remaining keyframes: {len(self.keyframes)}")

        # Determine where to navigate next
        if len(self.keyframes) == 0:
            # No keyframes left
            return -1
        elif current_kf_idx >= len(self.keyframes):
            # Was at end, go to new last keyframe
            new_idx = len(self.keyframes) - 1
            print(f"  Moving to keyframe {new_idx + 1} (new last keyframe)")
            return new_idx
        else:
            # Stay at same index (which now points to next keyframe)
            print(f"  Moving to keyframe {current_kf_idx + 1} (next in sequence)")
            return current_kf_idx

    def _edit_specific_keyframe(self, kf_idx: int):
        """Edit a specific keyframe (used during step-through)."""
        kf_num = kf_idx + 1
        keyframe = self.keyframes[kf_idx]
        servos = keyframe['servos']

        print("\n" + "="*60)
        print(f"EDIT KEYFRAME {kf_num}")
        print("="*60)

        print(f"\nCurrent position:")
        print(f"  Base={self.rad_to_deg(servos.get('base', 0)):7.2f}° "
              f"Shoulder={self.rad_to_deg(servos.get('shoulder', 0)):7.2f}° "
              f"Elbow={self.rad_to_deg(servos.get('elbow', 0)):7.2f}°")
        print(f"  Wrist={self.rad_to_deg(servos.get('wrist', 0)):7.2f}° "
              f"Hand={self.rad_to_deg(servos.get('hand', 0)):7.2f}°")

        # Robot should already be at this position from step-through
        # Ask user if ready to enable DEMA
        print("\n" + "="*60)
        print("READY TO ENABLE DEMA")
        print("="*60)
        print("\n⚠️  Robot is at the current keyframe position.")
        print("When you press ENTER, DEMA will enable and the robot will go LIMP.")
        print("Make sure you are ready to support/reposition the robot!")
        print("\nPress ENTER to enable DEMA (or 'c' to cancel): ", end='', flush=True)

        response = input().strip().lower()
        if response == 'c':
            print("✗ Edit cancelled")
            return

        # Enable DEMA for manual positioning
        print("\nEnabling DEMA (robot will go limp)...")
        self.enable_full_dema()
        time.sleep(1.5)

        # Wait for user to position robot
        print("\n" + "="*60)
        print("MANUAL POSITIONING")
        print("="*60)
        print("\n✓ DEMA enabled - robot is now limp")
        print("\nMove the robot to the new position for this keyframe.")
        print("Press ENTER when ready to record new position...")
        input()

        # Read position WHILE DEMA is still active (before servos re-engage)
        print("\nReading position while in DEMA mode...")
        new_position = self.wait_for_fresh_position(timeout=5.0)

        # NOW disable DEMA (after we have the position)
        print("Disabling DEMA to lock position...")
        self.disable_dema()
        time.sleep(0.5)

        # Update keyframe
        keyframe['servos'] = {
            'base': new_position['base'],
            'shoulder': new_position['shoulder'],
            'elbow': new_position['elbow'],
            'wrist': new_position['wrist'],
            'hand': new_position['hand'],
            'roll': servos.get('roll', -1.5),
            'spd': servos.get('spd', 0),
            'acc': servos.get('acc', 10.0)
        }

        print(f"\n✓ Keyframe {kf_num} updated!")
        print(f"  New position:")
        print(f"  Base={self.rad_to_deg(new_position['base']):7.2f}° "
              f"Shoulder={self.rad_to_deg(new_position['shoulder']):7.2f}° "
              f"Elbow={self.rad_to_deg(new_position['elbow']):7.2f}°")
        print(f"  Wrist={self.rad_to_deg(new_position['wrist']):7.2f}° "
              f"Hand={self.rad_to_deg(new_position['hand']):7.2f}°")

        # Leave DEMA disabled so we can continue step-through
        print("\n✓ DEMA disabled - ready to continue step-through")

    def _add_keyframe_at_end(self):
        """Add a new keyframe at the end of the animation."""
        print("\n" + "="*60)
        print("ADD KEYFRAME AT END")
        print("="*60)

        # Use the insert method with the last position
        last_idx = len(self.keyframes) - 1
        new_idx = self._insert_new_keyframe(last_idx, insert_after=True)

        if new_idx is not None:
            print(f"\n✓ Keyframe added at end (position {new_idx + 1})")
        else:
            print("\n✗ Add cancelled")

    def _insert_keyframe_at_position(self):
        """Insert a keyframe at a user-specified position."""
        print("\n" + "="*60)
        print("INSERT KEYFRAME AT POSITION")
        print("="*60)

        # Show current keyframes
        print(f"\nCurrent keyframes: {len(self.keyframes)}")
        for i in range(len(self.keyframes)):
            print(f"  {i+1}. Keyframe {i+1}")

        # Ask for position
        print(f"\nInsert new keyframe before which keyframe? (1-{len(self.keyframes)+1}): ", end='', flush=True)
        print(f"\n  (Enter {len(self.keyframes)+1} to add at end)")
        print("Choice: ", end='', flush=True)

        try:
            position = int(input().strip())
            if position < 1 or position > len(self.keyframes) + 1:
                print("✗ Invalid position")
                return
        except ValueError:
            print("✗ Invalid input")
            return

        # Insert before the specified position
        if position == len(self.keyframes) + 1:
            # Add at end
            target_idx = len(self.keyframes) - 1
            insert_after = True
        else:
            # Insert before
            target_idx = position - 1
            insert_after = False

        new_idx = self._insert_new_keyframe(target_idx, insert_after=insert_after)

        if new_idx is not None:
            print(f"\n✓ Keyframe inserted at position {new_idx + 1}")
        else:
            print("\n✗ Insert cancelled")

    def _delete_keyframe_from_menu(self):
        """Delete a keyframe by number from the main menu."""
        if len(self.keyframes) <= 1:
            print("\n⚠ Cannot delete the only remaining keyframe!")
            print("Animation must have at least 1 keyframe.")
            time.sleep(2)
            return

        print("\n" + "="*60)
        print("DELETE KEYFRAME")
        print("="*60)

        # Show current keyframes
        print(f"\nCurrent keyframes: {len(self.keyframes)}")
        for i in range(len(self.keyframes)):
            kf = self.keyframes[i]
            servos = kf['servos']
            print(f"  {i+1}. Base={self.rad_to_deg(servos.get('base', 0)):6.2f}° "
                  f"Shoulder={self.rad_to_deg(servos.get('shoulder', 0)):6.2f}° "
                  f"Elbow={self.rad_to_deg(servos.get('elbow', 0)):6.2f}°")

        # Ask which to delete
        print(f"\nDelete which keyframe? (1-{len(self.keyframes)}, or 0 to cancel): ", end='', flush=True)

        try:
            kf_num = int(input().strip())
            if kf_num == 0:
                print("✗ Delete cancelled")
                return
            if kf_num < 1 or kf_num > len(self.keyframes):
                print("✗ Invalid keyframe number")
                return
        except ValueError:
            print("✗ Invalid input")
            return

        # Delete using the existing method
        kf_idx = kf_num - 1
        result = self._delete_current_keyframe(kf_idx)

        if result == -1:
            print("\n⚠ All keyframes deleted - animation is now empty!")
            time.sleep(2)
        elif result is not None:
            print(f"\n✓ Keyframe {kf_num} deleted successfully")
        # else: cancelled or error (already printed)

    def _list_keyframes(self):
        """List all keyframes with details."""
        print("\n" + "="*60)
        print("KEYFRAME LIST")
        print("="*60)

        for i, kf in enumerate(self.keyframes):
            servos = kf['servos']
            print(f"\n{i+1}. Keyframe {i+1}:")
            print(f"   Base={self.rad_to_deg(servos.get('base', 0)):7.2f}° "
                  f"Shoulder={self.rad_to_deg(servos.get('shoulder', 0)):7.2f}° "
                  f"Elbow={self.rad_to_deg(servos.get('elbow', 0)):7.2f}°")
            print(f"   Wrist={self.rad_to_deg(servos.get('wrist', 0)):7.2f}° "
                  f"Hand={self.rad_to_deg(servos.get('hand', 0)):7.2f}°")
            print(f"   Duration: {kf['duration']:.2f}s  Timing: {kf['timing']:.1f}x")

    def _edit_keyframe_position(self):
        """Edit a specific keyframe by moving robot to new position."""
        print("\n" + "="*60)
        print("EDIT KEYFRAME POSITION")
        print("="*60)

        # Show keyframe list
        print("\nAvailable keyframes:")
        for i in range(len(self.keyframes)):
            print(f"  {i+1}. Keyframe {i+1}")

        # Get keyframe number
        try:
            kf_num = int(input("\nEnter keyframe number to edit (0 to cancel): "))
            if kf_num == 0:
                return

            if kf_num < 1 or kf_num > len(self.keyframes):
                print("✗ Invalid keyframe number")
                return

            kf_idx = kf_num - 1
        except ValueError:
            print("✗ Invalid input")
            return

        # Show current position
        keyframe = self.keyframes[kf_idx]
        servos = keyframe['servos']
        print(f"\nCurrent position for Keyframe {kf_num}:")
        print(f"  Base={self.rad_to_deg(servos.get('base', 0)):7.2f}° "
              f"Shoulder={self.rad_to_deg(servos.get('shoulder', 0)):7.2f}° "
              f"Elbow={self.rad_to_deg(servos.get('elbow', 0)):7.2f}°")
        print(f"  Wrist={self.rad_to_deg(servos.get('wrist', 0)):7.2f}° "
              f"Hand={self.rad_to_deg(servos.get('hand', 0)):7.2f}°")

        # Ensure DEMA is OFF before moving
        print(f"\nDisabling DEMA to move to Keyframe {kf_num}...")
        self.disable_dema()
        time.sleep(1)

        # Move to current position
        print(f"Moving to current Keyframe {kf_num} position...")
        self.move_to_position(keyframe)
        success, actual_position = self.wait_for_position(keyframe, tolerance_deg=7.5, timeout=8.0)

        if not success:
            # Robot didn't reach target - update keyframe with actual position
            print("    ⚙️  Updating keyframe with actual reached position...")
            keyframe['servos']['base'] = actual_position['base']
            keyframe['servos']['shoulder'] = actual_position['shoulder']
            keyframe['servos']['elbow'] = actual_position['elbow']
            keyframe['servos']['wrist'] = actual_position['wrist']
            keyframe['servos']['hand'] = actual_position['hand']
            print(f"    ✓ Keyframe {kf_num} updated to actual position")

        # Wait for user confirmation that robot is at position
        print("\n" + "="*60)
        print("READY TO ENABLE DEMA")
        print("="*60)
        print("\n⚠️  Robot is at the current keyframe position.")
        print("When you press ENTER, DEMA will enable and the robot will go LIMP.")
        print("Make sure you are ready to support/reposition the robot!")
        print("\nPress ENTER to enable DEMA...", end='', flush=True)
        input()

        # Enable DEMA for manual positioning
        print("\nEnabling DEMA (robot will go limp)...")
        self.enable_full_dema()
        time.sleep(1.5)

        # Wait for user to position robot
        print("\n" + "="*60)
        print("MANUAL POSITIONING")
        print("="*60)
        print("\n✓ DEMA enabled - robot is now limp")
        print("\nMove the robot to the new position for this keyframe.")
        print("Press ENTER when ready to record new position...")
        input()

        # Read position WHILE DEMA is still active (before servos re-engage)
        print("\nReading position while in DEMA mode...")
        new_position = self.wait_for_fresh_position(timeout=5.0)

        # NOW disable DEMA (after we have the position)
        print("Disabling DEMA to lock position...")
        self.disable_dema()
        time.sleep(0.5)

        # Update keyframe
        keyframe['servos'] = {
            'base': new_position['base'],
            'shoulder': new_position['shoulder'],
            'elbow': new_position['elbow'],
            'wrist': new_position['wrist'],
            'hand': new_position['hand'],
            'roll': servos.get('roll', -1.5),
            'spd': servos.get('spd', 0),
            'acc': servos.get('acc', 10.0)
        }

        print(f"\n✓ Keyframe {kf_num} updated!")
        print(f"  New position:")
        print(f"  Base={self.rad_to_deg(new_position['base']):7.2f}° "
              f"Shoulder={self.rad_to_deg(new_position['shoulder']):7.2f}° "
              f"Elbow={self.rad_to_deg(new_position['elbow']):7.2f}°")
        print(f"  Wrist={self.rad_to_deg(new_position['wrist']):7.2f}° "
              f"Hand={self.rad_to_deg(new_position['hand']):7.2f}°")

        # Leave DEMA disabled so robot holds new position
        print("\n✓ DEMA disabled - robot holding new position")

    def _adjust_animation_speed(self):
        """Adjust animation speed using presets or custom acceleration ranges."""
        print("\n" + "="*60)
        print("ADJUST ANIMATION SPEED")
        print("="*60)

        if not self.keyframes:
            print("\n✗ No keyframes to adjust")
            return

        # Show current acceleration range
        current_acc_values = [kf['servos'].get('acc', 10.0) for kf in self.keyframes]
        current_min = min(current_acc_values)
        current_max = max(current_acc_values)

        print(f"\nCurrent acceleration range: {current_min:.1f} - {current_max:.1f}")
        print(f"Current keyframes: {len(self.keyframes)}")

        # Show presets
        print("\n" + "-"*60)
        print("SPEED PRESETS (Higher acc = FASTER movement):")
        print("-"*60)
        for name, (min_acc, max_acc) in PRESETS.items():
            if min_acc == max_acc:
                print(f"  {name:10s} - {min_acc:.0f}")
            else:
                print(f"  {name:10s} - {min_acc:.0f} to {max_acc:.0f}")

        print("\n" + "-"*60)
        print("OPTIONS:")
        print("  [preset_name] - Use a preset (e.g., 'fast', 'medium')")
        print("  [number]      - Custom single value (e.g., '100')")
        print("  [min-max]     - Custom range (e.g., '50-150')")
        print("  [cancel]      - Cancel adjustment")
        print("-"*60)

        # Get user choice
        print("\nEnter choice: ", end='', flush=True)
        choice = input().strip().lower()

        if choice == 'cancel' or choice == '':
            print("✗ Adjustment cancelled")
            return

        # Parse choice
        min_acc = None
        max_acc = None

        if choice in PRESETS:
            min_acc, max_acc = PRESETS[choice]
            print(f"\n✓ Using preset '{choice}': {min_acc:.1f} - {max_acc:.1f}")
        else:
            try:
                min_acc, max_acc = parse_acceleration_range(choice)
                print(f"\n✓ Using custom range: {min_acc:.1f} - {max_acc:.1f}")
            except ValueError as e:
                print(f"\n✗ Invalid input: {e}")
                return

        # Validate range
        if min_acc < 0.0 or max_acc > 254.0:
            print(f"⚠ Warning: Acceleration values should be between 0.0 and 254.0")
            print(f"  (You specified: {min_acc:.1f}-{max_acc:.1f})")
            print("\nContinue anyway? (y/n): ", end='', flush=True)
            if input().strip().lower() != 'y':
                print("✗ Adjustment cancelled")
                return

        # Ask about duration adjustment
        print("\n" + "-"*60)
        print("DURATION ADJUSTMENT:")
        print("  Higher acc = faster movement = shorter durations")
        print("  Lower acc = slower movement = longer durations")
        print("-"*60)
        print("\nAdjust durations based on acceleration change? (y/n): ", end='', flush=True)
        adjust_duration = input().strip().lower() == 'y'

        # Build temp JSON structure for adjustment
        temp_data = {
            'name': self.animation_name,
            'keyframes': self.keyframes
        }

        # Apply adjustment
        print("\nApplying speed adjustment...")
        modified_data = apply_speed_adjustment(
            temp_data,
            min_acc,
            max_acc,
            distribution='varied',
            adjust_duration=adjust_duration,
            verbose=True
        )

        # Update keyframes in place
        self.keyframes = modified_data['keyframes']

        print("\n✓ Speed adjustment applied!")
        print("\nWould you like to preview the adjusted animation? (y/n): ", end='', flush=True)
        if input().strip().lower() == 'y':
            self._replay_and_measure(skip_dema_prompt=True)

    def _save_edited_animation(self, original_json_file: str, original_data: Dict):
        """Save the edited animation with a new timestamp and convert to Python."""
        print("\n" + "="*60)
        print("SAVE EDITED ANIMATION")
        print("="*60)

        # Ask for new name (optional)
        print(f"\nCurrent name: '{self.animation_name}'")
        print("Enter new name (or press ENTER to keep current name): ", end='', flush=True)
        new_name = input().strip()
        if new_name:
            self.animation_name = new_name

        # Build new JSON data
        data = {
            "name": self.animation_name,
            "description": original_data.get('description', 'Edited animation'),
            "category": original_data.get('category', 'custom'),
            "created": datetime.now().isoformat(),
            "keyframes": self.keyframes,
            "keyframe_count": len(self.keyframes)
        }

        # Generate filename
        filename = f"animation_{self.animation_name}.json"
        filepath = Path("./json") / filename

        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Save JSON
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            print(f"\n✓ Animation saved to: {filepath}")
            print(f"  Name: {self.animation_name}")
            print(f"  Keyframes: {len(self.keyframes)}")

            # Automatically convert to Python
            self.convert_json_to_python(filepath)

        except Exception as e:
            print(f"\n✗ Error saving animation: {e}")

    def _replay_and_measure(self, skip_dema_prompt: bool = False) -> List[float]:
        """
        Replay animation and measure actual time to reach each keyframe.

        Returns:
            List of actual durations (time to reach each keyframe)
        """
        if not self.keyframes:
            print("\n✗ No keyframes to replay")
            return []

        print(f"▶ Replaying animation with {len(self.keyframes)} keyframes...")

        # Disable DEMA for controlled playback
        print("\n  Disabling DEMA for playback...")
        self.disable_dema()
        time.sleep(1)

        actual_durations = []

        # Start timing total animation duration
        animation_start_time = time.time()

        # Play through keyframes
        print("\n  Playing keyframes and measuring durations...")
        for i, keyframe in enumerate(self.keyframes):
            print(f"\n  → Keyframe {i+1}/{len(self.keyframes)}")

            # Start timing
            start_time = time.time()

            # Send movement command
            self.move_to_position(keyframe)

            # Wait for robot to reach position (ignore prescribed duration)
            success, actual_position = self.wait_for_position(keyframe, tolerance_deg=7.5, timeout=8.0)

            if not success:
                # Robot didn't reach target - update keyframe with actual position
                print("    ⚙️  Updating keyframe with actual reached position...")

                # Update the keyframe with actual position (preserve spd, acc, roll)
                keyframe['servos']['base'] = actual_position['base']
                keyframe['servos']['shoulder'] = actual_position['shoulder']
                keyframe['servos']['elbow'] = actual_position['elbow']
                keyframe['servos']['wrist'] = actual_position['wrist']
                keyframe['servos']['hand'] = actual_position['hand']

                print(f"    ✓ Keyframe {i+1} updated to actual position")

            # Measure actual time
            actual_time = time.time() - start_time
            actual_durations.append(round(actual_time, 2))

            prescribed_duration = keyframe.get('duration', 0.5)
            print(f"    Actual time: {actual_time:.2f}s (prescribed: {prescribed_duration:.2f}s)")

        # Calculate total animation time
        total_animation_time = time.time() - animation_start_time

        print("\n✓ Playback complete")
        print(f"⏱️  Total animation duration: {total_animation_time:.2f} seconds")
        return actual_durations

    def _check_duration_calibration(self, json_file: str, data: Dict, actual_durations: List[float]):
        """
        Check if actual durations differ significantly from prescribed ones.
        Offer to update the JSON file if needed.
        """
        prescribed_durations = [kf.get('duration', 0.5) for kf in self.keyframes]

        # Calculate differences
        differences = []
        for i, (actual, prescribed) in enumerate(zip(actual_durations, prescribed_durations)):
            diff = abs(actual - prescribed)
            diff_pct = (diff / max(prescribed, 0.1)) * 100  # Avoid division by zero
            differences.append((i, actual, prescribed, diff, diff_pct))

        # Check if any differences are significant (>30% or >0.5s)
        significant_diffs = [d for d in differences if d[3] > 0.5 or d[4] > 30]

        if not significant_diffs:
            print("\n✓ Duration calibration looks good! All keyframes within tolerance.")
            return

        # Show significant differences
        print("\n" + "="*60)
        print("DURATION CALIBRATION ANALYSIS")
        print("="*60)
        print("\nSignificant differences detected:")

        for i, actual, prescribed, diff, diff_pct in significant_diffs:
            print(f"\n  Keyframe {i+1}:")
            print(f"    Prescribed: {prescribed:.2f}s")
            print(f"    Actual:     {actual:.2f}s")
            print(f"    Difference: {diff:.2f}s ({diff_pct:.1f}%)")

        # Offer to update
        print("\n" + "="*60)
        print(f"Update {json_file} with measured durations? (y/n): ", end='', flush=True)
        response = input().strip().lower()

        if response == 'y':
            # Update durations in data
            for i, actual in enumerate(actual_durations):
                if i < len(self.keyframes):
                    self.keyframes[i]['duration'] = actual
                    data['keyframes'][i]['duration'] = actual

            # Write back to file
            try:
                with open(json_file, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"\n✓ Updated {json_file} with calibrated durations")
                print("\nUpdated durations:")
                for i, actual in enumerate(actual_durations):
                    print(f"  Keyframe {i+1}: {actual:.2f}s")
            except Exception as e:
                print(f"\n✗ Error updating file: {e}")
        else:
            print("\n✓ Durations not updated")

    def run(self):
        """Main application loop."""
        print("\n" + "="*60)
        print("LuxoPi Animation Recorder")
        print("="*60)

        # Connect to robot
        if not self.connect():
            return

        # Start serial read thread
        self.start_read_thread()

        # Wait for initial connection
        print("\nWaiting for robot to initialize (5 seconds)...")
        for i in range(5, 0, -1):
            print(f"\r  {i} seconds remaining...", end='', flush=True)
            time.sleep(1)
        print("\r  Ready!                    ")

        # Enable full DEMA
        if not self.enable_full_dema():
            print("✗ Failed to enable DEMA mode")
            return

        time.sleep(1)

        # Main loop
        while True:
            # Recording phase
            self.recording_loop()

            if not self.keyframes:
                print("\nNo keyframes recorded. Exiting...")
                break

            # Post-recording menu
            action = self.post_recording_menu()

            if action == 'restart':
                # Reset for new recording
                print("\n\nStarting new recording session...")
                time.sleep(1)
                continue
            else:
                break

        # Cleanup
        print("\nCleaning up...")
        # Keep DEMA enabled so robot stays limp

        self.running = False
        if self.ser:
            self.ser.close()

        print("✓ Goodbye! (DEMA left enabled)")

    def cleanup(self):
        """Cleanup resources."""
        self.running = False
        if self.old_settings:
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, self.old_settings)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Interactive animation recorder for LuxoPi RoArm-M3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record a new animation
  python3 animation_recorder.py

  # Preview an existing JSON animation
  python3 animation_recorder.py --preview ./json/animation_hopping.json

  # Preview a Python animation (auto-converts to JSON format)
  python3 animation_recorder.py --preview ./python/animation_big_bow.py

  # Use a different serial port
  python3 animation_recorder.py --port /dev/ttyUSB0
        """
    )

    parser.add_argument(
        '--port',
        default='/dev/ttyAMA0',
        help='Serial port (default: /dev/ttyAMA0)'
    )

    parser.add_argument(
        '--baudrate',
        type=int,
        default=115200,
        help='Baud rate (default: 115200)'
    )

    parser.add_argument(
        '--preview',
        metavar='FILE',
        help='Preview/test an animation from a JSON or Python file (auto disables/enables DEMA)'
    )

    args = parser.parse_args()

    recorder = AnimationRecorder(port=args.port, baudrate=args.baudrate)

    try:
        # Check if preview mode is enabled
        if args.preview:
            recorder.preview_animation(args.preview)
        else:
            recorder.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        recorder.cleanup()
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        recorder.cleanup()


if __name__ == '__main__':
    main()
