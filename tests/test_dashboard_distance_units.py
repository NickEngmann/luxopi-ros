"""Check the API/physical sensor boundary without ROS dependencies."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('side,metres,expected_cm', [
    ('left', 1.0, 100.0), ('right', 0.04, 4.0), ('left', 0.01, 1.0),
])
def test_distance_event_converts_for_classifier_but_keeps_ui_metres(side, metres, expected_cm):
    source = Path('src/luxo_behaviors/luxo_behaviors/simulator_dashboard.py').read_text()
    klass = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))
    method = next(node for node in klass.body
                  if isinstance(node, ast.FunctionDef) and node.name == '_publish_event')
    namespace = {'Float32': lambda **kwargs: SimpleNamespace(**kwargs)}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<dashboard>', 'exec'), namespace)
    sent, updates = [], []
    obj = SimpleNamespace(
        _event_publishers={'distance': {side: SimpleNamespace(publish=sent.append)}},
        _sensor_update=lambda **kwargs: updates.append(kwargs),
    )
    namespace['_publish_event'](obj, {'type': 'distance', 'side': side, 'metres': metres})
    assert [message.data for message in sent] == [expected_cm, expected_cm]
    assert updates == [{f'{side}_distance': metres}]
