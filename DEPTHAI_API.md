# DepthAI Camera ROS2 Integration Guide

This guide provides instructions for working with OAK-D cameras in ROS2 Humble, focusing on point cloud generation for collision avoidance and RGB image processing for computer vision tasks.

## 1. Camera Setup and Basic Operation

### 1.1 Launch the Camera

The DepthAI ROS driver provides several launch files for different use cases:

```bash
# Basic RGB-D with point cloud
ros2 launch depthai_ros_driver rgbd_pcl.launch.py

# Point cloud only (more reliable for collision avoidance)
ros2 launch depthai_ros_driver pointcloud.launch.py

# With a custom configuration file
ros2 launch depthai_ros_driver pointcloud.launch.py params_file:=/path/to/config.yaml
```

### 1.2 Working Configuration

For reliable point cloud generation, use the following configuration:

```yaml
# Save as luxopijr.yaml or similar
/oak:
  ros__parameters:
    camera:
      i_nn_type: none
    stereo:
      i_align_depth: true
      i_board_socket_id: 2
      i_subpixel: true
      i_right_rect_publish_topic: true
      i_right_rect_synced: false
```

Launch with:
```bash
ros2 launch depthai_ros_driver pointcloud.launch.py params_file:=./luxopijr.yaml
```

### 1.3 Available Topics

After launching the camera, these topics should be available:

#### Point Cloud Data
- `/oak/points` - Main 3D point cloud (sensor_msgs/PointCloud2)

#### RGB Camera
- `/oak/rgb/image_raw` - Raw RGB image
- `/oak/rgb/image_raw/compressed` - Compressed RGB image (for network-efficient transport)
- `/oak/rgb/image_raw/compressedDepth` - Compressed depth-optimized format
- `/oak/rgb/image_raw/theora` - Theora-compressed video stream
- `/oak/rgb/camera_info` - Camera calibration and parameters
- `/oak/rgb/image_rect` - Rectified RGB image (undistorted)
- `/oak/rgb/preview/image_raw` - Lower resolution preview image (if enabled)

#### Stereo Camera
- `/oak/stereo/image_raw` - Raw stereo depth image
- `/oak/stereo/image_rect` - Rectified stereo depth image
- `/oak/stereo/camera_info` - Stereo camera calibration
- `/oak/stereo/image_raw/compressed` - Compressed stereo image
- `/oak/stereo/image_raw/compressedDepth` - Compressed depth-optimized format
- `/oak/stereo/image_raw/theora` - Theora-compressed video stream

#### Left and Right Camera (if enabled)
- `/oak/left/image_raw` - Raw left camera image
- `/oak/left/camera_info` - Left camera calibration
- `/oak/right/image_raw` - Raw right camera image
- `/oak/right/camera_info` - Right camera calibration
- `/oak/left_rect/image_rect` - Rectified left camera image (if enabled)
- `/oak/right_rect/image_rect` - Rectified right camera image (if enabled)

#### IMU Data
- `/oak/imu/data` - Accelerometer and gyroscope data
- `/oak/imu/data_raw` - Raw IMU data (if available)

#### Neural Network Output (when enabled)
- `/oak/nn/detections` - Object detection results (when using MobileNet or YOLO)
- `/oak/nn/image_raw` - Neural network output visualization
- `/oak/nn/spatial_detections` - 3D spatial locations of detected objects

## 2. Visualizing and Inspecting Data

### 2.1 Command Line Tools

```bash
# List all camera topics
ros2 topic list | grep oak

# View topic information
ros2 topic info /oak/points

# Echo point cloud data (verbose!)
ros2 topic echo /oak/points --truncate-length 100

# Check message publishing rate
ros2 topic hz /oak/points

# View RGB image (requires image_view package)
ros2 run image_view image_view --ros-args -r image:=/oak/rgb/image_raw
```

### 2.2 Using RViz2 for Visualization

```bash
# Launch RViz2
ros2 run rviz2 rviz2
```

In RViz2:
1. Set the fixed frame to `oak` or `oak_right_camera_optical_frame`
2. Add a PointCloud2 display and set the topic to `/oak/points`
3. Add an Image display and set the topic to `/oak/rgb/image_raw`

