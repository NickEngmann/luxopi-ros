#!/usr/bin/env python3
"""Measure real MuJoCo simulated seconds per wall second at 1x/2x/3x."""
import argparse
import json
import time
from urllib.request import Request, urlopen


def get(url):
    with urlopen(url + '/api/state', timeout=5) as response:
        return json.load(response)


def post(url, event):
    request = Request(url + '/api/events', data=json.dumps(event).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=5) as response:
        return response.status, json.load(response)


def wait(url, predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = get(url)
        if predicate(value):
            return value
        time.sleep(.1)
    raise AssertionError({'last_state': get(url)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', default='docs/validation/2026-10-06/simulator-time-scale-e2e.json')
    parser.add_argument('--sample-seconds', type=float, default=2.0)
    args = parser.parse_args()
    results = []
    post(args.url, {'type':'simulator_autonomy','enabled':False})
    post(args.url, {'type':'cancel_animation'})
    post(args.url, {'type':'state_request','state':'IDLE'})
    try:
        wait(args.url, lambda s:s.get('health',{}).get('healthy') and s.get('state')=='IDLE')
        for scale in (1,2,3):
            status, _ = post(args.url, {'type':'simulation_speed','scale':scale})
            assert status == 202
            wait(args.url, lambda s, v=scale:s.get('simulation_speed')==v and s.get('physics',{}).get('time_scale')==v)
            before = get(args.url)['physics']['simulation_time_seconds']
            started = time.monotonic()
            time.sleep(args.sample_seconds)
            wall = time.monotonic() - started
            after = get(args.url)['physics']['simulation_time_seconds']
            rate = (after-before)/wall
            assert rate >= scale*.70, {'scale':scale,'simulated_seconds_per_wall_second':rate}
            results.append({'scenario':f'{scale}x_clock_advances','passed':True,'scale':scale,
                            'simulated_seconds':round(after-before,3),'wall_seconds':round(wall,3),
                            'simulated_seconds_per_wall_second':round(rate,2)})
            print(json.dumps(results[-1]),flush=True)
    finally:
        post(args.url, {'type':'simulation_speed','scale':1})
        post(args.url, {'type':'state_request','state':'IDLE'})
        post(args.url, {'type':'simulator_autonomy','enabled':True})
    result={'suite':'simulator_time_scale_e2e','passed':len(results),'failed':0,
            'scenarios':results,'sample_seconds':args.sample_seconds}
    with open(args.output,'w') as output:
        json.dump(result,output,indent=2);output.write('\n')
    print(json.dumps({'passed':len(results),'output':args.output},indent=2))


if __name__=='__main__': main()
