#!/usr/bin/env python3
"""
Idle animation plugins for the LuxoPi system.
Enhanced with highly expressive, human-like movements that make the robot appear sentient.
"""

import random
import math
from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class GentleSwayAnimation(AnimationPlugin):
    """Natural human-like swaying with subtle breathing and micro-adjustments"""

    @property
    def name(self) -> str:
        return "gentle_sway"

    @property
    def description(self) -> str:
        return "Natural human-like swaying with subtle breathing and micro-adjustments"

    def get_category(self) -> str:
        return "idle"

    def get_keyframe_names(self) -> Optional[List[str]]:
        """Descriptive names for each keyframe."""
        return [
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12", "Keyframe 13", "Keyframe 14", "Keyframe 15",
            "Keyframe 16", "Keyframe 17"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        keyframes = [
            [0.00, -0.65, 1.20, 1.00, -1.50, 1.0, 1.60],
            [0.00, -0.88, 1.32, 1.42, -1.60, 1.0, 1.40],
            [0.09, -0.78, 1.25, 1.38, -1.20, 1.0, 1.50],
            [0.24, -0.70, 1.18, 1.45, -1.80, 1.0, 1.60],
            [0.27, -0.56, 1.16, 1.47, -0.90, 1.0, 1.40],
            [0.51, -0.60, 1.08, 1.52, -2.10, 1.0, 1.50],
            [0.60, -0.70, 1.05, 1.54, -0.80, 1.0, 1.60],
            [0.42, -0.65, 1.12, 1.45, -1.90, 1.0, 1.40],
            [0.12, -0.72, 1.20, 1.38, -1.10, 1.0, 1.50],
            [-0.09, -0.76, 1.22, 1.36, -2.00, 1.0, 1.60],
            [-0.30, -0.73, 1.18, 1.40, -0.85, 1.0, 1.40],
            [-0.54, -0.62, 1.10, 1.48, -1.70, 1.0, 1.50],
            [-0.60, -0.54, 1.08, 1.46, -0.90, 1.0, 1.60],
            [-0.24, -0.74, 1.20, 1.40, -1.60, 1.0, 1.40],
            [-0.05, -0.80, 1.26, 1.41, -1.30, 1.0, 1.50],
            [0.00, -0.80, 1.29, 1.40, -1.50, 1.0, 1.60],
            [0.00, -0.65, 1.20, 1.00, -1.50, 1.0, 1.40],
        ]

        durations = [0.39, 0.55, 0.58, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.34, 0.67, 0.30, 0.30, 0.32, 0.50]

        return keyframes, durations


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
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12", "Keyframe 13", "Keyframe 14", "Keyframe 15",
            "Keyframe 16"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
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


class BreathingAnimation(AnimationPlugin):
    """Deep yogic breathing with chest expansion and micro-movements"""

    @property
    def name(self) -> str:
        return "breathing"

    @property
    def description(self) -> str:
        return "Deep yogic breathing with chest expansion and micro-movements"

    def get_category(self) -> str:
        return "idle"

    def get_keyframe_names(self) -> Optional[List[str]]:
        """Descriptive names for each keyframe."""
        return [
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12", "Keyframe 13", "Keyframe 14", "Keyframe 15"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0

        keyframes = [
            [base_pos +0.05, -0.65, 1.20, 1.00, -1.50, 1.0, 1.60],
            [base_pos -0.03, -0.88, 1.32, 1.43, -1.30, 1.0, 1.40],
            [base_pos +0.04, -0.95, 1.34, 1.50, -1.80, 1.0, 1.50],
            [base_pos +0.05, -1.05, 1.38, 1.60, -0.90, 1.0, 1.60],
            [base_pos -0.05, -1.10, 1.42, 1.68, -2.00, 1.0, 1.40],
            [base_pos +0.02, -1.08, 1.41, 1.66, -0.80, 1.0, 1.50],
            [base_pos +0.06, -1.06, 1.40, 1.64, -1.70, 1.0, 1.60],
            [base_pos -0.03, -1.00, 1.36, 1.55, -1.10, 1.0, 1.40],
            [base_pos, -0.85, 1.30, 1.45, -1.90, 1.0, 1.50],
            [base_pos +0.05, -0.65, 1.20, 1.25, -0.85, 1.0, 1.60],
            [base_pos -0.03, -0.62, 1.18, 1.22, -2.20, 1.0, 1.40],
            [base_pos +0.02, -0.72, 1.24, 1.32, -0.75, 1.0, 1.50],
            [base_pos +0.05, -0.80, 1.28, 1.38, -1.60, 1.0, 1.60],
            [base_pos -0.03, -0.84, 1.20, 1.39, -1.30, 1.0, 1.40],
            [base_pos +0.02, -0.65, 1.20, 1.00, -1.50, 1.0, 1.50],
        ]

        durations = [0.69, 0.30, 0.30, 0.30, 0.58, 0.58, 0.30, 0.56, 0.30, 0.44, 0.30, 0.30, 0.30, 0.30, 0.50]

        return keyframes, durations


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
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12", "Keyframe 13", "Keyframe 14", "Keyframe 15",
            "Keyframe 16"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
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
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12", "Keyframe 13", "Keyframe 14", "Keyframe 15",
            "Keyframe 16"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
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


class ScanningWatchAnimation(AnimationPlugin):
    """Alert scanning with quick focus changes and threat assessment behaviors."""
    
    @property
    def name(self) -> str:
        return "scanning_watch"
    
    @property
    def description(self) -> str:
        return "Vigilant scanning with snap-focus and evaluation pauses"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Alert rise", "Snap left", "Quick eval", "Scan sweep",
                "Pause suspicious", "Continue scan", "Snap right", "Lock target",
                "Zoom focus", "Threat assess", "Relax false alarm", "Final check",
                "All clear", "Return rest", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        alert_height = -0.6
        
        keyframes = [
            [0.0, -0.65, 1.2, 1.0, -1.5, 13.0, 1.50],                          # Home 2
            [0.0, alert_height, 1.0, 1.3, -1.2, 16.0, 2.30],                   # Rise to alert
            [-0.75, alert_height - 0.05, 0.95, 1.2, -1.9, 21.0, 1.40],        # Snap look left
            [-0.7, alert_height, 1.0, 1.25, -0.85, 17.0, 1.50],                 # Quick evaluation
            [-0.35, alert_height + 0.05, 1.05, 1.3, -1.7, 15.0, 1.50],         # Scanning across
            [0.0, alert_height - 0.1, 0.95, 1.35, -1.0, 14.0, 1.50],          # Pause - something?
            [0.35, alert_height, 1.02, 1.38, -1.8, 15.5, 1.50],                # Continue scanning
            [0.8, alert_height - 0.05, 0.95, 1.42, -0.8, 20.5, 1.60],         # Snap look right
            [0.75, alert_height - 0.15, 0.9, 1.38, -2.0, 18.0, 1.50],         # Lock on target
            [0.72, alert_height - 0.2, 0.85, 1.35, -0.9, 16.5, 1.50],         # Zoom in focus
            [0.7, alert_height - 0.18, 0.87, 1.37, -1.8, 14.5, 1.50],         # Assess threat level
            [0.4, alert_height + 0.1, 1.1, 1.4, -1.1, 12.5, 0.90],            # Relax - false alarm
            [-0.3, alert_height, 1.05, 1.35, -1.7, 15.0, 1.50],               # One final check
            [0.0, -0.7, 1.15, 1.38, -1.3, 13.5, 0.70],                        # All clear, lowering
            [0.0, -0.82, 1.2, 1.39, -1.6, 12.0, 0.90],                        # Return to rest
            [0.0, -0.65, 1.2, 1.0, -1.5, 13.0, 1.50]                          # Home 2
        ]
        
        # Quick, alert scanning
        durations = [0.4, 0.45, 0.6, 0.4, 0.55, 0.55, 0.45, 0.6, 0.4, 0.45, 0.55, 0.6, 0.6, 0.55, 0.6, 0.6]
        
        return keyframes, durations


class SettlingAdjustAnimation(AnimationPlugin):
    """Fidgety comfort-seeking with multiple attempts to find the right position."""
    
    @property
    def name(self) -> str:
        return "settling_adjust"
    
    @property
    def description(self) -> str:
        return "Restless fidgeting with shoulder rolls and position testing"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Uncomfortable shift", "Shoulder roll left", "Test position",
                "Nope adjust", "Shoulder roll right", "Lean test", "Still not right",
                "Big readjust", "Getting closer", "Tiny tweak 1", "Tiny tweak 2",
                "Almost there", "One more shift", "Ahh perfect", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_adj = random.uniform(-0.4, 0.4)
        shoulder_var = random.uniform(-0.25, 0.25)
        
        keyframes = [
            [0.0, -0.65, 1.2, 1.0, -1.5, 12.0, 1.50],                                   # Starting position
            [base_adj * 0.3, -0.78, 1.35, 1.35, -1.3, 15.0, 1.50],                      # Uncomfortable
            [base_adj * 0.5 - 0.2, -0.95 + shoulder_var, 1.2, 1.5, -1.8, 14.5, 1.40],   # Roll shoulder left
            [base_adj * 0.4, -0.82, 1.32, 1.38, -0.9, 16.0, 1.50],                      # Test this spot
            [base_adj * 0.6, -0.85 + shoulder_var*0.5, 1.28, 1.42, -2.0, 15.5, 1.50],   # Nope, adjust more
            [base_adj * 0.5 + 0.2, -0.95 - shoulder_var, 1.2, 1.5, -0.8, 14.0, 1.60],   # Roll shoulder right
            [-base_adj * 0.3, -0.75, 1.35, 1.35, -1.7, 16.5, 1.50],                     # Try leaning
            [-base_adj * 0.5, -0.88, 1.27, 1.43, -1.1, 15.0, 1.50],                     # Still not comfortable
            [base_adj * 0.7, -0.6, 1.4, 1.2, -1.9, 17.0, 1.50],                         # Big position change
            [base_adj * 0.3, -0.8, 1.3, 1.4, -0.85, 13.5, 1.50],                         # This is better
            [base_adj * 0.15, -0.82, 1.31, 1.39, -1.6, 12.5, 1.50],                     # Tiny adjustment
            [base_adj * 0.1, -0.83, 1.3, 1.4, -1.2, 11.5, 1.50],                        # Another tiny one
            [0.05, -0.84, 1.3, 1.4, -1.7, 11.0, 1.50],                                  # Almost perfect
            [0.0, -0.845, 1.3, 1.4, -1.3, 10.5, 1.50],                                  # One final shift
            [0.0, -0.85, 1.1, 1.4, -1.6, 10.0, 1.50],                                   # Ahh, comfortable
            [0.0, -0.65, 1.2, 1.0, -1.5, 12.0, 1.50]                                    # Home 2
        ]
        
        # Fidgety but faster
        durations = [0.6, 0.55, 0.55, 0.45, 0.55, 0.55, 0.45, 0.55, 0.45, 0.55, 0.6, 0.7, 0.7, 0.8, 0.95, 0.6]
        
        return keyframes, durations


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
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12", "Keyframe 13", "Keyframe 14", "Keyframe 15",
            "Keyframe 16", "Keyframe 17", "Keyframe 18", "Keyframe 19"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
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


class NeckStretchAnimation(AnimationPlugin):
    """Neck stretching and rotation movements for relief and flexibility."""
    
    @property
    def name(self) -> str:
        return "neck_stretch"
    
    @property
    def description(self) -> str:
        return "Neck rolls and stretches like relieving tension"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Prepare stretch", "Tilt head left", "Deep stretch left",
                "Roll back", "Tilt head right", "Deep stretch right", "Roll forward",
                "Chin to chest", "Look up stretch", "Center crack", "Relief shake",
                "Final adjust", "Relaxed", "Home 2"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.50],                    # Home 2
            [base_pos, -0.8, 1.25, 1.35, -1.3, 11.0, 1.50],                   # Prepare for stretch
            [base_pos - 0.4, -0.75, 1.2, 1.3, -1.9, 10.5, 1.40],              # Tilt head left
            [base_pos - 0.6, -0.7, 1.15, 1.25, -0.8, 10.0, 1.40],             # Deep stretch left side
            [base_pos - 0.3, -0.9, 1.1, 1.5, -2.2, 10.5, 1.50],               # Roll head back
            [base_pos + 0.4, -0.75, 1.2, 1.3, -0.75, 10.5, 1.60],              # Tilt head right
            [base_pos + 0.6, -0.7, 1.15, 1.25, -1.8, 10.0, 1.60],             # Deep stretch right
            [base_pos + 0.3, -0.5, 1.35, 1.05, -1.0, 11.0, 1.50],             # Roll head forward
            [base_pos, -0.4, 1.45, 0.95, -2.0, 10.5, 1.50],                   # Chin to chest stretch
            [base_pos, -1.05, 0.9, 1.7, -0.85, 10.0, 2.40],                    # Look way up, stretch throat
            [base_pos + 0.05, -0.85, 1.2, 1.4, -1.7, 16.0, 1.50],             # Quick center adjustment
            [base_pos - 0.05, -0.85, 1.25, 1.4, -1.2, 15.5, 1.30],            # Relief shake
            [base_pos, -0.83, 1.28, 1.39, -1.6, 12.5, 1.50],                  # Final position adjust
            [base_pos, -0.84, 1.2, 1.4, -1.4, 11.5, 0.90],                    # Relaxed after stretch
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.50]                     # Home 2
        ]
        
        # Stretches need time but not too slow
        durations = [0.6, 0.7, 0.8, 1.2, 0.8, 0.8, 1.2, 0.8, 0.8, 1.4, 0.4, 0.4, 0.6, 0.7, 0.6]
        
        return keyframes, durations


