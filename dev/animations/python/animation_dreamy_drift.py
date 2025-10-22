#!/usr/bin/env python3
"""
Weightless floating with smooth figure-8 patterns

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T21:51:49.067302
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class DreamyDriftAnimation(AnimationPlugin):
    """Weightless floating with smooth figure-8 patterns"""

    @property
    def name(self) -> str:
        return "dreamy_drift"

    @property
    def description(self) -> str:
        return "Weightless floating with smooth figure-8 patterns"

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
            [0.00, -0.65, 1.20, 1.00, -1.50, 3.1, 1.60],
            [0.08, -0.88, 1.27, 1.43, -1.30, 1.6, 1.40],
            [0.15, -1.05, 1.05, 1.65, -1.80, 3.8, 1.50],
            [-0.40, -1.00, 1.10, 1.60, -0.85, 4.0, 1.60],
            [-0.50, -0.95, 1.15, 1.55, -2.10, 4.3, 1.40],
            [0.30, -0.85, 1.25, 1.45, -0.80, 1.6, 1.50],
            [0.45, -0.55, 1.45, 1.15, -1.90, 1.5, 1.60],
            [0.35, -0.75, 1.30, 1.35, -1.00, 4.0, 1.40],
            [0.00, -0.90, 1.20, 1.50, -1.70, 4.6, 1.50],
            [-0.35, -0.80, 1.25, 1.40, -0.90, 5.0, 1.60],
            [-0.20, -0.65, 1.35, 1.25, -1.80, 2.5, 1.40],
            [0.00, -0.75, 1.28, 1.35, -1.10, 3.4, 1.50],
            [0.00, -0.82, 1.29, 1.38, -1.60, 1.1, 1.60],
            [0.00, -0.84, 1.20, 1.39, -1.40, 3.6, 1.40],
            [0.00, -0.65, 1.20, 1.00, -1.50, 4.9, 1.50],
            [-0.21, -0.64, 0.71, 0.78, -1.50, 3.2, 1.60],
            [-0.07, -0.66, 0.47, 0.69, -1.50, 2.1, 1.40],
            [0.00, -0.66, 0.29, 0.02, -1.50, 2.9, 1.50],
            [-0.00, -0.60, 1.19, 1.00, -1.50, 2.1, 1.60],
        ]

        durations = [0.41, 0.79, 0.85, 0.73, 1.05, 0.93, 1.18, 0.82, 0.30, 0.68, 0.30, 0.45, 0.36, 0.59, 0.47, 0.30, 0.46, 0.98, 0.50]

        return keyframes, durations
