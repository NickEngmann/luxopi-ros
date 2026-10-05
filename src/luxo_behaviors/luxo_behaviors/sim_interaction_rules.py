"""ROS-free validators and FSM mapping used by simulation interaction nodes."""

from luxo_behaviors.state_machine import LuxoState


def parse_petting_event(value):
    """Parse only the collision classifier's bounded petting event format."""
    if not isinstance(value, str):
        raise ValueError("petting event must be text")
    action, separator, raw_pressure = value.partition(":")
    if not separator or action not in {"petting_started", "petting_stopped"}:
        raise ValueError("unsupported petting event")
    try:
        pressure = int(raw_pressure)
    except ValueError as exc:
        raise ValueError("petting pressure must be an integer") from exc
    if not 0 <= pressure <= 255:
        raise ValueError("petting pressure must be between 0 and 255")
    if action == "petting_started" and pressure <= 1:
        raise ValueError("petting start pressure must exceed 1")
    return action, pressure


def animation_state_for(category, trigger_source=None):
    """Map plugin category to FSM state while preserving petting ownership."""
    if trigger_source == "emotion" or category == "emotion":
        return LuxoState.EMOTION_REACTING
    if category == "petting":
        return LuxoState.PETTING
    return LuxoState.ANIMATING
