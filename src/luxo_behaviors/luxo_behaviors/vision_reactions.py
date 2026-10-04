"""Shared live/sim detection-boundary emotion policy, without capture SDK imports."""
import numpy as np

EMOTION_ANIMATIONS = {
    'happy': ['excited', 'playful', 'dance'],
    'sad': ['sad'],
    'surprise': ['startled', 'curious'],
    'anger': ['shake', 'think', 'startled'],
    'neutral': ['idle', 'stretch', 'nod']
}


class VisionReactionMixin:
    def _can_trigger_emotion_animation(self) -> bool:
        """Check if we can trigger an emotion-based animation right now."""
        current_time = self.get_clock().now()
        
        # Check if any animation is currently running
        if self.current_animation_name:
            self.get_logger().debug(f"Cannot trigger emotion animation: '{self.current_animation_name}' is currently running")
            return False
        
        # Check if we're in a state that allows emotion animations
        if self.current_state not in ['IDLE', 'EMOTION_REACTING']:
            self.get_logger().debug(f"Cannot trigger emotion animation in state: {self.current_state}")
            return False
        
        # Check post-animation delay (after ANY animation, not just emotion ones)
        time_since_any_animation = (current_time - self.last_any_animation_end_time).nanoseconds / 1e9
        if time_since_any_animation < self.post_animation_delay:
            remaining_delay = self.post_animation_delay - time_since_any_animation
            self.get_logger().debug(f"Post-animation delay active: {remaining_delay:.1f}s remaining")
            return False
        
        # Check emotion-specific cooldown
        time_since_last_emotion_animation = (current_time - self.last_animation_time).nanoseconds / 1e9
        if time_since_last_emotion_animation < self.emotion_cooldown:
            remaining_cooldown = self.emotion_cooldown - time_since_last_emotion_animation
            self.get_logger().debug(f"Emotion cooldown active: {remaining_cooldown:.1f}s remaining")
            return False
        
        # Check if there's an active goal handle
        if self._active_goal_handle and not getattr(self._active_goal_handle, '_finished', False):
            self.get_logger().debug("Cannot trigger emotion animation: active goal handle exists")
            return False
        
        return True

    def process_emotion_buffer(self):
        """Process the emotion buffer and trigger an animation if conditions are met"""
        current_time = self.get_clock().now()
        
        # Check if we've collected enough data and if the buffer duration has elapsed
        if (len(self.emotion_buffer) > 0 and 
                ((current_time - self.emotion_buffer_start_time).nanoseconds / 1e9) >= self.emotion_buffer_duration):
            
            # Early check if we can trigger animations at all
            if not self._can_trigger_emotion_animation():
                self.get_logger().debug("Clearing emotion buffer - cannot trigger animation right now")
                # Reset the buffer and start time
                self.emotion_buffer.clear()
                self.emotion_buffer_start_time = current_time
                return
            
            # Get the current elapsed time since last animation
            time_since_last_animation = (current_time - self.last_animation_time).nanoseconds / 1e9
            
            # Count occurrences of each emotion in the buffer
            emotion_counts = {}
            valid_distances = []
            
            for emotion, distance, timestamp in self.emotion_buffer:
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
                # Filter out invalid distance readings (0.00m or >4.0m likely errors)
                if distance is not None and 0.3 < distance < 4.0:
                    valid_distances.append(distance)
            
            # Calculate average distance from valid readings only
            avg_distance = None
            if valid_distances:
                avg_distance = sum(valid_distances) / len(valid_distances)
                if self.verbose:
                    self.get_logger().debug(f"Valid distances: {len(valid_distances)}/{len(self.emotion_buffer)}, avg: {avg_distance:.2f}m")
            
            # Check if we have at least 3 emotion samples
            if len(self.emotion_buffer) < 3:
                self.get_logger().debug(f"Not enough emotion samples ({len(self.emotion_buffer)}), need at least 3")
                # Reset buffer and start time
                self.emotion_buffer.clear()
                self.emotion_buffer_start_time = current_time
                return
            
            # Find the most common emotion
            if emotion_counts:
                # Sort emotions by count (highest first)
                sorted_emotions = sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)
                dominant_emotion = sorted_emotions[0][0]
                
                # Calculate percentage of dominant emotion
                dominant_percentage = (emotion_counts[dominant_emotion] / len(self.emotion_buffer)) * 100
                
                # Log buffer statistics
                if self.verbose:
                    self.get_logger().info(f"Buffer stats: {emotion_counts}, samples: {len(self.emotion_buffer)}")
                
                # Only trigger if dominant enough (using configurable threshold)
                if dominant_percentage >= self.emotion_threshold:
                    # Double-check we can still trigger (state might have changed)
                    if not self._can_trigger_emotion_animation():
                        self.get_logger().debug("Animation conditions changed during processing - skipping trigger")
                    # Check if this emotion is too repetitive
                    elif self._is_too_repetitive(dominant_emotion):
                        self.get_logger().info(f"Emotion {dominant_emotion} is repetitive, but checking if we should override...")
                        
                        # If it's been a long time since last animation, allow it anyway
                        if time_since_last_animation > self.emotion_cooldown * 2:
                            self.get_logger().info(f"Overriding repetition check due to long idle time ({time_since_last_animation:.1f}s)")
                            # Trigger the animation
                            self.trigger_animation(dominant_emotion, avg_distance)
                        else:
                            self.get_logger().info(f"Skipping repetitive emotion: {dominant_emotion}")
                    else:
                        self.get_logger().info(f"Triggering animation for emotion: {dominant_emotion} ({dominant_percentage:.1f}%)")
                        # Trigger the animation
                        self.trigger_animation(dominant_emotion, avg_distance)
                else:
                    self.get_logger().debug(f"No dominant emotion found, highest: {dominant_emotion} ({dominant_percentage:.1f}%)")
            
            # Reset the buffer and start time
            self.emotion_buffer.clear()
            self.emotion_buffer_start_time = current_time

    def _is_too_repetitive(self, emotion):
        """Check if an emotion is being detected too repetitively"""
        # If it's the same as the last triggered emotion, check how long ago that was
        if emotion == self.last_emotion:
            # But allow it if enough time has passed
            current_time = self.get_clock().now()
            time_since_last = (current_time - self.last_animation_time).nanoseconds / 1e9
            if time_since_last > self.emotion_cooldown * 1.5:  # 7.5 seconds
                return False  # Allow it after extended time
            return True
            
        # If this emotion appears too frequently in our recent history
        if len(self.recent_emotions) >= 3:  # Check last 3 animations
            emotion_counts = {}
            for e in self.recent_emotions:
                emotion_counts[e] = emotion_counts.get(e, 0) + 1
                
            # If this emotion was ALL of our last 3 animations, skip it
            if emotion in emotion_counts and emotion_counts[emotion] >= 3:
                return True
        
        return False

    def trigger_animation(self, emotion, distance=None):
        """Trigger an animation based on detected emotion using the action system"""
        # Update state with ROS2 time
        self.last_emotion = emotion
        self.last_animation_time = self.get_clock().now()
        
        # When triggering an animation, update display emotion tracking
        with self.data_lock:
            self.displayed_emotion = emotion
            self.last_emotion_display_time = self.last_animation_time
        
        # Add to recent emotions history
        self.recent_emotions.append(emotion)
        
        # Get corresponding animation options
        if emotion in self.emotion_to_animation:
            animation_options = self.emotion_to_animation[emotion]
            # Randomly select one animation from the available options
            animation = np.random.choice(animation_options)
            
            # Add speed modifier based on distance if available
            speed_modifier = 1.0
            if distance is not None:
                # Closer distance = faster reaction (within reason)
                if 0.5 <= distance <= 3.0:
                    # Map 0.5m->1.5 (faster) and 3.0m->0.7 (slower)
                    speed = 1.5 - ((distance - 0.5) * 0.32)
                    speed_modifier = speed
                
            # Cancel any existing animation goal
            if self._active_goal_handle:
                self.get_logger().info("Cancelling previous emotion-triggered animation")
                self._active_goal_handle.cancel_goal_async()
            
            # Notify animation command that this is an emotion trigger
            self._notify_animation_trigger('emotion')
            
            # Send animation goal using action system
            self._send_animation_goal(animation, speed_modifier, emotion)
    
    def _notify_animation_trigger(self, source: str):
        """Notify the animation command server about the trigger source."""
        try:
            from std_msgs.msg import String
            msg = String()
            msg.data = source
            self.animation_trigger_publisher.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing animation trigger source: {e}")
    
    def _send_animation_goal(self, animation_name, speed_multiplier, trigger_emotion):
        """Send an animation goal to the action server"""
        if not self._animation_action_client.server_is_ready():
            self.get_logger().warn("Animation action server not ready")
            return
        
        # Create goal message
        from luxo_interfaces.action import PlayAnimation
        goal_msg = PlayAnimation.Goal()
        goal_msg.animation_name = animation_name
        goal_msg.speed_multiplier = speed_multiplier
        goal_msg.allow_interruption = True  # Emotions can be interrupted
        goal_msg.use_hardware_feedback = False
        
        self.get_logger().info(
            f"Sending emotion-triggered animation: {animation_name} "
            f"(speed: {speed_multiplier:.1f}, emotion: {trigger_emotion})"
        )
        
        # Send goal asynchronously
        send_goal_future = self._animation_action_client.send_goal_async(
            goal_msg,
            feedback_callback=self._animation_feedback_callback
        )
        
        # Add callback for when goal is accepted/rejected
        send_goal_future.add_done_callback(
            lambda future: self._goal_response_callback(future, animation_name)
        )
    
    def _goal_response_callback(self, future, animation_name):
        """Handle the goal response from the action server"""
        try:
            goal_handle = future.result()
            
            if not goal_handle.accepted:
                self.get_logger().warn(f'Animation goal rejected: {animation_name}')
                return
            
            self.get_logger().debug(f'Animation goal accepted: {animation_name}')
            self._active_goal_handle = goal_handle
            
            # Get the result asynchronously
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(
                lambda future: self._get_result_callback(future, animation_name)
            )
            
        except Exception as e:
            self.get_logger().error(f"Error in goal response callback: {e}")
    
    def _get_result_callback(self, future, animation_name):
        """Handle the result of the animation"""
        try:
            result = future.result().result
            
            if result.success:
                self.get_logger().info(
                    f"Emotion-triggered animation completed: {animation_name} "
                    f"(duration: {result.actual_duration:.1f}s)"
                )
            else:
                self.get_logger().warn(
                    f"Emotion-triggered animation failed: {animation_name} - {result.message}"
                )
                
            # Clear the active goal handle and update timing
            self._active_goal_handle = None
            self.last_any_animation_end_time = self.get_clock().now()
            
            # When animation ends, start the post-animation emotion timeout
            with self.data_lock:
                self.last_emotion_display_time = self.last_any_animation_end_time
            
        except Exception as e:
            self.get_logger().error(f"Error in result callback: {e}")
    
    def _animation_feedback_callback(self, feedback_msg):
        """Handle feedback from the animation action"""
        feedback = feedback_msg.feedback
        
        if self.verbose:
            self.get_logger().debug(
                f"Animation progress: {feedback.progress*100:.1f}% "
                f"(step {feedback.current_keyframe+1}/{feedback.total_keyframes})"
            )
    
