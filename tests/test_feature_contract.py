"""Feature retention and execution tests for every registered animation/lamp mode."""
import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from test_state_scenarios import make_manager
from test_collision_faults import make_node

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('feature_inventory',ROOT/'scripts/check_feature_contract.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MANIFEST = json.loads((ROOT/'docs/feature-coverage.json').read_text())


def test_no_registered_feature_removed_or_renamed():
    assert module.inventory() == MANIFEST['inventory']


def test_canonical_registry_is_deterministic_and_all_plans_validate():
    from luxo_behaviors.animation_capabilities import ANIMATION_CLASSES
    from luxo_behaviors.animation_plan import validate_animation_plan
    for name, cls in ANIMATION_CLASSES.items():
        plugin = cls(SimpleNamespace())
        plan = validate_animation_plan(
            *plugin.get_keyframes(), keyframe_names=plugin.get_keyframe_names()
        )
        assert plan == validate_animation_plan(
            *plugin.get_keyframes(), keyframe_names=plugin.get_keyframe_names()
        ), name


def test_strict_animation_plan_rejects_bad_shape_duration_and_nonfinite_values():
    from luxo_behaviors.animation_plan import validate_animation_plan
    with pytest.raises(ValueError, match='acceleration'):
        validate_animation_plan([[0, 0, 0, 0, 0]], [1.0])
    with pytest.raises(ValueError, match='duration'):
        validate_animation_plan([[0, 0, 0, 0, -1.5, 10]], [float('inf')])
    with pytest.raises(ValueError, match='non-finite'):
        validate_animation_plan([[0, 0, float('nan'), 0, -1.5, 10]], [1.0])


@pytest.mark.parametrize('name',[item['name'] for item in MANIFEST['inventory']['animations']])
def test_every_plugin_generates_finite_full_trajectory(name):
    import inspect,importlib
    from luxo_behaviors.animation_plugin_base import AnimationPlugin
    for mod_name in module.MODULES:
        mod = importlib.import_module('luxo_behaviors.animation_plugins.'+mod_name)
        for _, cls in inspect.getmembers(mod,inspect.isclass):
            if cls is not AnimationPlugin and issubclass(cls,AnimationPlugin):
                plugin = cls(SimpleNamespace())
                if plugin.name == name:
                    frames,durations=plugin.get_keyframes()
                    assert frames and len(frames)==len(durations)
                    assert all(len(frame)==6 for frame in frames)
                    assert np.isfinite(np.asarray(frames)).all()
                    assert np.isfinite(durations).all() and min(durations)>0
                    return
    pytest.fail('Registered plugin not found')


class Lamp:
    def __init__(self):
        self.colors=[]
        self.brightness=[]
        self.clears=0
    def set_solid_color(self,*color):
        self.colors.append(color)
        return True
    def set_brightness(self,value):
        self.brightness.append(value)
        return True
    def clear_all(self):
        self.clears+=1


@pytest.mark.parametrize('name,color',[
    ('red',(255,0,0,0)),('orange',(255,128,0,0)),('yellow',(255,255,0,0)),
    ('green',(0,255,0,0)),('cyan',(0,255,255,0)),('blue',(0,0,255,0)),
    ('purple',(128,0,255,0)),('white',(255,255,255,100)),
])
def test_actual_color_callback_reaches_led_sink(name,color):
    node,_=make_manager()
    node._neopixel_controller=Lamp()
    node.color_control_callback(SimpleNamespace(data='color:'+name))
    assert node._neopixel_controller.colors[-1]==color


@pytest.mark.parametrize('temperature,expected',[(0,(200,200,255,0)),(.5,(255,255,255,50)),(1,(255,200,150,150))])
def test_color_temperature_actual_callback(temperature,expected):
    node,_=make_manager()
    node.color_temp_control_callback(SimpleNamespace(data='color_temp:'+str(temperature)))
    assert node._default_white_color==expected
    assert node._color_temperature==temperature


def test_brightness_on_off_consumer_lifecycle():
    node,_=make_manager()
    node._neopixel_controller=Lamp()
    node.brightness_control_callback(SimpleNamespace(data='brightness:0.4'))
    assert node._neopixel_controller.brightness==[.4]
    node.light_control_callback(SimpleNamespace(data=False))
    assert not node._lights_enabled and node._neopixel_controller.clears>=1
    node.light_control_callback(SimpleNamespace(data=True))
    assert node._lights_enabled and not node._neopixel_override_active


def test_gesture_passthrough_actual_consumer_enabled_disabled():
    node=make_node()
    node.get_logger=lambda: SimpleNamespace(info=lambda *a:None)
    seen=[]
    node.gesture_pub=SimpleNamespace(publish=lambda msg:seen.append(msg.data))
    node.enable_gestures=False
    node.gesture_callback(SimpleNamespace(data='left'))
    assert not seen
    node.enable_gestures=True
    for direction in ('left','right','up','down'):
        node.gesture_callback(SimpleNamespace(data=direction))
    assert seen==['left','right','up','down']


def test_immutable_plan_can_be_adjusted_without_mutation():
    from types import SimpleNamespace
    from luxo_behaviors.animation_capabilities import ANIMATION_CLASSES
    from luxo_behaviors.animation_plan import validate_animation_plan
    node = SimpleNamespace(get_logger=lambda: SimpleNamespace(debug=lambda *args: None))
    plugin = ANIMATION_CLASSES["dance"](node)
    frames, durations = validate_animation_plan(*plugin.get_keyframes())
    adjusted = plugin.adjust_keyframes_to_current_base(frames, 0.3)
    prepared = plugin.prepare_for_current_position([0.3, -0.65, 1.2, 1.0, -1.5], adjusted)
    assert prepared and adjusted
    assert frames == validate_animation_plan(*plugin.get_keyframes())[0]
    assert adjusted[0][0] == 0.3
