#!/usr/bin/env python3
"""Interrupt an owned simulator node and verify Compose recovers its graph.

Only an isolated luxopi/simulator image with no devices or host networking is
eligible. This deliberately terminates its state manager; do not run alongside
other simulator tests.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def inspect(container):
    return json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]


# Executed only by docker exec inside the selected container PID namespace.
STATE_SIGNAL_SCRIPT = r"""import json,os,signal,sys
matches=[]
for item in os.listdir('/proc'):
 if not item.isdigit(): continue
 try:
  command=open('/proc/'+item+'/cmdline','rb').read().split(b'\0')
  stat=open('/proc/'+item+'/stat').read().rsplit(')',1)[1].split()
 except (FileNotFoundError,ProcessLookupError,PermissionError): continue
 if any(arg.endswith(b'/lib/luxo_behaviors/state_manager') for arg in command):
  matches.append({'pid':int(item),'start_ticks':stat[19]})
assert len(matches)==1,matches
identity=matches[0]
if len(sys.argv)>2:
 assert identity==json.loads(sys.argv[2]),'State-manager PID changed or was reused'
kind={'pause':signal.SIGSTOP,'resume':signal.SIGCONT}[sys.argv[1]]
os.kill(identity['pid'],kind)
print(json.dumps(identity))
"""


def signal_state(container,operation,identity=None):
    command=['docker','exec',container,'python3','-c',STATE_SIGNAL_SCRIPT,operation]
    if identity is not None:command.append(json.dumps(identity))
    return json.loads(subprocess.check_output(command))


def unchanged_container(before,current):
    assert current['Id']==before['Id'],'Container replaced during pause'
    assert current['RestartCount']==before['RestartCount'],'Unexpected container restart during pause'
    assert current['State']['StartedAt']==before['State']['StartedAt'],'Container restarted during pause'


def read_health(url):
    try:
        with urllib.request.urlopen(url+'/healthz',timeout=3) as response:
            return response.status,json.load(response)
    except urllib.error.HTTPError as response:
        return response.code,json.load(response)


def pause_check(args,before):
    report=dict(started_at=datetime.datetime.now(datetime.UTC).isoformat(),
                mode='pause-state',previous_started_at=before['State']['StartedAt'],
                previous_restart_count=before['RestartCount'],passed=False)
    identity=None
    try:
        identity=signal_state(args.container,'pause')
        report['paused_container_process']=identity
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            unchanged_container(before,inspect(args.container))
            code,health=read_health(args.url)
            if code==503 and health.get('health',{}).get('state_fresh') is False:
                report['stale_health']=health
                break
            time.sleep(.2)
        assert 'stale_health' in report,'Paused state heartbeat did not make health503/stale-state'
    except BaseException as exc:
        report['error']=repr(exc)
        raise
    finally:
        try:
            if identity is not None:
                # Refuse to send CONT to a replacement container or reused PID.
                unchanged_container(before,inspect(args.container))
                report['resumed_container_process']=signal_state(args.container,'resume',identity)
        except BaseException as exc:
            report['resume_error']=repr(exc)
            raise
        finally:
            args.output.write_text(json.dumps(report,indent=2))
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            unchanged_container(before,inspect(args.container))
            code,health=read_health(args.url)
            if code==200 and health.get('healthy'):
                report.update(passed=True,recovered_health=health)
                break
            time.sleep(.2)
        assert report['passed'],'Resumed heartbeat did not restore health200'
        print(json.dumps(report),flush=True)
    except BaseException as exc:
        report['error']=repr(exc)
        raise
    finally:
        report['ended_at']=datetime.datetime.now(datetime.UTC).isoformat()
        args.output.write_text(json.dumps(report,indent=2))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pause-state',action='store_true',help='Pause/resume state heartbeat without terminating the container')
    parser.add_argument('--container', default='luxopi-ros-modernized-simulator-1')
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', type=Path, default=Path('/tmp/luxopi-restart-e2e.json'))
    args = parser.parse_args()
    if urllib.parse.urlparse(args.url).hostname not in ('localhost', '127.0.0.1', '::1'):
        raise SystemExit('Requires a local isolated simulator endpoint')
    before = inspect(args.container)
    config, host = before['Config'], before['HostConfig']
    assert config['Image'] in {
        'luxopi/simulator:local', 'luxopi/physics-simulator:local',
    }, 'Unexpected container image'
    assert config.get('Labels', {}).get('com.docker.compose.service') == 'simulator'
    assert not host.get('Devices') and host['NetworkMode'] != 'host'
    assert host['RestartPolicy']['Name'] == 'unless-stopped'
    assert 'ROS_DOMAIN_ID=73' in config['Env'] and 'ROS_LOCALHOST_ONLY=1' in config['Env']
    mapped_ports = before['NetworkSettings']['Ports'].get('8080/tcp') or []
    assert str(urllib.parse.urlparse(args.url).port or 80) in {
        item['HostPort'] for item in mapped_ports
    }, 'Health endpoint must refer to the selected container'
    with urllib.request.urlopen(args.url + '/healthz', timeout=5) as response:
        assert response.status == 200
    if args.pause_state:
        pause_check(args,before)
        return
    # Search and signal only inside this container's PID namespace. Executables
    # must be the installed ROS state-manager entry point, never a host process.
    terminate = '''import os,signal
matches=[]
for item in os.listdir('/proc'):
 if not item.isdigit(): continue
 try: command=open('/proc/'+item+'/cmdline','rb').read().split(b'\\0')
 except (FileNotFoundError,ProcessLookupError,PermissionError): continue
 if any(arg.endswith(b'/lib/luxo_behaviors/state_manager') for arg in command): matches.append(int(item))
assert len(matches)==1,matches
os.kill(matches[0],signal.SIGTERM)
print(matches[0])
'''
    started = time.monotonic()
    pid = int(subprocess.check_output(['docker', 'exec', args.container, 'python3', '-c', terminate]))
    report = dict(started_at=datetime.datetime.now(datetime.UTC).isoformat(),
                  terminated_container_pid=pid, previous_started_at=before['State']['StartedAt'],
                  previous_restart_count=before['RestartCount'], passed=False)
    try:
        deadline = started + 90
        while time.monotonic() < deadline:
            current = inspect(args.container)
            restarted = current['RestartCount'] > before['RestartCount']
            if restarted and current['State']['StartedAt'] != before['State']['StartedAt']:
                try:
                    with urllib.request.urlopen(args.url + '/healthz', timeout=3) as response:
                        health = json.load(response)
                    assert response.status == 200
                    report.update(passed=True, restart_count=current['RestartCount'],
                                  recovered_started_at=current['State']['StartedAt'],
                                  health=health, elapsed_seconds=round(time.monotonic()-started, 3))
                    break
                except (OSError, AssertionError):
                    pass
            time.sleep(.5)
        assert report['passed'], 'Critical-node exit did not recover a healthy graph within 90 seconds'
        print(json.dumps(report), flush=True)
    finally:
        args.output.write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
