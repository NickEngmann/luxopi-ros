#!/usr/bin/env python3
"""
Emotion-based animation plugins for the LuxoPi system.
These animations express various emotional states.
"""

import random
from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


# COMMENTED OUT: This animation stretches forward and breaks things
# class ExcitedHopAnimation(AnimationPlugin):
#     """An excited bouncy hop animation with Disney-style principles."""
#
#     @property
#     def name(self) -> str:
#         return "excited"
#
#     @property
#     def description(self) -> str:
#         return "Energetic bouncing hop expressing excitement"
#
#     def get_category(self) -> str:
#         return "emotion"
#
#     def get_keyframe_names(self) -> Optional[List[str]]:
#         return [
#             "Initial wiggle", "Opposite wiggle", "Crouch prep", "Compress",
#             "Spring load", "Launch up", "Air wiggle", "Peak joy",
#             "Descent begin", "Impact prep", "Land compress", "Bounce back",
#             "Secondary hop", "Mini bounce", "Victory wiggle", "Settle down",
#             "Return home 1", "Return home 2"
#         ]
#
#     def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
#         base_pos = 0.0
#
#         keyframes = [
#             [base_pos+0.15, -0.1, 0.7, 0.5, -1.3, 17.0, 2.10],   # Initial wiggle - back
#             [base_pos-0.15, -0.15, 0.65, 0.55, -1.7, 18.0, 2.10], # Opposite wiggle - back
#             [base_pos, 0.2, 1.2, 0.3, -1.5, 16.0, 1.50],         # Crouch prep - forward OK
#             [base_pos, 0.3, 1.4, 0.1, -1.2, 15.0, 0.70],         # Compress - forward OK
#             [base_pos, -0.9, 1.6, 0.5, -1.8, 13.0, 1.50],        # Spring load - far back
#             [base_pos, -0.6, 0.4, 1.2, -0.9, 22.0, 2.40],        # Launch up - back
#             [base_pos+0.2, -0.7, 0.3, 1.3, -2.0, 21.0, 2.10],    # Air wiggle - back
#             [base_pos-0.1, -0.8, 0.2, 1.4, -0.8, 20.0, 2.60],    # Peak joy - back
#             [base_pos, -0.5, 0.5, 1.1, -1.6, 18.0, 1.50],        # Descent begin - back
#             [base_pos, -0.2, 0.8, 0.8, -1.2, 17.0, 1.50],        # Impact prep - back
#             [base_pos, 0.25, 1.5, 0.2, -1.8, 14.0, 0.70],        # Land compress - forward OK
#             [base_pos, -0.3, 0.9, 0.9, -1.0, 19.0, 2.10],        # Bounce back - back
#             [base_pos+0.1, -0.5, 0.6, 1.1, -1.7, 20.0, 1.50],    # Secondary hop - back
#             [base_pos, -0.1, 1.0, 0.6, -1.3, 16.0, 2.10],        # Mini bounce - back
#             [base_pos-0.2, -0.4, 0.8, 0.8, -1.9, 18.0, 2.10],    # Victory wiggle - back
#             [base_pos, -0.2, 0.9, 0.7, -1.5, 15.0, 0.90],        # Settle down - back
#             [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0, 1.50],         # Return home 1
#             [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0, 1.50]        # Return home 2
#         ]
#
#         # Fast exciting hops
#         durations = [0.4, 0.45, 0.55, 0.6, 0.85, 0.6, 0.35, 0.35, 0.45, 0.55, 0.75, 0.6, 0.45, 0.55, 0.45, 0.6, 0.6, 0.9]
#
#         return keyframes, durations


