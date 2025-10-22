#!/usr/bin/env python3
"""
Engaged listening with eyebrow raises, micro-nods, and 'mm-hmm' gestures

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T22:03:09.389803
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class AttentiveListeningAnimation(AnimationPlugin):
    """Engaged listening with eyebrow raises, micro-nods, and 'mm-hmm' gestures"""

    @property
    def name(self) -> str:
        return "attentive_listening"

    @property
    def description(self) -> str:
        return "Engaged listening with eyebrow raises, micro-nods, and 'mm-hmm' gestures"

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
            [0.00, -0.65, 1.20, 1.00, -1.50, 7.0, 1.60],
            [0.00, -0.70, 1.20, 1.35, -1.30, 11.5, 1.40],
            [0.00, -0.65, 1.15, 1.30, -1.80, 10.6, 1.50],
            [-0.15, -0.50, 1.00, 1.15, -0.90, 8.7, 1.60],
            [-0.12, -0.52, 1.02, 1.12, -2.00, 11.5, 1.40],
            [-0.35, -0.55, 1.05, 1.20, -0.80, 11.7, 1.50],
            [-0.32, -0.62, 1.12, 1.28, -1.90, 11.5, 1.60],
            [-0.30, -0.58, 1.08, 1.24, -1.00, 6.0, 1.40],
            [0.10, -0.60, 1.10, 1.30, -1.70, 10.2, 1.50],
            [0.38, -0.58, 1.08, 1.32, -0.85, 8.8, 1.60],
            [0.15, -0.48, 0.98, 1.18, -2.10, 9.5, 1.84],
            [0.00, -0.72, 1.22, 1.42, -0.75, 8.7, 1.50],
            [0.00, -0.68, 1.18, 1.38, -1.80, 10.7, 1.60],
            [0.00, -0.55, 1.05, 1.25, -1.20, 7.3, 1.40],
            [0.00, -0.78, 1.26, 1.38, -1.60, 11.0, 1.50],
            [0.00, -0.65, 1.20, 1.00, -1.50, 9.2, 1.60],
        ]

        durations = [0.60, 0.77, 0.85, 0.30, 0.43, 0.38, 0.30, 0.30, 0.30, 0.30, 0.58, 0.30, 0.30, 0.58, 0.58, 0.50]

        return keyframes, durations
