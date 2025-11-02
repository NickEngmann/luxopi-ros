#!/usr/bin/env python3
#idle_behavior.py
"""
Idle behavior module for Luxo robot.
Handles idle animations and head variations.
"""

import random
import time
from typing import Optional, List
from rclpy.action import ActionClient
from std_msgs.msg import Bool
from luxo_interfaces.action import PlayAnimation
from luxo_behaviors.state_machine import LuxoState
from luxo_behaviors.shared_utils import IdleAnimationConfig
import numpy as np


class IdleBehavior:
    """Mixin class for idle behavior functionality."""
    
    def setup_idle_behavior(self):
        """Initialize idle behavior attributes and action clients."""
        # Idle animation configuration
        self.idle_config = IdleAnimationConfig()
        self.idle_animations = self.idle_config.idle_animations
        self.idle_animations_enabled = True  # Can be disabled if needed
        
        # Idle animation tracking
        self.last_idle_animation = None
        self.min_idle_time_before_animation = self.idle_config.min_idle_time_before_animation
        self.idle_animation_interval = random.uniform(
            self.idle_config.idle_animation_interval_min, 
            self.idle_config.idle_animation_interval_max
        )
        self.last_idle_animation_time = self.node.get_clock().now()
        
        # Idle head variation tracking
        self.idle_head_variation_enabled = False  # Will be set by hardware interface
        self.idle_head_variation_interval = 1.25  # Maximum interval - actual will be random 0.2 to this value (very frequent)
        self.idle_head_base_rotation_range = 0.5  # Back to original for more movement
        self.idle_head_look_up_range = 0.75  # Increased 15% for more upward movement
        self.idle_head_look_down_range = 0.1  # Decreased 20% to reduce downward movement
        self.last_idle_head_variation_time = self.node.get_clock().now()
        self.current_idle_head_target = None
        self.idle_head_variation_active = False
        self.idle_base_position = [0.0, -0.55, 1.2, 1.0, 2.0]  # Standard idle position (without antenna)
        self.idle_antenna_min = 0.9  # Minimum antenna position
        self.idle_antenna_max = 2.2  # Maximum antenna position
        
        # Create action client for triggering animations
        self._idle_animation_client = ActionClient(
            self.node,
            PlayAnimation,
            'play_animation'
        )

        # Store original idle timing values for demo mode restoration
        self.original_min_idle_time = self.min_idle_time_before_animation
        self.original_idle_interval_min = self.idle_config.idle_animation_interval_min
        self.original_idle_interval_max = self.idle_config.idle_animation_interval_max

        # Subscribe to rainbow mode to reduce idle time during demo mode
        self.rainbow_mode_active = False
        self.rainbow_mode_sub = self.node.create_subscription(
            Bool,
            '/luxo/rainbow_mode',
            self.rainbow_mode_callback,
            10
        )

        self.node.get_logger().info("Idle behavior initialized")

    def rainbow_mode_callback(self, msg):
        """Handle rainbow mode changes - reduce idle time during demo mode."""
        self.rainbow_mode_active = msg.data

        if self.rainbow_mode_active:
            # Demo mode: Reduce idle times for more frequent interactions
            self.min_idle_time_before_animation = 2.0  # Reduced from 5.0
            self.idle_config.idle_animation_interval_min = 3.0  # Reduced from 10.0
            self.idle_config.idle_animation_interval_max = 15.0  # Reduced from 60.0

            # Update current interval if needed (set to new random value in demo range)
            self.idle_animation_interval = random.uniform(
                self.idle_config.idle_animation_interval_min,
                self.idle_config.idle_animation_interval_max
            )

            self.node.get_logger().info(
                f"🌈 Demo mode: Idle times reduced - "
                f"min: {self.min_idle_time_before_animation}s, "
                f"interval: {self.idle_config.idle_animation_interval_min}-{self.idle_config.idle_animation_interval_max}s"
            )
        else:
            # Normal mode: Restore original idle times
            self.min_idle_time_before_animation = self.original_min_idle_time
            self.idle_config.idle_animation_interval_min = self.original_idle_interval_min
            self.idle_config.idle_animation_interval_max = self.original_idle_interval_max

            # Update current interval to normal range
            self.idle_animation_interval = random.uniform(
                self.idle_config.idle_animation_interval_min,
                self.idle_config.idle_animation_interval_max
            )

            self.node.get_logger().info(
                f"Normal mode: Idle times restored - "
                f"min: {self.min_idle_time_before_animation}s, "
                f"interval: {self.idle_config.idle_animation_interval_min}-{self.idle_config.idle_animation_interval_max}s"
            )

    def check_idle_animations(self, current_time) -> bool:
        """
        Check if we should trigger an idle animation.
        Returns True if an animation was triggered.
        """
        # Only trigger idle animations in IDLE state
        if not self._is_in_state(LuxoState.IDLE):
            return False
        
        # Check if idle animations are enabled
        if not getattr(self, 'idle_animations_enabled', True):
            return False
        
        # Check for any active collisions
        if any(status['active'] for status in self.collision_status.values()):
            return False
        
        time_since_activity = (current_time - self.last_activity_time).nanoseconds / 1e9
        time_since_last_animation = (current_time - self.last_idle_animation_time).nanoseconds / 1e9
        
        # Check if voice is very active (only very recent voice should affect idle)
        voice_very_active = False
        if hasattr(self, 'voice_active') and self.voice_active and hasattr(self, 'last_voice_time'):
            if self.last_voice_time is not None:
                time_since_voice = (current_time - self.last_voice_time).nanoseconds / 1e9
            else:
                time_since_voice = float('inf')
            voice_very_active = time_since_voice < 2.0  # Only consider very recent voice activity
        
        if voice_very_active:
            self.node.get_logger().debug("Very recent voice activity - allowing idle animations to coexist")
        
        # If we've been idle for a while and enough time has passed since last animation
        if (time_since_activity > self.min_idle_time_before_animation and 
            time_since_last_animation > self.idle_animation_interval):
            
            self.node.get_logger().info(
                f"Device idle for {time_since_activity:.1f}s - triggering idle animation "
                f"(voice influence: {getattr(self, 'voice_influence', 0.0):.2f})"
            )
            
            # Trigger a random idle animation
            self.trigger_idle_animation()
            
            # Update timers
            self.last_idle_animation_time = current_time
            self.idle_animation_interval = random.uniform(
                self.idle_config.idle_animation_interval_min,
                self.idle_config.idle_animation_interval_max
            )
            
            return True
        
        return False
    
    def trigger_idle_animation(self):
        """Trigger a random idle animation."""
        try:
            # Don't trigger if not in IDLE state or action client not ready
            if not self._is_in_state(LuxoState.IDLE):
                return
                
            if not self._idle_animation_client.wait_for_server(timeout_sec=1.0):
                self.node.get_logger().warn("Animation action server not available for idle animation")
                return
            
            # Only clear idle head variation, not voice following
            if self.idle_head_variation_active:
                self.idle_head_variation_active = False
                self.current_idle_head_target = None
                self.node.get_logger().info("Cleared idle head variation for animation")
            
            # Allow voice following to continue during idle animations
            current_voice_influence = getattr(self, 'voice_influence', 0.0)
            if current_voice_influence > 0.1:
                self.node.get_logger().info(
                    f"Triggering idle animation while voice following active "
                    f"(influence: {current_voice_influence:.2f})"
                )
            
            # Select a random animation, avoiding the last one
            available_animations = [a for a in self.idle_animations if a != self.last_idle_animation]
            if not available_animations:
                available_animations = self.idle_animations
                
            selected_animation = random.choice(available_animations)
            self.last_idle_animation = selected_animation
            
            # Create goal for idle animation
            goal = PlayAnimation.Goal()
            goal.animation_name = selected_animation

            # Speed up animations during rainbow demo mode for more energy
            if self.rainbow_mode_active:
                goal.speed_multiplier = random.uniform(1.2, 1.4)  # 1.3x average speed in demo mode
            else:
                goal.speed_multiplier = random.uniform(0.8, 1.2)  # Slight speed variation (normal)

            goal.allow_interruption = True  # Always allow interruption for idle animations
            goal.use_hardware_feedback = False

            mode_indicator = "🌈" if self.rainbow_mode_active else ""
            self.node.get_logger().info(
                f"{mode_indicator}Triggering idle animation: {selected_animation} "
                f"(speed: {goal.speed_multiplier:.1f}x)"
            )
            
            # Send goal asynchronously
            future = self._idle_animation_client.send_goal_async(goal)
            future.add_done_callback(self._idle_animation_response_callback)
            
            # Update activity time to prevent immediate re-triggering
            self.last_activity_time = self.node.get_clock().now()
            
        except Exception as e:
            self.node.get_logger().error(f"Error triggering idle animation: {e}")
    
    def _idle_animation_response_callback(self, future):
        """Handle the response from idle animation goal."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.node.get_logger().info("Idle animation goal rejected")
                return
            
            self.node.get_logger().info("Idle animation goal accepted")
            
        except Exception as e:
            self.node.get_logger().error(f"Error in idle animation response: {e}")
    
    def check_idle_head_variation(self, current_time) -> bool:
        """
        Check if we should apply idle head variation.
        Returns True if variation is active.
        """
        self.node.get_logger().debug(f"Checking idle head variation: enabled={self.idle_head_variation_enabled}, voice_influence={getattr(self, 'voice_influence', 0.0)}")
        # Only apply idle head variations in IDLE state
        if not self._is_in_state(LuxoState.IDLE):
            self.idle_head_variation_active = False
            self.current_idle_head_target = None
            return False

        # Check if enabled
        if not self.idle_head_variation_enabled:
            return False

        # Modified: Allow idle head variations even during voice following
        # This keeps the robot looking alive while tracking voice
        # We'll preserve the base angle from voice following but vary other joints
        
        # Check if it's time for a new variation
        time_since_last_variation = (current_time - self.last_idle_head_variation_time).nanoseconds / 1e9

        # Use very short intervals for continuous movement
        current_interval = getattr(self, '_current_idle_variation_interval', self.idle_head_variation_interval)

        if time_since_last_variation > current_interval:
            # Generate new idle head target
            self._generate_idle_head_variation()

            # Set new random interval for next variation - much shorter for rapid movement
            self._current_idle_variation_interval = random.uniform(0.1, self.idle_head_variation_interval)
            self.last_idle_head_variation_time = current_time
            
            return True
        
        return self.idle_head_variation_active
    
    def _generate_idle_head_variation(self):
        """Generate a new idle head variation target with more lifelike movement patterns."""
        try:
            # Start with current position
            base_position = self.current_joints.copy()

            # Check if voice following is active
            voice_is_active = hasattr(self, 'voice_influence') and self.voice_influence > 0.1

            # Decide movement pattern - prioritize sequential fluid movements
            movement_type = random.random()

            if movement_type < 0.60:  # 60% - Sequential joint movement (fluid thinking feel)
                self._generate_sequential_movement(base_position, preserve_base=voice_is_active)
            elif movement_type < 0.75:  # 15% - Paired joint movement
                self._generate_paired_movement(base_position, preserve_base=voice_is_active)
            elif movement_type < 0.90:  # 15% - Full coordinated movement
                self._generate_full_movement(base_position, preserve_base=voice_is_active)
            elif movement_type < 0.97:  # 7% - Single joint with antenna
                self._generate_single_joint_movement(base_position, preserve_base=voice_is_active)
            else:  # 3% - Just antenna expression (minimal)
                self._generate_antenna_only_movement(base_position)

            # Set the new target
            self.current_idle_head_target = base_position
            self.idle_head_variation_active = True

        except Exception as e:
            self.node.get_logger().error(f"Error generating idle head variation: {e}")
            self.idle_head_variation_active = False

    def _generate_single_joint_movement(self, base_position, preserve_base=False):
        """Move a single joint with antenna expression."""
        # Choose which joint to move (exclude base if preserving for voice)
        if preserve_base:
            joint_choice = random.choice(['shoulder', 'elbow', 'wrist'])
        else:
            joint_choice = random.choice(['base', 'shoulder', 'elbow', 'wrist'])

        # Ensure we have space for antenna and acceleration
        while len(base_position) < 7:
            if len(base_position) == 5:
                base_position.append(random.uniform(7.0, 20.0))  # Varying acceleration
            else:
                base_position.append(0.0)

        # Apply movement to chosen joint - much more dramatic variations
        if joint_choice == 'base':
            variation = random.uniform(-self.idle_head_base_rotation_range*1.2,
                                     self.idle_head_base_rotation_range*1.2)  # Bigger movements
            new_base = self.position_utils.normalize_angle(base_position[0] + variation)
            base_position[0] = np.clip(new_base, self.base_min_limit, self.base_max_limit)
            # Antenna follows base rotation - turning head shows interest
            base_position[6] = self._get_expressive_antenna(emotion='curious', intensity=abs(variation)*3)
        elif joint_choice == 'shoulder':
            # Strong bias towards looking up (negative variation) with bigger movements
            variation = random.uniform(-0.6, 0.25)  # Much bigger range, strong upward bias
            base_position[1] = self.idle_base_position[1] + variation
            # Antenna expresses the looking direction
            base_position[6] = self._get_expressive_antenna(
                emotion='alert' if variation < 0 else 'content',
                intensity=abs(variation)*2.5
            )
        elif joint_choice == 'elbow':
            variation = random.uniform(-0.15, 0.15)  # Bigger movements
            base_position[2] = self.idle_base_position[2] + variation
            # Subtle antenna adjustment
            base_position[6] = self._get_expressive_antenna(emotion='thinking', intensity=1.2)
        else:  # wrist
            variation = random.uniform(-0.08, 0.08)  # Bigger movements
            base_position[3] = self.idle_base_position[3] + variation
            # Small antenna twitch
            base_position[6] = self._get_expressive_antenna(emotion='subtle', intensity=1.1)

        # Faster acceleration for more responsive movement
        base_position[5] = random.uniform(12.0, 22.0)

        self.node.get_logger().debug(f"Single joint movement: {joint_choice}")

    def _generate_sequential_movement(self, base_position, preserve_base=False):
        """Create a true cascading sequential movement through joints."""
        # Initialize sequential state if needed
        if not hasattr(self, '_sequential_state'):
            self._sequential_state = 0
            self._sequential_targets = {}

        # Ensure we have space for antenna and acceleration
        while len(base_position) < 7:
            if len(base_position) == 5:
                base_position.append(20.0)  # Fast acceleration for rapid cascading
            else:
                base_position.append(0.0)

        # Define target positions for full movement
        if self._sequential_state == 0:
            # Generate new target positions
            if preserve_base:
                # Keep base unchanged when voice following
                base_var = 0.0
                new_base = base_position[0]
            else:
                base_var = random.uniform(-0.4, 0.4)  # Much larger movements
                new_base = self.position_utils.normalize_angle(base_position[0] + base_var)

            shoulder_var = random.uniform(-0.5, 0.2)  # Strong upward bias, bigger range
            elbow_var = random.uniform(-0.15, 0.15)
            wrist_var = random.uniform(-0.08, 0.08)

            self._sequential_targets = {
                'base': np.clip(new_base, self.base_min_limit, self.base_max_limit) if not preserve_base else base_position[0],
                'shoulder': self.idle_base_position[1] + shoulder_var,
                'elbow': self.idle_base_position[2] + elbow_var,
                'wrist': self.idle_base_position[3] + wrist_var,
                'antenna': self._get_expressive_antenna(
                    emotion='curious' if shoulder_var < 0 else 'content',
                    intensity=1.5
                )
            }

        # Apply movement in cascade based on state
        if self._sequential_state == 0:
            # First move base and antenna (like head turning with expression)
            base_position[0] = self._sequential_targets['base']
            base_position[6] = self._sequential_targets['antenna'] * 0.8  # Start antenna movement
            self._sequential_state = 1
        elif self._sequential_state == 1:
            # Add shoulder movement
            base_position[0] = self._sequential_targets['base']
            base_position[1] = self._sequential_targets['shoulder']
            base_position[6] = self._sequential_targets['antenna'] * 0.9
            self._sequential_state = 2
        elif self._sequential_state == 2:
            # Add elbow movement
            base_position[0] = self._sequential_targets['base']
            base_position[1] = self._sequential_targets['shoulder']
            base_position[2] = self._sequential_targets['elbow']
            base_position[6] = self._sequential_targets['antenna']
            self._sequential_state = 3
        else:
            # Final - add wrist
            base_position[0] = self._sequential_targets['base']
            base_position[1] = self._sequential_targets['shoulder']
            base_position[2] = self._sequential_targets['elbow']
            base_position[3] = self._sequential_targets['wrist']
            base_position[6] = self._sequential_targets['antenna']
            self._sequential_state = 0  # Reset for next sequence

        # Fast acceleration for snappy sequential movement
        base_position[5] = random.uniform(15.0, 25.0)

        self.node.get_logger().debug(f"Sequential movement state: {self._sequential_state}")

    def _generate_paired_movement(self, base_position, preserve_base=False):
        """Move 2-3 joints together for coordinated expression."""
        # Choose joint pairs that work well together (avoid look_around if preserving base)
        if preserve_base:
            pair_type = random.choice(['lean', 'gesture', 'lean'])  # Weight towards lean since look_around is limited
        else:
            pair_type = random.choice(['look_around', 'lean', 'gesture'])

        # Ensure we have space for antenna and acceleration
        while len(base_position) < 7:
            if len(base_position) == 5:
                base_position.append(12.0)
            else:
                base_position.append(0.0)

        if pair_type == 'look_around':
            # Base and shoulder move together for looking - much more dramatic
            if preserve_base:
                # Only move shoulder when preserving base for voice
                base_var = 0.0
                shoulder_var = random.uniform(-0.45, 0.2)  # Strong bias towards looking up, bigger range
                # Don't modify base when preserving
            else:
                base_var = random.uniform(-0.5, 0.5)  # Big sweeping looks
                shoulder_var = random.uniform(-0.45, 0.2)  # Strong bias towards looking up, bigger range
                new_base = self.position_utils.normalize_angle(base_position[0] + base_var)
                base_position[0] = np.clip(new_base, self.base_min_limit, self.base_max_limit)

            base_position[1] = self.idle_base_position[1] + shoulder_var
            # Antenna shows interest level
            base_position[6] = self._get_expressive_antenna(
                emotion='interested',
                intensity=abs(shoulder_var)*2.5 if preserve_base else abs(base_var)*2.5
            )
        elif pair_type == 'lean':
            # Shoulder and elbow for leaning motion - much more expressive
            shoulder_var = random.uniform(-0.4, 0.2)  # Bigger range, stronger upward bias
            elbow_var = random.uniform(-0.15, 0.15)  # Bigger movements
            base_position[1] = self.idle_base_position[1] + shoulder_var
            base_position[2] = self.idle_base_position[2] + elbow_var
            # Antenna shows effort/relaxation
            base_position[6] = self._get_expressive_antenna(
                emotion='focused' if shoulder_var < 0 else 'relaxed',
                intensity=1.5
            )
        else:  # gesture
            # Elbow and wrist for gestures - more noticeable
            elbow_var = random.uniform(-0.12, 0.12)  # Bigger
            wrist_var = random.uniform(-0.1, 0.1)  # Bigger
            base_position[2] = self.idle_base_position[2] + elbow_var
            base_position[3] = self.idle_base_position[3] + wrist_var
            # Antenna adds personality
            base_position[6] = self._get_expressive_antenna(emotion='playful', intensity=1.3)

        # Faster acceleration for snappier movements
        base_position[5] = random.uniform(12.0, 20.0)

        self.node.get_logger().debug(f"Paired movement: {pair_type}")

    def _generate_antenna_only_movement(self, base_position):
        """Just move the antenna for pure expression."""
        # Ensure we have space for antenna and acceleration
        while len(base_position) < 7:
            if len(base_position) == 5:
                base_position.append(random.uniform(20.0, 35.0))  # Quick antenna movements
            else:
                base_position.append(0.0)

        # Keep other joints mostly stable with tiny variations
        if random.random() < 0.3:  # 30% chance of tiny body adjustment
            base_position[0] += random.uniform(-0.02, 0.02)
            base_position[0] = np.clip(base_position[0], self.base_min_limit, self.base_max_limit)

        # Generate expressive antenna movement
        expression_type = random.choice([
            'thinking', 'alert', 'curious', 'content',
            'playful', 'focused', 'surprised', 'subtle'
        ])

        base_position[6] = self._get_expressive_antenna(emotion=expression_type)
        base_position[5] = random.uniform(15.0, 30.0)  # Snappy antenna movement

        self.node.get_logger().debug(f"Antenna expression: {expression_type}")

    def _generate_full_movement(self, base_position, preserve_base=False):
        """Original full coordinated movement with enhanced antenna expression."""
        if preserve_base:
            # Don't modify base when voice following is active
            base_variation = 0.0
        else:
            # Generate random variation for base rotation
            base_variation = random.uniform(
                -self.idle_head_base_rotation_range,
                self.idle_head_base_rotation_range
            )

            # Apply variation to base, keeping within limits
            new_base = self.position_utils.normalize_angle(base_position[0] + base_variation)
            new_base = np.clip(new_base, self.base_min_limit, self.base_max_limit)
            base_position[0] = new_base

        # For other joints, use the idle base position as reference with strong looking up bias
        look_type = random.random()
        if look_type < 0.85:  # Look up (85% chance - much more common)
            shoulder_variation = random.uniform(0.2, self.idle_head_look_up_range)  # Much more dramatic upward
            base_position[1] = self.idle_base_position[1] - shoulder_variation
            variation_description = f"looking up (+{shoulder_variation:.2f})"
            emotion = 'alert' if shoulder_variation > 0.4 else 'curious'
        elif look_type < 0.95:  # Stay neutral (10% chance)
            base_position[1] = self.idle_base_position[1]
            variation_description = "staying neutral"
            emotion = 'content'
        else:  # Look down slightly (5% chance - rare)
            base_position[1] = self.idle_base_position[1]
            variation_description = "staying neutral"
            emotion = 'content'

        # Use base idle position for elbow, wrist, hand with small variations
        base_position[2] = self.idle_base_position[2]
        base_position[3] = self.idle_base_position[3]
        base_position[4] = self.idle_base_position[4]

        # Add more frequent tiny variations to other joints for continuous movement
        if random.random() < 0.7:  # Very frequent
            base_position[2] += random.uniform(-0.025, 0.025)  # Slightly larger range
        if random.random() < 0.6:
            base_position[3] += random.uniform(-0.02, 0.02)

        # Ensure we have space for antenna and acceleration
        while len(base_position) < 7:
            if len(base_position) == 5:
                base_position.append(random.uniform(5.0, 18.0))  # Varying acceleration
            else:
                base_position.append(0.0)

        # Generate expressive antenna movement based on overall motion
        base_position[6] = self._get_expressive_antenna(
            emotion=emotion,
            intensity=abs(base_variation)*2 + abs(shoulder_variation if 'shoulder_variation' in locals() else 0)
        )
        base_position[5] = random.uniform(15.0, 25.0)  # Much more dynamic acceleration

        self.node.get_logger().info(
            f"Full movement: base {np.rad2deg(base_variation):.1f}°, {variation_description}"
        )

    def _get_expressive_antenna(self, emotion='neutral', intensity=1.0):
        """Generate antenna position based on emotion and intensity.
        The antenna acts like an eyebrow - crucial for expression."""

        # Base positions for different emotions (0.5 to 2.6 range)
        antenna_emotions = {
            'alert': (2.0, 2.6),      # Perked up, attentive
            'curious': (1.8, 2.4),    # Raised, interested
            'thinking': (1.4, 2.0),   # Mid-high, contemplative
            'content': (1.2, 1.8),    # Neutral-comfortable
            'relaxed': (0.8, 1.4),    # Lowered, calm
            'tired': (0.5, 1.0),      # Drooped
            'playful': (1.5, 2.5),    # Dynamic range
            'focused': (1.6, 2.2),    # Concentrated
            'surprised': (2.2, 2.6),  # Raised high
            'interested': (1.7, 2.3), # Moderately raised
            'subtle': (1.0, 1.6),     # Small movements
            'neutral': (1.0, 2.0)     # Default range
        }

        # Get range for emotion
        min_pos, max_pos = antenna_emotions.get(emotion, (1.0, 2.0))

        # Add some randomness within the emotional range
        base_position = random.uniform(min_pos, max_pos)

        # Apply intensity modifier (0.5 to 1.5 typical)
        intensity = np.clip(intensity, 0.3, 2.0)

        # For playful emotion, add extra variation
        if emotion == 'playful':
            base_position += random.uniform(-0.3, 0.3) * intensity

        # For thinking, add small oscillation range
        if emotion == 'thinking':
            base_position += random.uniform(-0.15, 0.15)

        # Ensure within physical limits
        return np.clip(base_position, self.idle_antenna_min, self.idle_antenna_max)
    
    def apply_idle_head_variation(self, positions: List[float]) -> List[float]:
        """
        Apply idle head variation to joint positions if active.

        Args:
            positions: Current joint positions

        Returns:
            Modified positions with idle variation applied
        """
        if not self.idle_head_variation_active or not self.current_idle_head_target:
            return positions

        # Only apply in IDLE state
        if not self._is_in_state(LuxoState.IDLE):
            self.idle_head_variation_active = False
            self.current_idle_head_target = None
            return positions

        # Modified: Allow idle head variations even with voice following
        # When voice is active, we preserve the base from voice following
        # but apply idle variations to other joints
        if hasattr(self, 'voice_influence') and self.voice_influence > 0.1:
            # Mix voice base with idle variations for other joints
            mixed_position = positions.copy()
            # Keep base from voice following (positions[0])
            # Apply idle variations to other joints
            for i in range(1, min(len(positions), len(self.current_idle_head_target))):
                mixed_position[i] = self.current_idle_head_target[i]
            return mixed_position

        # Use the idle head target
        return self.current_idle_head_target.copy()
    
    def check_extended_idle_timeout(self, current_time) -> bool:
        """
        Check if robot has been idle long enough to return home.
        Returns True if we should return home.
        """
        time_since_activity = (current_time - self.last_activity_time).nanoseconds / 1e9
        
        # Check if we're already at home position
        already_at_home = self._at_position(self.current_joints, self.home_position_2, self.home_position_tolerance)
        
        # Extended idle timeout
        if (time_since_activity > 180.0 and  # 3 minutes
            self._is_in_state(LuxoState.IDLE) and 
            not already_at_home):
            
            self.node.get_logger().info(
                f"Device idle for {time_since_activity:.1f}s - returning to home position"
            )
            
            # Request state transition to RETURNING_HOME
            if self._transition_to_state(LuxoState.RETURNING_HOME):
                self.is_returning_to_rest = True
                self.go_to_rest_position("Extended idle timeout")
                return True
            else:
                self.node.get_logger().warn("Failed to transition to RETURNING_HOME state")
        
        return False