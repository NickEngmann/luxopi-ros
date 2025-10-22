#!/usr/bin/env python3
"""
Enthusiastic tail wagging with full body involvement

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T21:46:39.427938
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class TailWagAnimation(AnimationPlugin):
    """Enthusiastic tail wagging with full body involvement"""

    @property
    def name(self) -> str:
        return "tail_wag"

    @property
    def description(self) -> str:
        return "Enthusiastic tail wagging with full body involvement"

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
            [0.00, -0.65, 1.20, 1.00, -1.50, 0.0, 1.60],
            [0.00, -0.70, 1.15, 1.05, -1.30, 0.0, 1.40],
            [0.40, -0.60, 1.10, 0.95, -2.00, 0.0, 1.50],
            [-0.40, -0.60, 1.10, 0.95, -1.00, 0.0, 1.60],
            [0.50, -0.55, 1.05, 0.90, -2.20, 0.0, 1.40],
            [-0.50, -0.55, 1.05, 0.90, -0.80, 0.0, 1.50],
            [0.30, -0.62, 1.12, 0.98, -1.80, 0.0, 1.60],
            [-0.30, -0.62, 1.12, 0.98, -1.20, 0.0, 1.40],
            [0.10, -0.68, 1.18, 1.08, -1.90, 0.0, 1.50],
            [0.00, -0.50, 1.00, 0.80, -1.50, 0.0, 1.60],
            [-0.20, -0.70, 1.20, 1.10, -1.60, 0.0, 1.40],
            [0.00, -0.75, 1.25, 1.15, -1.50, 0.0, 1.50],
            [0.00, -0.65, 1.20, 1.00, -1.50, 0.0, 1.60],
        ]

        durations = [0.52, 0.72, 0.50, 0.62, 0.60, 0.56, 0.30, 0.86, 0.37, 1.40, 0.30, 0.45, 0.50]

        return keyframes, durations
