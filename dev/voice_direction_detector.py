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
                 vad_aggressiveness=3, confidence_threshold=0.5, calibration_time=3.0):
        """
        Initialize the voice direction detector
        
        Args:
            rate: Sample rate (Hz)
            channels: Number of audio channels
            vad_frames: VAD frame duration in ms
            doa_frames: DOA calculation window in ms
            vad_aggressiveness: WebRTC VAD aggressiveness (0-3)
            confidence_threshold: Minimum ratio of voice detections to report direction
            calibration_time: Background noise calibration time in seconds
        """
        self.rate = rate
        self.channels = channels
        self.vad_frames = vad_frames
        self.doa_frames = doa_frames
        self.confidence_threshold = confidence_threshold
        self.calibration_time = calibration_time
        
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
        self.voice_history = deque(maxlen=15)  # Increased from 10 to 15 for more stability
        self.spectral_history = deque(maxlen=8)  # Increased from 5 to 8
        
        # Precompute frequency bins for efficiency
        self.freq_bins = np.fft.fftfreq(self.chunk_size, 1/self.rate)
        self.speech_mask = (self.freq_bins >= self.speech_low_freq) & (self.freq_bins <= self.speech_high_freq)
        
        # Background noise calibration (made less aggressive)
        self.background_noise_energy = None
        self.background_noise_spectrum = None
        self.is_calibrated = False
        self.calibration_samples = []
        self.adaptive_background_history = deque(maxlen=50)
        self.noise_floor_multiplier = 1.5  # Reduced from 1.5 to 1.3
        self.snr_threshold = 2.0  # Reduced from 2.0 to 1.5
        
        # Dynamic thresholds (will be updated after calibration)
        self.dynamic_energy_threshold = self.voice_energy_threshold
        self.adaptive_update_rate = 0.05  # Slower adaptation (was 0.05)
        
        # LED persistence to prevent blinking
        self.led_persistence_time = 1.5  # Keep LEDs on for 1.5 seconds after voice stops
        self.last_voice_time = 0
        self.last_led_update_time = 0
        self.led_update_interval = 0.1  # Update LEDs at most every 100ms
        self.current_led_direction = None
        
        # Enhanced adaptive noise floor with recovery
        self.calibration_quality_threshold = 0.6  # Max allowed voice ratio during calibration
        self.contaminated_calibration = False
        self.recalibration_trigger_count = 0
        self.recalibration_threshold = 50  # Trigger recalibration after N suspicious samples
        self.min_quiet_samples_for_recalibration = 100  # Need N quiet samples to recalibrate
        self.quiet_samples_buffer = deque(maxlen=self.min_quiet_samples_for_recalibration)
        
        # Multiple noise floor estimates for robustness
        self.primary_noise_floor = None
        self.secondary_noise_floor = None
        self.tertiary_noise_floor = None
        self.noise_floor_history = deque(maxlen=200)  # Store history for analysis
        
        # Adaptive parameters that change based on environment
        self.adaptive_rate_fast = 0.1    # Fast adaptation when recovering
        self.adaptive_rate_normal = 0.02  # Normal adaptation rate
        self.adaptive_rate_slow = 0.005   # Slow adaptation in stable conditions
        self.current_adaptive_rate = self.adaptive_rate_normal
        
        # Calibration validation variables
        self.calibration_voice_detections = 0
        self.calibration_total_samples = 0
        
        print("[OK] Voice Direction Detector initialized")
        print(f"    Sample rate: {rate} Hz")
        print(f"    Channels: {channels}")
        print(f"    VAD frame: {vad_frames} ms")
        print(f"    DOA window: {doa_frames} ms")
        print(f"    Speech band: {self.speech_low_freq}-{self.speech_high_freq} Hz")
        print(f"    Calibration time: {calibration_time} seconds")
        print(f"    SNR threshold: {self.snr_threshold} dB")
        print(f"    LED persistence: {self.led_persistence_time} seconds")

    def calculate_snr(self, signal_spectrum):
        """
        Calculate Signal-to-Noise Ratio
        
        Args:
            signal_spectrum: FFT magnitude spectrum of current audio
            
        Returns:
            float: SNR in dB
        """
        if self.background_noise_spectrum is None:
            return float('inf')  # No background reference
        
        # Ensure same length
        min_len = min(len(signal_spectrum), len(self.background_noise_spectrum))
        signal_power = np.mean(signal_spectrum[:min_len]**2)
        noise_power = np.mean(self.background_noise_spectrum[:min_len]**2)
        
        if noise_power == 0:
            return float('inf')
        
        snr_linear = signal_power / noise_power
        snr_db = 10 * np.log10(snr_linear) if snr_linear > 0 else -float('inf')
        
        return snr_db

    def validate_calibration_quality(self):
        """
        Check if initial calibration was contaminated with voice
        
        Returns:
            bool: True if calibration appears to be good quality
        """
        if self.calibration_total_samples == 0:
            return True
            
        voice_ratio = self.calibration_voice_detections / self.calibration_total_samples
        
        if voice_ratio > self.calibration_quality_threshold:
            self.contaminated_calibration = True
            print(f"\n[WARNING] Calibration may be contaminated!")
            print(f"    Voice detected in {voice_ratio:.1%} of calibration samples")
            print(f"    Threshold: {self.calibration_quality_threshold:.1%}")
            print(f"    Will use adaptive recovery mode")
            return False
        else:
            print(f"\n[OK] Calibration quality good ({voice_ratio:.1%} voice content)")
            return True

    def calibrate_background_noise(self, mic):
        """
        Enhanced background noise calibration with quality validation
        
        Args:
            mic: MicArray instance
        """
        print(f"\n[CALIBRATION] Measuring background noise for {self.calibration_time} seconds...")
        print("Please remain quiet during calibration...")
        
        calibration_chunks_needed = int(self.calibration_time * 1000 / self.vad_frames)
        calibration_samples = []
        
        pixel_ring.set_color(r=255, g=255, b=0)  # Yellow during calibration
        
        self.calibration_voice_detections = 0
        self.calibration_total_samples = 0
        
        for i, chunk in enumerate(mic.read_chunks()):
            if i >= calibration_chunks_needed:
                break
            
            # Extract audio for analysis
            if self.channels == 6:
                audio_for_analysis = chunk[1::self.channels]
                mono_audio = chunk[1::self.channels].tobytes()
            else:
                audio_for_analysis = chunk[0::self.channels]
                mono_audio = chunk[0::self.channels].tobytes()
            
            # Check for voice contamination during calibration
            try:
                vad_result = self.vad.is_speech(mono_audio, self.rate)
                if vad_result:
                    self.calibration_voice_detections += 1
            except:
                pass  # If VAD fails, continue without voice detection
            
            self.calibration_total_samples += 1
            calibration_samples.append(audio_for_analysis)
            
            # Progress indicator
            progress = (i + 1) / calibration_chunks_needed
            print(f"\rCalibration progress: {progress:.0%}", end='', flush=True)
        
        # Calculate background noise characteristics
        all_samples = np.concatenate(calibration_samples)
        self.background_noise_energy = np.var(all_samples.astype(np.float32))
        
        # Calculate background noise spectrum
        audio_float = all_samples.astype(np.float32) / 32768.0
        audio_float = audio_float - np.mean(audio_float)
        windowed = audio_float * np.hanning(len(audio_float))
        fft_data = np.abs(fft(windowed))
        self.background_noise_spectrum = fft_data[:len(fft_data)//2]
        
        # Initialize multiple noise floor estimates
        self.primary_noise_floor = self.background_noise_energy
        self.secondary_noise_floor = self.background_noise_energy * 1.2
        self.tertiary_noise_floor = self.background_noise_energy * 0.8
        
        # Set dynamic thresholds based on background noise
        self.dynamic_energy_threshold = max(
            self.voice_energy_threshold,
            self.background_noise_energy * self.noise_floor_multiplier
        )
        
        # Validate calibration quality
        calibration_good = self.validate_calibration_quality()
        
        if not calibration_good:
            # Start with more conservative thresholds and faster adaptation
            self.dynamic_energy_threshold *= 1.5  # More conservative
            self.current_adaptive_rate = self.adaptive_rate_fast
            print(f"    Using recovery mode with faster adaptation")
        
        self.is_calibrated = True
        pixel_ring.off()
        
        print(f"\n[CALIBRATION] Complete!")
        print(f"    Background noise energy: {self.background_noise_energy:.2e}")
        print(f"    Dynamic energy threshold: {self.dynamic_energy_threshold:.2e}")
        print(f"    Adaptive rate: {self.current_adaptive_rate}")
        if calibration_good:
            print(f"    Status: Good quality")
        else:
            print(f"    Status: Contaminated - using recovery mode")

    def detect_noise_floor_drift(self):
        """
        Detect if the noise floor has drifted significantly and needs adjustment
        
        Returns:
            bool: True if recalibration is recommended
        """
        if len(self.noise_floor_history) < 50:
            return False
        
        recent_samples = list(self.noise_floor_history)[-50:]
        median_recent = np.median(recent_samples)
        
        # Check if recent noise floor is significantly different from calibrated
        drift_ratio = median_recent / self.background_noise_energy
        
        # Significant drift detected
        if drift_ratio > 3.0 or drift_ratio < 0.3:
            self.recalibration_trigger_count += 1
            
            if self.recalibration_trigger_count >= self.recalibration_threshold:
                return True
        else:
            # Reset trigger count if drift is normal
            self.recalibration_trigger_count = max(0, self.recalibration_trigger_count - 1)
        
        return False

    def perform_quiet_recalibration(self):
        """
        Recalibrate noise floor using accumulated quiet samples
        """
        if len(self.quiet_samples_buffer) < self.min_quiet_samples_for_recalibration:
            return False
        
        print(f"\n[RECALIBRATION] Using {len(self.quiet_samples_buffer)} quiet samples...")
        
        # Calculate new noise floor from quiet samples
        quiet_energies = list(self.quiet_samples_buffer)
        new_noise_floor = np.median(quiet_energies)
        
        # Validate the new noise floor (shouldn't be too different unless environment changed)
        if self.background_noise_energy is not None:
            ratio = new_noise_floor / self.background_noise_energy
            if 0.1 <= ratio <= 10.0:  # Reasonable range
                # Update noise floor with weighted average
                self.background_noise_energy = (
                    0.7 * self.background_noise_energy + 
                    0.3 * new_noise_floor
                )
                
                # Update thresholds
                self.dynamic_energy_threshold = max(
                    self.voice_energy_threshold,
                    self.background_noise_energy * self.noise_floor_multiplier
                )
                
                # Reset contamination flag if we've successfully recalibrated
                if self.contaminated_calibration:
                    self.contaminated_calibration = False
                    self.current_adaptive_rate = self.adaptive_rate_normal
                    print(f"    Recovered from contaminated calibration")
                
                self.recalibration_trigger_count = 0
                self.quiet_samples_buffer.clear()
                
                print(f"    New noise floor: {self.background_noise_energy:.2e}")
                print(f"    New threshold: {self.dynamic_energy_threshold:.2e}")
                return True
        
        return False

    def update_adaptive_background(self, audio_data, is_voice):
        """
        Enhanced adaptive background updating with recovery mechanisms
        
        Args:
            audio_data: Current audio chunk
            is_voice: Whether current chunk is classified as voice
        """
        current_energy = np.var(audio_data.astype(np.float32))
        self.noise_floor_history.append(current_energy)
        
        if not is_voice and self.is_calibrated:
            # Add to quiet samples buffer for potential recalibration
            self.adaptive_background_history.append(current_energy)
            self.quiet_samples_buffer.append(current_energy)
            
            # Update background noise energy with current adaptive rate
            if len(self.adaptive_background_history) >= 10:
                recent_background = np.median(list(self.adaptive_background_history))
                
                # Adaptive rate changes based on stability
                if self.contaminated_calibration:
                    # Faster adaptation during recovery
                    adaptation_rate = self.adaptive_rate_fast
                else:
                    # Normal or slow adaptation
                    adaptation_rate = self.current_adaptive_rate
                
                # Update with exponential moving average
                self.background_noise_energy = (
                    (1 - adaptation_rate) * self.background_noise_energy +
                    adaptation_rate * recent_background
                )
                
                # Update multiple noise floor estimates
                self.primary_noise_floor = self.background_noise_energy
                self.secondary_noise_floor = recent_background
                
                # Update dynamic threshold
                self.dynamic_energy_threshold = max(
                    self.voice_energy_threshold,
                    self.background_noise_energy * self.noise_floor_multiplier
                )
        
        # Check for drift and potential recalibration
        if self.detect_noise_floor_drift():
            print(f"\n[ADAPTIVE] Significant noise floor drift detected")
            if len(self.quiet_samples_buffer) >= self.min_quiet_samples_for_recalibration:
                self.perform_quiet_recalibration()
            else:
                print(f"    Need {self.min_quiet_samples_for_recalibration - len(self.quiet_samples_buffer)} more quiet samples for recalibration")

    def analyze_speech_characteristics(self, audio_data):
        """
        Analyze audio for speech-specific characteristics with background noise consideration
        
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
        current_energy = np.var(audio_float)
        
        if total_energy < 1e-10:  # Silence
            return {'is_voice': False, 'confidence': 0.0, 'reason': 'silence', 'snr_db': -float('inf')}
        
        # Calculate SNR
        snr_db = self.calculate_snr(fft_data)
        
        # Energy in speech frequency band
        speech_energy = np.sum(fft_data[self.speech_mask[:len(fft_data)]]**2)
        speech_ratio = speech_energy / total_energy if total_energy > 0 else 0
        
        # Energy-based noise rejection using calibrated background (made more lenient)
        if self.is_calibrated:
            energy_above_background = current_energy > (self.background_noise_energy * self.noise_floor_multiplier)
            snr_sufficient = snr_db >= self.snr_threshold
        else:
            # Fallback to original thresholds if not calibrated
            energy_above_background = True
            snr_sufficient = True
        
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
        
        # Voice classification criteria (more lenient)
        criteria = {
            'speech_energy': speech_ratio >= (self.voice_energy_threshold),  # Reduced threshold
            'spectral_centroid': self.spectral_centroid_range[0] <= spectral_centroid <= self.spectral_centroid_range[1],
            'spectral_rolloff': spectral_rolloff <= 4500,  # Increased from 4000
            'zero_crossing': 0.01 <= zcr <= 0.3,  # More lenient range
            'energy_level': total_energy > 1e-6,  # Reduced from 1e-6
        }
        
        # Add noise criteria as bonus, not requirements
        if energy_above_background:
            criteria['energy_above_background'] = True
        if snr_sufficient:
            criteria['snr_sufficient'] = True
        
        # Calculate voice confidence
        passed_criteria = sum(criteria.values())
        total_criteria = len(criteria)
        voice_confidence = passed_criteria / total_criteria
        
        # Additional noise rejection (more lenient)
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
        
        # Boost confidence if SNR is very high
        if snr_db > 12.0:  # Very clear signal
            voice_confidence = min(1.0, voice_confidence * 1.2)
        elif snr_db < 3.0:  # Very poor signal
            voice_confidence *= 0.5
        
        # More lenient final decision - don't require all noise criteria
        base_voice_detection = voice_confidence >= 0.6
        
        # Only apply strict noise filtering if we have very poor SNR or energy
        if self.is_calibrated:
            # Allow voice if basic criteria pass, even with moderate noise
            if snr_db < 0:  # Very poor SNR (was 3.0)
                base_voice_detection = False
            elif not energy_above_background and current_energy < (self.background_noise_energy * 0.8):
                # Only reject if significantly below background
                base_voice_detection = False
        
        is_voice = base_voice_detection
        
        return {
            'is_voice': is_voice,
            'confidence': voice_confidence,
            'speech_ratio': speech_ratio,
            'spectral_centroid': spectral_centroid,
            'spectral_rolloff': spectral_rolloff,
            'zcr': zcr,
            'snr_db': snr_db,
            'criteria': criteria
        }
    
    def is_speech_detected(self, mono_audio, chunk_data):
        """
        Enhanced speech detection combining VAD, spectral analysis, and background noise calibration
        
        Args:
            mono_audio: Raw audio bytes for VAD
            chunk_data: Numpy array for spectral analysis
            
        Returns:
            bool: True if speech is detected
        """
        # Basic VAD check
        vad_result = self.vad.is_speech(mono_audio, self.rate)
        
        # If VAD says no speech and we're being conservative, trust it more
        if not vad_result:
            # Still do spectral analysis for learning, but weight VAD heavily
            if self.channels == 6:
                audio_for_analysis = chunk_data[1::self.channels]
            else:
                audio_for_analysis = chunk_data[0::self.channels]
            
            speech_analysis = self.analyze_speech_characteristics(audio_for_analysis)
            self.spectral_history.append(speech_analysis['confidence'])
            self.update_adaptive_background(audio_for_analysis, False)
            
            # Only override VAD if spectral analysis is very confident
            return speech_analysis['confidence'] > 0.8
        
        # VAD detected something, verify with spectral analysis
        if self.channels == 6:
            audio_for_analysis = chunk_data[1::self.channels]
        else:
            audio_for_analysis = chunk_data[0::self.channels]
        
        speech_analysis = self.analyze_speech_characteristics(audio_for_analysis)
        self.spectral_history.append(speech_analysis['confidence'])
        
        # Update adaptive background
        preliminary_voice_detection = speech_analysis['is_voice']
        self.update_adaptive_background(audio_for_analysis, preliminary_voice_detection)
        
        # Combine VAD and spectral with more weight on VAD
        spectral_confidence = np.mean(list(self.spectral_history)) if self.spectral_history else 0
        
        # Trust VAD more, use spectral as confirmation
        return vad_result and (speech_analysis['is_voice'] or spectral_confidence > 0.4)

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
    
    def update_leds(self, direction, force_update=False):
        """
        Update LEDs with rate limiting and persistence
        
        Args:
            direction: Direction to display (or None to turn off)
            force_update: Force update regardless of timing
        """
        current_time = time.time()
        
        # Rate limit LED updates to prevent flickering
        if not force_update and (current_time - self.last_led_update_time) < self.led_update_interval:
            return
        
        if direction is not None:
            # Voice detected - update LEDs and record time
            pixel_ring.set_direction(direction, self.channels)
            self.current_led_direction = direction
            self.last_voice_time = current_time
        else:
            # No voice - check if we should keep LEDs on due to persistence
            time_since_voice = current_time - self.last_voice_time
            if time_since_voice > self.led_persistence_time:
                # Persistence time expired - turn off LEDs
                pixel_ring.off()
                self.current_led_direction = None
            # Otherwise, keep current LEDs on
        
        self.last_led_update_time = current_time

    def run(self, callback=None, debug=False):
        """
        Run continuous voice direction detection with background noise calibration
        
        Args:
            callback: Optional function to call with (direction, confidence) when voice detected
            debug: Show debug information
        """
        print("\n[MIC] Voice Direction Detection with Background Calibration")
        print("=" * 60)
        
        try:
            # Initialize pixel ring
            pixel_ring.off()
            
            with MicArray(self.rate, self.channels, self.chunk_size) as mic:
                # Perform background noise calibration
                if not self.is_calibrated:
                    self.calibrate_background_noise(mic)
                
                print("\nListening for voice... (Press Ctrl+C to stop)")
                print("=" * 50)
                
                speech_count = 0
                chunks = []
                last_direction = None
                last_report_time = time.time()
                report_interval = 0.5
                
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
                        
                        # Lower threshold for direction detection (was 0.6, now 0.4)
                        if speech_count > (self.doa_chunks * 0.4):  # 40% of chunks must be voice
                            # Calculate DOA from accumulated audio
                            frames = np.concatenate(chunks)
                            direction = mic.get_direction(frames)
                            
                            if direction is not None:
                                # Smooth the direction
                                smoothed_direction = self.get_smoothed_direction(direction)
                                
                                # Update LEDs with persistence
                                self.update_leds(smoothed_direction)
                                
                                # Report if significant change or timeout
                                direction_changed = (
                                    last_direction is None or 
                                    abs(smoothed_direction - last_direction) > 15 or  # Increased from 10 to reduce updates
                                    (current_time - last_report_time) > report_interval
                                )
                                
                                if direction_changed:
                                    compass = self.get_compass_visual(smoothed_direction)
                                    spectral_conf = np.mean(list(self.spectral_history)) if self.spectral_history else 0
                                    
                                    # Show actual SNR if available
                                    latest_snr = "N/A"
                                    if hasattr(self, '_last_snr'):
                                        latest_snr = f"{self._last_snr:.1f}dB"
                                    
                                    if not debug:
                                        print(f"\r[VOICE] {smoothed_direction:3d}° {compass} "
                                              f"(VAD: {confidence:.0%}, Spectral: {spectral_conf:.0%}, SNR: {latest_snr})    ", 
                                              end='', flush=True)
                                    else:
                                        print(f"\n[VOICE] Direction: {smoothed_direction:3d}° {compass} "
                                              f"(VAD: {confidence:.0%}, Spectral: {spectral_conf:.0%}, SNR: {latest_snr})")
                                    
                                    if callback:
                                        callback(smoothed_direction, confidence)
                                    
                                    last_direction = smoothed_direction
                                    last_report_time = current_time
                        else:
                            # No voice detected - use LED persistence
                            self.update_leds(None)  # This will maintain LEDs during persistence period
                            
                            if not debug:
                                spectral_conf = np.mean(list(self.spectral_history)) if self.spectral_history else 0
                                bg_energy = f"{self.background_noise_energy:.1e}" if self.is_calibrated else "N/A"
                                led_status = "ON" if self.current_led_direction is not None else "OFF"
                                print(f"\r[IDLE] No voice (VAD: {confidence:.0%}, Spectral: {spectral_conf:.0%}, BG: {bg_energy}, LED: {led_status})    ", 
                                      end='', flush=True)
                            
                            # Only clear last_direction if LEDs are actually off
                            if self.current_led_direction is None:
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
    parser.add_argument('--calibration-time', type=float, default=3.0,
                        help='Background noise calibration time in seconds (default: 3.0)')
    parser.add_argument('--snr-threshold', type=float, default=6.0,
                        help='Minimum SNR threshold in dB (default: 6.0)')
    parser.add_argument('--skip-calibration', action='store_true',
                        help='Skip initial background noise calibration')
    
    args = parser.parse_args()
    
    try:  
        # Create detector
        detector = VoiceDirectionDetector(
            rate=args.rate,
            channels=args.channels,
            vad_frames=args.vad_frames,
            doa_frames=args.doa_frames,
            vad_aggressiveness=args.vad_level,
            confidence_threshold=args.threshold,
            calibration_time=args.calibration_time
        )
        
        # Override SNR threshold if specified
        if hasattr(args, 'snr_threshold'):
            detector.snr_threshold = args.snr_threshold
        
        # Skip calibration if requested
        if args.skip_calibration:
            detector.is_calibrated = True
            print("[INFO] Skipping background noise calibration")
        
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