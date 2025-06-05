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

class VoiceDirectionDetector:
    """Main class for detecting voice direction"""
    
    def __init__(self, rate=16000, channels=4, vad_frames=10, doa_frames=200, 
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
        
        # History for smoothing
        self.direction_history = deque(maxlen=5)
        self.voice_history = deque(maxlen=10)
        
        print("[OK] Voice Direction Detector initialized")
        print(f"    Sample rate: {rate} Hz")
        print(f"    Channels: {channels}")
        print(f"    VAD frame: {vad_frames} ms")
        print(f"    DOA window: {doa_frames} ms")
        
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
                    # Use single channel audio for VAD (channel 0)
                    mono_audio = chunk[0::self.channels].tobytes()
                    
                    # Check if speech is detected
                    is_speech = self.vad.is_speech(mono_audio, self.rate)
                    self.voice_history.append(is_speech)
                    
                    if is_speech:
                        speech_count += 1
                        if debug:
                            sys.stdout.write('1')
                    else:
                        if debug:
                            sys.stdout.write('0')
                    
                    if debug:
                        sys.stdout.flush()
                    
                    # Collect chunks for DOA calculation
                    chunks.append(chunk)
                    
                    if len(chunks) == self.doa_chunks:
                        confidence = self.get_voice_confidence()
                        current_time = time.time()
                        
                        # If enough speech was detected
                        if speech_count > (self.doa_chunks / 2):
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
                                    
                                    if not debug:
                                        print(f"\r[VOICE] Detected at {smoothed_direction:3d}° {compass} "
                                              f"(confidence: {confidence:.0%})    ", end='', flush=True)
                                    else:
                                        print(f"\n[VOICE] Direction: {smoothed_direction:3d}° {compass} "
                                              f"(confidence: {confidence:.0%})")
                                    
                                    if callback:
                                        callback(smoothed_direction, confidence)
                                    
                                    last_direction = smoothed_direction
                                    last_report_time = current_time
                        else:
                            # No voice detected
                            if not debug:
                                print(f"\r[IDLE] No voice detected (confidence: {confidence:.0%})    ", 
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
        # Define compass directions
        directions = [
            (0, "N"), (45, "NE"), (90, "E"), (135, "SE"),
            (180, "S"), (225, "SW"), (270, "W"), (315, "NW")
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
        
        # Create arrow visual
        arrow = "→"
        if 337.5 <= angle or angle < 22.5:
            arrow = "↑"
        elif 22.5 <= angle < 67.5:
            arrow = "↗"
        elif 67.5 <= angle < 112.5:
            arrow = "→"
        elif 112.5 <= angle < 157.5:
            arrow = "↘"
        elif 157.5 <= angle < 202.5:
            arrow = "↓"
        elif 202.5 <= angle < 247.5:
            arrow = "↙"
        elif 247.5 <= angle < 292.5:
            arrow = "←"
        elif 292.5 <= angle < 337.5:
            arrow = "↖"
        
        return f"{arrow} {closest_dir}"


def example_callback(direction, confidence):
    """Example callback function for voice direction events"""
    timestamp = time.strftime("%H:%M:%S")
    # This will print on a new line when called
    print(f"\n[{timestamp}] Voice Event - Direction: {direction}° (confidence: {confidence:.0%})")


def test_dependencies():
    """Test that all required dependencies are available"""
    print("[TEST] Checking dependencies...")
    
    try:
        import pyaudio
        print("[OK] PyAudio is installed")
    except ImportError:
        print("[ERROR] PyAudio is not installed. Run: pip install pyaudio")
        return False
    
    try:
        import webrtcvad
        print("[OK] webrtcvad is installed")
    except ImportError:
        print("[ERROR] webrtcvad is not installed. Run: pip install webrtcvad")
        return False
    
    try:
        from gcc_phat import gcc_phat
        print("[OK] gcc_phat is available")
    except ImportError:
        print("[ERROR] gcc_phat.py is not found in the current directory")
        return False
    
    return True


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
    parser.add_argument('--vad-frames', type=int, default=10,
                        help='VAD frame duration in ms (default: 10)')
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
    parser.add_argument('--test', action='store_true',
                        help='Test dependencies only')
    
    args = parser.parse_args()
    
    try:
        if args.test:
            # Just test dependencies
            test_dependencies()
        else:
            # Check dependencies first
            if not test_dependencies():
                print("\n[ERROR] Missing dependencies. Please install them and try again.")
                sys.exit(1)
            
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
        print("\nPlease make sure:")
        print("1. ReSpeaker Mic Array v2.0 is connected")
        print("2. You have proper permissions (try running with sudo)")
        print("3. Required files are in the current directory:")
        print("   - mic_array.py")
        print("   - pixel_ring.py")
        print("   - gcc_phat.py")
        print("4. Required dependencies are installed:")
        print("   pip install pyaudio webrtcvad numpy")
        sys.exit(1)


if __name__ == "__main__":
    main()