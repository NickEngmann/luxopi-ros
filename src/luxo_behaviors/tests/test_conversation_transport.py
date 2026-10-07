import sys
import json
import socket
from pathlib import Path
import time

import pytest

from luxo_behaviors.conversation_transport import ConversationClient, SimulatedConversation, LocalEventReceiver


def test_real_child_session_stderr_drain_and_stale_id_rejection():
    child = '''
import json, os, sys
sys.stderr.write('diagnostic\\n' * 10000)
sys.stderr.flush()
for line in sys.stdin:
    request=json.loads(line)
    print(json.dumps({'id':'stale','response':'wrong'}),flush=True)
    print(json.dumps({'id':request['id'],'response':request['text'],'pid':os.getpid()}),flush=True)
'''
    client = ConversationClient([sys.executable, "-u", "-c", child], timeout=3)
    try:
        first = client.request("dance")
        second = client.request("hello")
        assert first["response"] == "dance" and second["response"] == "hello"
        assert first["pid"] == second["pid"]
        assert len(client.diagnostics) <= 32
    finally:
        client.close()


def test_local_service_ready_handshake_moves_model_warmup_before_first_request():
    child = '''
import json,sys,time
time.sleep(.15)
sys.stderr.write('LUXOPI_LOCAL_SERVICE_READY\\n');sys.stderr.flush()
for line in sys.stdin:
 request=json.loads(line)
 print(json.dumps({'id':request['id'],'response':'warm'}),flush=True)
'''
    client = ConversationClient([sys.executable, "-u", "-c", child], timeout=2,
                                wait_for_ready=True, startup_timeout=1)
    try:
        client.start()
        assert client._ready_event.is_set()
        assert client.request("first turn")["response"] == "warm"
    finally:
        client.close()


def test_hung_child_is_killed_and_next_request_starts_fresh():
    child = '''
import json, sys, time
for line in sys.stdin:
    request=json.loads(line)
    if request['text']=='hang': time.sleep(30)
    print(json.dumps({'id':request['id'],'response':'ready'}),flush=True)
'''
    client = ConversationClient([sys.executable, "-u", "-c", child], timeout=0.3)
    try:
        with pytest.raises(TimeoutError):
            client.request("hang")
        assert client._process is None
        assert client.request("hello")["response"] == "ready"
    finally:
        client.close()


def test_simulator_does_not_execute_arbitrary_response_text():
    client = SimulatedConversation()
    assert client.request("Please dance")["animation"] == "dance"
    assert client.request("please don't dance")["animation"] is None
    assert client.request("I saw someone dance")["animation"] is None


def test_local_event_receiver_rejects_invalid_data_and_preserves_other_socket(tmp_path):
    path = str(tmp_path / "events.sock")
    receiver = LocalEventReceiver(path)
    sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        with pytest.raises(OSError):
            LocalEventReceiver(path)
        sender.sendto(b"bad json", path)
        assert receiver.read() is None
        sender.sendto(json.dumps({"event": "status", "status": "speaking"}).encode(), path)
        assert receiver.read()["status"] == "speaking"
        assert (tmp_path / "events.sock").stat().st_mode & 0o777 == 0o600
    finally:
        sender.close()
        receiver.close()
    assert not (tmp_path / "events.sock").exists()


def test_close_reaps_owned_model_server_group_even_if_service_exits_first():
    child = '''
import json, subprocess, sys
model=subprocess.Popen([sys.executable,'-c',
    'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'])
for line in sys.stdin:
    request=json.loads(line)
    print(json.dumps({'id':request['id'],'response':'ready','model_pid':model.pid}),flush=True)
'''
    client = ConversationClient([sys.executable, "-u", "-c", child], timeout=2)
    result = client.request("hello")
    client.close()
    stat_path = Path(f"/proc/{result['model_pid']}/stat")
    deadline = time.monotonic() + 1
    def reaped_or_zombie():
        try:
            return stat_path.read_text().split(")", 1)[1].split()[0] == "Z"
        except (FileNotFoundError,ProcessLookupError):
            return True  # Successful reap can race with the preceding /proc lookup.
    while not reaped_or_zombie() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert reaped_or_zombie()


def test_progress_and_final_in_one_write_are_correlated_and_both_consumed():
    child='''
import json,sys
for line in sys.stdin:
 r=json.loads(line)
 events=[{'id':'stale','event':'transcript','text':'wrong'},
         {'id':r['id'],'event':'transcript','text':'Please dance'},
         {'id':r['id'],'response':'ready','text':'Please dance'}]
 sys.stdout.write(''.join(json.dumps(e)+'\\n' for e in events));sys.stdout.flush()
'''
    client=ConversationClient([sys.executable,'-u','-c',child],timeout=2)
    seen=[]
    try:
        result=client.request_audio('a'*32+'.wav',on_transcript=seen.append)
        assert seen==['Please dance'] and result['response']=='ready'
    finally:client.close()


def test_recoverable_request_error_preserves_warm_child_for_following_command():
    from luxo_behaviors.conversation_transport import ConversationRequestError
    child='''
import json,sys,os
for line in sys.stdin:
 r=json.loads(line)
 if r['text']=='bad':result={'error':'bad utterance','error_type':'request_error','recoverable':True}
 else:result={'response':'ready','pid':os.getpid()}
 print(json.dumps({'id':r['id'],**result}),flush=True)
'''
    client=ConversationClient([sys.executable,'-u','-c',child],timeout=2)
    try:
        first=client.request('good')
        with pytest.raises(ConversationRequestError):client.request('bad')
        assert client.request('good')['pid']==first['pid']
    finally:client.close()


def test_progress_never_extends_transaction_deadline_and_timeout_restarts_child():
    child='''
import json,sys,time,os
for line in sys.stdin:
 r=json.loads(line)
 if r['text']=='hang':
  for i in range(8):
   print(json.dumps({'id':r['id'],'event':'transcript','text':'partial'}),flush=True);time.sleep(.05)
  time.sleep(30)
 print(json.dumps({'id':r['id'],'response':'ready','pid':os.getpid()}),flush=True)
'''
    client=ConversationClient([sys.executable,'-u','-c',child],timeout=.3)
    try:
        first=client.request('good')
        start=time.monotonic()
        with pytest.raises(TimeoutError):client.request('hang')
        assert time.monotonic()-start<1 and client._process is None
        assert client.request('good')['pid']!=first['pid']
    finally:client.close()


def test_excess_progress_is_protocol_failure_and_restarts_owned_service():
    child='''
import json,sys,os
for line in sys.stdin:
 r=json.loads(line)
 if r['text']=='flood':
  for i in range(9):print(json.dumps({'id':r['id'],'event':'transcript','text':'partial'}),flush=True)
 print(json.dumps({'id':r['id'],'response':'ready','pid':os.getpid()}),flush=True)
'''
    client=ConversationClient([sys.executable,'-u','-c',child],timeout=2)
    try:
        first=client.request('good')
        with pytest.raises(RuntimeError,match='excessive'):client.request('flood')
        assert client._process is None and client.request('good')['pid']!=first['pid']
    finally:client.close()
