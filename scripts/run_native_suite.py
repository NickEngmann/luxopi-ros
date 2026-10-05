#!/usr/bin/env python3
"""Sequential real ROS suite; exclusively owns simulator inputs while running."""
import argparse
import datetime,hashlib,json,os,pathlib,subprocess,time
if os.environ.get('ROS_DOMAIN_ID') != '73' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
    raise SystemExit('Requires ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--resume-report',type=pathlib.Path,help='Reuse only a verified passing prefix from identical production sources and runner hashes')
args=parser.parse_args()
base=pathlib.Path(__file__).resolve().parents[1];out=pathlib.Path('/tmp/luxopi-final-'+datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ'));out.mkdir()
files=sorted(base.glob('src/**/*.py'))+sorted(base.glob('roarm_ws_em1/src/**/*.py'))
digest=hashlib.sha256()
for file in files:digest.update(str(file.relative_to(base)).encode());digest.update(file.read_bytes())
report=dict(started_at=datetime.datetime.now(datetime.UTC).isoformat(),runtime_commit=os.environ.get('LUXOPI_RUNTIME_COMMIT','unknown'),source_sha256=digest.hexdigest(),suites=[],output_directory=str(out))
SUITES = [('run_motion_scenarios.py',['--all-animations','--output',str(out/'motion.json')]),('run_state_scenarios.py',[]),('run_lighting_scenarios.py',[]),('run_vision_scenarios.py',[]),('run_sensor_scenarios.py',[]),('run_voice_motion_scenarios.py',[]),('run_voice_cue_scenarios.py',[]),('run_watchdog_scenarios.py',[])]
report['runner_sha256'] = {script: hashlib.sha256((base/'scripts'/script).read_bytes()).hexdigest() for script,_ in SUITES}
prefix=0
if args.resume_report:
    previous=json.loads(args.resume_report.read_text())
    assert previous['source_sha256']==report['source_sha256'],'Production source changed; run the full suite'
    for old in previous['suites']:
        if not old['passed']: break
        name=old['script']
        assert name==SUITES[prefix][0] and previous['runner_sha256'][name]==report['runner_sha256'][name],'Passing runner changed; run the full suite'
        report['suites'].append(dict(old,reused_from=str(args.resume_report)))
        prefix+=1
    report['resumed_from']=str(args.resume_report)
for script,args in SUITES[prefix:]:
    started=time.monotonic();target=out/(script+'.log');command=['python3',str(base/'scripts'/script),*args]
    print('START '+script,flush=True)
    with target.open('w') as log: result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=500)
    entry=dict(script=script,passed=result.returncode==0,exit_code=result.returncode,duration_seconds=round(time.monotonic()-started,3),log=str(target))
    report['suites'].append(entry);print(json.dumps(entry),flush=True)
    report['ended_at']=datetime.datetime.now(datetime.UTC).isoformat();(out/'summary.json').write_text(json.dumps(report,indent=2))
    if result.returncode:print(target.read_text()[-5000:],flush=True);break
print('REPORT '+str(out),flush=True)

raise SystemExit(0 if len(report['suites']) == len(SUITES) and all(s['passed'] for s in report['suites']) else 1)
