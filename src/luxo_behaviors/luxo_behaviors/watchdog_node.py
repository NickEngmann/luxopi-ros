#!/usr/bin/env python3
"""
Watchdog node for monitoring critical system topics and triggering recovery.

This node monitors critical topics like /luxo/current_state and /joint_states
to detect when nodes stop publishing (silent failure mode). When a failure is
detected, it can trigger various recovery mechanisms.
"""

import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timedelta

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import String, Header, Bool
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
from luxo_interfaces.msg import StateInfo
from luxo_interfaces.srv import RequestStateTransition
from action_msgs.msg import GoalStatusArray


class WatchdogNode(Node):
    """Monitors critical topics and triggers recovery when nodes fail."""
    
    def __init__(self):
        super().__init__('watchdog')
        
        # Parameters
        self.declare_parameter('state_timeout', 30.0)  # seconds
        self.declare_parameter('joint_timeout', 25.0)  # seconds
        self.declare_parameter('animation_timeout', 60.0)  # seconds without animation commands
        self.declare_parameter('serial_feedback_timeout', 5.0)  # seconds without position feedback
        self.declare_parameter('movement_source_timeout', 30.0)  # seconds without movement source updates
        self.declare_parameter('stuck_state_duration', 300.0)  # 5 minutes in same state
        self.declare_parameter('stuck_joint_duration', 120.0)  # 2 minutes without joint movement
        self.declare_parameter('recovery_delay', 10.0)  # seconds between recovery attempts
        self.declare_parameter('max_recovery_attempts', 3)
        self.declare_parameter('enable_node_restart', False)  # Whether to kill/restart nodes
        self.declare_parameter('enable_state_recovery', True)  # Whether to try state transitions
        
        # Get parameters
        self.state_timeout = self.get_parameter('state_timeout').value
        self.joint_timeout = self.get_parameter('joint_timeout').value
        self.animation_timeout = self.get_parameter('animation_timeout').value
        self.serial_feedback_timeout = self.get_parameter('serial_feedback_timeout').value
        self.movement_source_timeout = self.get_parameter('movement_source_timeout').value
        self.stuck_state_duration = self.get_parameter('stuck_state_duration').value
        self.stuck_joint_duration = self.get_parameter('stuck_joint_duration').value
        self.recovery_delay = self.get_parameter('recovery_delay').value
        self.max_recovery_attempts = self.get_parameter('max_recovery_attempts').value
        self.enable_node_restart = self.get_parameter('enable_node_restart').value
        self.enable_state_recovery = self.get_parameter('enable_state_recovery').value
        
        # Topic monitoring - timing
        self.last_state_msg = None
        self.last_joint_msg = None
        self.last_animation_cmd = None
        self.last_serial_feedback = None
        self.last_movement_source = None
        self.last_animation_status = None
        
        # Topic monitoring - content
        self.last_state_value = None
        self.last_state_change_time = None
        self.last_joint_positions = None
        self.last_joint_change_time = None
        
        # Failure detection flags
        self.state_failure_detected = False
        self.joint_failure_detected = False
        self.animation_failure_detected = False
        self.serial_failure_detected = False
        self.stuck_state_detected = False
        self.stuck_joints_detected = False
        self.silent_failure_detected = False
        
        # Recovery tracking
        self.recovery_attempts = {
            'state': 0, 'joint': 0, 'animation': 0, 
            'serial': 0, 'stuck': 0, 'silent': 0
        }
        self.last_recovery_time = {
            'state': None, 'joint': None, 'animation': None,
            'serial': None, 'stuck': None, 'silent': None
        }
        # Track when we've given up on recovery
        self.recovery_exhausted = {
            'state': None, 'joint': None, 'animation': None,
            'serial': None, 'stuck': None, 'silent': None
        }
        # Track last error log time to prevent spam
        self.last_error_log = {
            'state': None, 'joint': None, 'animation': None,
            'serial': None, 'stuck': None, 'silent': None
        }
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Subscribers - Core topics
        self.state_sub = self.create_subscription(
            StateInfo,
            '/luxo/current_state',
            self.state_callback,
            10
        )
        
        self.joint_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_callback,
            10
        )
        
        # Subscribers - Animation system
        self.animation_cmd_sub = self.create_subscription(
            String,
            '/roarm/animation_command',
            self.animation_cmd_callback,
            10
        )
        
        self.animation_status_sub = self.create_subscription(
            GoalStatusArray,
            '/animation_action/_action/status',
            self.animation_status_callback,
            10
        )
        
        # Subscribers - Serial communication
        self.serial_feedback_sub = self.create_subscription(
            String,
            '/roarm/position',
            self.serial_feedback_callback,
            10
        )
        
        # Subscribers - Movement coordination
        self.movement_source_sub = self.create_subscription(
            String,
            '/luxo/movement_source',
            self.movement_source_callback,
            10
        )
        
        # Publishers
        self.watchdog_status_pub = self.create_publisher(
            String,
            '/watchdog/status',
            10
        )
        
        # Service clients
        self.state_transition_client = self.create_client(
            RequestStateTransition,
            '/luxo/request_state_transition'
        )
        
        # Timer for periodic checks
        self.check_timer = self.create_timer(1.0, self.check_topics)
        
        # Timer for status publishing
        self.status_timer = self.create_timer(5.0, self.publish_status)
        
        # Timer for content validation
        self.content_timer = self.create_timer(2.0, self.check_content)
        
        # Timer for cross-topic correlation
        self.correlation_timer = self.create_timer(5.0, self.check_correlations)
        
        # Watchdog self-health
        self._last_check_time = time.time()
        self._check_count = 0
        self._startup_time = self.get_clock().now()
        
        self.get_logger().info('Watchdog node initialized')
        self.get_logger().info(f'Monitoring timeouts - State: {self.state_timeout}s, Joint: {self.joint_timeout}s')
    
    def state_callback(self, msg):
        """Record timestamp and content of state message."""
        with self.lock:
            self.last_state_msg = self.get_clock().now()
            
            # Track state changes
            if self.last_state_value != msg.current_state:
                self.last_state_value = msg.current_state
                self.last_state_change_time = self.get_clock().now()
                self.get_logger().info(f'State changed to: {msg.current_state}')
            
            if self.state_failure_detected:
                self.get_logger().info('State topic recovered')
                self.state_failure_detected = False
                self.recovery_attempts['state'] = 0
                self.recovery_exhausted['state'] = None
    
    def joint_callback(self, msg):
        """Record timestamp and positions of joint message."""
        with self.lock:
            # Always update the timestamp when we receive a message
            self.last_joint_msg = self.get_clock().now()
            
            # Track joint changes
            if msg.position and len(msg.position) >= 6:
                if self.last_joint_positions is None:
                    self.last_joint_positions = list(msg.position)
                    self.last_joint_change_time = self.get_clock().now()
                else:
                    # Check if joints have moved significantly (> 0.05 radians)
                    if any(abs(a - b) > 0.05 for a, b in zip(msg.position, self.last_joint_positions)):
                        self.last_joint_positions = list(msg.position)
                        self.last_joint_change_time = self.get_clock().now()
            
            # Clear failure state if it was detected
            if self.joint_failure_detected:
                self.get_logger().info('Joint topic recovered')
                self.joint_failure_detected = False
                self.recovery_attempts['joint'] = 0
                self.recovery_exhausted['joint'] = None
    
    def animation_cmd_callback(self, msg):
        """Record animation commands."""
        with self.lock:
            self.last_animation_cmd = self.get_clock().now()
            if self.animation_failure_detected:
                self.get_logger().info('Animation commands recovered')
                self.animation_failure_detected = False
                self.recovery_attempts['animation'] = 0
                self.recovery_exhausted['animation'] = None
    
    def animation_status_callback(self, msg):
        """Record animation action status."""
        with self.lock:
            self.last_animation_status = self.get_clock().now()
    
    def serial_feedback_callback(self, msg):
        """Record serial position feedback."""
        with self.lock:
            self.last_serial_feedback = self.get_clock().now()
            if self.serial_failure_detected:
                self.get_logger().info('Serial feedback recovered')
                self.serial_failure_detected = False
                self.recovery_attempts['serial'] = 0
                self.recovery_exhausted['serial'] = None
    
    def movement_source_callback(self, msg):
        """Record movement source updates."""
        with self.lock:
            self.last_movement_source = self.get_clock().now()
    
    def check_topics(self):
        """Check if topics are being published within timeout."""
        current_time = self.get_clock().now()
        
        # Update watchdog self-health
        self._last_check_time = time.time()
        self._check_count += 1
        
        with self.lock:
            # Calculate node uptime
            node_uptime = (current_time - self._startup_time).nanoseconds / 1e9
            
            # Check state topic
            if self.last_state_msg is None:
                # Give topics time to start publishing after node startup
                if node_uptime > 10.0:  # Only check after 10 seconds of node uptime
                    if not self.state_failure_detected:
                        self.state_failure_detected = True
                        self.get_logger().error('State topic never received after 10s startup grace period')
                        self.trigger_recovery('state')
            else:
                state_age = (current_time - self.last_state_msg).nanoseconds / 1e9
                if state_age > self.state_timeout:
                    if not self.state_failure_detected:
                        self.state_failure_detected = True
                        self.get_logger().error(f'State topic timeout detected! Last message {state_age:.1f}s ago')
                    # Always attempt recovery for persistent failures
                    self.trigger_recovery('state')
            
            # Check joint topic
            if self.last_joint_msg is None:
                # Give topics time to start publishing after node startup
                if node_uptime > 10.0:  # Only check after 10 seconds of node uptime
                    if not self.joint_failure_detected:
                        self.joint_failure_detected = True
                        self.get_logger().error('Joint topic never received after 10s startup grace period')
                        self.trigger_recovery('joint')
            else:
                joint_age = (current_time - self.last_joint_msg).nanoseconds / 1e9
                if joint_age > self.joint_timeout:
                    if not self.joint_failure_detected:
                        self.joint_failure_detected = True
                        self.get_logger().error(f'Joint topic timeout detected! Last message {joint_age:.1f}s ago')
                    # Always attempt recovery for persistent failures
                    self.trigger_recovery('joint')
            
            # Check animation commands (more lenient as not always active)
            if self.last_animation_cmd is not None:
                animation_age = (current_time - self.last_animation_cmd).nanoseconds / 1e9
                if animation_age > self.animation_timeout and not self.animation_failure_detected:
                    # Only flag if we're in a state that should be animating
                    if self.last_state_value in ['ANIMATING', 'IDLE']:
                        self.animation_failure_detected = True
                        self.get_logger().error(f'Animation timeout detected! Last command {animation_age:.1f}s ago in {self.last_state_value} state')
                        self.trigger_recovery('animation')
            
            # Check serial feedback
            if self.last_serial_feedback is not None:
                serial_age = (current_time - self.last_serial_feedback).nanoseconds / 1e9
                if serial_age > self.serial_feedback_timeout:
                    if not self.serial_failure_detected:
                        self.serial_failure_detected = True
                        self.get_logger().error(f'Serial feedback timeout detected! Last feedback {serial_age:.1f}s ago')
                    # Always attempt recovery for persistent failures
                    self.trigger_recovery('serial')
    
    def trigger_recovery(self, failure_type):
        """Trigger recovery mechanism based on failure type."""
        # Check if we've exhausted recovery attempts
        if self.recovery_exhausted[failure_type] is not None:
            # Only log periodically after exhaustion (every 5 minutes)
            time_since_exhausted = datetime.now() - self.recovery_exhausted[failure_type]
            if time_since_exhausted.total_seconds() > 300:  # 5 minutes
                # Reset and try again
                self.recovery_exhausted[failure_type] = None
                self.recovery_attempts[failure_type] = 0
                self.get_logger().info(f'Resetting {failure_type} recovery after 5 minute cooldown')
            else:
                # Don't spam logs - only log every 30 seconds
                if self.last_error_log[failure_type] is None or \
                   (datetime.now() - self.last_error_log[failure_type]).total_seconds() > 30:
                    self.get_logger().debug(f'Recovery exhausted for {failure_type}, waiting for cooldown')
                    self.last_error_log[failure_type] = datetime.now()
                return
        
        # Check recovery delay with exponential backoff
        if self.last_recovery_time[failure_type] is not None:
            # Exponential backoff: delay * 2^(attempt-1)
            backoff_delay = self.recovery_delay * (2 ** (self.recovery_attempts[failure_type] - 1))
            backoff_delay = min(backoff_delay, 120.0)  # Cap at 2 minutes
            
            time_since_last = datetime.now() - self.last_recovery_time[failure_type]
            if time_since_last.total_seconds() < backoff_delay:
                return
        
        # Check if we should attempt recovery
        if self.recovery_attempts[failure_type] >= self.max_recovery_attempts:
            if self.recovery_exhausted[failure_type] is None:
                self.get_logger().error(f'Max recovery attempts reached for {failure_type}, entering cooldown')
                self.recovery_exhausted[failure_type] = datetime.now()
            return
        
        self.recovery_attempts[failure_type] += 1
        self.last_recovery_time[failure_type] = datetime.now()
        
        self.get_logger().warning(f'Attempting recovery for {failure_type} (attempt {self.recovery_attempts[failure_type]}/{self.max_recovery_attempts})')
        
        # Try different recovery strategies
        if failure_type == 'state':
            self.recover_state_manager()
        elif failure_type == 'joint':
            self.recover_hardware_interface()
        elif failure_type == 'animation':
            self.recover_animation_system()
        elif failure_type == 'serial':
            self.recover_serial_communication()
        elif failure_type == 'stuck':
            self.recover_stuck_system()
        elif failure_type == 'silent':
            self.recover_silent_failure()
    
    def recover_state_manager(self):
        """Attempt to recover the state manager."""
        if self.enable_state_recovery:
            # Try requesting a state transition to force state manager to respond
            self.get_logger().info('Attempting state transition to IDLE to recover state manager')
            
            if self.state_transition_client.wait_for_service(timeout_sec=2.0):
                request = RequestStateTransition.Request()
                request.requested_state = 'IDLE'
                request.requesting_node = 'watchdog'
                request.priority = 90
                request.force = True
                request.completion = False
                
                future = self.state_transition_client.call_async(request)
                future.add_done_callback(self.state_transition_callback)
            else:
                self.get_logger().error('State transition service not available')
                
                # If service not available, might need node restart
                if self.enable_node_restart:
                    self.restart_node('state_manager')
    
    def recover_hardware_interface(self):
        """Attempt to recover the hardware interface."""
        if self.enable_state_recovery:
            # Try transitioning through states to reset hardware
            self.get_logger().info('Attempting state transition to RETURNING_HOME to recover hardware')
            
            if self.state_transition_client.wait_for_service(timeout_sec=2.0):
                request = RequestStateTransition.Request()
                request.requested_state = 'RETURNING_HOME'
                request.requesting_node = 'watchdog'
                request.priority = 90
                request.force = True
                request.completion = False
                
                future = self.state_transition_client.call_async(request)
                future.add_done_callback(self.state_transition_callback)
            else:
                self.get_logger().error('State transition service not available')
                
                # If service not available, might need node restart
                if self.enable_node_restart:
                    self.restart_node('hardware_interface')
    
    def state_transition_callback(self, future):
        """Handle state transition response."""
        try:
            response = future.result()
            if response.success:
                self.get_logger().info('Recovery state transition successful')
            else:
                self.get_logger().error(f'Recovery state transition failed: {response.message}')
        except Exception as e:
            self.get_logger().error(f'State transition failed: {str(e)}')
    
    def restart_node(self, node_name):
        """Attempt to restart a specific node (requires node restart capability)."""
        if not self.enable_node_restart:
            self.get_logger().warning(f'Node restart disabled, cannot restart {node_name}')
            return
        
        self.get_logger().warning(f'Attempting to restart {node_name} node')
        
        # This is a placeholder - actual implementation would depend on how nodes are launched
        # Options include:
        # 1. Using lifecycle nodes (best approach)
        # 2. Sending signals to process
        # 3. Using a node manager service
        # 4. Triggering systemd restart
        
        # For now, log what would be done
        self.get_logger().error(f'Node restart not implemented - would restart {node_name}')
        
        # Could implement by finding and killing the process
        # try:
        #     # Find process by name
        #     result = subprocess.run(['pgrep', '-f', node_name], capture_output=True, text=True)
        #     if result.returncode == 0:
        #         pid = int(result.stdout.strip())
        #         os.kill(pid, signal.SIGTERM)
        #         self.get_logger().info(f'Sent SIGTERM to {node_name} (PID: {pid})')
        # except Exception as e:
        #     self.get_logger().error(f'Failed to restart {node_name}: {str(e)}')
    
    def recover_animation_system(self):
        """Recover the animation system."""
        self.get_logger().info('Attempting to recover animation system')
        
        # Try triggering an idle animation to kickstart the system
        if self.state_transition_client.wait_for_service(timeout_sec=2.0):
            # First try to go to IDLE
            request = RequestStateTransition.Request()
            request.requested_state = 'IDLE'
            request.requesting_node = 'watchdog'
            request.priority = 90
            request.force = True
            request.completion = False
            
            future = self.state_transition_client.call_async(request)
            future.add_done_callback(
                lambda f: self.get_logger().info('Animation recovery: Transitioned to IDLE')
            )
    
    def recover_serial_communication(self):
        """Recover serial communication."""
        self.get_logger().info('Attempting to recover serial communication')
        
        # Try RETURNING_HOME to force serial communication
        if self.state_transition_client.wait_for_service(timeout_sec=2.0):
            request = RequestStateTransition.Request()
            request.requested_state = 'RETURNING_HOME'
            request.requesting_node = 'watchdog'
            request.priority = 90
            request.force = True
            request.completion = False
            
            future = self.state_transition_client.call_async(request)
            future.add_done_callback(self.state_transition_callback)
    
    def recover_stuck_system(self):
        """Recover from stuck state or joints."""
        self.get_logger().info('Attempting to recover from stuck system')
        
        # Clear stuck flags
        with self.lock:
            self.stuck_state_detected = False
            self.stuck_joints_detected = False
        
        # Force a state transition cycle
        if self.state_transition_client.wait_for_service(timeout_sec=2.0):
            # Go to RETURNING_HOME then IDLE
            request = RequestStateTransition.Request()
            request.requested_state = 'RETURNING_HOME'
            request.requesting_node = 'watchdog'
            request.priority = 90
            request.force = True
            request.completion = False
            
            future = self.state_transition_client.call_async(request)
            future.add_done_callback(
                lambda f: self.get_logger().info('Stuck recovery: Initiated return home')
            )
    
    def recover_silent_failure(self):
        """Recover from silent failure mode."""
        self.get_logger().error('RECOVERING FROM SILENT FAILURE MODE')
        
        # This is the critical recovery for the 4+ hour issue
        # Try multiple recovery strategies in sequence
        
        # 1. Force state transition to break out of stuck logic
        if self.state_transition_client.wait_for_service(timeout_sec=2.0):
            request = RequestStateTransition.Request()
            request.requested_state = 'ERROR'  # Force ERROR state first
            request.requesting_node = 'watchdog'
            request.priority = 90
            request.force = True
            request.completion = False
            
            future = self.state_transition_client.call_async(request)
            future.add_done_callback(
                lambda f: self._silent_failure_recovery_phase2()
            )
    
    def _silent_failure_recovery_phase2(self):
        """Phase 2 of silent failure recovery."""
        # After ERROR state, transition to IDLE
        threading.Timer(2.0, lambda: self._request_idle_for_recovery()).start()
    
    def _request_idle_for_recovery(self):
        """Request IDLE state for recovery."""
        try:
            request = RequestStateTransition.Request()
            request.requested_state = 'IDLE'
            request.requesting_node = 'watchdog'
            request.priority = 90
            request.force = True
            request.completion = False
            
            future = self.state_transition_client.call_async(request)
            future.add_done_callback(
                lambda f: self.get_logger().info('Silent failure recovery: Returned to IDLE')
            )
            
            # Clear the silent failure flag after recovery attempt
            with self.lock:
                self.silent_failure_detected = False
                
        except Exception as e:
            self.get_logger().error(f'Failed to request IDLE: {e}')
    
    def publish_status(self):
        """Publish watchdog status."""
        with self.lock:
            status_parts = []
            current_time = self.get_clock().now()
            
            # Core topic status
            if self.last_state_msg is not None:
                state_age = (current_time - self.last_state_msg).nanoseconds / 1e9
                status_parts.append(f'State: {state_age:.1f}s')
                if self.last_state_value:
                    status_parts.append(f'({self.last_state_value})')
            else:
                status_parts.append('State: Never')
            
            if self.last_joint_msg is not None:
                joint_age = (current_time - self.last_joint_msg).nanoseconds / 1e9
                status_parts.append(f'Joint: {joint_age:.1f}s')
            else:
                status_parts.append('Joint: Never')
            
            # Animation and serial status
            if self.last_animation_cmd is not None:
                anim_age = (current_time - self.last_animation_cmd).nanoseconds / 1e9
                status_parts.append(f'Anim: {anim_age:.1f}s')
            
            if self.last_serial_feedback is not None:
                serial_age = (current_time - self.last_serial_feedback).nanoseconds / 1e9
                status_parts.append(f'Serial: {serial_age:.1f}s')
            
            # Content status
            if self.last_state_change_time is not None:
                state_duration = (current_time - self.last_state_change_time).nanoseconds / 1e9
                if state_duration > 60:
                    status_parts.append(f'StateFor: {state_duration/60:.1f}m')
            
            if self.last_joint_change_time is not None:
                joint_stillness = (current_time - self.last_joint_change_time).nanoseconds / 1e9
                if joint_stillness > 30:
                    status_parts.append(f'JointStill: {joint_stillness:.1f}s')
            
            # Failure indicators
            failures = []
            if self.state_failure_detected: failures.append('STATE')
            if self.joint_failure_detected: failures.append('JOINT')
            if self.animation_failure_detected: failures.append('ANIM')
            if self.serial_failure_detected: failures.append('SERIAL')
            if self.stuck_state_detected: failures.append('STUCK_STATE')
            if self.stuck_joints_detected: failures.append('STUCK_JOINT')
            if self.silent_failure_detected: failures.append('SILENT_FAIL')
            
            if failures:
                status_parts.append(f'FAIL: {",".join(failures)}')
            
            # Recovery attempts (only show non-zero)
            recoveries = []
            for key, count in self.recovery_attempts.items():
                if count > 0:
                    recoveries.append(f'{key}:{count}')
            if recoveries:
                status_parts.append(f'Recoveries: {",".join(recoveries)}')
            
            # Watchdog health
            watchdog_age = time.time() - self._last_check_time
            if watchdog_age > 5.0:
                status_parts.append(f'WATCHDOG_STUCK: {watchdog_age:.1f}s')
            
            status_msg = String()
            status_msg.data = ' | '.join(status_parts)
            self.watchdog_status_pub.publish(status_msg)
            
            # Only log if there's a failure or it's been a while
            if failures or self._check_count % 12 == 0:  # Log every minute when healthy
                self.get_logger().info(f'Watchdog: {status_msg.data}')


    def check_content(self):
        """Check for stuck states and joints."""
        current_time = self.get_clock().now()
        
        with self.lock:
            # Check for stuck state
            if (self.last_state_change_time is not None and 
                self.last_state_value is not None):
                state_duration = (current_time - self.last_state_change_time).nanoseconds / 1e9
                
                # Don't flag IDLE as stuck (it's normal to be idle for long periods)
                if (state_duration > self.stuck_state_duration and 
                    self.last_state_value not in ['IDLE', 'SHUTDOWN'] and
                    not self.stuck_state_detected):
                    self.stuck_state_detected = True
                    self.get_logger().error(
                        f'State stuck detected! In {self.last_state_value} for {state_duration:.1f}s'
                    )
                    self.trigger_recovery('stuck')
            
            # Check for stuck joints
            if self.last_joint_change_time is not None:
                joint_stillness = (current_time - self.last_joint_change_time).nanoseconds / 1e9
                
                # Only flag if we're in a state that should have movement
                if (joint_stillness > self.stuck_joint_duration and
                    self.last_state_value in ['ANIMATING', 'VOICE_FOLLOWING', 'COLLISION_AVOIDING'] and
                    not self.stuck_joints_detected):
                    self.stuck_joints_detected = True
                    self.get_logger().error(
                        f'Joints stuck detected! No movement for {joint_stillness:.1f}s in {self.last_state_value} state'
                    )
                    self.trigger_recovery('stuck')
    
    def check_correlations(self):
        """Check cross-topic correlations to detect silent failures."""
        current_time = self.get_clock().now()
        
        with self.lock:
            # Silent failure: System metrics continue but no commands
            if (self.last_state_msg is not None and 
                self.last_joint_msg is not None):
                
                # Check if we're getting state/joint updates but no animation commands
                if self.last_animation_cmd is not None:
                    animation_age = (current_time - self.last_animation_cmd).nanoseconds / 1e9
                    state_age = (current_time - self.last_state_msg).nanoseconds / 1e9
                    
                    # If state is updating but animations aren't in an active state
                    if (state_age < 5.0 and  # State is updating
                        animation_age > 120.0 and  # No animations for 2 minutes
                        self.last_state_value in ['IDLE', 'ANIMATING'] and
                        not self.silent_failure_detected):
                        
                        self.silent_failure_detected = True
                        self.get_logger().error(
                            f'SILENT FAILURE detected! State updating but no animations for {animation_age:.1f}s'
                        )
                        self.trigger_recovery('silent')
                
                # Check if serial feedback stopped while joints are updating
                if self.last_serial_feedback is not None:
                    serial_age = (current_time - self.last_serial_feedback).nanoseconds / 1e9
                    joint_age = (current_time - self.last_joint_msg).nanoseconds / 1e9
                    
                    if (joint_age < 5.0 and  # Joints updating
                        serial_age > 10.0 and  # No serial feedback
                        not self.serial_failure_detected):
                        
                        self.get_logger().warning(
                            'Correlation failure: Joint states updating but no serial feedback'
                        )


def main(args=None):
    rclpy.init(args=args)
    
    watchdog = WatchdogNode()
    
    try:
        rclpy.spin(watchdog)
    except KeyboardInterrupt:
        pass
    finally:
        watchdog.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()