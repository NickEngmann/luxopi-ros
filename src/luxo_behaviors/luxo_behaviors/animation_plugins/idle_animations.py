#!/usr/bin/env python3
"""
Idle animation plugins for the LuxoPi system.
These animations provide lifelike idle behaviors with more expressive movements.
"""

import random
import math
from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class GentleSwayAnimation(AnimationPlugin):
    """Gentle swaying motion like a lamp in a breeze."""
    
    @property
    def name(self) -> str:
        return "gentle_sway"
    
    @property
    def description(self) -> str:
        return "Gentle swaying motion as if moved by air currents"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Rest", "Build sway", "Sway right", "Peak right", "Return center", 
                "Sway left", "Peak left", "Settle", "Final rest", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        # More pronounced swaying with natural build-up
        sway_amount = random.uniform(0.3, 0.45)
        
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],                          # Start at home
            [base_pos + sway_amount*0.3, -0.78, 1.25, 1.38, 0.0],      # Build sway
            [base_pos + sway_amount*0.7, -0.72, 1.22, 1.45, 0.0],      # Continue right
            [base_pos + sway_amount, -0.7, 1.2, 1.5, 0.0],             # Peak right
            [base_pos + sway_amount*0.2, -0.8, 1.28, 1.42, 0.0],       # Return center
            [base_pos - sway_amount*0.7, -0.75, 1.24, 1.35, 0.0],      # Sway left
            [base_pos - sway_amount, -0.72, 1.22, 1.32, 0.0],          # Peak left
            [base_pos - sway_amount*0.3, -0.82, 1.28, 1.38, 0.0],      # Begin settle
            [base_pos, -0.84, 1.29, 1.39, 0.0],                        # Almost home
            [base_pos, -0.85, 1.3, 1.4, 0.0]                           # End at home
        ]
        
        # Natural timing with acceleration/deceleration
        durations = [0.9, 0.8, 0.7, 0.5, 0.9, 0.8, 0.5, 0.7, 0.7, 1.0]
        
        return keyframes, durations


class CuriousExplorationAnimation(AnimationPlugin):
    """More pronounced curious exploration of the environment."""
    
    @property
    def name(self) -> str:
        return "curious_exploration"
    
    @property
    def description(self) -> str:
        return "Active exploration of surroundings with curiosity"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Alert", "Lean forward", "Investigate left", "Examine", 
                "Sweep right", "Inspect", "Pull back", "Consider", "Return home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = random.uniform(-0.15, 0.15)
        
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],                    # Start at home
            [base_pos, -0.65, 1.15, 1.25, 0.0],                  # Alert posture
            [base_pos, -0.5, 1.0, 1.1, 0.0],                     # Lean forward 
            [base_pos - 0.4, -0.45, 0.95, 1.05, 0.0],            # Look left
            [base_pos - 0.35, -0.55, 1.05, 1.15, 0.0],           # Examine closer
            [base_pos + 0.5, -0.5, 1.0, 1.2, 0.0],               # Sweep to right
            [base_pos + 0.45, -0.6, 1.1, 1.3, 0.0],              # Inspect right
            [base_pos + 0.1, -0.75, 1.2, 1.35, 0.0],             # Pull back
            [base_pos, -0.8, 1.25, 1.38, 0.0],                   # Consider
            [base_pos, -0.85, 1.3, 1.4, 0.0]                     # Return home
        ]
        
        durations = [0.5, 0.7, 0.8, 0.9, 0.6, 1.0, 0.7, 0.8, 0.7, 1.0]
        
        return keyframes, durations