class SleepAnimation(AnimationPlugin):
    """Folded sleepy dog - folds into C-shape """
    
    @property
    def name(self) -> str:
        return "sleep"
    
    @property
    def description(self) -> str:
        return "Folded C-shape with neck movements like a sleepy dog"

    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Initial fold", "Deep C-curve", 
            "Content right", "Blissful left",
            "Happy center", "Happy center again"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -1.3, 1.4, 0.8, -2.2, 10.0, 1.50],        # Initial fold - starting to curve
            [base_pos, -1.6, 1.8, 1.2, -2.8, 8.0, 1.50],         # Deep C-curve - folded position
            [base_pos+0.4, -1.75, 1.95, 1.5, -2.5, 9.5, 1.60],   # Content right - deeper fold
            [base_pos-0.4, -1.8, 2.0, 1.6, -3.0, 8.0, 1.40],     # Blissful left - maximum fold
            [base_pos, -1.75, 1.95, 1.4, -2.7, 9.0, 2.60],       # Happy center - balanced
            [base_pos, -1.75, 1.95, 1.4, -2.7, 9.0, 2.60],       # Happy center again - balanced
        ]
        
        # Smooth neck movement durations
        durations = [0.85, 1.02, 0.68, 0.77, 0.9, 0.9]
        
        return keyframes, durations


