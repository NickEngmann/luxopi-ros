#!/usr/bin/env python3
"""
Idle animation plugins for the LuxoPi system.
Enhanced with highly expressive, human-like movements that make the robot appear sentient.
"""

import random
import math
from typing import List, Tuple, Optional
from luxo_behaviors.animation_plugin_base import AnimationPlugin


class GentleSwayAnimation(AnimationPlugin):
    """Natural human swaying with micro-movements and breathing integration."""
    
    @property
    def name(self) -> str:
        return "gentle_sway"
    
    @property
    def description(self) -> str:
        return "Natural human-like swaying with subtle breathing and micro-adjustments"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Start", "Inhale begin", "Shift weight right", "Lean into sway", 
                "Micro-adjust shoulder", "Full sway right", "Hold with breath", 
                "Exhale return", "Through center", "Shift weight left", 
                "Micro head tilt", "Full sway left", "Hold and settle",
                "Gentle return", "Balance check", "Settle", "Home 2"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        sway_amount = random.uniform(0.45, 0.65)
        breath_lift = random.uniform(0.1, 0.15)
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00],                          # Start at home 2
            [base_pos, -0.88, 1.32, 1.42, -1.6, 10.5, 1.00],                        # Subtle inhale - antenna lifts slightly
            [base_pos + sway_amount*0.15, -0.78, 1.25, 1.38, -1.2, 11.0, 0.40],     # Begin shift - antenna follows
            [base_pos + sway_amount*0.4, -0.7, 1.18, 1.45, -1.8, 10.0, 1.00],       # Lean into movement
            [base_pos + sway_amount*0.45, -0.68 + breath_lift, 1.16, 1.47, -0.9, 13.5, 1.00], # Micro shoulder adjust
            [base_pos + sway_amount*0.85, -0.6, 1.08, 1.52, -2.1, 11.5, 1.00],      # Near full sway - antenna opposite
            [base_pos + sway_amount, -0.58 - breath_lift, 1.05, 1.54, -0.8, 10.0, 1.00], # Full sway with breath
            [base_pos + sway_amount*0.7, -0.65, 1.12, 1.45, -1.9, 11.0, 1.00],      # Begin exhale return
            [base_pos + sway_amount*0.2, -0.72, 1.2, 1.38, -1.1, 12.0, 1.00],       # Through center
            [base_pos - sway_amount*0.15, -0.76, 1.22, 1.36, -2.0, 10.5, 1.40],     # Begin left shift
            [base_pos - sway_amount*0.5, -0.73, 1.18, 1.4, -0.85, 14.0, 1.00],      # Head tilt moment
            [base_pos - sway_amount*0.9, -0.62, 1.1, 1.48, -1.7, 11.0, 1.40],       # Near full left
            [base_pos - sway_amount, -0.6 + breath_lift*0.5, 1.08, 1.46, -0.9, 10.0, 0.60], # Full left with settle
            [base_pos - sway_amount*0.4, -0.74, 1.2, 1.4, -1.6, 11.5, 1.00],        # Gentle return
            [base_pos - 0.05, -0.8, 1.26, 1.41, -1.3, 12.5, 1.00],                  # Balance check
            [base_pos, -0.8, 1.29, 1.4, -1.5, 11.0, 1.00],                         # Near home
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00]                           # Home 2
        ]
        
        # Natural timing, slightly faster
        durations = [0.6, 0.8, 0.7, 0.95, 0.55, 0.7, 0.95, 0.7, 0.6, 0.8, 0.55, 0.7, 0.95, 0.7, 0.6, 0.7, 0.6]
        
        return keyframes, durations


class CuriousExplorationAnimation(AnimationPlugin):
    """Animated exploration with human curiosity, double-takes, and focused attention."""
    
    @property
    def name(self) -> str:
        return "curious_exploration"
    
    @property
    def description(self) -> str:
        return "Lively exploration with squints, double-takes, and 'aha' moments"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Something caught eye", "Quick glance", "Wait what?", 
                "Double-take lean", "Squint examine", "Head cock confused",
                "Lean way in", "Aha moment", "Pull back process", "Look up thinking",
                "Glance right compare", "Nod understanding", "Satisfied exhale", 
                "Return posture", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = random.uniform(-0.25, 0.25)
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 13.0, 1.00],                    # Start at home 2
            [base_pos - 0.1, -0.65, 1.15, 1.3, -1.2, 16.0, 2.40],             # Something catches attention
            [base_pos - 0.55, -0.55, 1.05, 1.2, -1.9, 19.0, 1.40],            # Quick glance left
            [base_pos - 0.5, -0.6, 1.1, 1.25, -0.85, 15.0, 1.00],              # Pause - wait what?
            [base_pos - 0.45, -0.45, 0.9, 1.05, -2.0, 17.5, 1.00],            # Double-take lean forward
            [base_pos - 0.42, -0.4, 0.85, 1.0, -0.8, 14.5, 1.00],             # Squint for detail
            [base_pos - 0.48, -0.42, 0.87, 1.08, -1.8, 16.5, 1.00],           # Head tilt confused
            [base_pos - 0.4, -0.25, 0.65, 0.85, -0.9, 12.0, 1.00],            # Lean way in to inspect
            [base_pos - 0.35, -0.3, 0.7, 0.95, -2.1, 20.0, 1.00],             # Aha! I see it
            [base_pos - 0.2, -0.65, 1.15, 1.4, -0.75, 15.5, 1.00],             # Pull back to process
            [base_pos, -0.95, 0.85, 1.65, -1.7, 11.5, 1.60],                  # Look up thinking about it
            [base_pos + 0.65, -0.5, 1.05, 1.35, -0.85, 18.0, 1.80],            # Glance right to compare
            [base_pos + 0.2, -0.6, 1.12, 1.3, -1.9, 16.0, 1.00],              # Nod - I understand now
            [base_pos, -0.75, 1.23, 1.37, -1.1, 13.5, 1.00],                  # Satisfied exhale
            [base_pos, -0.82, 1.28, 1.39, -1.6, 12.0, 0.60],                  # Return to rest
            [base_pos, -0.65, 1.2, 1.0, -1.5, 13.0, 1.00]                     # Home 2
        ]
        
        # Quick, curious exploration
        durations = [0.6, 0.4, 0.6, 0.55, 0.45, 0.55, 0.45, 0.6, 0.35, 0.55, 0.7, 0.7, 0.45, 0.55, 0.6, 0.6]
        
        return keyframes, durations


