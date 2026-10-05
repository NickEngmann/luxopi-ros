#!/usr/bin/env python3
"""
Response-based animation plugins for the LuxoPi system.
These animations are responses to commands or interactions.
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class NoddingAnimation(AnimationPlugin):
    """Make the arm nod 'yes' with playful wrist movement."""
    
    @property
    def name(self) -> str:
        return "nod"
    
    @property
    def description(self) -> str:
        return "Enthusiastic nodding motion with wrist articulation"
    
    def get_category(self) -> str:
        return "response"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Start at home 2", "First nod down", "First nod up", "Quick double nod down",
            "Quick double nod up", "Big nod down", "Big nod up", "Excited wiggle left",
            "Excited wiggle right", "Final affirmative nod", "Settle", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0],      # Start at home 2
            [base_pos+0.05, -0.65, 1.2, 1.35, -1.6, 20.0], # First nod down
            [base_pos+0.05, -0.65, 1.2, 0.0, -1.4, 21.0],  # First nod up
            [base_pos-0.05, -0.65, 1.2, 1.3, -1.5, 22.0],  # Quick double nod down
            [base_pos-0.05, -0.65, 1.2, 0.1, -1.5, 22.0],  # Quick double nod up
            [base_pos+0.1, -0.65, 1.2, 1.35, -1.7, 19.0],  # Big nod down
            [base_pos+0.1, -0.65, 1.2, 0.0, -1.3, 20.0],   # Big nod up
            [base_pos-0.15, -0.7, 1.3, 0.8, -1.8, 21.0],   # Excited wiggle left
            [base_pos+0.15, -0.6, 1.1, 0.8, -1.2, 21.0],   # Excited wiggle right
            [base_pos, -0.65, 1.2, 1.2, -1.5, 18.0],       # Final affirmative nod
            [base_pos, -0.65, 1.2, 1.0, -1.5, 16.0],       # Settle
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0]        # Return home 2
        ]
        
        # Fast, snappy nodding
        durations = [0.6, 0.35, 0.45, 0.35, 0.35, 0.4, 0.45, 0.35, 0.35, 0.35, 0.4, 0.9]
        
        return keyframes, durations


class HeadShakeAnimation(AnimationPlugin):
    """Make the arm shake 'no' with expressive disagreement."""
    
    @property
    def name(self) -> str:
        return "shake"
    
    @property
    def description(self) -> str:
        return "Expressive head shaking with varying intensity"
    
    def get_category(self) -> str:
        return "response"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Neutral", "Wind up", "Big shake right", "Big shake left",
            "Fast shake right", "Fast shake left", "Medium shake right",
            "Medium shake left", "Small shake right", "Small shake left",
            "Tiny shake", "Settle", "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.3, 0.8, 0.6, -1.5, 14.0],       # Neutral - back
            [base_pos-0.1, -0.4, 0.9, 0.7, -1.4, 16.0],   # Wind up - back
            [base_pos+0.35, -0.5, 0.9, 0.8, -2.1, 21.0],  # Big shake right - back
            [base_pos-0.4, -0.5, 0.9, 0.8, -0.9, 22.0],   # Big shake left - back
            [base_pos+0.3, -0.45, 0.85, 0.75, -2.0, 22.5], # Fast shake right - back
            [base_pos-0.35, -0.45, 0.85, 0.75, -1.0, 22.0], # Fast shake left - back
            [base_pos+0.25, -0.4, 0.8, 0.7, -1.9, 20.0],  # Medium shake right - back
            [base_pos-0.25, -0.4, 0.8, 0.7, -1.1, 20.0],  # Medium shake left - back
            [base_pos+0.15, -0.35, 0.75, 0.65, -1.7, 18.0], # Small shake right - back
            [base_pos-0.15, -0.35, 0.75, 0.65, -1.3, 18.0], # Small shake left - back
            [base_pos, -0.3, 0.7, 0.6, -1.5, 16.0],       # Tiny shake - back
            [base_pos, -0.4, 0.9, 0.7, -1.5, 14.0],       # Settle - back
            [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0],        # Return home 1
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0]       # Return home 2
        ]
        
        # Faster shakes
        durations = [0.7, 0.4, 0.55, 0.6, 0.45, 0.5, 0.4, 0.4, 0.35, 0.35, 0.4, 0.6, 0.7, 0.9]
        
        return keyframes, durations


class CloseAnimation(AnimationPlugin):
    """Move the arm to a closed/shutdown position."""
    
    @property
    def name(self) -> str:
        return "close"
    
    @property
    def description(self) -> str:
        return "Compact closing motion for shutdown or storage"
    
    def get_category(self) -> str:
        return "response"
    
    @property
    def preserve_base_position(self) -> bool:
        """This animation should not preserve base position - always returns to center."""
        return False
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Prepare fold", "Begin folding", "Continue fold", "Final position", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Use current base position for smooth transition
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.9, 1.0, 1.5, -1.3, 11.0],   # Prepare - slight right
            [base_pos, -0.9, 1.5, 1.6, -1.8, 10.5],   # Begin fold - left to balance
            [base_pos, -1.1, 2.0, 1.7, -2.2, 10.0],   # Continue - more left
            [base_pos, -1.4, 2.0, 1.8, -0.8, 10.0],   # Final closed - right extreme to balance
            [base_pos, -0.55, 1.2, 1.0, -2.0, 10.0]   # Go directly to home 2 (close) - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [1.64, 2.29, 2.4, 2.4, 1.3]
        
        return keyframes, durations


class StopAnimation(AnimationPlugin):
    """Immediately stop and return to neutral position."""
    
    @property
    def name(self) -> str:
        return "stop"
    
    @property
    def description(self) -> str:
        return "Emergency stop returning to safe neutral position"
    
    def get_category(self) -> str:
        return "response"
    
    @property
    def preserve_base_position(self) -> bool:
        """Emergency stop should center the base for safety."""
        return False
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Just return to a safe neutral position quickly, then home
        keyframes = [
            [0.0, 0.3, 0.7, 0.3, -1.5, 14.0],     # Safe neutral - center
            [0.0, 0.5, 1.3, 1.4, -1.5, 12.0],     # Return home 1 - neutral
            [0.0, -0.55, 1.2, 1.0, -2.0, 10.0]    # Return home 2 - neutral
        ]
        
        durations = [0.71, 0.58, 1.3]  # Scaled for safety but still relatively quick
        
        return keyframes, durations


class ListeningAnimation(AnimationPlugin):
    """Small, quiet acknowledgement that a user has the robot's attention."""

    @property
    def name(self) -> str:
        return "listening"

    @property
    def description(self) -> str:
        return "Lift into a calm attentive pose"

    def get_category(self) -> str:
        return "response"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Rest", "Attend", "Settle into listening"]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        return [
            [0.0, -0.65, 1.2, 1.0, -1.5, 10.0],
            [0.0, -0.56, 1.08, 1.26, -1.4, 11.0],
            [0.0, -0.62, 1.16, 1.12, -1.5, 10.0],
        ], [0.45, 0.4, 0.45]


