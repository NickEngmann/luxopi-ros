#!/usr/bin/env python3
import sys
import webrtcvad
import numpy as np
from mic_array import MicArray
from pixel_ring import pixel_ring
from scipy.signal import butter, lfilter
import noisereduce as nr

# ── Configuration ──────────────────────────────────────────────────────────────
RATE                = 16000      # sampling rate in Hz
CHANNELS            = 4          # number of mics in your array
VAD_MODE            = 3          # 0–3 aggressiveness (3 = most aggressive)
VAD_FRAMES          = 20         # ms per VAD frame (10, 20 or 30)
DOA_FRAMES          = 200        # ms over which to compute DOA
DOA_THRESHOLD       = 0.75       # require 75% of frames to count as “speech”
NOISE_CALIB_SECONDS = 1.0        # seconds of background noise to record at startup
ENERGY_FACTOR       = 1.5        # multiplier on noise RMS for energy threshold

def main():
    # 1) VAD init
    vad = webrtcvad.Vad(VAD_MODE)

    # 2) design 300–3400 Hz band-pass
    nyq = RATE / 2
    b, a = butter(4, [300/nyq, 3400/nyq], btype='band')

    # 3) compute sizes
    chunk_size = int(RATE * VAD_FRAMES / 1000)        # samples per read
    doa_chunks = int(DOA_FRAMES / VAD_FRAMES)         # frames per DOA window

    try:
        with MicArray(RATE, CHANNELS, chunk_size) as mic:
            # ── noise calibration ───────────────────────────────────────
            print(f"Calibrating noise for {NOISE_CALIB_SECONDS:.1f}s…", file=sys.stderr)
            chunks_iter   = mic.read_chunks()
            noise_frames  = int(NOISE_CALIB_SECONDS * 1000 / VAD_FRAMES)
            noise_samples = []
            for _ in range(noise_frames):
                chunk     = next(chunks_iter)
                mono      = chunk[0::CHANNELS]
                mono_filt = lfilter(b, a, mono)
                noise_samples.append(mono_filt)

            noise_profile = np.concatenate(noise_samples)
            noise_rms     = np.sqrt(np.mean(noise_profile**2))
            noise_floor   = noise_rms * ENERGY_FACTOR
            print(f"Noise RMS={noise_rms:.1f}, floor={noise_floor:.1f}", file=sys.stderr)

            # ── main loop ────────────────────────────────────────────────
            speech_count = 0
            window       = []

            for chunk in chunks_iter:
                # 1) extract & band-pass one mic channel
                mono      = chunk[0::CHANNELS]
                mono_filt = lfilter(b, a, mono)

                # 2) denoise (no verbose arg)
                mono_dn = nr.reduce_noise(
                    y=mono_filt,
                    sr=RATE,
                    y_noise=noise_profile,
                    stationary=True,
                    prop_decrease=1.0
                )

                # 3) energy threshold
                rms       = np.sqrt(np.mean(mono_dn**2))
                is_speech = False
                if rms >= noise_floor:
                    clipped   = np.clip(mono_dn, -32768, 32767).astype(np.int16)
                    is_speech = vad.is_speech(clipped.tobytes(), RATE)

                # 4) print VAD bit
                sys.stdout.write('1' if is_speech else '0')
                sys.stdout.flush()

                # 5) accumulate for DOA
                if is_speech:
                    speech_count += 1
                window.append(chunk)

                if len(window) == doa_chunks:
                    if speech_count > (doa_chunks * DOA_THRESHOLD):
                        frames    = np.concatenate(window)
                        direction = mic.get_direction(frames)
                        pixel_ring.set_direction(direction)
                        print(f"\n{int(direction)}")
                    speech_count = 0
                    window       = []

    except KeyboardInterrupt:
        pass
    finally:
        pixel_ring.off()

if __name__ == '__main__':
    main()
