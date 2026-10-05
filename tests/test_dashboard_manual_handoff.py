"""Exercise dashboard handoff methods without ROS, including delivery order."""
import ast
from pathlib import Path
import threading
from types import SimpleNamespace


def dashboard():
    source = Path('src/luxo_behaviors/luxo_behaviors/simulator_dashboard.py').read_text()
    klass = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef))
    methods = [n for n in klass.body if isinstance(n, ast.FunctionDef)
               and n.name in {'_manual_state_request_done', '_flush_manual_target'}]
    clock = SimpleNamespace(monotonic=lambda: 1.0)
    namespace = {
        'time': clock,
        'JointState': lambda: SimpleNamespace(
            header=SimpleNamespace(frame_id=''), name=[], position=[]
        ),
    }
    exec(compile(ast.Module(body=methods, type_ignores=[]), '<dashboard>', 'exec'), namespace)
    sent, results = [], []
    obj = SimpleNamespace(
        _manual_generation=2, _manual_granted=False, _manual_deadline=3.0,
        _pending_manual_target={'base': .2}, _lock=threading.Lock(),
        _snapshot={'state': 'USER_CONTROL', 'motion': {'state': 'IDLE'}},
        _manual_target_publisher=SimpleNamespace(publish=sent.append),
        _sensor_update=lambda **kwargs: results.append(kwargs),
    )
    return obj, namespace, clock, sent, results


def test_service_grant_waits_for_motion_consumer_state():
    obj, ns, _, sent, results = dashboard()
    future = SimpleNamespace(result=lambda: SimpleNamespace(success=True, current_state='USER_CONTROL'))
    ns['_manual_state_request_done'](obj, future, 2)
    ns['_flush_manual_target'](obj)
    assert not sent and obj._pending_manual_target
    obj._snapshot['motion']['state'] = 'USER_CONTROL'
    ns['_flush_manual_target'](obj)
    assert len(sent) == 1 and sent[0].position == [.2]
    assert sent[0].header.frame_id == 'manual:2'
    assert results[-1]['manual_pose_result']['success']
    ns['_flush_manual_target'](obj)
    assert len(sent) == 1


def test_stale_service_completion_cannot_grant_replacement_pose():
    obj, ns, _, _, _ = dashboard()
    future = SimpleNamespace(result=lambda: SimpleNamespace(success=True, current_state='USER_CONTROL'))
    ns['_manual_state_request_done'](obj, future, 1)
    assert not obj._manual_granted


def test_missing_consumer_ack_expires_without_publishing():
    obj, ns, clock, sent, results = dashboard()
    clock.monotonic = lambda: 4.0
    ns['_flush_manual_target'](obj)
    assert not sent and obj._pending_manual_target is None
    assert not results[-1]['manual_pose_result']['success']
