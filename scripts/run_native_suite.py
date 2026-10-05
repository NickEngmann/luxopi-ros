#!/usr/bin/env python3
"""Sequential real ROS suite; exclusively owns simulator inputs while running."""
import datetime,hashlib,json,os,pathlib,subprocess,time
if os.environ.get('ROS_DOMAIN_ID') != '73' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
    raise SystemExit('Requires ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1')
base=pathlib.Path(__file__).resolve().parents[1];out=pathlib.Path('/tmp/luxopi-final-'+datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ'));out.mkdir()
files=sorted(base.glob('src/**/*.py'))+sorted(base.glob('roarm_ws_em1/src/**/*.py'))
digest=hashlib.sha256()
for file in files:digest.update(str(file.relative_to(base)).encode());digest.update(file.read_bytes())
report=dict(started_at=datetime.datetime.now(datetime.UTC).isoformat(),runtime_commit=os.environ.get('LUXOPI_RUNTIME_COMMIT','unknown'),source_sha256=digest.hexdigest(),suites=[],output_directory=str(out))
for script,args in [('run_motion_scenarios.py',['--all-animations','--output',str(out/'motion.json')]),('run_state_scenarios.py',[]),('run_lighting_scenarios.py',[]),('run_vision_scenarios.py',[]),('run_sensor_scenarios.py',[]),('run_voice_motion_scenarios.py',[]),('run_watchdog_scenarios.py',[])]:
    started=time.monotonic();target=out/(script+'.log');command=['python3',str(base/'scripts'/script),*args]
    print('START '+script,flush=True)
    with target.open('w') as log: result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=500)
    entry=dict(script=script,passed=result.returncode==0,exit_code=result.returncode,duration_seconds=round(time.monotonic()-started,3),log=str(target))
    report['suites'].append(entry);print(json.dumps(entry),flush=True)
    report['ended_at']=datetime.datetime.now(datetime.UTC).isoformat();(out/'summary.json').write_text(json.dumps(report,indent=2))
    if result.returncode:print(target.read_text()[-5000:],flush=True);break
print('REPORT '+str(out),flush=True)

raise SystemExit(0 if len(report['suites']) == 7 and all(s['passed'] for s in report['suites']) else 1)
