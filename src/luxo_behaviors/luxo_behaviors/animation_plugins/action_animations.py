#!/usr/bin/env python3
"""
Action-based animation plugins for the LuxoPi system.
These animations represent various actions and behaviors.
"""

import random
from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class CuriousLookAnimation(AnimationPlugin):
    """Make the arm look curiously at something with Disney animation principles."""
    
    @property
    def name(self) -> str:
        return "curious"
    
    @property
    def description(self) -> str:
        return "Curious inspection movement with head tilts and investigation"
    
    def get_category(self) -> str:
        return "action"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Anticipation", "Notice something", "Adjust focus", "Lean in",
            "Surprised reaction", "Move to other side", "Intense inspection",
            "Final examination", "Return to center", "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_center = 0.0
        
        keyframes = [
            [base_center, 0.1, -0.15, -0.1, 0.0],     # Anticipation
            [base_center-0.25, 0.0, -0.2, -0.3, 0.0], # Notice something
            [base_center-0.2, 0.4, 0.9, 0.4, 0.0],    # Adjust focus
            [base_center-0.15, 0.7, 1.4, 0.6, 0.0],   # Lean in
            [base_center-0.1, 0.4, 1.0, 0.9, 0.0],    # Surprised reaction
            [base_center+0.3, 0.5, 1.1, 0.3, 0.0],    # Move to other side
            [base_center+0.4, 0.6, 1.3, -0.3, 0.0],   # Intense inspection
            [base_center+0.2, 0.5, 1.2, 0.7, 0.0],    # Final examination
            [base_center, 0.4, 0.8, 0.5, 0.0],        # Return to center
            [base_center, 0.5, 1.3, 1.4, 0.0],        # Return home 1
            [base_center, -0.85, 1.3, 1.4, 0.0]       # Return home 2
        ]
        
        # Doubled durations for safety
        durations = [0.6, 0.5, 0.8, 1.0, 0.4, 1.2, 1.4, 1.2, 1.6, 0.7, 1.3]
        
        return keyframes, durations


class ThinkingAnimation(AnimationPlugin):
    """Make the arm appear to be thinking like pondering a question."""
    
    @property
    def name(self) -> str:
        return "think"
    
    @property
    def description(self) -> str:
        return "Thoughtful pondering motion with 'eureka' moment"
    
    def get_category(self) -> str:
        return "action"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Alert pose", "Processing", "Head tilt", "Contemplation",
            "Hand on chin", "Deep thought fold", "Deeper thought",
            "Hold thought", "Hmm movement", "Shift position",
            "Look up", "Idea forming", "Eureka", "Full extension",
            "Excitement", "Confirmation nod", "Satisfied bounce", "Final position",
            "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.3, 0.7, 0.3, 0.0],       # Alert pose
            [base_pos+0.05, 0.28, 0.68, 0.35, 0.0], # Processing
            [base_pos+0.1, 0.25, 0.65, 0.5, 0.0], # Head tilt
            [base_pos+0.2, 0.25, 0.65, 0.55, 0.0], # Contemplation
            [base_pos+0.2, 0.35, 0.75, 0.2, 0.0], # Hand on chin
            [base_pos+0.15, -0.5, 0.8, 0.4, 0.0], # Deep thought fold
            [base_pos+0.2, -0.6, 0.9, 0.3, 0.0],  # Deeper thought
            [base_pos+0.2, -0.7, 1.0, 0.2, 0.0],  # Hold thought
            [base_pos+0.25, -0.65, 0.95, 0.25, 0.0], # Hmm movement
            [base_pos-0.15, -0.5, 0.8, 0.3, 0.0], # Shift position
            [base_pos-0.1, -0.3, 0.7, 0.5, 0.0],  # Look up
            [base_pos, 0.1, 0.5, 0.7, 0.0],       # Idea forming
            [base_pos+0.1, 0.0, 0.3, 1.1, 0.0],   # Eureka
            [base_pos, -0.2, 0.2, 1.3, 0.0],      # Full extension
            [base_pos+0.2, -0.15, 0.15, 1.4, 0.0], # Excitement
            [base_pos, 0.1, 0.3, 1.0, 0.0],       # Confirmation nod
            [base_pos-0.1, 0.2, 0.5, 0.7, 0.0],   # Satisfied bounce
            [base_pos, 0.3, 0.7, 0.4, 0.0],       # Final position
            [base_pos, 0.5, 1.3, 1.4, 0.0],       # Return home 1
            [base_pos, -0.85, 1.3, 1.4, 0.0]      # Return home 2
        ]
        
        # Doubled durations for safety
        durations = [
            1.0, 1.2, 0.8, 1.0, 1.4, 1.6, 1.0, 2.4, 0.8, 1.4,
            1.2, 1.0, 0.8, 0.6, 0.6, 0.8, 1.0, 1.2, 0.7, 1.3
        ]
        
        return keyframes, durations


