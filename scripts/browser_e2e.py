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
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', default='/tmp/luxopi-browser-e2e.json')
    parser.add_argument('--screenshot', default='/tmp/luxopi-simulator-dashboard.png')
    parser.add_argument('--pause-state-manager-pid', type=int,
                        help='optional simulator-only PID; pause it to verify /healthz stale recovery')
    args = parser.parse_args()
    evidence, errors, console_errors, failed_requests, canceled_model_requests = [], [], [], [], []
    asset_status = {}
    failure = None
    started = time.monotonic()
    with sync_playwright() as browser_api:
        browser = browser_api.chromium.launch(headless=True, args=[
            '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader',
        ])
        page = browser.new_page(viewport={'width': 1440, 'height': 1080})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: console_errors.append(message.text)
                if message.type == 'error' else None)
        def capture_failed_request(request):
            item = {'url': request.url, 'failure': request.failure}
            if request.failure == 'net::ERR_ABORTED' and '/assets/' in request.url and request.url.endswith('.stl'):
                # Switching between the M3 and legacy model cancels mesh loads
                # for the now-hidden model; these are expected cancellations.
                canceled_model_requests.append(item)
            else:
                failed_requests.append(item)
        page.on('requestfailed', capture_failed_request)
        page.on('response', lambda response: asset_status.__setitem__(response.url, response.status)
                if '/assets/' in response.url else None)
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
        def stop_sensor_heartbeat():
            page.evaluate('''async () => {
                if (window.__luxoSensorTimer) clearInterval(window.__luxoSensorTimer);
                window.__luxoSensorTimer = null;
                await (window.__luxoSensorPending || Promise.resolve());
            }''')
        def start_sensor_heartbeat(include_front=True):
            page.evaluate('''(includeFront) => {
                const events = [
                    {type:'distance', side:'left', metres:1.0},
                    {type:'distance', side:'right', metres:1.0},
                    {type:'touch', sensor:'head_bottom', value:0},
                    {type:'touch', sensor:'head_left', value:0},
                    {type:'touch', sensor:'head_right', value:0},
                ];
                if (includeFront) events.push({type:'proximity', value:0});
                const publish = () => {
                    window.__luxoSensorPending = Promise.all(events.map(event => fetch('/api/events', {
                        method:'POST', headers:{'Content-Type':'application/json'},
                        body:JSON.stringify(event), cache:'no-store'
                    }))).then(responses => {
                        if (responses.some(response => response.status !== 202))
                            window.__luxoSensorError = 'sensor heartbeat request rejected';
                    }).catch(error => { window.__luxoSensorError = String(error); });
                };
                if (window.__luxoSensorTimer) clearInterval(window.__luxoSensorTimer);
                window.__luxoSensorError = '';
                window.__luxoSensorTimer = setInterval(publish, 150);
                publish();
            }''', include_front)
        try:
            # The dashboard polls ROS state continuously, so waiting for a
            # network-idle window can never be a reliable page-load condition.
            page.goto(args.url, wait_until='domcontentloaded')
            page.wait_for_function('document.querySelector("#connectionText").textContent.includes("ROS API")')
            page.wait_for_function('''() => {
                const text = document.querySelector('#modelStatus').textContent;
                return text.includes('kinematic') || text.includes('dynamics');
            }''', timeout=30000)
            required_m3_meshes = {
                f'/assets/roarm_m3/{name}.stl'
                for name in ('base_link', 'link1', 'link2', 'link3', 'link4', 'link5', 'gripper_link')
            }
            loaded_asset_paths = {urlsplit(url).path for url, status in asset_status.items() if status == 200}
            missing_m3_meshes = sorted(required_m3_meshes - loaded_asset_paths)
            assert not missing_m3_meshes, {'missing_m3_meshes': missing_m3_meshes, 'asset_status': asset_status}
            snapshot = wait(lambda s: bool(s.get('health', {}).get('components')), timeout=30)
            if snapshot['state'] != 'IDLE':
                page.locator('#resetIdle').click()
                snapshot = wait(lambda s: s['state'] == 'IDLE', timeout=10)
            assert all(snapshot['health']['components'].values()), snapshot['health']
            backend = snapshot.get('simulation_backend', 'kinematic')
            assert backend in {'kinematic', 'mujoco'}, backend
            expected_engine = 'MuJoCo M3 dynamics' if backend == 'mujoco' else 'Kinematic preview'
            page.wait_for_function(
                '(expected) => document.querySelector("#engineCaption").textContent.includes(expected)',
                arg=expected_engine,
            )
            warning_text = page.locator('#physicsWarning').inner_text()
            assert ('uncalibrated simulated actuation' in warning_text) if backend == 'mujoco' else ('kinematic view' in warning_text)
            health_response = page.request.get(args.url + '/healthz')
            assert health_response.status == 200, health_response.text()
            assert health_response.json()['healthy'] is True
            animation_count = len(snapshot.get('animation_names', []))
            assert animation_count > 0
            assert page.locator('#animationNameSelect option').count() == animation_count
            record('render_and_graph', nodes=snapshot['health']['node_count'],
                   model=page.locator('#modelStatus').inner_text(), animations=animation_count,
                   joint_names=snapshot['joint_names'], health_status=health_response.status,
                   simulation_backend=backend, engine_caption=page.locator('#engineCaption').inner_text(),
                   loaded_m3_meshes=sorted(path.rsplit('/', 1)[-1] for path in required_m3_meshes))
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

            # The limiter fails closed without fresh sensor coverage. Maintain
            # clear synthetic ranges/FSRs while testing bounded motion.
            start_sensor_heartbeat()
            snapshot = wait(lambda s: s['sensors'].get('front_severity') == 'safe'
                            and s['sensors'].get('left_severity') == 'safe'
                            and s['sensors'].get('right_severity') == 'safe', timeout=5)
            if snapshot['motion'].get('motion_frozen') or snapshot['motion'].get('avoidance_mode') == 'hold_replan':
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
                snapshot = wait(lambda s: abs(s['positions'][0] - target) < .04
                                and not s['motion'].get('motion_frozen')
                                and s['motion'].get('avoidance_mode') == 'clear', timeout=20)
                record('initial_fresh_intent_releases_prior_hold', joint=joint_name,
                       target=target, observed=snapshot['positions'][0])
                page.locator('#resetIdle').click()
                wait(lambda s: s['state'] == 'IDLE', timeout=10)
            page.locator('#commandInput').fill('Please nod')
            page.locator('#commandForm button').click()
            snapshot = wait(lambda s: s['transcript'] == 'Please nod' and bool(s['response']))
            page.wait_for_function('document.querySelector("#transcript").textContent === "Please nod"')
            page.wait_for_function('document.querySelector("#response").textContent !== "No response yet."')
            record('conversation_text_and_reply', transcript=snapshot['transcript'], response=snapshot['response'])
            # Animation commands are retimed to the simulated actuator limits;
            # the full nod gesture takes about a minute at those bounds.
            wait(lambda s: s['status'] == 'idle' and s['state'] == 'IDLE', timeout=90)

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
            direction_data = snapshot['direction_evidence']
            direction_error = abs((direction_data['measured_mic_angle'] - direction_data['requested_mic_angle'] + 180) % 360 - 180)
            assert direction_error < 10, direction_data
            record('actual_direction_estimator', evidence=direction_data)
            wait(lambda s: not s['voice_active'] and s['state'] == 'IDLE', timeout=15)

            # Raw proximity input must reach the collision classifier, not just echo in the UI.
            stop_sensor_heartbeat()
            start_sensor_heartbeat(include_front=False)
            page.wait_for_timeout(200)
            page.evaluate("document.querySelector('#proximityRange').value = '80'")
            page.locator('#sendProximity').click()
            snapshot = wait(lambda s: s['sensors'].get('front_severity') == 'danger'
                            and s['motion'].get('motion_frozen'))
            motion_status = snapshot.get('motion') or snapshot['sensors'].get('motion_status', snapshot.get('motion_status', {}))
            mode = motion_status.get('avoidance_mode', '')
            assert mode.startswith('hold_') or mode == 'adjust', motion_status
            page.wait_for_function(
                '''() => {
                    const text = document.querySelector('#motionAvoidance').innerText;
                    return text.includes('hold_') || text.includes('adjust');
                }''',
                timeout=5000,
            )
            ui_avoidance = page.locator('#motionAvoidance').inner_text()
            assert 'hold_' in ui_avoidance or 'adjust' in ui_avoidance, ui_avoidance
            record('raw_sensor_collision_to_motion_hold', state=snapshot['state'], motion=snapshot['motion'])
            page.evaluate("document.querySelector('#proximityRange').value = '0'")
            page.locator('#sendProximity').click()
            # Motion requires fresh range and matching FSR coverage in all
            # directions before it releases a stale-sensor hold. Keep the
            # clear readings alive through the classifier's clear dwell.
            clear_events = [
                {'type': 'proximity', 'value': 0},
                {'type': 'distance', 'side': 'left', 'metres': 1.0},
                {'type': 'distance', 'side': 'right', 'metres': 1.0},
                {'type': 'touch', 'sensor': 'head_bottom', 'value': 0},
                {'type': 'touch', 'sensor': 'head_left', 'value': 0},
                {'type': 'touch', 'sensor': 'head_right', 'value': 0},
            ]
            clear_until = time.monotonic() + 0.8
            while time.monotonic() < clear_until:
                for event in clear_events:
                    response = page.request.post(args.url + '/api/events', data=event)
                    assert response.status == 202, response.text()
                page.wait_for_timeout(80)
            snapshot = wait(lambda s: s['motion'].get('motion_frozen')
                            and s['motion'].get('avoidance_mode') == 'hold_replan'
                            and s['state'] == 'IDLE'
                            and all(s['sensors'].get(key) == 'safe'
                                    for key in ('front_severity', 'left_severity', 'right_severity')),
                            timeout=20)
            record('collision_clear_waits_for_fresh_intent', motion=snapshot['motion'])

            # Safe readings clear the hazard but must not resume the canceled
            # dance. A new bounded manual target is the fresh movement intent.
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
            snapshot = wait(lambda s: abs(s['positions'][0] - target) < .04
                            and not s['motion'].get('motion_frozen')
                            and s['motion'].get('avoidance_mode') == 'clear', timeout=20)
            record('fresh_manual_intent_releases_replan_hold', joint=joint_name,
                   target=target, observed=snapshot['positions'][0], motion=snapshot['motion'])
            page.locator('#resetIdle').click()
            snapshot = wait(lambda s: s['state'] == 'IDLE', timeout=10)
            stop_sensor_heartbeat()
            start_sensor_heartbeat()
            record('collision_quiet_recovery', motion=snapshot['motion'])

            response = page.request.post(args.url + '/api/events', data={'type': 'animation', 'name': 'unknown'})
            assert response.status == 400
            response = page.request.post(args.url + '/api/events', data={'type': 'voice_command', 'text': 'x' * 2001})
            assert response.status == 400
            record('invalid_requests_rejected')
            page.screenshot(path=args.screenshot, full_page=True)
            assert not errors, errors
            assert not console_errors, console_errors
            assert not failed_requests, failed_requests
            assert all(status == 200 for url, status in asset_status.items() if '/assets/' in url), asset_status
            record('no_browser_errors', console_errors=len(console_errors),
                   canceled_hidden_model_mesh_requests=len(canceled_model_requests))
            if args.pause_state_manager_pid:
                pid = args.pause_state_manager_pid
                command_path = Path(f'/proc/{pid}/cmdline')
                command = command_path.read_bytes().replace(b'\0', b' ').decode(errors='replace')
                executable = Path(command.split(maxsplit=1)[0]).name if command else ''
                assert executable in {'state_manager', 'state_manager_node'}, {
                    'pid': pid, 'cmdline': command,
                    'expected_executable': 'state_manager or state_manager_node',
                }
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
            try:
                stop_sensor_heartbeat()
            except Exception:
                pass
            Path(args.output).write_text(json.dumps({
                'results': evidence, 'error': failure, 'page_errors': errors,
                'console_errors': console_errors,
                'failed_requests': failed_requests,
                'canceled_hidden_model_mesh_requests': canceled_model_requests,
                'elapsed_seconds': time.monotonic() - started,
                'url': args.url,
            }, indent=2) + '\n')
            browser.close()


if __name__ == '__main__':
    main()
