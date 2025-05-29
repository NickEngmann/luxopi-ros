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
                "Gentle return", "Balance check", "Settle", "Home 1", "Home 2"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        sway_amount = random.uniform(0.45, 0.65)
        breath_lift = random.uniform(0.1, 0.15)
        
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],                          # Start at home
            [base_pos, -0.88, 1.32, 1.42, 0.0],                        # Subtle inhale
            [base_pos + sway_amount*0.15, -0.78, 1.25, 1.38, 0.0],     # Begin shift
            [base_pos + sway_amount*0.4, -0.7, 1.18, 1.45, 0.0],       # Lean into movement
            [base_pos + sway_amount*0.45, -0.68 + breath_lift, 1.16, 1.47, 0.0], # Micro shoulder adjust
            [base_pos + sway_amount*0.85, -0.6, 1.08, 1.52, 0.0],      # Near full sway
            [base_pos + sway_amount, -0.58 - breath_lift, 1.05, 1.54, 0.0], # Full sway with breath
            [base_pos + sway_amount*0.7, -0.65, 1.12, 1.45, 0.0],      # Begin exhale return
            [base_pos + sway_amount*0.2, -0.72, 1.2, 1.38, 0.0],       # Through center
            [base_pos - sway_amount*0.15, -0.76, 1.22, 1.36, 0.0],     # Begin left shift
            [base_pos - sway_amount*0.5, -0.73, 1.18, 1.4, 0.0],       # Head tilt moment
            [base_pos - sway_amount*0.9, -0.62, 1.1, 1.48, 0.0],       # Near full left
            [base_pos - sway_amount, -0.6 + breath_lift*0.5, 1.08, 1.46, 0.0], # Full left with settle
            [base_pos - sway_amount*0.4, -0.74, 1.2, 1.4, 0.0],        # Gentle return
            [base_pos - 0.05, -0.8, 1.26, 1.41, 0.0],                  # Balance check
            [base_pos, -0.8, 1.29, 1.4, 0.0],                         # Near home
            [base_pos, -0.85, 1.3, 1.4, 0.0]                           # Home 2
        ]
        
        # Natural human-like timing with breath rhythm
        durations = [0.6, 0.8, 0.7, 0.9, 0.5, 0.8, 1.4, 1.0, 0.9, 0.8, 0.6, 0.9, 1.5, 1.1, 0.7, 0.6, 0.5, 0.8]
        
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
            [base_pos, -0.85, 1.3, 1.4, 0.0],                    # Start at home
            [base_pos - 0.1, -0.65, 1.15, 1.3, 0.0],             # Something catches attention
            [base_pos - 0.55, -0.55, 1.05, 1.2, 0.0],            # Quick glance left
            [base_pos - 0.5, -0.6, 1.1, 1.25, 0.0],              # Pause - wait what?
            [base_pos - 0.45, -0.45, 0.9, 1.05, 0.0],            # Double-take lean forward
            [base_pos - 0.42, -0.4, 0.85, 1.0, 0.0],             # Squint for detail
            [base_pos - 0.48, -0.42, 0.87, 1.08, 0.0],           # Head tilt confused
            [base_pos - 0.4, -0.25, 0.65, 0.85, 0.0],            # Lean way in to inspect
            [base_pos - 0.35, -0.3, 0.7, 0.95, 0.0],             # Aha! I see it
            [base_pos - 0.2, -0.65, 1.15, 1.4, 0.0],             # Pull back to process
            [base_pos, -0.95, 0.85, 1.65, 0.0],                  # Look up thinking about it
            [base_pos + 0.65, -0.5, 1.05, 1.35, 0.0],            # Glance right to compare
            [base_pos + 0.2, -0.6, 1.12, 1.3, 0.0],              # Nod - I understand now
            [base_pos, -0.75, 1.23, 1.37, 0.0],                  # Satisfied exhale
            [base_pos, -0.82, 1.28, 1.39, 0.0],                  # Return to rest
            [base_pos, -0.85, 1.3, 1.4, 0.0]                     # Home directly
        ]
        
        # Varied timing for natural investigation
        durations = [0.6, 0.6, 0.6, 0.8, 0.7, 0.6, 0.7, 0.9, 0.6, 0.7, 1.0, 0.7, 0.5, 0.8, 0.6, 0.7]
        
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
        sway = random.uniform(-0.05, 0.05)  # Subtle sway during breathing
        
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],                    # Rest position
            [base_pos, -0.88, 1.32, 1.43, 0.0],                  # Mental preparation
            [base_pos + sway, -0.95, 1.34, 1.5, 0.0],            # Begin deep inhale
            [base_pos, -1.08, 1.38, 1.6, 0.0],                   # Chest expanding
            [base_pos - sway, -1.18, 1.42, 1.68, 0.0],           # Full expansion
            [base_pos, -1.16, 1.41, 1.66, 0.0],                  # Hold at peak
            [base_pos + sway*0.5, -1.14, 1.4, 1.64, 0.0],        # Slight waver in hold
            [base_pos, -1.0, 1.36, 1.55, 0.0],                   # Begin controlled exhale
            [base_pos - sway, -0.85, 1.3, 1.45, 0.0],            # Releasing downward
            [base_pos, -0.65, 1.2, 1.25, 0.0],                   # Deep exhale compression
            [base_pos, -0.62, 1.18, 1.22, 0.0],                  # Bottom of breath pause
            [base_pos, -0.72, 1.24, 1.32, 0.0],                  # Small recovery inhale
            [base_pos, -0.8, 1.28, 1.38, 0.0],                   # Settling
            [base_pos, -0.84, 1.2, 1.39, 0.0],                  # Peaceful state
            [base_pos, -0.85, 1.3, 1.4, 0.0]                     # Home directly
        ]
        
        # Yogic breathing rhythm
        durations = [0.8, 0.7, 1.2, 1.0, 0.8, 2.0, 0.6, 1.1, 1.0, 0.9, 1.4, 0.8, 0.7, 0.6, 0.8]
        
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
                "Home 1", "Home 2"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],                    # Home
            [base_pos, -0.7, 1.2, 1.35, 0.0],                    # Shift to attention
            [base_pos, -0.65, 1.15, 1.3, 0.0],                   # Eyebrow raise interest
            [base_pos - 0.15, -0.5, 1.0, 1.15, 0.0],             # Lean in curious
            [base_pos - 0.12, -0.52, 1.02, 1.12, 0.0],           # Micro nod understanding
            [base_pos - 0.35, -0.55, 1.05, 1.2, 0.0],            # Head tilt questioning
            [base_pos - 0.32, -0.62, 1.12, 1.28, 0.0],           # Processing information
            [base_pos - 0.3, -0.58, 1.08, 1.24, 0.0],            # Another micro nod
            [base_pos + 0.1, -0.6, 1.1, 1.3, 0.0],               # Shift weight/position
            [base_pos + 0.38, -0.58, 1.08, 1.32, 0.0],           # Head tilt other way
            [base_pos + 0.15, -0.48, 0.98, 1.18, 0.0],           # Deep understanding nod
            [base_pos, -0.72, 1.22, 1.42, 0.0],                  # Pull back to think
            [base_pos, -0.68, 1.18, 1.38, 0.0],                  # Understanding dawns
            [base_pos, -0.55, 1.05, 1.25, 0.0],                  # Agreement gesture forward
            [base_pos, -0.78, 1.26, 1.38, 0.0],                  # Settle back satisfied
            [base_pos, -0.85, 1.3, 1.4, 0.0]                     # Home 2
        ]
        
        # Conversational rhythm
        durations = [0.6, 0.7, 0.7, 0.7, 0.7, 0.8, 0.6, 0.6, 0.7, 0.8, 0.6, 0.9, 0.7, 0.6, 0.8, 0.6, 0.8]
        
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
                "Home 1", "Home 2"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        energy = random.uniform(0.8, 1.2)  # Varies the energy level
        
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],                          # Home
            [base_pos, -0.5, 1.55, 0.95, 0.0],                         # Deep anticipation
            [base_pos + 0.05, -0.45, 1.6, 0.9, 0.0],                   # Coiled spring
            [base_pos - 0.1, -1.25 * energy, 0.85, 1.75, 0.0],         # Explosive jump
            [base_pos + 0.15, -1.2 * energy, 0.8, 1.8, 0.0],           # Peak of jump
            [base_pos, -0.35, 1.45, 0.85, 0.0],                        # Soft landing
            [base_pos - 0.45, -0.75, 1.15, 1.55, 0.0],                 # Hip sway left
            [base_pos - 0.4, -0.8, 1.1, 1.5, 0.0],                     # Shoulder shimmy
            [base_pos + 0.45, -0.75, 1.15, 1.55, 0.0],                 # Hip sway right
            [base_pos, -0.55, 1.35, 1.1, 0.0],                         # Prep double bounce
            [base_pos + 0.1, -1.0, 1.0, 1.6, 0.0],                     # Quick pop up
            [base_pos - 0.1, -0.6, 1.3, 1.2, 0.0],                     # Quick drop
            [base_pos + 0.25, -0.72, 1.18, 1.42, 0.0],                 # Wiggle right
            [base_pos - 0.25, -0.75, 1.2, 1.45, 0.0],                  # And left
            [base_pos, -0.8, 1.25, 1.38, 0.0],                         # Happy settling
            [base_pos, -0.85, 1.3, 1.4, 0.0]                           # Home 2
        ]
        
        # Rhythmic, musical timing
        durations = [0.7, 0.7, 0.6, 0.8, 0.7, 0.6, 0.6, 0.7, 0.8, 0.6, 0.7, 0.7, 0.8, 0.8, 0.6, 0.6, 0.8]
        
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
            [0.0, -0.85, 1.3, 1.4, 0.0],                          # Home
            [0.0, alert_height, 1.0, 1.3, 0.0],                   # Rise to alert
            [-0.75, alert_height - 0.05, 0.95, 1.2, 0.0],        # Snap look left
            [-0.7, alert_height, 1.0, 1.25, 0.0],                 # Quick evaluation
            [-0.35, alert_height + 0.05, 1.05, 1.3, 0.0],         # Scanning across
            [0.0, alert_height - 0.1, 0.95, 1.35, 0.0],          # Pause - something?
            [0.35, alert_height, 1.02, 1.38, 0.0],                # Continue scanning
            [0.8, alert_height - 0.05, 0.95, 1.42, 0.0],         # Snap look right
            [0.75, alert_height - 0.15, 0.9, 1.38, 0.0],         # Lock on target
            [0.72, alert_height - 0.2, 0.85, 1.35, 0.0],         # Zoom in focus
            [0.7, alert_height - 0.18, 0.87, 1.37, 0.0],         # Assess threat level
            [0.4, alert_height + 0.1, 1.1, 1.4, 0.0],            # Relax - false alarm
            [-0.3, alert_height, 1.05, 1.35, 0.0],               # One final check
            [0.0, -0.7, 1.15, 1.38, 0.0],                        # All clear, lowering
            [0.0, -0.82, 1.2, 1.39, 0.0],                       # Return to rest
            [0.0, -0.85, 1.3, 1.4, 0.0]                          # Home directly
        ]
        
        # Alert, purposeful timing with snap movements
        durations = [0.6, 0.6, 0.6, 0.8, 0.8, 0.7, 0.8, 0.8, 0.6, 0.7, 0.9, 0.6, 0.7, 0.6, 0.7, 0.8]
        
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
        # More dramatic adjustments
        base_adj = random.uniform(-0.4, 0.4)
        shoulder_var = random.uniform(-0.25, 0.25)
        
        keyframes = [
            [0.0, -0.85, 1.3, 1.4, 0.0],                                   # Starting position
            [base_adj * 0.3, -0.78, 1.35, 1.35, 0.0],                      # Uncomfortable
            [base_adj * 0.5 - 0.2, -0.95 + shoulder_var, 1.2, 1.5, 0.0],   # Roll shoulder left
            [base_adj * 0.4, -0.82, 1.32, 1.38, 0.0],                      # Test this spot
            [base_adj * 0.6, -0.85 + shoulder_var*0.5, 1.28, 1.42, 0.0],   # Nope, adjust more
            [base_adj * 0.5 + 0.2, -0.95 - shoulder_var, 1.2, 1.5, 0.0],   # Roll shoulder right
            [-base_adj * 0.3, -0.75, 1.35, 1.35, 0.0],                     # Try leaning
            [-base_adj * 0.5, -0.88, 1.27, 1.43, 0.0],                     # Still not comfortable
            [base_adj * 0.7, -0.6, 1.4, 1.2, 0.0],                         # Big position change
            [base_adj * 0.3, -0.8, 1.3, 1.4, 0.0],                         # This is better
            [base_adj * 0.15, -0.82, 1.31, 1.39, 0.0],                     # Tiny adjustment
            [base_adj * 0.1, -0.83, 1.3, 1.4, 0.0],                        # Another tiny one
            [0.05, -0.84, 1.3, 1.4, 0.0],                                  # Almost perfect
            [0.0, -0.845, 1.3, 1.4, 0.0],                                  # One final shift
            [0.0, -0.85, 1.1, 1.4, 0.0],                                   # Ahh, comfortable
            [0.0, -0.85, 1.3, 1.4, 0.0]                                    # Already home
        ]
        
        # Fidgety, restless timing
        durations = [0.7, 0.6, 0.7, 0.6, 0.7, 0.7, 0.6, 0.6, 0.8, 0.6, 0.8, 0.8, 0.6, 0.8, 0.8, 0.8]
        
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
        # Smooth figure-8 pattern
        drift_radius = 0.5
        
        keyframes = [
            [0.0, -0.85, 1.3, 1.4, 0.0],                           # Home
            [0.08, -0.88, 1.27, 1.43, 0.0],                        # Subtle drift start
            [0.15, -1.1, 1.05, 1.65, 0.0],                         # Float gently up
            [-drift_radius*0.8, -1.05, 1.1, 1.6, 0.0],             # Arc to left high
            [-drift_radius, -1.0, 1.15, 1.55, 0.0],                # Suspend at peak
            [drift_radius*0.6, -0.85, 1.25, 1.45, 0.0],            # Fall gently right
            [drift_radius*0.9, -0.55, 1.45, 1.15, 0.0],            # Swoop down low
            [drift_radius*0.7, -0.75, 1.3, 1.35, 0.0],             # Begin rise
            [0.0, -0.9, 1.2, 1.5, 0.0],                            # Cross center of 8
            [-drift_radius*0.7, -0.8, 1.25, 1.4, 0.0],             # Float to opposite
            [-0.2, -0.65, 1.35, 1.25, 0.0],                        # Slow downward spiral
            [0.0, -0.75, 1.28, 1.35, 0.0],                         # Gravity slowly returns
            [0.0, -0.82, 1.29, 1.38, 0.0],                         # Soft landing approach
            [0.0, -0.84, 1.2, 1.39, 0.0],                          # Almost settled
            [0.0, -0.85, 1.3, 1.4, 0.0]                            # Home directly (close enough)
        ]
        
        # Slow, ethereal timing
        durations = [0.8, 1.0, 1.4, 1.6, 2.0, 1.5, 1.3, 1.4, 1.2, 1.5, 1.3, 1.0, 0.8, 0.7, 0.8]
        
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
                "Final adjust", "Relaxed", "Home 1", "Home 2"]
    
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        base_pos = 0.0
        
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, 0.0],                    # Home
            [base_pos, -0.8, 1.25, 1.35, 0.0],                   # Prepare for stretch
            [base_pos - 0.4, -0.75, 1.2, 1.3, 0.0],              # Tilt head left
            [base_pos - 0.6, -0.7, 1.15, 1.25, 0.0],             # Deep stretch left side
            [base_pos - 0.3, -0.9, 1.1, 1.5, 0.0],               # Roll head back
            [base_pos + 0.4, -0.75, 1.2, 1.3, 0.0],              # Tilt head right
            [base_pos + 0.6, -0.7, 1.15, 1.25, 0.0],             # Deep stretch right
            [base_pos + 0.3, -0.5, 1.35, 1.05, 0.0],             # Roll head forward
            [base_pos, -0.4, 1.45, 0.95, 0.0],                   # Chin to chest stretch
            [base_pos, -1.1, 0.9, 1.7, 0.0],                     # Look way up, stretch throat
            [base_pos + 0.05, -0.85, 1.2, 1.4, 0.0],             # Quick center adjustment
            [base_pos - 0.05, -0.85, 1.25, 1.4, 0.0],            # Relief shake
            [base_pos, -0.83, 1.28, 1.39, 0.0],                  # Final position adjust
            [base_pos, -0.84, 1.2, 1.4, 0.0],                   # Relaxed after stretch
            [base_pos, -0.85, 1.3, 1.4, 0.0]                     # Home 2
        ]
        
        # Slow stretching movements
        durations = [0.6, 0.8, 1.0, 1.5, 1.2, 1.0, 1.5, 1.2, 1.3, 1.8, 0.6, 0.6, 0.6, 0.8, 0.7, 0.8]
        
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
            [base_pos, -0.85, 1.3, 1.4, 0.0],                    # Home
            [base_pos, -0.75, 1.35, 1.35, 0.0],                  # Feeling tired
            [base_pos, -0.9, 1.15, 1.5, 0.0],                    # Yawn beginning
            [base_pos - 0.1, -1.05, 1.0, 1.65, 0.0],             # Mouth opening wide
            [base_pos, -1.2, 0.8, 1.8, 0.0],                     # Arms stretching up
            [base_pos + 0.1, -1.35, 0.6, 1.95, 0.0],             # Full body extension
            [base_pos, -1.32, 0.62, 1.93, 0.0],                  # Hold at peak
            [base_pos - 0.05, -1.25, 0.7, 1.85, 0.0],            # Shudder during release
            [base_pos, -1.0, 0.95, 1.6, 0.0],                    # Arms coming down
            [base_pos, -0.8, 1.2, 1.4, 0.0],                     # Yawn closing
            [base_pos, -0.78, 1.25, 1.38, 0.0],                  # Sleepy blink
            [base_pos + 0.15, -0.82, 1.27, 1.4, 0.0],            # Shake head to wake
            [base_pos, -0.84, 1.2, 1.4, 0.0],                   # Back to normal
            [base_pos, -0.85, 1.3, 1.4, 0.0]                     # Home directly
        ]
        
        # Yawning rhythm with holds
        durations = [0.6, 0.8, 1.0, 1.2, 1.4, 0.8, 2.0, 0.6, 1.2, 1.0, 0.8, 0.7, 0.7, 0.8]
        
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
            [base_pos, -0.85, 1.3, 1.4, 0.0],                    # Home
            [base_pos, -0.75, 1.2, 1.35, 0.0],                   # Get ready
            [base_pos + 0.2, -0.85, 1.15, 1.45, 0.0],            # Right shoulder up
            [base_pos - 0.2, -0.85, 1.15, 1.45, 0.0],            # Left shoulder up
            [base_pos + 0.15, -0.8, 1.18, 1.42, 0.0],            # Quick right
            [base_pos - 0.15, -0.8, 1.18, 1.42, 0.0],            # Quick left
            [base_pos + 0.25, -0.78, 1.22, 1.38, 0.0],           # Double shimmy
            [base_pos - 0.25, -0.78, 1.22, 1.38, 0.0],           # Other side
            [base_pos + 0.35, -0.7, 1.25, 1.35, 0.0],            # Big shimmy right
            [base_pos - 0.35, -0.7, 1.25, 1.35, 0.0],            # Big shimmy left
            [base_pos, -0.75, 1.2, 1.4, 0.0],                    # Back to center
            [base_pos + 0.1, -0.8, 1.25, 1.38, 0.0],             # Final little shake
            [base_pos, -0.83, 1.28, 1.39, 0.0],                  # Cool down
            [base_pos, -0.85, 1.3, 1.4, 0.0]                     # Home directly
        ]
        
        # Rhythmic shimmy timing
        durations = [0.5, 0.6, 0.6, 0.6, 0.6, 0.7, 0.6, 0.6, 0.5, 0.5, 0.6, 0.6, 0.7, 0.8]
        
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
            [base_pos, -0.85, 1.3, 1.4, 0.0],                    # Home
            [base_pos, -0.78, 1.25, 1.38, 0.0],                  # Slight head lift
            [base_pos - 0.4, -0.75, 1.22, 1.35, 0.0],            # Casual glance left
            [base_pos - 0.35, -0.72, 1.2, 1.32, 0.0],            # Hmm, what's that?
            [base_pos, -0.77, 1.23, 1.37, 0.0],                  # Look back to center
            [base_pos + 0.3, -0.75, 1.22, 1.4, 0.0],             # Glance right
            [base_pos + 0.35, -0.85, 1.15, 1.5, 0.0],            # Look up and right
            [base_pos + 0.5, -0.8, 1.2, 1.45, 0.0],              # Check behind
            [base_pos, -0.78, 1.24, 1.38, 0.0],                  # Back to center
            [base_pos - 0.25, -0.76, 1.23, 1.36, 0.0],           # Quick left check
            [base_pos, -0.8, 1.26, 1.38, 0.0],                   # All good
            [base_pos, -0.84, 1.29, 1.39, 0.0],                  # Settling back
            [base_pos, -0.85, 1.3, 1.4, 0.0]                     # Home directly
        ]
        
        # Casual, relaxed timing
        durations = [0.6, 0.7, 1.0, 0.8, 0.9, 1.1, 0.9, 1.2, 0.8, 0.6, 0.7, 0.6, 0.8]
        
        return keyframes, durations