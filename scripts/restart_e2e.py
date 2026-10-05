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
import urllib.parse
import urllib.request


def inspect(container):
    return json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', default='luxopi-ros-modernized-simulator-1')
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', type=Path, default=Path('/tmp/luxopi-restart-e2e.json'))
    args = parser.parse_args()
    if urllib.parse.urlparse(args.url).hostname not in ('localhost', '127.0.0.1', '::1'):
        raise SystemExit('Requires a local isolated simulator endpoint')
    before = inspect(args.container)
    config, host = before['Config'], before['HostConfig']
    assert config['Image'] == 'luxopi/simulator:local', 'Unexpected container image'
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
