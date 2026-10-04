"""Real state/lamp callbacks use simulated LED sink without physical drivers."""
import json
import pathlib
import sys
from types import SimpleNamespace
from unittest.mock import patch
import pytest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src/luxo_behaviors'))
from luxo_behaviors.virtual_lighting import VirtualNeoPixelController
from test_state_scenarios import make_manager


def test_effect_sink_bounded_snapshot_and_all_state_used_methods():
    lamp=VirtualNeoPixelController()
    for effect in ('breathing_effect','spinning_dot','spinning_group'):
        getattr(lamp,effect)((255,0,0,0),cycles=3,blocking=False)
        snapshot=lamp.snapshot()
        assert snapshot['rgbw']==[255,0,0,0]
        assert snapshot['parameters']['cycles']==3
    lamp.bouncing_direction_indicator((255,255,255,0),(0,100,255,0),bounce_range=8,blocking=False)
    assert lamp.snapshot()['parameters']['secondary_color']==[0,100,255,0]
    assert lamp.set_brightness(.3)
    assert not lamp.set_brightness(float('nan'))
    lamp.stop_effect();lamp.clear_all()
    assert lamp.snapshot()['effect']=='off'
    assert lamp.snapshot()['rgbw']==[0,0,0,0]
    assert lamp.is_initialized()
    assert len(json.dumps(lamp.snapshot()))<1024


def virtual_manager():
    node,state=make_manager()
    node.simulated_lighting=True
    import builtins
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name in ('board','neopixel') or name.endswith('neopixel_control'):
            raise AssertionError('Simulator attempted physical LED imports')
        return original(name,*args,**kwargs)
    with patch('builtins.__import__',side_effect=guarded):
        node._initialize_neopixel()
    return node,state


def test_actual_callback_telemetry_shows_brightness_color_and_state():
    node,state=virtual_manager()
    output=[]
    node.light_state_publisher=SimpleNamespace(publish=lambda msg:output.append(json.loads(msg.data)))
    node.brightness_control_callback(SimpleNamespace(data='brightness:0.25'))
    node.color_control_callback(SimpleNamespace(data='color:blue'))
    node.publish_state()
    assert output[-1]['brightness']==.25
    assert output[-1]['rgbw']==[0,0,255,0]
    assert output[-1]['state']=='INITIALIZING'
    assert output[-1]['simulated'] and output[-1]['enabled']
    node.light_control_callback(SimpleNamespace(data=False))
    node.publish_state()
    assert not output[-1]['enabled'] and output[-1]['effect']=='off'
    node.light_control_callback(SimpleNamespace(data=True))
    node.publish_state()
    assert output[-1]['enabled']


@pytest.mark.parametrize('state_name,effect',[
 ('IDLE','solid'),('INITIALIZING','spinning_dot'),('ANIMATING','spinning_group'),
 ('PETTING','spinning_group'),('USER_CONTROL','bouncing_direction_indicator'),
 ('ERROR','breathing'),('COLLISION_AVOIDING','spinning_group'),
])
def test_actual_state_visuals_visible_in_virtual_sink(state_name,effect):
    node,state=virtual_manager()
    # Force immediate observation instead of waiting prior animation-duration gate.
    node._neopixel_animation_start_time=None
    node._neopixel_last_visual_state=None
    node._update_neopixel_for_state(state[state_name])
    assert node._neopixel_controller.snapshot()['effect']==effect
