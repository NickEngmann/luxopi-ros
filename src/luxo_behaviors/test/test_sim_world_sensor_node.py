"""ROS E2E for virtual rays publishing the real collision classifier inputs."""

import json
import os
from pathlib import Path
import time

import pytest

rclpy = pytest.importorskip("rclpy")
pytest.importorskip("mujoco")
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32, Int16, UInt8, String

from luxo_behaviors.joint_profiles import ROARM_M3_NAMES
from luxo_behaviors.sim_world_sensors import SimWorldSensors
from luxo_behaviors.collision_ros_node import CollisionNode


def test_actual_m3_feedback_generates_front_and_side_raw_samples_and_stales_out():
    description = Path(os.environ.get("LUXO_M3_DESCRIPTION", "/tmp/luxopi-m3.urdf"))
    assets = Path(__file__).parents[1] / "luxo_behaviors/assets/roarm_m3"
    if not description.is_file() or not assets.is_dir():
        pytest.skip("requires generated M3 URDF and vendor model assets")
    scene = [{
        "name": "front_box",
        "shape": "box",
        "center_m": [0.15, 0.0, 0.61],
        "half_extents_m": [0.03, 0.06, 0.06],
    }]
    rclpy.init(args=[])
    sensor = probe = classifier = None
    executor = SingleThreadedExecutor()
    try:
        sensor = SimWorldSensors(parameter_overrides=[
            Parameter("robot_description_file", value=str(description)),
            Parameter("asset_directory", value=str(assets)),
            Parameter("obstacles_json", value=json.dumps(scene, separators=(",", ":"))),
        ])
        probe = Node("sim_world_sensor_e2e")
        classifier = CollisionNode()
        # This test targets sensor fusion after startup. Avoid waiting through
        # the production five-second false-positive guard in a short unit run.
        classifier.startup_complete = True
        classifier.startup_timer.cancel()
        statuses = []
        probe.create_subscription(String, '/collision/sensor_status',
                                  lambda msg: statuses.append(json.loads(msg.data)), 10)
        joints = probe.create_publisher(JointState, "/joint_states", 10)
        front, left, right = [], [], []
        contacts = {name: [] for name in ('head_bottom', 'head_left', 'head_right')}
        for name, samples in contacts.items():
            probe.create_subscription(UInt8, f'/touch_sensors/{name}',
                                      lambda msg, samples=samples: samples.append(msg.data), 10)
        probe.create_subscription(Int16, "/i2c/apds9960/proximity", lambda msg: front.append(msg.data), 10)
        probe.create_subscription(Float32, "/i2c/vl53_left/distance", lambda msg: left.append(msg.data), 10)
        probe.create_subscription(Float32, "/i2c/vl53_right/distance", lambda msg: right.append(msg.data), 10)
        executor.add_node(sensor)
        executor.add_node(probe)
        executor.add_node(classifier)

        state = JointState()
        state.name = list(ROARM_M3_NAMES)
        state.position = [0.0] * len(ROARM_M3_NAMES)
        sensor.joint_callback(state)
        valid_feedback_at = sensor.last_joint_feedback_at
        malformed = JointState()
        malformed.name = list(ROARM_M3_NAMES)
        malformed.position = [0.0] * len(ROARM_M3_NAMES)
        malformed.position[1] = 1.7  # outside the vendor shoulder limit + tolerance
        sensor.joint_callback(malformed)
        assert sensor.last_joint_feedback == list(state.position)
        assert sensor.last_joint_feedback_at == valid_feedback_at
        sensor.last_joint_feedback = None
        sensor.last_joint_feedback_at = 0.0
        start = time.monotonic()
        last_send = 0.0
        while time.monotonic() - start < 1.2:
            elapsed = time.monotonic() - start
            if elapsed < 0.55 and elapsed - last_send >= 0.04:
                joints.publish(state)
                last_send = elapsed
            executor.spin_once(timeout_sec=0.005)

        assert len(front) >= 2
        assert sum(sample > 15 for sample in front) >= 2  # repeated obstacle samples reach the real classifier
        assert len(left) >= 2 and left[-1] == pytest.approx(80.0)
        assert len(right) >= 2 and right[-1] == pytest.approx(80.0)
        assert all(len(samples) >= 2 and set(samples) == {0} for samples in contacts.values()), {
            "received": contacts,
            "publisher_matches": {name: publisher.get_subscription_count()
                                  for name, publisher in sensor.contact_pubs.items()},
            "feedback_age": time.monotonic() - sensor.last_joint_feedback_at,
        }
        assert {sample['direction'] for sample in statuses if sample['valid']} == {'front', 'left', 'right'}
        assert all(not sample['fsr_contact_latched'] for sample in statuses)
        front_obstacle_samples = [
            sample for sample in statuses
            if sample['direction'] == 'front' and sample['valid']
        ]
        assert any(sample['active'] and sample['severity'] == 'danger'
                   for sample in front_obstacle_samples), json.dumps(front_obstacle_samples)
        # Wait through the feedback TTL and one publication interval before
        # asserting that queued sensor samples have drained. Under load, the
        # final ROS JointState can arrive after the test publisher stops.
        stale_deadline = sensor.last_joint_feedback_at + sensor.feedback_timeout + 0.1
        while time.monotonic() < stale_deadline:
            executor.spin_once(timeout_sec=0.005)
        before_stale = len(front)
        contact_counts = {name: len(samples) for name, samples in contacts.items()}
        stale_start = time.monotonic()
        while time.monotonic() - stale_start < 0.2:
            executor.spin_once(timeout_sec=0.005)
        assert len(front) == before_stale  # old joint pose cannot fake a live sensor
        assert {name: len(samples) for name, samples in contacts.items()} == contact_counts
        # The fixture stops after its feedback TTL; the classifier then has
        # its own raw-data TTL. Wait for that second stage, not an exact edge.
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            latest = {sample['direction']: sample for sample in statuses}
            if len(latest) == 3 and all(not sample['valid'] for sample in latest.values()):
                break
            executor.spin_once(timeout_sec=0.005)
        assert len(latest) == 3 and all(not sample['valid'] for sample in latest.values())
    finally:
        if sensor is not None:
            executor.remove_node(sensor)
            sensor.destroy_node()
        if probe is not None:
            executor.remove_node(probe)
            probe.destroy_node()
        if classifier is not None:
            executor.remove_node(classifier)
            classifier.destroy_node()
        executor.shutdown()
        rclpy.try_shutdown()
