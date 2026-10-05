"""ROS-free validators and FSM mapping used by simulation interaction nodes."""

from luxo_behaviors.state_machine import LuxoState


VOICE_CUE_FOR_STATUS = {
    "listening": "listening",
    "thinking": "thinking",
    "speaking": "speaking",
}


class VoiceCueLifecycle:
    """Bounded, session-scoped visual cues that never own conversation state."""

    def __init__(self, max_pending=8):
        self.max_pending = max_pending
        self.generation = 0
        self.active = False
        self.suppressed = False
        self._pending = []
        self._transcript_pending = False

    def status(self, value):
        """Record a voice status and return the current session generation."""
        if value == "idle":
            was_active = self.active
            allow_settle = was_active and not self.suppressed
            if self.active:
                self.generation += 1
            self.active = False
            self._pending = ["settle"] if allow_settle else []
            self.suppressed = False
            self._transcript_pending = False
            return self.generation
        if value not in VOICE_CUE_FOR_STATUS:
            return self.generation
        if not self.active:
            self.generation += 1
            self.active = True
            self.suppressed = False
            self._pending.clear()
            self._pending.append("listening")
            if self._transcript_pending:
                self._append("acknowledge")
                self._transcript_pending = False
            if value == "listening":
                return self.generation
        cue = VOICE_CUE_FOR_STATUS[value]
        if not self.suppressed and (not self._pending or self._pending[-1] != cue):
            if len(self._pending) >= self.max_pending:
                self._pending.pop(0)
            self._pending.append(cue)
        return self.generation

    def transcript(self):
        if self.active and not self.suppressed:
            self._append("acknowledge")
        elif not self.active:
            self._transcript_pending = True

    def suppress(self):
        """Drop stale presentation after a real action takes motion authority."""
        self.suppressed = True
        self._pending.clear()

    def _append(self, cue):
        if cue not in self._pending:
            if len(self._pending) >= self.max_pending:
                self._pending.pop(0)
            self._pending.append(cue)

    def pop(self):
        if not self._pending or self.suppressed:
            return None
        if not self.active and self._pending[0] != "settle":
            return None
        return self._pending.pop(0)

    def is_current(self, generation):
        return self.active and generation == self.generation


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
