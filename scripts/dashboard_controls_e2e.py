#!/usr/bin/env python3
"""Press and verify every usable simulator dashboard control through Chromium."""
import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

STATES = ['INITIALIZING','IDLE','ANIMATING','VOICE_FOLLOWING','COLLISION_AVOIDING',
          'RETURNING_HOME','ESCAPE_MODE','USER_CONTROL','EMOTION_REACTING','PETTING','ERROR','SHUTDOWN']
COLORS = ['white','red','orange','yellow','green','cyan','blue','purple']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', default='docs/validation/2026-10-06/dashboard-controls-e2e.json')
    args = parser.parse_args()
    evidence, errors = [], []
    start = time.monotonic()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1200})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.goto(args.url, wait_until='domcontentloaded')
        page.wait_for_function('document.querySelector("#connectionText").textContent.includes("ROS API")', timeout=30000)

        def snapshot():
            return page.evaluate('async()=> (await fetch("/api/state",{cache:"no-store"})).json()')

        def wait(pred, timeout=12):
            deadline = time.monotonic()+timeout
            while time.monotonic()<deadline:
                current=snapshot()
                if pred(current): return current
                page.wait_for_timeout(100)
            raise AssertionError({'timeout':timeout,'state':snapshot()})

        def record(name, **detail):
            evidence.append({'scenario':name,'passed':True,**detail})
            print(json.dumps(evidence[-1]), flush=True)

        def set_range(selector, value):
            page.locator(selector).evaluate('(el,value)=>{el.value=String(value);el.dispatchEvent(new Event("input",{bubbles:true}))}', value)

        def click(selector, name, wait_for=None):
            locator=page.locator(selector)
            locator.wait_for(state='visible',timeout=5000)
            assert locator.is_enabled(), f'{name}: control unexpectedly disabled'
            locator.click(timeout=5000)
            if wait_for:
                result=wait(wait_for)
                keys=('state_request_result','manual_pose_result','animation_request','animation_result','animation_cancel_result','animation_cancel_requested','last_voice_command','simulation_speed','simulator_autonomy_enabled','gesture','proximity','requested_mic_direction','petting_zone_requested','simulated_obstacles','vision_request','light_color_requested','light_control_requested','brightness_requested','color_temperature_requested')
                record(name,result={'state':result.get('state'),'animation':result.get('animation'),'physics_time_scale':result.get('physics',{}).get('time_scale'),'sensors':{key:result.get('sensors',{})[key] for key in keys if key in result.get('sensors',{})}})
            else:
                page.wait_for_timeout(250)
                record(name)

        try:
            # Pause synthetic idle movement while controls are individually driven.
            response=page.request.post(args.url+'/api/events',data={'type':'simulator_autonomy','enabled':False})
            assert response.status==202,response.text()
            page.request.post(args.url+'/api/events',data={'type':'cancel_animation'})
            page.request.post(args.url+'/api/events',data={'type':'state_request','state':'IDLE'})
            wait(lambda s:s.get('health',{}).get('healthy') and s.get('state')=='IDLE',timeout=30)
            record('pause_autonomous_activity_for_isolated_controls')
            initial=snapshot()
            assert page.locator('#simulationSpeed').input_value()=='1'
            # Exercise all UI view/model choices; the legacy view has both renderers.
            page.wait_for_function("document.querySelector('#view2d').onclick !== null", timeout=10000)
            page.locator('#modelSelect').evaluate("el=>{el.value='legacy';el.dispatchEvent(new Event('change',{bubbles:true}))}")
            # The incoming six-axis joint snapshot can select the M3 model on
            # startup. Wait for the explicit user selection to win that race.
            page.wait_for_function("window.luxoModelChoice===true && document.querySelector('#modelSelect').value==='legacy' && !document.querySelector('#view2d').disabled", timeout=5000)
            click('#view2d','view_fk_2d',lambda s: page.locator('#robotCanvas2D').is_visible())
            click('#view3d','view_mesh_3d',lambda s: page.locator('#robotCanvas3D').is_visible())
            page.locator('#modelSelect').select_option('m3'); page.wait_for_timeout(150)
            record('select_vendor_m3_model', selected=page.locator('#modelSelect').input_value())
            # Time scale is an applied, observable simulator setting at all supported values.
            for scale in (2,3,1):
                page.locator('#simulationSpeed').select_option(str(scale))
                wait(lambda s:s.get('simulation_speed')==float(scale))
                record(f'simulation_speed_{scale}x',scale=scale)
            # User command form and its three quick-command buttons.
            page.locator('#commandInput').fill('Tell me a joke')
            click('#commandForm button[type=submit]','voice_form_submit',lambda s:s.get('sensors',{}).get('last_voice_command')=='Tell me a joke')
            for text in ('Please dance','Please nod','Tell me a joke'):
                click(f'[data-command="{text}"]',f'quick_command_{text.lower().replace(" ","_")}',lambda s,t=text:s.get('sensors',{}).get('last_voice_command')==t)
            # Audio controls are deliberately unavailable in this silent physics profile.
            assert page.locator('#uploadAudio').is_disabled() and page.locator('#audioFile').is_disabled()
            assert page.locator('#recordMic').is_disabled()
            record('audio_controls_disabled_without_audio_profile',reason=page.locator('#audioUploadStatus').inner_text())
            # Action goal and cancellation through the visible controls.
            page.locator('#animationNameSelect').select_option('nod')
            set_range('#animationSpeed',2)
            click('#runAnimation','run_animation_button',lambda s:s.get('sensors',{}).get('animation_request')=='nod')
            click('#cancelAnimation','cancel_animation_button',lambda s:s.get('sensors',{}).get('animation_cancel_requested') is True or s.get('sensors',{}).get('animation_cancel_result') is not None)
            # Queue cancellation before the asynchronous ROS action goal can
            # return its handle. This used to lose the cancel and start motion.
            for event in (
                {'type':'animation','name':'dance','speed':0.5},
                {'type':'cancel_animation'},
            ):
                response=page.request.post(args.url+'/api/events',data=event)
                assert response.status==202,response.text()
            result=wait(lambda s:s.get('sensors',{}).get('animation_cancel_result'),timeout=12)
            cancel_result=result['sensors']['animation_cancel_result']
            assert cancel_result.get('accepted') is True, cancel_result
            record('cancel_animation_before_goal_ack',result=cancel_result)
            # Exercise all state selector/button paths, then use reset after each.
            for state in STATES:
                page.locator('#stateSelect').select_option(state)
                click('#requestState',f'request_state_{state.lower()}',lambda s,st=state:(
                    s.get('sensors',{}).get('state_request_result',{}).get('requested')==st
                    and s.get('sensors',{}).get('state_request_result',{}).get('success') is True
                    and s.get('state')==st))
                req=snapshot()['sensors']['state_request_result']
                assert req.get('success') is True, {'state':state,'result':req}
                click('#resetIdle',f'reset_idle_after_{state.lower()}',lambda s:(
                    s.get('state')=='IDLE'
                    and s.get('sensors',{}).get('state_request_result',{}).get('requested')=='IDLE'
                    and s['sensors']['state_request_result'].get('success')))
            # Both manual-pose actions and the selected six-axis controls.
            sliders=page.locator('#manualJointFields input[type=range]')
            assert sliders.count()==6
            sliders.nth(0).evaluate('(el)=>{el.value="0.15";el.dispatchEvent(new Event("input",{bubbles:true}))}')
            click('#applyManualPose','apply_manual_pose',lambda s:s.get('sensors',{}).get('manual_pose_result',{}).get('success') is True)
            click('#resetManualPose','reset_manual_pose',lambda s:s.get('sensors',{}).get('manual_pose_result',{}).get('success') is True)
            # Light button at every permitted color. Toggle and range settings then apply.
            for color in COLORS:
                page.locator('#lightColor').select_option(color)
                click('#sendLights',f'apply_lights_{color}',lambda s,c=color:s.get('sensors',{}).get('light_color_requested')==c)
            page.locator('#lightsEnabled').uncheck(); set_range('#brightnessRange',0.4); set_range('#colorTempRange',0.7)
            click('#sendLights','apply_lights_disabled_and_ranges',lambda s:s.get('sensors',{}).get('light_control_requested') is False)
            page.locator('#lightsEnabled').check(); click('#sendLights','apply_lights_enabled',lambda s:s.get('sensors',{}).get('light_control_requested') is True)
            # Four angle presets plus the injection action.
            for degrees in (0,90,180,270):
                click(f'[data-direction="{degrees}"]',f'select_direction_{degrees}',lambda s,d=degrees:int(page.locator('#directionRange').input_value())==d)
                click('#sendDirection',f'inject_direction_{degrees}',lambda s,d=degrees:s.get('sensors',{}).get('requested_mic_direction')==float(d))
            # Each touch/FSR control must latch, publish pressure, and release to zero.
            for sensor in ('head_top','head_left','head_right','head_bottom'):
                selector=f'[data-touch="{sensor}"]'
                click(selector,f'touch_{sensor}_press',lambda s,k=sensor:s.get('sensors',{}).get(k)==3)
                click(selector,f'touch_{sensor}_release',lambda s,k=sensor:s.get('sensors',{}).get(k)==0)
            for zone in ('top_front','antenna'):
                selector=f'[data-petting-zone="{zone}"]'
                click(selector,f'petting_{zone}_press',lambda s,z=zone:s.get('sensors',{}).get('petting_zone_requested',{}).get('active') is True and s['sensors']['petting_zone_requested'].get('zone')==z)
                click(selector,f'petting_{zone}_release',lambda s,z=zone:s.get('sensors',{}).get('petting_zone_requested',{}).get('active') is False and s['sensors']['petting_zone_requested'].get('zone')==z)
            # Every visible APDS gesture goes through the real ROS topic bridge.
            for gesture in ('left','right','up','down','near'):
                click(f'[data-gesture="{gesture}"]',f'apds_gesture_{gesture}',lambda s,g=gesture:s.get('sensors',{}).get('gesture')==g)
            set_range('#proximityRange',190)
            click('#sendProximity','apds_proximity_near',lambda s:s.get('sensors',{}).get('proximity')==190)
            set_range('#proximityRange',0)
            click('#sendProximity','apds_proximity_clear',lambda s:s.get('sensors',{}).get('proximity')==0)
            # Both side range sensors publish centimetre inputs through the UI.
            set_range('#leftDistance',0.2); set_range('#rightDistance',0.25)
            click('#sendDistances','publish_left_and_right_ranges',lambda s:s.get('sensors',{}).get('right_distance')==0.25)
            # Each obstacle control activates and clears its matching virtual STL/range event.
            for side in ('front','left','right'):
                selector=f'[data-side="{side}"]'
                click(selector,f'obstacle_{side}_activate',lambda s,k=side:s.get('sensors',{}).get('simulated_obstacles',{}).get(k) is True)
                click(selector,f'obstacle_{side}_clear',lambda s,k=side:s.get('sensors',{}).get('simulated_obstacles',{}).get(k) is False)
            # A refresh must restore latched control state so the first click releases it.
            for label, selector, event, active_pred, clear_pred in (
                ('touch','[data-touch="head_top"]',{'type':'touch','sensor':'head_top','value':3},
                 lambda s:s.get('sensors',{}).get('head_top')==3,
                 lambda s:s.get('sensors',{}).get('head_top')==0),
                ('petting','[data-petting-zone="antenna"]',{'type':'petting_zone','zone':'antenna','active':True},
                 lambda s:s.get('sensors',{}).get('petting_zone_requested',{}).get('active') is True,
                 lambda s:s.get('sensors',{}).get('petting_zone_requested',{}).get('active') is False),
                ('obstacle','[data-side="left"]',{'type':'collision','side':'left','active':True},
                 lambda s:s.get('sensors',{}).get('simulated_obstacles',{}).get('left') is True,
                 lambda s:s.get('sensors',{}).get('simulated_obstacles',{}).get('left') is False),
            ):
                assert page.request.post(args.url+'/api/events',data=event).status==202
                wait(active_pred)
                page.reload(wait_until='domcontentloaded')
                page.wait_for_function('document.querySelector("#connectionText").textContent.includes("ROS API")')
                wait(active_pred)
                page.wait_for_function('(selector)=>document.querySelector(selector).getAttribute("aria-pressed")==="true"',arg=selector)
                record(f'{label}_latch_restored_after_refresh')
                click(selector,f'{label}_first_click_releases_after_refresh',clear_pred)
            # Sensor dropouts stop one raw range stream and must fail safe until recovery.
            for side in ('front','left','right'):
                for event in (
                    {'type':'proximity','value':0},
                    {'type':'distance','side':'left','metres':1.0},
                    {'type':'distance','side':'right','metres':1.0},
                    *({'type':'touch','sensor':name,'value':0} for name in ('head_bottom','head_left','head_right')),
                ):
                    response=page.request.post(args.url+'/api/events',data=event)
                    assert response.status==202,response.text()
                wait(lambda s:not s.get('motion',{}).get('stale',[]),timeout=5)
                selector=f'[data-sensor-fault="{side}"]'
                click(selector,f'{side}_sensor_fault_enable',lambda s,k=side:s.get('sensors',{}).get('simulated_sensor_faults',{}).get(k) is True)
                held=wait(lambda s,k=side:s.get('motion',{}).get('avoidance_mode')=='hold_stale' and k in s.get('motion',{}).get('stale',[]),timeout=8)
                record(f'{side}_sensor_dropout_causes_stale_coverage_hold',result={'avoidance_mode':held['motion']['avoidance_mode'],'stale':held['motion']['stale']})
                click(selector,f'{side}_sensor_fault_clear',lambda s,k=side:s.get('sensors',{}).get('simulated_sensor_faults',{}).get(k) is False)
                recovered=wait(lambda s,k=side:s.get('motion',{}).get('avoidance_mode') not in {'hold_stale','hold_unconfigured'} and k not in s.get('motion',{}).get('stale',[]),timeout=8)
                record(f'{side}_sensor_recovery_restores_coverage',result={'avoidance_mode':recovered['motion']['avoidance_mode'],'stale':recovered['motion']['stale']})
            # Camera/person emotion submit and validation for analyze-without-image.
            page.locator('#emotion').select_option('happy'); set_range('#personDistance',1.2)
            click('#sendVision','publish_happy_person',lambda s:s.get('sensors',{}).get('vision_request',{}).get('emotion')=='happy')
            page.locator('#personPresent').uncheck()
            click('#sendVision','publish_person_absent',lambda s:s.get('sensors',{}).get('vision_request',{}).get('person_present') is False)
            click('#analyzeVisionImage','analyze_image_without_file_validation',lambda s:page.locator('#visionImageStatus').inner_text().startswith('Choose a JPEG or PNG'))
            # Restore neutral simulator after deliberately exercising every input.
            page.request.post(args.url+'/api/events',data={'type':'proximity','value':0})
            for sensor in ('head_top','head_left','head_right','head_bottom'):
                page.request.post(args.url+'/api/events',data={'type':'touch','sensor':sensor,'value':0})
            for zone in ('top_front','antenna'):
                page.request.post(args.url+'/api/events',data={'type':'petting_zone','zone':zone,'active':False})
            for side in ('left','right'):
                page.request.post(args.url+'/api/events',data={'type':'distance','side':side,'metres':1.0})
            for side in ('front','left','right'):
                page.request.post(args.url+'/api/events',data={'type':'collision','side':side,'active':False})
            page.request.post(args.url+'/api/events',data={'type':'vision','person_present':False,'emotion':'neutral','metres':1.5})
            page.locator('#stateSelect').select_option('IDLE'); click('#resetIdle','final_recovery_to_idle',lambda s:s.get('state')=='IDLE')
            page.locator('#simulationSpeed').select_option('1'); wait(lambda s:s.get('simulation_speed')==1.0)
            response=page.request.post(args.url+'/api/events',data={'type':'simulator_autonomy','enabled':True})
            assert response.status==202,response.text()
            wait(lambda s:s.get('sensors',{}).get('simulator_autonomy_enabled') is True)
            record('restore_autonomous_activity')
            final=snapshot()
            assert final.get('health',{}).get('healthy') is True, final.get('health')
            assert len(evidence)>=40, len(evidence)
        finally:
            # Always remove injected inputs, including when an assertion fails midway.
            for event in (
                {'type':'proximity','value':0},
                *({'type':'touch','sensor':name,'value':0} for name in ('head_top','head_left','head_right','head_bottom')),
                *({'type':'petting_zone','zone':zone,'active':False} for zone in ('top_front','antenna')),
                {'type':'distance','side':'left','metres':1.0},
                {'type':'distance','side':'right','metres':1.0},
                *({'type':'collision','side':side,'active':False} for side in ('front','left','right')),
                *({'type':'sensor_fault','side':side,'active':False} for side in ('front','left','right')),
                {'type':'vision','person_present':False,'emotion':'neutral','metres':1.5},
                {'type':'state_request','state':'IDLE'},
                {'type':'simulator_autonomy','enabled':True},
            ):
                try:
                    page.request.post(args.url+'/api/events',data=event,timeout=2000)
                except Exception:
                    pass
            browser.close()
    result={'suite':'dashboard_controls_e2e','passed':len(evidence),'failed':len(errors),'duration_seconds':round(time.monotonic()-start,2),'scenarios':evidence,'browser_errors':errors}
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'failed':result['failed'],'duration_seconds':result['duration_seconds'],'output':str(out)},indent=2))
    assert not errors, errors


if __name__=='__main__': main()