class YawningStretchAnimation(AnimationPlugin):
    """Big yawning stretch with full body extension."""
    
    @property
    def name(self) -> str:
        return "yawning_stretch"
    
    @property
    def description(self) -> str:
        return "Tired yawning with arms stretching up and out"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Feel tired", "Yawn starting", "Mouth open wide",
                "Arms up stretch", "Full extension", "Peak stretch hold",
                "Shudder release", "Arms lowering", "Yawn closing", 
                "Sleepy blink", "Shake it off", "Return normal", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.50],                    # Home 2
            [base_pos, -0.75, 1.35, 1.35, -1.3, 11.5, 0.60],                  # Feeling tired
            [base_pos, -0.9, 1.15, 1.5, -1.8, 10.5, 1.50],                    # Yawn beginning
            [base_pos - 0.1, -1.0, 1.0, 1.65, -0.8, 10.0, 1.50],              # Mouth opening wide
            [base_pos, -1.05, 0.8, 1.8, -2.1, 10.0, 2.40],                    # Arms stretching up
            [base_pos + 0.1, -1.1, 0.6, 1.95, -0.75, 10.0, 1.50],             # Full body extension (at limit)
            [base_pos, -1.08, 0.62, 1.93, -1.9, 10.0, 2.60],                  # Hold at peak
            [base_pos - 0.05, -1.05, 0.7, 1.85, -0.85, 14.0, 1.50],           # Shudder during release
            [base_pos, -1.0, 0.95, 1.6, -1.7, 11.0, 0.70],                    # Arms coming down
            [base_pos, -0.8, 1.2, 1.4, -1.1, 12.0, 1.50],                     # Yawn closing
            [base_pos, -0.78, 1.25, 1.38, -1.8, 13.0, 0.60],                  # Sleepy blink
            [base_pos + 0.15, -0.82, 1.27, 1.4, -1.0, 15.5, 1.30],            # Shake head to wake
            [base_pos, -0.84, 1.2, 1.4, -1.6, 12.5, 1.50],                    # Back to normal
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.50]                     # Home 2
        ]
        
        # Yawn timing with good hold
        durations = [0.6, 0.7, 0.8, 0.95, 0.95, 0.95, 1.6, 0.55, 0.8, 0.6, 0.6, 0.45, 0.6, 0.6]
        
        return keyframes, durations