### 2.3 Camera Parameters

View current parameters:
```bash
ros2 param list | grep oak
```

Set parameters (for runtime-adjustable parameters):
```bash
ros2 param set /oak stereo.i_subpixel true
```

## 3. Understanding Point Cloud Data

Our OAK-D-PRO camera generates a point cloud with these characteristics:

- Frame ID: `oak_right_camera_optical_frame`
- Format: Each point contains (x, y, z, intensity)
- Reference frame:
  - X axis points right
  - Y axis points down
  - Z axis points forward (into the scene)
- Data quality:
  - May contain NaN values for unknown points
  - Point cloud density depends on stereo matching confidence
  - "Message lost" warnings indicate high processing load but usually aren't critical

## 4. Collision Avoidance Implementation

### 4.1 Basic Algorithm

For basic collision avoidance with the point cloud:

1. Subscribe to `/oak/points` topic
2. Process and filter point cloud data (remove NaNs, sample for efficiency)
3. Identify points in the forward direction (positive Z values)
4. Calculate distances to obstacles
5. If the minimum distance is below a safety threshold, stop the robot
6. Otherwise, adjust velocity based on obstacle proximity

### 4.2 Sample Code Structure

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
import numpy as np
import struct
from geometry_msgs.msg import Twist

class CollisionAvoidanceNode(Node):
    def __init__(self):
        super().__init__('collision_avoidance_node')
        
        # Create subscription to point cloud
        self.point_cloud_sub = self.create_subscription(
            PointCloud2,
            '/oak/points',
            self.point_cloud_callback,
            10)
            
        # Publisher for robot velocity commands
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Parameters
        self.safety_distance = 0.5  # meters
        self.max_speed = 0.2  # m/s
        
    def point_cloud_callback(self, msg):
        # Extract and process point cloud data
        points = self.process_point_cloud(msg)
        
        # Find minimum distance to obstacles in front
        min_distance = self.find_minimum_distance(points)
        
        # Control robot based on obstacle proximity
        if min_distance < self.safety_distance:
            self.stop_robot()
        else:
            self.move_robot(min_distance)
```

## 5. Computer Vision with RGB Camera

The OAK-D-PRO provides high-quality RGB images suitable for various computer vision tasks:

### 5.1 RGB Image Access

Subscribe to `/oak/rgb/image_raw` to receive RGB images.

### 5.2 Sample Implementation

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class VisionProcessingNode(Node):
    def __init__(self):
        super().__init__('vision_processing_node')
        
        # Subscribe to RGB image
        self.image_sub = self.create_subscription(
            Image,
            '/oak/rgb/image_raw',
            self.image_callback,
            10)
            
        # CV Bridge for converting ROS images to OpenCV format
        self.bridge = CvBridge()
        
    def image_callback(self, msg):
        # Convert ROS Image to OpenCV format
        cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        
        # Process image as needed
        # Example: convert to grayscale
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Example: detect faces
        # face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        # faces = face_cascade.detectMultiScale(gray, 1.1, 4)
```

## 6. Advanced Features

### 6.1 Neural Networks and Inference

OAK-D cameras can run neural networks directly on the device. To enable:

1. Set `camera.i_nn_type` to `rgb` (for RGB-based models) or `spatial` (for depth-aware models)
2. Configure the model using `nn.i_nn_config_path`

Example configuration for MobileNet:
```yaml
/oak:
  ros__parameters:
    camera:
      i_nn_type: rgb
    nn:
      i_nn_config_path: /opt/ros/humble/share/depthai_ros_driver/mobilenet.json
```

### 6.2 Available Neural Network Types

- MobileNet: Object detection
- YOLO: Object detection with bounding boxes
- Segmentation: Pixel-level semantic segmentation

#### Example Neural Network Launch

```bash
# Launch camera with MobileNet detection
ros2 launch depthai_ros_driver camera.launch.py

# Launch camera with segmentation
ros2 launch depthai_ros_driver example_segmentation.launch.py
```

### 6.3 Depth Filtering Options

