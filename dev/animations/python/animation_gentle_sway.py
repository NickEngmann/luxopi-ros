#!/usr/bin/env python3
"""
Natural human-like swaying with subtle breathing and micro-adjustments

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T22:05:33.641675
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class GentleSwayAnimation(AnimationPlugin):
    """Natural human-like swaying with subtle breathing and micro-adjustments"""

    @property
    def name(self) -> str:
        return "gentle_sway"

    @property
    def description(self) -> str:
        return "Natural human-like swaying with subtle breathing and micro-adjustments"

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
            [0.00, -0.65, 1.20, 1.00, -1.50, 1.0, 1.60],
            [0.00, -0.88, 1.32, 1.42, -1.60, 1.0, 1.40],
            [0.09, -0.78, 1.25, 1.38, -1.20, 1.0, 1.50],
            [0.24, -0.70, 1.18, 1.45, -1.80, 1.0, 1.60],
            [0.27, -0.56, 1.16, 1.47, -0.90, 1.0, 1.40],
            [0.51, -0.60, 1.08, 1.52, -2.10, 1.0, 1.50],
            [0.60, -0.70, 1.05, 1.54, -0.80, 1.0, 1.60],
            [0.42, -0.65, 1.12, 1.45, -1.90, 1.0, 1.40],
            [0.12, -0.72, 1.20, 1.38, -1.10, 1.0, 1.50],
            [-0.09, -0.76, 1.22, 1.36, -2.00, 1.0, 1.60],
            [-0.30, -0.73, 1.18, 1.40, -0.85, 1.0, 1.40],
            [-0.54, -0.62, 1.10, 1.48, -1.70, 1.0, 1.50],
            [-0.60, -0.54, 1.08, 1.46, -0.90, 1.0, 1.60],
            [-0.24, -0.74, 1.20, 1.40, -1.60, 1.0, 1.40],
            [-0.05, -0.80, 1.26, 1.41, -1.30, 1.0, 1.50],
            [0.00, -0.80, 1.29, 1.40, -1.50, 1.0, 1.60],
            [0.00, -0.65, 1.20, 1.00, -1.50, 1.0, 1.40],
        ]

        durations = [0.39, 0.55, 0.58, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.34, 0.67, 0.30, 0.30, 0.32, 0.50]

        return keyframes, durations