class BreathingAnimation(AnimationPlugin):
    """Deep meditative breathing with full body expansion and subtle movements."""
    
    @property
    def name(self) -> str:
        return "breathing"
    
    @property
    def description(self) -> str:
        return "Deep yogic breathing with chest expansion and micro-movements"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Rest", "Prepare mind", "Begin inhale", "Deep expansion", 
                "Full breath", "Peak hold", "Slight waver", "Control exhale",
                "Release down", "Deep exhale", "Bottom pause", "Micro inhale",
                "Final settle", "Peace", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        sway = random.uniform(-0.05, 0.05)
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.5, 0.60],                    # Rest position
            [base_pos, -0.88, 1.32, 1.43, -1.3, 10.0, 1.00],                  # Mental preparation
            [base_pos + sway, -0.95, 1.34, 1.5, -1.8, 10.0, 1.00],            # Begin deep inhale
            [base_pos, -1.05, 1.38, 1.6, -0.9, 10.5, 1.00],                   # Chest expanding
            [base_pos - sway, -1.1, 1.42, 1.68, -2.0, 10.0, 1.00],            # Full expansion (at limit)
            [base_pos, -1.08, 1.41, 1.66, -0.8, 10.0, 3.14],                  # Hold at peak
            [base_pos + sway*0.5, -1.06, 1.4, 1.64, -1.7, 11.0, 1.00],        # Slight waver in hold
            [base_pos, -1.0, 1.36, 1.55, -1.1, 10.5, 1.00],                   # Begin controlled exhale
            [base_pos - sway, -0.85, 1.3, 1.45, -1.9, 10.0, 0.40],            # Releasing downward
            [base_pos, -0.65, 1.2, 1.25, -0.85, 10.5, 0.40],                   # Deep exhale compression
            [base_pos, -0.62, 1.18, 1.22, -2.2, 10.0, 1.00],                  # Bottom of breath pause
            [base_pos, -0.72, 1.24, 1.32, -0.75, 11.5, 1.00],                  # Small recovery inhale
            [base_pos, -0.8, 1.28, 1.38, -1.6, 11.0, 1.00],                   # Settling
            [base_pos, -0.84, 1.2, 1.39, -1.3, 10.5, 1.00],                   # Peaceful state
            [base_pos, -0.65, 1.2, 1.0, -1.5, 10.0, 1.00]                     # Home 2
        ]
        
        # Deliberate breathing, slightly faster
        durations = [0.8, 0.95, 0.95, 0.8, 0.95, 1.6, 0.7, 0.8, 0.95, 0.8, 0.95, 0.7, 0.7, 0.8, 0.95]
        
        return keyframes, durations


class AttentiveListeningAnimation(AnimationPlugin):
    """Active listening with micro-expressions, subtle nods, and engagement cues."""
    
    @property
    def name(self) -> str:
        return "attentive_listening"
    
    @property
    def description(self) -> str:
        return "Engaged listening with eyebrow raises, micro-nods, and 'mm-hmm' gestures"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Attention shift", "Eyebrow raise", "Lean in curious", 
                "Micro nod 1", "Head tilt left", "Processing", "Micro nod 2",
                "Shift weight", "Head tilt right", "Deep nod", "Pull back think",
                "Understanding dawn", "Agreement gesture", "Settle satisfied", 
                "Home 2"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.5, 1.00],                    # Home 2
            [base_pos, -0.7, 1.2, 1.35, -1.3, 14.0, 2.40],                    # Shift to attention
            [base_pos, -0.65, 1.15, 1.3, -1.8, 15.5, 0.60],                   # Eyebrow raise interest
            [base_pos - 0.15, -0.5, 1.0, 1.15, -0.9, 13.0, 2.00],             # Lean in curious
            [base_pos - 0.12, -0.52, 1.02, 1.12, -2.0, 16.0, 1.00],           # Micro nod understanding
            [base_pos - 0.35, -0.55, 1.05, 1.2, -0.8, 14.5, 2.00],            # Head tilt questioning
            [base_pos - 0.32, -0.62, 1.12, 1.28, -1.9, 13.5, 1.00],           # Processing information
            [base_pos - 0.3, -0.58, 1.08, 1.24, -1.0, 15.0, 1.00],            # Another micro nod
            [base_pos + 0.1, -0.6, 1.1, 1.3, -1.7, 14.0, 1.00],               # Shift weight/position
            [base_pos + 0.38, -0.58, 1.08, 1.32, -0.85, 14.5, 1.00],           # Head tilt other way
            [base_pos + 0.15, -0.48, 0.98, 1.18, -2.1, 17.0, 1.00],           # Deep understanding nod
            [base_pos, -0.72, 1.22, 1.42, -0.75, 12.0, 1.60],                  # Pull back to think
            [base_pos, -0.68, 1.18, 1.38, -1.8, 13.5, 1.00],                  # Understanding dawns
            [base_pos, -0.55, 1.05, 1.25, -1.2, 15.0, 1.00],                  # Agreement gesture forward
            [base_pos, -0.78, 1.26, 1.38, -1.6, 11.5, 0.60],                  # Settle back satisfied
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.5, 1.00]                     # Home 2
        ]
        
        # Conversational pace
        durations = [0.6, 0.55, 0.55, 0.6, 0.4, 0.55, 0.55, 0.55, 0.55, 0.55, 0.45, 0.6, 0.55, 0.55, 0.7, 0.6]
        
        return keyframes, durations


