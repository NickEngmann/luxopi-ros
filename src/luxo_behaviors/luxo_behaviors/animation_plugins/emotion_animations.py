#!/usr/bin/env python3
"""
Emotion-based animation plugins for the LuxoPi system.
These animations express various emotional states.
"""

import random
from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin




class BigBounceAnimation(AnimationPlugin):
    """A big, energetic bouncing animation with dramatic movements and personality."""

    @property
    def name(self) -> str:
        return "big_bounce"

    @property
    def description(self) -> str:
        return "Large energetic bounces with explosive movements and varying rhythms"

    def get_category(self) -> str:
        return "action"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Start position", "Compress left", "Launch up left", "Compress right",
            "Launch prep", "Extend high", "Bounce center", "Twist down",
            "Side bounce", "Up again", "Quick compress", "High bounce left",
            "Steady position", "Lower compress", "Explosive up", "Quick down",
            "Side launch", "Recovery left", "Up bounce", "Quick center",
            "Side swing", "Center bounce", "Twist up", "Quick launch",
            "Far left swing", "Balance right", "High center", "Settle down", "Return home"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        keyframes = [
            [-0.03, -0.87, 1.22, 0.99, -1.08, 225.9, 1.60],
            [-0.36, -1.35, 2.15, 0.99, -1.75, 146.7, 1.40],
            [0.42, -0.80, 0.83, 0.97, -0.96, 230.4, 1.50],
            [0.42, -1.63, 2.14, 1.02, -1.74, 158.8, 1.46],
            [0.00, -0.64, 0.32, 0.57, -1.08, 217.2, 1.40],
            [-0.21, -0.76, 2.19, 0.98, -1.82, 209.0, 1.50],
            [-0.82, -0.71, 0.94, 0.83, -0.90, 220.5, 1.60],
            [-0.80, -0.71, 0.68, 0.26, -2.02, 225.0, 1.40],
            [0.29, -0.89, 0.73, 0.07, -1.01, 144.8, 1.50],
            [0.29, -1.41, 2.11, 0.98, -2.12, 232.0, 1.60],
            [0.29, -0.73, 0.79, 0.14, -1.23, 204.5, 1.40],
            [0.02, -1.52, 1.93, 1.00, -1.96, 196.2, 1.35],
            [0.02, -1.51, 1.93, 0.98, -1.03, 151.8, 1.45],
            [0.02, -0.97, 0.92, 0.18, -1.89, 207.1, 1.40],
            [0.02, -1.52, 2.03, 0.87, -1.22, 241.6, 1.35],
            [0.02, -0.74, 0.71, 0.06, -1.96, 201.5, 1.60],
            [0.02, -1.64, 2.38, 0.61, -1.00, 222.2, 1.26],
            [-0.49, -0.80, 1.07, 0.35, -1.90, 165.8, 1.50],
            [-0.51, -1.37, 2.41, 0.61, -0.93, 199.6, 1.60],
            [-0.51, -0.69, 0.84, 0.06, -1.86, 206.6, 1.40],
            [-0.50, -1.12, 2.45, 0.33, -1.11, 148.9, 1.50],
            [-0.15, -0.78, 1.03, 0.14, -1.81, 210.7, 1.60],
            [0.13, -1.28, 2.39, 0.33, -0.99, 223.8, 1.40],
            [0.19, -0.78, 1.08, 0.15, -1.78, 243.8, 1.50],
            [0.47, -1.39, 2.41, 0.44, -0.94, 160.7, 1.60],
            [-1.30, -0.68, 0.91, -0.04, -1.91, 205.1, 1.40],
            [0.74, -0.65, 0.73, 0.23, -0.82, 191.8, 1.50],
            [0.12, -1.41, 2.22, 0.74, -1.85, 229.9, 1.60],
            [0.12, -0.89, 1.16, 1.36, -1.50, 180.8, 1.40],
        ]

        durations = [0.87, 1.34, 1.10, 1.84, 1.31, 1.03, 0.43, 0.75, 1.40, 1.42, 1.53, 0.30, 1.18, 1.18, 1.46, 1.56, 1.46, 1.10, 1.40, 1.16, 1.15, 1.17, 1.02, 1.25, 2.23, 1.25, 1.68, 1.10, 0.50]

        return keyframes, durations