class ShoulderShimmy(AnimationPlugin):
    """Playful shoulder shimmy dance move."""
    
    @property
    def name(self) -> str:
        return "shoulder_shimmy"
    
    @property
    def description(self) -> str:
        return "Fun shoulder shimmy with alternating movements"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Prep stance", "Right shoulder up", "Left shoulder up",
                "Quick right", "Quick left", "Double shimmy 1", "Double shimmy 2",
                "Big shimmy right", "Big shimmy left", "Shimmy center",
                "Final shake", "Cool down", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 14.0, 1.50],                    # Home 2
            [base_pos, -0.75, 1.2, 1.35, -1.3, 16.0, 1.50],                   # Get ready
            [base_pos + 0.2, -0.85, 1.15, 1.45, -1.8, 18.0, 1.60],            # Right shoulder up
            [base_pos - 0.2, -0.85, 1.15, 1.45, -0.9, 18.5, 1.40],            # Left shoulder up
            [base_pos + 0.15, -0.8, 1.18, 1.42, -2.0, 19.0, 1.60],            # Quick right
            [base_pos - 0.15, -0.8, 1.18, 1.42, -0.8, 19.5, 1.40],            # Quick left
            [base_pos + 0.25, -0.78, 1.22, 1.38, -1.8, 20.0, 1.50],           # Double shimmy
            [base_pos - 0.25, -0.78, 1.22, 1.38, -1.0, 20.5, 1.50],           # Other side
            [base_pos + 0.35, -0.7, 1.25, 1.35, -2.1, 21.0, 1.60],            # Big shimmy right
            [base_pos - 0.35, -0.7, 1.25, 1.35, -0.75, 21.5, 1.40],           # Big shimmy left
            [base_pos, -0.75, 1.2, 1.4, -1.7, 17.0, 1.50],                    # Back to center
            [base_pos + 0.1, -0.8, 1.25, 1.38, -1.2, 16.0, 1.30],             # Final little shake
            [base_pos, -0.83, 1.28, 1.39, -1.6, 13.0, 0.70],                  # Cool down
            [base_pos, -0.65, 1.2, 1.0, -1.5, 14.0, 1.50]                     # Home 2
        ]
        
        # Quick shimmy timing
        durations = [0.45, 0.4, 0.4, 0.4, 0.35, 0.4, 0.4, 0.4, 0.45, 0.5, 0.4, 0.35, 0.55, 0.45]
        
        return keyframes, durations