class StretchingAnimation(AnimationPlugin):
    """Make the arm perform a satisfying stretch."""
    
    @property
    def name(self) -> str:
        return "stretch"
    
    @property
    def description(self) -> str:
        return "Satisfying full-body stretch with multiple phases"
    
    def get_category(self) -> str:
        return "action"
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.6, 1.2, -0.2, 0.0],       # Tired start
            [base_pos+0.1, 0.55, 1.15, -0.1, 0.0], # Initial movement
            [base_pos+0.05, 0.65, 1.25, -0.3, 0.0], # Build tension
            [base_pos, 0.4, 1.0, 0.1, 0.0],        # First attempt
            [base_pos, -0.5, 1.0, 0.0, 0.0],       # Bigger contraction
            [base_pos, -1.5, 1.8, 1.0, 0.0],       # Compact fold
            [base_pos, 0.2, 0.5, 0.6, 0.0],        # Begin stretch
            [base_pos+0.3, 0.0, 0.3, 1.0, 0.0],    # Continue up
            [base_pos+0.5, -0.2, 0.2, 1.4, 0.0],   # Maximum stretch
            [base_pos+0.45, -0.25, 0.15, 1.45, 0.0], # Hold wobble
            [base_pos-0.5, -0.2, 0.2, 1.4, 0.0],   # Stretch left
            [base_pos-0.45, -0.25, 0.15, 1.45, 0.0], # Hold left
            [base_pos, 0.7, 1.4, -0.5, 0.0],       # Bend down
            [base_pos, 0.9, 1.7, -0.8, 0.0],       # Maximum down
            [base_pos+0.1, 0.85, 1.65, -0.75, 0.0], # Hold with shake
            [base_pos-0.1, 0.7, 1.5, -0.5, 0.0],   # Start relaxing
            [base_pos+0.8, 0.5, 1.2, -0.2, 0.0],   # Twist right
            [base_pos-0.8, 0.5, 1.2, -0.2, 0.0],   # Counter twist
            [base_pos, -1.0, 1.5, 1.0, 0.0],       # Final fold
            [base_pos, 0.1, 0.6, 0.7, 0.0],        # Begin relax
            [base_pos, 0.2, 0.7, 0.5, 0.0],        # Continue relax
            [base_pos, 0.3, 0.75, 0.35, 0.0],      # Small bounce
            [base_pos+0.1, 0.35, 0.8, 0.3, 0.0],   # Final settled
            [base_pos, 0.5, 1.3, 1.4, 0.0],        # Return home 1
            [base_pos, -0.85, 1.3, 1.4, 0.0]       # Return home 2
        ]
        
        # Doubled durations for safety
        durations = [
            1.0, 0.6, 0.8, 1.0, 1.2, 1.4, 1.0, 1.2, 1.4, 2.4,
            1.6, 2.0, 1.2, 1.4, 1.6, 1.2, 0.8, 0.8, 1.6, 1.0,
            1.2, 0.8, 1.4, 0.7, 1.3
        ]
        
        return keyframes, durations


