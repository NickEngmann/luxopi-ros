#!/usr/bin/env python3
"""Exercise the live simulator via Chromium; no hardware or audio playback.

Requires optional Playwright and installed Chromium. Run against a dedicated
simulator graph: tests intentionally change lamp/sensor/animation state.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import time

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', default='/tmp/luxopi-browser-e2e.json')
    parser.add_argument('--screenshot', default='/tmp/luxopi-simulator-dashboard.png')
    parser.add_argument('--pause-state-manager-pid', type=int,
                        help='optional simulator-only PID; pause it to verify /healthz stale recovery')
    args = parser.parse_args()
    evidence, errors, failed_requests = [], [], []
    failure = None
    started = time.monotonic()
    with sync_playwright() as browser_api:
        browser = browser_api.chromium.launch(headless=True, args=[
            '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader',
        ])
        page = browser.new_page(viewport={'width': 1440, 'height': 1080})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('requestfailed', lambda request: failed_requests.append(
            {'url': request.url, 'failure': request.failure}))
        def state():
            return page.evaluate('async () => (await fetch("/api/state")).json()')
        def wait(predicate, timeout=15):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                snapshot = state()
                if predicate(snapshot):
                    return snapshot
                page.wait_for_timeout(100)
            raise AssertionError({'reason': 'expected simulator output timed out', 'last': state()})
        def record(name, **fields):
            entry = {'scenario': name, 'passed': True, **fields}
            evidence.append(entry)
            print(json.dumps(entry), flush=True)
        try:
            page.goto(args.url, wait_until='networkidle')
            page.wait_for_function('document.querySelector("#connectionText").textContent.includes("ROS API")')
            page.wait_for_function('document.querySelector("#modelStatus").textContent.includes("kinematic")', timeout=30000)
            snapshot = wait(lambda s: s['state'] == 'IDLE', timeout=30)
            assert all(snapshot['health']['components'].values()), snapshot['health']
            health_response = page.request.get(args.url + '/healthz')
            assert health_response.status == 200, health_response.text()
            assert health_response.json()['healthy'] is True
            animation_count = len(snapshot.get('animation_names', []))
            assert animation_count > 0
            assert page.locator('#animationNameSelect option').count() == animation_count
            record('render_and_graph', nodes=snapshot['health']['node_count'],
                   model=page.locator('#modelStatus').inner_text(), animations=animation_count,
                   joint_names=snapshot['joint_names'], health_status=health_response.status)
            if len(snapshot['joint_names']) == 6:
                assert page.locator('#modelSelect').input_value() == 'm3'
                assert page.locator('#modelStatus').inner_text().find('all six live') >= 0
            assert page.locator('#manualJointFields input[type=range]').count() == len(snapshot['joint_names'])
            if len(snapshot['joint_names']) == 4:
                page.locator('#view2d').click()
                assert page.locator('#robotCanvas2D').is_visible()
            else:
                assert page.locator('#view2d').is_disabled()
            page.locator('#view3d').click()
            assert page.locator('#robotCanvas3D').is_visible()
            record('both_robot_views')

            page.locator('#commandInput').fill('Please nod')
            page.locator('#commandForm button').click()
            snapshot = wait(lambda s: s['transcript'] == 'Please nod' and bool(s['response']))
            page.wait_for_function('document.querySelector("#transcript").textContent === "Please nod"')
            page.wait_for_function('document.querySelector("#response").textContent !== "No response yet."')
            record('conversation_text_and_reply', transcript=snapshot['transcript'], response=snapshot['response'])
            wait(lambda s: s['status'] == 'idle' and s['state'] == 'IDLE', timeout=20)

            # Force every FSM state through the dashboard's explicit simulator-only
            # test control and verify the real state-service response.
            for state_name in [
                'ANIMATING', 'VOICE_FOLLOWING', 'COLLISION_AVOIDING',
                'RETURNING_HOME', 'ESCAPE_MODE', 'USER_CONTROL', 'EMOTION_REACTING',
                'PETTING', 'ERROR', 'INITIALIZING', 'SHUTDOWN', 'IDLE',
            ]:
                page.locator('#stateSelect').select_option(state_name)
                page.locator('#requestState').click()
                snapshot = wait(lambda s, expected=state_name:
                                s['sensors'].get('state_request_result', {}).get('requested') == expected,
                                timeout=10)
                result = snapshot['sensors']['state_request_result']
                assert result['success'], {'requested': state_name, 'response': result}
                record('forced_fsm_state_response', requested=state_name,
                       current=result.get('state'), message=result.get('message'))
                if state_name != 'IDLE':
                    page.locator('#resetIdle').click()
                    wait(lambda s: s['sensors'].get('state_request_result', {}).get('requested') == 'IDLE'
                         and s['sensors']['state_request_result'].get('success')
                         and s['state'] == 'IDLE', timeout=10)

            # Send a small, bounded pose through USER_CONTROL and prove the
            # controller moves the matching first joint before returning to IDLE.
            snapshot = state()
            joint_name = snapshot['joint_names'][0]
            current = snapshot['positions'][0]
            lower, upper = snapshot['joint_limits'][joint_name]
            target = min(upper, max(lower, current + (0.12 if current + 0.12 <= upper else -0.12)))
            page.locator('#manualJoint0').evaluate(
                "(el, value) => {el.value=String(value);el.dispatchEvent(new Event('input',{bubbles:true}))}",
                target,
            )
            page.locator('#applyManualPose').click()
            snapshot = wait(lambda s: s['sensors'].get('manual_pose_result', {}).get('success')
                            and s['state'] == 'USER_CONTROL', timeout=10)
            snapshot = wait(lambda s: abs(s['positions'][0] - target) < .04, timeout=8)
            record('manual_profile_pose_to_joint_feedback', joint=joint_name,
                   target=target, observed=snapshot['positions'][0], joint_names=snapshot['joint_names'])
            if len(snapshot['joint_names']) == 6:
                # The checked-in legacy view is still useful with a live M3
                # graph. Its first four kinematic axes must follow the M3 names.
                page.locator('#modelSelect').select_option('legacy')
                assert not page.locator('#view2d').is_disabled()
                page.locator('#view2d').click()
                before_legacy_view = page.locator('#robotCanvas2D').evaluate('(canvas) => canvas.toDataURL()')
                current = snapshot['positions'][0]
                lower, upper = snapshot['joint_limits'][joint_name]
                target2 = min(upper, max(lower, current + (0.1 if current + 0.1 <= upper else -0.1)))
                page.locator('#manualJoint0').evaluate(
                    "(el, value) => {el.value=String(value);el.dispatchEvent(new Event('input',{bubbles:true}))}",
                    target2,
                )
                page.locator('#applyManualPose').click()
                snapshot = wait(lambda s: abs(s['positions'][0] - target2) < .04, timeout=8)
                after_legacy_view = page.locator('#robotCanvas2D').evaluate('(canvas) => canvas.toDataURL()')
                assert after_legacy_view != before_legacy_view, 'legacy view did not follow canonical M3 joint values'
                record('legacy_view_tracks_m3_joint_feedback', joint=joint_name,
                       target=target2, observed=snapshot['positions'][0])
                page.locator('#modelSelect').select_option('m3')
                page.locator('#view3d').click()
            page.locator('#resetIdle').click()
            wait(lambda s: s['state'] == 'IDLE', timeout=10)

            # Capture all form values in one event turn, avoiding a polling race.
            page.evaluate('''() => {
                document.querySelector('#brightnessRange').value = '0.22';
                document.querySelector('#lightColor').value = 'blue';
                document.querySelector('#lightsEnabled').checked = true;
                document.querySelector('#sendLights').click();
            }''')
            snapshot = wait(lambda s: abs(s['sensors'].get('light_state', {}).get('brightness', -1) - .22) < .001
                            and s['sensors']['light_state']['rgbw'] == [0, 0, 255, 0])
            record('lamp_controls_to_consumer', light=snapshot['sensors']['light_state'])

            page.locator('#animationNameSelect').select_option('dance')
            page.evaluate("document.querySelector('#animationSpeed').value = '2'")
            page.locator('#runAnimation').click()
            snapshot = wait(lambda s: s['state'] == 'ANIMATING')
            before = snapshot['positions']
            snapshot = wait(lambda s: any(abs(a-b) > .001 for a,b in zip(s['positions'], before)))
            page.locator('#cancelAnimation').click()
            snapshot = wait(lambda s: s['sensors'].get('animation_result', {}).get('state') == 'canceled')
            record('action_moves_and_cancels', result=snapshot['sensors']['animation_result'])
            wait(lambda s: s['state'] == 'IDLE')

            page.locator('[data-direction="90"]').click()
            page.locator('#sendDirection').click()
            snapshot = wait(lambda s: s['direction_evidence'].get('requested_mic_angle') == 90)
            assert abs(snapshot['direction_evidence']['error_degrees']) < 10
            record('actual_direction_estimator', evidence=snapshot['direction_evidence'])
            wait(lambda s: not s['voice_active'] and s['state'] == 'IDLE', timeout=15)

            # Raw proximity input must reach the collision classifier, not just echo in the UI.
            page.evaluate("document.querySelector('#proximityRange').value = '80'")
            page.locator('#sendProximity').click()
            snapshot = wait(lambda s: s['sensors'].get('front_severity') == 'danger'
                            and s['motion'].get('motion_frozen'))
            record('raw_sensor_collision_to_motion_hold', state=snapshot['state'], motion=snapshot['motion'])
            page.evaluate("document.querySelector('#proximityRange').value = '0'")
            page.locator('#sendProximity').click()
            wait(lambda s: not s['motion'].get('motion_frozen') and s['state'] == 'IDLE', timeout=20)
            record('collision_quiet_recovery')

            response = page.request.post(args.url + '/api/events', data={'type': 'animation', 'name': 'unknown'})
            assert response.status == 400
            response = page.request.post(args.url + '/api/events', data={'type': 'voice_command', 'text': 'x' * 2001})
            assert response.status == 400
            record('invalid_requests_rejected')
            page.screenshot(path=args.screenshot, full_page=True)
            assert not errors, errors
            assert not failed_requests, failed_requests
            record('no_browser_errors')
            if args.pause_state_manager_pid:
                pid = args.pause_state_manager_pid
                command_path = Path(f'/proc/{pid}/cmdline')
                command = command_path.read_bytes().replace(b'\0', b' ').decode(errors='replace')
                assert 'state_manager_node' in command, {'pid': pid, 'cmdline': command}
                os.kill(pid, signal.SIGSTOP)
                try:
                    deadline = time.monotonic() + 7
                    unhealthy = None
                    while time.monotonic() < deadline:
                        response = page.request.get(args.url + '/healthz')
                        if response.status == 503:
                            unhealthy = response.json()
                            break
                        page.wait_for_timeout(250)
                    assert unhealthy is not None, 'health endpoint did not fail when state publisher paused'
                    assert unhealthy['health']['state_fresh'] is False, unhealthy
                    record('health_fails_on_stale_state', health=unhealthy['health'])
                finally:
                    os.kill(pid, signal.SIGCONT)
                deadline = time.monotonic() + 8
                recovered = None
                while time.monotonic() < deadline:
                    response = page.request.get(args.url + '/healthz')
                    if response.status == 200:
                        recovered = response.json()
                        break
                    page.wait_for_timeout(200)
                assert recovered is not None, 'health endpoint did not recover after state publisher resumed'
                record('health_recovers_after_state_publisher_resume', health=recovered['health'])
            else:
                record('health_stale_fault_test_skipped', reason='pass --pause-state-manager-pid for simulator process')
        except Exception as exc:
            failure = str(exc)
            page.screenshot(path=args.screenshot, full_page=True)
            raise
        finally:
            Path(args.output).write_text(json.dumps({
                'results': evidence, 'error': failure, 'page_errors': errors,
                'failed_requests': failed_requests, 'elapsed_seconds': time.monotonic() - started,
                'url': args.url,
            }, indent=2) + '\n')
            browser.close()


if __name__ == '__main__':
    main()
