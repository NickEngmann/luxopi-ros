"""Neutral animation capability registry shared by ROS, simulator and text adapters."""

import importlib
import inspect

from luxo_behaviors.animation_plugin_base import AnimationPlugin


ANIMATION_PLUGIN_MODULES = (
    "luxo_behaviors.animation_plugins.emotion_animations",
    "luxo_behaviors.animation_plugins.action_animations",
    "luxo_behaviors.animation_plugins.response_animations",
    "luxo_behaviors.animation_plugins.idle_animations",
    "luxo_behaviors.animation_plugins.petting_animations",
)


def discover_animation_classes():
    """Return the unique plugin-name to class mapping, without ROS imports."""
    classes = {}
    for module_name in ANIMATION_PLUGIN_MODULES:
        module = importlib.import_module(module_name)
        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if candidate is AnimationPlugin or not issubclass(candidate, AnimationPlugin):
                continue
            instance = candidate(None)
            name = instance.name
            if not isinstance(name, str) or not name or name in classes:
                raise ValueError(f"invalid or duplicate animation capability: {name!r}")
            classes[name] = candidate
    return classes


ANIMATION_CLASSES = discover_animation_classes()
ANIMATION_NAMES = frozenset(ANIMATION_CLASSES)


def load_animation_plugins(node):
    """Instantiate and validate all capabilities for a running action server."""
    plugins = {}
    for name, plugin_class in ANIMATION_CLASSES.items():
        plugin = plugin_class(node)
        if not plugin.validate_keyframes():
            raise ValueError(f"invalid animation plan for capability {name!r}")
        plugins[name] = plugin
    return plugins
