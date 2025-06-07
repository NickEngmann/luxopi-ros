#!/usr/bin/env python3
"""
Voice Direction Detection using ReSpeaker Mic Array v2.0
This script detects the direction of voice audio using DOA (Direction of Arrival)
calculated from audio data and VAD (Voice Activity Detection) using webrtcvad.
"""

import sys
import time
import numpy as np
import webrtcvad
from collections import deque
from mic_array import MicArray
from pixel_ring import pixel_ring
from scipy import signal
from scipy.fft import fft

class VoiceDirectionDetector:
    """Main class for detecting voice direction"""
    
    def __init__(self, rate=16000, channels=4, vad_frames=20, doa_frames=200, 
                 vad_aggressiveness=3, confidence_threshold=0.5):
        """
        Initialize the voice direction detector
        
        Args:
            rate: Sample rate (Hz)
            channels: Number of audio channels
            vad_frames: VAD frame duration in ms
            doa_frames: DOA calculation window in ms
            vad_aggressiveness: WebRTC VAD aggressiveness (0-3)
            confidence_threshold: Minimum ratio of voice detections to report direction
        """
        self.rate = rate
        self.channels = channels
        self.vad_frames = vad_frames
        self.doa_frames = doa_frames
        self.confidence_threshold = confidence_threshold
        
        # Initialize VAD
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        
        # Calculate chunk size
        self.chunk_size = int(rate * vad_frames / 1000)
        self.doa_chunks = int(doa_frames / vad_frames)
        
        # Voice-specific frequency analysis parameters
        self.speech_low_freq = 300   # Hz - Lower bound of speech
        self.speech_high_freq = 3400 # Hz - Upper bound of speech
        self.voice_energy_threshold = 0.4  # Minimum energy in speech band
        self.spectral_centroid_range = (500, 2000)  # Expected range for voice
        
        # History for smoothing
        self.direction_history = deque(maxlen=5)
        self.voice_history = deque(maxlen=10)
        self.spectral_history = deque(maxlen=5)
        
        # Precompute frequency bins for efficiency
        self.freq_bins = np.fft.fftfreq(self.chunk_size, 1/self.rate)
        self.speech_mask = (self.freq_bins >= self.speech_low_freq) & (self.freq_bins <= self.speech_high_freq)
        
        print("[OK] Voice Direction Detector initialized")
        print(f"    Sample rate: {rate} Hz")
        print(f"    Channels: {channels}")
        print(f"    VAD frame: {vad_frames} ms")
        print(f"    DOA window: {doa_frames} ms")
        print(f"    Speech band: {self.speech_low_freq}-{self.speech_high_freq} Hz")
        
    def analyze_speech_characteristics(self, audio_data):
        """
        Analyze audio for speech-specific characteristics
        
        Returns:
            dict: Analysis results with voice probability
        """
        # Convert to float for analysis
        audio_float = audio_data.astype(np.float32) / 32768.0
        
        # Remove DC component
        audio_float = audio_float - np.mean(audio_float)
        
        # Apply window to reduce spectral leakage
        windowed = audio_float * np.hanning(len(audio_float))
        
        # Compute FFT
        fft_data = np.abs(fft(windowed))
        fft_data = fft_data[:len(fft_data)//2]  # Keep only positive frequencies
        
        # Calculate total energy
        total_energy = np.sum(fft_data**2)
        if total_energy < 1e-10:  # Silence
            return {'is_voice': False, 'confidence': 0.0, 'reason': 'silence'}
        
        # Energy in speech frequency band
        speech_energy = np.sum(fft_data[self.speech_mask[:len(fft_data)]]**2)
        speech_ratio = speech_energy / total_energy if total_energy > 0 else 0
        
        # Spectral centroid (brightness measure)
        freqs = self.freq_bins[:len(fft_data)]
        spectral_centroid = np.sum(freqs * fft_data**2) / np.sum(fft_data**2) if np.sum(fft_data**2) > 0 else 0
        
        # Spectral rolloff (frequency below which 85% of energy is contained)
        cumulative_energy = np.cumsum(fft_data**2)
        rolloff_threshold = 0.85 * total_energy
        rolloff_idx = np.where(cumulative_energy >= rolloff_threshold)[0]
        spectral_rolloff = freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else self.rate/2
        
        # Zero crossing rate (indicates voiced vs unvoiced)
        zero_crossings = np.sum(np.diff(np.sign(audio_float)) != 0)
        zcr = zero_crossings / len(audio_float)
        
        # Voice classification criteria
        criteria = {
            'speech_energy': speech_ratio >= self.voice_energy_threshold,
            'spectral_centroid': self.spectral_centroid_range[0] <= spectral_centroid <= self.spectral_centroid_range[1],
            'spectral_rolloff': spectral_rolloff <= 4000,  # Voice typically rolls off before 4kHz
            'zero_crossing': 0.01 <= zcr <= 0.3,  # Voice has moderate ZCR
            'energy_level': total_energy > 1e-6,  # Minimum energy threshold
        }
        
        # Calculate voice confidence
        passed_criteria = sum(criteria.values())
        voice_confidence = passed_criteria / len(criteria)
        
        # Additional noise rejection
        # High frequency noise detection
        high_freq_mask = freqs > 4000
        if len(high_freq_mask) > 0:
            high_freq_energy = np.sum(fft_data[high_freq_mask]**2)
            high_freq_ratio = high_freq_energy / total_energy if total_energy > 0 else 0
            
            # If too much high frequency content, likely noise
            if high_freq_ratio > 0.3:
                voice_confidence *= 0.5
        
        # Sudden energy spikes (like paper crumpling) have different characteristics
        if spectral_rolloff > 6000 and zcr > 0.5:
            voice_confidence *= 0.2  # Likely broadband noise
        
        is_voice = voice_confidence >= 0.6  # Require 60% confidence
        
        return {
            'is_voice': is_voice,
            'confidence': voice_confidence,
            'speech_ratio': speech_ratio,
            'spectral_centroid': spectral_centroid,
            'spectral_rolloff': spectral_rolloff,
            'zcr': zcr,
            'criteria': criteria
        }
    
    def is_speech_detected(self, mono_audio, chunk_data):
        """
        Enhanced speech detection combining VAD and spectral analysis
        
        Args:
            mono_audio: Raw audio bytes for VAD
            chunk_data: Numpy array for spectral analysis
            
        Returns:
            bool: True if speech is detected
        """
        # Basic VAD check
        vad_result = self.vad.is_speech(mono_audio, self.rate)
        
        # If VAD says no speech, trust it (high precision, lower recall)
        if not vad_result:
            return False
        
        # If VAD detects something, verify it's actually voice
        if self.channels == 6:
            audio_for_analysis = chunk_data[1::self.channels]  # Channel 1
        else:
            audio_for_analysis = chunk_data[0::self.channels]  # Channel 0
        
        # Perform spectral analysis
        speech_analysis = self.analyze_speech_characteristics(audio_for_analysis)
        self.spectral_history.append(speech_analysis['confidence'])
        
        # Use both VAD and spectral analysis
        spectral_confidence = np.mean(list(self.spectral_history)) if self.spectral_history else 0
        
        # Require both VAD detection AND good spectral characteristics
        return speech_analysis['is_voice'] and spectral_confidence > 0.5

    def get_smoothed_direction(self, direction):
        """Apply circular mean to smooth direction readings"""
        self.direction_history.append(direction)
        
        if len(self.direction_history) > 0:
            # Use circular mean for angle averaging
            angles_rad = np.array([d * np.pi / 180 for d in self.direction_history])
            mean_sin = np.mean(np.sin(angles_rad))
            mean_cos = np.mean(np.cos(angles_rad))
            mean_direction = np.arctan2(mean_sin, mean_cos) * 180 / np.pi
            
            # Convert back to 0-359 range
            if mean_direction < 0:
                mean_direction += 360
                
            return int(mean_direction)
        
        return direction
    
    def get_voice_confidence(self):
        """Calculate confidence based on recent voice detections"""
        if len(self.voice_history) > 0:
            return sum(self.voice_history) / len(self.voice_history)
        return 0
    
    def run(self, callback=None, debug=False):
        """
        Run continuous voice direction detection
        
        Args:
            callback: Optional function to call with (direction, confidence) when voice detected
            debug: Show debug information
        """
        print("\n[MIC] Voice Direction Detection Started")
        print("=" * 50)
        print("Listening for voice... (Press Ctrl+C to stop)")
        print("=" * 50)
        
        speech_count = 0
        chunks = []
        last_direction = None
        last_report_time = time.time()
        report_interval = 0.5  # Minimum time between reports
        
        try:
            # Initialize pixel ring
            pixel_ring.off()
            
            with MicArray(self.rate, self.channels, self.chunk_size) as mic:
                for chunk in mic.read_chunks():
                    if self.channels == 6:
                        # Use raw microphone data (channel 1) instead of processed (channel 0)
                        mono_audio = chunk[1::self.channels].tobytes()
                    else:
                        # Use channel 0 for other configurations
                        mono_audio = chunk[0::self.channels].tobytes()
                    
                    # Enhanced speech detection
                    is_speech = self.is_speech_detected(mono_audio, chunk)
                    self.voice_history.append(is_speech)
                    
                    if is_speech:
                        speech_count += 1
                        if debug:
                            sys.stdout.write('V')  # V for Voice
                    else:
                        if debug:
                            sys.stdout.write('.')  # . for no voice
                    
                    if debug:
                        sys.stdout.flush()
                    
                    # Collect chunks for DOA calculation
                    chunks.append(chunk)
                    
                    if len(chunks) == self.doa_chunks:
                        confidence = self.get_voice_confidence()
                        current_time = time.time()
                        
                        # Require higher threshold for direction detection
                        if speech_count > (self.doa_chunks * 0.6):  # 60% of chunks must be voice
                            # Calculate DOA from accumulated audio
                            frames = np.concatenate(chunks)
                            direction = mic.get_direction(frames)
                            
                            if direction is not None:
                                # Smooth the direction
                                smoothed_direction = self.get_smoothed_direction(direction)
                                
                                # Update pixel ring
                                pixel_ring.set_direction(smoothed_direction)
                                
                                # Report if significant change or timeout
                                direction_changed = (
                                    last_direction is None or 
                                    abs(smoothed_direction - last_direction) > 10 or
                                    (current_time - last_report_time) > report_interval
                                )
                                
                                if direction_changed:
                                    compass = self.get_compass_visual(smoothed_direction)
                                    spectral_conf = np.mean(list(self.spectral_history)) if self.spectral_history else 0
                                    
                                    if not debug:
                                        print(f"\r[VOICE] Detected at {smoothed_direction:3d}° {compass} "
                                              f"(VAD: {confidence:.0%}, Spectral: {spectral_conf:.0%})    ", 
                                              end='', flush=True)
                                    else:
                                        print(f"\n[VOICE] Direction: {smoothed_direction:3d}° {compass} "
                                              f"(VAD: {confidence:.0%}, Spectral: {spectral_conf:.0%})")
                                    
                                    if callback:
                                        callback(smoothed_direction, confidence)
                                    
                                    last_direction = smoothed_direction
                                    last_report_time = current_time
                        else:
                            # No voice detected
                            if not debug:
                                spectral_conf = np.mean(list(self.spectral_history)) if self.spectral_history else 0
                                print(f"\r[IDLE] No voice detected (VAD: {confidence:.0%}, Spectral: {spectral_conf:.0%})    ", 
                                      end='', flush=True)
                            
                            # Turn off pixel ring when no voice
                            if confidence < 0.2:
                                pixel_ring.off()
                            
                            last_direction = None
                        
                        # Reset for next window
                        speech_count = 0
                        chunks = []
                        
        except KeyboardInterrupt:
            print("\n\n[STOP] Stopped by user")
        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            pixel_ring.off()
            print("[EXIT] Goodbye!")
    
    @staticmethod
    def get_compass_visual(angle):
        """Get a visual compass representation of the angle"""
        # Define compass directions (East and West flipped for device orientation)
        directions = [
            (0, "N"), (45, "NW"), (90, "W"), (135, "SW"),
            (180, "S"), (225, "SE"), (270, "E"), (315, "NE")
        ]
        
        # Find closest direction
        min_diff = float('inf')
        closest_dir = "N"
        
        for dir_angle, dir_symbol in directions:
            diff = abs(angle - dir_angle)
            if diff > 180:
                diff = 360 - diff
            if diff < min_diff:
                min_diff = diff
                closest_dir = dir_symbol
        
        # Create arrow visual (flipped for East/West)
        arrow = "→"
        if 337.5 <= angle or angle < 22.5:
            arrow = "↑"
        elif 22.5 <= angle < 67.5:
            arrow = "↖"  # Was ↗, now points NW
        elif 67.5 <= angle < 112.5:
            arrow = "←"  # Was →, now points W
        elif 112.5 <= angle < 157.5:
            arrow = "↙"  # Was ↘, now points SW
        elif 157.5 <= angle < 202.5:
            arrow = "↓"
        elif 202.5 <= angle < 247.5:
            arrow = "↘"  # Was ↙, now points SE
        elif 247.5 <= angle < 292.5:
            arrow = "→"  # Was ←, now points E
        elif 292.5 <= angle < 337.5:
            arrow = "↗"  # Was ↖, now points NE
        
        return f"{arrow} {closest_dir}"


def example_callback(direction, confidence):
    """Example callback function for voice direction events"""
    timestamp = time.strftime("%H:%M:%S")
    # This will print on a new line when called
    print(f"\n[{timestamp}] Voice Event - Direction: {direction}° (confidence: {confidence:.0%})")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Voice Direction Detection using ReSpeaker Mic Array v2.0'
    )
    parser.add_argument('--rate', type=int, default=16000,
                        help='Sample rate in Hz (default: 16000)')
    parser.add_argument('--channels', type=int, default=4,
                        help='Number of channels (default: 4)')
    parser.add_argument('--vad-frames', type=int, default=20,
                        help='VAD frame duration in ms (default: 20)')
    parser.add_argument('--doa-frames', type=int, default=200,
                        help='DOA window duration in ms (default: 200)')
    parser.add_argument('--vad-level', type=int, default=3, choices=[0, 1, 2, 3],
                        help='VAD aggressiveness level 0-3 (default: 3)')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Voice detection confidence threshold (default: 0.5)')
    parser.add_argument('--callback', action='store_true',
                        help='Enable callback example')
    parser.add_argument('--debug', action='store_true',
                        help='Show debug information')
    
    args = parser.parse_args()
    
    try:  
        # Create detector
        detector = VoiceDirectionDetector(
            rate=args.rate,
            channels=args.channels,
            vad_frames=args.vad_frames,
            doa_frames=args.doa_frames,
            vad_aggressiveness=args.vad_level,
            confidence_threshold=args.threshold
        )
        
        # Run detection
        if args.callback:
            detector.run(callback=example_callback, debug=args.debug)
        else:
            detector.run(debug=args.debug)
            
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()