#!/usr/bin/env python3
"""
Animation created with recorder on 2025-10-23 20:22

Generated from JSON by json_to_animation.py
Original file: 2025-10-23T20:22:45.700207
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class CuriousAnimation(AnimationPlugin):
    """Animation created with recorder on 2025-10-23 20:22"""

    @property
    def name(self) -> str:
        return "curious"

    @property
    def description(self) -> str:
        return "Animation created with recorder on 2025-10-23 20:22"

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
            [base_pos +0.05, -1.53, 2.24, 0.90, -1.16, 12.7, 1.45],
            [base_pos -0.08, -1.58, 1.83, 0.70, -2.00, 12.7, 1.26],
            [base_pos +0.02, -1.53, 2.22, 0.91, -1.00, 12.6, 1.35],
            [base_pos, -1.59, 1.84, 0.75, -1.88, 11.2, 1.46],
            [base_pos -0.08, -0.19, 1.22, 0.42, -1.09, 13.3, 1.76],
            [base_pos -0.03, -0.56, 0.53, 0.15, -1.87, 11.6, 1.50],
            [base_pos +0.05, -1.62, 1.30, 1.46, -1.50, 11.0, 1.46],
        ]

        durations = [0.36, 0.35, 0.32, 1.18, 0.67, 1.59, 0.50]

        return keyframes, durations
