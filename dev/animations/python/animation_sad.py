#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-21 20:26

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T20:29:31.597666
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class SadAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-21 20:26"""

    @property
    def name(self) -> str:
        return "sad"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-21 20:26"

    def get_category(self) -> str:
        return "custom"

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
            "Keyframe 16",
            "Keyframe 17",
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
        keyframes = [
            [0.13, -0.83, 1.19, 1.31, -1.21, 11.3, 1.60],
            [0.13, -0.56, 1.74, 1.31, -1.97, 7.1, 1.40],
            [0.15, -0.08, 2.18, 0.61, -1.05, 6.0, 1.82],
            [0.10, 0.21, 2.33, 0.42, -1.82, 11.4, 1.96],
            [-1.00, 0.21, 2.28, 0.44, -1.15, 9.0, 1.76],
            [0.22, 0.21, 2.21, 0.51, -1.89, 8.7, 1.86],
            [1.16, -0.35, 2.22, 0.92, -1.07, 5.7, 2.00],
            [1.11, -0.76, 1.41, 1.57, -2.13, 9.0, 1.40],
            [1.15, -0.93, 1.02, 0.38, -0.97, 5.2, 1.50],
            [0.30, -1.06, 1.09, -0.07, -1.78, 5.2, 1.60],
            [0.14, -1.11, 0.69, -0.07, -1.13, 9.4, 1.40],
            [0.19, -1.10, 1.31, 1.58, -1.89, 5.0, 1.50],
            [0.13, -0.94, 2.21, 0.92, -1.11, 9.3, 1.60],
            [0.10, 0.25, 2.07, 0.82, -1.89, 11.0, 1.77],
            [0.10, 0.50, 2.05, 0.66, -1.14, 9.1, 1.95],
            [0.10, -0.24, 1.61, 1.31, -1.80, 11.8, 1.97],
            [0.10, -0.73, 1.19, 1.31, -1.50, 10.8, 1.40],
        ]

        durations = [0.51, 1.03, 0.41, 0.69, 0.73, 1.04, 1.26, 0.94, 0.80, 0.41, 1.22, 0.94, 0.82, 0.30, 0.92, 0.74, 0.50]

        return keyframes, durations
