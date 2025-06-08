#!/usr/bin/env python3
"""
Debug version of ROS2 Voice Direction Detection Node
Enhanced with debugging output to diagnose voice detection issues
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32, Bool, String, Header
import numpy as np
import threading
import time
from collections import deque
from .mic_array import MicArray
from .pixel_ring import pixel_ring
import webrtcvad
from scipy.fft import fft


class VoiceDirectionNode(Node):
    def __init__(self):
        super().__init__('voice_direction_node')
        
        # Declare parameters
        self.declare_parameter('sample_rate', 16000)
        self.declare_parameter('channels', 4)
        self.declare_parameter('vad_frames', 20)
        self.declare_parameter('doa_frames', 200)
        self.declare_parameter('vad_aggressiveness', 3)
        self.declare_parameter('confidence_threshold', 0.5)
        self.declare_parameter('publish_rate', 10.0)  # Hz
        self.declare_parameter('enable_pixel_ring', True)
        self.declare_parameter('min_report_interval', 0.5)  # seconds
        self.declare_parameter('direction_smoothing_window', 5)
        self.declare_parameter('enable_voice_following', True)
        self.declare_parameter('direction_stability_threshold', 90.0)  # degrees
        self.declare_parameter('min_consistent_samples', 1)
        self.declare_parameter('debug_mode', True)  # Add debug parameter
        self.declare_parameter('bypass_state_check', True)  # Bypass state checking for debugging
        self.declare_parameter('calibration_time', 3.0)  # Background noise calibration time
        self.declare_parameter('snr_threshold', 2.0)  # SNR threshold in dB
        self.declare_parameter('skip_calibration', False)  # Skip calibration option
        self.declare_parameter('mic_orientation_offset', 180.0)  # Offset to align mic with robot front
        self.declare_parameter('mic_mounting_correction', 45.0)  # Additional mounting correction
        
        # Get parameters
        self.rate = self.get_parameter('sample_rate').value
        self.channels = self.get_parameter('channels').value
        self.vad_frames = self.get_parameter('vad_frames').value
        self.doa_frames = self.get_parameter('doa_frames').value
        self.vad_aggressiveness = self.get_parameter('vad_aggressiveness').value
        self.confidence_threshold = self.get_parameter('confidence_threshold').value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.enable_pixel_ring = self.get_parameter('enable_pixel_ring').value
        self.min_report_interval = self.get_parameter('min_report_interval').value
        self.direction_smoothing_window = self.get_parameter('direction_smoothing_window').value
        self.enable_voice_following = self.get_parameter('enable_voice_following').value
        self.direction_stability_threshold = self.get_parameter('direction_stability_threshold').value
        self.min_consistent_samples = self.get_parameter('min_consistent_samples').value
        self.bypass_state_check = self.get_parameter('bypass_state_check').value
        self.calibration_time = self.get_parameter('calibration_time').value
        self.snr_threshold = self.get_parameter('snr_threshold').value
        self.skip_calibration = self.get_parameter('skip_calibration').value
        self.mic_orientation_offset = self.get_parameter('mic_orientation_offset').value
        self.mic_mounting_correction = self.get_parameter('mic_mounting_correction').value
        self.debug_mode = True
        
        # Enhanced speech analysis parameters
        self.speech_low_freq = 300
        self.speech_high_freq = 3400
        self.voice_energy_threshold = 0.4
        self.spectral_centroid_range = (500, 2000)
        
        # Background noise calibration
        self.background_noise_energy = None
        self.background_noise_spectrum = None
        self.is_calibrated = False
        self.calibration_samples = []
        self.adaptive_background_history = deque(maxlen=50)
        self.noise_floor_multiplier = 1.5
        self.adaptive_update_rate = 0.05
        self.default_background_noise_energy = 1e-6  # Default value
        
        # Dynamic thresholds
        self.dynamic_energy_threshold = self.voice_energy_threshold
        
        # LED persistence
        self.led_persistence_time = 1.5
        self.last_voice_time = 0
        self.last_led_update_time = 0
        self.led_update_interval = 0.1
        self.current_led_direction = None
        
        # Initialize VAD
        self.vad = webrtcvad.Vad(self.vad_aggressiveness)
        
        # Calculate chunk size
        self.chunk_size = int(self.rate * self.vad_frames / 1000)
        self.doa_chunks = int(self.doa_frames / self.vad_frames)
        
        # Enhanced history for better smoothing - matching standalone script
        self.direction_history = deque(maxlen=self.direction_smoothing_window)
        self.voice_history = deque(maxlen=15)  # Match standalone
        self.spectral_history = deque(maxlen=8)  # Match standalone
        self.raw_direction_buffer = deque(maxlen=10)
        
        # Precompute frequency bins for efficiency
        self.freq_bins = np.fft.fftfreq(self.chunk_size, 1/self.rate)
        self.speech_mask = (self.freq_bins >= self.speech_low_freq) & (self.freq_bins <= self.speech_high_freq)
        
        # State tracking
        self.last_direction = None
        self.last_stable_direction = None
        self.last_report_time = self.get_clock().now()
        self.voice_active = False
        self.current_confidence = 0.0
        self.consistent_direction_count = 0
        self.current_state = "UNKNOWN"
        self.current_animation = None
        
        # Debug counters
        self.audio_chunks_received = 0
        self.speech_detections = 0
        self.direction_calculations = 0
        self.messages_published = 0
        self.spectral_confidence = 0.0
        self.current_snr = 0.0
        
        # Enhanced adaptive noise floor with recovery - matching standalone
        self.calibration_quality_threshold = 0.6
        self.contaminated_calibration = False
        self.recalibration_trigger_count = 0
        self.recalibration_threshold = 50
        self.min_quiet_samples_for_recalibration = 100
        self.quiet_samples_buffer = deque(maxlen=self.min_quiet_samples_for_recalibration)
        
        # Multiple noise floor estimates for robustness
        self.primary_noise_floor = None
        self.secondary_noise_floor = None
        self.tertiary_noise_floor = None
        self.noise_floor_history = deque(maxlen=200)
        
        # Adaptive parameters that change based on environment
        self.adaptive_rate_fast = 0.1
        self.adaptive_rate_normal = 0.02
        self.adaptive_rate_slow = 0.005
        self.current_adaptive_rate = self.adaptive_rate_normal
        
        # Calibration validation variables
        self.calibration_voice_detections = 0
        self.calibration_total_samples = 0
        
        # Add SNR tracking for compatibility
        self._last_snr = 0.0
        
        # Subscribe to robot state
        self.state_subscriber = self.create_subscription(
            String,
            '/luxo/current_state',
            self.state_callback,
            10
        )
        
        # Subscribe to animation status
        self.animation_subscriber = self.create_subscription(
            String,
            '/roarm/current_animation',
            self.animation_callback,
            10
        )
        
        # Publishers
        self.voice_direction_pub = self.create_publisher(
            Float32,
            '/voice/direction',
            10
        )
        
        self.voice_active_pub = self.create_publisher(
            Bool,
            '/voice/active',
            10
        )
        
        self.voice_confidence_pub = self.create_publisher(
            Float32,
            '/voice/confidence',
            10
        )
        
        self.voice_info_pub = self.create_publisher(
            String,
            '/voice/info',
            10
        )
        
        self.voice_follow_pub = self.create_publisher(
            Float32,
            '/voice/follow_direction',
            10
        )
        
        # Debug publisher
        self.debug_pub = self.create_publisher(
            String,
            '/voice/debug',
            10
        )
        
        # Add spectral confidence publisher
        self.spectral_confidence_pub = self.create_publisher(
            Float32,
            '/voice/spectral_confidence',
            10
        )
        
        # Add SNR publisher
        self.snr_pub = self.create_publisher(
            Float32,
            '/voice/snr',
            10
        )
        
        # Thread control
        self.running = False
        self.audio_thread = None
        
        # Timer for publishing voice status
        self.status_timer = self.create_timer(1.0 / self.publish_rate, self.publish_voice_status)
        
        # Debug timer
        if self.debug_mode:
            self.debug_timer = self.create_timer(15.0, self.publish_debug_info)
        
        self.get_logger().info('Voice Direction Node initialized (DEBUG MODE with Enhanced Speech Analysis)')
        self.get_logger().info(f'Sample rate: {self.rate} Hz, Channels: {self.channels}')
        self.get_logger().info(f'Voice following enabled: {self.enable_voice_following}')
        self.get_logger().info(f'Direction stability threshold: {self.direction_stability_threshold}°')
        self.get_logger().info(f'Bypass state check: {self.bypass_state_check}')
        self.get_logger().info(f'Debug mode: {self.debug_mode}')
        self.get_logger().info(f'Calibration time: {self.calibration_time} seconds')
        self.get_logger().info(f'SNR threshold: {self.snr_threshold} dB')
        self.get_logger().info(f'Mic orientation offset: {self.mic_orientation_offset}° (base rotation)')
        self.get_logger().info(f'Mic mounting correction: {self.mic_mounting_correction}° (fine tuning)')
        self.get_logger().info('Tip: If robot faces away from voice, try mic_orientation_offset:=0.0 or mic_orientation_offset:=180.0')
        
        # Start audio processing
        self.start_audio_processing()

    def validate_calibration_quality(self):
        """Check if initial calibration was contaminated with voice"""
        if self.calibration_total_samples == 0:
            return True
            
        voice_ratio = self.calibration_voice_detections / self.calibration_total_samples
        
        if voice_ratio > self.calibration_quality_threshold:
            self.contaminated_calibration = True
            self.get_logger().warning(f"Calibration may be contaminated! "
                                     f"Voice detected in {voice_ratio:.1%} of calibration samples "
                                     f"(threshold: {self.calibration_quality_threshold:.1%}). "
                                     f"Will use adaptive recovery mode")
            return False
        else:
            self.get_logger().info(f"Calibration quality good ({voice_ratio:.1%} voice content)")
            return True

    def calibrate_background_noise(self, mic):
        """Enhanced background noise calibration with quality validation"""
        self.get_logger().info(f'Measuring background noise for {self.calibration_time} seconds...')
        self.get_logger().info('Please remain quiet during calibration...')
        
        calibration_chunks_needed = int(self.calibration_time * 1000 / self.vad_frames)
        calibration_samples = []
        
        if self.enable_pixel_ring:
            try:
                pixel_ring.set_color(r=255, g=255, b=0)  # Yellow during calibration
            except:
                pass
        
        self.calibration_voice_detections = 0
        self.calibration_total_samples = 0
        
        chunk_count = 0
        for chunk in mic.read_chunks():
            if chunk_count >= calibration_chunks_needed:
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
            chunk_count += 1
            
            # Progress indicator
            if chunk_count % 10 == 0:
                progress = chunk_count / calibration_chunks_needed
                self.get_logger().info(f'Calibration progress: {progress:.0%}')
        
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
            self.get_logger().info("Using recovery mode with faster adaptation")
        
        self.is_calibrated = True
        
        if self.enable_pixel_ring:
            try:
                pixel_ring.off()
            except:
                pass
        
        self.get_logger().info('Background noise calibration complete!')
        self.get_logger().info(f'Background noise energy: {self.background_noise_energy:.2e}')
        self.get_logger().info(f'Dynamic energy threshold: {self.dynamic_energy_threshold:.2e}')
        self.get_logger().info(f'Adaptive rate: {self.current_adaptive_rate}')
        if calibration_good:
            self.get_logger().info('Status: Good quality')
        else:
            self.get_logger().info('Status: Contaminated - using recovery mode')

    def detect_noise_floor_drift(self):
        """Detect if the noise floor has drifted significantly and needs adjustment"""
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
        """Recalibrate noise floor using accumulated quiet samples"""
        if len(self.quiet_samples_buffer) < self.min_quiet_samples_for_recalibration:
            return False
        
        self.get_logger().info(f"[RECALIBRATION] Using {len(self.quiet_samples_buffer)} quiet samples...")
        
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
                    self.get_logger().info("Recovered from contaminated calibration")
                
                self.recalibration_trigger_count = 0
                self.quiet_samples_buffer.clear()
                
                self.get_logger().info(f"New noise floor: {self.background_noise_energy:.2e}")
                self.get_logger().info(f"New threshold: {self.dynamic_energy_threshold:.2e}")
                return True
        
        return False

    def update_adaptive_background(self, audio_data, is_voice):
        """Enhanced adaptive background updating with recovery mechanisms"""
        current_energy = np.var(audio_data.astype(np.float32))
        self.noise_floor_history.append(current_energy)
        
        # Initialize background noise energy if not set
        if self.background_noise_energy is None:
            self.background_noise_energy = self.default_background_noise_energy
        
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
            self.get_logger().info("[ADAPTIVE] Significant noise floor drift detected")
            if len(self.quiet_samples_buffer) >= self.min_quiet_samples_for_recalibration:
                self.perform_quiet_recalibration()
            else:
                needed = self.min_quiet_samples_for_recalibration - len(self.quiet_samples_buffer)
                self.get_logger().info(f"Need {needed} more quiet samples for recalibration")

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

    def analyze_speech_characteristics(self, audio_data):
        """Analyze audio for speech-specific characteristics with background noise consideration"""
        # Convert to float for analysis
        audio_float = audio_data.astype(np.float32) / 32768.0
        
        # Remove DC component
        audio_float = audio_float - np.mean(audio_float)
        
        # Apply window to reduce spectral leakage
        windowed = audio_float * np.hanning(len(audio_float))
        
        # Compute FFT
        fft_data = np.abs(fft(windowed))
        fft_data = fft_data[:len(fft_data)//2]
        
        # Calculate total energy
        total_energy = np.sum(fft_data**2)
        current_energy = np.var(audio_float)
        
        if total_energy < 1e-10:
            return {'is_voice': False, 'confidence': 0.0, 'reason': 'silence', 'snr_db': -float('inf')}
        
        # Calculate SNR
        snr_db = self.calculate_snr(fft_data)
        self.current_snr = snr_db
        self._last_snr = snr_db  # Track for debug output
        
        # Energy in speech frequency band
        speech_energy = np.sum(fft_data[self.speech_mask[:len(fft_data)]]**2)
        speech_ratio = speech_energy / total_energy if total_energy > 0 else 0
        
        # Energy-based noise rejection using calibrated background (made more lenient)
        if self.is_calibrated and self.background_noise_energy is not None:
            energy_above_background = current_energy > (self.background_noise_energy * self.noise_floor_multiplier)
            snr_sufficient = snr_db >= self.snr_threshold
        else:
            # Fallback to original thresholds if not calibrated or background_noise_energy is None
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
        
        # Zero crossing rate
        zero_crossings = np.sum(np.diff(np.sign(audio_float)) != 0)
        zcr = zero_crossings / len(audio_float)
        
        # Voice classification criteria (more lenient - matching standalone)
        criteria = {
            'speech_energy': speech_ratio >= self.voice_energy_threshold,
            'spectral_centroid': self.spectral_centroid_range[0] <= spectral_centroid <= self.spectral_centroid_range[1],
            'spectral_rolloff': spectral_rolloff <= 4500,
            'zero_crossing': 0.01 <= zcr <= 0.3,
            'energy_level': total_energy > 1e-6,
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
        
        # More lenient final decision - matching standalone
        base_voice_detection = voice_confidence >= 0.6
        
        # Only apply strict noise filtering if we have very poor SNR or energy
        if self.is_calibrated and self.background_noise_energy is not None:
            # Allow voice if basic criteria pass, even with moderate noise
            if snr_db < 0:  # Very poor SNR
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
        """Enhanced speech detection combining VAD, spectral analysis, and background noise calibration"""
        # Basic VAD check
        vad_result = self.vad.is_speech(mono_audio, self.rate)
        
        # Extract audio for analysis
        if self.channels == 6:
            audio_for_analysis = chunk_data[1::self.channels]
        else:
            audio_for_analysis = chunk_data[0::self.channels]
        
        # Perform spectral analysis
        speech_analysis = self.analyze_speech_characteristics(audio_for_analysis)
        self.spectral_history.append(speech_analysis['confidence'])
        
        # Update adaptive background
        preliminary_voice_detection = speech_analysis['is_voice']
        self.update_adaptive_background(audio_for_analysis, preliminary_voice_detection)
        
        # If VAD says no speech, only override if spectral analysis is very confident
        if not vad_result:
            return speech_analysis['confidence'] > 0.8
        
        # Combine VAD and spectral with more weight on VAD
        spectral_confidence = np.mean(list(self.spectral_history)) if self.spectral_history else 0
        
        # Update spectral confidence for publishing
        self.spectral_confidence = spectral_confidence
        
        # Trust VAD more, use spectral as confirmation - matching standalone
        return vad_result and (speech_analysis['is_voice'] or spectral_confidence > 0.4)
    
    def update_leds(self, direction, force_update=False):
        """Update LEDs with rate limiting and persistence"""
        current_time = time.time()
        
        # Rate limit LED updates to prevent flickering
        if not force_update and (current_time - self.last_led_update_time) < self.led_update_interval:
            return
        
        if direction is not None:
            # Voice detected - update LEDs and record time
            if self.enable_pixel_ring:
                try:
                    pixel_ring.set_direction(direction, self.channels)
                except:
                    pass
            self.current_led_direction = direction
            self.last_voice_time = current_time
        else:
            # No voice - check if we should keep LEDs on due to persistence
            time_since_voice = current_time - self.last_voice_time
            if time_since_voice > self.led_persistence_time:
                if self.enable_pixel_ring:
                    try:
                        pixel_ring.off()
                    except:
                        pass
                self.current_led_direction = None
        
        self.last_led_update_time = current_time

    def publish_debug_info(self):
        """Publish debug information periodically"""
        debug_msg = String()
        debug_msg.data = (
            f"chunks:{self.audio_chunks_received}, "
            f"speech:{self.speech_detections}, "
            f"directions:{self.direction_calculations}, "
            f"published:{self.messages_published}, "
            f"state:{self.current_state}, "
            f"vad_confidence:{self.current_confidence:.2f}, "
            f"spectral_confidence:{self.spectral_confidence:.2f}, "
            f"snr:{self.current_snr:.1f}dB, "
            f"active:{self.voice_active}"
        )
        self.debug_pub.publish(debug_msg)
        
        # Publish spectral confidence
        spec_msg = Float32()
        spec_msg.data = self.spectral_confidence
        self.spectral_confidence_pub.publish(spec_msg)
        
        # Publish SNR
        snr_msg = Float32()
        snr_msg.data = self.current_snr
        self.snr_pub.publish(snr_msg)
        
        if self.debug_mode:
            self.get_logger().info(f"[DEBUG] {debug_msg.data}")
    
    def state_callback(self, msg):
        """Update current robot state"""
        self.current_state = msg.data
        if self.debug_mode:
            self.get_logger().debug(f"Robot state updated: {self.current_state}")
    
    def animation_callback(self, msg):
        """Update current animation"""
        self.current_animation = msg.data if msg.data else None
    
    def should_process_voice(self):
        """Check if we should process voice based on robot state"""
        if self.bypass_state_check:
            return True
            
        allowed_states = ['IDLE', 'ANIMATING', 'EMOTION_REACTING']
        return self.current_state in allowed_states
    
    def get_smoothed_direction(self, direction):
        """Apply circular mean to smooth direction readings - matching standalone"""
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
    
    def convert_mic_to_robot_angle(self, mic_angle):
        """Convert microphone array angle to robot base angle
        
        The mic array may be mounted differently than the robot's forward direction.
        Adjust this method based on your hardware setup.
        """
        # Apply orientation offset to align mic coordinates with robot coordinates
        # Default 180° means mic's 0° is at robot's back
        corrected_angle = mic_angle + self.mic_orientation_offset
        
        # Apply additional correction for any mounting offset
        corrected_angle += self.mic_mounting_correction
        
        # Normalize to 0-360 range first
        while corrected_angle < 0:
            corrected_angle += 360
        while corrected_angle >= 360:
            corrected_angle -= 360
        
        # Convert to -180 to 180 range for robot base
        robot_angle = corrected_angle
        if robot_angle > 180:
            robot_angle -= 360
            
        return robot_angle
    
    def publish_voice_direction(self, direction, confidence):
        """Publish voice direction information"""
        current_time = self.get_clock().now()
        
        # Convert mic angle to robot angle
        robot_angle = self.convert_mic_to_robot_angle(direction)
        
        # Publish raw direction
        direction_msg = Float32()
        direction_msg.data = float(robot_angle)
        self.voice_direction_pub.publish(direction_msg)
        
        # Publish confidence
        conf_msg = Float32()
        conf_msg.data = confidence
        self.voice_confidence_pub.publish(conf_msg)
        
        # Publish detailed info with spectral data
        info_msg = String()
        info_msg.data = (
            f"direction:{robot_angle:.1f},vad_confidence:{confidence:.2f},"
            f"spectral_confidence:{self.spectral_confidence:.2f},"
            f"state:{self.current_state}"
        )
        self.voice_info_pub.publish(info_msg)
        
        # Always publish follow direction if voice following is enabled
        if self.enable_voice_following:
            follow_msg = Float32()
            follow_msg.data = float(robot_angle)
            self.voice_follow_pub.publish(follow_msg)
            
            self.get_logger().info(
                f'[VOICE DETECTED] Mic: {direction}° → Robot: {robot_angle}° '
                f'VAD: {confidence:.0%}, Spectral: {self.spectral_confidence:.0%}, '
                f'SNR: {self.current_snr:.1f}dB'
            )
        
        self.messages_published += 1
    
    def publish_voice_status(self):
        """Periodically publish voice activity status"""
        active_msg = Bool()
        active_msg.data = self.voice_active
        self.voice_active_pub.publish(active_msg)
        
        # Update voice active based on recent detections
        current_time = self.get_clock().now()
        time_since_last = (current_time - self.last_report_time).nanoseconds / 1e9
        
        # Consider voice inactive if no detection for 2 seconds
        if time_since_last > 2.0:
            self.voice_active = False
            self.current_confidence = 0.0
            
            # Turn off pixel ring when voice inactive
            if self.enable_pixel_ring and not self.voice_active:
                try:
                    pixel_ring.off()
                except:
                    pass
    
    def audio_processing_thread(self):
        """Main audio processing thread - matching standalone logic"""
        self.get_logger().info('Starting audio processing thread')
        
        speech_count = 0
        chunks = []
        
        try:
            with MicArray(self.rate, self.channels, self.chunk_size) as mic:
                self.get_logger().info('Microphone array initialized successfully')
                
                # Perform background noise calibration
                if not self.skip_calibration and not self.is_calibrated:
                    self.calibrate_background_noise(mic)
                else:
                    # If calibration is skipped, initialize with default values
                    if self.background_noise_energy is None:
                        self.background_noise_energy = self.default_background_noise_energy
                        self.dynamic_energy_threshold = max(
                            self.voice_energy_threshold,
                            self.background_noise_energy * self.noise_floor_multiplier
                        )
                        self.get_logger().info(f"Using default background noise energy: {self.background_noise_energy:.2e}")
                
                for chunk in mic.read_chunks():
                    if not self.running:
                        break
                    
                    self.audio_chunks_received += 1
                    
                    # Log every 100th chunk in debug mode
                    if self.debug_mode and self.audio_chunks_received % 100 == 0:
                        self.get_logger().debug(f"Received {self.audio_chunks_received} audio chunks")
                    
                    # Check if we should process
                    if not self.should_process_voice():
                        if self.debug_mode and self.audio_chunks_received % 100 == 0:
                            self.get_logger().debug(f"Skipping processing - state: {self.current_state}")
                        continue
                    
                    # Enhanced speech detection
                    if self.channels == 6:
                        mono_audio = chunk[1::self.channels].tobytes()
                    else:
                        mono_audio = chunk[0::self.channels].tobytes()
                    
                    # Use enhanced speech detection
                    is_speech = self.is_speech_detected(mono_audio, chunk)
                    self.voice_history.append(is_speech)
                    
                    if is_speech:
                        speech_count += 1
                        self.speech_detections += 1
                    
                    # Collect chunks for DOA calculation
                    chunks.append(chunk)
                    
                    if len(chunks) == self.doa_chunks:
                        confidence = self.get_voice_confidence()
                        self.current_confidence = confidence
                        current_time = self.get_clock().now()
                        
                        # MATCH STANDALONE: Only use speech count threshold (40%)
                        # Remove the additional confidence threshold check
                        if speech_count > (self.doa_chunks * 0.4):  # 40% of chunks must be voice
                            frames = np.concatenate(chunks)
                            direction = mic.get_direction(frames)
                            
                            if direction is not None:
                                self.direction_calculations += 1
                                
                                # Smooth the direction - remove stable direction filtering
                                smoothed_direction = self.get_smoothed_direction(direction)
                                
                                # Update LEDs with persistence
                                self.update_leds(smoothed_direction)
                                
                                # Report if significant change or timeout
                                direction_changed = (
                                    self.last_direction is None or 
                                    abs(smoothed_direction - self.last_direction) > 15 or
                                    (current_time - self.last_report_time).nanoseconds / 1e9 > self.min_report_interval
                                )
                                
                                if direction_changed:
                                    self.voice_active = True
                                    self.last_direction = smoothed_direction
                                    self.last_report_time = current_time
                                    
                                    self.publish_voice_direction(smoothed_direction, confidence)
                        else:
                            # No voice detected - use LED persistence
                            self.update_leds(None)
                            
                            if self.debug_mode:
                                self.get_logger().debug(
                                    f"Not enough speech: {speech_count}/{self.doa_chunks} chunks "
                                    f"(need {int(self.doa_chunks * 0.4)})"
                                )
                        
                        # Reset for next window
                        speech_count = 0
                        chunks = []
                        
        except Exception as e:
            self.get_logger().error(f'Error in audio processing: {e}')
            import traceback
            traceback.print_exc()
        finally:
            if self.enable_pixel_ring:
                try:
                    pixel_ring.off()
                except:
                    pass
            self.get_logger().info('Audio processing thread stopped')
    
    def start_audio_processing(self):
        """Start the audio processing thread"""
        if not self.running:
            self.running = True
            self.audio_thread = threading.Thread(target=self.audio_processing_thread, daemon=True)
            self.audio_thread.start()
            self.get_logger().info('Audio processing started')
    
    def stop_audio_processing(self):
        """Stop the audio processing thread"""
        if self.running:
            self.running = False
            if self.audio_thread:
                self.audio_thread.join(timeout=2.0)
            self.get_logger().info('Audio processing stopped')
    
    def destroy_node(self):
        """Clean up when node is destroyed"""
        self.get_logger().info('Shutting down Voice Direction Node')
        self.stop_audio_processing()
        
        if self.enable_pixel_ring:
            try:
                pixel_ring.off()
            except:
                pass
        
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = VoiceDirectionNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()