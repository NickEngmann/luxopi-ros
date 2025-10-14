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
from luxo_behaviors.state_machine import LuxoState


class StateVocalizationBehavior:
    """Mixin class for state-specific vocalizations."""

    def setup_state_vocalization(self):
        """Initialize state vocalization attributes and subscriptions."""

        # Vocalization state
        self.last_state_phrase_time = 0
        self.state_phrase_cooldown = 8.0  # Seconds between state phrases
        self.current_robot_state = None
        self.last_vocalized_state = None
        self.current_emotion = None
        self.collision_detected = False

        # Priority flag - STT->LLM->TTS pipeline is always prioritized
        self.stt_pipeline_active = False

        # Subscribe to state changes
        self.state_sub = self.node.create_subscription(
            String,
            '/luxo/current_state',
            self.state_change_callback,
            10
        )

        # Subscribe to emotion detection
        self.emotion_sub = self.node.create_subscription(
            String,
            '/camera/emotion',
            self.emotion_callback,
            10
        )

        # Subscribe to collision severity
        self.collision_sub = self.node.create_subscription(
            String,
            '/collision/severity',
            self.collision_callback,
            10
        )

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
                "Purr",
                "Mmm",
                "That feels nice",
                "I like that",
                "Keep going",
                "So nice",
                "Purring",
                "Mmmhmm",
                "Wonderful",
                "This is great",
                "Love this",
                "Purrfect",
                "More please",
                "Feels good",
                "So soothing",
                "Yes yes yes",
                "Happy noises",
                "Purr purr",
                "Contentment",
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

        # Emotion-specific phrases (for EMOTION_REACTING state)
        self.emotion_phrases = {
            'happy': [
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

            'sad': [
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

            'angry': [
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

            'surprised': [
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

    def state_change_callback(self, msg):
        """Handle state changes and speak appropriate phrases."""
        new_state = msg.data
        self.current_robot_state = new_state

        # Don't vocalize for IDLE state
        if new_state == 'IDLE':
            return

        # Don't vocalize if we just vocalized this state recently
        if new_state == self.last_vocalized_state:
            return

        # Check cooldown
        current_time = time.time()
        if current_time - self.last_state_phrase_time < self.state_phrase_cooldown:
            return

        # Priority: Don't interrupt STT pipeline
        if self.stt_pipeline_active or self.is_speaking:
            return

        # Speak a phrase for this state (in a separate thread to avoid blocking)
        threading.Thread(
            target=self._speak_state_phrase,
            args=(new_state,),
            daemon=True
        ).start()

    def emotion_callback(self, msg):
        """Handle emotion detection and speak appropriate phrases (only in EMOTION_REACTING state)."""
        self.current_emotion = msg.data.lower()

        # Only vocalize emotions when in EMOTION_REACTING state
        if self.current_robot_state != 'EMOTION_REACTING':
            return

        # Don't repeat same emotion
        if self.last_vocalized_state == f'EMOTION_{self.current_emotion}':
            return

        # Check cooldown
        current_time = time.time()
        if current_time - self.last_state_phrase_time < self.state_phrase_cooldown:
            return

        # Priority: Don't interrupt STT pipeline
        if self.stt_pipeline_active or self.is_speaking:
            return

        # Speak an emotion phrase (in a separate thread)
        threading.Thread(
            target=self._speak_emotion_phrase,
            args=(self.current_emotion,),
            daemon=True
        ).start()

    def collision_callback(self, msg):
        """Handle collision events and speak collision phrases."""
        severity = msg.data

        # Only speak on DANGER or COLLISION severity
        if severity not in ['DANGER', 'COLLISION']:
            return

        # Don't spam collision phrases
        current_time = time.time()
        if current_time - self.last_state_phrase_time < 3.0:  # Shorter cooldown for collisions
            return

        # Priority: Don't interrupt STT pipeline
        if self.stt_pipeline_active or self.is_speaking:
            return

        # Speak a collision phrase (in a separate thread)
        threading.Thread(
            target=self._speak_state_phrase,
            args=('COLLISION_AVOIDING',),
            daemon=True
        ).start()

    def _speak_state_phrase(self, state):
        """Speak a random phrase for the given state."""
        try:
            # Get phrases for this state
            phrases = self.state_phrases.get(state, [])
            if not phrases:
                return

            # Pick a random phrase
            phrase = random.choice(phrases)

            # Update tracking
            self.last_state_phrase_time = time.time()
            self.last_vocalized_state = state

            # Speak using the same method as filler TTS (respects voice transformer)
            self._generate_and_play_tts(phrase, is_filler=False)

        except Exception as e:
            if self.verbose:
                self.node.get_logger().error(f"Error speaking state phrase: {e}")

    def _speak_emotion_phrase(self, emotion):
        """Speak a random phrase for the given emotion."""
        try:
            # Get phrases for this emotion
            phrases = self.emotion_phrases.get(emotion, [])
            if not phrases:
                return

            # Pick a random phrase
            phrase = random.choice(phrases)

            # Update tracking
            self.last_state_phrase_time = time.time()
            self.last_vocalized_state = f'EMOTION_{emotion}'

            # Speak using the same method as filler TTS (respects voice transformer)
            self._generate_and_play_tts(phrase, is_filler=False)

        except Exception as e:
            if self.verbose:
                self.node.get_logger().error(f"Error speaking emotion phrase: {e}")
