"""Silent visual speaking duration; WAV inspection never opens an audio device."""
import math
import wave


def speaking_preview_duration(result, fallback, *, use_synthesized_audio=False):
    duration=float(fallback)
    if not math.isfinite(duration):duration=0.
    if use_synthesized_audio and isinstance(result.get('audio_path'),str):
        try:
            with wave.open(result['audio_path'],'rb') as audio:
                duration=audio.getnframes()/audio.getframerate()
        except (OSError,EOFError,wave.Error,ZeroDivisionError):
            pass
    return max(0.,min(10.,duration))