class PlayfulBobAnimation(AnimationPlugin):
    """Energetic, bouncy movements with personality and dance-like rhythm."""
    
    @property
    def name(self) -> str:
        return "playful_bob"
    
    @property
    def description(self) -> str:
        return "Bouncy dance-like movements with hip sways and shoulder rolls"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Anticipation dip", "Spring loaded", "Burst up", 
                "Air time", "Land soft", "Hip sway left", "Shoulder shimmy",
                "Hip sway right", "Double bounce prep", "Quick pop 1", "Quick pop 2",
                "Wiggle celebration", "Cool down bounce", "Happy settle", 
                "Home 2"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        energy = random.uniform(0.8, 1.0)  # Reduced max stretch
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 14.0, 1.00],                          # Home 2
            [base_pos, -0.6, 1.55, 0.95, -1.2, 18.0, 1.00],                         # Deep anticipation - back
            [base_pos + 0.05, -0.55, 1.6, 0.9, -1.9, 20.0, 1.00],                   # Coiled spring - back
            [base_pos - 0.1, -1.0 * energy, 0.85, 1.75, -0.8, 22.5, 1.00],          # Explosive jump (at limit)
            [base_pos + 0.15, -0.95 * energy, 0.8, 1.8, -2.2, 22.0, 3.14],          # Peak of jump
            [base_pos, -0.45, 1.45, 0.85, -0.85, 16.0, 1.00],                        # Soft landing - back
            [base_pos - 0.45, -0.85, 1.15, 1.55, -1.8, 17.5, 1.40],                 # Hip sway left - back
            [base_pos - 0.4, -0.9, 1.1, 1.5, -0.9, 18.5, 1.00],                     # Shoulder shimmy - back
            [base_pos + 0.45, -0.85, 1.15, 1.55, -2.0, 17.0, 1.80],                 # Hip sway right - back
            [base_pos, -0.65, 1.35, 1.1, -0.75, 19.0, 2.20],                         # Prep double bounce - back
            [base_pos + 0.1, -1.0, 1.0, 1.6, -1.7, 21.0, 2.80],                     # Quick pop up - far back
            [base_pos - 0.1, -0.7, 1.3, 1.2, -1.0, 20.5, 1.00],                     # Quick drop - back
            [base_pos + 0.25, -0.82, 1.18, 1.42, -1.9, 18.0, 1.80],                 # Wiggle right - back
            [base_pos - 0.25, -0.85, 1.2, 1.45, -0.85, 17.5, 1.40],                  # And left - back
            [base_pos, -0.9, 1.25, 1.38, -1.6, 13.0, 3.14],                         # Happy settling - back
            [base_pos, -0.65, 1.2, 1.0, -1.5, 14.0, 1.00]                           # Home 2
        ]
        
        # Fast, bouncy rhythm
        durations = [0.55, 0.45, 0.4, 0.55, 0.35, 0.6, 0.6, 0.4, 0.7, 0.4, 0.45, 0.45, 0.45, 0.45, 0.6, 0.55]
        
        return keyframes, durations


