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
            [base_pos, -0.85, 1.3, 1.4, -1.5, 12.0],                          # Start at home - gentle
            [base_pos, -0.88, 1.32, 1.42, -1.6, 10.5],                        # Subtle inhale - very gentle
            [base_pos + sway_amount*0.15, -0.78, 1.25, 1.38, -1.2, 11.0],     # Begin shift - gentle
            [base_pos + sway_amount*0.4, -0.7, 1.18, 1.45, -1.8, 10.0],       # Lean into movement - slowest
            [base_pos + sway_amount*0.45, -0.68 + breath_lift, 1.16, 1.47, -0.9, 13.5], # Micro shoulder adjust - moderate
            [base_pos + sway_amount*0.85, -0.6, 1.08, 1.52, -2.1, 11.5],      # Near full sway - gentle
            [base_pos + sway_amount, -0.58 - breath_lift, 1.05, 1.54, -0.7, 10.0], # Full sway with breath - slowest
            [base_pos + sway_amount*0.7, -0.65, 1.12, 1.45, -1.9, 11.0],      # Begin exhale return - gentle
            [base_pos + sway_amount*0.2, -0.72, 1.2, 1.38, -1.1, 12.0],       # Through center - gentle
            [base_pos - sway_amount*0.15, -0.76, 1.22, 1.36, -2.0, 10.5],     # Begin left shift - very gentle
            [base_pos - sway_amount*0.5, -0.73, 1.18, 1.4, -0.8, 14.0],       # Head tilt moment - moderate
            [base_pos - sway_amount*0.9, -0.62, 1.1, 1.48, -1.7, 11.0],       # Near full left - gentle
            [base_pos - sway_amount, -0.6 + breath_lift*0.5, 1.08, 1.46, -0.9, 10.0], # Full left with settle - slowest
            [base_pos - sway_amount*0.4, -0.74, 1.2, 1.4, -1.6, 11.5],        # Gentle return - gentle
            [base_pos - 0.05, -0.8, 1.26, 1.41, -1.3, 12.5],                  # Balance check - moderate
            [base_pos, -0.8, 1.29, 1.4, -1.5, 11.0],                         # Near home - gentle
            [base_pos, -0.85, 1.3, 1.4, -1.5, 12.0]                           # Home 2 - gentle
        ]
        
        # Natural human-like timing scaled by acceleration (base duration * 10 / acceleration)
        durations = [0.5, 0.76, 0.64, 0.9, 0.37, 0.70, 1.4, 0.91, 0.75, 0.76, 0.43, 0.82, 1.5, 0.96, 0.56, 0.55, 0.67]
        
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
            [base_pos, -0.85, 1.3, 1.4, -1.5, 13.0],                    # Start at home - moderate
            [base_pos - 0.1, -0.65, 1.15, 1.3, -1.2, 16.0],             # Something catches attention - quick
            [base_pos - 0.55, -0.55, 1.05, 1.2, -1.9, 19.0],            # Quick glance left - fast
            [base_pos - 0.5, -0.6, 1.1, 1.25, -0.8, 15.0],              # Pause - wait what? - quick
            [base_pos - 0.45, -0.45, 0.9, 1.05, -2.0, 17.5],            # Double-take lean forward - fast
            [base_pos - 0.42, -0.4, 0.85, 1.0, -0.7, 14.5],             # Squint for detail - moderate
            [base_pos - 0.48, -0.42, 0.87, 1.08, -1.8, 16.5],           # Head tilt confused - quick
            [base_pos - 0.4, -0.25, 0.65, 0.85, -0.9, 12.0],            # Lean way in to inspect - gentle
            [base_pos - 0.35, -0.3, 0.7, 0.95, -2.1, 20.0],             # Aha! I see it - fast
            [base_pos - 0.2, -0.65, 1.15, 1.4, -0.6, 15.5],             # Pull back to process - quick
            [base_pos, -0.95, 0.85, 1.65, -1.7, 11.5],                  # Look up thinking about it - gentle
            [base_pos + 0.65, -0.5, 1.05, 1.35, -0.8, 18.0],            # Glance right to compare - fast
            [base_pos + 0.2, -0.6, 1.12, 1.3, -1.9, 16.0],              # Nod - I understand now - quick
            [base_pos, -0.75, 1.23, 1.37, -1.1, 13.5],                  # Satisfied exhale - moderate
            [base_pos, -0.82, 1.28, 1.39, -1.6, 12.0],                  # Return to rest - gentle
            [base_pos, -0.85, 1.3, 1.4, -1.5, 13.0]                     # Home directly - moderate
        ]
        
        # Varied timing for natural investigation (base duration * 10 / acceleration)
        durations = [0.46, 0.38, 0.26, 0.53, 0.34, 0.41, 0.36, 0.75, 0.25, 0.45, 0.87, 0.33, 0.31, 0.59, 0.5, 0.54]
        
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
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.5],                    # Rest position - very gentle
            [base_pos, -0.88, 1.32, 1.43, -1.3, 10.0],                  # Mental preparation - slowest
            [base_pos + sway, -0.95, 1.34, 1.5, -1.8, 10.0],            # Begin deep inhale - slowest
            [base_pos, -1.08, 1.38, 1.6, -0.9, 10.5],                   # Chest expanding - very gentle
            [base_pos - sway, -1.18, 1.42, 1.68, -2.0, 10.0],           # Full expansion - slowest
            [base_pos, -1.16, 1.41, 1.66, -0.7, 10.0],                  # Hold at peak - slowest
            [base_pos + sway*0.5, -1.14, 1.4, 1.64, -1.7, 11.0],        # Slight waver in hold - gentle
            [base_pos, -1.0, 1.36, 1.55, -1.1, 10.5],                   # Begin controlled exhale - very gentle
            [base_pos - sway, -0.85, 1.3, 1.45, -1.9, 10.0],            # Releasing downward - slowest
            [base_pos, -0.65, 1.2, 1.25, -0.8, 10.5],                   # Deep exhale compression - very gentle
            [base_pos, -0.62, 1.18, 1.22, -2.2, 10.0],                  # Bottom of breath pause - slowest
            [base_pos, -0.72, 1.24, 1.32, -0.6, 11.5],                  # Small recovery inhale - gentle
            [base_pos, -0.8, 1.28, 1.38, -1.6, 11.0],                   # Settling - gentle
            [base_pos, -0.84, 1.2, 1.39, -1.3, 10.5],                  # Peaceful state - very gentle
            [base_pos, -0.85, 1.3, 1.4, -1.5, 10.0]                     # Home directly - slowest
        ]
        
        # Yogic breathing rhythm (base duration * 10 / acceleration)
        durations = [0.76, 0.7, 1.2, 0.95, 0.8, 2.0, 0.55, 1.05, 1.0, 0.86, 1.4, 0.70, 0.64, 0.57, 0.8]
        
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
            [base_pos, -0.85, 1.3, 1.4, -1.5, 12.5],                    # Home - moderate
            [base_pos, -0.7, 1.2, 1.35, -1.3, 14.0],                    # Shift to attention - moderate
            [base_pos, -0.65, 1.15, 1.3, -1.8, 15.5],                   # Eyebrow raise interest - quick
            [base_pos - 0.15, -0.5, 1.0, 1.15, -0.9, 13.0],             # Lean in curious - moderate
            [base_pos - 0.12, -0.52, 1.02, 1.12, -2.0, 16.0],           # Micro nod understanding - quick
            [base_pos - 0.35, -0.55, 1.05, 1.2, -0.7, 14.5],            # Head tilt questioning - moderate
            [base_pos - 0.32, -0.62, 1.12, 1.28, -1.9, 13.5],           # Processing information - moderate
            [base_pos - 0.3, -0.58, 1.08, 1.24, -1.0, 15.0],            # Another micro nod - quick
            [base_pos + 0.1, -0.6, 1.1, 1.3, -1.7, 14.0],               # Shift weight/position - moderate
            [base_pos + 0.38, -0.58, 1.08, 1.32, -0.8, 14.5],           # Head tilt other way - moderate
            [base_pos + 0.15, -0.48, 0.98, 1.18, -2.1, 17.0],           # Deep understanding nod - fast
            [base_pos, -0.72, 1.22, 1.42, -0.6, 12.0],                  # Pull back to think - gentle
            [base_pos, -0.68, 1.18, 1.38, -1.8, 13.5],                  # Understanding dawns - moderate
            [base_pos, -0.55, 1.05, 1.25, -1.2, 15.0],                  # Agreement gesture forward - quick
            [base_pos, -0.78, 1.26, 1.38, -1.6, 11.5],                  # Settle back satisfied - gentle
            [base_pos, -0.85, 1.3, 1.4, -1.5, 12.5]                     # Home 2 - moderate
        ]
        
        # Conversational rhythm (base duration * 10 / acceleration)
        durations = [0.48, 0.5, 0.45, 0.54, 0.44, 0.55, 0.44, 0.4, 0.5, 0.55, 0.35, 0.75, 0.52, 0.4, 0.70, 0.64]
        
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
        energy = random.uniform(0.8, 1.2)
        
        keyframes = [
            [base_pos, -0.85, 1.3, 1.4, -1.5, 14.0],                          # Home - moderate
            [base_pos, -0.5, 1.55, 0.95, -1.2, 18.0],                         # Deep anticipation - fast
            [base_pos + 0.05, -0.45, 1.6, 0.9, -1.9, 20.0],                   # Coiled spring - fast
            [base_pos - 0.1, -1.25 * energy, 0.85, 1.75, -0.7, 22.5],         # Explosive jump - fastest
            [base_pos + 0.15, -1.2 * energy, 0.8, 1.8, -2.2, 22.0],           # Peak of jump - fastest
            [base_pos, -0.35, 1.45, 0.85, -0.8, 16.0],                        # Soft landing - quick
            [base_pos - 0.45, -0.75, 1.15, 1.55, -1.8, 17.5],                 # Hip sway left - fast
            [base_pos - 0.4, -0.8, 1.1, 1.5, -0.9, 18.5],                     # Shoulder shimmy - fast
            [base_pos + 0.45, -0.75, 1.15, 1.55, -2.0, 17.0],                 # Hip sway right - fast
            [base_pos, -0.55, 1.35, 1.1, -0.6, 19.0],                         # Prep double bounce - fast
            [base_pos + 0.1, -1.0, 1.0, 1.6, -1.7, 21.0],                     # Quick pop up - very fast
            [base_pos - 0.1, -0.6, 1.3, 1.2, -1.0, 20.5],                     # Quick drop - very fast
            [base_pos + 0.25, -0.72, 1.18, 1.42, -1.9, 18.0],                 # Wiggle right - fast
            [base_pos - 0.25, -0.75, 1.2, 1.45, -0.8, 17.5],                  # And left - fast
            [base_pos, -0.8, 1.25, 1.38, -1.6, 13.0],                         # Happy settling - moderate
            [base_pos, -0.85, 1.3, 1.4, -1.5, 14.0]                           # Home 2 - moderate
        ]
        
        # Rhythmic, musical timing (base duration * 10 / acceleration)
        durations = [0.5, 0.39, 0.3, 0.31, 0.27, 0.38, 0.29, 0.32, 0.41, 0.26, 0.29, 0.29, 0.39, 0.4, 0.46, 0.57]
        
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
            [0.0, -0.85, 1.3, 1.4, -1.5, 13.0],                          # Home - moderate
            [0.0, alert_height, 1.0, 1.3, -1.2, 16.0],                   # Rise to alert - quick
            [-0.75, alert_height - 0.05, 0.95, 1.2, -1.9, 21.0],        # Snap look left - very fast
            [-0.7, alert_height, 1.0, 1.25, -0.8, 17.0],                 # Quick evaluation - fast
            [-0.35, alert_height + 0.05, 1.05, 1.3, -1.7, 15.0],         # Scanning across - quick
            [0.0, alert_height - 0.1, 0.95, 1.35, -1.0, 14.0],          # Pause - something? - moderate
            [0.35, alert_height, 1.02, 1.38, -1.8, 15.5],                # Continue scanning - quick
            [0.8, alert_height - 0.05, 0.95, 1.42, -0.7, 20.5],         # Snap look right - very fast
            [0.75, alert_height - 0.15, 0.9, 1.38, -2.0, 18.0],         # Lock on target - fast
            [0.72, alert_height - 0.2, 0.85, 1.35, -0.9, 16.5],         # Zoom in focus - quick
            [0.7, alert_height - 0.18, 0.87, 1.37, -1.8, 14.5],         # Assess threat level - moderate
            [0.4, alert_height + 0.1, 1.1, 1.4, -1.1, 12.5],            # Relax - false alarm - gentle
            [-0.3, alert_height, 1.05, 1.35, -1.7, 15.0],               # One final check - quick
            [0.0, -0.7, 1.15, 1.38, -1.3, 13.5],                        # All clear, lowering - moderate
            [0.0, -0.82, 1.2, 1.39, -1.6, 12.0],                       # Return to rest - gentle
            [0.0, -0.85, 1.3, 1.4, -1.5, 13.0]                          # Home directly - moderate
        ]
        
        # Alert, purposeful timing with snap movements (base duration * 10 / acceleration)
        durations = [0.46, 0.38, 0.24, 0.47, 0.53, 0.5, 0.52, 0.34, 0.33, 0.42, 0.62, 0.48, 0.47, 0.44, 0.58, 0.62]
        
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
            [0.0, -0.85, 1.3, 1.4, -1.5, 12.0],                                   # Starting position - gentle
            [base_adj * 0.3, -0.78, 1.35, 1.35, -1.3, 15.0],                      # Uncomfortable - quick
            [base_adj * 0.5 - 0.2, -0.95 + shoulder_var, 1.2, 1.5, -1.8, 14.5],   # Roll shoulder left - moderate
            [base_adj * 0.4, -0.82, 1.32, 1.38, -0.9, 16.0],                      # Test this spot - quick
            [base_adj * 0.6, -0.85 + shoulder_var*0.5, 1.28, 1.42, -2.0, 15.5],   # Nope, adjust more - quick
            [base_adj * 0.5 + 0.2, -0.95 - shoulder_var, 1.2, 1.5, -0.7, 14.0],   # Roll shoulder right - moderate
            [-base_adj * 0.3, -0.75, 1.35, 1.35, -1.7, 16.5],                     # Try leaning - quick
            [-base_adj * 0.5, -0.88, 1.27, 1.43, -1.1, 15.0],                     # Still not comfortable - quick
            [base_adj * 0.7, -0.6, 1.4, 1.2, -1.9, 17.0],                         # Big position change - fast
            [base_adj * 0.3, -0.8, 1.3, 1.4, -0.8, 13.5],                         # This is better - moderate
            [base_adj * 0.15, -0.82, 1.31, 1.39, -1.6, 12.5],                     # Tiny adjustment - gentle
            [base_adj * 0.1, -0.83, 1.3, 1.4, -1.2, 11.5],                        # Another tiny one - gentle
            [0.05, -0.84, 1.3, 1.4, -1.7, 11.0],                                  # Almost perfect - gentle
            [0.0, -0.845, 1.3, 1.4, -1.3, 10.5],                                  # One final shift - very gentle
            [0.0, -0.85, 1.1, 1.4, -1.6, 10.0],                                   # Ahh, comfortable - slowest
            [0.0, -0.85, 1.3, 1.4, -1.5, 12.0]                                    # Already home - gentle
        ]
        
        # Fidgety, restless timing (base duration * 10 / acceleration)
        durations = [0.58, 0.4, 0.48, 0.38, 0.45, 0.5, 0.36, 0.4, 0.47, 0.44, 0.64, 0.70, 0.55, 0.76, 0.8, 0.67]
        
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
            [0.0, -0.85, 1.3, 1.4, -1.5, 10.0],                           # Home - slowest
            [0.08, -0.88, 1.27, 1.43, -1.3, 10.5],                        # Subtle drift start - very gentle
            [0.15, -1.1, 1.05, 1.65, -1.8, 10.0],                         # Float gently up - slowest
            [-drift_radius*0.8, -1.05, 1.1, 1.6, -0.8, 10.5],             # Arc to left high - very gentle
            [-drift_radius, -1.0, 1.15, 1.55, -2.1, 10.0],                # Suspend at peak - slowest
            [drift_radius*0.6, -0.85, 1.25, 1.45, -0.7, 10.5],            # Fall gently right - very gentle
            [drift_radius*0.9, -0.55, 1.45, 1.15, -1.9, 11.0],            # Swoop down low - gentle
            [drift_radius*0.7, -0.75, 1.3, 1.35, -1.0, 10.5],             # Begin rise - very gentle
            [0.0, -0.9, 1.2, 1.5, -1.7, 10.0],                            # Cross center of 8 - slowest
            [-drift_radius*0.7, -0.8, 1.25, 1.4, -0.9, 10.5],             # Float to opposite - very gentle
            [-0.2, -0.65, 1.35, 1.25, -1.8, 11.5],                        # Slow downward spiral - gentle
            [0.0, -0.75, 1.28, 1.35, -1.1, 11.0],                         # Gravity slowly returns - gentle
            [0.0, -0.82, 1.29, 1.38, -1.6, 10.5],                         # Soft landing approach - very gentle
            [0.0, -0.84, 1.2, 1.39, -1.4, 10.0],                          # Almost settled - slowest
            [0.0, -0.85, 1.3, 1.4, -1.5, 10.0]                            # Home directly - slowest
        ]
        
        # Slow, ethereal timing (base duration * 10 / acceleration)
        durations = [0.8, 0.95, 1.4, 1.52, 2.0, 1.43, 1.18, 1.33, 1.2, 1.43, 1.13, 0.91, 0.76, 0.7, 0.8]
        
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
            [base_pos, -0.85, 1.3, 1.4, -1.5, 12.0],                    # Home - gentle
            [base_pos, -0.8, 1.25, 1.35, -1.3, 11.0],                   # Prepare for stretch - gentle
            [base_pos - 0.4, -0.75, 1.2, 1.3, -1.9, 10.5],              # Tilt head left - very gentle
            [base_pos - 0.6, -0.7, 1.15, 1.25, -0.7, 10.0],             # Deep stretch left side - slowest
            [base_pos - 0.3, -0.9, 1.1, 1.5, -2.2, 10.5],               # Roll head back - very gentle
            [base_pos + 0.4, -0.75, 1.2, 1.3, -0.6, 10.5],              # Tilt head right - very gentle
            [base_pos + 0.6, -0.7, 1.15, 1.25, -1.8, 10.0],             # Deep stretch right - slowest
            [base_pos + 0.3, -0.5, 1.35, 1.05, -1.0, 11.0],             # Roll head forward - gentle
            [base_pos, -0.4, 1.45, 0.95, -2.0, 10.5],                   # Chin to chest stretch - very gentle
            [base_pos, -1.1, 0.9, 1.7, -0.8, 10.0],                     # Look way up, stretch throat - slowest
            [base_pos + 0.05, -0.85, 1.2, 1.4, -1.7, 16.0],             # Quick center adjustment - quick
            [base_pos - 0.05, -0.85, 1.25, 1.4, -1.2, 15.5],            # Relief shake - quick
            [base_pos, -0.83, 1.28, 1.39, -1.6, 12.5],                  # Final position adjust - gentle
            [base_pos, -0.84, 1.2, 1.4, -1.4, 11.5],                   # Relaxed after stretch - gentle
            [base_pos, -0.85, 1.3, 1.4, -1.5, 12.0]                     # Home 2 - gentle
        ]
        
        # Slow stretching movements (base duration * 10 / acceleration)
        durations = [0.5, 0.73, 0.95, 1.5, 1.14, 0.95, 1.5, 1.09, 1.24, 1.8, 0.38, 0.39, 0.48, 0.70, 0.67]
        
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
            [base_pos, -0.85, 1.3, 1.4, -1.5, 12.0],                    # Home - gentle
            [base_pos, -0.75, 1.35, 1.35, -1.3, 11.5],                  # Feeling tired - gentle
            [base_pos, -0.9, 1.15, 1.5, -1.8, 10.5],                    # Yawn beginning - very gentle
            [base_pos - 0.1, -1.05, 1.0, 1.65, -0.7, 10.0],             # Mouth opening wide - slowest
            [base_pos, -1.2, 0.8, 1.8, -2.1, 10.0],                     # Arms stretching up - slowest
            [base_pos + 0.1, -1.35, 0.6, 1.95, -0.6, 10.0],             # Full body extension - slowest
            [base_pos, -1.32, 0.62, 1.93, -1.9, 10.0],                  # Hold at peak - slowest
            [base_pos - 0.05, -1.25, 0.7, 1.85, -0.8, 14.0],            # Shudder during release - moderate
            [base_pos, -1.0, 0.95, 1.6, -1.7, 11.0],                    # Arms coming down - gentle
            [base_pos, -0.8, 1.2, 1.4, -1.1, 12.0],                     # Yawn closing - gentle
            [base_pos, -0.78, 1.25, 1.38, -1.8, 13.0],                  # Sleepy blink - moderate
            [base_pos + 0.15, -0.82, 1.27, 1.4, -1.0, 15.5],            # Shake head to wake - quick
            [base_pos, -0.84, 1.2, 1.4, -1.6, 12.5],                   # Back to normal - gentle
            [base_pos, -0.85, 1.3, 1.4, -1.5, 12.0]                     # Home directly - gentle
        ]
        
        # Yawning rhythm with holds (base duration * 10 / acceleration)
        durations = [0.5, 0.70, 0.95, 1.2, 1.4, 0.8, 2.0, 0.43, 1.09, 0.83, 0.62, 0.45, 0.56, 0.67]
        
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
            [base_pos, -0.85, 1.3, 1.4, -1.5, 14.0],                    # Home - moderate
            [base_pos, -0.75, 1.2, 1.35, -1.3, 16.0],                   # Get ready - quick
            [base_pos + 0.2, -0.85, 1.15, 1.45, -1.8, 18.0],            # Right shoulder up - fast
            [base_pos - 0.2, -0.85, 1.15, 1.45, -0.9, 18.5],            # Left shoulder up - fast
            [base_pos + 0.15, -0.8, 1.18, 1.42, -2.0, 19.0],            # Quick right - fast
            [base_pos - 0.15, -0.8, 1.18, 1.42, -0.7, 19.5],            # Quick left - fast
            [base_pos + 0.25, -0.78, 1.22, 1.38, -1.8, 20.0],           # Double shimmy - fast
            [base_pos - 0.25, -0.78, 1.22, 1.38, -1.0, 20.5],           # Other side - fast
            [base_pos + 0.35, -0.7, 1.25, 1.35, -2.1, 21.0],            # Big shimmy right - very fast
            [base_pos - 0.35, -0.7, 1.25, 1.35, -0.6, 21.5],            # Big shimmy left - very fast
            [base_pos, -0.75, 1.2, 1.4, -1.7, 17.0],                    # Back to center - fast
            [base_pos + 0.1, -0.8, 1.25, 1.38, -1.2, 16.0],             # Final little shake - quick
            [base_pos, -0.83, 1.28, 1.39, -1.6, 13.0],                  # Cool down - moderate
            [base_pos, -0.85, 1.3, 1.4, -1.5, 14.0]                     # Home directly - moderate
        ]
        
        # Rhythmic shimmy timing (base duration * 10 / acceleration)
        durations = [0.36, 0.38, 0.28, 0.27, 0.26, 0.31, 0.25, 0.24, 0.19, 0.19, 0.29, 0.31, 0.54, 0.57]
        
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
            [base_pos, -0.85, 1.3, 1.4, -1.5, 13.0],                    # Home - moderate
            [base_pos, -0.78, 1.25, 1.38, -1.3, 14.0],                  # Slight head lift - moderate
            [base_pos - 0.4, -0.75, 1.22, 1.35, -1.8, 15.0],            # Casual glance left - quick
            [base_pos - 0.35, -0.72, 1.2, 1.32, -0.9, 14.5],            # Hmm, what's that? - moderate
            [base_pos, -0.77, 1.23, 1.37, -1.7, 13.5],                  # Look back to center - moderate
            [base_pos + 0.3, -0.75, 1.22, 1.4, -1.1, 15.5],             # Glance right - quick
            [base_pos + 0.35, -0.85, 1.15, 1.5, -2.0, 14.0],            # Look up and right - moderate
            [base_pos + 0.5, -0.8, 1.2, 1.45, -0.7, 13.0],              # Check behind - moderate
            [base_pos, -0.78, 1.24, 1.38, -1.8, 13.5],                  # Back to center - moderate
            [base_pos - 0.25, -0.76, 1.23, 1.36, -1.0, 16.0],           # Quick left check - quick
            [base_pos, -0.8, 1.26, 1.38, -1.6, 12.5],                   # All good - gentle
            [base_pos, -0.84, 1.29, 1.39, -1.4, 11.5],                  # Settling back - gentle
            [base_pos, -0.85, 1.3, 1.4, -1.5, 13.0]                     # Home directly - moderate
        ]
        
        # Casual, relaxed timing (base duration * 10 / acceleration)
        durations = [0.46, 0.5, 0.67, 0.55, 0.67, 0.71, 0.64, 0.92, 0.59, 0.38, 0.56, 0.52, 0.62]
        
        return keyframes, durations