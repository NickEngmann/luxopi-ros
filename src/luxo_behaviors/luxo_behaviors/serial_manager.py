#!/usr/bin/env python3

import serial
import threading
import json
import time
import os
import subprocess
import atexit
from std_msgs.msg import String

class SerialManager(threading.Thread):
    """
    Manages serial communication with the robot hardware.
    Acts as an abstraction layer between hardware protocols and ROS nodes.
    """
    def __init__(self, node, serial_port='/dev/ttyAMA0', baud_rate=115200, read_throttle=0.1):
        """
        Initialize the serial manager.
        
        Args:
            node: The ROS node that owns this manager (for logging)
            serial_port: Path to the serial device
            baud_rate: Serial communication baud rate
            read_throttle: Delay between serial read attempts to reduce CPU usage (set to 0 for max responsiveness)
        """
        # Initialize thread
        threading.Thread.__init__(self, daemon=True)
        
        self.node = node
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.read_throttle = read_throttle  # Setting this to 0 for responsiveness
        
        # Connection control
        self.running = False
        self.connection_active = False
        self.connection_lock = threading.Lock()
        self.ser = None
        
        # Callback for data received
        self.data_callback = None
        
        # Simplified tracking variables
        self.last_heartbeat_time = 0
        self.heartbeat_interval = 2.0  # Send a heartbeat every 2 seconds if no other traffic
        
        # Create publisher for arm position feedback
        self.position_publisher = self.node.create_publisher(
            String,
            'roarm/position',
            10
        )
        
        # Register clean shutdown handler
        atexit.register(self.ensure_closed)
    
    def set_data_callback(self, callback):
        """Set callback function that will be called when data is received."""
        self.data_callback = callback
    
    def check_fix_permissions(self):
        """Check and fix permissions on the serial port if needed"""
        try:
            self.node.get_logger().info(f"Checking permissions on {self.serial_port}")
            
            # Check if we have read/write access
            if not os.access(self.serial_port, os.R_OK | os.W_OK):
                self.node.get_logger().warn(f"Insufficient permissions on {self.serial_port}, attempting to fix")
                
                try:
                    # Try to fix permissions using sudo chmod
                    cmd = ['sudo', 'chmod', '777', self.serial_port]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        self.node.get_logger().info("Successfully updated port permissions")
                        return True
                    else:
                        self.node.get_logger().error(f"Failed to update permissions: {result.stderr}")
                        return False
                        
                except subprocess.SubprocessError as e:
                    self.node.get_logger().error(f"Failed to run chmod command: {e}")
                    return False
            
            return True  # Permissions are already OK
            
        except Exception as e:
            self.node.get_logger().error(f"Error checking/fixing permissions: {e}")
            return False
    
    def ensure_closed(self):
        """Guaranteed cleanup method registered with atexit"""
        self.close()
    
    def connect(self):
        """Establish connection to the serial port"""
        # Check permissions first
        if not self.check_fix_permissions():
            self.node.get_logger().warn("Continuing without fixing permissions, may fail")
        
        try:
            # Force close any existing connection
            self.close()
            
            # Wait a moment before trying to open again
            time.sleep(0.5)
            
            # Open serial port with simpler settings similar to the working example
            self.ser = serial.Serial(
                port=self.serial_port, 
                baudrate=self.baud_rate, 
                timeout=1,      # Add timeout
                dsrdtr=False,   # Disable hardware flow control
                rtscts=False    # Disable hardware flow control
            )
            
            # Clear any buffered data
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            # Flow control settings that work in the test script
            self.ser.setRTS(False)
            self.ser.setDTR(False)
            
            self.node.get_logger().info(f"Serial port {self.serial_port} connected successfully at {self.baud_rate} baud")
            
            # Update connection status
            with self.connection_lock:
                self.connection_active = True
            
            # Reset heartbeat timing
            self.last_heartbeat_time = time.time()
            
            # If not already running, start the thread
            if not self.running:
                self.running = True
                self.start()
            
            # Send a ping to verify connection is working
            self.send_command(json.dumps({'T': 0}), "Connection test ping")
            
            return True
            
        except serial.SerialException as e:
            self.node.get_logger().error(f"Failed to open serial port: {e}")
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def is_connected(self):
        """Thread-safe method to check connection status"""
        with self.connection_lock:
            return self.connection_active and hasattr(self, 'ser') and self.ser and self.ser.is_open
    
    def send_command(self, cmd_str, description=""):
        """Send a command to the robot arm."""
        if not self.is_connected():
            self.node.get_logger().error("Cannot send command: Serial connection is not active")
            return False
        
        try:
            # Add description to logs
            if description:
                self.node.get_logger().debug(f"Sending {description}: {cmd_str}")
            
            # Ensure command ends with CRLF (consistent with working example)
            if not cmd_str.endswith('\r\n'):
                cmd_str = cmd_str.rstrip('\n') + '\r\n'
            
            # Write command to serial port
            self.ser.write(cmd_str.encode())
            self.ser.flush()
            
            # Update heartbeat time since we've sent data
            self.last_heartbeat_time = time.time()
            
            return True
        except Exception as e:
            self.node.get_logger().error(f"Serial write error: {e}")
            with self.connection_lock:
                self.connection_active = False
            return False
    
    def run(self):
        """Thread main method - reads from serial port"""
        self.node.get_logger().info("Serial read thread started")
        
        while self.running:
            if self.is_connected():
                try:
                    # Check if we should send a heartbeat to keep the connection alive
                    current_time = time.time()
                    if current_time - self.last_heartbeat_time >= self.heartbeat_interval:
                        self._send_heartbeat()
                    
                    # Read directly from the serial port without delay
                    if self.ser.in_waiting > 0:
                        raw_data = self.ser.readline()
                        
                        if raw_data:
                            try:
                                line = raw_data.decode('utf-8', errors='replace').strip()
                                if line:
                                    # Process immediately without additional logging/filtering
                                    self._process_response(line)
                            except UnicodeDecodeError:
                                self._process_binary_response(raw_data)
                    # Only sleep a tiny amount if no data to prevent tight loop
                    elif self.read_throttle > 0:
                        time.sleep(self.read_throttle)
                        
                except Exception as e:
                    self.node.get_logger().error(f"Error reading from serial: {e}")
                    time.sleep(1.0)  # Sleep longer on error
                    # Attempt reconnection on the next loop if there's an error
                    with self.connection_lock:
                        self.connection_active = False
            else:
                # If not connected, wait a bit before next check
                time.sleep(1.0)
                
        self.node.get_logger().info("Serial read thread stopped")
        
    def _process_binary_response(self, raw_data):
        """Process binary (non-UTF8) data received from the serial port"""
        try:
            # Log the hex representation for debugging
            hex_data = ' '.join([f"{b:02x}" for b in raw_data])
            self.node.get_logger().debug(f"Processing binary data: {hex_data}")
            
            # If we have a data callback, pass the raw data along
            if self.data_callback:
                # Pass hex representation as it's more useful than raw bytes
                self.data_callback(f"BINARY:{hex_data}")
                    
        except Exception as e:
            self.node.get_logger().error(f"Error processing binary data: {e}")
    
    def _send_heartbeat(self):
        """Send a heartbeat message to keep the connection alive"""
        try:
            if self.is_connected():
                # Use CRLF line ending for heartbeat
                heartbeat_cmd = json.dumps({'T': 0})
                self.ser.write((heartbeat_cmd + '\r\n').encode())
                self.ser.flush()
                self.last_heartbeat_time = time.time()
                self.node.get_logger().debug("Heartbeat sent")
        except Exception as e:
            self.node.get_logger().debug(f"Failed to send heartbeat: {e}")
            with self.connection_lock:
                self.connection_active = False
    
    def _process_response(self, response):
        """Process a response from the hardware."""
        # Check if this is a position feedback response (T:105 or T:1051)
        try:
            data = json.loads(response)
            if isinstance(data, dict) and 'T' in data:
                # Check for continuous position feedback (T:1051)
                if data['T'] == 1051 and 'b' in data and 's' in data and 'e' in data:
                    # Convert position data to a list format
                    position_list = [
                        data.get('b', 0.0),  # base
                        data.get('s', 0.0),  # shoulder
                        data.get('e', 0.0),  # elbow
                        data.get('t', 0.0),  # wrist (t in the message)
                        data.get('g', 0.0)  # gripper/hand (default to 0.0 if not present)
                    ]
                    
                    # Publish position data to ROS topic as a list format
                    msg = String()
                    msg.data = json.dumps(position_list)
                    self.position_publisher.publish(msg)
                    
                    # Only log occasionally to prevent log flooding
                    if not hasattr(self, '_last_1051_log_time') or time.time() - self._last_1051_log_time > 10.0:
                        self.node.get_logger().debug(f"Position feedback published: {position_list}")
                        self._last_1051_log_time = time.time()
                    
                    # If we have a position feedback callback registered, call it with this data
                    if hasattr(self, '_position_feedback_callback') and self._position_feedback_callback:
                        self._position_feedback_callback(data)
                        # Clear the callback after it's been used once
                        self._position_feedback_callback = None
                        self.node.get_logger().info("Used continuous position feedback for initialization")
                    
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # Not JSON or not the expected format, ignore for position processing
            pass
            
        # If we have a callback registered, pass the data along
        if self.data_callback:
            self.data_callback(response)
    
    def close(self):
        """Close the serial connection and clean up resources."""
        self.node.get_logger().info("Closing serial connection")
        self.running = False
        
        # Join thread if it's running
        if threading.current_thread() != self:
            try:
                self.join(timeout=1.0)
            except RuntimeError:
                # Thread may not have been started yet
                pass
        
        # Close the serial port
        if hasattr(self, 'ser') and self.ser:
            try:
                if self.ser.is_open:
                    self.ser.flush()
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                    self.ser.close()
            except Exception as e:
                self.node.get_logger().error(f"Error closing serial port: {e}")
        
        with self.connection_lock:
            self.connection_active = False
            self.ser = None
            
        self.node.get_logger().info("Serial connection closed")

    def enable_torque(self):
        """Enable torque on the arm."""
        # Send torque lock command (T:210, cmd:1)
        torque_cmd = json.dumps({'T': 210, 'cmd': 1})
        success = self.send_command(torque_cmd, "Enabling torque lock")
        if success:
            self.node.get_logger().info("Torque lock enabled")
        else:
            self.node.get_logger().error("Failed to enable torque")
        return success
    
    def disable_torque(self):
        """Disable torque on the arm."""
        # Send torque unlock command (T:210, cmd:0)
        torque_cmd = json.dumps({'T': 210, 'cmd': 0})
        success = self.send_command(torque_cmd, "Disabling torque lock")
        if success:
            self.node.get_logger().info("Torque lock disabled")
        else:
            self.node.get_logger().error("Failed to disable torque")
        return success
    
    def initialize_arm(self):
        """Initialize the arm by moving to home position."""
        # Send initialization command (T:100)
        init_cmd = json.dumps({'T': 100})
        success = self.send_command(init_cmd, "Initializing arm position")
        if success:
            self.node.get_logger().info("Arm initialized to home position")
        else:
            self.node.get_logger().error("Failed to initialize arm position")
        return success
    
    def emergency_stop(self):
        """Send emergency stop command to immediately halt all movement."""
        stop_cmd = json.dumps({'T': 0})
        success = self.send_command(stop_cmd, "Emergency STOP")
        if success:
            self.node.get_logger().warn("Emergency stop activated")
        else:
            self.node.get_logger().error("Failed to send emergency stop command")
        return success
    
    def reset_emergency(self):
        """Reset emergency stop flag on the arm."""
        reset_cmd = json.dumps({'T': 999})
        success = self.send_command(reset_cmd, "Reset emergency flag")
        if success:
            self.node.get_logger().info("Emergency flag reset")
        else:
            self.node.get_logger().error("Failed to reset emergency flag")
        return success
    
    def control_single_joint(self, joint_id, rad_angle, speed=0, accel=10):
        """
        Control a single joint directly.
        
        Args:
            joint_id (int): Joint identifier (1-BASE, 2-SHOULDER, 3-ELBOW, 4-EOAT)
            rad_angle (float): Target angle in radians
            speed (int): Speed in steps/s
            accel (int): Acceleration in steps/s^2
        """
        cmd = {
            'T': 101,
            'joint': joint_id,
            'rad': rad_angle,
            'spd': speed,
            'acc': accel
        }
        success = self.send_command(json.dumps(cmd), f"Control joint {joint_id}")
        if not success:
            self.node.get_logger().error(f"Failed to control joint {joint_id}")
        return success
    
    def control_all_joints(self, base=0, shoulder=0, elbow=0, wrist=0, roll=0, hand=0, speed=0, accel=10):
        """
        Control all joints simultaneously with angles in radians.
        
        Args:
            base (float): Base joint angle in radians
            shoulder (float): Shoulder joint angle in radians
            elbow (float): Elbow joint angle in radians
            wrist (float): Wrist joint angle in radians
            roll (float): Roll joint angle in radians
            hand (float): Hand joint angle in radians
            speed (int): Speed
            accel (int): Acceleration
        """
        cmd = {
            'T': 102,
            'base': base,
            'shoulder': shoulder,
            'elbow': elbow,
            'wrist': wrist,
            'roll': roll,
            'hand': hand,
            'spd': speed,
            'acc': accel
        }
        success = self.send_command(json.dumps(cmd), "Control all joints")
        if not success:
            self.node.get_logger().error("Failed to control all joints")
        return success
    
    def control_single_axis(self, axis, position, speed=0.25):
        """
        Control a single axis movement.
        
        Args:
            axis (int): Axis identifier (1-x, 2-y, 3-z, 4-t)
            position (float): Target position
            speed (float): Movement speed
        """
        cmd = {
            'T': 103,
            'axis': axis,
            'pos': position,
            'spd': speed
        }
        success = self.send_command(json.dumps(cmd), f"Control axis {axis}")
        if not success:
            self.node.get_logger().error(f"Failed to control axis {axis}")
        return success
    
    def control_position(self, x=235, y=0, z=234, t=0, r=0, g=0, speed=0.25):
        """
        Control arm to move to specific position coordinates.
        
        Args:
            x (float): X coordinate
            y (float): Y coordinate
            z (float): Z coordinate
            t (float): Angle t in radians
            r (float): Angle r in radians
            g (float): Grip angle in radians
            speed (float): Movement speed
        """
        cmd = {
            'T': 104,
            'x': x,
            'y': y,
            'z': z,
            't': t,
            'r': r,
            'g': g,
            'spd': speed
        }
        success = self.send_command(json.dumps(cmd), "Move to position")
        if not success:
            self.node.get_logger().error("Failed to move to position")
        return success
    
    def direct_position_control(self, x=235, y=0, z=234, t=0, r=0, g=0):
        """
        Control arm to move directly to position without interpolation.
        
        Args:
            x (float): X coordinate
            y (float): Y coordinate
            z (float): Z coordinate
            t (float): Angle t in radians
            r (float): Angle r in radians
            g (float): Grip angle in radians
        """
        cmd = {
            'T': 1041,
            'x': x,
            'y': y,
            'z': z,
            't': t,
            'r': r,
            'g': g
        }
        success = self.send_command(json.dumps(cmd), "Direct position control")
        if not success:
            self.node.get_logger().error("Failed direct position control")
        return success
    
    def control_gripper(self, angle, speed=0, accel=0):
        """
        Control the gripper/hand.
        
        Args:
            angle (float): Hand angle in radians (1.57=release, 0.0=grab)
            speed (int): Movement speed
            accel (int): Acceleration
        """
        cmd = {
            'T': 106,
            'cmd': angle,
            'spd': speed,
            'acc': accel
        }
        success = self.send_command(json.dumps(cmd), f"Control gripper: {angle}")
        if not success:
            self.node.get_logger().error("Failed to control gripper")
        return success
    
    def set_gripper_torque(self, torque=200):
        """
        Set the gripper/hand torque.
        
        Args:
            torque (int): Torque limit (default: 200)
        """
        cmd = {
            'T': 107,
            'tor': torque
        }
        success = self.send_command(json.dumps(cmd), f"Set gripper torque: {torque}")
        if not success:
            self.node.get_logger().error("Failed to set gripper torque")
        return success
    
    def set_joint_pid(self, joint_id, p=16, i=0):
        """
        Set PID parameters for a specific joint.
        
        Args:
            joint_id (int): Joint ID (1-BASE, 2-SHOULDER, 3-ELBOW, 4-EOAT)
            p (int): P component (default: 16)
            i (int): I component (default: 0)
        """
        cmd = {
            'T': 108,
            'joint': joint_id,
            'p': p,
            'i': i
        }
        success = self.send_command(json.dumps(cmd), f"Set joint {joint_id} PID: P={p}, I={i}")
        if not success:
            self.node.get_logger().error(f"Failed to set joint {joint_id} PID")
        return success
    
    def reset_pid(self):
        """Reset all PID parameters to default values."""
        cmd = {'T': 109}
        success = self.send_command(json.dumps(cmd), "Reset PID parameters")
        if not success:
            self.node.get_logger().error("Failed to reset PID parameters")
        return success
    
    def set_new_x_axis(self, angle=0):
        """
        Set a new X-axis orientation.
        
        Args:
            angle (float): New X-axis angle in radians
        """
        cmd = {
            'T': 110,
            'xAxisAngle': angle
        }
        success = self.send_command(json.dumps(cmd), f"Set new X-axis: {angle}")
        if not success:
            self.node.get_logger().error("Failed to set new X-axis")
        return success
    
    def set_delay(self, delay_ms=1000):
        """
        Set a delay in milliseconds in the command sequence.
        
        Args:
            delay_ms (int): Delay in milliseconds
        """
        cmd = {
            'T': 111,
            'cmd': delay_ms
        }
        success = self.send_command(json.dumps(cmd), f"Set delay: {delay_ms}ms")
        if not success:
            self.node.get_logger().error("Failed to set delay")
        return success
    
    def set_dynamic_adaptation(self, mode=1, base=60, shoulder=125, elbow=125, wrist=125, roll=125, hand=125):
        """
        Configure dynamic external force adaptation.
        
        Args:
            mode (int): 0=stop adaptation, 1=start adaptation
            base, shoulder, elbow, wrist, roll, hand: Torque limits for each joint
        """
        try:
            if mode == 0:
                # Reset all torque limits to 1000 (effectively disabling adaptation)
                b, s, e, t, r, h = 1000, 1000, 1000, 1000, 1000, 1000
                self.node.get_logger().info("Disabling dynamic adaptation (all limits set to 1000)")
            else:
                # Use the provided torque limits
                b, s, e, t, r, h = base, shoulder, elbow, wrist, roll, hand
                self.node.get_logger().info(f"Setting dynamic adaptation limits - base:{b} shoulder:{s} elbow:{e} wrist:{t} roll:{r} hand:{h}")
                
            cmd = {
                'T': 112,
                'mode': mode,
                'b': b,
                's': s,
                'e': e,
                't': t,
                'r': r,
                'h': h
            }
            
            # Send the command and wait for response
            cmd_str = json.dumps(cmd)
            self.node.get_logger().info(f"Sending dynamic adaptation command: {cmd_str}")
            success = self.send_command(cmd_str, f"Dynamic adaptation mode: {mode}")
            
            # Allow extra time for this command to take effect
            time.sleep(0.5)
            
            if not success:
                self.node.get_logger().error("Failed to set dynamic adaptation")
                
            return success
        except Exception as e:
            self.node.get_logger().error(f"Error in set_dynamic_adaptation: {e}")
            return False
    
    def control_light(self, brightness=255):
        """
        Control the LED light brightness.
        
        Args:
            brightness (int): Brightness level (0-255)
        """
        if not 0 <= brightness <= 255:
            self.node.get_logger().warn(f"Brightness value {brightness} out of range (0-255), clamping")
            brightness = max(0, min(brightness, 255))
            
        cmd = {
            'T': 114,
            'led': brightness
        }
        success = self.send_command(json.dumps(cmd), f"Control light: {brightness}")
        if not success:
            self.node.get_logger().error("Failed to control light")
        return success
    
    def control_switch(self, pwm_a=0, pwm_b=0):
        """
        Control the 12V switches.
        
        Args:
            pwm_a (int): PWM A value (-255 to +255)
            pwm_b (int): PWM B value (-255 to +255)
        """
        if not -255 <= pwm_a <= 255 or not -255 <= pwm_b <= 255:
            self.node.get_logger().warn("PWM values out of range (-255 to +255), clamping")
            pwm_a = max(-255, min(pwm_a, 255))
            pwm_b = max(-255, min(pwm_b, 255))
            
        cmd = {
            'T': 113,
            'pwm_a': pwm_a,
            'pwm_b': pwm_b
        }
        success = self.send_command(json.dumps(cmd), f"Control switch: A={pwm_a}, B={pwm_b}")
        if not success:
            self.node.get_logger().error("Failed to control switch")
        return success
    
    def switch_off(self):
        """Turn off all switches."""
        cmd = {'T': 115}
        success = self.send_command(json.dumps(cmd), "Switch off")
        if not success:
            self.node.get_logger().error("Failed to switch off")
        return success
    
    
    def control_joint_angle_degrees(self, joint_id, angle, speed=10, accel=10):
        """
        Control a single joint using angles in degrees.
        
        Args:
            joint_id (int): Joint identifier (1-BASE, 2-SHOULDER, 3-ELBOW, 4-EOAT)
            angle (float): Target angle in degrees
            speed (float): Speed in degrees/s
            accel (float): Acceleration in degrees/s^2 (max 22.5)
        """
        cmd = {
            'T': 121,
            'joint': joint_id,
            'angle': angle,
            'spd': speed,
            'acc': min(accel, 22.5)  # Cap acceleration at max
        }
        success = self.send_command(json.dumps(cmd), f"Control joint {joint_id} in degrees: {angle}°")
        if not success:
            self.node.get_logger().error(f"Failed to control joint {joint_id} in degrees")
        return success
    
    def control_all_joints_degrees(self, base=0, shoulder=0, elbow=90, wrist=0, roll=0, hand=180, speed=10, accel=10):
        """
        Control all joints simultaneously with angles in degrees.
        
        Args:
            base (float): Base joint angle in degrees
            shoulder (float): Shoulder joint angle in degrees
            elbow (float): Elbow joint angle in degrees
            wrist (float): Wrist joint angle in degrees
            roll (float): Roll joint angle in degrees
            hand (float): Hand joint angle in degrees
            speed (float): Speed in degrees/s
            accel (float): Acceleration in degrees/s^2 (max 22.5)
        """
        cmd = {
            'T': 122,
            'b': base,
            's': shoulder,
            'e': elbow,
            't': wrist,
            'r': roll,
            'h': hand,
            'spd': speed,
            'acc': min(accel, 22.5)  # Cap acceleration at max
        }
        success = self.send_command(json.dumps(cmd), "Control all joints in degrees")
        if not success:
            self.node.get_logger().error("Failed to control all joints in degrees")
        return success
    
    def constant_control(self, mode=0, axis=0, command=0, speed=3):
        """
        Apply constant control (continuous movement) to a joint or axis.
        
        Args:
            mode (int): 0=angle mode, 1=position mode
            axis (int): Joint/axis to control
            command (int): 0=stop, 1=increase, 2=decrease
            speed (float): Movement speed
        """
        cmd = {
            'T': 123,
            'm': mode,
            'axis': axis,
            'cmd': command,
            'spd': speed
        }
        success = self.send_command(json.dumps(cmd), f"Constant control: mode={mode}, axis={axis}, cmd={command}")
        if not success:
            self.node.get_logger().error("Failed to apply constant control")
        return success

    
    def set_middle_position(self, servo_id):
        """
        Set the current position as the middle position for a servo.
        
        Args:
            servo_id (int): Servo ID
        """
        cmd = {
            'T': 502,
            'id': servo_id
        }
        success = self.send_command(json.dumps(cmd), f"Set middle position for servo {servo_id}")
        if success:
            self.node.get_logger().info(f"Middle position set for servo {servo_id}")
        else:
            self.node.get_logger().error(f"Failed to set middle position for servo {servo_id}")
        return success
    
    def set_servo_pid(self, servo_id, p=16):
        """
        Set the P value of a single servo's PID.
        
        Args:
            servo_id (int): Servo ID
            p (int): P value
        """
        cmd = {
            'T': 503,
            'id': servo_id,
            'p': p
        }
        success = self.send_command(json.dumps(cmd), f"Set P={p} for servo {servo_id}")
        if not success:
            self.node.get_logger().error(f"Failed to set P value for servo {servo_id}")
        return success
    
    def get_free_flash_space(self):
        """Request free flash space information."""
        cmd = {'T': 601}
        success = self.send_command(json.dumps(cmd), "Request free flash space")
        if not success:
            self.node.get_logger().error("Failed to request free flash space")
        return success
    
    def clear_nvs(self):
        """Clear non-volatile storage in case of WiFi issues."""
        cmd = {'T': 604}
        success = self.send_command(json.dumps(cmd), "Clear NVS storage")
        if success:
            self.node.get_logger().info("NVS storage cleared")
        else:
            self.node.get_logger().error("Failed to clear NVS storage")
        return success
    
    def set_info_printing(self, mode=1):
        """
        Configure debug information printing level.
        
        Args:
            mode (int): 0=no debug info, 1=print debug info, 2=flow feedback
        """
        cmd = {
            'T': 605,
            'cmd': mode
        }
        success = self.send_command(json.dumps(cmd), f"Set debug print mode: {mode}")
        if not success:
            self.node.get_logger().error("Failed to set debug print mode")
        return success
    
    def reboot_controller(self):
        """Reboot the arm controller."""
        cmd = {'T': 600}
        success = self.send_command(json.dumps(cmd), "Reboot controller")
        if success:
            self.node.get_logger().info("Controller reboot requested")
        else:
            self.node.get_logger().error("Failed to request controller reboot")
        return success
