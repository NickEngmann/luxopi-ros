"""Exercise the actual simulator warning callback with executor reordering."""
import ast
import json
import pathlib
from types import SimpleNamespace


CONTROLLER = pathlib.Path(__file__).resolve().parents[1] / (
    "src/luxo_behaviors/luxo_behaviors/sim_motion_controller.py"
)


class FakePolicy:
    stale_after = 0.5

    def __init__(self):
        self.updates = []

    def update_sensor(self, direction, active, now, *, severity, valid):
        self.updates.append((direction, active, now, severity, valid))


def make_node(now):
    tree = ast.parse(CONTROLLER.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "SimMotionController")
    namespace = {
        "Node": object,
        "json": json,
        "time": SimpleNamespace(monotonic=lambda: now[0]),
        "ReactiveAvoidance": FakePolicy,
    }
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(CONTROLLER), "exec"), namespace)
    node = namespace["SimMotionController"].__new__(namespace["SimMotionController"])
    node.collision_active = {"front": False, "left": False, "right": False}
    node.current_state = "IDLE"
    node.reactive_avoidance = FakePolicy()
    node._sensor_status_seen = set()
    node._sensor_status_at = {}
    node._sensor_status_payload = {}
    node._warning_started_at = {}
    node._request_state = lambda *args, **kwargs: None
    return node


def atomic(node, direction, now, *, active=True, severity="warning", valid=True):
    payload = {
        "direction": direction, "active": active, "severity": severity,
        "valid": valid,
    }
    node.sensor_status_callback(SimpleNamespace(data=json.dumps(payload)))


def warning(node, direction, active=True):
    node._collision_callback(direction)(SimpleNamespace(data=active))


def test_atomic_warning_before_bool_true_is_kept_and_repeated_true_does_not_refresh_edge():
    now = [10.0]
    node = make_node(now)
    atomic(node, "left", now[0])
    warning(node, "left")
    assert node.reactive_avoidance.updates == [
        ("left", True, 10.0, "warning", True)
    ]
    first_edge = node._warning_started_at["left"]
    now[0] = 10.2
    warning(node, "left")
    assert node._warning_started_at["left"] == first_edge
    assert len(node.reactive_avoidance.updates) == 1


def test_bool_true_before_atomic_warning_holds_unknown_then_accepts_fresh_severity():
    now = [20.0]
    node = make_node(now)
    warning(node, "right")
    assert node.reactive_avoidance.updates[-1] == (
        "right", True, 20.0, "warning", False
    )
    now[0] = 20.02
    atomic(node, "right", now[0], active=True, severity="danger", valid=True)
    assert node.reactive_avoidance.updates[-1] == (
        "right", True, 20.02, "danger", True
    )
