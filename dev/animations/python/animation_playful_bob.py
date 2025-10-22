#!/usr/bin/env python3
"""
Bouncy dance-like movements with hip sways and shoulder rolls

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T21:48:14.674939
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class PlayfulBobAnimation(AnimationPlugin):
    """Bouncy dance-like movements with hip sways and shoulder rolls"""

    @property
    def name(self) -> str:
        return "playful_bob"

    @property
    def description(self) -> str:
        return "Bouncy dance-like movements with hip sways and shoulder rolls"

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
            [0.00, -0.65, 1.20, 1.00, -1.50, 14.0, 1.60],
            [0.00, -0.60, 1.55, 0.95, -1.20, 18.0, 1.40],
            [0.05, -0.55, 1.60, 0.90, -1.90, 20.0, 1.50],
            [-0.07, -0.75, 0.93, 1.58, -0.80, 22.5, 1.60],
            [0.12, -0.75, 0.88, 1.58, -2.20, 22.0, 1.40],
            [0.00, -0.45, 1.45, 0.85, -0.85, 16.0, 1.94],
            [-0.45, -0.85, 1.15, 1.55, -1.80, 17.5, 1.60],
            [-0.40, -0.90, 1.10, 1.50, -0.90, 18.5, 1.40],
            [0.45, -0.85, 1.15, 1.55, -2.00, 17.0, 1.50],
            [0.00, -0.65, 1.35, 1.10, -0.75, 19.0, 1.60],
            [0.10, -1.00, 1.00, 1.60, -1.70, 21.0, 1.40],
            [-0.10, -0.70, 1.30, 1.20, -1.00, 20.5, 1.50],
            [0.25, -0.82, 1.18, 1.42, -1.90, 18.0, 1.60],
            [-0.25, -0.85, 1.20, 1.45, -0.85, 17.5, 1.40],
            [0.00, -0.90, 1.25, 1.38, -1.60, 13.0, 1.50],
            [0.00, -0.65, 1.20, 1.00, -1.50, 14.0, 1.60],
        ]

        durations = [0.30, 0.30, 0.84, 0.67, 1.40, 0.98, 0.30, 0.55, 0.90, 0.80, 1.05, 0.46, 0.39, 0.81, 0.89, 0.50]

        return keyframes, durations
