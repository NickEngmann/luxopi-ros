#!/usr/bin/env python3
"""
Audio Bridge: MicArray → DOA/LEDs + ALSA Loopback
This script captures from ReSpeaker MicArray, calculates DOA + controls LEDs,
and forwards stereo audio (Ch1+4) to ALSA loopback for Hailo Whisper to consume.
"""

import sys
import numpy as np
import time
import signal
import argparse
import subprocess
import pyaudio
from mic_array import MicArray
from pixel_ring import pixel_ring

# Audio configuration
RATE = 16000
CHANNELS = 6  # ReSpeaker has 6 channels
VAD_FRAMES = 30  # ms per chunk for VAD
CHUNK_DURATION_MS = VAD_FRAMES  # Process in 30ms chunks
CHUNK_SIZE = int(RATE * CHUNK_DURATION_MS / 1000)

# DOA configuration
DOA_FRAMES = 600  # ms for DOA calculation
DOA_CHUNKS = int(DOA_FRAMES / VAD_FRAMES)
DIRECTION_OFFSET = 250  # Calibration offset for your setup

# LED configuration
LED_BRIGHTNESS = 50
LED_TIMEOUT = 2.0  # Seconds of silence before turning off LEDs

# Amplitude thresholds for DOA
MIN_AMPLITUDE_THRESHOLD = 300
PEAK_AMPLITUDE_RATIO = 0.2


def calculate_rms(audio_chunk):
    """Calculate Root Mean Square (RMS) amplitude of audio chunk"""
    return np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))


def find_loopback_device():
    """Find the ALSA loopback device card number"""
    try:
        result = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            timeout=2
        )

        for line in result.stdout.split('\n'):
            if 'Loopback' in line and line.startswith('card'):
                # Extract card number
                card_num = line.split(':')[0].split()[1]
                return int(card_num)

        print("❌ Could not find loopback device")
        print("   Run: ./setup_loopback.sh first")
        return None

    except Exception as e:
        print(f"❌ Error finding loopback device: {e}")
        return None


def extract_stereo_channels(audio_chunk_6ch):
    """
    Extract channels 1 and 4 from 6-channel audio and create stereo output.

    Args:
        audio_chunk_6ch: Interleaved 6-channel int16 audio data

    Returns:
        Stereo float32 audio data (2 channels interleaved)
    """
    # Convert to numpy array if bytes
    if isinstance(audio_chunk_6ch, bytes):
        audio_array = np.frombuffer(audio_chunk_6ch, dtype=np.int16)
    else:
        audio_array = audio_chunk_6ch

    # Reshape to (samples, 6)
    samples = len(audio_array) // 6
    audio_6ch = audio_array.reshape(samples, 6)

    # Extract channels 1 and 4 (0-indexed: 0 and 3)
    stereo = np.zeros((samples, 2), dtype=np.float32)
    stereo[:, 0] = audio_6ch[:, 0].astype(np.float32) / 32768.0  # Channel 1 → Left
    stereo[:, 1] = audio_6ch[:, 3].astype(np.float32) / 32768.0  # Channel 4 → Right

    return stereo


