#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-21 21:03

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T21:06:27.687700
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class NodAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-21 21:03"""

    @property
    def name(self) -> str:
        return "nod"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-21 21:03"

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
            [base_pos, -0.54, 0.85, 1.09, -1.00, 89.3, 1.60],
            [base_pos -0.08, -0.54, 0.76, 0.66, -2.05, 50.6, 1.40],
            [base_pos -0.03, -0.54, 0.96, 1.68, -0.98, 115.3, 1.50],
            [base_pos, -0.54, 0.52, 0.59, -2.03, 139.1, 1.60],
            [base_pos -0.08, -0.52, 1.11, 1.58, -1.04, 43.9, 1.40],
            [base_pos -0.03, -0.47, 1.01, 0.87, -1.50, 36.8, 1.94],
        ]

        durations = [0.40, 0.69, 0.83, 0.94, 0.73, 0.50]

        return keyframes, durations