# COMMENTED OUT: This animation stretches forward and breaks things
# class SadDroopAnimation(AnimationPlugin):
#     """A sad drooping animation with heavy, slow movements."""
#
#     @property
#     def name(self) -> str:
#         return "sad"
#
#     @property
#     def description(self) -> str:
#         return "Slow, heavy drooping motion expressing sadness"
#
#     def get_category(self) -> str:
#         return "emotion"
#
#     def get_keyframe_names(self) -> Optional[List[str]]:
#         return [
#             "Normal state", "Feel sadness", "Begin droop", "Weight increases",
#             "Shoulders sag", "Head drops", "Deep sadness", "Hold sadness",
#             "Small sigh", "Another sigh", "Begin recovery", "Slow lift",
#             "Almost there", "Return home 1", "Return home 2"
#         ]
#
#     def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
#         base_pos = 0.0
#
#         keyframes = [
#             [base_pos, -0.2, 0.6, 0.4, -1.5, 13.0, 1.50],        # Normal state - back
#             [base_pos, -0.1, 0.7, 0.3, -1.3, 12.0, 0.50],        # Feel sadness - back
#             [base_pos-0.1, 0.0, 0.9, 0.2, -1.7, 11.0, 0.50],     # Begin droop - neutral
#             [base_pos-0.1, 0.1, 1.1, 0.1, -1.4, 10.0, 1.50],     # Weight increases - slight forward
#             [base_pos-0.15, 0.2, 1.3, 0.0, -1.8, 10.0, 1.50],    # Shoulders sag - forward
#             [base_pos-0.2, 0.3, 1.5, -0.1, -1.5, 9.0, 1.50],     # Head drops - forward OK
#             [base_pos-0.2, 0.3, 2.0, 0.0, -1.9, 8.0, 0.50],      # Deep sadness (proper slouch)
#             [base_pos-0.2, 0.3, 2.1, 0.0, -1.6, 8.0, 0.50],      # Hold sadness
#             [base_pos-0.15, 0.25, 2.0, 0.1, -1.8, 9.0, 1.50],    # Small sigh
#             [base_pos-0.15, 0.3, 2.0, 0.0, -1.5, 9.0, 1.50],     # Another sigh
#             [base_pos-0.1, -0.3, 1.8, 0.2, -1.7, 10.0, 1.50],    # Begin recovery - back
#             [base_pos, -0.5, 1.5, 0.5, -1.5, 11.0, 0.70],        # Slow lift - back
#             [base_pos, -0.2, 1.2, 0.8, -1.5, 12.0, 1.50],        # Almost there - back
#             [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0, 1.50],         # Return home 1
#             [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0, 1.50]        # Return home 2
#         ]
#
#         # Appropriately slow for sadness but not too sluggish
#         durations = [0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 1.2, 1.8, 1.0, 1.0, 0.9, 0.85, 0.8, 0.6, 0.9]
#
#         return keyframes, durations


# COMMENTED OUT: This animation stretches forward and breaks things
# class PlayfulBounceAnimation(AnimationPlugin):
#     """A playful, energetic bounce animation."""
#
#     @property
#     def name(self) -> str:
#         return "playful"
#
#     @property
#     def description(self) -> str:
#         return "Playful bouncing motion with joyful energy"
#
#     def get_category(self) -> str:
#         return "emotion"
#
#     def get_keyframe_names(self) -> Optional[List[str]]:
#         return [
#             "Ready stance", "Wind up wiggle", "Compress down", "Spring load",
#             "Explosive jump", "Air dance 1", "Air dance 2", "Peak twist",
#             "Fall begin", "Impact ready", "Bounce compress", "Spring again",
#             "Second jump", "Quick land", "Happy shake", "Final bounce",
#             "Return home 1", "Return home 2"
#         ]
#
#     def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
#         base_pos = 0.0
#
#         keyframes = [
#             [base_pos, -0.1, 0.8, 0.6, -1.5, 16.0, 1.50],        # Ready stance - back
#             [base_pos+0.2, -0.2, 0.75, 0.65, -1.2, 18.0, 2.40],  # Wind up wiggle - back
#             [base_pos, 0.2, 1.3, 0.2, -1.8, 15.0, 0.70],         # Compress down - forward OK
#             [base_pos, -0.8, 1.6, 0.6, -1.0, 14.0, 1.50],        # Spring load - far back
#             [base_pos, -0.6, 0.3, 1.3, -2.0, 22.0, 1.50],        # Explosive jump - back
#             [base_pos+0.3, -0.7, 0.2, 1.4, -0.8, 21.0, 1.50],    # Air dance 1 - back
#             [base_pos-0.3, -0.7, 0.2, 1.4, -2.1, 21.0, 1.50],    # Air dance 2 - back
#             [base_pos, -0.8, 0.1, 1.5, -1.0, 20.0, 2.60],        # Peak twist - far back
#             [base_pos, -0.4, 0.5, 1.1, -1.7, 18.0, 1.50],        # Fall begin - back
#             [base_pos, -0.1, 1.0, 0.5, -1.3, 16.0, 1.50],        # Impact ready - back
#             [base_pos, 0.3, 1.6, 0.1, -1.9, 14.0, 0.70],         # Bounce compress - forward OK
#             [base_pos, -0.7, 1.0, 0.8, -0.9, 19.0, 1.50],        # Spring again - back
#             [base_pos+0.1, -0.5, 0.4, 1.2, -1.8, 20.0, 1.50],    # Second jump - back
#             [base_pos, 0.1, 1.2, 0.4, -1.2, 17.0, 1.50],         # Quick land - slight forward
#             [base_pos-0.15, -0.3, 0.9, 0.7, -2.0, 18.0, 2.60],   # Happy shake - back
#             [base_pos, -0.2, 0.8, 0.8, -1.5, 16.0, 2.10],        # Final bounce - back
#             [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0, 1.50],         # Return home 1
#             [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0, 1.50]        # Return home 2
#         ]
#
#         # Quick playful bounces
#         durations = [0.45, 0.4, 0.6, 0.75, 0.65, 0.45, 0.5, 0.35, 0.45, 0.55, 0.75, 0.6, 0.5, 0.55, 0.4, 0.45, 0.6, 0.9]
#
#         return keyframes, durations


