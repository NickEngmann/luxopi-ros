#!/usr/bin/env python3
"""Exercise the live simulator via Chromium; no hardware or audio playback.

Requires optional Playwright and installed Chromium. Run against a dedicated
simulator graph: tests intentionally change lamp/sensor/animation state.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import signal
import sys
import time
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/luxo_behaviors'))
from luxo_behaviors.roarm_m3_kinematics import compute_m3_fk

from playwright.sync_api import sync_playwright


def matching_conversation_reply(snapshot, command, expected_replies, previous_response):
    """A new transcript alone is insufficient: the response may be from an old turn."""
    return (snapshot.get('transcript') == command
            and snapshot.get('response') in expected_replies
            and snapshot.get('response') != previous_response)


def idle_animation_names():
    """Read the driver list without importing ROS-only shared utilities."""
    source = Path(__file__).resolve().parents[1] / 'src/luxo_behaviors/luxo_behaviors/shared_utils.py'
    module = ast.parse(source.read_text())
    for item in module.body:
        if isinstance(item, ast.ClassDef) and item.name == 'IdleAnimationConfig':
            for statement in item.body:
                if isinstance(statement, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == 'DEFAULT_IDLE_ANIMATIONS'
                    for target in statement.targets
                ):
                    return set(ast.literal_eval(statement.value))
    raise AssertionError('IdleAnimationConfig.DEFAULT_IDLE_ANIMATIONS is missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', default='/tmp/luxopi-browser-e2e.json')
    parser.add_argument('--screenshot', default='/tmp/luxopi-simulator-dashboard.png')
    parser.add_argument('--expected-backend', choices=('kinematic', 'mujoco'),
                        help='fail if the dashboard reports a different simulation engine')
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
        def start_sensor_heartbeat(include_front=True, front_value=0):
            page.evaluate('''([includeFront, frontValue]) => {
                const events = [
                    {type:'distance', side:'left', metres:1.0},
                    {type:'distance', side:'right', metres:1.0},
                    {type:'touch', sensor:'head_bottom', value:0},
                    {type:'touch', sensor:'head_left', value:0},
                    {type:'touch', sensor:'head_right', value:0},
                ];
                if (includeFront) events.push({type:'proximity', value:frontValue});
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
            }''', [include_front, front_value])
        try:
            # The dashboard polls ROS state continuously, so waiting for a
            # network-idle window can never be a reliable page-load condition.
            page.goto(args.url, wait_until='domcontentloaded')
            page.wait_for_function('document.querySelector("#connectionText").textContent.includes("ROS API")')
            startup_snapshot = wait(lambda s:s.get('health',{}).get('healthy'), timeout=15)
            # Dedicated E2E simulators may intentionally start with synthetic
            # autonomy disabled. Enable it explicitly below instead of making
            # the dashboard's initial status a hidden runner prerequisite.
            autonomy_at_join = startup_snapshot.get('sensors',{}).get('simulator_autonomy_enabled')
            record('autonomy_status_on_initial_join', enabled=autonomy_at_join)
            if autonomy_at_join is not True:
                response = page.request.post(args.url + '/api/events',
                                             data={'type':'simulator_autonomy', 'enabled':True})
                assert response.status == 202, response.text()
                startup_snapshot = wait(lambda s:s.get('sensors',{}).get('simulator_autonomy_enabled') is True)
                record('autonomy_can_be_enabled_from_initially_paused_simulator')
            # Freeze autonomous motion while checking projected hover targets
            # and isolated stimuli. The dedicated idle-driver check restarts it.
            response = page.request.post(args.url + '/api/events',
                                         data={'type': 'simulator_autonomy', 'enabled': False})
            assert response.status == 202, response.text()
            wait(lambda s:s.get('sensors',{}).get('simulator_autonomy_enabled') is False)
            page.request.post(args.url + '/api/events', data={'type': 'cancel_animation'})
            page.request.post(args.url + '/api/events', data={'type': 'state_request', 'state': 'IDLE'})
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
            snapshot = wait(lambda s: s['state'] == 'IDLE' and not s.get('animation'), timeout=20)
            assert all(snapshot['health']['components'].values()), snapshot['health']
            backend = snapshot.get('simulation_backend', 'kinematic')
            assert backend in {'kinematic', 'mujoco'}, backend
            if args.expected_backend:
                assert backend == args.expected_backend, {
                    'expected_backend': args.expected_backend,
                    'reported_backend': backend,
                    'engine_caption': page.locator('#engineCaption').inner_text(),
                }
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
            expected_states = {
                'INITIALIZING', 'IDLE', 'ANIMATING', 'VOICE_FOLLOWING',
                'COLLISION_AVOIDING', 'RETURNING_HOME', 'ESCAPE_MODE',
                'USER_CONTROL', 'EMOTION_REACTING', 'PETTING', 'ERROR', 'SHUTDOWN',
            }
            visible_states = set(page.locator('#stateSelect option').all_text_contents())
            assert visible_states == expected_states, {
                'expected_states': sorted(expected_states),
                'visible_states': sorted(visible_states),
            }
            record('render_and_graph', nodes=snapshot['health']['node_count'],
                   model=page.locator('#modelStatus').inner_text(), animations=animation_count,
                   selectable_states=sorted(visible_states),
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

            # Hover the distal modeled link and require the exact URDF frame
            # plus the sensor-placement caveat in the live browser tooltip.
            hover_point = page.evaluate('(name) => window.luxoPartScreenPoint(name)', 'base_link')
            assert hover_point, 'M3 base link mesh did not expose a hover target'
            tooltip = ''
            hover_deadline = time.monotonic() + 5
            while time.monotonic() < hover_deadline and not tooltip:
                hover_point = page.evaluate('(name) => window.luxoPartScreenPoint(name)', 'base_link')
                page.mouse.move(hover_point['x'], hover_point['y'])
                page.wait_for_timeout(80)
                if page.locator('#partTooltip').evaluate('(el) => getComputedStyle(el).display') == 'block':
                    tooltip = page.locator('#partTooltip').inner_text()
            assert tooltip, 'hovering a visible robot mesh did not show its frame tooltip'
            hovered_frame = tooltip.splitlines()[0]
            assert hovered_frame in {'base_link', 'link1', 'link2', 'link3', 'link4', 'link5', 'gripper_link'}, tooltip
            assert 'physical sensor mount' in tooltip, tooltip
            record('hover_identifies_model_frame', frame=hovered_frame, tooltip=tooltip)

            # Check the added physical layout locators and ensure state-manager
            # RGBW/effect telemetry lights the modeled 60- and 16-pixel rings.
            visual_summary = page.evaluate('window.luxoVisualSummary()')
            assert visual_summary['ring60_pixels'] == 60
            assert visual_summary['ring16_pixels'] == 16
            assert set(visual_summary['sensors']) == {'left', 'right', 'rear', 'hand_tcp'}
            assert 'Luxonis' in visual_summary['camera']
            hover_expectations = {
                'left': 'Left-facing collision sensor',
                'right': 'Right-facing collision sensor',
                'rear': 'Rear-facing collision sensor',
                'hand_tcp': 'Collision sensor at the end of the hand TCP',
                'camera': 'OAK-D Lite',
                'ring60': '60-pixel ring placement guide',
                'ring16': '16-pixel ring placement guide',
            }
            for part, label in hover_expectations.items():
                part_tooltip = ''
                last_point = None
                hover_deadline = time.monotonic() + 3
                while time.monotonic() < hover_deadline and label not in part_tooltip:
                    point = page.evaluate('(name) => window.luxoSensorScreenPoint(name)', part) \
                        if part in visual_summary['sensors'] else page.evaluate(
                            '(name) => window.luxoVisualPartScreenPoint(name)', part)
                    last_point = point
                    assert point and 0 <= point['x'] <= page.viewport_size['width'] \
                        and 0 <= point['y'] <= page.viewport_size['height'], part
                    page.mouse.move(point['x'], point['y'])
                    page.wait_for_timeout(35)
                    part_tooltip = page.locator('#partTooltip').inner_text()
                assert label in part_tooltip, f'{part} hover label mismatch: {part_tooltip}; target={last_point}'
                record('hover_identifies_' + part, tooltip=part_tooltip)
            page.evaluate("window.luxoSetLightStateForTest({enabled:true,brightness:0.5,rgbw:[0,100,255,0],effect:'solid'})")
            lit = page.evaluate('window.luxoVisualSummary()')
            assert lit['ring60_lit'] == 60 and lit['ring16_lit'] == 16, lit
            page.evaluate("window.luxoSetLightStateForTest({enabled:false,effect:'off',rgbw:[0,0,0,0]})")
            dark = page.evaluate('window.luxoVisualSummary()')
            assert dark['ring60_lit'] == 0 and dark['ring16_lit'] == 0, dark
            record('hand_sensors_camera_and_led_rings', sensors=sorted(visual_summary['sensors']),
                   ring_pixels=[visual_summary['ring60_pixels'], visual_summary['ring16_pixels']],
                   state_manager_lighting='solid on/off rendered in both rings')

            # The limiter fails closed without fresh sensor coverage. Maintain
            # clear synthetic ranges/FSRs while testing bounded motion.
            # Wait for the controller's clear dwell too: a command sent
            # before that boundary is intentionally too old to release hold.
            start_sensor_heartbeat()
            snapshot = wait(lambda s: s['sensors'].get('front_severity') == 'safe'
                            and s['sensors'].get('left_severity') == 'safe'
                            and s['sensors'].get('right_severity') == 'safe'
                            and s['motion'].get('avoidance_mode') in ('clear', 'hold_replan')
                            and not s['motion'].get('avoidance_directions'), timeout=5)
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
            previous_response = state()['response']
            # Choose another bounded command if a prior run already left the
            # same reply, so this test requires an observable new response.
            animation = 'stretch' if previous_response in {"I'll nod for you.", 'Simulator heard: Please nod'} else 'nod'
            command_text = 'Please ' + animation
            expected_replies = {f"I'll {animation} for you.", 'Simulator heard: ' + command_text}
            page.locator('#commandInput').fill(command_text)
            page.locator('#commandForm button').click()
            snapshot = wait(lambda s: matching_conversation_reply(s, command_text, expected_replies, previous_response))
            page.wait_for_function('(text) => document.querySelector("#transcript").textContent === text', arg=command_text)
            page.wait_for_function('(reply) => document.querySelector("#response").textContent === reply', arg=snapshot['response'])
            record('conversation_text_and_reply', transcript=snapshot['transcript'], response=snapshot['response'],
                   previous_response=previous_response, matched_command=animation)
            # Animation commands are retimed to the simulated actuator limits;
            # the full nod gesture takes about a minute at those bounds.
            snapshot = wait(lambda s: s['status'] == 'idle' and s['state'] == 'IDLE', timeout=90)
            record('conversation_animation_returns_to_idle', state=snapshot['state'],
                   animation=snapshot.get('animation', ''))

            # Only externally meaningful recovery/manual states are selectable.
            # Behavior-owned states must be entered by their actual interaction.
            for state_name in ['RETURNING_HOME', 'USER_CONTROL', 'IDLE']:
                page.locator('#stateSelect').select_option(state_name)
                page.locator('#requestState').click()
                snapshot = wait(lambda s, expected=state_name:
                                s['sensors'].get('state_request_result', {}).get('requested') == expected,
                                timeout=10)
                result = snapshot['sensors']['state_request_result']
                assert result['success'], {'requested': state_name, 'response': result}
                record('manual_state_request', requested=state_name,
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
                # Compare the frame against the exact joint sample the 3D
                # renderer consumed; the next physics sample may arrive while
                # browser and API polling are on different intervals.
                pose = page.evaluate('window.luxoJointPositions')
                expected_frames = compute_m3_fk(pose)
                frames = page.evaluate('window.luxoM3FramePositions()')
                frame_expectations = expected_frames
                for name, expected in frame_expectations.items():
                    error = max(abs(actual - reference)
                                for actual, reference in zip(frames[name], expected))
                    assert error < 1e-4, {'frame': name, 'actual': frames[name],
                                          'expected': expected, 'error_m': error,
                                          'joints': pose}
                record('vendor_gripper_and_hand_tcp_frame', frames=frames,
                       expected=frame_expectations, tolerance_m=1e-4,
                       joints=pose)
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

            # User edits must survive several real polling turns before Send.
            page.evaluate('''() => {
                for (const [id,value] of [['brightnessRange','0.22'],['colorTempRange','0.7']]) {
                    const field=document.getElementById(id);field.value=value;
                    field.dispatchEvent(new Event('input',{bubbles:true}));
                }
                const checkbox=document.getElementById('lightsEnabled');checkbox.checked=false;
                checkbox.dispatchEvent(new Event('change',{bubbles:true}));
                document.getElementById('lightColor').value='blue';
            }''')
            page.wait_for_timeout(700)
            assert abs(float(page.locator('#brightnessRange').input_value())-.22)<.001
            assert abs(float(page.locator('#colorTempRange').input_value())-.7)<.001
            assert not page.locator('#lightsEnabled').is_checked()
            record('lighting_drafts_survive_live_polling')
            page.locator('#lightsEnabled').check()
            page.locator('#sendLights').click()
            snapshot = wait(lambda s: abs(s['sensors'].get('light_state', {}).get('brightness', -1) - .22) < .001
                            and s['sensors']['light_state']['rgbw'] == [0, 0, 255, 0]
                            and s['sensors']['light_state'].get('color_temperature') == .7)
            page.wait_for_function("Object.values(lightingDrafts).every(d=>!d.edited&&!d.pending)")
            page.wait_for_function("window.luxoVisualSummary().ring60_color === '#0000ff' && window.luxoVisualSummary().ring16_color === '#0000ff'")
            rendered_light = page.evaluate('window.luxoVisualSummary()')
            assert rendered_light['ring60_lit'] == 60 and rendered_light['ring16_lit'] == 16, rendered_light
            record('lamp_controls_to_consumer', light=snapshot['sensors']['light_state'])
            record('live_led_telemetry_updates_both_rendered_rings',
                   ring60_color=rendered_light['ring60_color'], ring16_color=rendered_light['ring16_color'],
                   lit_pixels=[rendered_light['ring60_lit'], rendered_light['ring16_lit']])

            page.locator('#animationNameSelect').select_option('dance')
            page.evaluate("document.querySelector('#animationSpeed').value = '2'")
            page.locator('#runAnimation').click()
            snapshot = wait(lambda s: s['state'] == 'ANIMATING')
            before = snapshot['positions']
            snapshot = wait(lambda s: any(abs(a-b) > .001 for a,b in zip(s['positions'], before)))
            page.locator('#cancelAnimation').click()
            snapshot = wait(lambda s: (s['sensors'].get('animation_result') or {}).get('state') == 'canceled')
            record('action_moves_and_cancels', result=snapshot['sensors']['animation_result'])
            wait(lambda s: s['state'] == 'IDLE')

            # Pair the explicit cancellation scenario with a no-cancel action:
            # it must publish moving joint feedback, finish successfully, and
            # return to IDLE on its own.
            page.locator('#animationNameSelect').select_option('acknowledge')
            page.locator('#animationSpeed').evaluate("el => {el.value='2';el.dispatchEvent(new Event('input',{bubbles:true}))}")
            page.locator('#runAnimation').click()
            snapshot = wait(lambda s: s['state'] == 'ANIMATING'
                            and s['sensors'].get('animation_request') == 'acknowledge')
            before_complete = snapshot['positions']
            snapshot = wait(lambda s: (s['sensors'].get('animation_result') or {}).get('state') == 'completed', timeout=90)
            assert any(abs(a-b) > .001 for a, b in zip(snapshot['positions'], before_complete)), snapshot
            snapshot = wait(lambda s: s['state'] == 'IDLE' and not s.get('animation'), timeout=10)
            record('action_completes_without_external_cancellation',
                   result=snapshot['sensors'].get('animation_result'), state=snapshot['state'])

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
            response = page.request.post(args.url + '/api/events',
                                         data={'type': 'sensor_fault', 'side': 'front', 'active': True})
            assert response.status == 202, response.text()
            start_sensor_heartbeat(include_front=False)
            page.wait_for_timeout(200)
            page.evaluate("document.querySelector('#proximityRange').value = '80'")
            page.locator('#sendProximity').click()
            # APDS confirmation needs distinct fresh samples, like a real
            # periodic sensor. Keep danger evidence fresh through braking
            # and browser rendering instead of depending on one cached sample.
            stop_sensor_heartbeat()
            start_sensor_heartbeat(front_value=80)
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
            stop_sensor_heartbeat()
            start_sensor_heartbeat(include_front=False)
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
            # Preserve fresh front coverage while the UI obtains USER_CONTROL
            # and submits the new intent; otherwise this test's deliberate
            # front-ray fault correctly reasserts hold_stale after 0.5 seconds.
            start_sensor_heartbeat()
            snapshot = wait(lambda s: s['motion'].get('motion_frozen')
                            and s['motion'].get('avoidance_mode') == 'hold_replan'
                            and s['state'] in ('IDLE', 'USER_CONTROL')
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
            response = page.request.post(args.url + '/api/events',
                                         data={'type': 'sensor_fault', 'side': 'front', 'active': False})
            assert response.status == 202, response.text()
            page.locator('#resetIdle').click()
            snapshot = wait(lambda s: s['state'] == 'IDLE', timeout=10)
            stop_sensor_heartbeat()
            start_sensor_heartbeat()
            record('collision_quiet_recovery', motion=snapshot['motion'])

            # Exercise APDS threshold behavior without the browser's periodic
            # sensor heartbeat masking the event path. Pause only the geometric front
            # source while these direct APDS controls are under test; otherwise
            # its no-obstacle 0 samples correctly replace the injected values.
            stop_sensor_heartbeat()
            response = page.request.post(args.url + '/api/events',
                                         data={'type': 'sensor_fault', 'side': 'front', 'active': True})
            assert response.status == 202, response.text()
            wait(lambda s: s['sensors'].get('simulated_sensor_faults', {}).get('front') is True,
                 timeout=3)
            # Flush any high sample retained by a previous interrupted run
            # after the geometric source has been paused.
            for _ in range(2):
                response = page.request.post(args.url + '/api/events', data={'type': 'proximity', 'value': 0})
                assert response.status == 202, response.text()
            wait(lambda s: s['sensors'].get('front_severity') == 'safe', timeout=3)
            page.evaluate("document.querySelector('#proximityRange').value = '80'")
            page.locator('#sendProximity').click()
            page.wait_for_timeout(100)
            page.locator('#sendProximity').click()
            snapshot = wait(lambda s: s['sensors'].get('front_severity') in ('warning', 'danger')
                            and s['state'] == 'COLLISION_AVOIDING', timeout=5)
            record('apds_debounce_then_collision_hold',
                   samples_sent=2,
                   second_sample_value=snapshot['sensors'].get('proximity'),
                   severity=snapshot['sensors'].get('front_severity'), state=snapshot['state'])
            page.evaluate("document.querySelector('#proximityRange').value = '0'")
            page.locator('#sendProximity').click()
            start_sensor_heartbeat()
            snapshot = wait(lambda s: s['state'] == 'IDLE'
                            and s['sensors'].get('front_severity') == 'safe', timeout=15)
            response = page.request.post(args.url + '/api/events',
                                         data={'type': 'sensor_fault', 'side': 'front', 'active': False})
            assert response.status == 202, response.text()
            record('apds_event_clears_with_fresh_safe_samples')

            # Inject one person/emotion event from the same visible controls.
            # SimCameraInteraction must buffer it, request the real action,
            # move the model, and complete back to IDLE.
            page.locator('#personPresent').check()
            page.locator('#emotion').select_option('happy')
            positions_before_emotion = snapshot['positions']
            page.locator('#sendVision').click()
            snapshot = wait(lambda s: s['sensors'].get('emotion') == 'happy'
                            and s['sensors'].get('person_present') is True, timeout=8)
            snapshot = wait(lambda s: s['state'] in ('EMOTION_REACTING', 'ANIMATING')
                            and s.get('animation') in {'excited', 'playful', 'dance'}, timeout=20)
            emotion_animation = snapshot['animation']
            snapshot = wait(lambda s: s.get('animation') == emotion_animation
                            and any(abs(a-b) > .001 for a, b in zip(
                                s['positions'], positions_before_emotion)), timeout=15)
            record('emotion_event_triggers_real_animation_and_motion',
                   emotion='happy', animation=emotion_animation,
                   position_before=positions_before_emotion, position_during=snapshot['positions'])
            snapshot = wait(lambda s: s['state'] == 'IDLE' and not s.get('animation'), timeout=90)
            record('emotion_animation_completes_and_recovers_to_idle', state=snapshot['state'])

            # The same dashboard obstacle control must attach a randomly
            # selected checked-in STL to the modeled distal sensor frame.
            stop_sensor_heartbeat()
            page.locator('[data-side="front"]').click()
            page.wait_for_function("window.luxoObstacleProps.front")
            prop = page.evaluate('window.luxoObstacleProps.front')
            assert prop in {'crate', 'wedge', 'can', 'cone', 'rock'}, prop
            snapshot = wait(lambda s: s.get('physics', {}).get('virtual_obstacles', {}).get('front') is True,
                            timeout=5)
            collider_enabled_during_stimulus = snapshot['physics']['virtual_obstacles']['front']
            page.locator('[data-side="front"]').click()
            start_sensor_heartbeat()
            snapshot = wait(lambda s: s['sensors'].get('front_severity') == 'safe'
                            and s.get('physics', {}).get('virtual_obstacles', {}).get('front') is False,
                            timeout=10)
            record('random_stl_physics_obstacle', asset=prop, frame='simulated_obstacle_front',
                   collider_enabled_during_stimulus=collider_enabled_during_stimulus,
                   collider_released=not snapshot['physics']['virtual_obstacles']['front'])

            # The physics profile must include the autonomous idle driver:
            # after a quiet interval, it should launch a registered idle action
            # and produce new joint feedback without any dashboard input.
            stop_sensor_heartbeat()
            for zone in ('antenna', 'top_front'):
                response = page.request.post(args.url + '/api/events',
                                             data={'type': 'petting_zone', 'zone': zone, 'active': False})
                assert response.status == 202, response.text()
            for sensor in ('head_bottom', 'head_left', 'head_right'):
                response = page.request.post(args.url + '/api/events',
                                             data={'type': 'touch', 'sensor': sensor, 'value': 0})
                assert response.status == 202, response.text()
            page.locator('#resetIdle').click()
            snapshot = wait(lambda s: s['state'] == 'IDLE' and not s.get('animation'), timeout=12)
            initial_positions = snapshot['positions']
            idle_animations = idle_animation_names()
            response = page.request.post(args.url + '/api/events',
                                         data={'type': 'simulator_autonomy', 'enabled': True})
            assert response.status == 202, response.text()
            snapshot = wait(lambda s: s['state'] == 'ANIMATING'
                            and s.get('animation') in idle_animations, timeout=35)
            started_animation = snapshot['animation']
            snapshot = wait(lambda s: s.get('animation') == started_animation
                            and any(abs(a-b) > .001 for a, b in zip(s['positions'], initial_positions)),
                            timeout=15)
            record('autonomous_idle_animation_moves_robot', animation=started_animation,
                   position_before=initial_positions, position_during=snapshot['positions'])

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
            # E2E may be interrupted between sensor stimuli; release latched
            # virtual petting and return the simulator to a known idle state.
            try:
                for zone in ('antenna', 'top_front'):
                    page.request.post(args.url + '/api/events',
                                      data={'type': 'petting_zone', 'zone': zone, 'active': False},
                                      timeout=3000)
                for sensor in ('head_bottom', 'head_left', 'head_right'):
                    page.request.post(args.url + '/api/events',
                                      data={'type': 'touch', 'sensor': sensor, 'value': 0},
                                      timeout=3000)
                for side in ('front', 'left', 'right'):
                    page.request.post(args.url + '/api/events',
                                      data={'type': 'sensor_fault', 'side': side, 'active': False},
                                      timeout=3000)
                page.request.post(args.url + '/api/events', data={'type': 'proximity', 'value': 0},
                                  timeout=3000)
                page.request.post(args.url + '/api/events', data={'type': 'state_request', 'state': 'IDLE'},
                                  timeout=3000)
                page.request.post(args.url + '/api/events', data={'type': 'simulator_autonomy', 'enabled': True},
                                  timeout=3000)
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
