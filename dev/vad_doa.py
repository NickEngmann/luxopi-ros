#!/usr/bin/env python3
"""
Voice Activity Detection with Direction of Arrival estimation
Improved version with amplitude-based filtering for more stable DOA
"""

import sys
import webrtcvad
import numpy as np
import time
from mic_array import MicArray
from pixel_ring import pixel_ring

# Configuration parameters
config = {
    'audio': {'rate': 16000, 'channels': 6, 'vad_frames': 20, 'doa_frames': 400},
    'vad': {'aggressiveness': 3, 'speech_ratio': 0.5, 'timeout': 1.5},
    'amplitude': {'min_amplitude': 300, 'peak_ratio': 0.2, 'peak_decay_rate': 0.995},
    'stability': {'history_size': 5, 'max_angular_std': 60, 'smoothing_factor': 0.7},
    'led': {'brightness': 50},
    'debug': {'print_amplitude': True, 'print_confidence': True, 'disable_stability_filter': True, 'print_raw_direction': True},
    'array': {'direction_offset': 250},
}

# Extract configuration values
RATE = config['audio']['rate']
CHANNELS = config['audio']['channels']
VAD_FRAMES = config['audio']['vad_frames']
DOA_FRAMES = config['audio']['doa_frames']

MIN_AMPLITUDE_THRESHOLD = config['amplitude']['min_amplitude']
PEAK_AMPLITUDE_RATIO = config['amplitude']['peak_ratio']


def calculate_rms(audio_chunk):
    """Calculate Root Mean Square (RMS) amplitude of audio chunk"""
    return np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))


def main():
    vad = webrtcvad.Vad(config['vad']['aggressiveness'])

    speech_count = 0
    chunks = []
    doa_chunks = int(DOA_FRAMES / VAD_FRAMES)
    last_speech_time = time.time()
    last_direction = None
    leds_on = False
    
    # Track recent peak amplitude for adaptive thresholding
    recent_peak_amplitude = MIN_AMPLITUDE_THRESHOLD
    amplitude_decay_rate = config['amplitude']['peak_decay_rate']
    
    # Track direction stability
    direction_history = []
    history_size = config['stability']['history_size']
    max_angular_std = config['stability']['max_angular_std']
    
    # Set LED brightness
    if pixel_ring:
        pixel_ring.set_brightness(config['led']['brightness'])

    try:
        with MicArray(RATE, CHANNELS, RATE * VAD_FRAMES / 1000, direction_offset=config['array']['direction_offset']) as mic:
            for chunk in mic.read_chunks():
                current_time = time.time()
                
                # Calculate chunk amplitude
                chunk_amplitude = calculate_rms(chunk)
                
                # Update peak amplitude tracker
                if chunk_amplitude > recent_peak_amplitude:
                    recent_peak_amplitude = chunk_amplitude
                else:
                    recent_peak_amplitude *= amplitude_decay_rate
                
                # Use single channel audio to detect voice activity
                if vad.is_speech(chunk[0::CHANNELS].tobytes(), RATE):
                    speech_count += 1
                    last_speech_time = current_time
                    sys.stdout.write('1')
                else:
                    sys.stdout.write('0')

                sys.stdout.flush()

                # Turn off LEDs if no speech for configured timeout
                if current_time - last_speech_time > config['vad']['timeout'] and leds_on:
                    pixel_ring.off()
                    leds_on = False
                    direction_history.clear()  # Clear history when speech stops

                chunks.append(chunk)
                if len(chunks) == doa_chunks:
                    # Calculate average amplitude over the DOA window
                    frames = np.concatenate(chunks)
                    avg_amplitude = calculate_rms(frames)
                    
                    # Only process DOA if we have enough speech and sufficient amplitude
                    if speech_count > (doa_chunks * config['vad']['speech_ratio']):
                        # Check if amplitude is sufficient for reliable DOA
                        amplitude_ratio = avg_amplitude / max(recent_peak_amplitude, MIN_AMPLITUDE_THRESHOLD)
                        
                        if avg_amplitude > MIN_AMPLITUDE_THRESHOLD and amplitude_ratio > PEAK_AMPLITUDE_RATIO:
                            direction = mic.get_direction(frames)
                            
                            # Print raw direction if debugging enabled
                            if config['debug'].get('print_raw_direction', False) and direction is not None:
                                print(f'\n[Raw: {int(direction)}°]', end='')
                            
                            # Add to direction history
                            if direction is not None:
                                # Skip stability filtering if disabled for debugging
                                if config['debug'].get('disable_stability_filter', False):
                                    pixel_ring.set_direction(int(direction))
                                    leds_on = True
                                    last_direction = int(direction)
                                    if config['debug']['print_amplitude']:
                                        print(f'\n{int(direction)}° (amplitude: {int(avg_amplitude)}, ratio: {amplitude_ratio:.2f}) [NO FILTER]')
                                    else:
                                        print(f'\n{int(direction)}° [NO FILTER]')
                                else:
                                    # Apply stability filtering as before
                                    direction_history.append(direction)
                                    if len(direction_history) > history_size:
                                        direction_history.pop(0)
                                
                                # Only update display if we have enough consistent readings
                                if len(direction_history) >= 2:
                                    # Check for consistency (handle wraparound at 0/360)
                                    angles = np.array(direction_history)
                                    # Convert to unit vectors to handle wraparound
                                    x_coords = np.cos(np.radians(angles))
                                    y_coords = np.sin(np.radians(angles))
                                    # Calculate average direction
                                    avg_x = np.mean(x_coords)
                                    avg_y = np.mean(y_coords)
                                    avg_direction = np.degrees(np.arctan2(avg_y, avg_x))
                                    if avg_direction < 0:
                                        avg_direction += 360
                                    
                                    # Calculate angular standard deviation
                                    angular_std = np.degrees(np.sqrt(-np.log(avg_x**2 + avg_y**2)))
                                    
                                    # Only update if directions are reasonably consistent
                                    if angular_std < max_angular_std:  # Within configured standard deviation
                                        pixel_ring.set_direction(int(avg_direction))
                                        leds_on = True
                                        last_direction = int(avg_direction)
                                        if config['debug']['print_amplitude']:
                                            print(f'\n{int(avg_direction)}° (amplitude: {int(avg_amplitude)}, ratio: {amplitude_ratio:.2f})')
                                        else:
                                            print(f'\n{int(avg_direction)}°')
                                    else:
                                        print(f'\n[Unstable: std={angular_std:.1f}°]', end='')
                                else:
                                    # First reading, just store it
                                    print(f'\n[Acquiring direction...]', end='')
                        else:
                            # Signal too weak for reliable DOA
                            print(f'\n[Weak signal: amplitude={int(avg_amplitude)}, ratio={amplitude_ratio:.2f}]', end='')
                    
                    speech_count = 0
                    chunks = []

    except KeyboardInterrupt:
        print("\nShutting down...")
        
    if pixel_ring:
        pixel_ring.off()


if __name__ == '__main__':
    main()