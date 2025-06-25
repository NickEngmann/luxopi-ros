"""
MicArray class for ReSpeaker 4 Mic Array
Calibrated implementation for accurate Direction of Arrival (DOA) detection
"""

import pyaudio
import numpy as np
from gcc_phat import gcc_phat

# Constants for ReSpeaker 4 Mic Array
SOUND_SPEED = 343.2

# Distance between opposite microphones for 4-mic array (in meters)
MIC_DISTANCE_4 = 0.08127
MAX_TDOA_4 = MIC_DISTANCE_4 / float(SOUND_SPEED)


class MicArray:
    """
    Interface for ReSpeaker 4 Mic Array with calibrated DOA detection
    
    Handles:
    - 6 channel audio input (4 mics + 2 reference channels)
    - Direction of Arrival calculation using proven GCC-PHAT algorithm
    - Proper audio device selection and calibration
    """
    
    def __init__(self, rate=16000, channels=6, chunk_size=160, direction_offset=0):
        """
        Initialize microphone array
        
        Parameters:
        -----------
        rate : int
            Sampling rate in Hz
        channels : int
            Number of audio channels (6 for ReSpeaker 4 Mic)
        chunk_size : int
            Number of samples per chunk
        direction_offset : int
            Direction offset for calibration in degrees
        """
        self.rate = rate
        self.channels = channels
        self.chunk_size = int(chunk_size)
        self.direction_offset = direction_offset
        
        # Initialize PyAudio
        self.p = pyaudio.PyAudio()
        self.stream = None
        
        # Speed of sound in m/s
        self.sound_speed = SOUND_SPEED
        
        # Maximum time delay between microphones
        self.max_tau = MAX_TDOA_4
        
    def __enter__(self):
        """Context manager entry"""
        # Find the ReSpeaker device
        device_index = None
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if "ReSpeaker" in info.get('name', '') and info['maxInputChannels'] >= self.channels:
                device_index = i
                break
        
        if device_index is None:
            print("Warning: ReSpeaker device not found, using default input")
            device_index = None
        
        # Open audio stream
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.chunk_size
        )
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        
    def read_chunks(self):
        """
        Generator that yields audio chunks
        
        Yields:
        -------
        chunk : ndarray
            Audio data with shape (chunk_size * channels,)
        """
        while True:
            try:
                # Read raw audio data
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                
                # Convert to numpy array
                chunk = np.frombuffer(data, dtype=np.int16)
                
                yield chunk
                
            except Exception as e:
                print(f"Audio read error: {e}")
                break
                
    def get_direction(self, frames):
        """
        Calculate direction of arrival from audio frames using the proven ReSpeaker algorithm
        
        Parameters:
        -----------
        frames : ndarray
            Multi-channel audio data
            
        Returns:
        --------
        direction : float
            Estimated direction in degrees (0-360)
        """
        # Check if signal is strong enough
        if np.max(np.abs(frames)) < 100:
            return None  # Signal too weak
        
        if self.channels == 6:
            # Use the 4 raw microphones (channels 1-4 in the 6-channel stream)
            # Create a 4-channel buffer from the 6-channel input
            buf_4ch = np.zeros(len(frames) // 6 * 4, dtype=frames.dtype)
            for i in range(4):
                buf_4ch[i::4] = frames[(i+1)::6]  # Extract channels 1-4
            
            # Use the proven 4-mic algorithm with proper calibration
            MIC_GROUP = [[0, 2], [1, 3]]  # Front-Back and Left-Right pairs
            
            tau = [0] * 2
            theta = [0] * 2
            
            # Calculate time delays for each microphone pair
            for i, mic_pair in enumerate(MIC_GROUP):
                tau[i], _ = gcc_phat(
                    buf_4ch[mic_pair[0]::4], 
                    buf_4ch[mic_pair[1]::4], 
                    fs=self.rate, 
                    max_tau=self.max_tau, 
                    interp=1
                )
                # Convert time delay to angle
                theta[i] = np.arcsin(np.clip(tau[i] / self.max_tau, -1, 1)) * 180 / np.pi
            
            # Determine the best direction estimate using the proven algorithm
            if np.abs(theta[0]) < np.abs(theta[1]):
                if theta[1] > 0:
                    best_guess = (theta[0] + 360) % 360
                else:
                    best_guess = (180 - theta[0])
            else:
                if theta[0] < 0:
                    best_guess = (theta[1] + 360) % 360
                else:
                    best_guess = (180 - theta[1])
                best_guess = (best_guess + 90 + 180) % 360
            
            # Apply the calibration offset for ReSpeaker 4 Mic Array
            best_guess = (-best_guess + 120) % 360
            
            # Invert direction to fix left/right movement issue
            best_guess = (360 - best_guess) % 360
            
            # Apply user-configurable direction offset
            best_guess = (best_guess + self.direction_offset) % 360
            
            return best_guess
        
        elif self.channels == 4:
            # Direct 4-channel processing
            MIC_GROUP = [[0, 2], [1, 3]]  # Front-Back and Left-Right pairs
            
            tau = [0] * 2
            theta = [0] * 2
            
            # Calculate time delays for each microphone pair
            for i, mic_pair in enumerate(MIC_GROUP):
                tau[i], _ = gcc_phat(
                    frames[mic_pair[0]::4], 
                    frames[mic_pair[1]::4], 
                    fs=self.rate, 
                    max_tau=self.max_tau, 
                    interp=1
                )
                # Convert time delay to angle
                theta[i] = np.arcsin(np.clip(tau[i] / self.max_tau, -1, 1)) * 180 / np.pi
            
            # Determine the best direction estimate
            if np.abs(theta[0]) < np.abs(theta[1]):
                if theta[1] > 0:
                    best_guess = (theta[0] + 360) % 360
                else:
                    best_guess = (180 - theta[0])
            else:
                if theta[0] < 0:
                    best_guess = (theta[1] + 360) % 360
                else:
                    best_guess = (180 - theta[1])
                best_guess = (best_guess + 90 + 180) % 360
            
            # Apply the calibration offset
            best_guess = (-best_guess + 120) % 360
            
            # Invert direction to fix left/right movement issue
            best_guess = (360 - best_guess) % 360
            
            # Apply user-configurable direction offset
            best_guess = (best_guess + self.direction_offset) % 360
            
            return best_guess
        
        else:
            # Unsupported number of channels
            return None


if __name__ == '__main__':
    """Test the microphone array"""
    import time
    
    with MicArray() as mic:
        print("Recording... Press Ctrl+C to stop")
        
        chunk_count = 0
        for chunk in mic.read_chunks():
            chunk_count += 1
            
            # Every second, calculate direction on accumulated data
            if chunk_count * mic.chunk_size >= mic.rate:
                print(f"Recorded {chunk_count} chunks")
                chunk_count = 0