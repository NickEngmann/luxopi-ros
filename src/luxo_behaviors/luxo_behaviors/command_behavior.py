#!/usr/bin/env python3
#command_behavior.py
"""
Unified Command Behavior Module for Luxo robot (MIXIN).
Handles BOTH voice assistant commands (mute, volume, speed, pitch)
AND robot hardware commands (sleep, wake, lights, brightness, colors).

Used by:
- luxopi_assistant_node (detects all commands from user speech)
- behavior_coordinator (coordinates voice with physical behaviors)
"""

import threading
import time
import re
import random
from typing import Optional, Dict, Set
from std_msgs.msg import Bool, String, Float32
from luxo_behaviors.state_machine import LuxoState
from rclpy.action import ActionClient
from luxo_interfaces.action import PlayAnimation


class CommandBehavior:
    """
    Unified command behavior mixin handling both voice assistant and robot hardware commands.

    Used as a mixin by:
    1. BehaviorCoordinator (behavior_coordinator.py) - For coordination with physical behaviors
    2. LuxopiAssistantNode (luxopi_assistant_node.py) - For command detection from speech
    """

    def setup_command_behavior(self, verbose=False, amplitude=120, speed=180, pitch=90, setup_publishers=True):
        """
        Initialize command behavior (mixin setup method).

        Args:
            verbose: Enable verbose logging
            amplitude: Voice amplitude (0-200)
            speed: Voice speed in WPM (80-450)
            pitch: Voice pitch (0-99)
            setup_publishers: If True, create ROS publishers for hardware control.
                             Set to False if only using coordination methods (e.g., behavior_coordinator)
        """
        self.verbose = verbose

        # Voice assistant settings (espeak parameters)
        self.is_muted = False
        self.amplitude = amplitude  # Volume: 0-200, default 120
        self.speed = speed          # Speed: 80-450 wpm, default 300
        self.pitch = pitch          # Pitch: 0-99, default 90

        # Voice assistant bounds and steps
        self.AMPLITUDE_MIN = 20
        self.AMPLITUDE_MAX = 200
        self.SPEED_MIN = 80
        self.SPEED_MAX = 450
        self.PITCH_MIN = 0
        self.PITCH_MAX = 99
        self.AMPLITUDE_STEP = 20
        self.SPEED_STEP = 50
        self.PITCH_STEP = 10

        # Robot hardware state tracking
        self.light_state = True
        self.sleep_state = False
        self.current_brightness = 0.2
        self.current_color_temp = 0.5
        self.color_mode = None

        # Command timing and cooldown
        self.command_cooldown = 2.0  # seconds
        self.last_command_time = self.node.get_clock().now()

        # Initialize patterns
        self._init_voice_assistant_patterns()
        self._init_robot_hardware_patterns()

        # ROS integration (optional - only needed if this node publishes commands)
        if setup_publishers:
            self._setup_ros_integration()
            if self.node:
                self.node.get_logger().info("CommandBehavior mixin initialized (with publishers)")
        else:
            # Still need command state tracking for coordination
            self.command_in_progress = False
            self.command_completion_time = None
            self.last_llm_interaction_time = None
            self.user_control_timeout = 3.0
            self.command_lock = threading.Lock()

            # Initialize stay mode tracking even without publishers
            self.stay_mode_active = False
            self.stay_mode_timer = None
            self.stay_mode_publish_count = 0

            if self.node:
                self.node.get_logger().info("CommandBehavior mixin initialized (coordination only, no publishers)")

    def _init_voice_assistant_patterns(self):
        """Initialize fuzzy patterns for voice assistant commands."""

        # Quick responses (bypass LLM entirely)
        self.quick_responses = {
            "hello": "Hello!",
            "hello there": "Hi there!",
            "hi": "Hey!",
            "hey": "Hello!",
            "good morning": "Good morning!",
            "good afternoon": "Good afternoon!",
            "good evening": "Good evening!",
            "goodbye": "Goodbye!",
            "bye": "Bye!",
            "thank you": "You're welcome!",
            "thanks": "No problem!",
            "how are you": "I'm doing great!",
            "what's up": "Not much, you?",
        }

        # Mute command patterns (flexible for fuzzy matching)
        self.mute_patterns = [
            r'(be|bee|beat).{0,5}(silent|silence|silents)',
            r'(be|bee|beat).{0,5}(quiet|quite|quieter)',
            r'(shut|shush|shot|shout).{0,5}(up|it|that)',
            r'(mute|moot|meet|muting).{0,5}(yourself)?',
            r'stop.{0,5}(talking|speaking|talk|speak)',
            r'\bhush\b',
            r'zip.{0,5}it',
            r'no.{0,5}more.{0,5}talking',
            r'(need|want).{0,5}silence',
            r'quiet.{0,5}down',
        ]

        # Unmute command patterns
        self.unmute_patterns = [
            r'(you.{0,5}can.{0,5})?talk.{0,5}(again|now)?',
            r'(you.{0,5}can.{0,5})?speak.{0,5}(again|now)?',
            r'(unmute|un.{0,5}mute|unmuting).{0,5}(yourself)?',
            r'start.{0,5}(talking|speaking).{0,5}(again)?',
            r'go.{0,5}ahead.{0,5}(and.{0,5})?(talk|speak)?',
            r'(it\'?s.{0,5})?okay.{0,5}(to.{0,5})?(talk|speak).{0,5}(now)?',
            r'(you\'?re.{0,5})?allowed.{0,5}to.{0,5}(talk|speak)',
            r'\bresume\b',
            r'back.{0,5}on',
        ]

        # Volume control patterns
        self.volume_up_patterns = [
            r'(speak|talk|be|bee).{0,5}(louder|loader|lauder|higher)',
            r'increase.{0,5}(your.{0,5})?(volume|volumes|loudness)',
            r'(raise|rays|race).{0,5}(your.{0,5}|the.{0,5})?(volume|voice)',
            r'\blouder\b',
            r'volume.{0,5}up',
            r'turn.{0,5}up.{0,5}(volume|voice)',
        ]

        self.volume_down_patterns = [
            r'(speak|talk|be|bee).{0,5}(quieter|quite|softer|lower)',
            r'decrease.{0,5}(your.{0,5})?(volume|volumes|loudness)',
            r'(lower|turn.{0,5}down).{0,5}(your.{0,5}|the.{0,5})?(volume|voice)',
            r'\bquieter\b',
            r'\bsofter\b',
            r'volume.{0,5}down',
            r'too.{0,5}(loud|load)',
        ]

        # Speed control patterns
        self.speed_up_patterns = [
            r'(speak|talk|speaks|talks).{0,5}(faster|quicker)',
            r'speed.{0,5}up',
            r'\b(faster|quicker)\b',
        ]

        self.speed_down_patterns = [
            r'(speak|talk|speaks|talks).{0,5}(slower|slow|more.{0,5}slowly)',
            r'slow.{0,5}down',
            r'too.{0,5}(fast|faster)',
            r'\b(slower|slow)\b',
        ]

        # Pitch control patterns
        self.pitch_up_patterns = [
            r'higher.{0,5}(pitch|voice)',
            r'(raise|rays|race).{0,5}(your.{0,5})?pitch',
            r'more.{0,5}high-pitched',
        ]

        self.pitch_down_patterns = [
            r'lower.{0,5}(pitch|voice)',
            r'deeper.{0,5}voice',
            r'more.{0,5}bass',
            r'lower.{0,5}your.{0,5}pitch',
        ]

        # Status request patterns
        self.status_patterns = [
            r'what\'?s.{0,5}your.{0,5}(status|settings|setting|configuration)',
            r'how.{0,5}are.{0,5}you.{0,5}configured',
            r'show.{0,5}(me.{0,5})?(your.{0,5})?settings',
            r'check.{0,5}settings',
            r'voice.{0,5}settings',
        ]

    def _init_robot_hardware_patterns(self):
        """Initialize fuzzy patterns for robot hardware commands."""

        # Sleep patterns - VERY FLEXIBLE for natural language
        self.sleep_patterns = [
            # Direct sleep commands
            r'go.{0,5}(to|the|a|and)?.{0,5}(sleep|slip|asleep|sleeps|sleeping)',
            r'(go|going).{0,10}(sleep|bed)',
            r'time.{0,10}(to|for|the)?.{0,10}(bed|sleep)',

            # "You're about to..." / "You should..." patterns
            r'(you\'?re|your|you|u).{0,10}(about|going|supposed).{0,10}(to|the)?.{0,10}(sleep|bed)',
            r'(you\'?re|your|you|u).{0,10}(should|need|have).{0,10}(to|the)?.{0,10}(sleep|bed)',

            # Questions about being asleep
            r'(are|r).{0,5}(you|u).{0,5}(asleep|sleeping)',
            r'(you|u).{0,5}(asleep|sleeping)',

            # Natural commands
            r'(it\'?s|its)?.{0,5}(time|night).{0,10}(to|for|the)?.{0,10}(sleep|bed)',
            r'(it\'?s|its).{0,5}bed.?time',
            r'sleep\s+(now|time|mode)',
            r'(sleep|sleeping).{0,5}(mode|time)',

            # Just the word "sleep" - MUST be last to avoid false positives
            r'\b(sleep|asleep)\b',

            # Night time phrases
            r'good.?night',
            r'nighty.{0,5}night',
            r'sweet.{0,5}dreams',

            # Power commands
            r'power.{0,5}down',
            r'shut.{0,5}down',
            r'power.{0,5}off',
        ]

        # Wake patterns - VERY FLEXIBLE for natural language
        self.wake_patterns = [
            # Direct wake commands
            r'wake.{0,5}(up|it)?',
            r'(get|git).{0,5}up',
            r'(rise|rice).{0,5}(and.{0,5})?shine',

            # Morning greetings
            r'good\s+morning',
            r'morning',

            # "You should..." / "Time to..." patterns
            r'(you\'?re|your|you|u).{0,10}(should|need|have).{0,10}(to|the)?.{0,10}(wake|get).{0,10}up',
            r'time.{0,10}(to|for).{0,10}(wake|get).{0,10}up',

            # Power commands
            r'power\s+(on|up)',
            r'(start|boot).{0,5}up',
            r'turn.{0,5}on',
        ]

        # Stay patterns - Robot freezes in current position
        self.stay_patterns = [
            # Stop commands - Most natural way to say "freeze" (MUST come before mute checks)
            r'(please|can.{0,5}you).{0,5}stop',  # "please stop", "can you stop"
            r'stop.{0,5}(now|please|it|there|right.{0,5}there)',  # "stop now", "stop please", etc.
            r'(just.{0,5})?stop.{0,5}(for.{0,5}a.{0,5})?(second|moment|minute)',  # "just stop for a moment"

            # Direct stay commands
            r'\bstay\b',
            r'stay.{0,5}(there|still|put|right.{0,5}there)',
            r'(don\'?t|dont|do not).{0,5}move',
            r'(stop|hold).{0,5}(moving|motion)',  # "stop moving" - more specific
            r'freeze',
            r'hold.{0,5}(that.{0,5})?position',
            r'keep.{0,5}(your.{0,5})?position',
            r'stay.{0,5}in.{0,5}place',
            r'\bpause\b',  # "pause" as synonym for stay

            # "You should stay" patterns
            r'(you\'?re|your|you|u).{0,10}(should|need|have).{0,10}to.{0,10}stay',
            r'(you\'?re|your|you|u).{0,10}(going|supposed).{0,10}to.{0,10}stay',
        ]

        # Move patterns - Exit stay mode and resume normal operation
        self.move_patterns = [
            # Direct move commands
            r'\bmove\b',
            r'(you.{0,5})?can.{0,5}move.{0,5}(now|again)?',
            r'start.{0,5}moving.{0,5}(again)?',
            r'(un|undo).{0,5}freeze',
            r'(un|undo).{0,5}stay',
            r'resume',
            r'go.{0,5}ahead.{0,5}(and.{0,5})?move',
            r'(it\'?s.{0,5})?okay.{0,5}to.{0,5}move',
        ]

        # Light ON patterns
        self.light_on_patterns = [
            r'(turn|turns|torn).{0,5}(on|in|and).{0,5}(the|a|an)?.{0,5}(light|lights|like)',
            r'(turn|turns|torn).{0,5}(the|a|an)?.{0,5}(light|lights|like).{0,5}(on|in|and)',
            r'(light|lights|like).{0,5}(on|in|and)',
            r'(switch|switches).{0,5}(light|lights).{0,5}on',
        ]

        # Light OFF patterns
        self.light_off_patterns = [
            r'(turn|turns|torn).{0,5}(off|of|out).{0,5}(the|a|an)?.{0,5}(light|lights|like)',
            r'(turn|turns|torn).{0,5}(the|a|an)?.{0,5}(light|lights|like).{0,5}(off|of|out)',
            r'(light|lights|like).{0,5}(off|of|out)',
            r'(switch|switches).{0,5}(light|lights).{0,5}off',
        ]

        # Color map for fuzzy matching
        self.color_variations = {
            'red': ['red', 'read', 'rad', 'rid'],
            'orange': ['orange', 'ornge', 'arrange'],
            'yellow': ['yellow', 'yello', 'mellow'],
            'green': ['green', 'grain', 'grin', 'scene'],
            'cyan': ['cyan', 'sign', 'sigh', 'turquoise', 'turquois'],
            'blue': ['blue', 'blew', 'glue', 'flew'],
            'purple': ['purple', 'violet', 'people', 'papal'],
            'white': ['white', 'wight', 'wright', 'bite', 'right']
        }

    def _setup_ros_integration(self):
        """Setup ROS publishers and subscriptions."""
        # Command state tracking
        self.command_in_progress = False
        self.command_completion_time = None
        self.last_llm_interaction_time = None
        self.user_control_timeout = 3.0
        self.command_lock = threading.Lock()

        # Stay mode continuous publishing state
        self.stay_mode_active = False
        self.stay_mode_timer = None
        self.stay_mode_publish_count = 0

        # Create publishers for robot hardware control
        self.light_control_publisher = self.node.create_publisher(Bool, '/luxo/light_control', 10)
        self.brightness_control_publisher = self.node.create_publisher(Float32, '/luxo/brightness_control', 10)
        self.color_temp_control_publisher = self.node.create_publisher(String, '/luxo/color_temp_control', 10)
        self.color_control_publisher = self.node.create_publisher(String, '/luxo/color_control', 10)
        self.pixel_ring_control_publisher = self.node.create_publisher(Bool, '/voice/pixel_ring_control', 10)
        self.sleep_mode_publisher = self.node.create_publisher(Bool, '/luxo/sleep_mode', 10)
        self.stay_mode_publisher = self.node.create_publisher(Bool, '/luxo/stay_mode', 10)

        if self.verbose:
            self.node.get_logger().info("ROS publishers created for command behavior")

    # ===================================================================
    # COMMAND DETECTION METHODS (used by luxopi_assistant_node)
    # ===================================================================

    def detect_command(self, text):
        """
        Detect ANY command (voice assistant OR robot hardware) from user speech.
        Returns tuple: (command_type, command_data, canned_response)

        command_type: 'voice_assistant', 'robot_hardware', 'quick_response', or None
        command_data: dict with command details
        canned_response: str to speak (skip LLM)
        """
        text_lower = text.lower().strip()

        # Check cooldown
        if self.last_command_time:
            current_time = self.node.get_clock().now()
            time_since_last = (current_time - self.last_command_time).nanoseconds / 1e9
            if time_since_last < self.command_cooldown:
                return None, None, None

        # Priority 1: Quick responses (highest priority - instant responses)
        quick_response = self._check_quick_response(text_lower)
        if quick_response:
            return 'quick_response', {'response': quick_response}, quick_response

        # Priority 2: Voice assistant commands (mute, volume, etc.)
        # Mute/unmute
        if self._check_mute_command(text_lower):
            response = self._get_mute_confirmation()
            return 'voice_assistant', {'action': 'mute'}, response

        if self._check_unmute_command(text_lower):
            response = self._get_unmute_confirmation()
            return 'voice_assistant', {'action': 'unmute'}, response

        # Volume
        volume_change = self._check_volume_command(text_lower)
        if volume_change:
            response = self._get_volume_confirmation(volume_change)
            return 'voice_assistant', {'action': 'volume_' + volume_change}, response

        # Speed
        speed_change = self._check_speed_command(text_lower)
        if speed_change:
            response = self._get_speed_confirmation(speed_change)
            return 'voice_assistant', {'action': 'speed_' + speed_change}, response

        # Pitch
        pitch_change = self._check_pitch_command(text_lower)
        if pitch_change:
            response = self._get_pitch_confirmation(pitch_change)
            return 'voice_assistant', {'action': 'pitch_' + pitch_change}, response

        # Status
        if self._check_status_command(text_lower):
            response = self._get_status_message()
            return 'voice_assistant', {'action': 'status'}, response

        # Priority 3: Robot hardware commands (sleep, lights, etc.)
        hw_command = self._detect_hardware_command(text_lower)
        if hw_command:
            response = self._get_hardware_confirmation(hw_command)
            return 'robot_hardware', {'command': hw_command}, response

        # No command detected
        return None, None, None

    def _detect_hardware_command(self, text):
        """Detect robot hardware commands. Returns command name or None."""

        # Sleep commands
        if any(re.search(pattern, text) for pattern in self.sleep_patterns):
            return 'go_to_sleep'

        # Wake commands (but not "wake up" in unmute context)
        if any(re.search(pattern, text) for pattern in self.wake_patterns):
            # Make sure it's not an unmute command
            if not self._check_unmute_command(text):
                return 'wake_up'

        # Stay commands
        if any(re.search(pattern, text) for pattern in self.stay_patterns):
            return 'stay'

        # Move commands (exit stay mode)
        if any(re.search(pattern, text) for pattern in self.move_patterns):
            return 'move'

        # Light ON
        if any(re.search(pattern, text) for pattern in self.light_on_patterns):
            return 'turn_on_light'

        # Light OFF
        if any(re.search(pattern, text) for pattern in self.light_off_patterns):
            return 'turn_off_light'

        # Brightness - check max/min first
        if 'min' in text or 'minimum' in text or 'dimmest' in text:
            if 'bright' in text or 'light' in text:
                return 'set_brightness_min'

        if 'max' in text or 'maximum' in text or 'brightest' in text:
            if 'bright' in text or 'light' in text:
                return 'set_brightness_max'

        # Then increase/decrease
        if any(word in text for word in ['bright', 'brighten', 'brighter', 'writer', 'rider']):
            return 'increase_brightness'

        if any(word in text for word in ['dim', 'dimmer', 'darker', 'dimer', 'timer']):
            return 'decrease_brightness'

        # Color temperature
        if any(word in text for word in ['warm', 'warmer', 'more warm', 'warm up', 'former']):
            return 'increase_color_temp'

        if any(word in text for word in ['cool', 'cooler', 'more cool', 'cool down', 'ruler']):
            return 'decrease_color_temp'

        # Colors
        for color, variations in self.color_variations.items():
            if any(var in text for var in variations):
                return f'set_color_{color}'

        return None

    def _get_hardware_confirmation(self, command):
        """Get canned response for hardware command."""
        confirmations = {
            'go_to_sleep': [
                "Okay, going to sleep now.",
                "Good night!",
                "Alright, time for bed.",
                "Sleep mode activated.",
            ],
            'wake_up': [
                "Good morning!",
                "I'm awake!",
                "Ready and awake!",
                "Waking up now.",
            ],
            'stay': [
                "Okay, staying still.",
                "Freezing in place.",
                "Holding position.",
                "I won't move.",
            ],
            'move': [
                "Okay, I can move again.",
                "Resuming movement.",
                "Unfrozen.",
                "Moving now.",
            ],
            'turn_on_light': [
                "Lights on.",
                "Turning on the lights.",
                "Let there be light!",
            ],
            'turn_off_light': [
                "Lights off.",
                "Turning off the lights.",
                "Going dark.",
            ],
            'increase_brightness': [
                "Increasing brightness.",
                "Making it brighter.",
                "Brighter.",
            ],
            'decrease_brightness': [
                "Decreasing brightness.",
                "Making it dimmer.",
                "Dimmer.",
            ],
            'set_brightness_max': [
                "Maximum brightness.",
                "Full bright.",
                "Brightest setting.",
            ],
            'set_brightness_min': [
                "Minimum brightness.",
                "Very dim.",
                "Lowest setting.",
            ],
            'increase_color_temp': [
                "Making it warmer.",
                "Warmer tone.",
                "Increasing warmth.",
            ],
            'decrease_color_temp': [
                "Making it cooler.",
                "Cooler tone.",
                "Decreasing warmth.",
            ],
        }

        # Color commands
        if command.startswith('set_color_'):
            color = command.replace('set_color_', '')
            return f"Setting color to {color}."

        # Get confirmation or default
        options = confirmations.get(command, ["Okay."])
        return random.choice(options)

    def execute_hardware_command(self, command):
        """
        Execute hardware command by publishing to ROS topics.
        Called by luxopi_assistant_node after detection.
        """
        try:
            if command == 'go_to_sleep':
                self._publish_sleep_mode(True)
            elif command == 'wake_up':
                self._publish_sleep_mode(False)
            elif command == 'stay':
                self._publish_stay_mode(True)
            elif command == 'move':
                self._publish_stay_mode(False)
            elif command == 'turn_on_light':
                self._publish_light_state(True)
            elif command == 'turn_off_light':
                self._publish_light_state(False)
            elif command == 'increase_brightness':
                self._adjust_brightness(increase=True)
            elif command == 'decrease_brightness':
                self._adjust_brightness(increase=False)
            elif command == 'set_brightness_max':
                self._set_brightness(1.0)
            elif command == 'set_brightness_min':
                self._set_brightness(0.1)
            elif command == 'increase_color_temp':
                self._adjust_color_temperature(increase=True)
            elif command == 'decrease_color_temp':
                self._adjust_color_temperature(increase=False)
            elif command.startswith('set_color_'):
                color = command.replace('set_color_', '')
                self._set_color(color)

            # Update timing
            self.last_command_time = self.node.get_clock().now()

        except Exception as e:
            self.node.get_logger().error(f"Error executing hardware command {command}: {e}")

    def _publish_sleep_mode(self, sleep: bool):
        """Publish sleep mode command."""
        try:
            msg = Bool()
            msg.data = sleep
            self.sleep_mode_publisher.publish(msg)
            self.sleep_state = sleep
            # ALWAYS log this - it's critical for debugging
            self.node.get_logger().info(f"📢 PUBLISHED sleep mode: {sleep} to /luxo/sleep_mode")
        except Exception as e:
            self.node.get_logger().error(f"Error publishing sleep mode: {e}")

    def _publish_stay_mode(self, stay: bool):
        """Publish stay mode command and setup continuous publishing."""
        try:
            self.stay_mode_active = stay
            self.stay_mode_publish_count = 0  # Track how many times we've published

            # Publish immediately
            msg = Bool()
            msg.data = stay
            self.stay_mode_publisher.publish(msg)
            self.node.get_logger().info(f"📢 PUBLISHED stay mode: {stay} to /luxo/stay_mode")

            # Always start/restart timer for continuous publishing (both True and False)
            if self.stay_mode_timer is not None:
                self.stay_mode_timer.cancel()
            self.stay_mode_timer = self.node.create_timer(5.0, self._stay_mode_timer_callback)

            if stay:
                self.node.get_logger().info("🔄 Started continuous STAY=True publishing (every 5s)")
            else:
                self.node.get_logger().info("🔄 Started continuous STAY=False publishing (every 5s for 30s)")
        except Exception as e:
            self.node.get_logger().error(f"Error publishing stay mode: {e}")

    def _stay_mode_timer_callback(self):
        """Timer callback to continuously publish stay mode state."""
        try:
            self.stay_mode_publish_count += 1

            # Publish current state
            msg = Bool()
            msg.data = self.stay_mode_active
            self.stay_mode_publisher.publish(msg)
            self.node.get_logger().debug(f"🔄 Republished STAY mode: {self.stay_mode_active} (count: {self.stay_mode_publish_count})")

            # If publishing False (exit mode), stop after 30 seconds (6 publications)
            if not self.stay_mode_active and self.stay_mode_publish_count >= 6:
                self.node.get_logger().info("⏹️ Stopped continuous STAY=False publishing after 30s")
                if self.stay_mode_timer is not None:
                    self.stay_mode_timer.cancel()
                    self.stay_mode_timer = None
        except Exception as e:
            self.node.get_logger().error(f"Error in stay mode timer callback: {e}")

    def _publish_light_state(self, state: bool):
        """Publish light control command."""
        try:
            msg = Bool()
            msg.data = state
            self.light_control_publisher.publish(msg)
            self.light_state = state
            if self.verbose:
                self.node.get_logger().info(f"Published light state: {state}")
        except Exception as e:
            self.node.get_logger().error(f"Error publishing light state: {e}")

    def _publish_pixel_ring_state(self, state: bool):
        """Publish pixel ring control command."""
        try:
            msg = Bool()
            msg.data = state
            self.pixel_ring_control_publisher.publish(msg)
            if self.verbose:
                self.node.get_logger().info(f"Published pixel ring state: {state}")
        except Exception as e:
            self.node.get_logger().error(f"Error publishing pixel ring state: {e}")

    def _adjust_brightness(self, increase: bool):
        """Adjust brightness and publish."""
        step = 0.1
        if increase:
            self.current_brightness = min(1.0, self.current_brightness + step)
        else:
            self.current_brightness = max(0.1, self.current_brightness - step)
        self._publish_brightness_control(self.current_brightness)

    def _set_brightness(self, level: float):
        """Set brightness to specific level and publish."""
        self.current_brightness = max(0.0, min(1.0, level))
        self._publish_brightness_control(self.current_brightness)

    def _adjust_color_temperature(self, increase: bool):
        """Adjust color temperature and publish."""
        step = 0.2
        if increase:
            self.current_color_temp = min(1.0, self.current_color_temp + step)
        else:
            self.current_color_temp = max(0.0, self.current_color_temp - step)

        # Clear color mode when adjusting temperature
        if self.color_mode:
            self.color_mode = None
            self._publish_color_control('white')
            time.sleep(0.1)

        self._publish_color_temperature(self.current_color_temp)

    def _set_color(self, color: str):
        """Set LED color and publish."""
        if color == 'white':
            self.color_mode = None
            self._publish_color_control('white')
            self._publish_color_temperature(self.current_color_temp)
        else:
            self.color_mode = color
            self._publish_color_control(color)

    def _publish_brightness_control(self, brightness: float):
        """Publish brightness control message."""
        try:
            msg = Float32()
            msg.data = brightness
            self.brightness_control_publisher.publish(msg)
        except Exception as e:
            self.node.get_logger().error(f"Error publishing brightness: {e}")

    def _publish_color_temperature(self, temp: float):
        """Publish color temperature control message."""
        try:
            msg = String()
            msg.data = f"color_temp:{temp}"
            self.color_temp_control_publisher.publish(msg)
        except Exception as e:
            self.node.get_logger().error(f"Error publishing color temperature: {e}")

    def _publish_color_control(self, color: str):
        """Publish color control message."""
        try:
            msg = String()
            msg.data = f"color:{color}"
            self.color_control_publisher.publish(msg)
        except Exception as e:
            self.node.get_logger().error(f"Error publishing color: {e}")

    # ===================================================================
    # VOICE ASSISTANT METHODS
    # ===================================================================

    def _check_quick_response(self, text):
        """Check if text has a quick response."""
        # Direct match
        if text in self.quick_responses:
            return self.quick_responses[text]

        # Partial match for common phrases
        for trigger, response in self.quick_responses.items():
            if trigger in text and len(text) < len(trigger) + 10:
                return response

        return None

    def _check_mute_command(self, text):
        """Check for mute command and update state."""
        for pattern in self.mute_patterns:
            if re.search(pattern, text):
                if not self.is_muted:
                    self.is_muted = True
                    if self.verbose:
                        self.node.get_logger().info(f"Mute command detected: '{text}'")
                    return True
                else:
                    if self.verbose:
                        self.node.get_logger().info("Already muted")
                    return False
        return False

    def _check_unmute_command(self, text):
        """Check for unmute command and update state."""
        for pattern in self.unmute_patterns:
            if re.search(pattern, text):
                if self.is_muted:
                    self.is_muted = False
                    if self.verbose:
                        self.node.get_logger().info(f"Unmute command detected: '{text}'")
                    return True
                else:
                    if self.verbose:
                        self.node.get_logger().info("Already unmuted")
                    return False
        return False

    def _check_volume_command(self, text):
        """Check for volume command and adjust."""
        # Volume up
        for pattern in self.volume_up_patterns:
            if re.search(pattern, text):
                old_volume = self.amplitude
                self.amplitude = min(self.AMPLITUDE_MAX, self.amplitude + self.AMPLITUDE_STEP)
                if self.verbose:
                    self.node.get_logger().info(f"Volume up: {old_volume} → {self.amplitude}")
                return "up"

        # Volume down
        for pattern in self.volume_down_patterns:
            if re.search(pattern, text):
                old_volume = self.amplitude
                self.amplitude = max(self.AMPLITUDE_MIN, self.amplitude - self.AMPLITUDE_STEP)
                if self.verbose:
                    self.node.get_logger().info(f"Volume down: {old_volume} → {self.amplitude}")
                return "down"

        return None

    def _check_speed_command(self, text):
        """Check for speed command and adjust."""
        # Speed up
        for pattern in self.speed_up_patterns:
            if re.search(pattern, text):
                old_speed = self.speed
                self.speed = min(self.SPEED_MAX, self.speed + self.SPEED_STEP)
                if self.verbose:
                    self.node.get_logger().info(f"Speed up: {old_speed} → {self.speed}")
                return "up"

        # Speed down
        for pattern in self.speed_down_patterns:
            if re.search(pattern, text):
                old_speed = self.speed
                self.speed = max(self.SPEED_MIN, self.speed - self.SPEED_STEP)
                if self.verbose:
                    self.node.get_logger().info(f"Speed down: {old_speed} → {self.speed}")
                return "down"

        return None

    def _check_pitch_command(self, text):
        """Check for pitch command and adjust."""
        # Pitch up
        for pattern in self.pitch_up_patterns:
            if re.search(pattern, text):
                old_pitch = self.pitch
                self.pitch = min(self.PITCH_MAX, self.pitch + self.PITCH_STEP)
                if self.verbose:
                    self.node.get_logger().info(f"Pitch up: {old_pitch} → {self.pitch}")
                return "up"

        # Pitch down
        for pattern in self.pitch_down_patterns:
            if re.search(pattern, text):
                old_pitch = self.pitch
                self.pitch = max(self.PITCH_MIN, self.pitch - self.PITCH_STEP)
                if self.verbose:
                    self.node.get_logger().info(f"Pitch down: {old_pitch} → {self.pitch}")
                return "down"

        return None

    def _check_status_command(self, text):
        """Check for status request command."""
        for pattern in self.status_patterns:
            if re.search(pattern, text):
                if self.verbose:
                    self.node.get_logger().info("Status request detected")
                return True
        return False

    def _get_status_message(self):
        """Generate status message."""
        mute_status = "muted" if self.is_muted else "unmuted"
        volume_pct = int((self.amplitude / self.AMPLITUDE_MAX) * 100)

        speed_desc = "normal"
        if self.speed < 250:
            speed_desc = "slow"
        elif self.speed > 350:
            speed_desc = "fast"

        pitch_desc = "normal"
        if self.pitch < 40:
            pitch_desc = "low"
        elif self.pitch > 60:
            pitch_desc = "high"

        return (f"I'm currently {mute_status}. "
                f"Volume is at {volume_pct} percent. "
                f"Speed is {speed_desc}. "
                f"Pitch is {pitch_desc}.")

    def _get_mute_confirmation(self):
        """Get mute confirmation message."""
        confirmations = [
            "Okay, I'll be quiet now.",
            "Sure, muting myself.",
            "Alright, I'm silent.",
            "Got it, no more talking.",
            "Understood, going silent.",
        ]
        return random.choice(confirmations)

    def _get_unmute_confirmation(self):
        """Get unmute confirmation message."""
        confirmations = [
            "Okay, I can talk again!",
            "Great, I'm back!",
            "Unmuted!",
            "Alright, ready to chat!",
            "I'm listening again!",
        ]
        return random.choice(confirmations)

    def _get_volume_confirmation(self, direction):
        """Get volume confirmation message."""
        if direction == "up":
            return random.choice([
                "Volume increased.",
                "Speaking louder now.",
                "Turning it up.",
                "Louder.",
            ])
        else:
            return random.choice([
                "Volume decreased.",
                "Speaking softer now.",
                "Turning it down.",
                "Quieter.",
            ])

    def _get_speed_confirmation(self, direction):
        """Get speed confirmation message."""
        if direction == "up":
            return random.choice([
                "Speaking faster now.",
                "Speeding up.",
                "Faster.",
            ])
        else:
            return random.choice([
                "Speaking slower now.",
                "Slowing down.",
                "Slower.",
            ])

    def _get_pitch_confirmation(self, direction):
        """Get pitch confirmation message."""
        if direction == "up":
            return random.choice([
                "Raising pitch.",
                "Higher voice.",
                "Pitch up.",
            ])
        else:
            return random.choice([
                "Lowering pitch.",
                "Deeper voice.",
                "Pitch down.",
            ])

    def should_speak(self):
        """Returns True if assistant should speak (not muted)."""
        return not self.is_muted

    def clean_parentheticals(self, text):
        """Remove or convert parenthetical expressions from LLM output."""
        standalone_replacements = {
            "(laughing)": "haha",
            "(chuckling)": "haha",
            "(giggling)": "hehe",
            "(smiling)": "",
            "(sighing)": "hmm",
            "(groaning)": "ugh",
            "(gasping)": "oh",
            "(crying)": "aww",
            "(yawning)": "yawn",
            "(thinking)": "hmm",
        }

        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        if text_lower in standalone_replacements:
            replacement = standalone_replacements[text_lower]
            return replacement if replacement else "..."

        # Remove all parentheticals
        cleaned = re.sub(r'\s*\([^)]*\)\s*', ' ', text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def is_placeholder_response(self, text):
        """Check if LLM response is a placeholder."""
        text_lower = text.lower().strip()

        placeholder_patterns = [
            r'\[your response.*?\]',
            r'\[response.*?\]',
            r'\[.*?here\]',
            r'\[insert.*?\]',
            r'\[reply.*?\]',
        ]

        for pattern in placeholder_patterns:
            if re.search(pattern, text_lower):
                return True

        if len(text.strip()) < 3:
            return True

        if not re.search(r'[a-zA-Z0-9]', text):
            return True

        return False

    def get_random_fallback(self):
        """Get random fallback response."""
        fallbacks = [
            "Mm-hmm",
            "I see",
            "Got it",
            "Okay",
            "Right",
            "Uh-huh",
            "Makes sense",
            "Alright",
            "Fair enough",
            "Understood"
        ]
        return random.choice(fallbacks)

    # ===================================================================
    # COORDINATION METHODS (for behavior_coordinator)
    # ===================================================================

    def can_speak_during_state(self, state) -> bool:
        """Check if speech is allowed in current state (for coordination)."""
        # States that allow voice output
        allowed_states = [
            LuxoState.IDLE,
            LuxoState.VOICE_FOLLOWING,
            LuxoState.ANIMATING,
            LuxoState.PETTING,
            LuxoState.EMOTION_REACTING,
            LuxoState.USER_CONTROL
        ]
        return state in allowed_states

    def should_mute_for_safety(self, collision_active, severity) -> bool:
        """Determine if we should temporarily mute for safety (for coordination)."""
        # Mute during danger-level collisions
        if collision_active and severity == 'danger':
            return True
        return False

    def check_command_completion(self, current_time):
        """
        Check if command should be completed (called from behavior_coordinator).
        Returns True if command was completed.
        """
        # This method is called by behavior_coordinator's safety_monitor_callback
        # to check if voice commands have finished executing

        should_complete = False

        with self.command_lock:
            if (self.command_in_progress and
                self.command_completion_time and
                hasattr(self, '_is_in_state') and
                self._is_in_state(LuxoState.USER_CONTROL)):
                # Command completion after grace period
                time_since_completion = (current_time - self.command_completion_time).nanoseconds / 1e9
                if time_since_completion > 0.5:  # 500ms grace period
                    should_complete = True

        if should_complete:
            try:
                self._complete_command()
                return True
            except Exception as e:
                if self.node:
                    self.node.get_logger().error(f"Error in command completion: {e}")
                return False

        return False

    def _complete_command(self):
        """Complete the current command (used by behavior_coordinator)."""
        with self.command_lock:
            if not self.command_in_progress:
                return

            self.node.get_logger().info("Completing voice command")
            self.command_in_progress = False
            self.command_completion_time = None

        # Transition to IDLE if we have the method
        if hasattr(self, '_transition_to_state'):
            try:
                self._transition_to_state(LuxoState.IDLE)
            except Exception as e:
                self.node.get_logger().error(f"Error transitioning to IDLE: {e}")

    def cleanup_command_behavior(self):
        """Clean up command behavior resources (for proper shutdown)."""
        if hasattr(self, 'command_lock'):
            with self.command_lock:
                self.command_in_progress = False
                self.command_completion_time = None

        if self.node:
            self.node.get_logger().info("CommandBehavior cleaned up")
