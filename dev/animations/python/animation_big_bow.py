#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-21 16:40

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T20:04:19.332623
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class BigBowAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-21 16:40"""

    @property
    def name(self) -> str:
        return "big_bow"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-21 16:40"

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