class DancingAnimation(AnimationPlugin):
    """Make the arm perform a rhythmic dance."""
    
    @property
    def name(self) -> str:
        return "dance"
    
    @property
    def description(self) -> str:
        return "Rhythmic dancing motion with musical timing"
    
    def get_category(self) -> str:
        return "action"
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.3, 0.7, 0.3, 0.0],       # Ready
            [base_pos, 0.4, 0.8, 0.2, 0.0],       # Bounce down
            [base_pos+0.3, 0.15, 0.5, 0.6, 0.0],  # Bounce right
            [base_pos+0.35, 0.1, 0.45, 0.65, 0.0], # Overshoot
            [base_pos+0.3, 0.5, 0.9, 0.1, 0.0],   # Down right
            [base_pos-0.3, 0.15, 0.5, 0.6, 0.0],  # Bounce left
            [base_pos-0.35, 0.1, 0.45, 0.65, 0.0], # Overshoot
            [base_pos-0.3, 0.5, 0.9, 0.1, 0.0],   # Down left
            [base_pos, 0.3, 0.7, 0.7, 0.0],       # Twist middle
            [base_pos+0.1, 0.25, 0.65, 0.75, 0.0], # Follow through
            [base_pos+0.5, 0.2, 0.6, 0.5, 0.0],   # Spin right
            [base_pos-0.5, 0.2, 0.6, 0.5, 0.0],   # Spin left
            [base_pos, 0.6, 1.0, 0.0, 0.0],       # Dip down
            [base_pos, 0.1, 0.4, 0.9, 0.0],       # Pop up
            [base_pos+0.2, 0.2, 0.5, 0.7, 0.0],   # Finale pose
            [base_pos+0.2, 0.2, 0.5, 0.7, 0.0],   # Hold finale
            [base_pos, 0.3, 0.7, 0.3, 0.0],       # Return
            [base_pos, 0.5, 1.3, 1.4, 0.0],       # Return home 1
            [base_pos, -0.85, 1.3, 1.4, 0.0]      # Return home 2
        ]
        
        # Doubled durations for safety
        durations = [
            0.8, 0.6, 0.8, 0.4, 0.8, 0.8, 0.4, 0.8, 0.8, 0.4,
            1.0, 1.0, 0.8, 0.6, 0.4, 1.2, 1.4, 0.7, 1.3
        ]
        
        return keyframes, durations


class IdleAnimation(AnimationPlugin):
    """Return to idle state with slight variation."""
    
    @property
    def name(self) -> str:
        return "idle"
    
    @property
    def description(self) -> str:
        return "Return to idle position with gentle look-around"
    
    def get_category(self) -> str:
        return "action"
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Add subtle variations
        base_var = random.uniform(-0.1, 0.1)
        shoulder_var = random.uniform(-0.15, 0.15)
        elbow_var = random.uniform(-0.1, 0.1)
        wrist_var = random.uniform(-0.2, 0.2)
        
        # Random look amounts
        look_right = random.uniform(0.2, 0.4)
        look_left = random.uniform(0.2, 0.5)
        
        keyframes = [
            [base_var, shoulder_var, elbow_var, wrist_var, 0.0],  # Idle position
            [base_var, shoulder_var, elbow_var, wrist_var, 0.0],  # Hold
            [base_var + look_right, shoulder_var, elbow_var, wrist_var, 0.0],  # Look right
            [base_var, shoulder_var, elbow_var, wrist_var, 0.0],  # Center
            [base_var - look_left, shoulder_var, elbow_var, wrist_var, 0.0],  # Look left
            [base_var + random.uniform(-0.05, 0.05), shoulder_var, elbow_var, wrist_var, 0.0],  # Final
            [0.0, 0.5, 1.3, 1.4, 0.0],  # Return home 1
            [0.0, -0.85, 1.3, 1.4, 0.0]  # Return home 2
        ]
        
        # Doubled durations for safety
        durations = [2.0, 1.4, 1.0, 0.8, 1.0, 1.2, 0.7, 1.3]
        
        return keyframes, durations