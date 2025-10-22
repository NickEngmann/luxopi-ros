#!/usr/bin/env python3
"""
Quick startled reaction with panic and recovery

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T21:32:21.627563
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class StartledAnimation(AnimationPlugin):
    """Quick startled reaction with panic and recovery"""

    @property
    def name(self) -> str:
        return "startled"

    @property
    def description(self) -> str:
        return "Quick startled reaction with panic and recovery"

    def get_category(self) -> str:
        return "emotion"

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
            [-0.03, -0.37, 0.79, 1.02, -1.50, 14.0, 2.01],
            [0.00, -0.25, 0.75, 0.45, -1.30, 15.0, 1.77],
            [0.00, -0.90, 1.40, 0.30, -1.90, 13.0, 1.50],
            [-0.40, -0.50, 0.20, 1.50, -0.80, 0.0, 1.60],
            [-0.50, -0.60, 0.10, 1.60, -2.10, 0.0, 1.40],
            [-0.60, -0.55, 0.15, 1.55, -0.75, 21.0, 1.50],
            [-0.40, -0.55, 0.15, 1.55, -2.20, 21.0, 1.60],
            [-0.30, -0.40, 0.60, 1.00, -1.00, 18.0, 1.82],
            [-0.22, -0.99, 0.91, 1.53, -1.80, 16.0, 1.50],
            [-0.49, -0.41, 0.98, 1.25, -1.20, 17.0, 2.02],
            [0.26, -0.40, 0.94, 1.08, -1.90, 17.0, 1.82],
            [-0.10, -0.30, 0.90, 0.60, -1.30, 15.0, 1.89],
            [0.00, -0.40, 1.00, 0.50, -1.70, 14.0, 2.02],
            [0.00, -0.50, 1.10, 0.40, -1.50, 13.0, 1.40],
            [0.10, -0.45, 1.05, 0.45, -1.60, 14.0, 1.94],
            [0.00, -0.40, 1.00, 0.50, -1.50, 13.0, 2.02],
            [0.00, 0.20, 1.30, 1.50, -1.50, 15.0, 1.76],
            [0.00, -0.65, 1.20, 1.00, -1.50, 10.0, 1.50],
        ]

        durations = [0.38, 1.12, 2.00, 0.30, 0.30, 0.30, 0.68, 0.76, 0.64, 0.55, 0.53, 0.60, 0.55, 0.30, 0.30, 0.95, 0.73, 0.50]

        return keyframes, durations
