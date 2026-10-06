"""Exercise the actual dashboard feedback callback without a ROS installation."""
import ast
from pathlib import Path
from types import SimpleNamespace

from luxo_behaviors.simulator_protocol import MANUAL_JOINT_LIMITS, valid_joint_feedback


def callback():
    tree = ast.parse(Path('src/luxo_behaviors/luxo_behaviors/simulator_dashboard.py').read_text())
    klass = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    method = next(node for node in klass.body
                  if isinstance(node, ast.FunctionDef) and node.name == '_joint_cb')
    namespace = {'time': SimpleNamespace(monotonic=lambda: 20.0),
                 'valid_joint_feedback': valid_joint_feedback}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<dashboard>', 'exec'), namespace)
    return namespace['_joint_cb']


def test_invalid_feedback_preserves_last_good_pose_and_timestamp_then_recovers():
    snapshot = {'positions': [0.0] * 4, '_joints_received_monotonic': 10.0}
    node = SimpleNamespace(_update=lambda **fields: snapshot.update(fields))
    cb = callback()
    cb(node, SimpleNamespace(name=list(MANUAL_JOINT_LIMITS), position=[float('nan')] * 4))
    assert snapshot['positions'] == [0.0] * 4
    assert snapshot['_joints_received_monotonic'] == 10.0
    assert snapshot['_joint_feedback_valid'] is False
    cb(node, SimpleNamespace(name=list(MANUAL_JOINT_LIMITS), position=[0.1] * 4))
    assert snapshot['positions'] == [0.1] * 4
    assert snapshot['_joints_received_monotonic'] == 20.0
    assert snapshot['_joint_feedback_valid'] is True