For improved depth quality, enable these stereo parameters:

```yaml
stereo:
  i_subpixel: true
  i_lr_check: true
  i_extended_disp: false
  i_enable_spatial_filter: true
  i_enable_temporal_filter: true
```

### 6.4 Feature Tracking

The OAK-D camera can track visual features across frames:

```yaml
/oak:
  ros__parameters:
    rgb:
      i_enable_feature_tracker: true
    stereo:
      i_left_rect_enable_feature_tracker: true
```

This publishes `/oak/rgb/features` and `/oak/left_rect/features` topics with tracked feature points.

### 6.5 Multi-Camera Setups

For using multiple OAK-D cameras together:

```bash
# Launch example with multiple cameras
ros2 launch depthai_ros_driver example_multicam.launch.py
```

Edit the config file at `/opt/ros/humble/share/depthai_ros_driver/config/multicam_example.yaml` to set parameters for each camera.

### 6.6 RealSense Compatibility Mode

For compatibility with code designed for RealSense cameras:

```bash
# Launch with RealSense topic compatibility
ros2 launch depthai_ros_driver camera.launch.py rs_compat:=true
```

This changes topic names to match RealSense convention:
- `/oak/rgb` → `/camera/color`
- `/oak/stereo` → `/camera/depth`
- `/oak/left` → `/camera/infra_2`
- `/oak/right` → `/camera/infra_1`

### 6.7 Working with Camera Calibration

Export and apply calibration:

```bash
# Export calibration to a file
ros2 service call /oak/save_calibration std_srvs/srv/Trigger

# Use external calibration file
/oak:
  ros__parameters:
    camera:
      i_external_calibration_path: "/path/to/calibration.json"
```

### 6.8 DepthAI Filters Package

The `depthai_filters` package provides useful nodes for processing camera data:

```bash
# Object detection overlay
ros2 launch depthai_filters example_det2d_overlay.launch.py

# Segmentation overlay
ros2 launch depthai_filters example_seg_overlay.launch.py

# WLS depth filter (improved depth quality)
ros2 launch depthai_filters example_wls_filter.launch.py

# Feature tracking visualization
ros2 launch depthai_filters example_feature_tracker.launch.py

# 3D features point cloud
ros2 launch depthai_filters example_features3d.launch.py
```

## 7. Integration with Robot Systems

### 7.1 Collision Avoidance Integration

For integrating collision avoidance with robot control systems:

```python
# Subscribe to point cloud and publish to cmd_vel
def point_cloud_callback(self, msg):
    # Process point cloud
    min_distance = process_point_cloud(msg)
    
    # Create velocity command
    cmd = Twist()
    if min_distance < self.safety_threshold:
        # Stop robot
        cmd.linear.x = 0.0
    else:
        # Scale velocity based on distance
        scale = min(1.0, (min_distance - self.safety_threshold) / self.safety_threshold)
        cmd.linear.x = self.max_speed * scale
    
    # Publish command
    self.cmd_vel_pub.publish(cmd)
```

### 7.2 SLAM and Mapping

For integrating with RTAB-Map SLAM:

```bash
# Launch RTAB-Map with OAK-D camera
ros2 launch depthai_ros_driver rtabmap.launch.py
```

For Nav2 integration:
1. Set up SLAM with RTAB-Map
2. Configure Nav2 parameters in your navigation package
3. Use the point cloud for obstacle detection in the local costmap

### 7.3 Custom Pipeline Creation

For advanced users, create custom pipelines:

```bash
# Create a new package for custom pipelines
ros2 pkg create --build-type ament_cmake my_depthai_pipelines

# Create a custom pipeline plugin
# See depthai_ros_driver documentation for plugin development
```

## 8. Troubleshooting

### 8.1 No Point Cloud Data

If `/oak/points` isn't publishing:
1. Check if the camera is connected: `ros2 node list | grep oak`
2. Enable stereo publishing: `ros2 param set /oak stereo.i_publish_topic true`
3. Check for TF frame issues in RViz2
4. Use `pointcloud.launch.py` with the known working configuration file

### 8.2 Poor Point Cloud Quality

