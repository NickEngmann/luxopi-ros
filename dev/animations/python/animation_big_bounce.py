#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-21 17:15

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T20:18:36.118795
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class BigBounceAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-21 17:15"""

    @property
    def name(self) -> str:
        return "big_bounce"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-21 17:15"

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
            "Keyframe 28",
            "Keyframe 29",
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
            [-0.03, -0.87, 1.22, 0.99, -1.08, 225.9, 1.60],
            [-0.36, -1.35, 2.15, 0.99, -1.75, 146.7, 1.40],
            [0.42, -0.80, 0.83, 0.97, -0.96, 230.4, 1.50],
            [0.42, -1.63, 2.14, 1.02, -1.74, 158.8, 1.46],
            [0.00, -0.64, 0.32, 0.57, -1.08, 217.2, 1.40],
            [-0.21, -0.76, 2.19, 0.98, -1.82, 209.0, 1.50],
            [-0.82, -0.71, 0.94, 0.83, -0.90, 220.5, 1.60],
            [-0.80, -0.71, 0.68, 0.26, -2.02, 225.0, 1.40],
            [0.29, -0.89, 0.73, 0.07, -1.01, 144.8, 1.50],
            [0.29, -1.41, 2.11, 0.98, -2.12, 232.0, 1.60],
            [0.29, -0.73, 0.79, 0.14, -1.23, 204.5, 1.40],
            [0.02, -1.52, 1.93, 1.00, -1.96, 196.2, 1.35],
            [0.02, -1.51, 1.93, 0.98, -1.03, 151.8, 1.45],
            [0.02, -0.97, 0.92, 0.18, -1.89, 207.1, 1.40],
            [0.02, -1.52, 2.03, 0.87, -1.22, 241.6, 1.35],
            [0.02, -0.74, 0.71, 0.06, -1.96, 201.5, 1.60],
            [0.02, -1.64, 2.38, 0.61, -1.00, 222.2, 1.26],
            [-0.49, -0.80, 1.07, 0.35, -1.90, 165.8, 1.50],
            [-0.51, -1.37, 2.41, 0.61, -0.93, 199.6, 1.60],
            [-0.51, -0.69, 0.84, 0.06, -1.86, 206.6, 1.40],
            [-0.50, -1.12, 2.45, 0.33, -1.11, 148.9, 1.50],
            [-0.15, -0.78, 1.03, 0.14, -1.81, 210.7, 1.60],
            [0.13, -1.28, 2.39, 0.33, -0.99, 223.8, 1.40],
            [0.19, -0.78, 1.08, 0.15, -1.78, 243.8, 1.50],
            [0.47, -1.39, 2.41, 0.44, -0.94, 160.7, 1.60],
            [-1.30, -0.68, 0.91, -0.04, -1.91, 205.1, 1.40],
            [0.74, -0.65, 0.73, 0.23, -0.82, 191.8, 1.50],
            [0.12, -1.41, 2.22, 0.74, -1.85, 229.9, 1.60],
            [0.12, -0.89, 1.16, 1.36, -1.50, 180.8, 1.40],
        ]

        durations = [0.87, 1.34, 1.10, 1.84, 1.31, 1.03, 0.43, 0.75, 1.40, 1.42, 1.53, 0.30, 1.18, 1.18, 1.46, 1.56, 1.46, 1.10, 1.40, 1.16, 1.15, 1.17, 1.02, 1.25, 2.23, 1.25, 1.68, 1.10, 0.50]

        return keyframes, durations
