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
            [base_pos, -1.3, 1.4, 0.8, -2.2, 10.0],        # Initial fold - starting to curve
            [base_pos, -1.6, 1.8, 1.2, -2.8, 8.0],         # Deep C-curve - folded position
            [base_pos+0.3, -1.65, 1.85, 1.3, -2.6, 9.0],   # Neck right - head movement
            [base_pos-0.3, -1.7, 1.9, 1.4, -2.9, 8.5],     # Neck left - opposite movement
            [base_pos+0.4, -1.75, 1.95, 1.5, -2.5, 9.5],   # Content right - deeper fold
            [base_pos-0.4, -1.8, 2.0, 1.6, -3.0, 8.0],     # Blissful left - maximum fold
            [base_pos, -1.75, 1.95, 1.4, -2.7, 9.0],       # Happy center - balanced
            [base_pos+0.2, -1.7, 1.9, 1.3, -2.5, 10.0],    # Gentle right - slight movement
            [base_pos-0.1, -1.6, 1.7, 1.1, -2.3, 11.0],    # Final left - starting to unfold
            [base_pos, -0.55, 1.2, 1.0, -2.0, 12.0]       # Settled contentment - final position
        ]
        
        # Smooth neck movement durations - 15% faster
        durations = [0.85, 1.02, 0.68, 0.77, 0.68, 0.77, 0.85, 0.94, 1.1, 1.53]
        
        return keyframes, durations


class ShyPetAnimation(AnimationPlugin):
    """Playful wiggle - energetic full-body wiggle with bouncy movements."""
    
    @property
    def name(self) -> str:
        return "bouncy_wiggle"
    
    @property
    def description(self) -> str:
        return "Energetic playful wiggle leaning backwards with bouncy movements"
    
    def get_category(self) -> str:
        return "petting"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Excited start", "Bounce right", "Wiggle left", "High bounce",
            "Spiral right", "Twist left", "Double bounce", "Side wiggle",
            "Settling bounce", "Final calm"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.1, 0.6, 0.3, -1.0, 16.0],       # Excited start - ready to play
            [base_pos+0.6, -0.5, 0.4, 0.2, -0.3, 15.0],   # Bounce right - lean back right
            [base_pos-0.6, -0.3, 0.8, 0.1, -1.8, 14.0],   # Wiggle left - lean back left
            [base_pos+0.3, -0.7, 0.2, 0.0, 0.2, 16.0],    # High bounce - lean way back
            [base_pos+0.7, -0.4, 1.2, 0.2, -1.5, 13.0],   # Spiral right - back and right
            [base_pos-0.7, -0.6, 0.5, 0.1, -0.8, 12.0],   # Twist left - back and left
            [base_pos+0.2, -0.5, 0.7, 0.3, -0.5, 11.0],   # Double bounce - gentle back lean
            [base_pos-0.4, -0.3, 1.0, 0.4, -1.3, 8.0],   # Side wiggle - settling back
            [base_pos+0.1, -0.4, 0.9, 0.6, -1.6, 12.0],   # Settling bounce - calming lean back
            [base_pos, -0.55, 1.2, 1.0, -2.0, 12.0]       # Final calm - final position
        ]
        
        # Quick, energetic durations - 15% faster
        durations = [0.43, 0.34, 0.51, 0.26, 0.43, 0.34, 0.51, 0.6, 0.85, 1.7]
        
        return keyframes, durations


class ContentPetAnimation(AnimationPlugin):
    """Sleepy lean - gradual melting into relaxed slouch like falling asleep from contentment."""
    
    @property
    def name(self) -> str:
        return "sleepy_melt"
    
    @property
    def description(self) -> str:
        return "Gradual sleepy melting into relaxed slouch from contentment"
    
    def get_category(self) -> str:
        return "petting"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Content start", "Gentle droop", "Sleepy lean", "Drowsy sag",
            "Heavy eyelids", "Nodding off", "Deep relax", "Almost asleep",
            "Heavy settle", "Peaceful rest"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.0, 0.5, 0.2, -1.2, 14.0],        # Content start - alert but relaxed
            [base_pos+0.1, 0.1, 0.7, 0.4, -1.4, 13.0],    # Gentle droop - starting to relax
            [base_pos+0.05, 0.2, 0.9, 0.6, -1.6, 12.5],   # Sleepy lean - getting drowsy
            [base_pos-0.05, 0.3, 1.1, 0.7, -1.8, 12.0],   # Drowsy sag - heavier
            [base_pos+0.02, 0.4, 1.3, 0.8, -1.9, 12.5],   # Heavy eyelids - very sleepy
            [base_pos-0.03, 0.45, 1.4, 0.85, -1.95, 12.0], # Nodding off - almost asleep
            [base_pos+0.01, 0.5, 1.5, 0.9, -2.0, 11.5],   # Deep relax - very heavy
            [base_pos, 0.52, 1.6, 0.95, -2.05, 10.0],     # Almost asleep - nearly there
            [base_pos, 0.54, 1.8, 0.98, -2.1, 9.5],       # Heavy settle - final droop
            [base_pos, -0.55, 1.2, 1.0, -2.0, 12.0]       # Peaceful rest - final position
        ]
        
        # Progressively slower, sleepier durations - 15% faster
        durations = [0.8, 1.2, 0.8, 0.7, 0.6, 0.8, 1.0, 0.9, 0.7, 1.7]
        
        return keyframes, durations
