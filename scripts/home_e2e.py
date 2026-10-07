#!/usr/bin/env python3
"""Silent HTTP home/safety E2E; exclusively owns an isolated simulator's inputs."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time
import urllib.parse
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8080')
    parser.add_argument('--container',default='luxopi-ros-modernized-simulator-1')
    parser.add_argument('--output',default='/tmp/luxopi-home-e2e.json')
    args=parser.parse_args()
    target=urllib.parse.urlparse(args.url)
    assert target.hostname in ('localhost','127.0.0.1','::1')
    container=json.loads(subprocess.check_output(['docker','inspect',args.container]))[0]
    assert container['Config']['Image'] in {'luxopi/simulator:local','luxopi/full-simulator:local',
                                           'luxopi/physics-simulator:local'}
    assert container['Config'].get('Labels',{}).get('com.docker.compose.service')=='simulator'
    assert not container['HostConfig'].get('Devices') and container['HostConfig']['NetworkMode']!='host'
    assert 'ROS_DOMAIN_ID=73' in container['Config']['Env'] and 'ROS_LOCALHOST_ONLY=1' in container['Config']['Env']
    assert str(target.port or 80) in {x['HostPort'] for x in container['NetworkSettings']['Ports'].get('8080/tcp',[])}
    assert not any(m['Destination'].startswith('/dev/') for m in container.get('Mounts',[]))
    assert 'LUXOPI_WORLD_SENSOR_FIXTURE=true' not in container['Config']['Env'], 'Manual sensor producer requires fixture disabled'
    pulse_at=0.0
    bottom=0
    evidence={'started_at':datetime.datetime.now(datetime.UTC).isoformat(),
              'container_image_id':container['Image'],'passed':False,'cases':[]}
    def post(event):
        request=urllib.request.Request(args.url+'/api/events',data=json.dumps(event).encode(),
                                      headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=5) as response:assert response.status==202
    def pulse():
        nonlocal pulse_at
        if time.monotonic()-pulse_at<.12:return
        pulse_at=time.monotonic()
        for event in [dict(type='distance',side='left',metres=1.0),
                      dict(type='distance',side='right',metres=1.0),
                      dict(type='touch',sensor='head_bottom',value=bottom),
                      dict(type='touch',sensor='head_left',value=0),
                      dict(type='touch',sensor='head_right',value=0),
                      dict(type='proximity',value=0)]:post(event)
    def snapshot():
        pulse()
        with urllib.request.urlopen(args.url+'/api/state',timeout=5) as response:return json.load(response)
    def wait(predicate,timeout=30):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            state=snapshot()
            if predicate(state):return state
            time.sleep(.03)
        raise AssertionError({'timeout':timeout,'last_state':snapshot()})
    def prepare():
        post(dict(type='state_request',state='IDLE'))
        state=wait(lambda s:s['state']=='IDLE')
        assert len(state['joint_names'])==6,'This test targets the vendor M3 profile'
        pose=[.15,-.2,.45,.2,-.8,.6]
        post(dict(type='manual_joint_target',positions=dict(zip(state['joint_names'],pose))))
        wait(lambda s:s['state']=='USER_CONTROL' and max(abs(a-b) for a,b in zip(s['positions'],pose))<.03)
        post(dict(type='state_request',state='IDLE'))
        return wait(lambda s:s['state']=='IDLE')
    def home():
        post(dict(type='state_request',state='RETURNING_HOME'))
        return wait(lambda s:s['state']=='RETURNING_HOME' and s['motion'].get('home_stage')==1)
    def record(name,**fields):
        item=dict(scenario=name,passed=True,**fields);evidence['cases'].append(item);print(json.dumps(item),flush=True)
    try:
        before=prepare();home();stages=set();started=time.monotonic()
        def finished(state):
            stage=state['motion'].get('home_stage')
            if stage is not None:stages.add(stage)
            return state['state']=='IDLE' and max(abs(a-b) for a,b in zip(
                state['positions'],[.15,-.85,1.3,1.4,-1.5,.6]))<.03
        final=wait(finished,timeout=35)
        assert stages=={1,2},stages
        record('home_two_stages_measured_then_idle',stages=sorted(stages),
               final_positions=final['positions'],elapsed_seconds=time.monotonic()-started)

        prepare();home();bottom=255
        held=wait(lambda s:s['state']=='COLLISION_AVOIDING' and s['motion'].get('motion_frozen'))
        bottom=0
        cleared=wait(lambda s:s['state']=='IDLE' and s['motion'].get('avoidance_mode')=='hold_replan')
        held_pose=cleared['positions'];end=time.monotonic()+.6
        while time.monotonic()<end:
            state=snapshot();assert state['state']=='IDLE',state
            assert max(abs(a-b) for a,b in zip(state['positions'],held_pose))<.04
            time.sleep(.03)
        record('home_contact_interrupt_clear_does_not_resume',held_state=held['state'],
               after_clear=cleared['state'],mode=cleared['motion']['avoidance_mode'])
        home();wait(finished,timeout=35)
        record('fresh_home_request_releases_replan_hold')

        prepare();home();current=snapshot();pose=list(current['positions']);pose[0]+=.12
        post(dict(type='manual_joint_target',positions=dict(zip(current['joint_names'],pose))))
        replaced=wait(lambda s:s['state']=='USER_CONTROL' and abs(s['positions'][0]-pose[0])<.03)
        end=time.monotonic()+.4
        while time.monotonic()<end:
            assert snapshot()['state']=='USER_CONTROL';time.sleep(.03)
        record('manual_replacement_survives_old_home_completion',final_state=replaced['state'])
        evidence['passed']=True
    except BaseException as exc:
        evidence['error']=repr(exc)
        raise
    finally:
        bottom=0
        try:
            pulse_at=0;pulse();post(dict(type='state_request',state='IDLE'))
        except Exception as exc:evidence['cleanup_error']=repr(exc)
        evidence['ended_at']=datetime.datetime.now(datetime.UTC).isoformat()
        Path(args.output).write_text(json.dumps(evidence,indent=2))


if __name__=='__main__':main()
