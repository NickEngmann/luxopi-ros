#!/usr/bin/env python3
"""
Deep yogic breathing with chest expansion and micro-movements

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T22:04:04.818758
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class BreathingAnimation(AnimationPlugin):
    """Deep yogic breathing with chest expansion and micro-movements"""

    @property
    def name(self) -> str:
        return "breathing"

    @property
    def description(self) -> str:
        return "Deep yogic breathing with chest expansion and micro-movements"

    def get_category(self) -> str:
        return "idle"

    def get_keyframe_names(self) -> Optional[List[str]]:
        """Descriptive names for each keyframe."""
        return [
            "Keyframe 1",
            "Keyframe 2",
            "Keyframe 3",
            "Keyframe 4",
            "Keyframe 5",
            "Keyframe 6",
            "Keyframe 7",
            "Keyframe 8",
            "Keyframe 9",
            "Keyframe 10",
            "Keyframe 11",
            "Keyframe 12",
            "Keyframe 13",
            "Keyframe 14",
            "Keyframe 15",
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        """
        Return keyframes and durations.

        Keyframe format: [base, shoulder, elbow, wrist, roll, acceleration, hand/antenna]
        - base: Base rotation (-90° to 90°)
        - shoulder: Shoulder joint (0° to 180°)
        - elbow: Elbow joint (0° to 180°)
        - wrist: Wrist joint (0° to 180°)
        - roll: Roll joint (-2.5 to -0.5)
        - acceleration: Movement speed (10.0 to 22.5)
        - hand/antenna: Eyebrow/antenna expression (0.5 to 2.6)
        """
        base_pos = 0.0
        
        keyframes = [
            [base_pos +0.05, -0.65, 1.20, 1.00, -1.50, 1.0, 1.60],
            [base_pos -0.03, -0.88, 1.32, 1.43, -1.30, 1.0, 1.40],
            [base_pos +0.04, -0.95, 1.34, 1.50, -1.80, 1.0, 1.50],
            [base_pos +0.05, -1.05, 1.38, 1.60, -0.90, 1.0, 1.60],
            [base_pos -0.05, -1.10, 1.42, 1.68, -2.00, 1.0, 1.40],
            [base_pos +0.02, -1.08, 1.41, 1.66, -0.80, 1.0, 1.50],
            [base_pos +0.06, -1.06, 1.40, 1.64, -1.70, 1.0, 1.60],
            [base_pos -0.03, -1.00, 1.36, 1.55, -1.10, 1.0, 1.40],
            [base_pos, -0.85, 1.30, 1.45, -1.90, 1.0, 1.50],
            [base_pos +0.05, -0.65, 1.20, 1.25, -0.85, 1.0, 1.60],
            [base_pos -0.03, -0.62, 1.18, 1.22, -2.20, 1.0, 1.40],
            [base_pos +0.02, -0.72, 1.24, 1.32, -0.75, 1.0, 1.50],
            [base_pos +0.05, -0.80, 1.28, 1.38, -1.60, 1.0, 1.60],
            [base_pos -0.03, -0.84, 1.20, 1.39, -1.30, 1.0, 1.40],
            [base_pos +0.02, -0.65, 1.20, 1.00, -1.50, 1.0, 1.50],
        ]

        durations = [0.69, 0.30, 0.30, 0.30, 0.58, 0.58, 0.30, 0.56, 0.30, 0.44, 0.30, 0.30, 0.30, 0.30, 0.50]

        return keyframes, durations
