#!/usr/bin/env python3
#animation_command.py
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import Bool, String
from sensor_msgs.msg import JointState
from luxo_interfaces.action import PlayAnimation
from luxo_interfaces.srv import RequestStateTransition
import time
import json
import uuid
from luxo_behaviors.joint_motion import (
    URDF_JOINT_LIMITS,
    clamp_joint_positions,
    format_target_positions,
)
import threading
from typing import Dict, List, Optional

# Import the base plugin class
from luxo_behaviors.animation_plugin_base import AnimationPlugin
# Import state machine classes and utilities
from luxo_behaviors.state_machine import LuxoState
from luxo_behaviors.shared_utils import StateUtils
from luxo_behaviors.motion_control import (
    AnimationGoalTracker, collision_status_from_warnings, scaled_duration,
)
from luxo_behaviors.sim_interaction_rules import animation_state_for
from luxo_behaviors.joint_profiles import ROARM_M3_NAMES, ROARM_M3_LIMITS, animation_pose_for_profile
from luxo_behaviors.animation_capabilities import load_animation_plugins
from luxo_behaviors.animation_plan import validate_animation_plan
from luxo_behaviors.trajectory_timing import retime_cubic_plan
from luxo_behaviors.continuous_trajectory import ContinuousTrajectory
from luxo_behaviors.joint_profiles import pose_to_animation_positions, joint_profile
import math



