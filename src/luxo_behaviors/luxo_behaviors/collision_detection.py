#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import PointCloud2, JointState
import numpy as np
import struct
import math
from std_msgs.msg import String, Bool
import time

class CollisionDetectionNode(Node):
    def __init__(self):
        super().__init__('collision_detection')
        
        # Parameters
        self.declare_parameter('safety_distance', 0.3)  # meters
        self.declare_parameter('robot_base_frame', 'oak')
        self.declare_parameter('point_cloud_topic', '/oak/points')
        self.declare_parameter('joint_states_topic', '/joint_states')
        self.declare_parameter('override_animation', True)
        self.declare_parameter('qos_reliability', 0)  # 0=BEST_EFFORT, 1=RELIABLE
        self.declare_parameter('qos_durability', 0)   # 0=VOLATILE, 1=TRANSIENT_LOCAL
        
        # Get parameters
        self.safety_distance = self.get_parameter('safety_distance').value
        self.robot_base_frame = self.get_parameter('robot_base_frame').value
        self.point_cloud_topic = self.get_parameter('point_cloud_topic').value
        self.joint_states_topic = self.get_parameter('joint_states_topic').value
        self.override_animation = self.get_parameter('override_animation').value
        qos_reliability = self.get_parameter('qos_reliability').value
        qos_durability = self.get_parameter('qos_durability').value
        
        # Set up QoS profile for point cloud - CRITICAL for compatibility
        point_cloud_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT if qos_reliability == 0 else QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE if qos_durability == 0 else QoSDurabilityPolicy.TRANSIENT_LOCAL,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5
        )
        
        # Subscribe to point cloud data with specific QoS
        self.point_cloud_sub = self.create_subscription(
            PointCloud2,
            self.point_cloud_topic,
            self.point_cloud_callback,
            qos_profile=point_cloud_qos)
        
        self.get_logger().info(f"Subscribing to {self.point_cloud_topic} with QoS: reliability={'BEST_EFFORT' if qos_reliability == 0 else 'RELIABLE'}, durability={'VOLATILE' if qos_durability == 0 else 'TRANSIENT_LOCAL'}")
            
        # Subscribe to joint states coming from animation
        self.joint_states_sub = self.create_subscription(
            JointState,
            self.joint_states_topic,
            self.joint_states_callback,
            10)
            
        # Publish safe joint states
        self.safe_joint_pub = self.create_publisher(
            JointState,
            '/safe_joint_states',
            10)
            
        # Publish collision status
        self.collision_status_pub = self.create_publisher(
            String,
            '/collision_status',
            10)
        
        # Published collision warning flag
        self.collision_warning_pub = self.create_publisher(
            Bool,
            '/collision_warning',
            10)
            
        # State variables
        self.collision_detected = False
        self.last_safe_joints = None
        self.original_joints = None
        self.last_collision_time = self.get_clock().now()
        self.consecutive_collision_count = 0
        self.last_status_time = self.get_clock().now()
        self.point_cloud_received = False
        
        # Tracking previous joint state
        self.previous_joint_state = None
        
        # Create a timer for regular status updates
        self.status_timer = self.create_timer(1.0, self.publish_status)
        
        # Create a timer to check if point cloud data is being received
        self.cloud_check_timer = self.create_timer(5.0, self.check_point_cloud)
        
        self.get_logger().info('Collision detection node initialized')
        self.get_logger().info(f'Safety distance: {self.safety_distance}m')
        self.get_logger().info(f'Override animation: {self.override_animation}')
    
    def check_point_cloud(self):
        """Check if point cloud data is being received."""
        if not self.point_cloud_received:
            self.get_logger().warn(f"No point cloud data received on {self.point_cloud_topic}. Check camera and QoS settings.")
        else:
            # Reset flag to check if new data arrives before next timer
            self.point_cloud_received = False
    
    def point_cloud_callback(self, msg):
        """Process point cloud data to detect potential collisions."""
        try:
            # Flag that we've received point cloud data
            self.point_cloud_received = True
            
            # Log message occasionally
            current_time = self.get_clock().now()
            time_since_last = (current_time - self.last_status_time).nanoseconds / 1e9
            if time_since_last > 10.0:  # Log every 10 seconds
                self.get_logger().info(f"Receiving point cloud data from {self.point_cloud_topic}")
                self.last_status_time = current_time
            
            # Extract points from point cloud (sample for efficiency)
            points = self.process_point_cloud(msg)
            
            if len(points) == 0:
                # No valid points, can't make collision decisions
                return
                
            # Convert from camera optical frame to robot's perspective
            # In camera optical frame, Z is forward, X is right, Y is down
            # Convert to robot-centric view where X is forward
            robot_x = points[:, 2]  # Camera Z becomes robot X (forward)
            robot_y = -points[:, 0]  # Negative camera X becomes robot Y (left)
            robot_z = -points[:, 1]  # Negative camera Y becomes robot Z (up)
            
            # Filter for points in front of the robot (positive X)
            # and within a reasonable workspace
            workspace_mask = (robot_x > 0) & (robot_x < 1.0) & \
                            (np.abs(robot_y) < 0.5) & \
                            (robot_z > -0.2) & (robot_z < 0.8)
            
            workspace_points = np.column_stack((
                robot_x[workspace_mask],
                robot_y[workspace_mask],
                robot_z[workspace_mask]
            ))
            
            if len(workspace_points) == 0:
                # No obstacles in the workspace
                self.update_collision_status(False)
                return
                
            # Calculate distances to robot base
            distances = np.sqrt(np.sum(workspace_points**2, axis=1))
            min_distance = np.min(distances)
            
            # Check if any points are too close
            collision_detected = min_distance < self.safety_distance
            
            # Update collision status
            self.update_collision_status(collision_detected, min_distance)
            
        except Exception as e:
            self.get_logger().error(f'Error processing point cloud: {str(e)}')
    
    def process_point_cloud(self, cloud_msg):
        """Extract points from PointCloud2 message."""
        # Get basic cloud info
        fields = cloud_msg.fields
        point_step = cloud_msg.point_step
        row_step = cloud_msg.row_step
        data = cloud_msg.data
        
        # Find field offsets
        offsets = {}
        for field in fields:
            offsets[field.name] = field.offset
        
        # Process points (sample every 100th point for efficiency)
        points = []
        for i in range(0, len(data), point_step * 100):
            if i + point_step <= len(data):
                # Extract x, y, z (assuming float32 datatype - 7)
                try:
                    x = struct.unpack_from('<f', data, i + offsets['x'])[0]
                    y = struct.unpack_from('<f', data, i + offsets['y'])[0]
                    z = struct.unpack_from('<f', data, i + offsets['z'])[0]
                    
                    # Filter out NaN or infinite values
                    if (not math.isnan(x) and not math.isnan(y) and not math.isnan(z) and
                        not math.isinf(x) and not math.isinf(y) and not math.isinf(z)):
                        points.append([x, y, z])
                except:
                    # Skip problematic points
                    pass
        
        return np.array(points) if points else np.empty((0, 3))
    
    def update_collision_status(self, collision_detected, min_distance=float('inf')):
        """Update collision status and publish warnings if needed."""
        current_time = self.get_clock().now()
        
        if collision_detected:
            # Increase consecutive collision counter
            self.consecutive_collision_count += 1
            
            # Set collision flag
            self.collision_detected = True
            
            # Update last collision time
            self.last_collision_time = current_time
            
            # Log and publish only when collision status changes or every few detections
            if self.consecutive_collision_count == 1 or self.consecutive_collision_count % 5 == 0:
                self.get_logger().warn(f'Potential collision detected! Distance: {min_distance:.2f}m')
                
                status_msg = String()
                status_msg.data = f"COLLISION WARNING: Object at {min_distance:.2f}m"
                self.collision_status_pub.publish(status_msg)
                
                warning_msg = Bool()
                warning_msg.data = True
                self.collision_warning_pub.publish(warning_msg)
        else:
            # If we were previously in collision state, log the all-clear
            if self.collision_detected:
                self.get_logger().info('Collision warning cleared')
                
                status_msg = String()
                status_msg.data = f"Path clear: {min_distance:.2f}m"
                self.collision_status_pub.publish(status_msg)
                
                warning_msg = Bool()
                warning_msg.data = False
                self.collision_warning_pub.publish(warning_msg)
            
            # Reset collision status
            self.collision_detected = False
            self.consecutive_collision_count = 0
    
    def joint_states_callback(self, msg):
        """Process joint states to enforce safety limits based on collision detection."""
        # Store original message
        self.original_joints = msg
        
        # If this is the first message, initialize last_safe_joints
        if self.last_safe_joints is None:
            self.last_safe_joints = msg
            self.previous_joint_state = msg
            return
            
        # If override is disabled, just republish the original
        if not self.override_animation:
            self.safe_joint_pub.publish(msg)
            return
            
        # If no collision detected, update last_safe_joints and republish
        if not self.collision_detected:
            self.last_safe_joints = msg
            self.safe_joint_pub.publish(msg)
            self.previous_joint_state = msg
            return
            
        # Collision detected - we need to modify the joint commands
        
        # Create a new joint state message
        safe_msg = JointState()
        safe_msg.header = msg.header
        safe_msg.name = msg.name.copy()
        
        # If we have previous safe joints, use those
        if self.last_safe_joints is not None:
            # Use last safe positions, but move slightly away from obstacle
            # This creates a smooth retreat motion
            
            # Get elapsed time since last collision for retreat speed control
            time_since_collision = (self.get_clock().now() - self.last_collision_time).nanoseconds / 1e9
            retreat_factor = min(1.0, time_since_collision * 2.0)  # Scale based on time
            
            # Interpolate between current position and last safe position
            current_pos = np.array(msg.position)
            previous_pos = np.array(self.previous_joint_state.position)
            last_safe_pos = np.array(self.last_safe_joints.position)
            
            # Calculate movement direction from previous to current position
            movement_direction = current_pos - previous_pos
            
            # If moving toward obstacle, modify to move back to safe position
            # Otherwise, allow movement parallel to obstacle
            safe_positions = []
            for i in range(len(current_pos)):
                # If joint is moving toward obstacle (positive value in certain joints)
                # This logic needs to be adapted to your specific robot kinematics
                if i == 0:  # Base joint - allow side-to-side, but constrained
                    # Allow more movement for base rotation (around vertical axis)
                    # as it's less likely to cause collision
                    safe_pos = previous_pos[i] + movement_direction[i] * 0.7
                    # Ensure we don't move too far from last safe position
                    if abs(safe_pos - last_safe_pos[i]) > 0.2:
                        safe_pos = previous_pos[i] + movement_direction[i] * 0.1
                elif i == 1 or i == 2:  # Shoulder and elbow - very restrictive
                    # These joints can push the arm forward into obstacles
                    if movement_direction[i] > 0 and self.collision_detected:
                        # Moving toward potential collision - restrict
                        safe_pos = previous_pos[i]
                    else:
                        # Moving away from or parallel to obstacle - allow with caution
                        safe_pos = previous_pos[i] + movement_direction[i] * 0.5
                else:  # Wrist and other joints - less restrictive
                    # These joints typically have less impact on collision
                    safe_pos = previous_pos[i] + movement_direction[i] * 0.8
                
                safe_positions.append(safe_pos)
            
            safe_msg.position = safe_positions
        else:
            # Fallback - just use the current message's positions
            # This should rarely happen
            safe_msg.position = msg.position
        
        # Publish safe joint states
        self.safe_joint_pub.publish(safe_msg)
        
        # Update previous joint state
        self.previous_joint_state = safe_msg
    
    def publish_status(self):
        """Regularly publish status updates."""
        if self.collision_detected:
            warning_msg = Bool()
            warning_msg.data = True
            self.collision_warning_pub.publish(warning_msg)
            status_msg = String()
            status_msg.data = "COLLISION STATUS: Obstacle detected"
            self.collision_status_pub.publish(status_msg)
        else:
            status_msg = String()
            status_msg.data = "COLLISION STATUS: Path clear"
            self.collision_status_pub.publish(status_msg)

def main(args=None):
    rclpy.init(args=args)
    node = CollisionDetectionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()