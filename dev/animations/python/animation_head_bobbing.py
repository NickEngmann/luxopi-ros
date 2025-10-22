#!/usr/bin/env python3
"""
Rhythmic head bobbing to an internal beat

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T21:53:52.402980
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class HeadBobbingAnimation(AnimationPlugin):
    """Rhythmic head bobbing to an internal beat"""

    @property
    def name(self) -> str:
        return "head_bobbing"

    @property
    def description(self) -> str:
        return "Rhythmic head bobbing to an internal beat"

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
            [base_pos, -0.65, 1.20, 1.00, -1.50, 4.9, 1.60],
            [base_pos, -0.65, 1.25, 0.85, -1.30, 4.5, 1.40],
            [base_pos, -0.80, 1.15, 1.15, -1.70, 4.0, 1.50],
            [base_pos, -0.68, 1.22, 0.90, -1.40, 2.5, 1.60],
            [base_pos, -0.78, 1.18, 1.10, -1.60, 3.3, 1.40],
            [base_pos, -0.60, 1.30, 0.80, -1.20, 3.9, 1.50],
            [base_pos, -0.85, 1.10, 1.20, -1.80, 4.2, 1.60],
            [base_pos -0.20, -0.70, 1.20, 0.95, -1.00, 1.3, 1.40],
            [base_pos +0.20, -0.70, 1.20, 0.95, -2.00, 1.7, 1.50],
            [base_pos, -0.65, 1.25, 0.85, -1.50, 3.6, 1.60],
            [base_pos, -0.80, 1.20, 1.05, -1.50, 2.8, 1.40],
            [base_pos, -0.65, 1.20, 1.00, -1.50, 1.1, 1.50],
        ]

        durations = [0.50, 1.12, 0.67, 0.30, 0.70, 1.27, 0.85, 0.30, 0.30, 0.60, 0.50, 0.50]

        return keyframes, durations