class ScanningWatchAnimation(AnimationPlugin):
    """Alert scanning with quick focus changes and threat assessment behaviors."""
    
    @property
    def name(self) -> str:
        return "scanning_watch"
    
    @property
    def description(self) -> str:
        return "Vigilant scanning with snap-focus and evaluation pauses"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Alert rise", "Snap left", "Quick eval", "Scan sweep",
                "Pause suspicious", "Continue scan", "Snap right", "Lock target",
                "Zoom focus", "Threat assess", "Relax false alarm", "Final check",
                "All clear", "Return rest", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        alert_height = -0.6
        
        keyframes = [
            [0.0, -0.65, 1.2, 1.0, -1.5, 13.0, 1.00],                          # Home 2
            [0.0, alert_height, 1.0, 1.3, -1.2, 16.0, 2.40],                   # Rise to alert
            [-0.75, alert_height - 0.05, 0.95, 1.2, -1.9, 21.0, 1.40],        # Snap look left
            [-0.7, alert_height, 1.0, 1.25, -0.85, 17.0, 1.00],                 # Quick evaluation
            [-0.35, alert_height + 0.05, 1.05, 1.3, -1.7, 15.0, 1.00],         # Scanning across
            [0.0, alert_height - 0.1, 0.95, 1.35, -1.0, 14.0, 1.00],          # Pause - something?
            [0.35, alert_height, 1.02, 1.38, -1.8, 15.5, 1.00],                # Continue scanning
            [0.8, alert_height - 0.05, 0.95, 1.42, -0.8, 20.5, 1.80],         # Snap look right
            [0.75, alert_height - 0.15, 0.9, 1.38, -2.0, 18.0, 1.00],         # Lock on target
            [0.72, alert_height - 0.2, 0.85, 1.35, -0.9, 16.5, 1.00],         # Zoom in focus
            [0.7, alert_height - 0.18, 0.87, 1.37, -1.8, 14.5, 1.00],         # Assess threat level
            [0.4, alert_height + 0.1, 1.1, 1.4, -1.1, 12.5, 0.60],            # Relax - false alarm
            [-0.3, alert_height, 1.05, 1.35, -1.7, 15.0, 1.00],               # One final check
            [0.0, -0.7, 1.15, 1.38, -1.3, 13.5, 0.40],                        # All clear, lowering
            [0.0, -0.82, 1.2, 1.39, -1.6, 12.0, 0.60],                        # Return to rest
            [0.0, -0.65, 1.2, 1.0, -1.5, 13.0, 1.00]                          # Home 2
        ]
        
        # Quick, alert scanning
        durations = [0.4, 0.45, 0.6, 0.4, 0.55, 0.55, 0.45, 0.6, 0.4, 0.45, 0.55, 0.6, 0.6, 0.55, 0.6, 0.6]
        
        return keyframes, durations


class SettlingAdjustAnimation(AnimationPlugin):
    """Fidgety comfort-seeking with multiple attempts to find the right position."""
    
    @property
    def name(self) -> str:
        return "settling_adjust"
    
    @property
    def description(self) -> str:
        return "Restless fidgeting with shoulder rolls and position testing"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Uncomfortable shift", "Shoulder roll left", "Test position",
                "Nope adjust", "Shoulder roll right", "Lean test", "Still not right",
                "Big readjust", "Getting closer", "Tiny tweak 1", "Tiny tweak 2",
                "Almost there", "One more shift", "Ahh perfect", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_adj = random.uniform(-0.4, 0.4)
        shoulder_var = random.uniform(-0.25, 0.25)
        
        keyframes = [
            [0.0, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00],                                   # Starting position
            [base_adj * 0.3, -0.78, 1.35, 1.35, -1.3, 15.0, 1.00],                      # Uncomfortable
            [base_adj * 0.5 - 0.2, -0.95 + shoulder_var, 1.2, 1.5, -1.8, 14.5, 1.40],   # Roll shoulder left
            [base_adj * 0.4, -0.82, 1.32, 1.38, -0.9, 16.0, 1.00],                      # Test this spot
            [base_adj * 0.6, -0.85 + shoulder_var*0.5, 1.28, 1.42, -2.0, 15.5, 1.00],   # Nope, adjust more
            [base_adj * 0.5 + 0.2, -0.95 - shoulder_var, 1.2, 1.5, -0.8, 14.0, 1.80],   # Roll shoulder right
            [-base_adj * 0.3, -0.75, 1.35, 1.35, -1.7, 16.5, 1.00],                     # Try leaning
            [-base_adj * 0.5, -0.88, 1.27, 1.43, -1.1, 15.0, 1.00],                     # Still not comfortable
            [base_adj * 0.7, -0.6, 1.4, 1.2, -1.9, 17.0, 1.00],                         # Big position change
            [base_adj * 0.3, -0.8, 1.3, 1.4, -0.85, 13.5, 1.00],                         # This is better
            [base_adj * 0.15, -0.82, 1.31, 1.39, -1.6, 12.5, 1.00],                     # Tiny adjustment
            [base_adj * 0.1, -0.83, 1.3, 1.4, -1.2, 11.5, 1.00],                        # Another tiny one
            [0.05, -0.84, 1.3, 1.4, -1.7, 11.0, 1.00],                                  # Almost perfect
            [0.0, -0.845, 1.3, 1.4, -1.3, 10.5, 1.00],                                  # One final shift
            [0.0, -0.85, 1.1, 1.4, -1.6, 10.0, 1.00],                                   # Ahh, comfortable
            [0.0, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00]                                    # Home 2
        ]
        
        # Fidgety but faster
        durations = [0.6, 0.55, 0.55, 0.45, 0.55, 0.55, 0.45, 0.55, 0.45, 0.55, 0.6, 0.7, 0.7, 0.8, 0.95, 0.6]
        
        return keyframes, durations


