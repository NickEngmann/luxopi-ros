#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-21 20:34

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T20:38:25.354514
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class StretchAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-21 20:34"""

    @property
    def name(self) -> str:
        return "stretch"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-21 20:34"

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
            "Keyframe 18",
            "Keyframe 19",
            "Keyframe 20",
            "Keyframe 21",
            "Keyframe 22",
            "Keyframe 23",
            "Keyframe 24",
            "Keyframe 25",
            "Keyframe 26",
            "Keyframe 27",
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
            [0.12, -0.64, 1.18, 1.19, -1.03, 1.6, 1.60],
            [0.09, -0.56, 1.24, 1.57, -1.85, 4.3, 1.40],
            [0.09, -0.73, 0.11, 1.64, -0.96, 4.4, 1.50],
            [0.04, -0.72, -0.12, 0.15, -1.95, 1.2, 1.60],
            [0.04, -0.48, 0.37, -0.16, -0.99, 3.5, 1.84],
            [0.05, -0.64, 0.01, -0.20, -1.84, 3.4, 1.50],
            [0.05, -0.25, 0.04, -0.04, -0.91, 3.4, 1.98],
            [-1.09, -0.33, -0.02, -0.01, -1.82, 3.2, 1.80],
            [-1.85, -0.42, 0.01, 0.00, -0.90, 3.5, 1.93],
            [-1.29, -0.48, 0.06, 0.05, -2.09, 4.7, 2.04],
            [-1.06, -0.57, 0.14, -0.35, -1.05, 4.6, 1.40],
            [0.09, -0.02, -0.17, -0.19, -1.81, 2.3, 1.81],
            [0.09, 0.15, -0.25, -0.12, -1.00, 3.4, 1.95],
            [0.09, -0.38, -0.16, -0.01, -2.06, 4.0, 1.81],
            [0.73, -0.45, -0.18, 0.01, -0.91, 4.0, 1.94],
            [1.18, -0.30, -0.21, -0.18, -2.01, 4.2, 1.99],
            [0.09, -0.31, -0.21, -0.18, -0.88, 3.9, 1.79],
            [0.09, -0.35, -0.52, -0.42, -1.81, 2.1, 1.91],
            [0.09, -0.45, 0.30, 0.28, -1.00, 4.7, 2.04],
            [0.09, -0.61, 1.19, 0.65, -1.96, 3.9, 1.40],
            [0.09, -0.57, 1.79, 1.29, -1.05, 1.4, 1.50],
            [0.09, 0.27, 2.07, 0.76, -2.01, 3.0, 1.98],
            [0.09, 0.52, 1.74, 0.82, -1.07, 4.5, 1.86],
            [0.09, 0.49, 1.89, 1.04, -1.94, 3.4, 1.95],
            [0.09, 0.47, 1.71, 0.89, -1.11, 3.2, 2.04],
            [0.09, -0.62, 1.18, 1.27, -1.94, 2.4, 1.40],
            [0.09, -0.63, 0.86, 1.27, -1.50, 1.4, 1.50],
        ]

        durations = [0.38, 0.73, 0.94, 0.64, 0.46, 0.53, 0.75, 0.51, 0.42, 0.72, 1.29, 0.30, 0.43, 0.44, 0.44, 0.65, 0.35, 0.87, 1.02, 0.69, 1.06, 0.38, 0.30, 0.30, 1.32, 0.30, 0.50]

        return keyframes, durations