class LookAroundCasual(AnimationPlugin):
    """Casual looking around as if checking surroundings."""
    
    @property
    def name(self) -> str:
        return "look_around_casual"
    
    @property
    def description(self) -> str:
        return "Casual glances around the environment"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Slight lift", "Glance left", "Notice something",
                "Look back center", "Glance right casual", "Up and right",
                "Check behind right", "Return center", "Quick left check",
                "All good", "Settle", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 13.0, 1.50],                    # Home 2
            [base_pos, -0.78, 1.25, 1.38, -1.3, 14.0, 1.50],                  # Slight head lift
            [base_pos - 0.4, -0.75, 1.22, 1.35, -1.8, 15.0, 1.40],            # Casual glance left
            [base_pos - 0.35, -0.72, 1.2, 1.32, -0.9, 14.5, 1.50],            # Hmm, what's that?
            [base_pos, -0.77, 1.23, 1.37, -1.7, 13.5, 1.50],                  # Look back to center
            [base_pos + 0.3, -0.75, 1.22, 1.4, -1.1, 15.5, 1.60],             # Glance right
            [base_pos + 0.35, -0.85, 1.15, 1.5, -2.0, 14.0, 1.60],            # Look up and right
            [base_pos + 0.5, -0.8, 1.2, 1.45, -0.8, 13.0, 1.50],              # Check behind
            [base_pos, -0.78, 1.24, 1.38, -1.8, 13.5, 1.50],                  # Back to center
            [base_pos - 0.25, -0.76, 1.23, 1.36, -1.0, 16.0, 1.40],           # Quick left check
            [base_pos, -0.8, 1.26, 1.38, -1.6, 12.5, 1.50],                   # All good
            [base_pos, -0.84, 1.29, 1.39, -1.4, 11.5, 1.50],                  # Settling back
            [base_pos, -0.65, 1.2, 1.0, -1.5, 13.0, 1.50]                     # Home 2
        ]
        
        # Casual but not sluggish
        durations = [0.6, 0.55, 0.6, 0.55, 0.7, 0.55, 0.6, 0.8, 0.7, 0.55, 0.6, 0.7, 0.6]
        
        return keyframes, durations


