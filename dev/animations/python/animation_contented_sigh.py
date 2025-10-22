#!/usr/bin/env python3
"""
Deep satisfying sigh with shoulders dropping and body relaxing

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T21:57:46.455118
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class ContentedSighAnimation(AnimationPlugin):
    """Deep satisfying sigh with shoulders dropping and body relaxing"""

    @property
    def name(self) -> str:
        return "contented_sigh"

    @property
    def description(self) -> str:
        return "Deep satisfying sigh with shoulders dropping and body relaxing"

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
            [base_pos +0.05, -0.65, 1.20, 1.00, -1.50, 4.4, 1.60],
            [base_pos -0.03, -0.80, 1.25, 1.35, -1.30, 2.4, 1.40],
            [base_pos +0.02, -1.00, 1.10, 1.60, -1.80, 3.1, 1.50],
            [base_pos +0.05, -1.05, 1.08, 1.62, -1.00, 3.5, 1.60],
            [base_pos -0.03, -0.90, 1.20, 1.50, -1.90, 4.8, 1.40],
            [base_pos +0.02, -0.60, 1.40, 1.20, -1.20, 1.2, 1.50],
            [base_pos +0.05, -0.40, 1.50, 1.00, -1.70, 4.4, 2.02],
            [base_pos -0.03, -0.30, 1.60, 0.80, -1.50, 5.0, 1.79],
            [base_pos +0.02, -0.50, 1.50, 0.90, -1.60, 2.7, 1.50],
            [base_pos +0.05, -0.75, 1.30, 1.10, -1.50, 1.5, 1.60],
            [base_pos -0.03, -0.65, 1.20, 1.00, -1.50, 2.6, 1.40],
            [base_pos, -0.63, 2.05, 1.05, -1.50, 4.6, 1.50],
            [base_pos +0.04, -0.01, 1.57, 1.00, -1.50, 4.3, 1.90],
            [base_pos -0.04, 0.23, 1.58, 0.98, -1.50, 10.0, 1.77],
            [base_pos +0.01, 0.51, 1.54, 0.79, -1.50, 10.0, 1.95],
        ]

        durations = [0.30, 0.30, 0.60, 0.75, 0.40, 0.30, 0.50, 0.30, 0.62, 0.30, 0.48, 0.59, 0.30, 1.30, 2.50]

        return keyframes, durations
