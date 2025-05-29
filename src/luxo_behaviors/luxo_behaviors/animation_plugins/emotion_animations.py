#!/usr/bin/env python3
"""
Emotion-based animation plugins for the LuxoPi system.
These animations express various emotional states.
"""

import random
from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class ExcitedHopAnimation(AnimationPlugin):
    """An excited bouncy hop animation with Disney-style principles."""
    
    @property
    def name(self) -> str:
        return "excited"
    
    @property
    def description(self) -> str:
        return "Energetic bouncing hop expressing excitement"
    
    def get_category(self) -> str:
        return "emotion"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Initial wiggle", "Opposite wiggle", "Crouch down", "Deep crouch",
            "Begin fold", "Maximum compression", "Explosive release", "Maximum extension",
            "Overshoot", "Apex wiggle 1", "Apex wiggle 2", "Start descent",
            "Continue descent", "Impact landing", "Compression", "Bounce prep",
            "Secondary bounce", "Small apex", "Second landing", "Mini-fold",
            "Final hop", "Settling", "Final position"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Use base_pos = 0 for consistency
        base_pos = 0.0
        
        keyframes = [
            [base_pos+0.2, 0.35, 0.7, 0.3, 0.0],  # Initial wiggle
            [base_pos-0.2, 0.32, 0.68, 0.35, 0.0], # Opposite wiggle
            [base_pos, 0.7, 1.3, 0.0, 0.0],       # Crouch down
            [base_pos+0.1, 1.0, 1.8, -0.3, 0.0],  # Deep crouch
            [base_pos, -1.0, 1.0, 0.0, 0.0],      # Begin fold
            [base_pos, -2.0, 2.0, 2.0, 0.0],      # Maximum compression
            [base_pos, 0.0, 0.3, 1.0, 0.0],       # Explosive release
            [base_pos, -0.3, 0.1, 1.4, 0.0],      # Maximum extension
            [base_pos-0.2, -0.4, 0.0, 1.6, 0.0],  # Overshoot
            [base_pos+0.3, -0.35, 0.05, 1.5, 0.0], # Apex wiggle 1
            [base_pos-0.25, -0.35, 0.05, 1.5, 0.0], # Apex wiggle 2
            [base_pos, -0.1, 0.3, 1.2, 0.0],      # Start descent
            [base_pos+0.2, 0.2, 0.6, 0.8, 0.0],   # Continue descent
            [base_pos+0.1, 0.75, 1.7, 0.0, 0.0],  # Impact landing
            [base_pos, 0.75, 1.8, -0.2, 0.0],     # Compression
            [base_pos-0.1, 0.75, 1.5, 0.1, 0.0],  # Bounce prep
            [base_pos-0.05, 0.2, 0.6, 0.8, 0.0],  # Secondary bounce
            [base_pos+0.1, 0.15, 0.5, 0.9, 0.0],  # Small apex
            [base_pos+0.15, 0.6, 1.2, 0.3, 0.0],  # Second landing
            [base_pos, 0.5, 1.0, 0.4, 0.0],       # Mini-fold
            [base_pos-0.05, 0.3, 0.8, 0.6, 0.0],  # Final hop
            [base_pos+0.05, 0.35, 0.75, 0.5, 0.0], # Settling
            [base_pos, -0.85, 1.3, 1.4, 0.0]      # Final position (already at home!)
        ]
        
        # Doubled most durations to slow down animation
        durations = [
            0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6,
            0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.65,
            0.6, 0.6, 0.6
        ]
        
        return keyframes, durations


class SadDroopAnimation(AnimationPlugin):
    """A sad drooping animation with heavy, slow movements."""
    
    @property
    def name(self) -> str:
        return "sad"
    
    @property
    def description(self) -> str:
        return "Slow, heavy drooping motion expressing sadness"
    
    def get_category(self) -> str:
        return "emotion"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Initial energy", "Realization", "Start droop", "Hesitation",
            "Resistance", "Heavy droop", "Full slump", "More compression",
            "Maximum sad", "Deep sigh", "Small movement", "Trembling",
            "Long pause", "Slow recovery start", "Continue recovery",
            "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.15, 0.5, 0.2, 0.0],      # Initial energy
            [base_pos-0.05, 0.25, 0.65, 0.0, 0.0], # Realization
            [base_pos-0.1, 0.4, 0.8, -0.3, 0.0],  # Start droop
            [base_pos-0.15, 0.45, 0.85, -0.35, 0.0], # Hesitation
            [base_pos-0.1, 0.35, 0.75, -0.2, 0.0], # Resistance
            [base_pos-0.25, 0.9, 1.6, -0.9, 0.0], # Heavy droop
            [base_pos-0.3, -1.0, 1.5, -0.8, 0.0], # Full slump
            [base_pos-0.35, -1.5, 1.8, 0.0, 0.0], # More compression
            [base_pos-0.4, -2.0, 2.0, 1.0, 0.0],  # Maximum sad
            [base_pos-0.35, -1.9, 1.9, 1.1, 0.0], # Deep sigh
            [base_pos-0.4, -2.0, 2.0, 1.0, 0.0],  # Small movement
            [base_pos-0.38, -1.95, 1.95, 0.95, 0.0], # Trembling
            [base_pos-0.4, -2.0, 2.0, 1.0, 0.0],  # Long pause
            [base_pos-0.35, -1.5, 1.7, 0.5, 0.0], # Slow recovery start
            [base_pos-0.3, -1.0, 1.5, 0.0, 0.0],  # Continue recovery
            [base_pos, 0.5, 1.3, 1.4, 0.0],       # Return home 1
            [base_pos, -0.85, 1.3, 1.4, 0.0]      # Return home 2
        ]
        
        # Increased durations for slower movement
        durations = [
            0.8, 0.8, 1.0, 0.6, 1.2, 1.6, 1.8, 1.8, 1.4, 1.0,
            0.8, 0.6, 1.6, 1.2, 1.2, 0.7, 1.3
        ]
        
        return keyframes, durations