# New animations added below

class ContentedSighAnimation(AnimationPlugin):
    """Deep satisfying sigh with shoulders dropping and body relaxing"""

    @property
    def name(self) -> str:
        return "contented_sigh"

    @property
    def description(self) -> str:
        return "Deep satisfying sigh with shoulders dropping and body relaxing"

    def get_category(self) -> str:
        return "idle"

    def get_keyframe_names(self) -> Optional[List[str]]:
        """Descriptive names for each keyframe."""
        return [
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12", "Keyframe 13", "Keyframe 14", "Keyframe 15"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0

        keyframes = [
            [base_pos +0.05, -0.65, 1.20, 1.00, -1.50, 4.4, 1.60],
            [base_pos -0.03, -0.80, 1.25, 1.35, -1.30, 2.4, 1.40],
            [base_pos +0.02, -1.00, 1.10, 1.60, -1.80, 3.1, 1.50],
            [base_pos +0.05, -1.05, 1.08, 1.62, -1.00, 3.5, 1.60],
            [base_pos -0.03, -0.90, 1.20, 1.50, -1.90, 4.8, 1.40],
            [base_pos +0.02, -0.60, 1.40, 1.20, -1.20, 1.2, 1.50],
            [base_pos +0.05, -0.40, 1.50, 1.00, -1.70, 4.4, 2.02],
            [base_pos -0.03, -0.30, 1.60, 0.80, -1.50, 5.0, 1.79],
            [base_pos +0.02, -0.50, 1.50, 0.90, -1.60, 2.7, 1.50],
            [base_pos +0.05, -0.75, 1.30, 1.10, -1.50, 1.5, 1.60],
            [base_pos -0.03, -0.65, 1.20, 1.00, -1.50, 2.6, 1.40],
            [base_pos, -0.63, 2.05, 1.05, -1.50, 4.6, 1.50],
            [base_pos +0.04, -0.01, 1.57, 1.00, -1.50, 4.3, 1.90],
            [base_pos -0.04, 0.23, 1.58, 0.98, -1.50, 10.0, 1.77],
            [base_pos +0.01, 0.51, 1.54, 0.79, -1.50, 10.0, 1.95],
        ]

        durations = [0.30, 0.30, 0.60, 0.75, 0.40, 0.30, 0.50, 0.30, 0.62, 0.30, 0.48, 0.59, 0.30, 1.30, 2.50]

        return keyframes, durations


class HeadBobbingAnimation(AnimationPlugin):
    """Rhythmic head bobbing to an internal beat"""

    @property
    def name(self) -> str:
        return "head_bobbing"

    @property
    def description(self) -> str:
        return "Rhythmic head bobbing to an internal beat"

    def get_category(self) -> str:
        return "idle"

    def get_keyframe_names(self) -> Optional[List[str]]:
        """Descriptive names for each keyframe."""
        return [
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0

        keyframes = [
            [base_pos, -0.65, 1.20, 1.00, -1.50, 4.9, 1.60],
            [base_pos, -0.65, 1.25, 0.85, -1.30, 4.5, 1.40],
            [base_pos, -0.80, 1.15, 1.15, -1.70, 4.0, 1.50],
            [base_pos, -0.68, 1.22, 0.90, -1.40, 2.5, 1.60],
            [base_pos, -0.78, 1.18, 1.10, -1.60, 3.3, 1.40],
            [base_pos, -0.60, 1.30, 0.80, -1.20, 3.9, 1.50],
            [base_pos, -0.85, 1.10, 1.20, -1.80, 4.2, 1.60],
            [base_pos -0.20, -0.70, 1.20, 0.95, -1.00, 1.3, 1.40],
            [base_pos +0.20, -0.70, 1.20, 0.95, -2.00, 1.7, 1.50],
            [base_pos, -0.65, 1.25, 0.85, -1.50, 3.6, 1.60],
            [base_pos, -0.80, 1.20, 1.05, -1.50, 2.8, 1.40],
            [base_pos, -0.65, 1.20, 1.00, -1.50, 1.1, 1.50],
        ]

        durations = [0.50, 1.12, 0.67, 0.30, 0.70, 1.27, 0.85, 0.30, 0.30, 0.60, 0.50, 0.50]

        return keyframes, durations


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
            "Keyframe 1", "Keyframe 2", "Keyframe 3", "Keyframe 4", "Keyframe 5",
            "Keyframe 6", "Keyframe 7", "Keyframe 8", "Keyframe 9", "Keyframe 10",
            "Keyframe 11", "Keyframe 12", "Keyframe 13"
        ]

    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
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


class PonderingAnimation(AnimationPlugin):
    """Deep pondering with chin stroking gestures."""
    
    @property
    def name(self) -> str:
        return "pondering"
    
    @property
    def description(self) -> str:
        return "Thoughtful pondering with metaphorical chin stroking"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Initial thought", "Chin stroke position", "Deep ponder",
                "Look up thinking", "Side glance", "Hmm moment", "Another angle",
                "Processing", "Slight nod", "Final think", "Resolution", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.50],                    # Home 2
            [base_pos, -0.75, 1.15, 1.2, -1.3, 13.0, 1.50],                   # Initial thought
            [base_pos, -0.5, 0.9, 0.8, -1.7, 11.0, 1.50],                     # Chin stroke position - back
            [base_pos - 0.1, -0.45, 0.85, 0.75, -1.0, 10.0, 1.80],            # Deep ponder - back
            [base_pos, -1.0, 0.8, 1.5, -1.8, 11.0, 1.80],                     # Look up thinking - far back
            [base_pos + 0.3, -0.7, 1.0, 1.1, -0.9, 12.0, 1.50],               # Side glance - back
            [base_pos, -0.55, 0.95, 0.85, -2.0, 10.0, 1.50],                  # Hmm moment - back
            [base_pos - 0.25, -0.6, 1.0, 0.9, -1.2, 11.0, 1.50],              # Another angle - back
            [base_pos, -0.65, 1.05, 0.95, -1.6, 10.0, 1.50],                  # Processing - back
            [base_pos, -0.7, 1.1, 1.0, -1.4, 13.0, 1.50],                     # Slight understanding nod - back
            [base_pos, -0.8, 1.15, 1.15, -1.8, 12.0, 1.80],                   # Final think - back
            [base_pos, -0.85, 1.2, 1.2, -1.5, 14.0, 1.50],                    # Resolution - back
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.50]                     # Home 2
        ]
        
        # Thoughtful timing
        durations = [0.6, 0.7, 0.8, 0.95, 0.8, 0.7, 0.95, 0.8, 0.95, 0.6, 0.7, 0.55, 0.6]
        
        return keyframes, durations