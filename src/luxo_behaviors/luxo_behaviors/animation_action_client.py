#!/usr/bin/env python3
"""
Example client for the animation action server.
Shows how to send animation goals and handle feedback/results.
"""

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from luxo_interfaces.action import PlayAnimation
import sys


class AnimationActionClient(Node):
    def __init__(self):
        super().__init__('animation_action_client')
        self._action_client = ActionClient(
            self, 
            PlayAnimation, 
            'play_animation'
        )
        
        self.get_logger().info('Animation action client initialized')
    
    def send_goal(self, animation_name, speed=1.0, allow_interruption=True):
        """Send an animation goal to the action server."""
        goal_msg = PlayAnimation.Goal()
        goal_msg.animation_name = animation_name
        goal_msg.speed_multiplier = speed
        goal_msg.allow_interruption = allow_interruption
        goal_msg.use_hardware_feedback = True
        
        self.get_logger().info(f'Waiting for action server...')
        if not self._action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('Action server not available!')
            return None
        
        self.get_logger().info(f'Sending goal: {animation_name} (speed: {speed})')
        
        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        
        self._send_goal_future.add_done_callback(self.goal_response_callback)
        
        return self._send_goal_future
    
    def goal_response_callback(self, future):
        """Handle the goal response from the server."""
        goal_handle = future.result()
        
        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected!')
            return
        
        self.get_logger().info('Goal accepted!')
        
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)
    
    def get_result_callback(self, future):
        """Handle the final result of the animation."""
        result = future.result().result
        
        self.get_logger().info('='*50)
        self.get_logger().info('Animation Result:')
        self.get_logger().info(f'  Success: {result.success}')
        self.get_logger().info(f'  Message: {result.message}')
        self.get_logger().info(f'  Duration: {result.actual_duration:.2f}s')
        self.get_logger().info(f'  Collision interruptions: {result.collision_interruptions}')
        self.get_logger().info(f'  Final state: {result.final_state}')
        self.get_logger().info(f'  Final positions: {[round(p, 2) for p in result.final_positions]}')
        self.get_logger().info('='*50)
        
        # Shutdown after receiving result
        rclpy.shutdown()
    
    def feedback_callback(self, feedback_msg):
        """Handle feedback during animation execution."""
        feedback = feedback_msg.feedback
        
        progress_bar = '█' * int(feedback.progress * 20)
        progress_bar = progress_bar.ljust(20, '░')
        
        self.get_logger().info(
            f'Progress: [{progress_bar}] {feedback.progress*100:.1f}% | '
            f'Step: {feedback.current_keyframe+1}/{feedback.total_keyframes} - '
            f'{feedback.current_step_name} | '
            f'Collision: {feedback.collision_status} | '
            f'Time remaining: {feedback.time_remaining:.1f}s'
        )
    
    def cancel_goal(self):
        """Cancel the current goal."""
        if hasattr(self, '_send_goal_future'):
            goal_handle = self._send_goal_future.result()
            
            self.get_logger().info('Canceling goal...')
            cancel_future = goal_handle.cancel_goal_async()
            
            # You could add a callback here to handle the cancel response
            return cancel_future
        else:
            self.get_logger().warn('No active goal to cancel')
            return None


def main(args=None):
    rclpy.init(args=args)
    
    # Get animation name from command line
    if len(sys.argv) < 2:
        print("Usage: ros2 run luxo_behaviors animation_action_client <animation_name> [speed]")
        print("Available animations: excited, sad, playful, curious, think, stretch, dance, nod, shake, idle")
        return
    
    animation_name = sys.argv[1]
    speed = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    
    client = AnimationActionClient()
    
    # Send the goal
    future = client.send_goal(animation_name, speed)
    
    if future:
        rclpy.spin(client)
    
    client.destroy_node()


if __name__ == '__main__':
    main()