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
            "Final nod", "Return neutral", "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.3, 0.7, 0.3, -1.5, 12.0],     # Neutral - center
            [base_pos, 0.35, 0.8, 0.0, -1.3, 14.0],    # First nod down - slight right
            [base_pos, 0.25, 0.6, 0.5, -1.7, 13.0],    # First nod up - left to balance
            [base_pos, 0.4, 0.85, -0.1, -1.2, 15.0],   # Second nod down - right to balance
            [base_pos, 0.27, 0.65, 0.4, -1.8, 14.0],   # Second nod up - left to balance
            [base_pos, 0.35, 0.75, 0.1, -1.1, 16.0],   # Third nod down - right to balance
            [base_pos, 0.28, 0.68, 0.35, -1.9, 15.0],  # Third nod up - left to balance
            [base_pos, 0.32, 0.72, 0.25, -1.4, 13.0],  # Final tiny nod - slight right
            [base_pos, 0.3, 0.7, 0.3, -1.5, 12.0],     # Return neutral - center
            [base_pos, 0.5, 1.3, 1.4, -1.5, 11.0],     # Return to home position 1 - neutral
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]    # Return to home position 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.5, 0.57, 0.46, 0.53, 0.43, 0.44, 0.4, 0.46, 0.67, 0.64, 1.3]
        
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
            "Third shake left", "Final shake right", "Final shake left", "Settle",
            "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.3, 0.7, 0.3, -1.5, 12.0],      # Neutral - center
            [base_pos-0.1, 0.3, 0.7, 0.3, -1.3, 13.0],  # Anticipation - slight right
            [base_pos+0.3, 0.3, 0.7, 0.35, -2.0, 18.0], # First right - left extreme for contrast
            [base_pos-0.35, 0.3, 0.7, 0.35, -0.8, 19.0], # First left - right extreme to balance
            [base_pos+0.25, 0.3, 0.7, 0.32, -1.8, 17.0], # Second right - left to balance
            [base_pos-0.3, 0.3, 0.7, 0.32, -1.0, 16.0],  # Second left - right to balance
            [base_pos+0.2, 0.3, 0.7, 0.3, -1.6, 15.0],   # Third right - left to balance
            [base_pos-0.2, 0.3, 0.7, 0.3, -1.2, 14.0],   # Third left - right to balance
            [base_pos+0.1, 0.3, 0.7, 0.3, -1.7, 16.0],   # Final right - left
            [base_pos-0.1, 0.3, 0.7, 0.3, -1.4, 15.0],   # Final left - slight right to balance
            [base_pos, 0.32, 0.72, 0.28, -1.5, 12.0],    # Settle - center neutral
            [base_pos, 0.5, 1.3, 1.4, -1.5, 11.0],       # Return home 1 - neutral
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]      # Return home 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.5, 0.46, 0.33, 0.32, 0.35, 0.38, 0.4, 0.43, 0.38, 0.4, 0.67, 0.64, 1.3]
        
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
    
    @property
    def preserve_base_position(self) -> bool:
        """This animation should not preserve base position - always returns to center."""
        return False
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Prepare fold", "Begin folding", "Continue fold", "Final position", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Use current base position for smooth transition
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.9, 1.0, 1.5, -1.3, 11.0],   # Prepare - slight right
            [base_pos, -0.9, 1.5, 1.6, -1.8, 10.5],   # Begin fold - left to balance
            [base_pos, -1.1, 2.0, 1.7, -2.2, 10.0],   # Continue - more left
            [base_pos, -1.4, 2.0, 1.8, -0.8, 10.0],   # Final closed - right extreme to balance
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]   # Go directly to home 2 (close) - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [1.64, 2.29, 2.4, 2.4, 1.3]
        
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
    
    @property
    def preserve_base_position(self) -> bool:
        """Emergency stop should center the base for safety."""
        return False
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Just return to a safe neutral position quickly, then home
        keyframes = [
            [0.0, 0.3, 0.7, 0.3, -1.5, 14.0],     # Safe neutral - center
            [0.0, 0.5, 1.3, 1.4, -1.5, 12.0],     # Return home 1 - neutral
            [0.0, -0.85, 1.3, 1.4, -1.5, 10.0]    # Return home 2 - neutral
        ]
        
        durations = [0.71, 0.58, 1.3]  # Scaled for safety but still relatively quick
        
        return keyframes, durations