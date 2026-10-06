"""Run real UI control logic under Node, with polling and delayed acknowledgments."""
from pathlib import Path
import subprocess


def test_lighting_drafts_survive_poll_and_submit_until_acknowledged():
    html=(Path(__file__).parents[1]/'src/luxo_behaviors/luxo_behaviors/simulator_ui.html').read_text()
    logic=html.split('const lightingDrafts=',1)[1].split('function update(d)',1)[0]
    logic='const lightingDrafts='+logic
    code="""
const assert=require('assert');const elements={};const $=id=>elements[id]||(elements[id]={value:'0.5',checked:true,textContent:''});
let resolveRequest;const send=event=>new Promise(resolve=>{if(event.type==='brightness')resolveRequest=resolve;else resolve(true)});
"""+logic+"""
(async()=>{
 syncLighting('brightness',.5);$('brightnessRange').value='.8';editLighting('brightness');syncLighting('brightness',.5);
 assert.equal($('brightnessRange').value,'.8');
 const submitted=submitLighting();syncLighting('brightness',.5);assert.equal($('brightnessRange').value,'.8');
 resolveRequest(true);await submitted;syncLighting('brightness',.5);assert.equal($('brightnessRange').value,'.8');
 // A new edit while a reply is in flight must survive that old acknowledgment.
 $('brightnessRange').value='.9';editLighting('brightness');syncLighting('brightness',.8);assert.equal($('brightnessRange').value,'.9');
 const next=submitLighting();resolveRequest(true);await next;syncLighting('brightness',.9);assert.equal(lightingDrafts.brightness.edited,false);
 syncLighting('brightness',.3);assert.equal($('brightnessRange').value,.3);
 $('lightsEnabled').checked=false;editLighting('enabled');syncLighting('enabled',true);assert.equal($('lightsEnabled').checked,false);
 $('colorTempRange').value='.2';editLighting('color_temperature');syncLighting('color_temperature',.6);assert.equal($('colorTempRange').value,'.2');
 const detail=healthDetail({healthy:false,reasons:['state_not_ready'],state_fresh:true,joint_state_fresh:true},'ERROR');
 assert(detail.includes('ERROR is not ready'));assert(!detail.includes('stale'));
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    subprocess.run(['node','-e',code],check=True,capture_output=True,text=True,timeout=10)


def test_complete_nonmodule_script_has_valid_javascript_syntax(tmp_path):
    html=(Path(__file__).parents[1]/'src/luxo_behaviors/luxo_behaviors/simulator_ui.html').read_text()
    script=tmp_path/'ui.js';script.write_text(html.split('<script>',1)[1].split('</script>',1)[0])
    subprocess.run(['node','--check',str(script)],check=True,capture_output=True,text=True)
