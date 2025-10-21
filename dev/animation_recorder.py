#!/usr/bin/env python3
"""
Animation Recording Tool for LuxoPi RoArm-M3

This tool allows you to manually position the robot arm and record keyframes
for creating new animations. It operates in DEMA (full compliance) mode so you
can physically move the arm to desired positions.

Usage:
    python3 animation_recorder.py [--port /dev/ttyAMA0]
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
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


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
        position = self.get_current_position()

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

    def wait_for_position(self, target_keyframe: Dict, tolerance_deg: float = 12.0, timeout: float = 30.0) -> bool:
        """
        Wait until robot reaches target position within tolerance.

        Args:
            target_keyframe: Target keyframe with servos dict (in RADIANS)
            tolerance_deg: Acceptable position error in degrees (default: 12.0)
            timeout: Maximum time to wait in seconds (default: 30.0)

        Returns:
            True if position reached, False if timeout
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
            max_error_rad = max(errors_rad.values())
            max_error_deg = self.rad_to_deg(max_error_rad)

            if max_error_rad <= tolerance_rad:
                print(f" ✓ Reached (max error: {max_error_deg:.2f}°)")
                print(f"\n    Current position:")
                print(f"      Base:     {self.rad_to_deg(current['base']):7.2f}° ({current['base']:.4f} rad)")
                print(f"      Shoulder: {self.rad_to_deg(current['shoulder']):7.2f}° ({current['shoulder']:.4f} rad)")
                print(f"      Elbow:    {self.rad_to_deg(current['elbow']):7.2f}° ({current['elbow']:.4f} rad)")
                print(f"      Wrist:    {self.rad_to_deg(current['wrist']):7.2f}° ({current['wrist']:.4f} rad)")
                print(f"      Hand:     {self.rad_to_deg(current['hand']):7.2f}° ({current['hand']:.4f} rad)")
                return True

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
        return False

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
            if not self.wait_for_position(keyframe, tolerance_deg=12.0, timeout=30.0):
                print("    ⚠ Warning: Robot did not reach target position")
                print("    Continue anyway? (y/n): ", end='', flush=True)
                response = input().strip().lower()
                if response != 'y':
                    print("\n✗ Playback cancelled")
                    return

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

    def save_animation(self):
        """Save animation to JSON file in animations/json/ folder."""
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
        output_dir = Path('animations/json')
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = f"animation_{self.animation_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = output_dir / filename

        # Save to file
        try:
            with open(filepath, 'w') as f:
                json.dump(animation_data, f, indent=2)
            print(f"\n✓ Animation saved to: {filepath}")
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
            print("  [E] - Edit animation")
            print("  [N] - Name/rename animation")
            print("  [S] - Save animation")
            print("  [D] - Discard and start over")
            print("  [Q] - Quit")
            print("\nChoice: ", end='', flush=True)

            choice = input().strip().upper()

            if choice == 'P':
                self.replay_animation()
            elif choice == 'E':
                self.edit_animation()
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

    def preview_animation(self, json_file: str):
        """Preview an animation from a JSON file and optionally calibrate durations."""
        print("\n" + "="*60)
        print("LuxoPi Animation Preview")
        print("="*60)

        # Load JSON file
        print(f"\nLoading animation from: {json_file}")
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"✗ File not found: {json_file}")
            return
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON: {e}")
            return

        animation_name = data.get('name', 'unknown')
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

        # Play animation and measure actual durations
        print(f"\nPlaying animation '{animation_name}'...\n")
        actual_durations = self._replay_and_measure(skip_dema_prompt=True)

        # Turn on DEMA
        print("\nTurning on DEMA...")
        self.enable_full_dema()
        time.sleep(1)

        # Compare actual vs prescribed durations
        if actual_durations:
            self._check_duration_calibration(json_file, data, actual_durations)

        # Cleanup
        print("\nPreview complete!")
        self.running = False
        if self.ser:
            self.ser.close()

        print("✓ Goodbye! (DEMA left enabled)")

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

        # Play through keyframes
        print("\n  Playing keyframes and measuring durations...")
        for i, keyframe in enumerate(self.keyframes):
            print(f"\n  → Keyframe {i+1}/{len(self.keyframes)}")

            # Start timing
            start_time = time.time()

            # Send movement command
            self.move_to_position(keyframe)

            # Wait for robot to reach position (ignore prescribed duration)
            if not self.wait_for_position(keyframe, tolerance_deg=12.0, timeout=30.0):
                print("    ⚠ Warning: Robot did not reach target position")
                print("    Continue anyway? (y/n): ", end='', flush=True)
                response = input().strip().lower()
                if response != 'y':
                    print("\n✗ Playback cancelled")
                    return []

            # Measure actual time
            actual_time = time.time() - start_time
            actual_durations.append(round(actual_time, 2))

            prescribed_duration = keyframe.get('duration', 0.5)
            print(f"    Actual time: {actual_time:.2f}s (prescribed: {prescribed_duration:.2f}s)")

        print("\n✓ Playback complete")
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

  # Preview an existing animation
  python3 animation_recorder.py --preview animations/json/animation_hopping.json

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
        metavar='JSON_FILE',
        help='Preview/test an animation from a JSON file (auto disables/enables DEMA)'
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
