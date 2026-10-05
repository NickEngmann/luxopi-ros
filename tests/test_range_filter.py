"""Obstacle approach must never be averaged into a false clearance."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from luxo_behaviors.range_filter import filtered_clearance


def test_sudden_obstacle_bypasses_old_clear_samples():
    history = []
    for value in (100, 100, 100, 100, 100):
        filtered_clearance(value, history)
    assert filtered_clearance(2, history)['distance'] == 2
    assert filtered_clearance(0, history)['distance'] == 0


def test_clearance_recovery_is_conservative():
    history = [2, 2, 2, 2, 2]
    assert filtered_clearance(100, history)['distance'] == 2
    for _ in range(5):
        result = filtered_clearance(100, history)
    assert result['distance'] == 100


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, 121, 400])
def test_invalid_sample_marks_unknown_and_drops_old_history(value):
    history = [100, 100, 100]
    result = filtered_clearance(value, history)
    assert not result['valid'] and math.isnan(result['distance'])
    assert history == []
    assert filtered_clearance(2, history)['distance'] == 2


def test_filter_never_overstates_current_clearance():
    history = []
    for value in (120, 100, 40, 10, .1, 20, 100, 0, 120, 119):
        assert 0 <= filtered_clearance(value, history)['distance'] <= value
        assert len(history) <= 5


def test_actual_driver_read_passes_imminent_and_invalid_samples_to_classifier():
    source = Path('src/luxo_behaviors/luxo_behaviors/i2c_device_manager.py').read_text()
    klass = next(node for node in ast.parse(source).body
                 if isinstance(node, ast.ClassDef) and node.name == 'VL53L4CDSensor')
    method = next(node for node in klass.body
                  if isinstance(node, ast.FunctionDef) and node.name == 'read')
    namespace = {'filtered_clearance': filtered_clearance}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<driver>', 'exec'), namespace)
    acknowledgments = []
    device = SimpleNamespace(data_ready=True, distance=2,
                             clear_interrupt=lambda: acknowledgments.append(True))
    obj = SimpleNamespace(active=True, device=device, reading_history=[100]*5,
                          history_size=5, outlier_threshold=15)
    assert namespace['read'](obj)['distance'] == 2
    device.distance = float('nan')
    assert not namespace['read'](obj)['valid']
    assert len(acknowledgments) == 2
