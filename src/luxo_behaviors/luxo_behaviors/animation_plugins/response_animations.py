#!/usr/bin/env python3
"""
Response-based animation plugins for the LuxoPi system.
These animations are responses to commands or interactions.
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class NoddingAnimation(AnimationPlugin):
    """Smooth, natural nodding 'yes' motion with satisfying rhythm."""

    @property
    def name(self) -> str:
        return "nod"

    @property
    def description(self) -> str:
        return "Natural nodding motion with varied tempo and organic movement"

    def get_category(self) -> str:
        return "response"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Start position", "First nod down", "First nod up",
            "Second nod down", "Second nod up", "Return home"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0

        keyframes = [
            [base_pos, -0.54, 0.85, 1.09, -1.00, 89.3, 1.60],
            [base_pos -0.08, -0.54, 0.76, 0.66, -2.05, 50.6, 1.40],
            [base_pos -0.03, -0.54, 0.96, 1.68, -0.98, 115.3, 1.50],
            [base_pos, -0.54, 0.52, 0.59, -2.03, 139.1, 1.60],
            [base_pos -0.08, -0.52, 1.11, 1.58, -1.04, 43.9, 1.40],
            [base_pos -0.03, -0.47, 1.01, 0.87, -1.50, 36.8, 1.94],
        ]

        durations = [0.40, 0.69, 0.83, 0.94, 0.73, 0.50]

        return keyframes, durations


class HeadShakeAnimation(AnimationPlugin):
    """Ultra-fast, emphatic 'no' shake with maximum speed and personality."""

    @property
    def name(self) -> str:
        return "shake"

    @property
    def description(self) -> str:
        return "Fast, emphatic head shake with wide sweeping motions"

    def get_category(self) -> str:
        return "response"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Start position", "Big swing left", "Big swing right", "Extreme left",
            "Extreme right", "Slow down left", "Center sweep", "Return home"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        keyframes = [
            [0.03, -0.46, 0.99, 0.94, -1.01, 0.0, 2.04],
            [-1.14, -0.46, 1.01, 1.14, -1.87, 0.0, 1.84],
            [0.93, -0.40, 1.02, 0.88, -1.12, 0.0, 1.92],
            [-1.10, -0.54, 1.98, 0.34, -1.83, 0.0, 1.60],
            [1.29, -0.46, 1.75, 0.53, -1.01, 0.0, 1.84],
            [-0.75, -0.48, 1.15, 0.89, -1.91, 0.0, 1.94],
            [0.45, -0.48, 1.03, 0.87, -1.07, 0.0, 2.04],
            [-0.04, -0.47, 1.03, 0.88, -1.50, 0.0, 1.84],
        ]

        durations = [0.79, 1.24, 2.04, 1.72, 1.61, 0.72, 0.31, 0.50]

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
            [base_pos, -0.9, 1.0, 1.5, -1.3, 11.0, 1.60],   # Prepare - slight right
            [base_pos, -0.9, 1.5, 1.6, -1.8, 10.5, 1.40],   # Begin fold - left to balance
            [base_pos, -1.1, 2.0, 1.7, -2.2, 10.0, 1.40],   # Continue - more left
            [base_pos, -1.4, 2.0, 1.8, -0.8, 10.0, 1.60],   # Final closed - right extreme to balance
            [base_pos, -0.55, 1.2, 1.0, -2.0, 10.0, 1.50]   # Go directly to home 2 (close) - neutral
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
            [0.0, 0.3, 0.7, 0.3, -1.5, 14.0, 1.50],     # Safe neutral - center
            [0.0, 0.5, 1.3, 1.4, -1.5, 12.0, 1.50],     # Return home 1 - neutral
            [0.0, -0.55, 1.2, 1.0, -2.0, 10.0, 1.50]    # Return home 2 - neutral
        ]

        durations = [0.71, 0.58, 1.3]  # Scaled for safety but still relatively quick

        return keyframes, durations


class SimpleBowAnimation(AnimationPlugin):
    """A simple, quick bow gesture for polite acknowledgment."""

    @property
    def name(self) -> str:
        return "simple_bow"

    @property
    def description(self) -> str:
        return "Quick polite bow with graceful movement"

    def get_category(self) -> str:
        return "response"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Start position", "Prepare bow", "Tilt forward",
            "Deep bow", "Rise up", "Return home"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0

        keyframes = [
            [base_pos, -1.04, 1.40, 0.82, -1.26, 10.8, 1.60],
            [base_pos -0.08, -0.76, 0.60, 1.25, -1.80, 14.8, 1.40],
            [base_pos -0.03, -0.50, 0.47, 1.27, -1.12, 11.2, 1.50],
            [base_pos, -0.36, 2.27, 0.72, -2.00, 13.0, 2.01],
            [base_pos -0.08, 0.33, 2.28, 0.42, -1.06, 11.6, 1.80],
            [base_pos -0.03, -1.03, 1.14, 1.02, -1.50, 11.0, 1.50],
        ]

        durations = [0.90, 0.51, 1.29, 0.64, 1.73, 0.50]

        return keyframes, durations


class BigBowAnimation(AnimationPlugin):
    """A grand, elaborate bow for special occasions or dramatic responses."""

    @property
    def name(self) -> str:
        return "big_bow"

    @property
    def description(self) -> str:
        return "Elaborate theatrical bow with flourish and personality"

    def get_category(self) -> str:
        return "response"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Prepare stance", "Wind up", "Sweep left", "Tilt preparation",
            "Deep dip", "Gather energy", "Extend outward", "Arc high",
            "Peak expression", "Descend gracefully", "Mid bow", "Hold pose",
            "Sweep gesture", "Extend again", "Rise dramatically",
            "Final flourish", "Side gesture", "Collect composure", "Return home"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        keyframes = [
            [0.01, -0.80, 1.29, 1.21, -1.11, 23.5, 1.60],
            [0.33, -0.47, 0.74, 1.12, -1.90, 17.4, 1.84],
            [-0.74, -0.47, 0.80, 1.08, -0.98, 18.6, 1.94],
            [-0.37, -0.40, 0.32, 0.50, -1.93, 20.1, 2.02],
            [0.04, -0.40, 0.02, 0.37, -0.91, 12.5, 1.82],
            [0.04, -0.86, 0.69, 0.37, -1.83, 19.5, 1.50],
            [0.04, -0.42, 0.22, 1.51, -0.87, 23.9, 2.03],
            [-0.01, -0.14, 2.10, 0.52, -1.82, 18.4, 1.74],
            [-0.01, 0.35, 2.39, 0.04, -0.98, 24.8, 1.91],
            [0.32, -0.71, 1.04, 1.02, -2.01, 13.2, 1.60],
            [0.32, -0.00, 1.86, 0.88, -1.09, 14.3, 1.70],
            [0.32, 0.52, 1.86, 0.61, -2.06, 17.9, 1.96],
            [-0.58, -0.31, 0.33, 1.16, -1.19, 22.0, 1.99],
            [-0.58, -0.00, 1.58, 1.14, -2.14, 23.4, 1.70],
            [-0.58, 0.33, 2.01, 0.54, -0.87, 20.4, 1.90],
            [-0.02, -0.37, 0.64, 0.06, -2.10, 21.4, 2.01],
            [0.55, -0.51, 0.29, -0.31, -0.86, 14.2, 1.40],
            [-0.02, -0.51, 0.54, -0.22, -2.06, 14.5, 1.50],
            [-0.02, -0.79, 1.16, 0.96, -1.50, 24.8, 1.60],
        ]

        durations = [0.77, 0.64, 0.79, 0.52, 0.72, 1.29, 1.75, 0.71, 2.02, 0.88, 0.53, 1.92, 0.94, 0.78, 1.61, 1.02, 0.51, 1.09, 0.50]

        return keyframes, durations