class StartledJumpAnimation(AnimationPlugin):
    """A startled jump reaction with quick, panicked movements."""
    
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
            "Calm state", "Tiny tension", "WHAT?!", "Jump back", "Peak startle",
            "Shake left", "Shake right", "Cautious look", "Is it safe?",
            "Check left", "Check right", "Still nervous", "Calming down",
            "Almost okay", "Final check", "All clear", "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.3, 0.8, 0.5, -1.5, 14.0, 1.50],        # Calm state - back
            [base_pos, -0.25, 0.75, 0.45, -1.3, 15.0, 1.50],     # Tiny tension - back
            [base_pos, -0.9, 1.4, 0.3, -1.9, 13.0, 0.70],        # WHAT?! - compress - far back
            [base_pos-0.4, -0.5, 0.2, 1.5, -0.8, 22.5, 1.50],    # Jump back - back
            [base_pos-0.5, -0.6, 0.1, 1.6, -2.1, 22.0, 1.50],    # Peak startle - back
            [base_pos-0.6, -0.55, 0.15, 1.55, -0.75, 21.0, 1.40], # Shake left - back
            [base_pos-0.4, -0.55, 0.15, 1.55, -2.2, 21.0, 1.60],  # Shake right - back
            [base_pos-0.3, -0.4, 0.6, 1.0, -1.0, 18.0, 1.50],     # Cautious look - back
            [base_pos-0.2, -0.1, 0.9, 0.7, -1.8, 16.0, 1.50],     # Is it safe? - back
            [base_pos-0.5, -0.2, 0.85, 0.75, -1.2, 17.0, 1.40],   # Check left - back
            [base_pos+0.3, -0.2, 0.85, 0.75, -1.9, 17.0, 1.60],   # Check right - back
            [base_pos-0.1, -0.3, 0.9, 0.6, -1.3, 15.0, 1.50],     # Still nervous - back
            [base_pos, -0.4, 1.0, 0.5, -1.7, 14.0, 0.70],         # Calming down - back
            [base_pos, -0.5, 1.1, 0.4, -1.5, 13.0, 1.50],         # Almost okay - back
            [base_pos+0.1, -0.45, 1.05, 0.45, -1.6, 14.0, 1.50],  # Final check - back
            [base_pos, -0.4, 1.0, 0.5, -1.5, 13.0, 1.50],         # All clear - back
            [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0, 1.50],          # Return home 1
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0, 1.50]         # Return home 2
        ]
        
        # Quick panic with appropriate recovery
        durations = [0.55, 0.4, 0.7, 0.65, 0.35, 0.35, 0.45, 0.45, 0.55, 0.7, 0.7, 0.55, 0.6, 0.7, 0.55, 0.6, 0.6, 0.9]
        
        return keyframes, durations