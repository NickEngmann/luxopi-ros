#!/usr/bin/env python3
"""
Petting-based animation plugins for the LuxoPi system.
These animations respond to touch/petting interactions.
"""

import random
from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class HappyPetAnimation(AnimationPlugin):
    """Folded blissful dog - folds into C-shape and moves neck back and forth contentedly."""
    
    @property
    def name(self) -> str:
        return "folded_wiggle"
    
    @property
    def description(self) -> str:
        return "Folded C-shape with neck movements like a content dog"
    
    def get_category(self) -> str:
        return "petting"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Initial fold", "Deep C-curve", "Neck right", "Neck left", 
            "Content right", "Blissful left", "Happy center", "Gentle right",
            "Final left", "Settled contentment"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -1.3, 1.4, 0.8, -2.2, 10.0, 1.00],        # Initial fold - starting to curve
            [base_pos, -1.6, 1.8, 1.2, -2.8, 8.0, 1.00],         # Deep C-curve - folded position
            [base_pos+0.3, -1.65, 1.85, 1.3, -2.6, 9.0, 1.80],   # Neck right - head movement
            [base_pos-0.3, -1.7, 1.9, 1.4, -2.9, 8.5, 1.40],     # Neck left - opposite movement
            [base_pos+0.4, -1.75, 1.95, 1.5, -2.5, 9.5, 1.80],   # Content right - deeper fold
            [base_pos-0.4, -1.8, 2.0, 1.6, -3.0, 8.0, 1.40],     # Blissful left - maximum fold
            [base_pos, -1.75, 1.95, 1.4, -2.7, 9.0, 3.14],       # Happy center - balanced
            [base_pos+0.2, -1.7, 1.9, 1.3, -2.5, 10.0, 1.80],    # Gentle right - slight movement
            [base_pos-0.1, -1.6, 1.7, 1.1, -2.3, 11.0, 1.00],    # Final left - starting to unfold
            [base_pos, -0.55, 1.2, 1.0, -2.0, 12.0, 0.60]       # Settled contentment - final position
        ]
        
        # Smooth neck movement durations - 15% faster
        durations = [0.85, 1.02, 0.68, 0.77, 0.68, 0.77, 0.85, 0.94, 1.1, 1.53]
        
        return keyframes, durations


class ShyPetAnimation(AnimationPlugin):
    """Playful wiggle - energetic wiggle with bouncy movements while staying compact."""
    
    @property
    def name(self) -> str:
        return "bouncy_wiggle"
    
    @property
    def description(self) -> str:
        return "Energetic playful wiggle with controlled movements"
    
    def get_category(self) -> str:
        return "petting"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Ready position", "Quick right bounce", "Wiggle left", "Up bounce",
            "Spiral movement", "Quick shake", "Double bounce", "Side wiggle",
            "Happy bounce", "Settle wiggle", "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.4, 0.8, 0.5, -1.5, 17.0, 1.00],        # Ready position - back
            [base_pos+0.4, -0.5, 0.7, 0.4, -1.2, 19.0, 1.80],    # Quick right bounce - back
            [base_pos-0.4, -0.3, 0.9, 0.3, -1.8, 18.0, 1.40],    # Wiggle left - back
            [base_pos+0.2, -0.6, 0.5, 0.6, -0.9, 20.0, 2.80],    # Up bounce - back
            [base_pos+0.5, -0.4, 1.0, 0.4, -2.0, 17.0, 1.00],    # Spiral movement - back
            [base_pos-0.5, -0.5, 0.6, 0.5, -0.8, 21.0, 1.20],    # Quick shake - back
            [base_pos+0.15, -0.45, 0.8, 0.45, -1.7, 19.0, 2.20], # Double bounce - back
            [base_pos-0.3, -0.35, 0.95, 0.55, -1.1, 18.0, 2.20], # Side wiggle - back
            [base_pos+0.1, -0.4, 0.85, 0.6, -1.9, 16.0, 3.14],   # Happy bounce - back
            [base_pos, -0.5, 0.9, 0.7, -1.5, 15.0, 0.60],        # Settle wiggle - back
            [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0, 1.00],         # Return home 1
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0, 1.00]        # Return home 2
        ]
        
        # Snappier playful timing
        durations = [0.45, 0.55, 0.7, 0.45, 0.7, 0.75, 0.4, 0.45, 0.45, 0.55, 0.6, 0.9]
        
        return keyframes, durations


class ContentPetAnimation(AnimationPlugin):
    """Sleepy lean - gradual melting into relaxed position with safe parameters."""
    
    @property
    def name(self) -> str:
        return "sleepy_melt"
    
    @property
    def description(self) -> str:
        return "Gradual sleepy melting into relaxed position"
    
    def get_category(self) -> str:
        return "petting"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Alert start", "Begin relax", "Getting sleepy", "Drooping more",
            "Heavy eyelids", "Almost asleep", "Deep relax", "Peaceful state",
            "Contented sigh", "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.3, 0.6, 0.4, -1.5, 15.0, 1.00],        # Alert start - back
            [base_pos+0.05, -0.2, 0.8, 0.5, -1.3, 14.0, 0.60],   # Begin relax - back
            [base_pos, -0.1, 1.0, 0.6, -1.6, 13.0, 0.20],        # Getting sleepy - back
            [base_pos-0.05, 0.0, 1.2, 0.7, -1.4, 12.0, 0.00],    # Drooping more - neutral
            [base_pos, 0.1, 1.3, 0.8, -1.7, 11.0, 1.00],         # Heavy eyelids - slight forward
            [base_pos, 0.15, 1.4, 0.9, -1.5, 10.5, 0.20],        # Almost asleep - slight forward
            [base_pos, 0.2, 1.5, 1.0, -1.8, 10.0, 0.60],         # Deep relax - forward OK
            [base_pos, 0.25, 1.6, 1.1, -1.6, 9.0, 1.00],         # Peaceful state - forward OK
            [base_pos, 0.2, 1.5, 1.0, -1.5, 10.0, 1.00],         # Contented sigh
            [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0, 1.00],         # Return home 1
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0, 1.00]        # Return home 2
        ]
        
        # Slow but not too slow
        durations = [0.6, 0.7, 0.8, 0.85, 0.9, 1.0, 1.2, 1.3, 1.2, 0.8, 0.9]
        
        return keyframes, durations