class AudioBridge:
    """Bridge between MicArray and ALSA Loopback with DOA processing"""

    def __init__(self, loopback_card, verbose=False, led_timeout=LED_TIMEOUT):
        self.loopback_card = loopback_card
        self.verbose = verbose
        self.running = True
        self.led_timeout = led_timeout

        # DOA state
        self.doa_chunks = []
        self.recent_peak_amplitude = MIN_AMPLITUDE_THRESHOLD
        self.amplitude_decay_rate = 0.995
        self.leds_on = False
        self.last_direction = None
        self.last_doa_time = None  # Track when we last detected valid DOA

        # Statistics
        self.frames_processed = 0
        self.doa_calculations = 0
        self.start_time = time.time()

        # Initialize PyAudio for loopback output
        self.pa = pyaudio.PyAudio()

        # Find loopback device index
        loopback_device_index = None
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if 'Loopback' in info['name'] and info['maxOutputChannels'] >= 2:
                loopback_device_index = i
                if self.verbose:
                    print(f"  📍 Found loopback device: {info['name']} (index {i})")
                break

        if loopback_device_index is None:
            raise RuntimeError("Could not find loopback device output")

        # Open loopback output stream (playback side - hw:X,0,0)
        self.loopback_stream = self.pa.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=RATE,
            output=True,
            output_device_index=loopback_device_index,
            frames_per_buffer=CHUNK_SIZE
        )

        # Set LED brightness
        if pixel_ring:
            pixel_ring.set_brightness(LED_BRIGHTNESS)

    def process_doa(self, mic, chunks):
        """Calculate DOA and update LEDs"""
        frames = np.concatenate(chunks)
        avg_amplitude = calculate_rms(frames)

        # Update peak amplitude tracker
        if avg_amplitude > self.recent_peak_amplitude:
            self.recent_peak_amplitude = avg_amplitude
        else:
            self.recent_peak_amplitude *= self.amplitude_decay_rate

        # Check if amplitude is sufficient for reliable DOA
        amplitude_ratio = avg_amplitude / max(self.recent_peak_amplitude, MIN_AMPLITUDE_THRESHOLD)

        if avg_amplitude > MIN_AMPLITUDE_THRESHOLD and amplitude_ratio > PEAK_AMPLITUDE_RATIO:
            direction = mic.get_direction(frames)

            if direction is not None:
                pixel_ring.set_direction(int(direction))
                self.leds_on = True
                self.last_direction = int(direction)
                self.last_doa_time = time.time()  # Update last detection time
                self.doa_calculations += 1

                if self.verbose:
                    print(f"  🎯 Direction: {int(direction)}° (amplitude: {int(avg_amplitude)})")
        else:
            if self.verbose:
                print(f"  🔇 Signal too weak: amplitude={int(avg_amplitude)}, ratio={amplitude_ratio:.2f}")

    def check_led_timeout(self):
        """Turn off LEDs if no DOA detected for LED_TIMEOUT seconds"""
        if self.leds_on and self.last_doa_time is not None:
            time_since_last_doa = time.time() - self.last_doa_time
            if time_since_last_doa >= self.led_timeout:
                if self.verbose:
                    print(f"  💤 LED timeout ({self.led_timeout}s) - turning off LEDs")
                pixel_ring.off()
                self.leds_on = False

    def run(self):
        """Main processing loop"""
        print("\n" + "="*60)
        print("  🌉 AUDIO BRIDGE: MicArray → DOA + Loopback")
        print("="*60)
        print(f"  Loopback card: {self.loopback_card}")
        print(f"  Sample rate: {RATE} Hz")
        print(f"  Chunk size: {CHUNK_SIZE} samples ({CHUNK_DURATION_MS}ms)")
        print(f"  DOA calculation: every {DOA_FRAMES}ms")
        print("="*60 + "\n")
        print("🎤 Starting audio capture from MicArray...")
        print("📡 Forwarding stereo (Ch1+4) to loopback...")
        print("🎯 Processing DOA and controlling LEDs...\n")
        print("(Press Ctrl+C to stop)\n")

        try:
            with MicArray(RATE, CHANNELS, RATE * VAD_FRAMES / 1000, direction_offset=DIRECTION_OFFSET) as mic:
                print("✅ MicArray initialized!\n")

                for chunk in mic.read_chunks():
                    if not self.running:
                        break

                    self.frames_processed += 1

                    # Extract stereo for loopback
                    stereo_audio = extract_stereo_channels(chunk)

                    # Write to loopback (this feeds Hailo Whisper)
                    self.loopback_stream.write(stereo_audio.tobytes())

                    # Accumulate for DOA calculation
                    self.doa_chunks.append(chunk)

                    if len(self.doa_chunks) >= DOA_CHUNKS:
                        # Calculate DOA and update LEDs
                        self.process_doa(mic, self.doa_chunks)
                        self.doa_chunks = []

                    # Check LED timeout (turn off if no recent DOA)
                    self.check_led_timeout()

                    # Periodic status (every 5 seconds)
                    if self.verbose and self.frames_processed % (5000 // CHUNK_DURATION_MS) == 0:
                        runtime = time.time() - self.start_time
                        print(f"  📊 Runtime: {runtime:.1f}s | Frames: {self.frames_processed} | DOA calcs: {self.doa_calculations}")

        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down...")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()

    def stop(self):
        """Clean shutdown"""
        self.running = False

        # Stop loopback stream
        if self.loopback_stream:
            self.loopback_stream.stop_stream()
            self.loopback_stream.close()

        if self.pa:
            self.pa.terminate()

        # Turn off LEDs
        if pixel_ring:
            pixel_ring.off()

        # Statistics
        runtime = time.time() - self.start_time
        print("\n" + "="*60)
        print("  📊 SESSION STATISTICS")
        print("="*60)
        print(f"  Runtime: {runtime:.1f} seconds")
        print(f"  Frames processed: {self.frames_processed}")
        print(f"  DOA calculations: {self.doa_calculations}")
        if self.last_direction is not None:
            print(f"  Last direction: {self.last_direction}°")
        print("="*60 + "\n")
        print("✨ Bridge stopped cleanly\n")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    if 'bridge' in globals():
        bridge.stop()
    sys.exit(0)


def main():
    global bridge

    parser = argparse.ArgumentParser(
        description='🌉 Audio Bridge: MicArray → DOA/LEDs + ALSA Loopback',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--led-timeout',
        type=float,
        default=LED_TIMEOUT,
        help=f'LED timeout in seconds (default: {LED_TIMEOUT}s) - turn off LEDs after this period of silence'
    )

    args = parser.parse_args()

    # Find loopback device
    loopback_card = find_loopback_device()
    if loopback_card is None:
        sys.exit(1)

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Create and run bridge
    bridge = AudioBridge(loopback_card, verbose=args.verbose, led_timeout=args.led_timeout)
    bridge.run()


if __name__ == "__main__":
    main()
