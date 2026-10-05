"""Bounded saved-WAV intake for the simulator; never opens an audio device."""
import io
from pathlib import Path
import re
import uuid
import wave

MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_SAVED_CLIPS = 128
AUDIO_NAME = re.compile(r"[a-f0-9]{32}\.wav\Z")


def validate_audio_name(name):
    if not isinstance(name, str) or not AUDIO_NAME.fullmatch(name):
        raise ValueError("Audio name must be a generated WAV basename")
    return name


def save_audio(payload, directory):
    """Save validated 0–30s mono/stereo PCM WAV in an explicit private directory."""
    if not directory:
        raise ValueError("Saved-audio recognition is not enabled")
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_AUDIO_BYTES:
        raise ValueError("WAV upload must contain 1–8388608 bytes")
    try:
        with wave.open(io.BytesIO(payload), 'rb') as audio:
            channels, width, rate, frames = (
                audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes())
            if channels not in (1, 2) or width not in (1, 2, 3, 4) or not 8000 <= rate <= 96000:
                raise ValueError("Supply mono/stereo PCM WAV at 8–96 kHz")
            if not 0 < frames <= rate * 30:
                raise ValueError("Supply 0–30 seconds of audio")
            if len(audio.readframes(frames)) != frames * channels * width:
                raise ValueError("WAV data is truncated")
    except (wave.Error, EOFError) as exc:
        raise ValueError("Supply an uncompressed PCM WAV file") from exc
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if sum(1 for clip in root.glob('*.wav') if AUDIO_NAME.fullmatch(clip.name)) >= MAX_SAVED_CLIPS:
        raise ValueError("Simulator audio queue storage is full")
    name = uuid.uuid4().hex + '.wav'
    target = root / name
    with target.open('xb') as output:
        target.chmod(0o600)
        output.write(payload)
    return name


def remove_audio(name, directory):
    if directory:
        (Path(directory) / validate_audio_name(name)).unlink(missing_ok=True)
