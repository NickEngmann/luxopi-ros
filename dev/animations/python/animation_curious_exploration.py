#!/usr/bin/env python3
"""
Lively exploration with squints, double-takes, and 'aha' moments

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T21:55:26.536395
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class CuriousExplorationAnimation(AnimationPlugin):
    """Lively exploration with squints, double-takes, and 'aha' moments"""

    @property
    def name(self) -> str:
        return "curious_exploration"

    @property
    def description(self) -> str:
        return "Lively exploration with squints, double-takes, and 'aha' moments"

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
            [-0.09, -0.65, 1.20, 1.00, -1.50, 1.0, 1.60],
            [-0.19, -0.65, 1.15, 1.30, -1.20, 1.0, 1.40],
            [-0.64, -0.55, 1.05, 1.20, -1.90, 1.0, 1.50],
            [-0.59, -0.60, 1.10, 1.25, -0.85, 1.0, 1.60],
            [-0.54, -0.45, 0.90, 1.05, -2.00, 1.0, 1.83],
            [-0.51, -0.40, 0.85, 1.00, -0.80, 1.0, 1.92],
            [-0.57, -0.42, 0.87, 1.08, -1.80, 1.0, 2.03],
            [-0.52, -0.20, 0.79, 0.92, -0.90, 1.0, 1.76],
            [-0.44, -0.30, 0.70, 0.95, -2.10, 1.0, 1.89],
            [-0.29, -0.65, 1.15, 1.40, -0.75, 1.0, 1.60],
            [-0.09, -0.95, 0.85, 1.65, -1.70, 1.0, 1.40],
            [0.56, -0.50, 1.05, 1.35, -0.85, 1.0, 1.50],
            [0.11, -0.60, 1.12, 1.30, -1.90, 1.0, 1.60],
            [-0.09, -0.75, 1.23, 1.37, -1.10, 1.0, 1.40],
            [-0.09, -0.82, 1.28, 1.39, -1.60, 1.0, 1.50],
            [-0.09, -0.65, 1.20, 1.00, -1.50, 1.0, 1.60],
        ]

        durations = [0.62, 0.82, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.70, 0.67, 0.90, 0.39, 0.30, 0.37, 0.62, 0.50]

        return keyframes, durations