class AnimationCommandActionServer(Node):
    def __init__(self):
        super().__init__('animation_command')

        # Parameter to control if this node should publish joint states
        self.declare_parameter('publish_joint_states_target', True)
        self.should_publish = self.get_parameter('publish_joint_states_target').get_parameter_value().bool_value

        # Parameter to control which joint names to use (for hardware compatibility)
        self.declare_parameter('use_hardware_joint_names', False)
        self.use_hardware_joint_names = self.get_parameter('use_hardware_joint_names').get_parameter_value().bool_value
        self.declare_parameter('joint_profile', 'urdf4')
        self.joint_profile = str(self.get_parameter('joint_profile').value).lower()
        self.current_gripper_position = 0.0
        self.declare_parameter('enable_feasible_retiming', False)
        self.declare_parameter('enable_continuous_retiming', False)
        self.declare_parameter('max_joint_velocity', 0.5)
        self.declare_parameter('max_joint_acceleration', 1.0)
        self.enable_feasible_retiming = bool(self.get_parameter('enable_feasible_retiming').value)
        self.enable_continuous_retiming = bool(self.get_parameter('enable_continuous_retiming').value)
        if self.enable_continuous_retiming and not self.enable_feasible_retiming:
            raise ValueError('Continuous timing requires bounded simulation feedback')
        self.max_joint_velocity = float(self.get_parameter('max_joint_velocity').value)
        self.max_joint_acceleration = float(self.get_parameter('max_joint_acceleration').value)
        if self.enable_feasible_retiming and self.use_hardware_joint_names:
            raise ValueError('Feasible retiming requires calibrated simulation feedback')
        self._sim_feedback = None
        self._sim_motion_status = None
        if self.enable_feasible_retiming:
            self.create_subscription(String, '/sim/motion_status', self.sim_motion_status_callback, 10)

        # Parameter to control which topic to publish to (hardware vs simulation)
        self.declare_parameter('publish_target_topic', False)
        self.publish_target = self.get_parameter('publish_target_topic').get_parameter_value().bool_value

        # Joint limits configuration
        self.joint_limits = {
            name: {'min': lower, 'max': upper}
            for name, (lower, upper) in URDF_JOINT_LIMITS.items()
        }
        if self.joint_profile in {'roarm_m3', 'm3', 'm3_6'} and not self.use_hardware_joint_names:
            self.joint_limits = {
                name: {'min': lower, 'max': upper}
                for name, (lower, upper) in ROARM_M3_LIMITS.items()
            }

        self.declare_parameter('enforce_joint_limits', True)
        self.enforce_joint_limits = self.get_parameter('enforce_joint_limits').value

        # Hardware position feedback parameter
        self.declare_parameter('use_hardware_position_feedback', False)
        self.use_hardware_position_feedback = self.get_parameter('use_hardware_position_feedback').get_parameter_value().bool_value

        # Hardware position feedback
        self.hardware_position_received = False

        # Create subscription for hardware position feedback
        if self.use_hardware_position_feedback:
            self.position_subscription = self.create_subscription(
                String,
                'roarm/position',
                self.position_feedback_callback,
                10)
            self.get_logger().info('Subscribed to roarm/position for hardware feedback')
        if not self.use_hardware_joint_names:
            self.position_subscription = self.create_subscription(
                JointState, '/joint_states', self.sim_profile_feedback_callback, 10
            )

        # Create subscription for animation commands (backward compatibility)
        self.command_subscription = self.create_subscription(
            String,
            '/roarm/animation_command',
            self.command_callback,
            10)

        # Create publisher for joint states
        joint_topic = '/joint_states_target' if self.publish_target else '/joint_states'
        self.joint_publisher = self.create_publisher(
            JointState,
            joint_topic,
            10)

        # Publisher for current animation status
        self.current_animation_publisher = self.create_publisher(
            String,
            '/roarm/current_animation',
            10
        )

        self.get_logger().info(f'Publishing joint states to: {joint_topic}')
        self.get_logger().info('Publishing animation status to: /roarm/current_animation')

        # Current joint positions
        self.current_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0]  # base, shoulder, elbow, wrist, hand, acceleration
        self.target_positions = self.current_positions.copy()

        self.behavior_coordinator = None
        self.node = None  # Will be set by hardware interface (replaces state_machine)

        # Track current state (received from global state manager)
        self.current_state = LuxoState.INITIALIZING
        self.state_lock = threading.Lock()

        # State manager communication
        self.state_client = self.create_client(
            RequestStateTransition,
            '/luxo/request_state_transition'
        )

        # Subscribe to state updates
        self.state_subscription = self.create_subscription(
            String,
            '/luxo/current_state',
            self.state_update_callback,
            10
        )

        # Define joint names
        if self.use_hardware_joint_names:
            self.joint_names = ['base', 'shoulder', 'elbow', 'wrist', 'hand']
            self.get_logger().info('Using hardware joint names for RoArm compatibility')
        elif self.joint_profile in {'roarm_m3', 'm3', 'm3_6'}:
            self.joint_names = list(ROARM_M3_NAMES)
            self.get_logger().info('Using canonical six-axis RoArm-M3 simulation profile')
        else:
            # The checked-in RoArm URDF models four revolute joints. Keep the
            # visualization publisher aligned with that model; the fifth
            # actuator and acceleration slot are hardware-only.
            self.joint_names = ['base_to_L1', 'L1_to_L2', 'L2_to_L3', 'L3_to_L4']

        # Timer for regular publishing
        self.timer = self.create_timer(0.25, self.publish_joint_states_target)

        # Animation state
        self.is_animating = False
        self.animation_steps = []
        self.current_step = 0
        self.step_durations = []
        self.animation_timer = None
        self.speed_multiplier = 1.0

        # Action server state
        self._goal_handle = None
        self._goal_lock = threading.Lock()
        self._goal_tracker = AnimationGoalTracker()
        self._target_intent_id = ""
        self._target_intent_sequence = 0
        # A replacement goal requests cancellation, then waits here until the
        # previous goal has stopped publishing targets.
        self._execution_lock = threading.Lock()

        # Movement source tracking
        self.movement_source = "idle"
        self.last_movement_source_change = self.get_clock().now()

        # DEMA control integration
        self.declare_parameter('enable_dema_integration', False)
        self.enable_dema_integration = False

        # Create publisher for movement type
        if self.enable_dema_integration:
            self.movement_source_publisher = self.create_publisher(
                String,
                '/roarm/movement_source',
                10
            )
            self.get_logger().info("Publishing movement source information for DEMA coordination")

        # Subscribe to collision status
        self.collision_status = "safe"
        self._legacy_collision_status = "safe"
        self._collision_warnings = {"front": False, "left": False, "right": False}
        self._atomic_sensor_status = {}
        self.collision_status_sub = self.create_subscription(
            String,
            '/collision_status_for_animation',
            self.collision_status_callback,
            10
        )
        self.declare_parameter('enable_collision_warning_inputs', False)
        if self.get_parameter('enable_collision_warning_inputs').value:
            self.sensor_status_sub = self.create_subscription(
                String, '/collision/sensor_status', self.sensor_status_callback, 10
            )
            self.collision_warning_subscriptions = [
                self.create_subscription(
                    Bool, topic, self._collision_warning_callback(direction), 10
                )
                for direction, topic in (
                    ('front', '/head_collision_warning'),
                    ('left', '/left_collision_warning'),
                    ('right', '/right_collision_warning'),
                )
            ]

        # Track if animation was preempted by collision
        self.collision_preempted = "danger" in self.collision_status
        self.animation_preemption_time = self.get_clock().now()

        # Track animation type for state machine
        self.animation_trigger_source = None  # 'command', 'emotion', 'action'

        # Load animation plugins
        self.animation_plugins = self._load_animation_plugins()
        self.get_logger().debug(f'Loaded {len(self.animation_plugins)} animation plugins')

        # Create action server
        self._action_server = ActionServer(
            self,
            PlayAnimation,
            'play_animation',
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            handle_accepted_callback=self.handle_accepted_callback,
            cancel_callback=self.cancel_callback,
            callback_group=ReentrantCallbackGroup()
        )
        # Legacy command publishers enter the exact same action arbiter as the
        # panel. This keeps cancellation/preemption and state ownership unified.
        self._compat_action_client = ActionClient(self, PlayAnimation, 'play_animation')

        # Initialize ROS time tracking
        self._init_time_tracking()

        # Maximum attempts to get hardware position
        self.max_position_attempts = 10
        self.position_request_interval = 0.5

        self.get_logger().info('Animation command action server initialized')
        self.get_logger().info(f'Available animations: {", ".join(self.animation_plugins.keys())}')
        self.get_logger().info(f'Publishing to topic: {joint_topic}')
        self.get_logger().info(f'Publish enabled: {self.should_publish}')
        self.get_logger().info(f'Hardware joint names: {self.use_hardware_joint_names}')
        self.get_logger().info(f'Joint names: {self.joint_names}')

        # Initialize hardware position if enabled
        if self.use_hardware_position_feedback:
            self.request_hardware_position()

    def state_update_callback(self, msg):
        """Handle state updates from global state manager"""
        try:
            new_state = LuxoState[msg.data.upper()]
            with self.state_lock:
                if self.current_state != new_state:
                    old_state = self.current_state
                    self.current_state = new_state
                    self.get_logger().debug(f"Animation node state updated: {old_state.name} -> {new_state.name}")
        except KeyError:
            self.get_logger().warn(f"Unknown state received: {msg.data}")
        except Exception as e:
            self.get_logger().error(f"Error in animation state update callback: {e}")

    def is_in_state(self, *states: LuxoState) -> bool:
        """Check if currently in any of the given states"""
        with self.state_lock:
            return self.current_state in states

    def get_current_state(self) -> LuxoState:
        """Get current state"""
        with self.state_lock:
            return self.current_state

    def request_state_transition(self, requested_state: LuxoState, priority: int = 50, force: bool = False, completion: bool = False):
        """Request a state transition from the global state manager"""
        return StateUtils.request_state_transition(self, requested_state, priority, force, completion)

    def _request_transition_and_wait(self, requested_state, priority, timeout=2.0):
        """Wait for the state manager's actual decision before moving."""
        if not self.state_client.service_is_ready():
            self.get_logger().warning('State manager unavailable; refusing animation start')
            return False
        request = RequestStateTransition.Request()
        request.requested_state = requested_state.name
        request.requesting_node = 'animation_command'
        request.priority = int(priority)
        request.force = False
        request.completion = False
        done = threading.Event()
        decision = {'accepted': False, 'message': 'state transition timed out'}
        future = self.state_client.call_async(request)

        def complete(result_future):
            try:
                response = result_future.result()
                decision['accepted'] = bool(response.success)
                decision['message'] = response.message
            except Exception as exc:
                decision['message'] = str(exc)
            finally:
                done.set()

        future.add_done_callback(complete)
        if not done.wait(timeout):
            self.get_logger().error(f'Timed out awaiting {requested_state.name} state grant')
            return False
        if not decision['accepted']:
            self.get_logger().warning(
                f'State manager denied {requested_state.name}: {decision["message"]}'
            )
        return decision['accepted']

    def set_collision_avoidance(self, behavior_coordinator):
        """Set the collision avoidance reference from hardware interface."""
        self.behavior_coordinator = behavior_coordinator
        self.get_logger().info("Collision avoidance reference set in animation command")

    def set_node(self, node):
        """Set the node reference from hardware interface (replaces set_state_machine)."""
        self.node = node
        self.get_logger().info("Node reference set in animation command")

    def _init_time_tracking(self):
        """Initialize all ROS time tracking variables."""
        now = self.get_clock().now()
        self._last_debug_time = now
        self._last_position_log_time = now
        self._last_movement_source_log_time = now
        self._last_source_log = now
        self.last_animation_end_time = now
        self.last_valid_positions = [0.0] * 5
        self.idle_reset_timer = None

    def collision_status_callback(self, msg):
        """Update collision status from collision avoidance system."""
        self._legacy_collision_status = msg.data
        self._refresh_collision_status()

    def _collision_warning_callback(self, direction):
        """Track warning telemetry; Bool input alone never implies danger."""
        def receive(message):
            self._collision_warnings[direction] = bool(message.data)
            self._refresh_collision_status()
        return receive

    def sensor_status_callback(self, message):
        """Use atomic classifier severity for action preemption decisions."""
        try:
            payload = json.loads(message.data)
            direction = payload['direction']
            if direction not in ('front', 'left', 'right'):
                return
            active = bool(payload['active'])
            severity = str(payload['severity']).lower()
            valid = bool(payload['valid'])
            if severity not in ('safe', 'warning', 'danger', 'contact', 'imminent'):
                return
            self._atomic_sensor_status[direction] = {
                'active': active, 'severity': severity, 'valid': valid,
            }
            self._refresh_collision_status()
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.get_logger().warning(f"Rejected malformed collision sensor status: {exc}")

    def _refresh_collision_status(self):
        legacy = collision_status_from_warnings(
            self._legacy_collision_status, self._collision_warnings.values()
        )
        atomic = [
            f"{direction}:{sample['severity']}"
            for direction, sample in self._atomic_sensor_status.items()
            if sample['active'] or sample['severity'] != 'safe'
        ]
        if 'danger' in legacy:
            self.collision_status = legacy
        elif any(any(level in item for level in (':danger', ':contact', ':imminent'))
                 for item in atomic):
            self.collision_status = 'danger:' + ','.join(atomic)
        elif atomic:
            self.collision_status = 'warning:' + ','.join(atomic)
        else:
            self.collision_status = legacy

        # Check if this is a danger status while we have an active goal
        if "danger" in self.collision_status and self._goal_handle and self._goal_handle.is_active:
            self.get_logger().warn(f"Collision danger detected during animation: {self.collision_status}")
            # Safety interruption is independent of whether the goal may be
            # replaced by another ordinary animation (visual cues opt out of
            # ordinary preemption but must still yield to collision handling).
            self.collision_preempted = True

    def _load_animation_plugins(self) -> Dict[str, AnimationPlugin]:
        """Load the canonical, ROS-independent catalog after strict plan validation."""
        plugins = load_animation_plugins(self)
        for name in plugins:
            self.get_logger().debug(f"Loaded animation capability: {name}")
        return plugins

    def goal_callback(self, goal_request):
        """Decide whether to accept or reject a goal request."""
        self.get_logger().debug(f'Received animation goal request: {goal_request.animation_name}')

        # Check if animation exists
        if goal_request.animation_name not in self.animation_plugins:
            self.get_logger().warn(f'Unknown animation: {goal_request.animation_name}')
            return GoalResponse.REJECT

        # Check if state allows animation
        if not self._can_start_animation():
            self.get_logger().warn(f'Cannot start animation in current state: {self.get_current_state().name}')
            return GoalResponse.REJECT

        # Non-interrupting behavior cues are best-effort presentation. They
        # never displace a real action; interruptible commands can still
        # replace a cue through this same action arbiter.
        with self._goal_lock:
            if (self._goal_handle is not None and self._goal_handle.is_active
                    and not goal_request.allow_interruption):
                self.get_logger().debug('Ignoring a non-interrupting cue while an action is active')
                return GoalResponse.REJECT

        # Accept the goal
        return GoalResponse.ACCEPT

    def _can_start_animation(self) -> bool:
        """Check if current state allows starting an animation."""
        # Check if we can transition to ANIMATING or EMOTION_REACTING
        allowed_states = [
            LuxoState.IDLE,
            LuxoState.ANIMATING,  # Allow if already animating
            LuxoState.EMOTION_REACTING,  # Allow if already reacting
            LuxoState.USER_CONTROL, # Allow if in user control mode
            LuxoState.RETURNING_HOME,  # Allow animations to interrupt return to home
            LuxoState.PETTING,  # Petting responses keep PETTING as the current owner
        ]

        return self.is_in_state(*allowed_states)

    def _determine_animation_state(self, animation_name: str, trigger_source: str = "") -> LuxoState:
        """Determine which state to transition to based on animation type."""
        # Get the plugin to check its category
        plugin = self.animation_plugins.get(animation_name)
        if not plugin:
            return LuxoState.ANIMATING

        # Check animation category
        category = plugin.get_category()

        return animation_state_for(category, trigger_source or self.animation_trigger_source)

    def handle_accepted_callback(self, goal_handle):
        """Start executing an accepted goal."""
        with self._goal_lock:
            # Cancel any existing goal
            if self._goal_handle is not None and self._goal_handle.is_active:
                self.get_logger().info('Cancelling previous animation goal')
                self._goal_tracker.cancel(self._goal_handle)

            self._goal_handle = goal_handle
            self._goal_tracker.accept(goal_handle)

        # Execute the goal immediately
        goal_handle.execute()

    def cancel_callback(self, goal_handle):
        """Accept or reject a cancel request."""
        self.get_logger().info('Received cancel request')
        with self._goal_lock:
            self._goal_tracker.cancel(goal_handle)
        return CancelResponse.ACCEPT

    def execute_callback(self, goal_handle):
        """Execute the animation goal (called by action server)."""
        try:
            with self._execution_lock:
                return self._execute_animation(goal_handle)
        finally:
            self._goal_tracker.finish(goal_handle)

    def _execute_animation(self, goal_handle):
        """Execute animation in the action server thread."""
        start_time = time.time()
        self._safety_intent_started = None
        collision_interruptions = 0
        final_state = "completed"
        cancel_event = self._goal_tracker.event_for(goal_handle)

        # Reset collision preemption flag
        self.collision_preempted = "danger" in self.collision_status
        state_transition_owned = False

        try:
            goal = goal_handle.request
            animation_name = goal.animation_name
            speed_multiplier = goal.speed_multiplier if 0.1 <= goal.speed_multiplier <= 2.0 else 1.0

            # A goal may be replaced while waiting for the execution lock.
            # Do not publish status or transition the robot for an already
            # superseded request.
            if cancel_event.is_set():
                result = PlayAnimation.Result()
                result.success = False
                result.message = f"Animation {animation_name} preempted before start"
                result.actual_duration = 0.0
                result.collision_interruptions = 0
                result.final_state = (
                    "canceled" if goal_handle.is_cancel_requested else "preempted"
                )
                result.final_positions = list(self.current_positions)
                if goal_handle.is_active:
                    if goal_handle.is_cancel_requested:
                        goal_handle.canceled()
                    else:
                        goal_handle.abort()
                return result

            # One stable identity covers every interpolated keyframe and idle
            # hold emitted for this goal. Repeated values or changing values
            # within the same plan are not a new post-hazard intent.
            goal_id = getattr(goal_handle, 'goal_id', None)
            raw_uuid = getattr(goal_id, 'uuid', ())
            try:
                uuid_bytes = bytes(raw_uuid)
            except (TypeError, ValueError):
                uuid_bytes = b''
            if len(uuid_bytes) == 16:
                goal_intent_id = str(uuid.UUID(bytes=uuid_bytes))
            else:
                self._target_intent_sequence += 1
                goal_intent_id = f"animation-goal-{self._target_intent_sequence}"

            self.get_logger().info(
                f'Executing animation: {animation_name} with speed {speed_multiplier}'
            )

            # Publish animation name
            anim_msg = String()
            anim_msg.data = animation_name
            self.current_animation_publisher.publish(anim_msg)

            # USER_CONTROL owns its voice session at priority 80. Animations
            # triggered during that session run inside it; they must not try a
            # lower-priority ANIMATING transition and then move after denial.
            if self.get_current_state() != LuxoState.USER_CONTROL:
                target_state = self._determine_animation_state(
                    animation_name, getattr(goal, "trigger_source", "")
                )
                if not self._request_transition_and_wait(target_state, priority=50):
                    result = PlayAnimation.Result()
                    result.success = False
                    result.message = f"State manager did not grant {target_state.name}; animation not started"
                    result.actual_duration = 0.0
                    result.collision_interruptions = 0
                    result.final_state = "rejected"
                    result.final_positions = list(self.current_positions)
                    goal_handle.abort()
                    return result
                state_transition_owned = True

            # Get the animation plugin
            plugin = self.animation_plugins[animation_name]

            # Get hardware position if requested
            if goal.use_hardware_feedback and self.use_hardware_position_feedback:
                self.request_hardware_position()

            # Get keyframes and durations
            keyframes, durations = validate_animation_plan(
                *plugin.get_keyframes(), keyframe_names=plugin.get_keyframe_names()
            )
            keyframe_names = plugin.get_keyframe_names()

            # Adjust keyframes to use current base position
            if not hasattr(plugin, 'preserve_base_position') or plugin.preserve_base_position:
                current_base = self.current_positions[0] if self.current_positions else 0.0
                keyframes = plugin.adjust_keyframes_to_current_base(keyframes, current_base)
                self.get_logger().info(f"Adjusted animation to current base position: {current_base:.2f}")

            # Prepare keyframes for current position
            if self.hardware_position_received:
                keyframes = plugin.prepare_for_current_position(
                    self.current_positions, keyframes
                )

            continuous_plan = None
            if self.enable_feasible_retiming:
                if self._sim_feedback is None or time.monotonic() - self._sim_feedback[0] > .5:
                    raise RuntimeError('Fresh joint feedback is required before an animation')
                # Retime the actual clamped profile targets, not metadata or an
                # unreachable recipe target. The gripper remains independently held.
                bounded_frames = []
                axes = min(5, len(joint_profile(self.joint_profile)[0]))
                for frame in keyframes:
                    _, mapped = animation_pose_for_profile(frame, self.joint_profile,
                        gripper_position=self.current_gripper_position)
                    bounded = list(frame)
                    bounded[:axes] = mapped[:axes]
                    bounded_frames.append(bounded)
                keyframes = bounded_frames
                planner = ContinuousTrajectory if self.enable_continuous_retiming else retime_cubic_plan
                timed = planner(
                    self.current_positions, keyframes, durations,
                    speed_multiplier=speed_multiplier,
                    max_velocity=self.max_joint_velocity,
                    max_acceleration=self.max_joint_acceleration, axes=axes)
                if self.enable_continuous_retiming:
                    continuous_plan = timed
                    durations = timed.durations
                else:
                    durations = timed
                speed_multiplier = 1.0  # Already applied exactly once before retiming.
                self.target_positions = list(self.current_positions)

            # Apply speed multiplier
            self.speed_multiplier = speed_multiplier  # Set the instance variable
            adjusted_durations = [d / speed_multiplier for d in durations]

            # Set movement source
            self.movement_source = "animation"
            self.last_movement_source_change = self.get_clock().now()
            self.is_animating = True  # Set animation flag
            if continuous_plan is not None:
                self.current_animation_name = animation_name
                self.current_animation_publisher.publish(String(data=animation_name))

            # Execute animation with progress feedback
            total_duration = sum(adjusted_durations)

            for i, (keyframe, duration) in enumerate(zip(keyframes, durations)):
                # Cancellation belongs to this goal, not a server-wide flag.
                if cancel_event.is_set():
                    final_state = "canceled" if goal_handle.is_cancel_requested else "preempted"
                    self.get_logger().info(f"Animation stopped: {final_state}")
                    break

                # Check if goal handle is still valid before proceeding
                if not goal_handle.is_active:
                    final_state = "preempted"
                    self.get_logger().warn("Goal handle no longer active")
                    break

                # Check if we've been preempted by collision
                if self.collision_preempted:
                    final_state = "preempted"
                    self.get_logger().warn("Animation preempted by collision system")
                    break

                # Add noise to keyframe
                # Plans are reproducible; per-frame random noise is excluded
                # from the motor path.
                noisy_keyframe = keyframe

                # Use actual collision status
                collision_status = self.collision_status

                # Calculate progress
                elapsed_time = time.time() - start_time
                progress = min(1.0, elapsed_time / total_duration)
                time_remaining = max(0.0, total_duration - elapsed_time)

                # Publish feedback - with error handling
                try:
                    if goal_handle.is_active:
                        feedback = PlayAnimation.Feedback()
                        feedback.progress = progress
                        feedback.current_keyframe = i
                        feedback.total_keyframes = len(keyframes)
                        feedback.current_step_name = keyframe_names[i] if keyframe_names else f"Step {i+1}"
                        feedback.collision_status = collision_status
                        feedback.current_joints = list(self.current_positions)
                        feedback.time_remaining = time_remaining

                        goal_handle.publish_feedback(feedback)
                except Exception as e:
                    # If we can't publish feedback, it's likely the goal was canceled
                    self.get_logger().debug(f"Could not publish feedback: {e}")
                    # Don't break - continue animation if possible

                # Log keyframe execution
                self.get_logger().info(
                    f"Executing keyframe {i+1}/{len(keyframes)}: "
                    f"{feedback.current_step_name if 'feedback' in locals() else f'Step {i+1}'} -> {[round(p, 2) for p in noisy_keyframe]}"
                )

                # Move to position
                if continuous_plan is not None:
                    completed = self.follow_continuous_stage(
                        continuous_plan, i, cancel_event, goal_intent_id)
                else:
                    completed = self.move_to_position(
                        noisy_keyframe, duration, easing=True,
                        animation_name=animation_name, cancel_event=cancel_event,
                        target_intent_id=goal_intent_id)

                if not completed:
                    final_state = "canceled" if goal_handle.is_cancel_requested else "preempted"
                    break

                # If collision interrupted, increment counter
                if collision_status != "safe":
                    collision_interruptions += 1

            if final_state == "completed" and cancel_event.is_set():
                final_state = "canceled" if goal_handle.is_cancel_requested else "preempted"

            # A preempted goal may finish after its replacement is accepted.
            # Only the tracker owner may clear shared motion/session state.
            owns_shared_state = self._goal_tracker.is_current(goal_handle)
            if owns_shared_state:
                self.is_animating = False
            actual_duration = time.time() - start_time

            # Transition to IDLE state after animation completes
            if state_transition_owned and owns_shared_state:
                self.request_state_transition(
                    LuxoState.IDLE, priority=30, completion=True
                )
                self.get_logger().info(
                    f"Animation {final_state} - requesting owned-state completion"
                )

            # Create result
            result = PlayAnimation.Result()
            result.success = final_state == "completed"
            result.message = f"Animation {animation_name} {final_state}"
            result.actual_duration = actual_duration
            result.collision_interruptions = collision_interruptions
            result.final_state = final_state
            result.final_positions = list(self.current_positions)

            # Handle goal completion based on state
            # IMPORTANT: Check if goal handle is still valid before calling methods
            try:
                if goal_handle.is_active:
                    if final_state == "completed":
                        goal_handle.succeed()
                    elif final_state == "canceled":
                        goal_handle.canceled()
                    else:
                        # For any non-completed state, abort
                        goal_handle.abort()
                else:
                    self.get_logger().debug("Goal handle no longer active, skipping state update")
            except Exception as e:
                self.get_logger().debug(f"Could not update goal state: {e}")
                # Goal was likely already canceled/aborted

            return result

        except Exception as e:
            self.get_logger().error(f"Error executing animation: {e}")

            # Request transition to ERROR state on exception
            if self._goal_tracker.is_current(goal_handle):
                self.request_state_transition(LuxoState.ERROR, priority=100)

            # Create error result
            result = PlayAnimation.Result()
            result.success = False
            result.message = f"Animation failed: {str(e)}"
            result.actual_duration = time.time() - start_time
            result.collision_interruptions = collision_interruptions
            result.final_state = "aborted"
            result.final_positions = list(self.current_positions)

            # Try to abort the goal if it's still active
            try:
                if goal_handle.is_active:
                    goal_handle.abort()
            except Exception as abort_error:
                self.get_logger().debug(f"Could not abort goal: {abort_error}")

            return result
        finally:
            # Clear animation name when done
            if self._goal_tracker.is_current(goal_handle):
                anim_msg = String()
                anim_msg.data = ""
                self.current_animation_publisher.publish(anim_msg)

    def command_callback(self, msg):
        """Route legacy commands through the action server's single arbiter."""
        command_parts = msg.data.strip().lower().split()
        if not command_parts:
            self.get_logger().warning('Ignoring empty animation command')
            return
        base_command = command_parts[0]

        # Extract speed parameter if present
        speed = 1.0
        if len(command_parts) > 1:
            try:
                speed = float(command_parts[1])
                speed = max(0.1, min(2.0, speed))
            except ValueError:
                pass

        # Check if animation exists
        if base_command not in self.animation_plugins:
            self.get_logger().warn(f'Unknown animation command: {base_command}')
            self.get_logger().info(f'Available: {", ".join(self.animation_plugins.keys())}')
            return

        if not self._compat_action_client.server_is_ready():
            self.get_logger().warning('Animation action server unavailable; command not executed')
            return

        goal = PlayAnimation.Goal()
        goal.animation_name = base_command
        goal.speed_multiplier = speed
        goal.allow_interruption = True
        goal.use_hardware_feedback = False
        self._compat_action_client.send_goal_async(goal).add_done_callback(
            self._compat_goal_response
        )

    def _compat_goal_response(self, future):
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.get_logger().warning('Animation command was rejected by the action arbiter')
                return
            goal_handle.get_result_async().add_done_callback(self._compat_goal_result)
        except Exception as exc:
            self.get_logger().error(f'Animation command dispatch failed: {exc}')

    def _compat_goal_result(self, future):
        try:
            wrapped = future.result()
            if not wrapped.result.success:
                self.get_logger().warning(f'Animation command ended: {wrapped.result.message}')
        except Exception as exc:
            self.get_logger().error(f'Animation command result failed: {exc}')





    def position_feedback_callback(self, msg):
        """Handle position feedback from the hardware."""
        try:
            position_list = json.loads(msg.data)

            if isinstance(position_list, list) and len(position_list) >= 5:
                # Filter positions
                if self.current_positions is None:
                    self.current_positions = position_list.copy()
                else:
                    tolerance = 0.03
                    filtered_positions = position_list.copy()

                    for i in range(min(len(position_list), len(self.current_positions))):
                        diff = abs(float(position_list[i]) - float(self.current_positions[i]))
                        if diff < tolerance:
                            filtered_positions[i] = self.current_positions[i]

                    self.current_positions = filtered_positions

                if not self.is_animating:
                    self.target_positions = self.current_positions.copy()

                self.hardware_position_received = True

        except Exception as e:
            self.get_logger().error(f"Error parsing position feedback: {e}")

    def request_hardware_position(self):
        """Request and wait for hardware position before proceeding."""
        if not self.use_hardware_position_feedback:
            return True

        self.get_logger().info("Waiting for initial hardware position...")

        attempts = 0
        self.hardware_position_received = False

        while attempts < self.max_position_attempts and not self.hardware_position_received:
            time.sleep(self.position_request_interval)
            attempts += 1

        if self.hardware_position_received:
            self.get_logger().info("Hardware position received")
            return True
        else:
            self.get_logger().warn("Failed to get hardware position, using defaults")
            return False

    def sim_profile_feedback_callback(self, msg):
        """Observe actual profile feedback; metadata is never a physical axis."""
        try:
            names, _ = joint_profile(self.joint_profile)
            indexed = dict(zip(msg.name, msg.position))
            if len(msg.name) != len(msg.position) or set(msg.name) != set(names) or len(indexed) != len(names):
                return
            measured = [float(indexed[name]) for name in names]
            if not all(math.isfinite(value) for value in measured):
                return
            velocity = dict(zip(msg.name, msg.velocity)) if len(msg.velocity) == len(names) else {}
            speeds = [float(velocity.get(name, float('inf'))) for name in names]
            self._sim_feedback = (time.monotonic(), measured, speeds)
            if len(names) == 6:
                self.current_gripper_position = min(1.5, max(0.0, measured[5]))
            if self.enable_feasible_retiming:
                self.current_positions = pose_to_animation_positions(names, measured)
                self.hardware_position_received = True
        except (KeyError, TypeError, ValueError):
            return

    def _wait_for_simulated_pose(self, target, cancel_event):
        """Do not report a keyframe complete until actual feedback settles."""
        _, expected = animation_pose_for_profile(target, self.joint_profile,
            gripper_position=self.current_gripper_position)
        wait_started = time.monotonic()
        deadline = wait_started + 4.0
        stable_since = None
        while time.monotonic() < deadline:
            if (cancel_event is not None and cancel_event.is_set()) or self.collision_preempted:
                return False
            safety_reason = self._safety_interrupt_reason(wait_started)
            if safety_reason:
                self.get_logger().warning(safety_reason)
                return False
            sample = self._sim_feedback
            now = time.monotonic()
            settled = (sample is not None and now - sample[0] <= .3
                       and max(abs(a-b) for a,b in zip(expected, sample[1])) <= .02
                       and all(math.isfinite(v) and abs(v) <= .02 for v in sample[2]))
            if settled:
                stable_since = now if stable_since is None else stable_since
                if now - stable_since >= .06:
                    return True
            else:
                stable_since = None
            time.sleep(.01)
        if 'warning' in getattr(self, 'collision_status', ''):
            # The safety controller intentionally changed this course. Do not
            # turn an unreachable original target into an actuator fault.
            self.get_logger().warning('Adjusted course requires a new animation plan')
            return False
        raise RuntimeError('Actual joint feedback did not settle at the animation keyframe')

    def sim_motion_status_callback(self, message):
        try:
            payload = json.loads(message.data)
            mode = payload['avoidance_mode']
            if payload.get('exclusive_motion_owner') == 'returning_home':
                mode = 'hold_home_owned'
            elif payload.get('motion_hold_requested') and not str(mode).startswith('hold_'):
                mode = 'hold_state'
            if isinstance(mode, str):
                now = time.monotonic()
                previous = getattr(self, '_sim_motion_status', None)
                if (mode == 'adjust' and previous is not None
                        and previous[1] == 'adjust' and now - previous[0] <= .3):
                    adjust_since = previous[2]
                else:
                    adjust_since = now if mode == 'adjust' else None
                self._sim_motion_status = (now, mode, adjust_since)
        except (KeyError, TypeError, ValueError):
            return

    def _safety_interrupt_reason(self, stage_started):
        """End stale/held plans cleanly; bound time spent demonstrating retreat.

        A newly published stage gets a short grace period for the controller to
        receive it. Warning adjustments remain active long enough to demonstrate
        real redirected motion, then require a newly planned action. Danger is
        handled immediately by ``collision_preempted``.
        """
        if not getattr(self, 'enable_feasible_retiming', False):
            return None
        now = time.monotonic()
        intent_started = getattr(self, '_safety_intent_started', None)
        if intent_started is not None:
            stage_started = intent_started
        if now - stage_started < .15:
            return None
        safety = getattr(self, '_sim_motion_status', None)
        if safety is None:
            return 'Simulator motion status is unavailable; stopping the animation plan'
        if now - safety[0] > .3:
            return 'Simulator motion status is stale; stopping the animation plan'
        mode = safety[1]
        if mode.startswith('hold_'):
            return f'Safety hold ({mode}) requires a new animation plan'
        if mode == 'adjust':
            adjust_since = safety[2] if len(safety) > 2 else safety[0]
            if now - adjust_since >= 2.0:
                return 'Warning retreat was applied; stopping for a fresh animation plan'
        return None

    def publish_joint_states_target(self):
        """Publish target joint states."""
        if not self.should_publish:
            self.get_logger().debug("Publishing disabled by parameter")
            return

        # Check movement source status
        current_time = self.get_clock().now()

        if not self.is_animating and self.movement_source == "animation":
            if not hasattr(self, 'last_animation_end_time'):
                self.last_animation_end_time = current_time

            time_since_animation_end = (current_time - self.last_animation_end_time).nanoseconds / 1e9
            if time_since_animation_end > 3.0:
                self.movement_source = "idle"
                self.publish_movement_source()

                # Request transition to IDLE state
                self.request_state_transition(LuxoState.IDLE, priority=30)

        if self.is_animating:
            self.last_animation_end_time = current_time

        # Create joint state message
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._target_intent_id
        msg.name = self.joint_names

        try:
            if self.joint_profile in {'roarm_m3', 'm3', 'm3_6'} and not self.use_hardware_joint_names:
                _, joint_positions = animation_pose_for_profile(
                    self.target_positions, self.joint_profile,
                    gripper_position=self.current_gripper_position,
                    enforce_animation_roll=not self.enable_feasible_retiming,
                )
            else:
                joint_positions = format_target_positions(
                    self.target_positions,
                    self.joint_names,
                    include_acceleration=self.publish_target and self.use_hardware_joint_names,
                )

            validated_positions = [float(pos) for pos in joint_positions]

            if self.enforce_joint_limits:
                validated_positions = self.apply_joint_limits(msg.name, validated_positions)

            msg.position = validated_positions

            # Encode movement source in velocity field
            source_code = 0  # idle
            if self.movement_source == "animation":
                source_code = 1
            elif self.movement_source == "collision":
                source_code = 2
            elif self.movement_source == "user":
                source_code = 3

            msg.velocity = [float(source_code)]

            self.joint_publisher.publish(msg)

            # Add debug logging
            if self.is_animating:
                accel_info = f", accel: {validated_positions[5]}" if len(validated_positions) > 5 else ""
                self.get_logger().debug(f"Published joint states during animation: {[round(p, 2) for p in validated_positions[:5]]}{accel_info}")

        except Exception as e:
            self.get_logger().error(f"Error publishing joint states: {e}")

    def apply_joint_limits(self, joint_names, joint_positions):
        """Apply joint limits to positions."""
        limits = {
            name: (value['min'], value['max'])
            for name, value in self.joint_limits.items()
        }
        return clamp_joint_positions(joint_names, joint_positions, limits)

    def ease_in_out(self, t):
        """Cubic easing function for smoother motion."""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2

    def follow_continuous_stage(self, plan, index, cancel_event, intent_id):
        """Stream one bounded stage, preserving velocity through interior poses."""
        started = time.monotonic()
        duration = plan.durations[index]
        self._target_intent_id = intent_id
        while True:
            if cancel_event.is_set() or self.collision_preempted:
                return False
            progress = min(1.0, (time.monotonic() - started) / duration)
            self.target_positions = plan.segment(index, progress)
            self.publish_joint_states_target()
            if self._safety_intent_started is None:
                self._safety_intent_started = time.monotonic()
            safety_reason = self._safety_interrupt_reason(started)
            if safety_reason:
                self.get_logger().warning(safety_reason)
                return False
            if progress >= 1.0:
                break
            time.sleep(.01)
        if index == len(plan.frames)-1:
            return self._wait_for_simulated_pose(self.target_positions, cancel_event)
        return True

    def move_to_position(
        self, positions, duration=1.0, easing=True, animation_name=None,
        cancel_event=None, target_intent_id=None,
    ):
        """Move to a specific position over a duration with optional easing."""
        start_positions = self.target_positions.copy()
        start_time = self.get_clock().now()
        start_monotonic = time.monotonic()

        adjusted_duration = scaled_duration(duration, self.speed_multiplier)

        # Store current animation name for tracking
        if animation_name:
            self.current_animation_name = animation_name
            # Publish animation name
            anim_msg = String()
            anim_msg.data = animation_name
            self.current_animation_publisher.publish(anim_msg)

        # Handle acceleration value if present
        if len(positions) > 5:
            # Update target positions to include acceleration
            target_with_accel = positions[:6]  # Take first 6 elements
        else:
            # No acceleration provided, use default
            target_with_accel = list(positions[:5]) + [10.0]  # Default acceleration

        elapsed_time = 0.0
        while elapsed_time < adjusted_duration:
            if cancel_event is not None and cancel_event.is_set():
                return False
            if self.collision_preempted:
                return False

            current_time = self.get_clock().now()
            elapsed_time = (current_time - start_time).nanoseconds / 1e9
            progress = min(1.0, elapsed_time / adjusted_duration)

            if easing:
                eased_progress = self.ease_in_out(progress)
            else:
                eased_progress = progress

            # Update positions including acceleration
            for i in range(5):  # Only interpolate joint positions, not acceleration
                self.target_positions[i] = start_positions[i] + eased_progress * (target_with_accel[i] - start_positions[i])

            # Set acceleration directly (don't interpolate)
            if len(self.target_positions) > 5:
                self.target_positions[5] = target_with_accel[5]
            else:
                self.target_positions.append(target_with_accel[5])

            # IMPORTANT: Explicitly publish the joint states during movement
            if target_intent_id is not None:
                self._target_intent_id = target_intent_id
            self.publish_joint_states_target()
            if self.enable_feasible_retiming and self._safety_intent_started is None:
                self._safety_intent_started = time.monotonic()

            safety_reason = self._safety_interrupt_reason(start_monotonic)
            if safety_reason:
                self.get_logger().warning(safety_reason)
                return False

            time.sleep(0.01)

        # Final position update
        self.target_positions = list(target_with_accel)

        # Final publish at target position
        self.publish_joint_states_target()

        if self.enable_feasible_retiming:
            return self._wait_for_simulated_pose(target_with_accel, cancel_event)
        return True




    def _reset_to_idle(self):
        """Reset movement source to idle."""
        if self.movement_source != "idle":
            self.movement_source = "idle"
            self.get_logger().info('Movement source reset to idle')
            self.publish_movement_source()

            # Request transition to IDLE state
            self.request_state_transition(LuxoState.IDLE, priority=30)

        if self.idle_reset_timer:
            self.idle_reset_timer.cancel()
            self.idle_reset_timer = None

    def _reset_to_idle_once(self):
        """Reset to idle and cancel the timer (for one-shot timers)."""
        self._reset_to_idle()


    def publish_movement_source(self):
        """Publish the current movement source."""
        if not self.enable_dema_integration:
            return

        try:
            msg = String()
            msg.data = self.movement_source
            self.movement_source_publisher.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing movement source: {e}")

def main(args=None):
    rclpy.init(args=args)

    # Use MultiThreadedExecutor for action server
    executor = MultiThreadedExecutor()
    animation_server = AnimationCommandActionServer()

    executor.add_node(animation_server)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        animation_server.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
