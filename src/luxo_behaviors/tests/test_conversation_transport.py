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
        except FileNotFoundError:
            return True  # Successful reap can race with the preceding /proc lookup.
    while not reaped_or_zombie() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert reaped_or_zombie()
