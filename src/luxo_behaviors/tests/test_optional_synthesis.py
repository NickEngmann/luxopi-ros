"""Real JSONL payloads and bridge worker, without ROS or playback devices."""
import ast
import json
import queue
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from luxo_behaviors.conversation_transport import ConversationClient, SimulatedConversation
from luxo_behaviors.speech_preview import speaking_preview_duration


@pytest.mark.parametrize('audio',[False,True])
def test_optional_synthesis_reaches_actual_child_payload_only_when_enabled(audio):
    child="import sys,json\nfor line in sys.stdin:\n r=json.loads(line);print(json.dumps({'id':r['id'],'response':'ready','payload':r}),flush=True)"
    client=ConversationClient([sys.executable,'-u','-c',child],timeout=2)
    try:
        method=client.request_audio if audio else client.request
        value='0123456789abcdef0123456789abcdef.wav' if audio else 'Please dance'
        assert 'synthesize' not in method(value)['payload']
        assert method(value,synthesize=True)['payload']['synthesize'] is True
    finally:client.close()


def test_simulated_backend_accepts_flag_without_claiming_real_synthesis():
    result=SimulatedConversation().request('dance',synthesize=True)
    assert result['audio_path'] is None and result['source']=='simulation'


def wav(path,seconds):
    with wave.open(str(path),'wb') as output:
        output.setparams((1,2,16000,0,'NONE','not compressed'))
        output.writeframes(b'\0\0'*int(seconds*16000))


def test_wav_header_controls_silent_speaking_preview_with_bounded_fallback(tmp_path):
    path=tmp_path/'response.wav';wav(path,2.25)
    assert speaking_preview_duration({'audio_path':str(path)},1.,use_synthesized_audio=True)==2.25
    assert speaking_preview_duration({'audio_path':str(path)},1.)==1.
    assert speaking_preview_duration({'audio_path':str(tmp_path/'missing')},1.,use_synthesized_audio=True)==1.
    wav(path,12.);assert speaking_preview_duration({'audio_path':str(path)},1.,use_synthesized_audio=True)==10.


@pytest.mark.parametrize('audio',[False,True])
def test_actual_bridge_worker_passes_flag_and_uses_generated_wav_duration(tmp_path,audio):
    source=Path(__file__).resolve().parents[1]/'luxo_behaviors/speech_bridge.py'
    tree=ast.parse(source.read_text())
    method=next(m for c in tree.body if isinstance(c,ast.ClassDef) for m in c.body if isinstance(m,ast.FunctionDef) and m.name=='_run')
    namespace=dict(queue=queue,String=SimpleNamespace,SimulatedConversation=SimulatedConversation,
                   speaking_preview_duration=speaking_preview_duration,remove_audio=lambda *a:None)
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(source),'exec'),namespace)
    path=tmp_path/'response.wav';wav(path,1.75)
    calls=[];waits=[];statuses=[]
    class Stop:
        stopped=False
        def is_set(self):return self.stopped
        def wait(self,duration):waits.append(duration);self.stopped=True
    def request(value,*,synthesize=False):
        calls.append((value,synthesize));return dict(text='dance',response='ready',audio_path=str(path))
    pending=queue.Queue();pending.put({'audio_file':'test.wav'} if audio else {'text':'dance'})
    bridge=SimpleNamespace(client=SimpleNamespace(request=request,request_audio=request),
        synthesize_speech=True,_stopping=Stop(),_pending=pending,_busy=SimpleNamespace(clear=lambda:None),
        audio_directory=str(tmp_path),_publish_status=statuses.append,
        get_parameter=lambda name:SimpleNamespace(value=1.),
        responses=SimpleNamespace(publish=lambda m:None),transcripts=SimpleNamespace(publish=lambda m:None))
    namespace['_run'](bridge)
    assert calls==[('test.wav' if audio else 'dance',True)]
    assert waits==[1.75] and statuses==['thinking','speaking']
