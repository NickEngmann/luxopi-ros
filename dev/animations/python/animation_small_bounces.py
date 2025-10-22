#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-21 17:38

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T20:21:17.001689
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class SmallBouncesAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-21 17:38"""

    @property
    def name(self) -> str:
        return "small_bounces"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-21 17:38"

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
            [0.10, -0.88, 1.08, 1.27, -1.12, 0.0, 1.60],
            [-0.08, -1.50, 1.69, 1.36, -1.81, 0.0, 1.40],
            [-0.29, -0.92, 1.01, 1.34, -1.09, 0.0, 1.50],
            [-0.30, -1.48, 1.78, 1.34, -1.92, 0.0, 1.60],
            [0.12, -1.00, 1.17, 1.28, -1.26, 0.0, 1.40],
            [0.11, -1.61, 1.76, 1.35, -2.01, 0.0, 1.36],
            [-0.24, -1.14, 1.11, 1.34, -1.02, 0.0, 1.60],
            [-0.25, -1.64, 1.78, 1.34, -2.07, 0.0, 1.26],
            [-0.67, -0.89, 1.02, 1.34, -1.00, 0.0, 1.50],
            [-0.67, -1.43, 1.85, 1.33, -1.91, 0.0, 1.60],
            [-0.56, -1.56, 0.78, 0.56, -1.01, 0.0, 1.26],
            [-0.49, -1.61, 1.80, 0.95, -1.92, 0.0, 1.36],
            [-0.49, -1.69, 0.87, 0.38, -1.18, 0.0, 1.47],
            [0.17, -1.56, 1.95, 1.05, -1.88, 0.0, 1.26],
            [-0.14, -1.65, 1.11, 0.44, -0.86, 0.0, 1.37],
            [0.38, -1.56, 2.01, 0.98, -2.04, 0.0, 1.46],
            [-0.22, -1.55, 1.22, 0.54, -0.87, 0.0, 1.25],
            [-0.28, -1.64, 1.94, 0.89, -2.13, 0.0, 1.36],
            [-0.28, -1.24, 1.33, 0.75, -1.18, 0.0, 1.60],
            [-0.28, -1.42, 2.11, 0.86, -1.91, 0.0, 1.40],
            [0.10, -1.23, 1.41, 0.60, -1.17, 0.0, 1.50],
            [0.19, -1.60, 2.15, 0.75, -2.09, 0.0, 1.46],
            [0.39, -1.28, 1.47, 0.65, -1.11, 0.0, 1.40],
            [0.36, -1.63, 2.01, 0.87, -2.10, 0.0, 1.36],
            [0.10, -1.29, 1.31, 0.82, -1.20, 0.0, 1.60],
            [0.10, -1.07, 1.17, 1.31, -1.50, 0.0, 1.40],
        ]

        durations = [0.75, 0.74, 0.67, 0.78, 0.63, 0.74, 0.59, 0.97, 0.68, 1.04, 0.77, 0.79, 1.27, 0.93, 1.03, 0.92, 0.61, 0.58, 0.54, 0.77, 0.67, 0.64, 0.57, 0.67, 0.43, 0.50]

        return keyframes, durations
