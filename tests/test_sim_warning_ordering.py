"""Exercise the actual simulator warning callback with executor reordering."""
import ast
import json
import pathlib
from types import SimpleNamespace

from luxo_behaviors.joint_profiles import URDF4_NAMES, joint_profile
from luxo_behaviors.joint_motion import ordered_joint_target
from luxo_behaviors.reactive_avoidance import ReactiveAvoidance
from luxo_behaviors.sim_motion_rules import validate_manual_pose


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
        "ordered_joint_target": ordered_joint_target,
        "validate_manual_pose": validate_manual_pose,
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
    node.joint_names = list(URDF4_NAMES)
    node.profile = "urdf4"
    node.animation_target = [0.0] * len(URDF4_NAMES)
    node.animation_intent_id = None
    node.animation_target_received_at = None
    node.get_logger = lambda: SimpleNamespace(warning=lambda *_args: None)
    node.manual_target = None
    node.manual_target_rejected = ""
    node.manual_intent_id = None
    node.manual_target_received_at = None
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


def _target(frame_id, positions):
    return SimpleNamespace(
        name=list(URDF4_NAMES),
        position=list(positions),
        header=SimpleNamespace(frame_id=frame_id),
    )


def test_old_goal_heartbeat_cannot_release_replan_hold_after_sensor_clear():
    now = [10.0]
    node = make_node(now)
    node.target_callback(_target("goal-1", [0.1, 0.0, 0.0, 0.0]))
    old_receipt = node.animation_target_received_at

    policy = ReactiveAvoidance()
    policy.update_sensor("left", True, 10.0, severity="warning", valid=True)
    policy.update_sensor("left", False, 11.0, severity="safe", valid=True)
    policy.update_sensor("left", False, 11.8, severity="safe", valid=True)
    now[0] = 12.0

    # The animation server may keep publishing its last goal while idle, and
    # its target values may continue changing during that same goal. Neither
    # makes it a new user intent after the hazard-clear dwell.
    node.target_callback(_target("goal-1", [0.2, 0.0, 0.0, 0.0]))
    assert node.animation_target_received_at == old_receipt
    decision = policy.adjust_target(
        [0.0] * 4, node.animation_target, URDF4_NAMES,
        now=now[0], target_received_at=node.animation_target_received_at,
    )
    assert decision["mode"] == "hold_replan"
    assert decision["target"] == [0.0] * 4

    # A distinct action goal is an explicit new plan and releases the hold.
    node.target_callback(_target("goal-2", [0.2, 0.0, 0.0, 0.0]))
    assert node.animation_target_received_at == now[0]
    decision = policy.adjust_target(
        [0.0] * 4, node.animation_target, URDF4_NAMES,
        now=now[0], target_received_at=node.animation_target_received_at,
    )
    assert decision["mode"] == "clear"
    assert decision["target"][0] == 0.2


def test_manual_pose_generation_marks_same_pose_click_as_new_intent():
    now = [30.0]
    node = make_node(now)
    node.current_state = "USER_CONTROL"
    pose = [0.0] * len(URDF4_NAMES)

    def manual(generation):
        node.manual_target_callback(SimpleNamespace(
            name=list(URDF4_NAMES), position=list(pose),
            header=SimpleNamespace(frame_id=f"manual:{generation}"),
        ))

    manual(1)
    first_receipt = node.manual_target_received_at
    now[0] = 31.0
    manual(1)  # duplicate delivery/keepalive is not a new button press
    assert node.manual_target_received_at == first_receipt
    manual(2)  # even the same pose is a distinct explicit intent
    assert node.manual_target_received_at == 31.0