class BreathingAnimation(AnimationPlugin):
    """Natural breathing-like motion with expansion and contraction."""
    
    @property
    def name(self) -> str:
        return "breathing"
    
    @property
    def description(self) -> str:
        return "Rhythmic breathing motion with natural timing"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Rest", "Begin inhale", "Deep inhale", "Hold breath", 
                "Begin exhale", "Deep exhale", "Pause", "Final settle", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        # More pronounced vertical movement
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],              # Rest position
            [base_pos, -0.95, 1.35, 1.5, 0.0],             # Begin inhale
            [base_pos, -1.05, 1.4, 1.55, 0.0],             # Deep inhale (expanded)
            [base_pos, -1.02, 1.38, 1.53, 0.0],            # Hold breath
            [base_pos, -0.9, 1.32, 1.45, 0.0],             # Begin exhale
            [base_pos, -0.75, 1.25, 1.35, 0.0],            # Deep exhale (compressed)
            [base_pos, -0.78, 1.27, 1.37, 0.0],            # Pause
            [base_pos, -0.83, 1.29, 1.39, 0.0],            # Final settle
            [base_pos, -0.85, 1.3, 1.4, 0.0]               # Return home
        ]
        
        # Natural breathing rhythm
        durations = [0.75, 0.8, 1.2, 0.8, 0.9, 1.0, 0.8, 0.7, 1.0]
        
        return keyframes, durations


class AttentiveListeningAnimation(AnimationPlugin):
    """Head tilts and movements as if listening attentively."""
    
    @property
    def name(self) -> str:
        return "attentive_listening"
    
    @property
    def description(self) -> str:
        return "Attentive listening movements with head tilts"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Perk up", "Tilt left", "Focus", "Tilt right", 
                "Lean in", "Process", "Nod slightly", "Return", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],                  # Home
            [base_pos, -0.7, 1.2, 1.3, 0.0],                   # Perk up (alert)
            [base_pos - 0.25, -0.68, 1.18, 1.25, 0.0],         # Tilt head left
            [base_pos - 0.2, -0.65, 1.15, 1.2, 0.0],           # Focus intently
            [base_pos + 0.3, -0.68, 1.18, 1.28, 0.0],          # Tilt head right
            [base_pos + 0.1, -0.6, 1.1, 1.15, 0.0],            # Lean in slightly
            [base_pos, -0.72, 1.22, 1.32, 0.0],                # Process/think
            [base_pos, -0.75, 1.25, 1.35, 0.0],                # Small nod
            [base_pos, -0.82, 1.28, 1.38, 0.0],                # Begin return
            [base_pos, -0.85, 1.3, 1.4, 0.0]                   # Home
        ]
        
        durations = [0.75, 0.6, 0.8, 0.7, 0.9, 0.8, 1.0, 0.8, 0.8, 1.0]
        
        return keyframes, durations


class PlayfulBobAnimation(AnimationPlugin):
    """Playful bobbing motion with personality."""
    
    @property
    def name(self) -> str:
        return "playful_bob"
    
    @property
    def description(self) -> str:
        return "Playful bobbing and bouncing idle motion"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Dip down", "Bob up", "Wiggle left", "Center bounce", 
                "Wiggle right", "Double bob", "Settle bounce", "Rest", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        # Playful movements with more energy
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],                    # Home
            [base_pos, -0.7, 1.4, 1.2, 0.0],                     # Dip down
            [base_pos, -1.0, 1.15, 1.5, 0.0],                    # Bob up high
            [base_pos - 0.3, -0.9, 1.2, 1.45, 0.0],              # Wiggle left
            [base_pos, -0.8, 1.25, 1.35, 0.0],                   # Center bounce
            [base_pos + 0.3, -0.9, 1.2, 1.45, 0.0],              # Wiggle right
            [base_pos, -0.75, 1.35, 1.25, 0.0],                  # Quick dip
            [base_pos, -0.88, 1.22, 1.42, 0.0],                  # Bounce up
            [base_pos, -0.83, 1.28, 1.38, 0.0],                  # Settle
            [base_pos, -0.85, 1.3, 1.4, 0.0]                     # Home
        ]
        
        # Bouncy timing
        durations = [0.5, 0.4, 0.5, 0.6, 0.4, 0.6, 0.35, 0.8, 0.8, 1.0]
        
        return keyframes, durations


