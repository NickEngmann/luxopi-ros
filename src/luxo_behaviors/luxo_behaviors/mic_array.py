"""
MicArray class for ReSpeaker 4 Mic Array
Calibrated implementation for accurate Direction of Arrival (DOA) detection
"""

import numpy as np
from .direction_estimation import estimate_direction, SOUND_SPEED, MIC_DISTANCE_4, MAX_TDOA_4



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
        
        # Keep offline estimation importable without a microphone runtime.
        import pyaudio
        self._pyaudio = pyaudio
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
            format=self._pyaudio.paInt16,
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
        return estimate_direction(frames, rate=self.rate, channels=self.channels,
                                  direction_offset=self.direction_offset)


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