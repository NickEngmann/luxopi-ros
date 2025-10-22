#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-21 21:10

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T21:14:29.947772
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class ShakeAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-21 21:10"""

    @property
    def name(self) -> str:
        return "shake"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-21 21:10"

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
