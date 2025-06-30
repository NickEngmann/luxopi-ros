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
            "Anticipation", "Notice something", "Quick double-take", "Lean in carefully",
            "Surprised pullback", "Cautious approach", "Close inspection",
            "Tilt examination", "Final look", "Satisfied nod", "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_center = 0.0
        
        keyframes = [
            [base_center, 0.1, 0.8, 0.9, -1.4, 16.0],      # Anticipation - slight prep
            [base_center-0.1, 0.2, 0.5, 0.3, -0.9, 19.0],  # Notice something - quick look
            [base_center-0.05, -0.3, 0.3, 0.6, -2.1, 20.0], # Quick double-take
            [base_center+0.15, -0.5, 0.8, 0.8, -0.8, 17.0], # Lean in carefully
            [base_center, -0.2, 0.4, 0.5, -1.9, 21.0],      # Surprised pullback
            [base_center+0.2, -0.6, 1.0, 0.9, -0.85, 16.0], # Cautious approach
            [base_center+0.1, -0.8, 1.2, 1.1, -2.0, 14.0],  # Close inspection
            [base_center-0.15, -0.7, 1.1, 1.0, -1.0, 18.0], # Tilt examination
            [base_center, -0.4, 0.7, 0.7, -1.6, 19.0],      # Final look
            [base_center, -0.2, 0.9, 0.5, -1.5, 15.0],      # Satisfied nod
            [base_center, 0.2, 1.3, 1.5, -1.5, 15.0],       # Return home 1 - neutral
            [base_center, -0.65, 1.2, 1.0, -1.5, 10.0]      # Return home 2 - neutral
        ]
        
        # Snappier durations
        durations = [0.4, 0.6, 0.45, 0.5, 0.35, 0.65, 0.7, 0.45, 0.45, 0.5, 0.6, 0.9]
        
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
            "Alert", "Processing tilt", "Chin scratch pose", "Deep thought",
            "Ponder left", "Ponder right", "Hmm moment", "Building idea",
            "Pre-eureka", "Eureka!", "Excitement bounce", "Pride pose",
            "Satisfied", "Return home 1", "Return home 2"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.2, 0.7, 0.5, -1.5, 15.0],        # Alert
            [base_pos+0.05, -0.1, 0.5, 0.7, -1.2, 17.0],  # Processing tilt
            [base_pos, -0.4, 0.9, 1.0, -1.8, 14.0],       # Chin scratch pose
            [base_pos-0.1, -0.6, 1.1, 1.2, -0.9, 12.0],   # Deep thought
            [base_pos+0.2, -0.5, 1.0, 1.1, -2.0, 16.0],   # Ponder left
            [base_pos-0.2, -0.5, 1.0, 1.1, -1.0, 16.0],   # Ponder right
            [base_pos, -0.7, 1.2, 1.3, -1.5, 11.0],       # Hmm moment
            [base_pos, -0.4, 0.8, 0.9, -1.3, 18.0],       # Building idea
            [base_pos, -0.2, 0.5, 0.6, -1.6, 20.0],       # Pre-eureka
            [base_pos, -0.1, 0.2, 0.3, -1.5, 22.0],       # Eureka! - quick up
            [base_pos, 0.1, 0.4, 0.2, -1.4, 21.0],        # Excitement bounce
            [base_pos, -0.3, 0.6, 0.8, -1.6, 17.0],       # Pride pose
            [base_pos, 0.0, 0.8, 0.6, -1.5, 15.0],        # Satisfied
            [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0],        # Return home 1
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0]       # Return home 2
        ]
        
        # Faster thinking
        durations = [0.6, 0.5, 0.7, 0.8, 0.6, 0.6, 0.85, 0.45, 0.35, 0.35, 0.35, 0.45, 0.6, 0.6, 0.9]
        
        return keyframes, durations


