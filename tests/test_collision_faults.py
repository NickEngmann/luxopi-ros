"""Execute actual collision-node methods with deterministic sensor/time faults."""
import ast
import math
import pathlib
from types import SimpleNamespace

PATH = pathlib.Path(__file__).resolve().parents[1]/'src/luxo_behaviors/luxo_behaviors/collision_ros_node.py'


class Stamp:
    def __init__(self, seconds):
        self.nanoseconds = int(seconds*1e9)
    def __sub__(self, other):
        return Stamp((self.nanoseconds-other.nanoseconds)/1e9)


def make_node():
    tree = ast.parse(PATH.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    # Constructor is transport setup; callbacks themselves remain unmodified.
    namespace = dict(Node=object, math=math, Bool=SimpleNamespace, String=SimpleNamespace,
                     ConfigureI2CSensor=SimpleNamespace(Request=SimpleNamespace))
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(PATH), 'exec'), namespace)
    node = namespace['CollisionNode'].__new__(namespace['CollisionNode'])
    node.now = 0.0
    node.get_clock = lambda: SimpleNamespace(now=lambda: Stamp(node.now))
    logger = SimpleNamespace(debug=lambda *a: None, warn=lambda *a: None, error=lambda *a: None)
    node.get_logger = lambda: logger
    node.proximity_threshold, node.side_distance_threshold = 15, 8.0
    node.danger_threshold, node.warning_threshold, node.data_timeout = 5.0, 15.0, 2.0
    node.fsr_collision_active = dict(front=False, left=False, right=False)
    node.current_proximity = node.prev_proximity = 0
    node.current_left_distance = node.current_right_distance = float('inf')
    node.prev_left_distance = node.prev_right_distance = float('inf')
    node.last_proximity_time = node.last_left_distance_time = node.last_right_distance_time = Stamp(0)
    node.last_touch_sensor_time, node.touch_sensors = {}, {}
    node.sensor_reinit_interval, node._last_sensor_reinit = 10.0, {}
    node.outputs = {}
    for name in ('collision_pub', 'left_collision_pub', 'right_collision_pub',
                 'front_severity_pub', 'left_severity_pub', 'right_severity_pub',
                 'collision_details_pub', 'proximity_pub', 'left_distance_pub', 'right_distance_pub'):
        node.outputs[name] = []
        setattr(node, name, SimpleNamespace(publish=lambda msg, name=name: node.outputs[name].append(msg.data)))
    node.requests = []
    node.sensor_config_client = SimpleNamespace(service_is_ready=lambda: True,
        call_async=lambda request: node.requests.append(request) or SimpleNamespace(add_done_callback=lambda cb: None))
    return node


def test_one_sample_repeated_by_timer_is_not_two_sensor_readings():
    node = make_node()
    node.left_distance_callback(SimpleNamespace(data=4.0))
    for _ in range(10):
        node.evaluate_collisions()
    assert not any(node.outputs['left_collision_pub'])
    node.left_distance_callback(SimpleNamespace(data=4.0))
    node.evaluate_collisions()
    assert node.outputs['left_collision_pub'][-1]
    assert node.outputs['left_severity_pub'][-1] == 'danger'


def test_proximity_requires_distinct_samples_and_clears():
    node = make_node()
    node.proximity_data_callback(SimpleNamespace(data=40))
    node.evaluate_collisions()
    node.evaluate_collisions()
    assert node.outputs['collision_pub'][-1] is False
    node.proximity_data_callback(SimpleNamespace(data=40))
    node.evaluate_collisions()
    assert node.outputs['collision_pub'][-1] is True
    node.proximity_data_callback(SimpleNamespace(data=0))
    node.evaluate_collisions()
    assert node.outputs['collision_pub'][-1] is False


def test_timeout_cannot_relatch_old_danger_samples():
    node = make_node()
    for _ in range(2):
        node.left_distance_callback(SimpleNamespace(data=3.0))
        node.proximity_data_callback(SimpleNamespace(data=50))
    node.evaluate_collisions()
    node.now = 3
    node.check_data_timeout()
    assert node.outputs['left_collision_pub'][-1] is False
    node.evaluate_collisions()
    assert node.outputs['collision_pub'][-1] is False
    assert node.current_left_distance == float('inf')
    node.left_distance_callback(SimpleNamespace(data=3.0))
    node.evaluate_collisions()
    assert node.outputs['left_collision_pub'][-1] is False


def test_recovery_after_gap_requires_two_fresh_samples():
    node = make_node()
    node.right_distance_callback(SimpleNamespace(data=4.0))
    node.now = 3
    node.right_distance_callback(SimpleNamespace(data=4.0))
    node.evaluate_collisions()
    assert node.outputs['right_collision_pub'][-1] is False
    node.right_distance_callback(SimpleNamespace(data=4.0))
    node.evaluate_collisions()
    assert node.outputs['right_collision_pub'][-1] is True


def test_invalid_distance_never_refreshes_health_or_reinit_storms():
    node = make_node()
    node.now = 3
    for invalid in (float('nan'), float('inf'), -2, 0, .9):
        node.left_distance_callback(SimpleNamespace(data=invalid))
    assert node.last_left_distance_time.nanoseconds == 0
    node.check_data_timeout()
    assert len(node.requests) == 3
    node.now = 4
    node.check_data_timeout()
    assert len(node.requests) == 3
    node.now = 14
    node.check_data_timeout()
    assert len(node.requests) == 6


def test_missing_i2c_service_never_blocks():
    node = make_node()
    node.sensor_config_client = SimpleNamespace(service_is_ready=lambda: False)
    node.now = 3
    node.check_data_timeout()
    assert not node.requests


def test_configured_severity_boundaries():
    node = make_node()
    assert node.determine_severity(4.99) == 'danger'
    assert node.determine_severity(5) == 'warning'
    assert node.determine_severity(14.99) == 'warning'
    assert node.determine_severity(15) == 'safe'


def test_fsr_collision_not_cleared_by_safe_distance_or_timeout():
    node = make_node()
    node.fsr_collision_active['front'] = True
    node.fsr_collision_active['left'] = True
    node.left_distance_callback(SimpleNamespace(data=30.0))
    node.evaluate_collisions()
    assert node.outputs['collision_pub'][-1] is True
    assert node.outputs['left_collision_pub'][-1] is True
    assert node.outputs['left_severity_pub'][-1] == 'danger'
    node.now = 3
    node.check_data_timeout()
    assert node.outputs['collision_pub'][-1] is True
    assert node.outputs['left_collision_pub'][-1] is True
