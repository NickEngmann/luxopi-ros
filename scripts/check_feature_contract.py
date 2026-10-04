#!/usr/bin/env python3
"""Inventory actual registered features; no ROS/device imports required."""
import ast
import importlib
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT/'src/luxo_behaviors/luxo_behaviors'
sys.path.insert(0,str(PACKAGE.parent))
from luxo_behaviors.animation_plugin_base import AnimationPlugin
from luxo_behaviors.state_machine import LuxoState
MODULES = ('action_animations','emotion_animations','response_animations','idle_animations','petting_animations')


def inventory():
    plugins = []
    for module_name in MODULES:
        module = importlib.import_module('luxo_behaviors.animation_plugins.'+module_name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls is not AnimationPlugin and issubclass(cls,AnimationPlugin):
                plugin = cls(SimpleNamespace())
                frames, durations = plugin.get_keyframes()
                plugins.append(dict(name=plugin.name, category=plugin.get_category(),
                    keyframes=len(frames), dimensions=sorted(set(map(len,frames))),
                    duration_seconds=round(sum(durations),4)))
    tree = ast.parse((PACKAGE/'command_behavior.py').read_text())
    mappings = next(node.value for node in ast.walk(tree)
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='command_mappings' for t in node.targets))
    return dict(states=[state.name for state in LuxoState],
                animations=sorted(plugins,key=lambda p:p['name']),
                voice_command_ids={str(k):v for k,v in ast.literal_eval(mappings).items()})


def main():
    actual = inventory()
    expected = json.loads((ROOT/'docs/feature-coverage.json').read_text())['inventory']
    if actual != expected:
        print(json.dumps(actual,indent=2))
        raise SystemExit('Feature contract changed; review manifest before accepting additions/removals')
    print(json.dumps(dict(animations=len(actual['animations']),states=len(actual['states']),
                         voice_command_ids=len(actual['voice_command_ids']),contract='pass')))

if __name__ == '__main__':
    main()
