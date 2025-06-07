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
            [base_center, 0.1, -0.15, -0.1, -1.4, 14.0],    # Anticipation - slight right
            [base_center-0.25, 0.0, -0.2, -0.3, -0.8, 17.0], # Notice something - right extreme
            [base_center-0.2, 0.4, 0.9, 0.4, -2.1, 15.0],    # Adjust focus - left extreme to balance
            [base_center-0.15, 0.7, 1.4, 0.6, -0.6, 18.0],   # Lean in - right to balance
            [base_center-0.1, 0.4, 1.0, 0.9, -1.9, 16.0],    # Surprised reaction - left
            [base_center+0.3, 0.5, 1.1, 0.3, -0.7, 19.0],    # Move to other side - right to balance
            [base_center+0.4, 0.6, 1.3, -0.3, -2.0, 14.0],   # Intense inspection - left extreme
            [base_center+0.2, 0.5, 1.2, 0.7, -0.9, 17.0],    # Final examination - right to balance
            [base_center, 0.4, 0.8, 0.5, -1.5, 13.0],        # Return to center - neutral
            [base_center, 0.5, 1.3, 1.4, -1.5, 11.0],        # Return home 1 - neutral
            [base_center, -0.85, 1.3, 1.4, -1.5, 10.0]       # Return home 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.43, 0.35, 0.53, 0.56, 0.38, 0.63, 1.0, 0.71, 1.23, 0.64, 1.3]
        
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
            [base_pos, 0.3, 0.7, 0.3, -1.5, 12.0],        # Alert pose - neutral
            [base_pos+0.05, 0.28, 0.68, 0.35, -1.3, 14.0], # Processing - slight right
            [base_pos+0.1, 0.25, 0.65, 0.5, -1.8, 15.0],   # Head tilt - left to balance
            [base_pos+0.2, 0.25, 0.65, 0.55, -0.9, 16.0],  # Contemplation - right to balance
            [base_pos+0.2, 0.35, 0.75, 0.2, -2.0, 13.0],   # Hand on chin - left extreme
            [base_pos+0.15, -0.5, 0.8, 0.4, -0.7, 17.0],   # Deep thought fold - right to balance
            [base_pos+0.2, -0.6, 0.9, 0.3, -1.9, 18.0],    # Deeper thought - left
            [base_pos+0.2, -0.7, 1.0, 0.2, -0.6, 19.0],    # Hold thought - right to balance
            [base_pos+0.25, -0.65, 0.95, 0.25, -1.7, 15.0], # Hmm movement - left
            [base_pos-0.15, -0.5, 0.8, 0.3, -0.8, 16.0],   # Shift position - right to balance
            [base_pos-0.1, -0.3, 0.7, 0.5, -2.1, 14.0],    # Look up - left extreme
            [base_pos, 0.1, 0.5, 0.7, -0.5, 20.0],         # Idea forming - right extreme to balance
            [base_pos+0.1, 0.0, 0.3, 1.1, -1.8, 17.0],     # Eureka - left
            [base_pos, -0.2, 0.2, 1.3, -0.7, 19.0],        # Full extension - right to balance
            [base_pos+0.2, -0.15, 0.15, 1.4, -1.6, 16.0],  # Excitement - left
            [base_pos, 0.1, 0.3, 1.0, -1.2, 15.0],         # Confirmation nod - slight right
            [base_pos-0.1, 0.2, 0.5, 0.7, -1.7, 14.0],     # Satisfied bounce - left
            [base_pos, 0.3, 0.7, 0.4, -1.5, 13.0],         # Final position - neutral
            [base_pos, 0.5, 1.3, 1.4, -1.5, 11.0],         # Return home 1 - neutral
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]        # Return home 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.83, 0.86, 0.53, 0.63, 1.08, 0.94, 0.56, 0.53, 0.53, 0.88, 0.86, 0.5, 0.47, 0.32, 0.38, 0.53, 0.71, 0.92, 0.64, 1.3]
        
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
            [base_pos, 0.6, 1.2, -0.2, -1.4, 13.0],        # Tired start - slight right
            [base_pos+0.1, 0.55, 1.15, -0.1, -1.8, 14.0],  # Initial movement - left to balance
            [base_pos+0.05, 0.65, 1.25, -0.3, -1.0, 15.0], # Build tension - right to balance
            [base_pos, 0.4, 1.0, 0.1, -2.0, 12.0],         # First attempt - left extreme
            [base_pos, -0.5, 1.0, 0.0, -0.5, 18.0],        # Bigger contraction - right extreme to balance
            [base_pos, -1.5, 1.8, 1.0, -2.3, 10.0],        # Compact fold - left extreme
            [base_pos, 0.2, 0.5, 0.6, -0.6, 19.0],         # Begin stretch - right to balance
            [base_pos+0.3, 0.0, 0.3, 1.0, -1.9, 16.0],     # Continue up - left
            [base_pos+0.5, -0.2, 0.2, 1.4, -0.7, 20.0],    # Maximum stretch - right to balance
            [base_pos+0.45, -0.25, 0.15, 1.45, -2.1, 11.0], # Hold wobble - left extreme
            [base_pos-0.5, -0.2, 0.2, 1.4, -0.5, 21.0],    # Stretch left - right extreme to balance
            [base_pos-0.45, -0.25, 0.15, 1.45, -1.8, 17.0], # Hold left - left
            [base_pos, 0.7, 1.4, -0.5, -0.8, 16.0],        # Bend down - right to balance
            [base_pos, 0.9, 1.7, -0.8, -2.2, 12.0],        # Maximum down - left extreme
            [base_pos+0.1, 0.85, 1.65, -0.75, -0.6, 18.0], # Hold with shake - right to balance
            [base_pos-0.1, 0.7, 1.5, -0.5, -1.7, 15.0],    # Start relaxing - left
            [base_pos+0.8, 0.5, 1.2, -0.2, -0.9, 17.0],    # Twist right - right
            [base_pos-0.8, 0.5, 1.2, -0.2, -1.9, 14.0],    # Counter twist - left to balance
            [base_pos, -1.0, 1.5, 1.0, -0.7, 19.0],        # Final fold - right
            [base_pos, 0.1, 0.6, 0.7, -1.6, 13.0],         # Begin relax - left to balance
            [base_pos, 0.2, 0.7, 0.5, -1.3, 14.0],         # Continue relax - slight left
            [base_pos, 0.3, 0.75, 0.35, -1.7, 15.0],       # Small bounce - left
            [base_pos+0.1, 0.35, 0.8, 0.3, -1.4, 13.0],    # Final settled - slight left
            [base_pos, 0.5, 1.3, 1.4, -1.5, 11.0],         # Return home 1 - neutral
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]        # Return home 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.77, 0.43, 0.53, 0.83, 0.67, 1.4, 0.53, 0.75, 0.7, 2.18, 0.76, 1.18, 0.75, 1.17, 0.89, 0.8, 0.47, 0.57, 0.84, 0.77, 0.86, 0.53, 1.08, 0.64, 1.3]
        
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
            [base_pos, 0.3, 0.7, 0.3, -1.5, 14.0],        # Ready - neutral
            [base_pos, 0.4, 0.8, 0.2, -1.2, 16.0],        # Bounce down - slight right
            [base_pos+0.3, 0.15, 0.5, 0.6, -1.8, 17.0],   # Bounce right - left to balance
            [base_pos+0.35, 0.1, 0.45, 0.65, -0.7, 19.0], # Overshoot - right extreme to balance
            [base_pos+0.3, 0.5, 0.9, 0.1, -2.0, 15.0],    # Down right - left extreme
            [base_pos-0.3, 0.15, 0.5, 0.6, -0.6, 20.0],   # Bounce left - right extreme to balance
            [base_pos-0.35, 0.1, 0.45, 0.65, -1.9, 18.0], # Overshoot - left
            [base_pos-0.3, 0.5, 0.9, 0.1, -0.8, 17.0],    # Down left - right to balance
            [base_pos, 0.3, 0.7, 0.7, -2.1, 13.0],        # Twist middle - left extreme
            [base_pos+0.1, 0.25, 0.65, 0.75, -0.5, 21.0], # Follow through - right extreme to balance
            [base_pos+0.5, 0.2, 0.6, 0.5, -1.7, 16.0],    # Spin right - left
            [base_pos-0.5, 0.2, 0.6, 0.5, -0.9, 18.0],    # Spin left - right to balance
            [base_pos, 0.6, 1.0, 0.0, -2.2, 12.0],        # Dip down - left extreme
            [base_pos, 0.1, 0.4, 0.9, -0.6, 20.0],        # Pop up - right extreme to balance
            [base_pos+0.2, 0.2, 0.5, 0.7, -1.8, 16.0],    # Finale pose - left
            [base_pos+0.2, 0.2, 0.5, 0.7, -1.5, 12.0],    # Hold finale - neutral
            [base_pos, 0.3, 0.7, 0.3, -1.5, 13.0],        # Return - neutral
            [base_pos, 0.5, 1.3, 1.4, -1.5, 11.0],        # Return home 1 - neutral
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]       # Return home 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [0.57, 0.38, 0.47, 0.32, 0.53, 0.4, 0.33, 0.47, 0.62, 0.29, 0.63, 0.56, 0.67, 0.3, 0.38, 1.0, 1.08, 0.64, 1.3]
        
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
        
        # Balanced roll variations within allowed range
        roll_start = random.uniform(-1.4, -1.0)
        roll_right = random.uniform(-0.8, -0.6)    # Right tilt
        roll_left = random.uniform(-2.2, -1.8)     # Left tilt to balance
        roll_center = random.uniform(-1.6, -1.4)   # Return toward center
        
        keyframes = [
            [base_var, shoulder_var, elbow_var, wrist_var, roll_start, 13.0],           # Idle position
            [base_var, shoulder_var, elbow_var, wrist_var, roll_right, 15.0],           # Right tilt
            [base_var + look_right, shoulder_var, elbow_var, wrist_var, roll_left, 16.0], # Look right with left tilt to balance
            [base_var, shoulder_var, elbow_var, wrist_var, roll_center, 14.0],          # Center
            [base_var - look_left, shoulder_var, elbow_var, wrist_var, roll_right, 15.0], # Look left with right tilt to balance
            [base_var + random.uniform(-0.05, 0.05), shoulder_var, elbow_var, wrist_var, -1.5, 12.0], # Final - neutral
            [0.0, 0.5, 1.3, 1.4, -1.5, 11.0],                                         # Return home 1 - neutral
            [0.0, -0.85, 1.3, 1.4, -1.5, 10.0]                                        # Return home 2 - neutral
        ]
        
        # Scaled durations (base duration * 10 / acceleration)
        durations = [1.54, 0.93, 0.63, 0.57, 0.67, 1.0, 0.64, 1.3]
        
        return keyframes, durations