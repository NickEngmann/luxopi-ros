"""Owned-container fault control safety; no Docker calls or actual signals."""
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec=importlib.util.spec_from_file_location('restart_e2e',Path(__file__).parents[1]/'scripts/restart_e2e.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def execute_signal(monkeypatch,argv,processes):
    import builtins,os,signal,sys
    sent=[]
    monkeypatch.setattr(os,'listdir',lambda path:list(processes))
    monkeypatch.setattr(os,'kill',lambda pid,kind:sent.append((pid,kind)))
    monkeypatch.setattr(sys,'argv',argv)
    def read(path,mode='r'):
        pid=path.split('/')[2];command,ticks=processes[pid]
        if path.endswith('cmdline'):return io.BytesIO(command)
        return io.StringIO(pid+' (python3) '+' '.join(['S']+['0']*18+[ticks]+['0']*3))
    monkeypatch.setattr(builtins,'open',read)
    exec(module.STATE_SIGNAL_SCRIPT,{})
    return sent


def test_resume_refuses_reused_pid_before_any_signal(monkeypatch):
    with pytest.raises(AssertionError,match='reused'):
        execute_signal(monkeypatch,['-c','resume',json.dumps({'pid':12,'start_ticks':'old'})],
                       {'12':(b'python3\0/ws/lib/luxo_behaviors/state_manager\0','new')})


def test_exact_ros_entrypoint_single_match_only(monkeypatch):
    import signal
    sent=execute_signal(monkeypatch,['-c','pause'],
        {'12':(b'python3\0/ws/lib/luxo_behaviors/state_manager\0','123'),
         '13':(b'python3\0/tmp/state_manager.py\0','999')})
    assert sent==[(12,signal.SIGSTOP)]


def test_multiple_state_managers_refuse_signal(monkeypatch):
    with pytest.raises(AssertionError):
        execute_signal(monkeypatch,['-c','pause'],
            {str(pid):(b'python3\0/ws/lib/luxo_behaviors/state_manager\0','1') for pid in (12,13)})


def test_fault_assertion_still_resumes_owned_process_in_finally(monkeypatch,tmp_path):
    identity={'pid':12,'start_ticks':'123'};calls=[]
    before={'Id':'owned','RestartCount':0,'State':{'StartedAt':'original'}}
    monkeypatch.setattr(module,'inspect',lambda c:before)
    monkeypatch.setattr(module,'signal_state',lambda c,op,token=None:calls.append((op,token)) or identity)
    monkeypatch.setattr(module,'read_health',lambda u:(200,{'healthy':True}))
    clock=iter([0.,16.]);monkeypatch.setattr(module.time,'monotonic',lambda:next(clock))
    args=SimpleNamespace(container='owned',url='http://127.0.0.1:8080',output=tmp_path/'result.json')
    with pytest.raises(AssertionError,match='health503'):
        module.pause_check(args,before)
    assert calls==[('pause',None),('resume',identity)]
    assert 'error' in json.loads(args.output.read_text())


def test_unexpected_container_restart_rejects_recovery():
    before={'Id':'owned','RestartCount':0,'State':{'StartedAt':'a'}}
    current={'Id':'owned','RestartCount':1,'State':{'StartedAt':'b'}}
    with pytest.raises(AssertionError,match='restart'):
        module.unchanged_container(before,current)


def test_signal_request_uses_docker_exec_container_namespace(monkeypatch):
    seen=[]
    identity={'pid':12,'start_ticks':'123'}
    monkeypatch.setattr(module.subprocess,'check_output',lambda command:seen.append(command) or json.dumps(identity).encode())
    assert module.signal_state('owned','resume',identity)==identity
    assert seen[0][:5]==['docker','exec','owned','python3','-c']
    assert seen[0][-2:] == ['resume',json.dumps(identity)]