class DreamyDriftAnimation(AnimationPlugin):
    """Ethereal floating movements with smooth, continuous flow."""
    
    @property
    def name(self) -> str:
        return "dreamy_drift"
    
    @property
    def description(self) -> str:
        return "Weightless floating with smooth figure-8 patterns"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Drift begins", "Float upward", "Arc left high",
                "Suspend peak", "Gentle fall right", "Swoop low", "Rise again",
                "Figure-8 cross", "Float opposite", "Slow spiral", "Gravity returns",
                "Soft landing", "Final settle", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        drift_radius = 0.5
        
        keyframes = [
            [0.0, -0.65, 1.2, 1.0, -1.5, 10.0, 1.00],                           # Home 2
            [0.08, -0.88, 1.27, 1.43, -1.3, 10.5, 1.00],                        # Subtle drift start
            [0.15, -1.05, 1.05, 1.65, -1.8, 10.0, 2.80],                        # Float gently up
            [-drift_radius*0.8, -1.0, 1.1, 1.6, -0.85, 10.5, 1.40],              # Arc to left high
            [-drift_radius, -0.95, 1.15, 1.55, -2.1, 10.0, 3.14],                # Suspend at peak
            [drift_radius*0.6, -0.85, 1.25, 1.45, -0.8, 10.5, 1.80],             # Fall gently right
            [drift_radius*0.9, -0.55, 1.45, 1.15, -1.9, 11.0, 0.40],            # Swoop down low
            [drift_radius*0.7, -0.75, 1.3, 1.35, -1.0, 10.5, 2.80],             # Begin rise
            [0.0, -0.9, 1.2, 1.5, -1.7, 10.0, 1.00],                            # Cross center of 8
            [-drift_radius*0.7, -0.8, 1.25, 1.4, -0.9, 10.5, 1.00],             # Float to opposite
            [-0.2, -0.65, 1.35, 1.25, -1.8, 11.5, 0.40],                        # Slow downward spiral
            [0.0, -0.75, 1.28, 1.35, -1.1, 11.0, 0.40],                         # Gravity slowly returns
            [0.0, -0.82, 1.29, 1.38, -1.6, 10.5, 1.00],                         # Soft landing approach
            [0.0, -0.84, 1.2, 1.39, -1.4, 10.0, 0.60],                          # Almost settled
            [0.0, -0.65, 1.2, 1.0, -1.5, 10.0, 1.00]                            # Home 2
        ]
        
        # Dreamy but not too slow
        durations = [0.95, 0.8, 0.95, 1.2, 1.6, 1.1, 0.85, 0.95, 0.95, 1.1, 0.8, 0.8, 0.8, 0.95, 0.95]
        
        return keyframes, durations


class NeckStretchAnimation(AnimationPlugin):
    """Neck stretching and rotation movements for relief and flexibility."""
    
    @property
    def name(self) -> str:
        return "neck_stretch"
    
    @property
    def description(self) -> str:
        return "Neck rolls and stretches like relieving tension"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Prepare stretch", "Tilt head left", "Deep stretch left",
                "Roll back", "Tilt head right", "Deep stretch right", "Roll forward",
                "Chin to chest", "Look up stretch", "Center crack", "Relief shake",
                "Final adjust", "Relaxed", "Home 2"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00],                    # Home 2
            [base_pos, -0.8, 1.25, 1.35, -1.3, 11.0, 1.00],                   # Prepare for stretch
            [base_pos - 0.4, -0.75, 1.2, 1.3, -1.9, 10.5, 1.40],              # Tilt head left
            [base_pos - 0.6, -0.7, 1.15, 1.25, -0.8, 10.0, 1.40],             # Deep stretch left side
            [base_pos - 0.3, -0.9, 1.1, 1.5, -2.2, 10.5, 1.00],               # Roll head back
            [base_pos + 0.4, -0.75, 1.2, 1.3, -0.75, 10.5, 1.80],              # Tilt head right
            [base_pos + 0.6, -0.7, 1.15, 1.25, -1.8, 10.0, 1.80],             # Deep stretch right
            [base_pos + 0.3, -0.5, 1.35, 1.05, -1.0, 11.0, 1.00],             # Roll head forward
            [base_pos, -0.4, 1.45, 0.95, -2.0, 10.5, 1.00],                   # Chin to chest stretch
            [base_pos, -1.05, 0.9, 1.7, -0.85, 10.0, 2.80],                    # Look way up, stretch throat
            [base_pos + 0.05, -0.85, 1.2, 1.4, -1.7, 16.0, 1.00],             # Quick center adjustment
            [base_pos - 0.05, -0.85, 1.25, 1.4, -1.2, 15.5, 1.20],            # Relief shake
            [base_pos, -0.83, 1.28, 1.39, -1.6, 12.5, 1.00],                  # Final position adjust
            [base_pos, -0.84, 1.2, 1.4, -1.4, 11.5, 0.60],                    # Relaxed after stretch
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00]                     # Home 2
        ]
        
        # Stretches need time but not too slow
        durations = [0.6, 0.7, 0.8, 1.2, 0.8, 0.8, 1.2, 0.8, 0.8, 1.4, 0.4, 0.4, 0.6, 0.7, 0.6]
        
        return keyframes, durations


class SleepAnimation(AnimationPlugin):
    """Folded sleepy dog - folds into C-shape """
    
    @property
    def name(self) -> str:
        return "sleep"
    
    @property
    def description(self) -> str:
        return "Folded C-shape with neck movements like a sleepy dog"

    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return [
            "Initial fold", "Deep C-curve", 
            "Content right", "Blissful left",
            "Happy center", "Happy center again"
        ]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -1.3, 1.4, 0.8, -2.2, 10.0, 1.00],        # Initial fold - starting to curve
            [base_pos, -1.6, 1.8, 1.2, -2.8, 8.0, 1.00],         # Deep C-curve - folded position
            [base_pos+0.4, -1.75, 1.95, 1.5, -2.5, 9.5, 1.80],   # Content right - deeper fold
            [base_pos-0.4, -1.8, 2.0, 1.6, -3.0, 8.0, 1.40],     # Blissful left - maximum fold
            [base_pos, -1.75, 1.95, 1.4, -2.7, 9.0, 3.14],       # Happy center - balanced
            [base_pos, -1.75, 1.95, 1.4, -2.7, 9.0, 3.14],       # Happy center again - balanced
        ]
        
        # Smooth neck movement durations
        durations = [0.85, 1.02, 0.68, 0.77, 0.9, 0.9]
        
        return keyframes, durations


