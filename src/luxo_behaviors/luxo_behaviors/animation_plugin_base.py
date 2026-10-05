#!/usr/bin/env python3
"""
Base class for animation plugins in the LuxoPi system.
Each animation should inherit from this base class and implement the required methods.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict
import random
from luxo_behaviors.animation_plan import validate_animation_plan


class AnimationPlugin(ABC):
    """Base class for all animation plugins."""
    
    def __init__(self, node):
        """
        Initialize the animation plugin.
        
        Args:
            node: The ROS node that owns this plugin (for logging and time)
        """
        self.node = node
        self.noise_amplitude = 0.05  # Default noise for natural movement
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this animation."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a human-readable description of this animation."""
        pass
    
    @abstractmethod
    def get_keyframes(self) -> Tuple[List[List[float]], List[float]]:
        """
        Return the keyframes and durations for this animation.
        
        Returns:
            Tuple of (keyframes, durations) where:
            - keyframes: List of [base, shoulder, elbow, wrist, roll, acceleration]
            - durations: List of durations in seconds for each transition
        """
        pass
    
    def get_keyframe_names(self) -> Optional[List[str]]:
        """
        Return optional names for each keyframe step.
        
        Returns:
            List of descriptive names for each keyframe, or None
        """
        return None
    
    def add_noise_to_position(self, positions: List[float], noise_amplitude: Optional[float] = None) -> List[float]:
        """
        Add subtle random noise to make animations less mechanical.
        
        Args:
            positions: Joint positions to add noise to
            noise_amplitude: Optional amplitude of noise to apply. Defaults to the instance's noise_amplitude.
            
        Returns:
            Joint positions with noise added
        """
        if noise_amplitude is None:
            noise_amplitude = self.noise_amplitude
        
        noisy_positions = []
        for pos in positions:
            noise = random.uniform(-noise_amplitude, noise_amplitude)
            noisy_positions.append(pos + noise)
        return noisy_positions
    
    def validate_keyframes(self) -> bool:
        """
        Validate that the animation keyframes are properly formed.
        
        Returns:
            True if valid, False otherwise
        """
        try:
            validate_animation_plan(
                *self.get_keyframes(), keyframe_names=self.get_keyframe_names()
            )
            return True
        except (TypeError, ValueError) as exc:
            if self.node is not None:
                self.node.get_logger().error(
                    f"Invalid animation plan '{self.name}': {exc}"
                )
            return False
    
    def get_metadata(self) -> Dict:
        """
        Get metadata about this animation.
        
        Returns:
            Dictionary with animation metadata
        """
        keyframes, durations = self.get_keyframes()
        total_duration = sum(durations)
        
        return {
            'name': self.name,
            'description': self.description,
            'total_duration': total_duration,
            'num_keyframes': len(keyframes),
            'keyframe_names': self.get_keyframe_names()
        }

    def adjust_keyframes_to_current_base(self, keyframes: List[List[float]], current_base_position: float) -> List[List[float]]:
        """
        Adjust all keyframes to use the current base position while preserving relative movements.
        
        Args:
            keyframes: Original keyframes from the animation
            current_base_position: Current base joint position
            
        Returns:
            Modified keyframes with adjusted base positions
        """
        if not keyframes:
            return keyframes
        
        adjusted_keyframes = []
        
        # Find the "neutral" base position used in the animation
        # This is typically the first keyframe's base position
        animation_base_reference = keyframes[0][0] if len(keyframes[0]) > 0 else 0.0
        
        for keyframe in keyframes:
            adjusted_keyframe = keyframe.copy()
            if len(adjusted_keyframe) > 0:
                # Calculate the offset from the animation's reference position
                base_offset = keyframe[0] - animation_base_reference
                
                # Apply this offset to the current base position
                adjusted_keyframe[0] = current_base_position + base_offset
                
                # Optional: Clamp to safe limits if needed
                # adjusted_keyframe[0] = max(-1.57, min(1.57, adjusted_keyframe[0]))
            
            adjusted_keyframes.append(adjusted_keyframe)
        
        self.node.get_logger().debug(
            f"Adjusted base positions from reference {animation_base_reference:.2f} "
            f"to current {current_base_position:.2f}"
        )
        
        return adjusted_keyframes

    @property
    def preserve_base_position(self) -> bool:
        """
        Whether this animation should preserve the current base position.
        Override in subclasses to return False for animations that need specific base positions.
        """
        return True

    def prepare_for_current_position(self, current_position: List[float], 
                                   keyframes: List[List[float]]) -> List[List[float]]:
        """
        Adjust the first keyframe to blend from current position.
        
        Args:
            current_position: Current joint positions
            keyframes: Original keyframes
            
        Returns:
            Modified keyframes with smooth transition from current position
        """
        if not keyframes:
            return keyframes
            
        modified_keyframes = [kf.copy() for kf in keyframes]
        
        # Create a blend between current position and first keyframe
        first_keyframe = modified_keyframes[0].copy()
        
        for i in range(min(len(first_keyframe), len(current_position))):
            # Calculate the intended movement
            intended_offset = first_keyframe[i] - current_position[i]
            # Scale it down for smoother transition
            scaled_offset = intended_offset * 0.5
            # Apply the scaled offset to current position
            first_keyframe[i] = current_position[i] + scaled_offset
        
        modified_keyframes[0] = first_keyframe
        
        return modified_keyframes
    
    @abstractmethod
    def get_category(self) -> str:
        """
        Get the category of this animation.
        
        Returns:
            Category string like "emotion", "action", "response", etc.
        """
        pass
