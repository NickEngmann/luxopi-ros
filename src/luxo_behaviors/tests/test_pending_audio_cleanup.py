"""Execute real shutdown-drain logic without ROS or devices."""
import ast
from pathlib import Path
import queue
from types import SimpleNamespace

from luxo_behaviors.audio_input import remove_audio


def cleanup_method():
    path=Path(__file__).parents[1]/'luxo_behaviors/speech_bridge.py'
    tree=ast.parse(path.read_text())
    method=next(m for c in tree.body if isinstance(c,ast.ClassDef) for m in c.body if isinstance(m,ast.FunctionDef) and m.name=='_discard_pending_audio')
    ns=dict(queue=queue,remove_audio=remove_audio)
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),ns)
    return ns['_discard_pending_audio']


def test_shutdown_removes_only_accepted_undequeued_upload(tmp_path):
    name='a'*32+'.wav';other='b'*32+'.wav'
    (tmp_path/name).write_bytes(b'accepted')
    (tmp_path/other).write_bytes(b'unrelated')
    pending=queue.Queue();pending.put({'audio_file':name});pending.put({'text':'hello'})
    bridge=SimpleNamespace(_pending=pending,audio_directory=str(tmp_path))
    cleanup_method()(bridge)
    assert pending.empty() and not (tmp_path/name).exists()
    assert (tmp_path/other).read_bytes()==b'unrelated'
    cleanup_method()(bridge) # Repeated shutdown drain is idempotent.