class AcknowledgeAnimation(AnimationPlugin):
    """Brief single nod confirming receipt of a spoken command."""

    @property
    def name(self) -> str:
        return "acknowledge"

    @property
    def description(self) -> str:
        return "A short nod to acknowledge a command"

    def get_category(self) -> str:
        return "response"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Ready", "Nod", "Return"]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        return [
            [0.0, -0.65, 1.2, 1.0, -1.5, 11.0],
            [0.0, -0.48, 0.98, 1.22, -1.5, 13.0],
            [0.0, -0.65, 1.2, 1.0, -1.5, 11.0],
        ], [0.4, 0.45, 0.5]


class ThinkingCueAnimation(AnimationPlugin):
    """Brief, recognizable pause while the assistant processes a request."""

    @property
    def name(self) -> str:
        return "thinking"

    @property
    def description(self) -> str:
        return "A measured look-up while working on a request"

    def get_category(self) -> str:
        return "response"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Neutral", "Consider", "Hold the thought"]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        return [
            [0.0, -0.65, 1.2, 1.0, -1.5, 10.0],
            [0.0, -0.88, 0.95, 1.45, -1.2, 11.0],
            [0.0, -0.82, 1.02, 1.38, -1.4, 10.0],
        ], [0.5, 0.5, 0.4]


class SpeakingCueAnimation(AnimationPlugin):
    """Subtle movement cue that the robot is delivering a response."""

    @property
    def name(self) -> str:
        return "speaking"

    @property
    def description(self) -> str:
        return "A small conversational sway while responding"

    def get_category(self) -> str:
        return "response"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Compose", "Speak", "Ease back"]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        return [
            [0.0, -0.65, 1.2, 1.0, -1.5, 10.0],
            [0.06, -0.58, 1.14, 1.12, -1.35, 11.0],
            [0.0, -0.64, 1.18, 1.02, -1.5, 10.0],
        ], [0.45, 0.5, 0.45]


class SettleAnimation(AnimationPlugin):
    """Return gently to the familiar idle pose after a voice session."""

    @property
    def name(self) -> str:
        return "settle"

    @property
    def description(self) -> str:
        return "A calm transition back to idle"

    def get_category(self) -> str:
        return "response"

    @property
    def preserve_base_position(self) -> bool:
        return False

    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Release", "Balance", "Home"]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        return [
            [0.0, -0.76, 1.26, 1.24, -1.5, 9.0],
            [0.0, -0.7, 1.22, 1.12, -1.5, 9.0],
            [0.0, -0.65, 1.2, 1.0, -1.5, 9.0],
        ], [0.45, 0.55, 0.65]