class YawningStretchAnimation(AnimationPlugin):
    """Big yawning stretch with full body extension."""
    
    @property
    def name(self) -> str:
        return "yawning_stretch"
    
    @property
    def description(self) -> str:
        return "Tired yawning with arms stretching up and out"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Feel tired", "Yawn starting", "Mouth open wide",
                "Arms up stretch", "Full extension", "Peak stretch hold",
                "Shudder release", "Arms lowering", "Yawn closing", 
                "Sleepy blink", "Shake it off", "Return normal", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00],                    # Home 2
            [base_pos, -0.75, 1.35, 1.35, -1.3, 11.5, 0.20],                  # Feeling tired
            [base_pos, -0.9, 1.15, 1.5, -1.8, 10.5, 1.00],                    # Yawn beginning
            [base_pos - 0.1, -1.0, 1.0, 1.65, -0.8, 10.0, 1.00],              # Mouth opening wide
            [base_pos, -1.05, 0.8, 1.8, -2.1, 10.0, 2.80],                    # Arms stretching up
            [base_pos + 0.1, -1.1, 0.6, 1.95, -0.75, 10.0, 1.00],             # Full body extension (at limit)
            [base_pos, -1.08, 0.62, 1.93, -1.9, 10.0, 3.14],                  # Hold at peak
            [base_pos - 0.05, -1.05, 0.7, 1.85, -0.85, 14.0, 1.00],           # Shudder during release
            [base_pos, -1.0, 0.95, 1.6, -1.7, 11.0, 0.40],                    # Arms coming down
            [base_pos, -0.8, 1.2, 1.4, -1.1, 12.0, 1.00],                     # Yawn closing
            [base_pos, -0.78, 1.25, 1.38, -1.8, 13.0, 0.20],                  # Sleepy blink
            [base_pos + 0.15, -0.82, 1.27, 1.4, -1.0, 15.5, 1.20],            # Shake head to wake
            [base_pos, -0.84, 1.2, 1.4, -1.6, 12.5, 1.00],                    # Back to normal
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00]                     # Home 2
        ]
        
        # Yawn timing with good hold
        durations = [0.6, 0.7, 0.8, 0.95, 0.95, 0.95, 1.6, 0.55, 0.8, 0.6, 0.6, 0.45, 0.6, 0.6]
        
        return keyframes, durations


class ShoulderShimmy(AnimationPlugin):
    """Playful shoulder shimmy dance move."""
    
    @property
    def name(self) -> str:
        return "shoulder_shimmy"
    
    @property
    def description(self) -> str:
        return "Fun shoulder shimmy with alternating movements"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Prep stance", "Right shoulder up", "Left shoulder up",
                "Quick right", "Quick left", "Double shimmy 1", "Double shimmy 2",
                "Big shimmy right", "Big shimmy left", "Shimmy center",
                "Final shake", "Cool down", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 14.0, 1.00],                    # Home 2
            [base_pos, -0.75, 1.2, 1.35, -1.3, 16.0, 1.00],                   # Get ready
            [base_pos + 0.2, -0.85, 1.15, 1.45, -1.8, 18.0, 1.80],            # Right shoulder up
            [base_pos - 0.2, -0.85, 1.15, 1.45, -0.9, 18.5, 1.40],            # Left shoulder up
            [base_pos + 0.15, -0.8, 1.18, 1.42, -2.0, 19.0, 1.80],            # Quick right
            [base_pos - 0.15, -0.8, 1.18, 1.42, -0.8, 19.5, 1.40],            # Quick left
            [base_pos + 0.25, -0.78, 1.22, 1.38, -1.8, 20.0, 1.00],           # Double shimmy
            [base_pos - 0.25, -0.78, 1.22, 1.38, -1.0, 20.5, 1.00],           # Other side
            [base_pos + 0.35, -0.7, 1.25, 1.35, -2.1, 21.0, 1.80],            # Big shimmy right
            [base_pos - 0.35, -0.7, 1.25, 1.35, -0.75, 21.5, 1.40],           # Big shimmy left
            [base_pos, -0.75, 1.2, 1.4, -1.7, 17.0, 1.00],                    # Back to center
            [base_pos + 0.1, -0.8, 1.25, 1.38, -1.2, 16.0, 1.20],             # Final little shake
            [base_pos, -0.83, 1.28, 1.39, -1.6, 13.0, 0.40],                  # Cool down
            [base_pos, -0.65, 1.2, 1.0, -1.5, 14.0, 1.00]                     # Home 2
        ]
        
        # Quick shimmy timing
        durations = [0.45, 0.4, 0.4, 0.4, 0.35, 0.4, 0.4, 0.4, 0.45, 0.5, 0.4, 0.35, 0.55, 0.45]
        
        return keyframes, durations


