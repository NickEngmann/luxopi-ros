#!/usr/bin/env python3
"""Silent supplied-WAV → actual local ASR/LLM → ROS consumer HTTP smoke.

Generate fixtures separately with Piper; never captures or plays audio. Functional
fixture coverage is not an accuracy or physical robot latency estimate.
"""
import argparse,datetime,json,math,re,time,urllib.parse,urllib.request
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8081')
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('/tmp/luxopi-audio-e2e.json'))
    args=parser.parse_args()
    if urllib.parse.urlparse(args.url).hostname not in ('localhost','127.0.0.1','::1'):
        raise SystemExit('Only local isolated simulator HTTP endpoints are supported')
    def snapshot():
        with urllib.request.urlopen(args.url+'/api/state',timeout=5) as response:return json.load(response)
    def normalized(text):return re.sub(r'[^a-z0-9 ]','',text.lower()).strip()
    results=[];error=None;started=datetime.datetime.now(datetime.UTC).isoformat()
    try:
        baseline=snapshot();assert baseline.get('audio_upload'),'Saved-audio profile is disabled'
        scenarios=[('dance','Please dance.'),('lamp','Turn the lamp blue.'),('brightness','Set brightness to fifty percent.'),('question','Why do plants need water?')]
        for name,expected in scenarios:
            deadline=time.monotonic()+45
            while snapshot().get('state')!='IDLE' or snapshot().get('animation'):
                if time.monotonic()>deadline:raise AssertionError('Simulator did not settle before '+name)
                time.sleep(.1)
            if name=='brightness':
                reset=urllib.request.Request(args.url+'/api/events',data=json.dumps({'type':'brightness','value':.25}).encode(),headers={'Content-Type':'application/json'},method='POST')
                with urllib.request.urlopen(reset,timeout=5) as response:assert response.status==202
                end=time.monotonic()+5
                while snapshot().get('sensors',{}).get('light_state',{}).get('brightness')!=.25:
                    if time.monotonic()>end:raise AssertionError('Brightness precondition did not reach actual lamp sink')
                    time.sleep(.1)
            before=snapshot();positions=before.get('positions',[]);previous_response=before.get('response','')
            body=(args.fixtures/(name+'.wav')).read_bytes()
            request=urllib.request.Request(args.url+'/api/audio',data=body,headers={'Content-Type':'audio/wav'},method='POST')
            with urllib.request.urlopen(request,timeout=5) as response:
                assert response.status==202;accepted=json.load(response)
            samples=[];first=time.monotonic();deadline=first+90
            transcript=None;response_text=None;motion=False;animation=False;lamp=False
            while time.monotonic()<deadline:
                state=snapshot();samples.append(state)
                for value in state.get('positions',[]):assert math.isfinite(value)
                if normalized(state.get('transcript',''))==normalized(expected):transcript=state['transcript']
                if transcript and state.get('response') and state['response']!=previous_response:response_text=state['response']
                animation=animation or state.get('animation')=='dance'
                motion=motion or bool(positions and len(positions)==len(state.get('positions',[])) and max(abs(a-b) for a,b in zip(positions,state['positions']))>.02)
                light=state.get('sensors',{}).get('light_state',{})
                lamp=lamp or (name=='lamp' and light.get('rgbw')==[0,0,255,0]) or (name=='brightness' and light.get('brightness')==.5)
                consumer=(animation and motion) if name=='dance' else lamp if name in ('lamp','brightness') else True
                if transcript and response_text and consumer and state.get('status')=='idle' and (name!='dance' or not state.get('animation')):break
                time.sleep(.1)
            assert transcript and response_text,dict(name=name,last=samples[-1])
            if name=='dance':assert animation and motion,'Actual dance/action motion was not observed'
            if name in ('lamp','brightness'):assert lamp,'Actual lamp sink did not update'
            assert samples[-1].get('status')=='idle','Speech did not complete'
            item=dict(scenario=name,passed=True,accepted=accepted,transcript=transcript,response=response_text,elapsed_seconds=round(time.monotonic()-first,3),animation_observed=animation,joint_movement=motion,lamp_observed=lamp,statuses=sorted({s.get('status','') for s in samples}),final_state=samples[-1].get('state'))
            results.append(item);print(json.dumps(item),flush=True)
    except Exception as exc:error=str(exc);raise
    finally:
        args.output.write_text(json.dumps(dict(started_at=started,ended_at=datetime.datetime.now(datetime.UTC).isoformat(),results=results,error=error,scope='Synthetic Piper fixtures through actual local models and ROS consumers; silent, not accuracy or hardware latency'),indent=2))

if __name__=='__main__':main()