class StretchingAnimation(AnimationPlugin):
    """Make the arm perform a satisfying stretch."""
    
    @property
    def name(self) -> str:
        return "stretch"
    
    @property
    def description(self) -> str:
        return "Satisfying full-body stretch with compact-to-extend motion"
    
    def get_category(self) -> str:
        return "action"
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, 0.3, 1.4, 0.8, -1.5, 13.0],         # Start tired
            [base_pos, 0.2, 1.5, 1.0, -1.6, 14.0],         # Begin compression
            [base_pos, -0.8, 1.8, 1.2, -1.4, 12.0],        # Compress more
            [base_pos, -1.0, 2.0, 1.0, -1.45, 10.0],       # Near max compact
            [base_pos, -0.9, 1.6, 0.8, -1.5, 11.0],        # Slight release
            [base_pos, -0.7, 1.2, 0.6, -1.4, 13.0],        # Build tension
            [base_pos, -0.4, 0.8, 0.4, -1.45, 16.0],       # Begin stretch
            [base_pos, -0.2, 0.4, 0.2, -1.45, 19.0],       # Continue up
            [base_pos, -0.1, 0.2, 0.1, -1.45, 21.0],       # Almost peak
            [base_pos, 0, 0, 0, -1.45, 8.0],               # Full stretch - straight up!
            [base_pos, 0, 0.1, 0.05, -1.5, 9.0],           # Hold with wobble
            [base_pos, -0.05, 0.15, 0.1, -1.4, 10.0],      # Slight wobble
            [base_pos, -0.2, 0.4, 0.3, -1.5, 14.0],        # Begin descent
            [base_pos, -0.4, 0.7, 0.6, -1.6, 16.0],        # Continue down
            [base_pos, -0.5, 1.0, 0.8, -1.5, 15.0],        # Lower more
            [base_pos, -0.3, 0.8, 0.7, -1.4, 17.0],        # Small bounce
            [base_pos, -0.1, 0.6, 0.5, -1.5, 18.0],        # Another bounce
            [base_pos, 0.1, 0.7, 0.4, -1.5, 16.0],         # Settling
            [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0],         # Return home 1
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0]        # Return home 2
        ]
        
        # Faster stretch
        durations = [0.7, 0.7, 0.8, 0.9, 0.85, 0.7, 0.6, 0.45, 0.35, 1.2, 0.9, 0.8, 0.7, 0.6, 0.6, 0.5, 0.45, 0.6, 0.6, 0.9]
        
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
            [base_pos, 0.2, 0.7, 0.4, -1.5, 17.0],        # Ready
            [base_pos+0.3, 0.3, 0.8, 0.3, -1.2, 20.0],    # Right bounce
            [base_pos+0.4, -0.2, 0.5, 0.6, -1.8, 21.0],   # Right high
            [base_pos+0.2, 0.1, 0.9, 0.5, -0.9, 19.0],    # Right low
            [base_pos-0.3, 0.3, 0.8, 0.3, -2.1, 20.0],    # Left bounce
            [base_pos-0.4, -0.2, 0.5, 0.6, -0.8, 21.0],   # Left high
            [base_pos-0.2, 0.1, 0.9, 0.5, -1.9, 19.0],    # Left low
            [base_pos, -0.4, 0.6, 0.7, -1.5, 22.0],       # Center pop
            [base_pos+0.2, -0.3, 0.7, 0.8, -1.0, 18.0],   # Twist right
            [base_pos-0.2, -0.3, 0.7, 0.8, -2.0, 18.0],   # Twist left
            [base_pos, 0.4, 1.2, 0.2, -1.5, 15.0],        # Dip down
            [base_pos, -0.5, 0.3, 0.9, -1.5, 22.0],       # Pop up
            [base_pos+0.1, -0.2, 0.5, 0.6, -1.6, 20.0],   # Finale pose
            [base_pos, 0.0, 0.7, 0.5, -1.5, 16.0],        # Cool down
            [base_pos, 0.2, 1.3, 1.5, -1.5, 15.0],        # Return home 1
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0]       # Return home 2
        ]
        
        # Snappy dance timing
        durations = [0.45, 0.35, 0.5, 0.35, 0.6, 0.5, 0.35, 0.35, 0.45, 0.45, 0.6, 0.65, 0.35, 0.6, 0.6, 0.9]
        
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
        # Small variations around home 2 position
        base_var = random.uniform(-0.05, 0.05)
        shoulder_var = random.uniform(-0.7, -0.6)
        elbow_var = random.uniform(1.1, 1.3)
        wrist_var = random.uniform(0.9, 1.1)
        
        # Small look amounts
        look_right = random.uniform(0.05, 0.1)
        look_left = random.uniform(0.05, 0.1)
        
        # Hand variations within safe range
        hand_idle = random.uniform(-1.6, -1.4)
        hand_right = random.uniform(-1.3, -1.1)
        hand_left = random.uniform(-1.7, -1.9)
        
        keyframes = [
            [base_var, shoulder_var, elbow_var, wrist_var, hand_idle, 13.0],
            [base_var + look_right, shoulder_var + 0.05, elbow_var - 0.05, wrist_var, hand_right, 16.0],
            [base_var, shoulder_var - 0.03, elbow_var + 0.03, wrist_var + 0.05, -1.5, 15.0],
            [base_var - look_left, shoulder_var, elbow_var, wrist_var - 0.05, hand_left, 16.0],
            [base_var, shoulder_var, elbow_var, wrist_var, -1.5, 14.0],
            [0.0, -0.65, 1.2, 1.0, -1.5, 10.0]  # Return home 2
        ]
        
        # Gentle, relaxed timing
        durations = [1.2, 0.7, 0.6, 0.7, 0.85, 0.9]
        
        return keyframes, durations