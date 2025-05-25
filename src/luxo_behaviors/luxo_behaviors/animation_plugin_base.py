#!/usr/bin/env python3
"""
Base class for animation plugins in the LuxoPi system.
Each animation should inherit from this base class and implement the required methods.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict
import random


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
            - keyframes: List of joint positions [base, shoulder, elbow, wrist, hand]
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
    
    def add_noise_to_position(self, positions: List[float]) -> List[float]:
        """
        Add subtle random noise to make animations less mechanical.
        
        Args:
            positions: Joint positions to add noise to
            
        Returns:
            Joint positions with noise added
        """
        noisy_positions = []
        for pos in positions:
            noise = random.uniform(-self.noise_amplitude, self.noise_amplitude)
            noisy_positions.append(pos + noise)
        return noisy_positions
    
    def validate_keyframes(self) -> bool:
        """
        Validate that the animation keyframes are properly formed.
        
        Returns:
            True if valid, False otherwise
        """
        try:
            keyframes, durations = self.get_keyframes()
            
            # Check that we have keyframes
            if not keyframes or not durations:
                self.node.get_logger().error(f"Animation '{self.name}' has no keyframes or durations")
                return False
            
            # Check that keyframes and durations match
            if len(keyframes) != len(durations):
                self.node.get_logger().error(
                    f"Animation '{self.name}' has mismatched keyframes ({len(keyframes)}) "
                    f"and durations ({len(durations)})"
                )
                return False
            
            # Check that all keyframes have 5 joint values
            for i, keyframe in enumerate(keyframes):
                if len(keyframe) != 5:
                    self.node.get_logger().error(
                        f"Animation '{self.name}' keyframe {i} has {len(keyframe)} joints, expected 5"
                    )
                    return False
            
            # Check that all durations are positive
            for i, duration in enumerate(durations):
                if duration <= 0:
                    self.node.get_logger().error(
                        f"Animation '{self.name}' duration {i} is not positive: {duration}"
                    )
                    return False
            
            return True
            
        except Exception as e:
            self.node.get_logger().error(f"Error validating animation '{self.name}': {e}")
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