class SmallBouncesAnimation(AnimationPlugin):
    """Rapid, small bounces with ultra-fast movements for playful energy."""

    @property
    def name(self) -> str:
        return "small_bounces"

    @property
    def description(self) -> str:
        return "Quick, continuous small bounces with maximum speed for playful expression"

    def get_category(self) -> str:
        return "action"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Start", "Bounce 1 up", "Bounce 1 down", "Bounce 2 up", "Bounce 2 center",
            "Bounce 3 up", "Bounce 3 down", "Bounce 4 up", "Bounce 4 left",
            "Bounce 5 up", "Bounce 5 side", "Bounce 6 up", "Bounce 6 shift",
            "Bounce 7 up", "Bounce 7 down", "Bounce 8 up", "Bounce 8 center",
            "Bounce 9 up", "Bounce 9 mid", "Bounce 10 up", "Bounce 10 center",
            "Bounce 11 up", "Bounce 11 right", "Bounce 12 up", "Bounce 12 final",
            "Return home"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        keyframes = [
            [0.10, -0.88, 1.08, 1.27, -1.12, 0.0, 1.60],
            [-0.08, -1.50, 1.69, 1.36, -1.81, 0.0, 1.40],
            [-0.29, -0.92, 1.01, 1.34, -1.09, 0.0, 1.50],
            [-0.30, -1.48, 1.78, 1.34, -1.92, 0.0, 1.60],
            [0.12, -1.00, 1.17, 1.28, -1.26, 0.0, 1.40],
            [0.11, -1.61, 1.76, 1.35, -2.01, 0.0, 1.36],
            [-0.24, -1.14, 1.11, 1.34, -1.02, 0.0, 1.60],
            [-0.25, -1.64, 1.78, 1.34, -2.07, 0.0, 1.26],
            [-0.67, -0.89, 1.02, 1.34, -1.00, 0.0, 1.50],
            [-0.67, -1.43, 1.85, 1.33, -1.91, 0.0, 1.60],
            [-0.56, -1.56, 0.78, 0.56, -1.01, 0.0, 1.26],
            [-0.49, -1.61, 1.80, 0.95, -1.92, 0.0, 1.36],
            [-0.49, -1.69, 0.87, 0.38, -1.18, 0.0, 1.47],
            [0.17, -1.56, 1.95, 1.05, -1.88, 0.0, 1.26],
            [-0.14, -1.65, 1.11, 0.44, -0.86, 0.0, 1.37],
            [0.38, -1.56, 2.01, 0.98, -2.04, 0.0, 1.46],
            [-0.22, -1.55, 1.22, 0.54, -0.87, 0.0, 1.25],
            [-0.28, -1.64, 1.94, 0.89, -2.13, 0.0, 1.36],
            [-0.28, -1.24, 1.33, 0.75, -1.18, 0.0, 1.60],
            [-0.28, -1.42, 2.11, 0.86, -1.91, 0.0, 1.40],
            [0.10, -1.23, 1.41, 0.60, -1.17, 0.0, 1.50],
            [0.19, -1.60, 2.15, 0.75, -2.09, 0.0, 1.46],
            [0.39, -1.28, 1.47, 0.65, -1.11, 0.0, 1.40],
            [0.36, -1.63, 2.01, 0.87, -2.10, 0.0, 1.36],
            [0.10, -1.29, 1.31, 0.82, -1.20, 0.0, 1.60],
            [0.10, -1.07, 1.17, 1.31, -1.50, 0.0, 1.40],
        ]

        durations = [0.75, 0.74, 0.67, 0.78, 0.63, 0.74, 0.59, 0.97, 0.68, 1.04, 0.77, 0.79, 1.27, 0.93, 1.03, 0.92, 0.61, 0.58, 0.54, 0.77, 0.67, 0.64, 0.57, 0.67, 0.43, 0.50]

        return keyframes, durations

