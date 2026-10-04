"""Shared microphone direction estimation and silent simulated array fixtures.

ReSpeaker raw microphones are channels 1..4 in the six-channel stream.
Opposite pairs span 81.27 mm; calibration/sign convention matches MicArray.
"""
import numpy as np
from .gcc_phat import gcc_phat

SOUND_SPEED = 343.2
MIC_DISTANCE_4 = 0.08127
MAX_TDOA_4 = MIC_DISTANCE_4 / SOUND_SPEED


def estimate_direction(frames, rate=16000, channels=6, direction_offset=0, interp=16):
    frames = np.asarray(frames)
    if channels not in (4, 6) or frames.size == 0:
        return None
    if frames.ndim != 1 or frames.size % channels:
        raise ValueError('Expected complete interleaved microphone frames')
    frames = frames.astype(np.float64)
    raw = frames.reshape(-1, channels)
    raw = raw[:, 1:5] if channels == 6 else raw
    if not np.all(np.isfinite(raw)) or np.max(np.abs(raw)) < 100:
        return None
    theta = []
    for first, second in ((0, 2), (1, 3)):
        tau, _ = gcc_phat(raw[:, first], raw[:, second], fs=rate,
                          max_tau=MAX_TDOA_4, interp=interp)
        theta.append(np.degrees(np.arcsin(np.clip(tau / MAX_TDOA_4, -1, 1))))
    if abs(theta[0]) < abs(theta[1]):
        guess = theta[0] % 360 if theta[1] > 0 else 180 - theta[0]
    else:
        guess = theta[1] % 360 if theta[0] < 0 else 180 - theta[1]
        guess = (guess + 270) % 360
    return float((guess - 120 + direction_offset) % 360)


def circular_statistics(angles):
    radians = np.radians(angles)
    x, y = np.mean(np.cos(radians)), np.mean(np.sin(radians))
    strength = np.clip(x*x + y*y, np.finfo(float).tiny, 1.0)
    return float(np.degrees(np.arctan2(y, x)) % 360), float(np.degrees(np.sqrt(-np.log(strength))))


def robot_angle(angle, distance=1.0, offset_x=0.07, offset_y=0.0):
    distance = np.clip(distance, 0.3, 3.0)
    rad = np.radians(angle)
    corrected = np.degrees(np.arctan2(distance*np.sin(rad)-offset_y,
                                    distance*np.cos(rad)-offset_x)) % 360
    return float(-corrected)


def synthesize_direction(angle, rate=16000, duration=0.4, channels=6,
                         direction_offset=250, noise=0.02, seed=42):
    """Far-field delayed voiced-plus-broadband source, generated in memory.

    Known arrival angle uses the existing microphone calibration convention.
    Fractional delays model plane-wave opposite-pair arrival times. These ideal
    fixtures test software geometry, not real reverberation or microphone wiring.
    """
    if channels not in (4, 6):
        raise ValueError('Only 4 or 6 channels are supported')
    count = int(rate*duration)
    rng = np.random.default_rng(seed)
    t = np.arange(count)/rate
    voiced = sum(np.sin(2*np.pi*125*k*t)/k for k in range(1, 20))
    source = voiced + rng.normal(0, 0.5, count)
    # Zero edges avoid circular-wrap discontinuities dominating correlation.
    source *= np.minimum(np.minimum(t/0.02, (duration-t)/0.02), 1.0)
    raw_angle = np.radians((angle + 120 - direction_offset) % 360)
    pair_delays = MAX_TDOA_4 * np.array([np.sin(raw_angle), np.cos(raw_angle)])
    delays = [pair_delays[0]/2, pair_delays[1]/2,
              -pair_delays[0]/2, -pair_delays[1]/2]
    frequencies = np.fft.rfftfreq(count, 1/rate)
    spectrum = np.fft.rfft(source)
    raw = np.stack([np.fft.irfft(spectrum*np.exp(-2j*np.pi*frequencies*delay), n=count)
                    + rng.normal(0, noise, count) for delay in delays], axis=1)
    raw = np.clip(raw*4000, -32767, 32767).astype(np.int16)
    if channels == 4:
        return raw.reshape(-1)
    result = np.zeros((count, 6), dtype=np.int16)
    result[:, 1:5] = raw
    result[:, 0] = raw[:, 0]  # processed/VAD channel fixture
    return result.reshape(-1)


class DirectionActivity:
    """Track emitted direction activity with a deterministic quiet timeout."""
    def __init__(self, timeout=1.5):
        self.timeout = timeout
        self.last_active = None
        self.active = False

    def heard(self, now):
        self.last_active, self.active = now, True

    def expire(self, now):
        if self.active and now - self.last_active > self.timeout:
            self.active = False
            return True
        return False