class LookAroundCasual(AnimationPlugin):
    """Casual looking around as if checking surroundings."""
    
    @property
    def name(self) -> str:
        return "look_around_casual"
    
    @property
    def description(self) -> str:
        return "Casual glances around the environment"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Slight lift", "Glance left", "Notice something",
                "Look back center", "Glance right casual", "Up and right",
                "Check behind right", "Return center", "Quick left check",
                "All good", "Settle", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 13.0, 1.00],                    # Home 2
            [base_pos, -0.78, 1.25, 1.38, -1.3, 14.0, 1.00],                  # Slight head lift
            [base_pos - 0.4, -0.75, 1.22, 1.35, -1.8, 15.0, 1.40],            # Casual glance left
            [base_pos - 0.35, -0.72, 1.2, 1.32, -0.9, 14.5, 1.00],            # Hmm, what's that?
            [base_pos, -0.77, 1.23, 1.37, -1.7, 13.5, 1.00],                  # Look back to center
            [base_pos + 0.3, -0.75, 1.22, 1.4, -1.1, 15.5, 1.80],             # Glance right
            [base_pos + 0.35, -0.85, 1.15, 1.5, -2.0, 14.0, 1.80],            # Look up and right
            [base_pos + 0.5, -0.8, 1.2, 1.45, -0.8, 13.0, 1.00],              # Check behind
            [base_pos, -0.78, 1.24, 1.38, -1.8, 13.5, 1.00],                  # Back to center
            [base_pos - 0.25, -0.76, 1.23, 1.36, -1.0, 16.0, 1.40],           # Quick left check
            [base_pos, -0.8, 1.26, 1.38, -1.6, 12.5, 1.00],                   # All good
            [base_pos, -0.84, 1.29, 1.39, -1.4, 11.5, 1.00],                  # Settling back
            [base_pos, -0.65, 1.2, 1.0, -1.5, 13.0, 1.00]                     # Home 2
        ]
        
        # Casual but not sluggish
        durations = [0.6, 0.55, 0.6, 0.55, 0.7, 0.55, 0.6, 0.8, 0.7, 0.55, 0.6, 0.7, 0.6]
        
        return keyframes, durations


# New animations added below

class ContentedSighAnimation(AnimationPlugin):
    """Deep contented sigh with full body relaxation."""
    
    @property
    def name(self) -> str:
        return "contented_sigh"
    
    @property
    def description(self) -> str:
        return "Deep satisfying sigh with shoulders dropping and body relaxing"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Prepare inhale", "Deep breath in", "Peak hold",
                "Begin sigh", "Deep exhale", "Shoulders drop", "Full relax",
                "Settle deeper", "Content state", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00],                    # Home 2
            [base_pos, -0.8, 1.25, 1.35, -1.3, 11.0, 1.00],                   # Prepare for deep breath
            [base_pos, -1.0, 1.1, 1.6, -1.8, 10.0, 1.00],                     # Deep inhale
            [base_pos, -1.05, 1.08, 1.62, -1.0, 10.0, 3.14],                  # Hold at peak
            [base_pos, -0.9, 1.2, 1.5, -1.9, 11.0, 1.00],                     # Begin exhale
            [base_pos, -0.6, 1.4, 1.2, -1.2, 12.0, 1.00],                     # Deep sigh out - back
            [base_pos, -0.4, 1.5, 1.0, -1.7, 11.0, 1.00],                     # Shoulders drop - back
            [base_pos, -0.3, 1.6, 0.8, -1.5, 10.0, 0.60],                     # Full relaxation - back
            [base_pos, -0.5, 1.5, 0.9, -1.6, 10.0, 0.60],                     # Settle into comfort - back
            [base_pos, -0.75, 1.3, 1.1, -1.5, 11.0, 1.00],                    # Content final state
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00]                     # Home 2
        ]
        
        # Relaxed sigh timing
        durations = [0.6, 0.7, 0.95, 1.2, 0.8, 0.8, 0.85, 0.95, 0.95, 0.7, 0.6]
        
        return keyframes, durations


class HeadBobbingAnimation(AnimationPlugin):
    """Rhythmic head bobbing like listening to music."""
    
    @property
    def name(self) -> str:
        return "head_bobbing"
    
    @property
    def description(self) -> str:
        return "Rhythmic head bobbing to an internal beat"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "First beat down", "Beat up", "Double time 1", "Double time 2",
                "Beat down strong", "Beat up", "Side groove left", "Side groove right",
                "Final beat", "Cool down", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 16.0, 1.00],                    # Home 2
            [base_pos, -0.65, 1.25, 0.85, -1.3, 18.0, 0.40],                  # Beat down - back
            [base_pos, -0.8, 1.15, 1.15, -1.7, 18.0, 2.80],                   # Beat up - back
            [base_pos, -0.68, 1.22, 0.9, -1.4, 20.0, 1.00],                   # Quick beat 1 - back
            [base_pos, -0.78, 1.18, 1.1, -1.6, 20.0, 1.00],                   # Quick beat 2 - back
            [base_pos, -0.6, 1.3, 0.8, -1.2, 19.0, 0.40],                     # Strong beat down - back
            [base_pos, -0.85, 1.1, 1.2, -1.8, 18.0, 2.80],                    # Beat up - back
            [base_pos - 0.2, -0.7, 1.2, 0.95, -1.0, 17.0, 1.40],              # Groove left - back
            [base_pos + 0.2, -0.7, 1.2, 0.95, -2.0, 17.0, 1.80],              # Groove right - back
            [base_pos, -0.65, 1.25, 0.85, -1.5, 16.0, 1.00],                  # Final beat - back
            [base_pos, -0.8, 1.2, 1.05, -1.5, 15.0, 0.40],                    # Cool down - back
            [base_pos, -0.65, 1.2, 1.0, -1.5, 14.0, 1.00]                     # Home 2
        ]
        
        # Musical timing
        durations = [0.45, 0.4, 0.4, 0.35, 0.35, 0.4, 0.4, 0.45, 0.45, 0.45, 0.55, 0.55]
        
        return keyframes, durations