If point clouds are sparse or inaccurate:
1. Ensure good lighting conditions
2. Enable depth filtering options
3. Adjust stereo parameters:
   ```
   ros2 param set /oak stereo.i_subpixel true
   ros2 param set /oak stereo.i_lr_check true
   ```
4. Try WLS filtering: `ros2 launch depthai_filters example_wls_filter.launch.py`
5. Adjust the stereo matching algorithm:
   ```yaml
   stereo:
     i_depth_preset: HIGH_ACCURACY
     i_bilateral_sigma: 5
     i_stereo_conf_threshold: 200
   ```

### 8.3 RGB Camera Issues

If RGB images aren't available or have poor quality:
1. Check if the RGB topic is publishing: `ros2 topic hz /oak/rgb/image_raw`
2. Try adjusting exposure: `ros2 param set /oak rgb.r_exposure 20000`
3. Try with manual white balance: `ros2 param set /oak rgb.r_set_man_whitebalance true`
4. Adjust other camera settings:
   ```bash
   # Auto-exposure
   ros2 param set /oak rgb.r_set_man_exposure false
   
   # Manual ISO
   ros2 param set /oak rgb.r_iso 800
   
   # Focus
   ros2 param set /oak rgb.r_set_man_focus true
   ros2 param set /oak rgb.r_focus 150
   ```

### 8.4 Neural Network Issues

If neural networks aren't working correctly:
1. Check model path: `ros2 param get /oak nn.i_nn_config_path`
2. Verify NN type: `ros2 param get /oak camera.i_nn_type`
3. Check for errors in the logs
4. Try different blob file formats if the model isn't compatible

### 8.5 Performance Issues

If experiencing performance problems:
1. Reduce processing load by decreasing resolution:
   ```yaml
   rgb:
     i_resolution: 720P
   ```
2. Enable low-bandwidth mode for PoE cameras:
   ```yaml
   rgb:
     i_low_bandwidth: true
     i_low_bandwidth_quality: 50
   ```
3. Reduce frame rates:
   ```yaml
   rgb:
     i_fps: 15.0
   stereo:
     i_fps: 15.0
   ```

## 9. Reference

### 9.1 Key Parameters

For OAK-D-PRO cameras, important parameters include:

#### Camera System Parameters
- `camera.i_pipeline_type`: Camera pipeline type (RGBD, Stereo, RGB, RGBStereo, CamArray, etc.)
- `camera.i_nn_type`: Neural network type (none, rgb, spatial)
- `camera.i_mx_id`: Camera serial number for specific device connection
- `camera.i_usb_speed`: USB speed (SUPER, SUPER_PLUS)
- `camera.i_enable_imu`: Enable/disable IMU

#### RGB Camera Parameters
- `rgb.i_resolution`: RGB camera resolution (720P, 1080P, 4K, etc.)
- `rgb.i_fps`: Frame rate for RGB camera
- `rgb.i_publish_topic`: Enable/disable RGB topic publishing
- `rgb.r_exposure`: Runtime-adjustable exposure value
- `rgb.r_focus`: Runtime-adjustable focus value
- `rgb.r_iso`: Runtime-adjustable ISO value
- `rgb.r_whitebalance`: Runtime-adjustable white balance
- `rgb.i_output_isp`: Use ISP or video output
- `rgb.i_interleaved`: Enable/disable interleaved format

#### Stereo Parameters
- `stereo.i_align_depth`: Align depth to RGB camera
- `stereo.i_subpixel`: Enable subpixel refinement for better depth
- `stereo.i_lr_check`: Enable left-right consistency check
- `stereo.i_board_socket_id`: Which camera socket to use for stereo processing
- `stereo.i_publish_topic`: Enable/disable stereo topic publishing
- `stereo.i_output_disparity`: Output disparity instead of depth
- `stereo.i_depth_filter_size`: Size of median filter for depth
- `stereo.i_extended_disp`: Enable extended disparity
- `stereo.i_bilateral_sigma`: Bilateral filter sigma

#### Neural Network Parameters
- `nn.i_nn_config_path`: Path to neural network configuration
- `nn.i_num_inference_threads`: Number of inference threads
- `nn.i_num_pool_frames`: Number of frame buffers for neural network

