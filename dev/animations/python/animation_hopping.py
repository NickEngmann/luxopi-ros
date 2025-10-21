#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-20 20:50

Generated from JSON by json_to_animation.py
Original file: 2025-10-20T20:50:43.561422
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class HoppingAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-20 20:50"""

    @property
    def name(self) -> str:
        return "hopping"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-20 20:50"

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
        base_pos = 0.0
        
        keyframes = [
            [base_pos +0.05, -1.53, 2.34, 0.57, -1.50, 12.6, 1.45],
            [base_pos -0.03, -1.43, 1.84, 0.56, -1.50, 12.7, 1.40],
            [base_pos +0.02, -1.47, 2.43, 0.63, -1.50, 13.4, 1.50],
            [base_pos +0.05, -1.12, 1.44, 0.55, -1.50, 13.1, 1.60],
            [base_pos -0.03, -1.06, 1.93, 1.16, -1.50, 10.8, 1.40],
            [base_pos +0.02, -0.89, 1.09, 0.53, -1.50, 11.2, 1.50],
            [base_pos +0.04, -1.70, 2.44, 0.39, -1.50, 11.1, 1.47],
            [base_pos -0.03, -0.92, 1.08, 0.34, -1.50, 10.9, 1.40],
            [base_pos +0.02, -1.12, 2.35, 0.73, -1.50, 11.3, 1.50],
            [base_pos +0.05, -0.63, 0.68, 0.38, -1.50, 11.4, 1.60],
            [base_pos -0.03, -1.61, 2.22, 0.72, -1.50, 13.5, 1.26],
            [base_pos +0.01, -1.13, 1.39, 0.56, -1.50, 11.0, 1.50],
        ]

        durations = [0.31, 0.35, 0.71, 0.57, 0.82, 1.16, 1.10, 0.93, 1.25, 1.43, 0.74, 0.50]

        return keyframes, durations
