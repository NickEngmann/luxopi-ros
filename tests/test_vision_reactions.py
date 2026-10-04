"""Exercise shared live/simulator emotion policy without camera SDKs or ROS."""
from collections import deque
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/luxo_behaviors'))
from luxo_behaviors.vision_reactions import VisionReactionMixin,EMOTION_ANIMATIONS

class Stamp:
    def __init__(self,value):self.nanoseconds=int(value*1e9)
    def __sub__(self,other):return Stamp((self.nanoseconds-other.nanoseconds)/1e9)

class Harness(VisionReactionMixin):
    def __init__(self):
        self.now=10
        self.current_state='IDLE';self.current_animation_name=None
        self.last_any_animation_end_time=Stamp(0);self.last_animation_time=Stamp(0)
        self.post_animation_delay=3;self.emotion_cooldown=5;self.emotion_buffer_duration=2
        self.emotion_threshold=50;self._active_goal_handle=None;self.verbose=False
        self.emotion_buffer_start_time=Stamp(0);self.emotion_buffer=deque(maxlen=60)
        self.last_emotion='neutral';self.recent_emotions=deque(maxlen=3)
        self.data_lock=threading.Lock();self.emotion_to_animation=EMOTION_ANIMATIONS
        self.sent=[];self.triggers=[]
    def get_clock(self):return SimpleNamespace(now=lambda:Stamp(self.now))
    def get_logger(self):return SimpleNamespace(info=lambda *a:None,debug=lambda *a:None)
    def _notify_animation_trigger(self,source):self.triggers.append(source)
    def _send_animation_goal(self,name,speed,emotion):self.sent.append((name,speed,emotion))
    def detect(self,emotion,distance=1):
        self.emotion_buffer.append((emotion,distance,Stamp(self.now)))

@pytest.mark.parametrize('emotion',EMOTION_ANIMATIONS)
def test_shared_buffer_dominance_triggers_registered_emotion_action(emotion):
    h=Harness()
    for _ in range(3):h.detect(emotion)
    h.process_emotion_buffer()
    assert h.sent and h.sent[0][0] in EMOTION_ANIMATIONS[emotion]
    assert h.triggers==['emotion'] and h.last_emotion==emotion
    assert h.sent[0][1]==pytest.approx(1.34)
    assert not h.emotion_buffer

@pytest.mark.parametrize('state',['VOICE_FOLLOWING','USER_CONTROL','COLLISION_AVOIDING','ESCAPE_MODE','ERROR','SHUTDOWN'])
def test_same_live_state_policy_blocks_sim_emotion(state):
    h=Harness();h.current_state=state
    for _ in range(4):h.detect('happy')
    h.process_emotion_buffer()
    assert not h.sent and not h.emotion_buffer


def test_buffer_minimum_cooldown_animation_and_repetition_gates():
    h=Harness();h.detect('happy');h.process_emotion_buffer();assert not h.sent
    for _ in range(3):h.detect('happy')
    h.now=12;h.last_animation_time=Stamp(10);h.process_emotion_buffer();assert not h.sent
    h.now=20;h.current_animation_name='dance'
    for _ in range(3):h.detect('happy')
    h.process_emotion_buffer();assert not h.sent
    h.current_animation_name=None;h.last_emotion='happy';h.last_animation_time=Stamp(14)
    for _ in range(3):h.detect('happy')
    h.process_emotion_buffer();assert not h.sent
    h.now=26
    for _ in range(3):h.detect('happy')
    h.process_emotion_buffer();assert h.sent


def test_every_live_emotion_mapping_targets_an_actual_registered_plugin():
    manifest=json.loads((Path(__file__).resolve().parents[1]/'docs/feature-coverage.json').read_text())
    registered={p['name'] for p in manifest['inventory']['animations']}
    assert all(name in registered for names in EMOTION_ANIMATIONS.values() for name in names)


def test_live_class_inherits_shared_policy_not_duplicate_behavior():
    import ast
    package=Path(__file__).resolve().parents[1]/'src/luxo_behaviors/luxo_behaviors'
    tree=ast.parse((package/'camera_interaction.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CameraInteraction')
    assert any(isinstance(b,ast.Name) and b.id=='VisionReactionMixin' for b in cls.bases)
    assert not any(isinstance(n,ast.FunctionDef) and n.name=='process_emotion_buffer' for n in cls.body)
    sim=ast.parse((package/'sim_camera_interaction.py').read_text())
    imported={name.name.split('.')[0] for n in ast.walk(sim) if isinstance(n,(ast.Import,ast.ImportFrom)) for name in n.names} 
    assert not imported.intersection({'depthai','cv2','blobconverter','board','pyaudio'})


def detection_harness():
    import ast,math
    package=Path(__file__).resolve().parents[1]/'src/luxo_behaviors/luxo_behaviors'
    tree=ast.parse((package/'sim_camera_interaction.py').read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name!='__init__']
    globals=dict(VisionReactionMixin=VisionReactionMixin,Node=object,math=math,Bool=SimpleNamespace)
    exec(compile(ast.Module(body=[cls],type_ignores=[]),'sim_camera_interaction.py','exec'),globals)
    node=globals['SimCameraInteraction'].__new__(globals['SimCameraInteraction'])
    node.__dict__.update(Harness().__dict__)
    node.get_clock=lambda:SimpleNamespace(now=lambda:Stamp(node.now))
    node.get_logger=lambda:SimpleNamespace(warning=lambda *a:None,info=lambda *a:None,debug=lambda *a:None)
    node.detected_emotion=None;node.last_detection=None;node.person_present=False;node.person_distance=None
    node.output=dict(emotion=[],distance=[],person=[])
    for attribute,key in [('emotion_publisher','emotion'),('distance_publisher','distance'),('person_publisher','person')]:
        setattr(node,attribute,SimpleNamespace(publish=lambda msg,key=key:node.output[key].append(msg.data)))
    return node


def test_actual_detection_callbacks_emit_tracking_and_expire_presence():
    node=detection_harness()
    node.distance_input(SimpleNamespace(data=1.2))
    node.emotion_input(SimpleNamespace(data='happy'))
    assert node.output==dict(emotion=['happy'],distance=[1.2],person=[True,True])
    node.now=11
    node.process_detection()
    assert node.person_present
    node.now=13.01
    node.process_detection()
    assert node.output['person'][-1] is False
    assert node.detected_emotion is None and node.person_distance is None
    node.person_input(SimpleNamespace(data=True))
    node.person_input(SimpleNamespace(data=False))
    assert not node.person_present and not node.emotion_buffer


def test_actual_detection_callbacks_reject_invalid_data_without_refresh():
    node=detection_harness()
    for value in (float('nan'),float('inf'),0,-1,10):
        node.distance_input(SimpleNamespace(data=value))
    node.emotion_input(SimpleNamespace(data='not-an-emotion'))
    assert node.last_detection is None
    assert not any(node.output.values())