#### IMU Parameters
- `imu.i_acc_freq`: Accelerometer frequency
- `imu.i_gyro_freq`: Gyroscope frequency
- `imu.i_message_type`: IMU message type (IMU, IMU_WITH_MAG, etc.)

### 9.2 Advanced Pipeline Types

The OAK-D camera supports various pipeline configurations:

- `RGB`: Only RGB camera, good for vision tasks
- `RGBD`: RGB camera + depth, best for most applications
- `Stereo`: Stereo vision only, no RGB
- `RGBStereo`: RGB + left and right cameras all publishing
- `CamArray`: All detected cameras publishing
- `Depth`: Only depth output, no RGB
- `ToF`: Time-of-Flight camera mode (OAK-D-SR only)
- `DepthToF`: Depth + ToF mode (OAK-D-SR only)
- `StereoToF`: Stereo + ToF mode (OAK-D-SR only)
- `RGBToF`: RGB + ToF mode (OAK-D-SR only)

### 9.3 Useful Commands

```bash
# Stop camera
ros2 service call /oak/stop std_srvs/srv/Trigger

# Start camera
ros2 service call /oak/start std_srvs/srv/Trigger

# Save calibration
ros2 service call /oak/save_calibration std_srvs/srv/Trigger

# List all camera-related parameters
ros2 param list | grep oak

# Get camera info
ros2 topic echo /oak/rgb/camera_info --once

# View raw parameter YAML
ros2 param dump /oak
```

### 9.4 Supported Camera Models

The driver has been tested with these camera models:

- OAK-D (original)
- OAK-D-LITE
- OAK-D-PRO
- OAK-D-S2
- OAK-D-SR
- OAK-D-POE
- OAK-D-W
- OAK-1
- OAK-1-LITE

### 9.5 Sensor Resolutions and Properties

| Sensor Name | Available Resolutions       | Default Resolution |
|-------------|-----------------------------|--------------------|
| IMX378      | 12MP, 4K, 1080P            | 1080P              |
| OV9282      | 800P, 720P, 400P           | 800P               |
| OV9782      | 800P, 720P, 400P           | 800P               |
| OV9281      | 800P, 720P, 400P           | 800P               |
| IMX214      | 13MP, 12MP, 4K, 1080P      | 1080P              |
| IMX412      | 13MP, 12MP, 4K, 1080P      | 1080P              |
| OV7750      | 480P, 400P                 | 480P               |
| OV7251      | 480P, 400P                 | 480P               |
| IMX477      | 12MP, 4K, 1080P            | 1080P              |
| IMX577      | 12MP, 4K, 1080P            | 1080P              |
| AR0234      | 1200P                      | 1200P              |
| IMX582      | 48MP, 12MP, 4K             | 4K                 |
| LCM48       | 48MP, 12MP, 4K             | 4K                 |

## 10. Example Projects and Future Explorations

### 10.1 Emotion Recognition

For facial emotion recognition:

```yaml
/oak:
  ros__parameters:
    camera:
      i_nn_type: rgb
    nn:
      i_nn_config_path: /path/to/emotion_recognition_model.json
```

### 10.2 Person Following Robot

Combine RGB and depth data for person detection and following:

1. Use the spatial neural network to detect people
2. Extract 3D position from spatial detections
3. Control the robot to maintain a fixed distance from the person

### 10.3 Environment Mapping

Use point clouds for 3D mapping:

1. Integrate with RTAB-Map for dense 3D reconstruction
2. Create occupancy grid maps for navigation
3. Perform semantic segmentation for object-aware mapping

### 10.4 Gesture Control

Detect hand gestures and poses for robot control:

1. Use a hand detection model on the RGB stream
2. Map detected gestures to robot commands
3. Combine with depth data for 3D hand positioning

### 10.5 Multi-Camera Setups

For larger robots or environments:

1. Configure multiple OAK-D cameras with non-overlapping fields of view
2. Use TF transforms to represent the spatial relationship between cameras
3. Merge point clouds from multiple cameras for complete environment perception