class TailWagAnimation(AnimationPlugin):
    """Happy tail wagging motion with base swaying."""
    
    @property
    def name(self) -> str:
        return "tail_wag"
    
    @property
    def description(self) -> str:
        return "Enthusiastic tail wagging with full body involvement"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Wind up", "Wag right fast", "Wag left fast", "Big wag right",
                "Big wag left", "Double wag 1", "Double wag 2", "Excited wiggle",
                "Happy bounce", "Slow wag", "Settle", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 15.0, 1.00],                    # Home 2
            [base_pos, -0.7, 1.15, 1.05, -1.3, 17.0, 2.80],                   # Wind up
            [base_pos + 0.4, -0.6, 1.1, 0.95, -2.0, 20.0, 1.80],              # Fast wag right
            [base_pos - 0.4, -0.6, 1.1, 0.95, -1.0, 20.0, 1.40],              # Fast wag left
            [base_pos + 0.5, -0.55, 1.05, 0.9, -2.2, 19.0, 1.80],             # Big wag right
            [base_pos - 0.5, -0.55, 1.05, 0.9, -0.8, 19.0, 1.40],             # Big wag left
            [base_pos + 0.3, -0.62, 1.12, 0.98, -1.8, 21.0, 1.00],            # Quick double 1
            [base_pos - 0.3, -0.62, 1.12, 0.98, -1.2, 21.0, 1.00],            # Quick double 2
            [base_pos + 0.1, -0.68, 1.18, 1.08, -1.9, 18.0, 3.14],            # Excited wiggle
            [base_pos, -0.5, 1.0, 0.8, -1.5, 17.0, 3.14],                     # Happy bounce
            [base_pos - 0.2, -0.7, 1.2, 1.1, -1.6, 15.0, 0.40],               # Slow wag
            [base_pos, -0.75, 1.25, 1.15, -1.5, 14.0, 0.60],                  # Settle
            [base_pos, -0.65, 1.2, 1.0, -1.5, 13.0, 1.00]                     # Home 2
        ]
        
        # Fast wagging
        durations = [0.55, 0.45, 0.55, 0.6, 0.6, 0.7, 0.45, 0.45, 0.4, 0.45, 0.45, 0.55, 0.6]
        
        return keyframes, durations


class PonderingAnimation(AnimationPlugin):
    """Deep pondering with chin stroking gestures."""
    
    @property
    def name(self) -> str:
        return "pondering"
    
    @property
    def description(self) -> str:
        return "Thoughtful pondering with metaphorical chin stroking"
    
    def get_category(self) -> str:
        return "idle"
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        return ["Home", "Initial thought", "Chin stroke position", "Deep ponder",
                "Look up thinking", "Side glance", "Hmm moment", "Another angle",
                "Processing", "Slight nod", "Final think", "Resolution", "Home"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00],                    # Home 2
            [base_pos, -0.75, 1.15, 1.2, -1.3, 13.0, 1.00],                   # Initial thought
            [base_pos, -0.5, 0.9, 0.8, -1.7, 11.0, 1.00],                     # Chin stroke position - back
            [base_pos - 0.1, -0.45, 0.85, 0.75, -1.0, 10.0, 1.60],            # Deep ponder - back
            [base_pos, -1.0, 0.8, 1.5, -1.8, 11.0, 1.60],                     # Look up thinking - far back
            [base_pos + 0.3, -0.7, 1.0, 1.1, -0.9, 12.0, 1.00],               # Side glance - back
            [base_pos, -0.55, 0.95, 0.85, -2.0, 10.0, 1.00],                  # Hmm moment - back
            [base_pos - 0.25, -0.6, 1.0, 0.9, -1.2, 11.0, 1.00],              # Another angle - back
            [base_pos, -0.65, 1.05, 0.95, -1.6, 10.0, 1.00],                  # Processing - back
            [base_pos, -0.7, 1.1, 1.0, -1.4, 13.0, 1.00],                     # Slight understanding nod - back
            [base_pos, -0.8, 1.15, 1.15, -1.8, 12.0, 1.60],                   # Final think - back
            [base_pos, -0.85, 1.2, 1.2, -1.5, 14.0, 1.00],                    # Resolution - back
            [base_pos, -0.65, 1.2, 1.0, -1.5, 12.0, 1.00]                     # Home 2
        ]
        
        # Thoughtful timing
        durations = [0.6, 0.7, 0.8, 0.95, 0.8, 0.7, 0.95, 0.8, 0.95, 0.6, 0.7, 0.55, 0.6]
        
        return keyframes, durations