class ScanningWatchAnimation(AnimationPlugin):
    """Watchful scanning of the environment."""
    
    @property
    def name(self) -> str:
        return "scanning_watch"
    
    @property
    def description(self) -> str:
        return "Systematic scanning of surroundings"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Raise head", "Scan far left", "Scan left", "Scan center",
                "Scan right", "Scan far right", "Return center", "Lower", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Systematic scanning pattern
        scan_height = -0.7  # Higher position for scanning
        
        keyframes = [
            [0.0, -0.85, 1.3, 1.4, 0.0],                        # Home
            [0.0, scan_height, 1.15, 1.3, 0.0],                 # Raise to scan height
            [-0.6, scan_height, 1.15, 1.25, 0.0],               # Far left
            [-0.3, scan_height + 0.05, 1.17, 1.28, 0.0],        # Left
            [0.0, scan_height, 1.15, 1.3, 0.0],                 # Center
            [0.3, scan_height + 0.05, 1.17, 1.32, 0.0],         # Right
            [0.6, scan_height, 1.15, 1.35, 0.0],                # Far right
            [0.0, scan_height + 0.1, 1.2, 1.3, 0.0],            # Return center
            [0.0, -0.82, 1.27, 1.37, 0.0],                      # Lower
            [0.0, -0.85, 1.3, 1.4, 0.0]                         # Home
        ]
        
        # Smooth scanning motion
        durations = [0.5, 0.7, 0.8, 0.6, 0.5, 0.6, 0.8, 0.7, 0.8, 1.0]
        
        return keyframes, durations


class SettlingAdjustAnimation(AnimationPlugin):
    """Natural settling movements with micro-adjustments."""
    
    @property
    def name(self) -> str:
        return "settling_adjust"
    
    @property
    def description(self) -> str:
        return "Natural settling adjustments and repositioning"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Shift weight", "Adjust base", "Settle shoulder",
                "Micro adjust", "Counter shift", "Find balance", "Final settle", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Random micro-adjustments for natural feel
        base_adj = random.uniform(-0.2, 0.2)
        shoulder_adj = random.uniform(-0.15, 0.15)
        
        keyframes = [
            [base_adj, -0.85, 1.3, 1.4, 0.0],                              # Home
            [base_adj * 0.5, -0.82, 1.32, 1.38, 0.0],                 # Shift weight
            [base_adj, -0.88, 1.28, 1.42, 0.0],                       # Adjust base
            [base_adj * 0.7, -0.85 + shoulder_adj, 1.3, 1.4, 0.0],    # Settle shoulder
            [base_adj * 0.3, -0.83, 1.31, 1.39, 0.0],                 # Micro adjust
            [-base_adj * 0.4, -0.87, 1.29, 1.41, 0.0],                # Counter shift
            [base_adj, -0.84, 1.3, 1.4, 0.0],                              # Find balance
            [base_adj, -0.85, 1.3, 1.4, 0.0],                              # Final settle
            [base_adj, -0.85, 1.3, 1.4, 0.0]                               # Home
        ]
        
        # Natural settling rhythm
        durations = [0.5, 0.7, 0.6, 0.8, 0.5, 0.6, 0.7, 0.8, 1.0]
        
        return keyframes, durations


class DreamyDriftAnimation(AnimationPlugin):
    """Slow, dreamy drifting movements."""
    
    @property
    def name(self) -> str:
        return "dreamy_drift"
    
    @property
    def description(self) -> str:
        return "Slow, dreamy drifting as if lost in thought"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Begin drift", "Float left", "Drift up", "Wander right",
                "Gentle sway", "Float down", "Return drift", "Settle", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        # Smooth, flowing movements
        drift_radius = 0.35
        
        keyframes = [
            [0.0, -0.85, 1.3, 1.4, 0.0],                           # Home
            [0.1, -0.88, 1.32, 1.42, 0.0],                         # Begin drift
            [-drift_radius, -0.9, 1.35, 1.45, 0.0],                # Float left
            [-drift_radius * 0.7, -0.95, 1.38, 1.48, 0.0],         # Drift up
            [drift_radius * 0.8, -0.92, 1.36, 1.46, 0.0],          # Wander right
            [drift_radius * 0.5, -0.85, 1.32, 1.42, 0.0],          # Gentle sway
            [0.15, -0.78, 1.28, 1.38, 0.0],                        # Float down
            [-0.1, -0.82, 1.29, 1.39, 0.0],                        # Return drift
            [0.0, -0.84, 1.3, 1.4, 0.0],                           # Settle
            [0.0, -0.85, 1.3, 1.4, 0.0]                            # Home
        ]
        
        # Slow, dreamy timing
        durations = [0.7, 1.0, 1.2, 0.9, 1.1, 0.8, 1.0, 0.9, 0.6, 1.0]
        
        return keyframes, durations