class PlayfulBounceAnimation(AnimationPlugin):
    """A playful, energetic bounce animation."""
    
    @property
    def name(self) -> str:
        return "playful"
    
    @property
    def description(self) -> str:
        return "Playful bouncing motion with joyful energy"
    
    def get_category(self) -> str:
        return "emotion"
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.35, 0.8, 0.4, 0.0],      # Initial pose
            [base_pos+0.25, 0.3, 0.75, 0.45, 0.0], # Anticipation wiggle
            [base_pos-0.25, 0.3, 0.75, 0.5, 0.0], # Opposite wiggle
            [base_pos, -1.0, 1.0, 0.0, 0.0],      # Start folding
            [base_pos, -2.0, 2.0, 2.0, 0.0],      # Maximum compression
            [base_pos, -2.0, 2.0, 1.8, 0.0],      # Hold compression
            [base_pos, 0.0, 0.2, 1.2, 0.0],       # Explosive release
            [base_pos, -0.2, 0.1, 1.5, 0.0],      # Maximum extension
            [base_pos+0.2, -0.1, 0.1, 1.6, 0.0],  # Follow through
            [base_pos-0.2, -0.1, 0.1, 1.5, 0.0],  # Joyful wiggle
            [base_pos+0.1, 0.2, 0.4, 0.9, 0.0],   # Begin fall
            [base_pos+0.2, 0.8, 1.5, 0.1, 0.0],   # Impact
            [base_pos+0.3, 0.9, 1.6, 0.0, 0.0],   # Compression
            [base_pos+0.2, -1.0, 1.0, 0.5, 0.0],  # Second bounce prep
            [base_pos+0.1, -1.8, 1.8, 1.5, 0.0],  # Second compression
            [base_pos-0.3, 0.1, 0.4, 0.9, 0.0],   # Second bounce
            [base_pos-0.4, 0.05, 0.35, 1.0, 0.0], # Second apex
            [base_pos-0.5, 0.7, 1.3, 0.2, 0.0],   # Second landing
            [base_pos-0.3, -0.5, 1.0, 1.0, 0.0],  # Mini-fold
            [base_pos, 0.15, 0.5, 0.8, 0.0],      # Final hop
            [base_pos+0.05, 0.4, 0.85, 0.45, 0.0], # Overshoot
            [base_pos, 0.3, 0.7, 0.5, 0.0],       # Settle
            [base_pos, 0.35, 0.75, 0.4, 0.0],     # Final position
            [base_pos, 0.5, 1.3, 1.4, 0.0],       # Return home 1
            [base_pos, -0.85, 1.3, 1.4, 0.0]      # Return home 2
        ]
        
        # Doubled durations for safety
        durations = [
            0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6,
            0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6,
            0.6, 0.6, 0.8, 0.7, 1.3
        ]
        
        return keyframes, durations


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
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.3, 0.7, 0.0, 0.0],       # Calm start
            [base_pos, 0.32, 0.72, -0.05, 0.0],   # Subtle tension
            [base_pos, -1.0, 1.0, 0.0, 0.0],      # Quick compression
            [base_pos-0.4, -0.3, 0.1, 1.6, 0.0],  # Explosive panic
            [base_pos-0.6, -0.4, 0.0, 1.8, 0.0],  # Maximum shock
            [base_pos-0.5, -0.35, 0.05, 1.7, 0.0], # Violent shake
            [base_pos-0.7, -0.35, 0.05, 1.7, 0.0], # Opposing shake
            [base_pos-0.55, -0.15, 0.3, 1.3, 0.0], # Initial settling
            [base_pos-0.45, 0.5, 1.0, 0.7, 0.0],  # Cautious stance
            [base_pos-0.6, 0.4, 0.9, 0.8, 0.0],   # Nervous bounce
            [base_pos-0.3, 0.45, 0.95, 0.5, 0.0], # Hesitant peek
            [base_pos-0.5, 0.5, 1.0, 0.7, 0.0],   # Quick recoil
            [base_pos-0.2, 0.4, 0.9, 0.4, 0.0],   # Braver peek
            [base_pos+0.3, 0.35, 0.85, 0.5, 0.0], # Quick glance right
            [base_pos-0.4, 0.35, 0.85, 0.5, 0.0], # Rapid glance left
            [base_pos+0.2, 0.35, 0.85, 0.5, 0.0], # Less extreme glance
            [base_pos-0.1, 0.4, 0.9, 0.45, 0.0],  # Back to center
            [base_pos-0.05, 0.35, 0.8, 0.35, 0.0], # Beginning to relax
            [base_pos, 0.3, 0.7, 0.25, 0.0],      # Vigilant final pose
            [base_pos, 0.5, 1.3, 1.4, 0.0],       # Return home 1
            [base_pos, -0.85, 1.3, 1.4, 0.0]      # Return home 2
        ]
        
        # Doubled durations for safety (but kept some quick movements for effect)
        durations = [
            0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6,
            0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.8, 1.0, 0.7, 1.3
        ]
        
        return keyframes, durations