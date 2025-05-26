#!/usr/bin/env python3
"""
Response-based animation plugins for the LuxoPi system.
These animations are responses to commands or interactions.
"""

from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class NoddingAnimation(AnimationPlugin):
    """Make the arm nod 'yes' with varying intensity."""
    
    @property
    def name(self) -> str:
        return "nod"
    
    @property
    def description(self) -> str:
        return "Nodding motion indicating agreement or acknowledgment"
    
    def get_category(self) -> str:
        return "response"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Neutral", "First nod down", "First nod up", "Second nod down",
            "Second nod up", "Third nod down", "Third nod up",
            "Final nod", "Return neutral"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.3, 0.7, 0.3, 0.0],    # Neutral
            [base_pos, 0.35, 0.8, 0.0, 0.0],   # First nod down
            [base_pos, 0.25, 0.6, 0.5, 0.0],   # First nod up
            [base_pos, 0.4, 0.85, -0.1, 0.0],  # Second nod down
            [base_pos, 0.27, 0.65, 0.4, 0.0],  # Second nod up
            [base_pos, 0.35, 0.75, 0.1, 0.0],  # Third nod down
            [base_pos, 0.28, 0.68, 0.35, 0.0], # Third nod up
            [base_pos, 0.32, 0.72, 0.25, 0.0], # Final tiny nod
            [base_pos, 0.3, 0.7, 0.3, 0.0]     # Return neutral
        ]
        
        durations = [0.3, 0.4, 0.3, 0.4, 0.25, 0.35, 0.2, 0.25, 0.4]
        
        return keyframes, durations


class HeadShakeAnimation(AnimationPlugin):
    """Make the arm shake 'no' with decreasing intensity."""
    
    @property
    def name(self) -> str:
        return "shake"
    
    @property
    def description(self) -> str:
        return "Head shaking motion indicating disagreement or denial"
    
    def get_category(self) -> str:
        return "response"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Neutral", "Anticipation", "First shake right", "First shake left",
            "Second shake right", "Second shake left", "Third shake right",
            "Third shake left", "Final shake right", "Final shake left", "Settle"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.3, 0.7, 0.3, 0.0],      # Neutral
            [base_pos-0.1, 0.3, 0.7, 0.3, 0.0],  # Anticipation
            [base_pos+0.3, 0.3, 0.7, 0.35, 0.0], # First right
            [base_pos-0.35, 0.3, 0.7, 0.35, 0.0], # First left
            [base_pos+0.25, 0.3, 0.7, 0.32, 0.0], # Second right
            [base_pos-0.3, 0.3, 0.7, 0.32, 0.0],  # Second left
            [base_pos+0.2, 0.3, 0.7, 0.3, 0.0],   # Third right
            [base_pos-0.2, 0.3, 0.7, 0.3, 0.0],   # Third left
            [base_pos+0.1, 0.3, 0.7, 0.3, 0.0],   # Final right
            [base_pos-0.1, 0.3, 0.7, 0.3, 0.0],   # Final left
            [base_pos, 0.32, 0.72, 0.28, 0.0]     # Settle
        ]
        
        durations = [0.3, 0.2, 0.25, 0.25, 0.25, 0.25, 0.2, 0.2, 0.15, 0.15, 0.4]
        
        return keyframes, durations


class CloseAnimation(AnimationPlugin):
    """Move the arm to a closed/shutdown position."""
    
    @property
    def name(self) -> str:
        return "close"
    
    @property
    def description(self) -> str:
        return "Compact closing motion for shutdown or storage"
    
    def get_category(self) -> str:
        return "response"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Prepare fold", "Begin folding", "Continue fold", "Final position"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Use current base position for smooth transition
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.9, 1.0, 1.5, 0.0],  # Prepare
            [base_pos, -0.9, 1.5, 1.6, 0.0],  # Begin fold
            [base_pos, -1.1, 2.0, 1.7, 0.0],  # Continue
            [base_pos, -1.4, 2.0, 1.8, 0.0]   # Final closed
        ]
        
        durations = [0.9, 1.2, 1.2, 1.2]
        
        return keyframes, durations


class StopAnimation(AnimationPlugin):
    """Immediately stop and return to neutral position."""
    
    @property
    def name(self) -> str:
        return "stop"
    
    @property
    def description(self) -> str:
        return "Emergency stop returning to safe neutral position"
    
    def get_category(self) -> str:
        return "response"
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Just return to a safe neutral position quickly
        keyframes = [
            [0.0, 0.3, 0.7, 0.3, 0.0]  # Safe neutral
        ]
        
        durations = [0.5]  # Quick movement
        
        return keyframes, durations