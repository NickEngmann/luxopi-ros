#!/usr/bin/env python3
"""Sequential real ROS suite; exclusively owns simulator inputs while running."""
import argparse
import datetime,hashlib,json,os,pathlib,subprocess,time
from native_suite_policy import motion_suite_timeout_seconds
if os.environ.get('ROS_DOMAIN_ID') != '73' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
    raise SystemExit('Requires ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--core-motion',action='store_true',help='Run four motion core cases without the full animation playlist')
parser.add_argument('--feasible-retiming',action='store_true',help='Enable slower plan-derived timing and endpoint checks; allow up to one hour')
parser.add_argument('--resume-report',type=pathlib.Path,help='Reuse only a verified passing prefix from identical production sources and runner hashes')
args=parser.parse_args()
base=pathlib.Path(__file__).resolve().parents[1];out=pathlib.Path('/tmp/luxopi-final-'+datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ'));out.mkdir()
files=sorted(base.glob('src/**/*.py'))+sorted(base.glob('roarm_ws_em1/src/**/*.py'))
digest=hashlib.sha256()
for file in files:digest.update(str(file.relative_to(base)).encode());digest.update(file.read_bytes())
report=dict(started_at=datetime.datetime.now(datetime.UTC).isoformat(),runtime_commit=os.environ.get('LUXOPI_RUNTIME_COMMIT','unknown'),source_sha256=digest.hexdigest(),feasible_retiming=args.feasible_retiming,full_animation_playlist=not args.core_motion,suites=[],output_directory=str(out))
SUITES = [('run_motion_scenarios.py',['--all-animations','--output',str(out/'motion.json')]),('run_state_scenarios.py',[]),('run_lighting_scenarios.py',[]),('run_vision_scenarios.py',[]),('run_sensor_scenarios.py',[]),('run_voice_motion_scenarios.py',[]),('run_voice_cue_scenarios.py',[]),('run_watchdog_scenarios.py',[]),('run_avoidance_scenarios.py',['--output',str(out/'avoidance.json')])]
report['continuous_retiming'] = os.environ.get('LUXOPI_CONTINUOUS_ANIMATION_TIMING', 'false').lower() == 'true'
if args.core_motion:
    SUITES[0][1].remove('--all-animations')
if args.feasible_retiming:
    SUITES[0][1].append('--feasible-retiming')
report['runner_sha256'] = {script: hashlib.sha256((base/'scripts'/script).read_bytes()).hexdigest() for script,_ in SUITES}
prefix=0
if args.resume_report:
    previous=json.loads(args.resume_report.read_text())
    assert previous.get('full_animation_playlist',True)==report['full_animation_playlist'],'Motion coverage changed; run full suite'
    assert previous.get('feasible_retiming',False)==report['feasible_retiming'],'Retiming mode changed; run full suite'
    assert previous.get('continuous_retiming',False)==report['continuous_retiming'],'Trajectory mode changed; run full suite'
    assert previous['source_sha256']==report['source_sha256'],'Production source changed; run the full suite'
    for old in previous['suites']:
        if not old['passed']: break
        name=old['script']
        assert name==SUITES[prefix][0] and previous['runner_sha256'][name]==report['runner_sha256'][name],'Passing runner changed; run the full suite'
        report['suites'].append(dict(old,reused_from=str(args.resume_report)))
        prefix+=1
    report['resumed_from']=str(args.resume_report)
for script,script_args in SUITES[prefix:]:
    started=time.monotonic();target=out/(script+'.log');command=['python3',str(base/'scripts'/script),*script_args]
    print('START '+script,flush=True)
    timed_out=False
    timeout = motion_suite_timeout_seconds(
        full_animation_playlist=not args.core_motion,
        feasible_retiming=args.feasible_retiming,
        continuous_retiming=report['continuous_retiming'],
    ) if script=='run_motion_scenarios.py' else 500
    with target.open('w') as log:
        try:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
            exit_code=result.returncode
        except subprocess.TimeoutExpired:
            timed_out=True
            exit_code=124
            log.write(f'\nNATIVE SUITE TIMED OUT after {timeout} seconds.\n')
    entry=dict(script=script,passed=exit_code==0,exit_code=exit_code,duration_seconds=round(time.monotonic()-started,3),log=str(target))
    if timed_out:
        entry['timed_out_after_seconds']=timeout
    report['suites'].append(entry);print(json.dumps(entry),flush=True)
    report['ended_at']=datetime.datetime.now(datetime.UTC).isoformat();(out/'summary.json').write_text(json.dumps(report,indent=2))
    if result.returncode:print(target.read_text()[-5000:],flush=True);break
print('REPORT '+str(out),flush=True)

raise SystemExit(0 if len(report['suites']) == len(SUITES) and all(s['passed'] for s in report['suites']) else 1)
