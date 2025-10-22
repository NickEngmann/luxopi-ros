#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-20 20:52

Generated from JSON by json_to_animation.py
Original file: 2025-10-21T19:57:30.449938
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class SimpleBowAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-20 20:52"""

    @property
    def name(self) -> str:
        return "simple_bow"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-20 20:52"

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
            [base_pos, -1.04, 1.40, 0.82, -1.26, 10.8, 1.60],
            [base_pos -0.08, -0.76, 0.60, 1.25, -1.80, 14.8, 1.40],
            [base_pos -0.03, -0.50, 0.47, 1.27, -1.12, 11.2, 1.50],
            [base_pos, -0.36, 2.27, 0.72, -2.00, 13.0, 2.01],
            [base_pos -0.08, 0.33, 2.28, 0.42, -1.06, 11.6, 1.80],
            [base_pos -0.03, -1.03, 1.14, 1.02, -1.50, 11.0, 1.50],
        ]

        durations = [0.90, 0.51, 1.29, 0.64, 1.73, 0.50]

        return keyframes, durations
