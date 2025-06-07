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
            [base_pos+0.2, 0.35, 0.7, 0.3, -1.2, 15.0],   # Initial wiggle - slight right tilt
            [base_pos-0.2, 0.32, 0.68, 0.35, -1.8, 16.0], # Opposite wiggle - strong left tilt to balance
            [base_pos, 0.7, 1.3, 0.0, -1.5, 14.0],        # Crouch down - center
            [base_pos+0.1, 1.0, 1.8, -0.3, -1.3, 13.0],   # Deep crouch - slight right
            [base_pos, -1.0, 1.0, 0.0, -2.0, 11.0],       # Begin fold - left extreme
            [base_pos, -2.0, 2.0, 2.0, -2.3, 10.0],       # Maximum compression - further left
            [base_pos, 0.0, 0.3, 1.0, -0.8, 20.0],        # Explosive release - right extreme to balance
            [base_pos, -0.3, 0.1, 1.4, -0.5, 22.0],       # Maximum extension - extreme right
            [base_pos-0.2, -0.4, 0.0, 1.6, -0.9, 18.0],   # Overshoot - back toward left
            [base_pos+0.3, -0.35, 0.05, 1.5, -2.1, 19.0], # Apex wiggle 1 - left extreme
            [base_pos-0.25, -0.35, 0.05, 1.5, -0.7, 21.0], # Apex wiggle 2 - right extreme to balance
            [base_pos, -0.1, 0.3, 1.2, -1.5, 17.0],       # Start descent - center
            [base_pos+0.2, 0.2, 0.6, 0.8, -1.0, 16.0],    # Continue descent - right
            [base_pos+0.1, 0.75, 1.7, 0.0, -1.8, 14.0],   # Impact landing - left to balance
            [base_pos, 0.75, 1.8, -0.2, -2.0, 12.0],      # Compression - further left
            [base_pos-0.1, 0.75, 1.5, 0.1, -0.8, 15.0],   # Bounce prep - right to balance
            [base_pos-0.05, 0.2, 0.6, 0.8, -1.2, 17.0],   # Secondary bounce - slight left
            [base_pos+0.1, 0.15, 0.5, 0.9, -1.8, 18.0],   # Small apex - left
            [base_pos+0.15, 0.6, 1.2, 0.3, -0.9, 16.0],   # Second landing - right to balance
            [base_pos, 0.5, 1.0, 0.4, -1.6, 13.0],        # Mini-fold - left
            [base_pos-0.05, 0.3, 0.8, 0.6, -1.3, 14.0],   # Final hop - slight left
            [base_pos+0.05, 0.35, 0.75, 0.5, -1.7, 12.0], # Settling - right to balance
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]       # Final position - center neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.4, 0.38, 0.43, 0.46, 0.55, 0.6, 0.3, 0.27, 0.33, 0.32, 0.29, 0.35, 0.38, 0.43, 0.5, 0.4, 0.35, 0.33, 0.38, 0.46, 0.43, 0.5, 0.6]
        
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
            [base_pos, 0.15, 0.5, 0.2, -1.4, 13.0],       # Initial energy - slight right
            [base_pos-0.05, 0.25, 0.65, 0.0, -1.6, 12.0], # Realization - left tilt
            [base_pos-0.1, 0.4, 0.8, -0.3, -1.9, 11.0],   # Start droop - more left
            [base_pos-0.15, 0.45, 0.85, -0.35, -2.1, 10.5], # Hesitation - further left
            [base_pos-0.1, 0.35, 0.75, -0.2, -1.8, 11.5], # Resistance - slight right return
            [base_pos-0.25, 0.9, 1.6, -0.9, -2.3, 10.0],  # Heavy droop - extreme left
            [base_pos-0.3, -1.0, 1.5, -0.8, -2.5, 10.0],  # Full slump - maximum left
            [base_pos-0.35, -1.5, 1.8, 0.0, -2.4, 10.0],  # More compression - slight right
            [base_pos-0.4, -2.0, 2.0, 1.0, -2.2, 10.0],   # Maximum sad - more right
            [base_pos-0.35, -1.9, 1.9, 1.1, -1.8, 11.0],  # Deep sigh - significant right shift
            [base_pos-0.4, -2.0, 2.0, 1.0, -1.9, 10.5],   # Small movement - slight left
            [base_pos-0.38, -1.95, 1.95, 0.95, -2.0, 10.5], # Trembling - slight left
            [base_pos-0.4, -2.0, 2.0, 1.0, -1.7, 11.0],   # Long pause - right to balance
            [base_pos-0.35, -1.5, 1.7, 0.5, -1.6, 11.5],  # Slow recovery start - less right
            [base_pos-0.3, -1.0, 1.5, 0.0, -1.5, 12.0],   # Continue recovery - center
            [base_pos, 0.5, 1.3, 1.4, -1.5, 11.0],        # Return home 1 - neutral
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]       # Return home 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.62, 0.67, 0.91, 0.57, 1.04, 1.6, 1.8, 1.8, 1.4, 0.91, 0.76, 0.57, 1.45, 1.04, 1.0, 0.64, 1.3]
        
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
            [base_pos, 0.35, 0.8, 0.4, -1.3, 14.0],       # Initial pose - slight left
            [base_pos+0.25, 0.3, 0.75, 0.45, -0.9, 17.0], # Anticipation wiggle - right to balance
            [base_pos-0.25, 0.3, 0.75, 0.5, -1.7, 16.0],  # Opposite wiggle - left to balance
            [base_pos, -1.0, 1.0, 0.0, -2.0, 12.0],       # Start folding - left extreme
            [base_pos, -2.0, 2.0, 2.0, -2.3, 10.0],       # Maximum compression - further left
            [base_pos, -2.0, 2.0, 1.8, -1.8, 11.0],       # Hold compression - right shift
            [base_pos, 0.0, 0.2, 1.2, -0.6, 20.0],        # Explosive release - right extreme
            [base_pos, -0.2, 0.1, 1.5, -0.5, 22.0],       # Maximum extension - more right
            [base_pos+0.2, -0.1, 0.1, 1.6, -0.8, 18.0],   # Follow through - left shift
            [base_pos-0.2, -0.1, 0.1, 1.5, -1.9, 19.0],   # Joyful wiggle - left extreme
            [base_pos+0.1, 0.2, 0.4, 0.9, -0.7, 17.0],    # Begin fall - right to balance
            [base_pos+0.2, 0.8, 1.5, 0.1, -1.2, 15.0],    # Impact - left
            [base_pos+0.3, 0.9, 1.6, 0.0, -1.8, 14.0],    # Compression - more left
            [base_pos+0.2, -1.0, 1.0, 0.5, -0.8, 16.0],   # Second bounce prep - right to balance
            [base_pos+0.1, -1.8, 1.8, 1.5, -2.0, 13.0],   # Second compression - left
            [base_pos-0.3, 0.1, 0.4, 0.9, -0.6, 21.0],    # Second bounce - right extreme
            [base_pos-0.4, 0.05, 0.35, 1.0, -1.0, 18.0],  # Second apex - left
            [base_pos-0.5, 0.7, 1.3, 0.2, -1.8, 15.0],    # Second landing - more left
            [base_pos-0.3, -0.5, 1.0, 1.0, -0.9, 17.0],   # Mini-fold - right to balance
            [base_pos, 0.15, 0.5, 0.8, -1.4, 14.0],       # Final hop - left
            [base_pos+0.05, 0.4, 0.85, 0.45, -1.6, 13.0], # Overshoot - more left
            [base_pos, 0.3, 0.7, 0.5, -1.5, 12.0],        # Settle - center
            [base_pos, 0.35, 0.75, 0.4, -1.5, 12.0],      # Final position - neutral
            [base_pos, 0.5, 1.3, 1.4, -1.5, 11.0],        # Return home 1 - neutral
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]       # Return home 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.43, 0.35, 0.38, 0.5, 0.6, 0.55, 0.3, 0.27, 0.33, 0.32, 0.35, 0.4, 0.43, 0.38, 0.46, 0.29, 0.33, 0.4, 0.35, 0.43, 0.46, 0.5, 0.67, 0.64, 1.3]
        
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
            [base_pos, 0.3, 0.7, 0.0, -1.5, 12.0],        # Calm start - neutral
            [base_pos, 0.32, 0.72, -0.05, -1.3, 13.0],    # Subtle tension - right
            [base_pos, -1.0, 1.0, 0.0, -2.2, 10.0],       # Quick compression - left extreme
            [base_pos-0.4, -0.3, 0.1, 1.6, -0.5, 22.0],   # Explosive panic - right extreme to balance
            [base_pos-0.6, -0.4, 0.0, 1.8, -0.7, 21.0],   # Maximum shock - more right
            [base_pos-0.5, -0.35, 0.05, 1.7, -2.0, 19.0], # Violent shake - left extreme
            [base_pos-0.7, -0.35, 0.05, 1.7, -0.6, 20.0], # Opposing shake - right extreme to balance
            [base_pos-0.55, -0.15, 0.3, 1.3, -1.8, 16.0], # Initial settling - left
            [base_pos-0.45, 0.5, 1.0, 0.7, -0.8, 17.0],   # Cautious stance - right to balance
            [base_pos-0.6, 0.4, 0.9, 0.8, -1.2, 15.0],    # Nervous bounce - left
            [base_pos-0.3, 0.45, 0.95, 0.5, -1.9, 14.0],  # Hesitant peek - more left
            [base_pos-0.5, 0.5, 1.0, 0.7, -0.7, 18.0],    # Quick recoil - right to balance
            [base_pos-0.2, 0.4, 0.9, 0.4, -1.3, 14.0],    # Braver peek - left
            [base_pos+0.3, 0.35, 0.85, 0.5, -2.1, 16.0],  # Quick glance right - left extreme
            [base_pos-0.4, 0.35, 0.85, 0.5, -0.5, 18.0],  # Rapid glance left - right extreme to balance
            [base_pos+0.2, 0.35, 0.85, 0.5, -1.8, 15.0],  # Less extreme glance - left
            [base_pos-0.1, 0.4, 0.9, 0.45, -0.9, 17.0],   # Back to center - right to balance
            [base_pos-0.05, 0.35, 0.8, 0.35, -1.4, 14.0], # Beginning to relax - left
            [base_pos, 0.3, 0.7, 0.25, -1.5, 12.0],       # Vigilant final pose - center neutral
            [base_pos, 0.5, 1.3, 1.4, -1.5, 11.0],        # Return home 1 - neutral
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]       # Return home 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.5, 0.46, 0.6, 0.27, 0.29, 0.32, 0.3, 0.38, 0.35, 0.4, 0.43, 0.33, 0.43, 0.38, 0.33, 0.4, 0.35, 0.43, 0.83, 0.64, 1.3]
        
        return keyframes, durations