class SadAnimation(AnimationPlugin):
    """A slow, expressive sad animation with organic, flowing movements."""

    @property
    def name(self) -> str:
        return "sad"

    @property
    def description(self) -> str:
        return "Melancholy animation with slow, heavy movements and emotional sighs"

    def get_category(self) -> str:
        return "emotion"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Start position", "Feel sadness", "Shoulders droop", "Look up slowly",
            "Peak sadness", "Turn left sadly", "Turn back center", "Look around lost",
            "Head hangs low", "Small sigh left", "Sigh down", "Another look up",
            "Small comfort", "Look around hopeful", "Gradual lift", "Almost better",
            "Return home"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        keyframes = [
            [0.13, -0.83, 1.19, 1.31, -1.21, 11.3, 1.60],
            [0.13, -0.56, 1.74, 1.31, -1.97, 7.1, 1.40],
            [0.15, -0.08, 2.18, 0.61, -1.05, 6.0, 1.82],
            [0.10, 0.21, 2.33, 0.42, -1.82, 11.4, 1.96],
            [-1.00, 0.21, 2.28, 0.44, -1.15, 9.0, 1.76],
            [0.22, 0.21, 2.21, 0.51, -1.89, 8.7, 1.86],
            [1.16, -0.35, 2.22, 0.92, -1.07, 5.7, 2.00],
            [1.11, -0.76, 1.41, 1.57, -2.13, 9.0, 1.40],
            [1.15, -0.93, 1.02, 0.38, -0.97, 5.2, 1.50],
            [0.30, -1.06, 1.09, -0.07, -1.78, 5.2, 1.60],
            [0.14, -1.11, 0.69, -0.07, -1.13, 9.4, 1.40],
            [0.19, -1.10, 1.31, 1.58, -1.89, 5.0, 1.50],
            [0.13, -0.94, 2.21, 0.92, -1.11, 9.3, 1.60],
            [0.10, 0.25, 2.07, 0.82, -1.89, 11.0, 1.77],
            [0.10, 0.50, 2.05, 0.66, -1.14, 9.1, 1.95],
            [0.10, -0.24, 1.61, 1.31, -1.80, 11.8, 1.97],
            [0.10, -0.73, 1.19, 1.31, -1.50, 10.8, 1.40],
        ]

        durations = [0.51, 1.03, 0.41, 0.69, 0.73, 1.04, 1.26, 0.94, 0.80, 0.41, 1.22, 0.94, 0.82, 0.30, 0.92, 0.74, 0.50]

        return keyframes, durations


class StartledJumpAnimation(AnimationPlugin):
    """Quick startled reaction with panic and recovery"""

    @property
    def name(self) -> str:
        return "startled"

    @property
    def description(self) -> str:
        return "Quick startled reaction with panic and recovery"

    def get_category(self) -> str:
        return "emotion"

    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12", "Keyframe 13", "Keyframe 14", "Keyframe 15",
            "Keyframe 16", "Keyframe 17", "Keyframe 18"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        keyframes = [
            [-0.03, -0.37, 0.79, 1.02, -1.50, 14.0, 2.01],
            [0.00, -0.25, 0.75, 0.45, -1.30, 15.0, 1.77],
            [0.00, -0.90, 1.40, 0.30, -1.90, 13.0, 1.50],
            [-0.40, -0.50, 0.20, 1.50, -0.80, 0.0, 1.60],
            [-0.50, -0.60, 0.10, 1.60, -2.10, 0.0, 1.40],
            [-0.60, -0.55, 0.15, 1.55, -0.75, 21.0, 1.50],
            [-0.40, -0.55, 0.15, 1.55, -2.20, 21.0, 1.60],
            [-0.30, -0.40, 0.60, 1.00, -1.00, 18.0, 1.82],
            [-0.22, -0.99, 0.91, 1.53, -1.80, 16.0, 1.50],
            [-0.49, -0.41, 0.98, 1.25, -1.20, 17.0, 2.02],
            [0.26, -0.40, 0.94, 1.08, -1.90, 17.0, 1.82],
            [-0.10, -0.30, 0.90, 0.60, -1.30, 15.0, 1.89],
            [0.00, -0.40, 1.00, 0.50, -1.70, 14.0, 2.02],
            [0.00, -0.50, 1.10, 0.40, -1.50, 13.0, 1.40],
            [0.10, -0.45, 1.05, 0.45, -1.60, 14.0, 1.94],
            [0.00, -0.40, 1.00, 0.50, -1.50, 13.0, 2.02],
            [0.00, 0.20, 1.30, 1.50, -1.50, 15.0, 1.76],
            [0.00, -0.65, 1.20, 1.00, -1.50, 10.0, 1.50],
        ]

        durations = [0.38, 1.12, 2.00, 0.30, 0.30, 0.30, 0.68, 0.76, 0.64, 0.55, 0.53, 0.60, 0.55, 0.30, 0.30, 0.95, 0.73, 0.50]

        return keyframes, durations