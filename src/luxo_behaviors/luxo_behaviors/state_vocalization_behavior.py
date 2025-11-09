#!/usr/bin/env python3
"""
State Vocalization Behavior Module
Provides state-specific vocalizations to make the robot more expressive.
The robot speaks cute/contextual phrases based on its current state and emotions.
"""

import random
import time
import threading
from std_msgs.msg import String
from luxo_interfaces.msg import StateInfo
from luxo_behaviors.state_machine import LuxoState
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy


class StateVocalizationBehavior:
    """Mixin class for state-specific vocalizations."""

    def setup_state_vocalization(self, callback_group=None):
        """Initialize state vocalization attributes and subscriptions.

        Args:
            callback_group: Optional callback group for concurrent callback processing
        """

        # Vocalization state
        self.last_state_phrase_time = 0
        self.state_phrase_cooldown = 4.0  # Seconds between state phrases (reduced for responsiveness)
        self.current_robot_state = None
        self.previous_robot_state = None  # Track previous state for transition detection
        self.last_vocalized_state = None
        self.current_emotion = None
        self.collision_detected = False

        # Cooldown logging flags - track if we've already logged about cooldown to reduce spam
        self.cooldown_logged_for_emotion = False
        self.cooldown_logged_for_state = False

        # Throttle "would vocalize" logs to once per 2 seconds max
        self.last_would_vocalize_log_time = {
            'muted': 0,
            'stt_tts_active': 0,
            'sleeping': 0,
            'frozen': 0
        }
        self.would_vocalize_log_interval = 2.0  # seconds

        # Priority flag - STT->LLM->TTS pipeline is always prioritized
        self.stt_pipeline_active = False

        # Subscribe to state_info which includes previous_state for true transition detection
        # This topic publishes whenever state changes, so we catch ALL transitions
        # Use BEST_EFFORT QoS with KEEP_LAST to only process latest states, avoiding callback blocking
        state_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1  # Only keep latest state
        )

        # Create subscription with callback group if provided (for concurrent processing)
        if callback_group:
            self.state_sub = self.node.create_subscription(
                StateInfo,
                '/luxo/state_info',
                self.state_change_callback,
                state_qos,
                callback_group=callback_group
            )
        else:
            self.state_sub = self.node.create_subscription(
                StateInfo,
                '/luxo/state_info',
                self.state_change_callback,
                state_qos
            )

        # Subscribe to emotion detection
        emotion_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )

        # Create subscription with callback group if provided (for concurrent processing)
        if callback_group:
            self.emotion_sub = self.node.create_subscription(
                String,
                '/camera/emotion',
                self.emotion_callback,
                emotion_qos,
                callback_group=callback_group
            )
        else:
            self.emotion_sub = self.node.create_subscription(
                String,
                '/camera/emotion',
                self.emotion_callback,
                emotion_qos
            )

        # NOTE: We rely exclusively on /luxo/current_state for COLLISION_AVOIDING and PETTING
        # This topic updates 2x per second and already includes these states
        # This simplifies the code and makes it more responsive

        # State-specific phrase dictionaries (10-20 variations each)
        self.state_phrases = {
            'RETURNING_HOME': [
                "Going back to my spot",
                "Time to head home",
                "Returning to base",
                "Back to my cozy corner",
                "Heading to my charging station",
                "Off to my safe space",
                "Time to rest up",
                "Going to my spot",
                "Returning to my favorite place",
                "Back to where I belong",
                "Homeward bound",
                "Retracing my steps",
                "Going back now",
                "Time to recharge",
                "Heading back to base"
            ],

            'ESCAPE_MODE': [
                "Whoa whoa whoa!",
                "Too close!",
                "Need some space!",
                "Getting out of here!",
                "Evasive maneuvers!",
                "Look out!",
                "Watch it!",
                "Personal space please!",
                "Backing away!",
                "Give me room!",
                "Too crowded!",
                "Need to escape!",
                "Getting away!",
                "This is intense!",
                "Making my exit!"
            ],

            'ERROR': [
                "Uh oh",
                "Something's wrong",
                "I'm confused",
                "Error detected",
                "Need a moment",
                "That's not right",
                "Hmm, trouble",
                "Having difficulties",
                "Systems check needed",
                "Something went wrong",
                "Not working right",
                "I'm stuck",
                "This is problematic",
                "Need help",
                "Malfunction alert"
            ],

            'PETTING': [
                "Prrrrr",
                "Mmmmmmm",
                "That feels nice",
                "I like that",
                "Keep going",
                "So nice",
                "Prr prrrr",
                "Mmmhmm",
                "Wonderful",
                "This is great",
                "Love this",
                "HMMMMMMMMMMM",
                "More please",
                "Feels good",
                "So soothing",
                "Yes yes yes",
                "Happy noises",
                "Brr brrrrr",
                "I loooovee this",
                "Blissful"
            ],

            'VOICE_FOLLOWING': [
                "Listening!",
                "I hear you",
                "Tracking your voice",
                "Following the sound",
                "Where are you?",
                "I'm listening",
                "Tuning in",
                "Ears perked",
                "Paying attention",
                "Locked on",
                "Hearing you",
                "Voice detected",
                "Following your voice",
                "I'm all ears",
                "Zeroing in"
            ],

            'COLLISION_AVOIDING': [
                "Ouch!",
                "Watch out!",
                "Obstacle!",
                "Careful!",
                "Something's there!",
                "Bumped into something!",
                "Object detected!",
                "Too close!",
                "Collision warning!",
                "Avoiding!",
                "Look out!",
                "Getting around this",
                "Navigating obstacles",
                "Dodging!",
                "Clear the path!"
            ]
        }

        # Emotion-specific phrases
        # NOTE: Camera publishes: happiness, sadness, anger, surprise, neutral, fear
        self.emotion_phrases = {
            'happiness': [
                "Yay!",
                "So happy!",
                "This is wonderful!",
                "I'm excited!",
                "What joy!",
                "Delightful!",
                "Hooray!",
                "Fantastic!",
                "Cheerful vibes!",
                "Love this energy!",
                "Beaming!",
                "So pleased!",
                "This is great!",
                "Happy times!",
                "Smiling inside!"
            ],

            'sadness': [
                "Oh no",
                "That's sad",
                "Feeling blue",
                "Aww",
                "Sorry to see that",
                "This is tough",
                "Sympathy",
                "Melancholy",
                "Poor thing",
                "That's rough",
                "Sadness detected",
                "I feel for you",
                "Tough times",
                "Heavy heart",
                "Compassion"
            ],

            'anger': [
                "Whoa",
                "Easy there",
                "Take it easy",
                "Calm down",
                "Deep breaths",
                "Let's relax",
                "No need to rage",
                "Peace please",
                "Chill out",
                "Anger detected",
                "Settle down",
                "Take a breath",
                "Easy now",
                "Calm vibes needed",
                "Relax friend"
            ],

            'surprise': [
                "Wow!",
                "Oh my!",
                "Surprising!",
                "Didn't expect that!",
                "What a shock!",
                "Amazing!",
                "Incredible!",
                "Astonishing!",
                "Whoa there!",
                "Plot twist!",
                "Unexpected!",
                "Well well well!",
                "How about that!",
                "Surprising development!",
                "Caught off guard!"
            ],

            'neutral': [
                "Hmm",
                "I see",
                "Okay",
                "Noted",
                "Understood",
                "Alright",
                "Got it",
                "Fair enough",
                "Makes sense",
                "Acknowledged",
                "Right",
                "Mmhmm",
                "Okay then",
                "Sure",
                "Affirmative"
            ],

            'fear': [
                "Scary!",
                "I'm nervous",
                "Yikes!",
                "Frightening",
                "Oh dear",
                "This is scary",
                "Eek!",
                "Alarming",
                "Worried",
                "Concerned",
                "Anxious",
                "Tense",
                "Scary stuff",
                "Fear detected",
                "Nervous energy"
            ]
        }

        self.node.get_logger().info("State vocalization behavior initialized")

    def _should_log_would_vocalize(self, condition_type: str) -> bool:
        """Check if enough time has passed to log a 'would vocalize' message.

        Args:
            condition_type: One of 'muted', 'stt_tts_active', 'sleeping', 'frozen'

        Returns:
            True if we should log, False if we should skip (throttled)
        """
        current_time = time.time()
        time_since_last = current_time - self.last_would_vocalize_log_time.get(condition_type, 0)

        if time_since_last >= self.would_vocalize_log_interval:
            self.last_would_vocalize_log_time[condition_type] = current_time
            return True
        return False

    def state_change_callback(self, msg):
        """Handle state changes and speak appropriate phrases.

        Uses StateInfo message which includes both current_state and previous_state,
        so we can detect ACTUAL state transitions, not just repeated state updates.

        SMART DETECTION: If msg.previous_state doesn't match our last known state,
        we MISSED a transition! We'll vocalize the missed state entry.
        """
        new_state = msg.current_state
        prev_state = msg.previous_state
        self.node.get_logger().debug(f"[StateVocalization] State change callback: {prev_state} → {new_state} (duration: {msg.state_duration:.1f}s)")

        # Only process if there's an actual state change
        if new_state == prev_state:
            self.node.get_logger().debug(f"[StateVocalization] → No state change detected: {new_state}")
            # No transition, skip silently
            return

        # Log the current transition
        self.node.get_logger().debug(
            f"[StateVocalization] 🔄 State transition: {prev_state} → {new_state} (duration: {msg.state_duration:.1f}s)"
        )

        # Update state tracking
        self.previous_robot_state = prev_state
        self.current_robot_state = new_state

        # Try to vocalize the new state
        self._try_vocalize_state(new_state, f"{prev_state} → {new_state}")

    def _try_vocalize_state(self, state, transition_desc):
        """Helper to try vocalizing a state with all checks.

        Args:
            state: The state to vocalize
            transition_desc: Description of the transition for logging
        """
        # Don't vocalize for IDLE or ANIMATING states
        if state in ['IDLE', 'ANIMATING']:
            self.node.get_logger().debug(f"[StateVocalization] → Skipping {state} state (no vocalization)")
            return

        # VOICE_FOLLOWING: Only vocalize 25% of the time (to avoid being too chatty)
        if state == 'VOICE_FOLLOWING':
            if random.random() > 0.10:  # 90% chance to skip
                self.node.get_logger().debug(f"[StateVocalization] → Skipping VOICE_FOLLOWING vocalization (random skip)")
                # Update cooldown timer so the skip counts towards cooldown
                self.last_state_phrase_time = time.time()
                return

        # COLLISION_AVOIDING: Only vocalize 85% of the time (to reduce verbosity)
        if state == 'COLLISION_AVOIDING':
            if random.random() > 0.85:  # 15% chance to skip
                self.node.get_logger().debug(f"[StateVocalization] → Skipping COLLISION_AVOIDING vocalization (random skip)")
                # Update cooldown timer so the skip counts towards cooldown
                self.last_state_phrase_time = time.time()
                return

        # Check if muted (throttle log to once per 2 seconds)
        if self.is_muted:
            if self._should_log_would_vocalize('muted'):
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize '{state}' ({transition_desc}) but assistant is muted 🔇")
            return

        # Check if STT pipeline is active (throttle log to once per 2 seconds)
        if self.stt_pipeline_active or self.is_speaking:
            if self._should_log_would_vocalize('stt_tts_active'):
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize '{state}' ({transition_desc}) but STT/TTS active")
            return

        # Check sleep mode (throttle log to once per 2 seconds)
        if self.is_sleep_mode:
            if self._should_log_would_vocalize('sleeping'):
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize '{state}' ({transition_desc}) but robot is sleeping 💤")
            return

        # Check stay mode (throttle log to once per 2 seconds)
        if self.is_stay_mode:
            if self._should_log_would_vocalize('frozen'):
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize '{state}' ({transition_desc}) but robot is frozen 🧊")
            return

        # Calculate time since last phrase
        current_time = time.time()
        time_since_last = current_time - self.last_state_phrase_time

        # Check cooldown (but only log once to reduce spam)
        if time_since_last < self.state_phrase_cooldown:
            # Only log once per cooldown period
            if not self.cooldown_logged_for_state:
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize '{state}' ({transition_desc}) but cooldown active ({time_since_last:.1f}s < {self.state_phrase_cooldown}s)")
                self.cooldown_logged_for_state = True
            return

        # Reset cooldown logging flag when cooldown expires
        self.cooldown_logged_for_state = False

        self.node.get_logger().info(f"[StateVocalization] ✅ Triggering phrase for state: {state} ({transition_desc})")

        # Reset cooldown logging flag since we're speaking now
        self.cooldown_logged_for_state = False

        # Speak a phrase for this state (in a separate thread to avoid blocking)
        threading.Thread(
            target=self._speak_state_phrase,
            args=(state,),
            daemon=True
        ).start()

    def emotion_callback(self, msg):
        """Handle emotion detection and speak appropriate phrases.

        NOTE: We vocalize immediately when emotion is detected, not when in EMOTION_REACTING state.
        This is because by the time we check the state, it's already switched to ANIMATING.
        The flow is: Emotion detected → EMOTION_REACTING → ANIMATING (emotion animation)
        """
        self.current_emotion = msg.data.lower()

        self.node.get_logger().info(f"[StateVocalization] Emotion detected: {self.current_emotion}, current state: {self.current_robot_state}")

        # Skip if we're in high-priority states (don't interrupt user control or collision avoidance)
        high_priority_states = ['USER_CONTROL', 'COLLISION_AVOIDING', 'ESCAPE_MODE', 'ERROR']
        if self.current_robot_state in high_priority_states:
            self.node.get_logger().info(f"[StateVocalization] → Skipping emotion (in high-priority state {self.current_robot_state})")
            return

        # Don't repeat same emotion
        if self.last_vocalized_state == f'EMOTION_{self.current_emotion}':
            self.node.get_logger().info(f"[StateVocalization] → Already vocalized emotion {self.current_emotion}")
            return

        # Check if muted (throttle log to once per 2 seconds)
        if self.is_muted:
            if self._should_log_would_vocalize('muted'):
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize emotion '{self.current_emotion}' but assistant is muted 🔇")
            return

        # Check if STT pipeline is active (throttle log to once per 2 seconds)
        if self.stt_pipeline_active or self.is_speaking:
            if self._should_log_would_vocalize('stt_tts_active'):
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize emotion '{self.current_emotion}' but STT/TTS active (stt:{self.stt_pipeline_active}, speaking:{self.is_speaking})")
            return

        # Check sleep mode (throttle log to once per 2 seconds)
        if self.is_sleep_mode:
            if self._should_log_would_vocalize('sleeping'):
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize emotion '{self.current_emotion}' but robot is sleeping 💤")
            return

        # Check stay mode (throttle log to once per 2 seconds)
        if self.is_stay_mode:
            if self._should_log_would_vocalize('frozen'):
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize emotion '{self.current_emotion}' but robot is frozen 🧊")
            return

        # Calculate time since last phrase
        current_time = time.time()
        time_since_last = current_time - self.last_state_phrase_time

        # Check cooldown (but only log once to reduce spam)
        if time_since_last < self.state_phrase_cooldown:
            # Only log once per cooldown period
            if not self.cooldown_logged_for_emotion:
                self.node.get_logger().info(f"[StateVocalization] → Would vocalize emotion '{self.current_emotion}' but cooldown active ({time_since_last:.1f}s < {self.state_phrase_cooldown}s)")
                self.cooldown_logged_for_emotion = True
            return

        # Reset cooldown logging flag when cooldown expires
        self.cooldown_logged_for_emotion = False

        # Probabilistic response: 75% for most emotions, 5% for neutral
        response_probability = 0.05 if self.current_emotion == 'neutral' else 0.75
        if random.random() > response_probability:
            self.node.get_logger().info(f"[StateVocalization] → Skipping emotion '{self.current_emotion}' (random skip, {int(response_probability*100)}% response rate)")
            # Update cooldown timer so the skip counts towards cooldown
            self.last_state_phrase_time = time.time()
            return

        self.node.get_logger().info(f"[StateVocalization] ✅ Triggering phrase for emotion: {self.current_emotion}")

        # Reset cooldown logging flag since we're speaking now
        self.cooldown_logged_for_emotion = False

        # Speak an emotion phrase (in a separate thread)
        threading.Thread(
            target=self._speak_emotion_phrase,
            args=(self.current_emotion,),
            daemon=True
        ).start()

    def _speak_state_phrase(self, state):
        """Speak a random phrase for the given state."""
        try:
            self.node.get_logger().info(f"[StateVocalization] _speak_state_phrase called for: {state}")

            # Double-check priority flags to prevent race conditions
            # (Check again in case user started speaking between callback and thread execution)
            if self.is_muted or self.stt_pipeline_active or self.is_speaking:
                self.node.get_logger().info(f"[StateVocalization] State phrase '{state}' cancelled - muted or STT/TTS active")
                return

            # Get phrases for this state
            phrases = self.state_phrases.get(state, [])
            if not phrases:
                self.node.get_logger().warn(f"[StateVocalization] No phrases found for state: {state}")
                return

            # Pick a random phrase
            phrase = random.choice(phrases)

            # Update tracking
            self.last_state_phrase_time = time.time()
            self.last_vocalized_state = state

            self.node.get_logger().info(f"[StateVocalization] Speaking phrase: '{phrase}' for state: {state}")

            # Speak using the same method as filler TTS (respects voice transformer)
            self._generate_and_play_tts(phrase, is_filler=False)

        except Exception as e:
            self.node.get_logger().error(f"[StateVocalization] Error speaking state phrase: {e}")

    def _speak_emotion_phrase(self, emotion):
        """Speak a random phrase for the given emotion."""
        try:
            self.node.get_logger().info(f"[StateVocalization] _speak_emotion_phrase called for: {emotion}")

            # Double-check priority flags to prevent race conditions
            # (Check again in case user started speaking between callback and thread execution)
            if self.is_muted or self.stt_pipeline_active or self.is_speaking:
                self.node.get_logger().info(f"[StateVocalization] Emotion phrase '{emotion}' cancelled - muted or STT/TTS active")
                return

            # Get phrases for this emotion
            phrases = self.emotion_phrases.get(emotion, [])
            if not phrases:
                self.node.get_logger().warn(f"[StateVocalization] No phrases found for emotion: {emotion}")
                return

            # Pick a random phrase
            phrase = random.choice(phrases)

            # Update tracking
            self.last_state_phrase_time = time.time()
            self.last_vocalized_state = f'EMOTION_{emotion}'

            self.node.get_logger().info(f"[StateVocalization] Speaking phrase: '{phrase}' for emotion: {emotion}")

            # Speak using the same method as filler TTS (respects voice transformer)
            self._generate_and_play_tts(phrase, is_filler=False)

        except Exception as e:
            self.node.get_logger().error(f"[StateVocalization] Error speaking emotion phrase: {e}")
