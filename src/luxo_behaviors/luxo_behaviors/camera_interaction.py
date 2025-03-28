#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from .MultiMsgSync import TwoStageHostSeqSync
import blobconverter
import cv2
import depthai as dai
import numpy as np
import time
from std_msgs.msg import String, Float32
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

def frame_norm(frame, bbox):
    normVals = np.full(len(bbox), frame.shape[0])
    normVals[::2] = frame.shape[1]
    return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

emotions = ['neutral', 'happy', 'sad', 'surprise', 'anger']

# Rename the class to match the file name for consistency
class CameraInteraction(Node):
    def __init__(self):
        super().__init__('camera_interaction')
        
        # Create ROS publishers
        self.emotion_publisher = self.create_publisher(String, '/camera/emotion', 10)
        self.distance_publisher = self.create_publisher(Float32, '/camera/person_distance', 10)
        
        # Create publisher for animation commands - direct animation control
        self.animation_publisher = self.create_publisher(
            String,
            '/roarm/animation_command',
            10)
        
        # Parameter for publishing the camera feed
        self.declare_parameter('publish_camera_feed', False)
        self.publish_camera_feed = self.get_parameter('publish_camera_feed').get_parameter_value().bool_value
        
        if self.publish_camera_feed:
            self.bridge = CvBridge()
            self.image_publisher = self.create_publisher(Image, '/camera/image_raw', 10)
        
        # Parameter for verbose mode
        self.declare_parameter('verbose', False)
        self.verbose = self.get_parameter('verbose').get_parameter_value().bool_value
        
        # Parameter to enable/disable emotional reactions
        self.declare_parameter('react_to_emotions', True)
        self.react_to_emotions = self.get_parameter('react_to_emotions').get_parameter_value().bool_value
        
        # Track last emotion and animation time for cooldown
        self.last_emotion = "neutral"
        self.last_animation_time = time.time()
        self.emotion_cooldown = 5.0  # Wait 5 seconds between animations
        
        # Map emotions to animations
        self.emotion_to_animation = {
            'happy': 'excited',
            'sad': 'sad',
            'surprise': 'startled',
            'anger': 'shake',
            'neutral': 'curious'
        }
        
        # Start camera detection system
        self.get_logger().info('Starting camera emotion detection...')
        try:
            # Initialize device and determine if stereo is available
            self.device = dai.Device()
            self.stereo = 1 < len(self.device.getConnectedCameras())
            self.get_logger().info(f"{'Stereo' if self.stereo else 'Mono'} camera detected")
            
            # Start pipeline
            self.device.startPipeline(self.create_pipeline())
            
            # Initialize sync and queues
            self.sync = TwoStageHostSeqSync()
            self.queues = {}
            
            # Create output queues
            for name in ["color", "detection", "recognition"]:
                self.queues[name] = self.device.getOutputQueue(name)
            
            # Create timer callback for processing camera data
            self.timer = self.create_timer(0.03, self.process_camera_data)  # ~30fps
            
            self.get_logger().info('Camera emotion detection initialized successfully')
            
        except Exception as e:
            self.get_logger().error(f'Failed to initialize camera: {e}')
            # Keep node running but disable camera processing
            self.device = None
    
    def create_pipeline(self):
        pipeline = dai.Pipeline()

        if self.verbose:
            self.get_logger().info("Creating Color Camera...")
        cam = pipeline.create(dai.node.ColorCamera)
        cam.setPreviewSize(1080, 1080)
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setInterleaved(False)
        cam.setBoardSocket(dai.CameraBoardSocket.RGB)
        cam.setImageOrientation(dai.CameraImageOrientation.ROTATE_180_DEG)

        cam_xout = pipeline.create(dai.node.XLinkOut)
        cam_xout.setStreamName("color")
        cam.preview.link(cam_xout.input)

        # Workaround: remove in 2.18, use `cam.setPreviewNumFramesPool(10)`
        # This manip uses 15*3.5 MB => 52 MB of RAM.
        copy_manip = pipeline.create(dai.node.ImageManip)
        copy_manip.setNumFramesPool(15)
        copy_manip.setMaxOutputFrameSize(3499200)
        cam.preview.link(copy_manip.inputImage)

        # ImageManip that will crop the frame before sending it to the Face detection NN node
        face_det_manip = pipeline.create(dai.node.ImageManip)
        face_det_manip.initialConfig.setResize(300, 300)
        face_det_manip.initialConfig.setFrameType(dai.RawImgFrame.Type.RGB888p)
        copy_manip.out.link(face_det_manip.inputImage)

        if self.stereo:
            monoLeft = pipeline.create(dai.node.MonoCamera)
            monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
            monoLeft.setBoardSocket(dai.CameraBoardSocket.LEFT)

            monoRight = pipeline.create(dai.node.MonoCamera)
            monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
            monoRight.setBoardSocket(dai.CameraBoardSocket.RIGHT)

            stereo = pipeline.create(dai.node.StereoDepth)
            stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
            stereo.setDepthAlign(dai.CameraBoardSocket.RGB)
            monoLeft.out.link(stereo.left)
            monoRight.out.link(stereo.right)

            # Spatial Detection network if OAK-D
            if self.verbose:
                self.get_logger().info("OAK-D detected, spatial coordinates will be available")
            face_det_nn = pipeline.create(dai.node.MobileNetSpatialDetectionNetwork)
            face_det_nn.setBoundingBoxScaleFactor(0.8)
            face_det_nn.setDepthLowerThreshold(100)
            face_det_nn.setDepthUpperThreshold(5000)
            stereo.depth.link(face_det_nn.inputDepth)
        else: # Detection network if OAK-1
            if self.verbose:
                self.get_logger().info("OAK-1 detected, spatial coordinates won't be available")
            face_det_nn = pipeline.create(dai.node.MobileNetDetectionNetwork)

        face_det_nn.setConfidenceThreshold(0.5)
        face_det_nn.setBlobPath(blobconverter.from_zoo(name="face-detection-retail-0004", shaves=6))
        face_det_manip.out.link(face_det_nn.input)

        # Send face detections to the host (for bounding boxes)
        face_det_xout = pipeline.create(dai.node.XLinkOut)
        face_det_xout.setStreamName("detection")
        face_det_nn.out.link(face_det_xout.input)

        # Script node will take the output from the face detection NN as an input and set ImageManipConfig
        # to the 'age_gender_manip' to crop the initial frame
        image_manip_script = pipeline.create(dai.node.Script)
        face_det_nn.out.link(image_manip_script.inputs['face_det_in'])

        # Only send metadata, we are only interested in timestamp, so we can sync
        # depth frames with NN output
        face_det_nn.passthrough.link(image_manip_script.inputs['passthrough'])
        copy_manip.out.link(image_manip_script.inputs['preview'])

        image_manip_script.setScript("""
        import time
        msgs = dict()

        def add_msg(msg, name, seq = None):
            global msgs
            if seq is None:
                seq = msg.getSequenceNum()
            seq = str(seq)

            # Each seq number has it's own dict of msgs
            if seq not in msgs:
                msgs[seq] = dict()
            msgs[seq][name] = msg

            # To avoid freezing (not necessary for this ObjDet model)
            if 15 < len(msgs):
                node.warn(f"Removing first element! len {len(msgs)}")
                msgs.popitem() # Remove first element

        def get_msgs():
            global msgs
            seq_remove = [] # Arr of sequence numbers to get deleted
            for seq, syncMsgs in msgs.items():
                seq_remove.append(seq) # Will get removed from dict if we find synced msgs pair

                # Check if we have both detections and color frame with this sequence number
                if len(syncMsgs) == 2: # 1 frame, 1 detection
                    for rm in seq_remove:
                        del msgs[rm]
                    return syncMsgs # Returned synced msgs
            return None

        def correct_bb(bb):
            if bb.xmin < 0: bb.xmin = 0.001
            if bb.ymin < 0: bb.ymin = 0.001
            if bb.xmax > 1: bb.xmax = 0.999
            if bb.ymax > 1: bb.ymax = 0.999
            return bb

        while True:
            time.sleep(0.001) # Avoid lazy looping

            preview = node.io['preview'].tryGet()
            if preview is not None:
                add_msg(preview, 'preview')

            face_dets = node.io['face_det_in'].tryGet()
            if face_dets is not None:
                # TODO: in 2.18.0.0 use face_dets.getSequenceNum()
                passthrough = node.io['passthrough'].get()
                seq = passthrough.getSequenceNum()
                add_msg(face_dets, 'dets', seq)

            sync_msgs = get_msgs()
            if sync_msgs is not None:
                img = sync_msgs['preview']
                dets = sync_msgs['dets']
                for i, det in enumerate(dets.detections):
                    cfg = ImageManipConfig()
                    correct_bb(det)
                    cfg.setCropRect(det.xmin, det.ymin, det.xmax, det.ymax)
                    cfg.setResize(64, 64)
                    cfg.setKeepAspectRatio(False)
                    node.io['manip_cfg'].send(cfg)
                    node.io['manip_img'].send(img)
        """)

        manip_manip = pipeline.create(dai.node.ImageManip)
        manip_manip.initialConfig.setResize(64, 64)
        manip_manip.setWaitForConfigInput(True)
        image_manip_script.outputs['manip_cfg'].link(manip_manip.inputConfig)
        image_manip_script.outputs['manip_img'].link(manip_manip.inputImage)

        # This ImageManip will crop the mono frame based on the NN detections. Resulting image will be the cropped
        # face that was detected by the face-detection NN.
        emotions_nn = pipeline.create(dai.node.NeuralNetwork)
        emotions_nn.setBlobPath(blobconverter.from_zoo(name="emotions-recognition-retail-0003", shaves=6))
        manip_manip.out.link(emotions_nn.input)

        recognition_xout = pipeline.create(dai.node.XLinkOut)
        recognition_xout.setStreamName("recognition")
        emotions_nn.out.link(recognition_xout.input)

        return pipeline

    def process_camera_data(self):
        """Process camera data and publish emotion results as ROS messages"""
        if self.device is None:
            return  # Skip if camera initialization failed
        
        # Process all available messages
        for name, q in self.queues.items():
            # Add all msgs (color frames, object detections and age/gender recognitions) to the Sync class.
            if q.has():
                self.sync.add_msg(q.get(), name)

        msgs = self.sync.get_msgs()
        if msgs is not None:
            frame = msgs["color"].getCvFrame()
            detections = msgs["detection"].detections
            recognitions = msgs["recognition"]

            # If set to publish camera feed
            if self.publish_camera_feed and frame is not None:
                try:
                    # Convert frame to ROS Image message
                    ros_image = self.bridge.cv2_to_imgmsg(frame, "bgr8")
                    # Publish the image
                    self.image_publisher.publish(ros_image)
                except Exception as e:
                    self.get_logger().error(f"Error publishing camera image: {e}")

            # Process each detected face
            for i, detection in enumerate(detections):
                bbox = frame_norm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                rec = recognitions[i]

                emotion_results = np.array(rec.getFirstLayerFp16())
                emotion_name = emotions[np.argmax(emotion_results)]
                
                # Create and publish emotion message
                emotion_msg = String()
                emotion_msg.data = emotion_name
                self.emotion_publisher.publish(emotion_msg)
                
                # Publish distance if stereo camera is available
                person_distance = None
                if self.stereo:
                    distance_msg = Float32()
                    # Convert from millimeters to meters
                    person_distance = detection.spatialCoordinates.z / 1000.0
                    distance_msg.data = person_distance
                    self.distance_publisher.publish(distance_msg)
                    
                    if self.verbose:
                        self.get_logger().info(f"Detected person with emotion: {emotion_name} at {person_distance:.2f}m")
                else:
                    if self.verbose:
                        self.get_logger().info(f"Detected person with emotion: {emotion_name}")
                
                # Trigger animations based on emotions if enabled
                if self.react_to_emotions:
                    self.handle_emotion_reaction(emotion_name, person_distance)
    
    def handle_emotion_reaction(self, emotion, distance=None):
        """Handle emotional reactions by triggering appropriate animations"""
        current_time = time.time()
        
        # Check if emotion has changed or if enough time has passed
        if (emotion != self.last_emotion or 
                (current_time - self.last_animation_time) > self.emotion_cooldown):
            
            # Update last emotion and time
            self.last_emotion = emotion
            self.last_animation_time = current_time
            
            # Get corresponding animation
            if emotion in self.emotion_to_animation:
                animation = self.emotion_to_animation[emotion]
                
                # Add speed modifier based on distance if available
                speed_modifier = ""
                if distance is not None:
                    # Closer distance = faster reaction (within reason)
                    if 0.5 <= distance <= 3.0:
                        # Map 0.5m->1.5 (faster) and 3.0m->0.7 (slower)
                        speed = 1.5 - ((distance - 0.5) * 0.32)
                        speed_modifier = f" {speed:.1f}"
                    
                # Publish the animation command
                cmd = String()
                cmd.data = f"{animation}{speed_modifier}"
                self.animation_publisher.publish(cmd)
                
                self.get_logger().info(f"Published emotion-triggered animation: {cmd.data}")
    
    def destroy_node(self):
        """Clean up resources when the node is shut down"""
        if hasattr(self, 'device') and self.device is not None:
            self.get_logger().info("Shutting down camera")
            self.device.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    camera_node = CameraInteraction()
    
    try:
        rclpy.spin(camera_node)
    except KeyboardInterrupt:
        pass
    finally:
        camera_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
