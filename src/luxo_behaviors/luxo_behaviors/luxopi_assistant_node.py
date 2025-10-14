#!/usr/bin/env python3
"""
🤖 LUXOPI AI VOICE ASSISTANT - ROS2 NODE
Ultra-fast real-time voice assistant using Whisper + Qwen
Achieves <1 second response time with warm models

Converted from standalone luxopi_assistant.py to ROS2 integration
"""

import subprocess
import time
import requests
import json
import sys
import os
import psutil
import gc  # For garbage collection
import re  # For regex filtering
from datetime import datetime
from difflib import SequenceMatcher  # For text similarity comparison
from pathlib import Path
import tempfile
import threading
import random

# ROS2 imports
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool

# Unified Command Behavior (handles both voice assistant and robot hardware commands)
from luxo_behaviors.command_behavior import CommandBehavior


def text_similarity(text1, text2):
    """Calculate similarity ratio between two texts (0.0 to 1.0)"""
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


class VoiceTransformer:
    """Applies sox-based transformations to voice output"""

    def __init__(self, preset_path=None):
        self.preset_path = preset_path
        self.preset_data = None
        self.temp_dir = Path(tempfile.gettempdir()) / "luxopi_voice"
        self.temp_dir.mkdir(exist_ok=True)

        if preset_path:
            self.load_preset(preset_path)

    def load_preset(self, preset_path):
        """Load a preset JSON file"""
        try:
            with open(preset_path, 'r') as f:
                self.preset_data = json.load(f)
            print(f"✅ Loaded preset: {self.preset_data.get('preset_name', 'Unknown')}")
            return True
        except Exception as e:
            print(f"⚠️  Failed to load preset: {e}")
            return False

    def apply_circuit_talk(self, input_file, output_file, intensity=300):
        """Apply circuit_talk transformation (R2D2-like beeping)"""
        factor = intensity / 100.0
        pitch_shift = min(1000, int(450 * factor))
        tremolo_freq = min(80, int(35 * factor))
        bp_center = min(2500, int(1000 * factor))
        od = min(45, int(18 * factor))
        gain_val = max(-10, int(-4 * factor))

        subprocess.run([
            "sox", str(input_file), str(output_file),
            "pitch", str(pitch_shift),
            "bandpass", str(bp_center), "450",
            "tremolo", str(tremolo_freq), "0.85",
            "overdrive", str(od),
            "echo", "0.06", "0.8", "4", "0.5",
            "highpass", str(min(1800, int(900 * factor))),
            "gain", str(gain_val)
        ], capture_output=True, check=True)

    def apply_beep_speak(self, input_file, output_file, intensity=220):
        """Apply beep_speak transformation"""
        factor = intensity / 100.0
        pitch_shift = min(1000, int(500 * factor))
        bp_center = min(3000, int(1000 * factor))
        tremolo_freq = min(100, int(40 * factor))
        od = min(50, int(15 * factor))
        gain_val = max(-10, int(-4 * factor))

        subprocess.run([
            "sox", str(input_file), str(output_file),
            "pitch", str(pitch_shift),
            "bandpass", str(bp_center), "400",
            "tremolo", str(tremolo_freq), "0.9",
            "overdrive", str(od),
            "highpass", str(min(2500, int(1200 * factor))),
            "gain", str(gain_val)
        ], capture_output=True, check=True)

    def apply_transformation(self, input_file, output_file, layer_type, intensity=200):
        """Apply a specific transformation by type"""
        if layer_type == 'circuit_talk':
            self.apply_circuit_talk(input_file, output_file, intensity)
        elif layer_type == 'beep_speak':
            self.apply_beep_speak(input_file, output_file, intensity)
        else:
            # If unknown, just copy the file
            subprocess.run(["cp", str(input_file), str(output_file)], check=True)

    def transform_from_preset(self, input_audio_path, verbose=False):
        """Apply transformations from loaded preset and return final audio path"""
        if not self.preset_data:
            return input_audio_path

        layers = self.preset_data.get('layers', [])
        if not layers:
            return input_audio_path

        try:
            # Create transformed layers
            layer_files = []

            for i, layer in enumerate(layers):
                # Skip muted layers or layers with zero mix
                if layer.get('muted', False) or layer.get('mix', 0) == 0:
                    if verbose:
                        print(f"      ⏭️  Skipping muted/zero layer: {layer.get('name', 'Unknown')}")
                    continue

                layer_name = layer.get('name', '')
                mix_level = layer.get('mix', 1.0)

                # Extract transformation type from layer name
                # e.g., "Circuit Talk (300%)" -> circuit_talk, 300
                if '(' in layer_name and '%' in layer_name:
                    base_name = layer_name.split('(')[0].strip().lower().replace(' ', '_')
                    intensity_str = layer_name.split('(')[1].split('%')[0]
                    try:
                        intensity = int(intensity_str)
                    except:
                        intensity = 200
                    is_transformation = True
                else:
                    # Base voice or processed voice - just use input
                    base_name = 'base'
                    intensity = 100
                    is_transformation = False

                # Generate layer file
                layer_file = self.temp_dir / f"layer_{i}.wav"

                if not is_transformation:
                    # Just copy the input (base voice, processed voice, etc.)
                    if verbose:
                        print(f"      📄 Layer {i}: {layer_name} (base, mix: {mix_level})")
                    subprocess.run(["cp", str(input_audio_path), str(layer_file)], check=True)
                else:
                    # Apply transformation
                    if verbose:
                        print(f"      🎨 Layer {i}: Applying {base_name} at {intensity}% (mix: {mix_level})")
                    self.apply_transformation(input_audio_path, layer_file, base_name, intensity)

                layer_files.append((layer_file, mix_level))

            if not layer_files:
                return input_audio_path

            # Mix all layers together
            output_file = self.temp_dir / "final_transformed.wav"
            cmd = ["sox", "-m"]
            for layer_file, mix_level in layer_files:
                cmd.extend(["-v", str(mix_level), str(layer_file)])
            cmd.append(str(output_file))

            if verbose:
                print(f"      🎚️  Mixing {len(layer_files)} layers...")

            subprocess.run(cmd, capture_output=True, check=True)

            return output_file

        except Exception as e:
            print(f"⚠️  Transformation error: {e}")
            return input_audio_path


class LuxopiAssistantNode(Node, CommandBehavior):
    """ROS2 node for Luxopi voice assistant"""

    def __init__(self):
        super().__init__('luxopi_assistant_node')
        # Note: self.node will be set to self for the mixin pattern
        self.node = self

        # CRITICAL: Wait for voice_direction_node to initialize loopback
        self.get_logger().info("⏳ Waiting 5 seconds for audio loopback to be ready...")
        time.sleep(5.0)
        self.get_logger().info("✅ Starting voice assistant initialization")

        # Declare ROS parameters with defaults
        self.declare_parameter('use_hailo', True)  # Hailo is DEFAULT mode
        self.declare_parameter('verbose', False)
        self.declare_parameter('voice_preset', '/home/pi/luxopi-ai/audio_experiments_web/preset_alpha-high-pitch.json')
        self.declare_parameter('whisper_step_ms', 1000)

        # Get parameters
        use_hailo = self.get_parameter('use_hailo').value
        verbose = self.get_parameter('verbose').value
        voice_preset = self.get_parameter('voice_preset').value
        whisper_step_ms = self.get_parameter('whisper_step_ms').value

        # Paths - using system-wide commands now
        self.use_hailo = use_hailo
        self.voice_transformer = VoiceTransformer(voice_preset) if voice_preset and os.path.exists(voice_preset) else None

        if use_hailo:
            self.whisper_stream = "/home/pi/luxopi-ai/hailo-speech-recognition/speech_recognition/hailo-whisper-stream"
        else:
            self.whisper_stream = "whisper-stream"  # Available in PATH via symlink

        self.whisper_model = "/home/pi/luxopi-ai/whisper.cpp/models/ggml-base.en.bin"
        self.llama_server = "llama-server"  # Available in PATH via symlink
        self.llm_model = "/home/pi/luxopi-ai/models/qwen3-0.6b-q4_0.gguf"

        self.goal_time = 2.0  # Target end-to-end time in seconds

        # Auto-detect USB audio output device
        self.speaker_device = self._detect_usb_speaker()

        # Initialize unified command behavior mixin (handles ALL commands - voice assistant AND robot hardware)
        self.setup_command_behavior(verbose=verbose)

        # Server settings
        self.server_port = 8081
        self.server_url = f"http://127.0.0.1:{self.server_port}"

        # Whisper settings
        self.whisper_step_ms = whisper_step_ms  # Process every N milliseconds (1 second chunks)

        # Audio buffer for accumulating speech
        self.audio_buffer = []
        self.last_speech_time = None
        self.first_speech_time = None
        self.first_stt_timestamp = None  # Track when first STT was received
        self.accumulated_speech_time = 0.0  # Track actual speech time (not silence)
        self.last_word_count = 0  # Track word count for stabilization detection
        self.word_count_stable_iterations = 0  # Count how many times word count stayed the same
        self.silence_threshold = 0.5  # Optimized: Detect silence after 0.5s (was 0.8s)
        self.max_speech_duration = 10.0  # Max speech length in seconds for context
        self.last_stt_time = 0.8  # Track actual STT time from hailo-whisper debug output (default fallback)
        self.stt_start_time = None  # Track when STT processing started (from marker)
        self.similarity_threshold = 0.75  # If last 2 transcriptions are 75%+ similar, consider it final
        self.word_count_stability_threshold = 3  # Number of identical word counts before processing
        self.is_speaking = False  # Track if we're currently playing TTS

        # Filler TTS (enabled by default in ROS architecture, fills gap during LLM processing)
        self.enable_filler = True  # Always enabled in ROS mode
        self.filler_active = threading.Event()  # Signal to stop filler
        self.filler_thread = None  # Background thread for filler messages
        self.filler_messages = [
            # Generic thinking sounds
            "Hmm",
            "Let me think",
            "One moment",
            "Thinking",
            "Let's see",
            "Hold on",
            "Give me a sec",
            "Just a moment",
            "Processing",
            "Right",
            # Lamp puns (because Luxopi is a robot lamp!)
            "Brightening up",
            "Illuminating",
            "Shedding light",
            "Bulb's warming up",
            "Charging up"
        ]

        # Verbose timing mode
        self.verbose = verbose
        self.max_events_history = 100  # Keep last 100 events in memory
        self.recent_events = []  # Circular buffer for recent events

        # Processes
        self.llm_server_proc = None
        self.whisper_proc = None

        # State
        self.running = True
        self.response_count = 0

        # Performance tracking
        self.metrics = {
            'start_time': time.time(),
            'queries': 0,
            'total_stt_time': 0,
            'total_llm_time': 0,
            'total_tts_time': 0,
            'fastest_response': float('inf'),
            'slowest_response': 0,
            'fastest_llm': float('inf'),
            'slowest_llm': 0,
            'llm_response_times': [],  # Track all LLM response times for analysis
            'filtered_noise': 0,
            'filtered_short': 0,
            'filtered_no_content': 0,
            'total_detections': 0
        }

        # ROS Publishers
        self.transcription_pub = self.create_publisher(String, '/voice/transcription', 10)
        self.llm_response_pub = self.create_publisher(String, '/voice/llm_response', 10)
        self.tts_active_pub = self.create_publisher(Bool, '/voice/tts_active', 10)

        # ROS Subscribers
        self.sleep_mode_sub = self.create_subscription(
            Bool,
            '/luxo/sleep_mode',
            self.sleep_mode_callback,
            10
        )

        # Sleep mode state
        self.is_sleep_mode = False
        self.saved_amplitude = None

        self.get_logger().info("✅ ROS publishers and subscribers created")
        self.get_logger().info(f"🔧 Hailo mode: {use_hailo}")
        self.get_logger().info(f"🔧 Voice preset: {voice_preset if voice_preset else 'None'}")
        self.get_logger().info(f"🔧 Whisper step: {whisper_step_ms}ms")

    def _detect_usb_speaker(self):
        """Auto-detect USB audio output device (not ReSpeaker)"""
        try:
            result = subprocess.run(
                ["aplay", "-l"],
                capture_output=True,
                text=True,
                timeout=2
            )

            # Parse aplay output to find USB device that's NOT ReSpeaker
            for line in result.stdout.split('\n'):
                if line.startswith('card '):
                    # Extract card number
                    card_num = line.split(':')[0].split()[1]
                    # Look for USB device that's not ReSpeaker (ReSpeaker is input only)
                    if 'USB' in line and 'ReSpeaker' not in line:
                        device = f"plughw:{card_num},0"
                        self.get_logger().info(f"🔊 Detected USB speaker: {device}")
                        return device

            # Fallback to default
            self.get_logger().warn("⚠️  No USB speaker detected, using default audio output")
            return "default"

        except Exception as e:
            self.get_logger().warn(f"⚠️  Error detecting audio device: {e}, using default")
            return "default"

    def print_banner(self):
        """Print startup banner"""
        self.get_logger().info("\n" + "="*60)
        self.get_logger().info("  🤖 LUXOPI AI VOICE ASSISTANT (ROS2 Node)")
        self.get_logger().info("  Ultra-fast STT → LLM Pipeline")
        self.get_logger().info("="*60)
        self.get_logger().info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.get_logger().info(f"  Target latency: < {self.goal_time} second")
        self.get_logger().info("="*60)

    def start_llm_server(self):
        """Start the LLM server in background"""
        self.get_logger().info("🚀 Starting LLM server...")

        # Kill any existing server
        subprocess.run(["pkill", "-f", "llama-server"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)

        # Start new server with optimized settings from benchmark
        cmd = [
            self.llama_server,
            "-m", self.llm_model,
            "--ctx-size", "512",     # Increased from 256 for better context
            "--threads", "4",        # 4 threads for balance
            "--port", str(self.server_port),
            "--host", "127.0.0.1",
            "-n", "50",              # Optimized response length
            "--batch-size", "512",   # Standard batch
            "--no-mmap",            # Keep model in RAM
            "--reasoning-budget", "0"  # DISABLE thinking output!
        ]

        self.get_logger().info(f"  Running: {' '.join(cmd)}")
        self.llm_server_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Simple approach: wait 10 seconds, then check health
        for attempt in range(3):
            self.get_logger().info(f"  Waiting 10 seconds for model to load (attempt {attempt + 1}/3)...")
            time.sleep(10)

            try:
                # Check if server is healthy
                response = requests.get(f"{self.server_url}/health", timeout=2)
                if response.status_code == 200:
                    self.get_logger().info("  ✅ Server is healthy! Warming up with test query...")
                    # Warm up with test query
                    warmup = {
                        "prompt": "Hello",
                        "n_predict": 5,
                        "temperature": 0.1
                    }
                    requests.post(f"{self.server_url}/completion",
                                json=warmup, timeout=10)
                    self.get_logger().info("✅ LLM server ready!")
                    return True
                else:
                    self.get_logger().error(f"  ❌ Health check returned {response.status_code}")
            except Exception as e:
                self.get_logger().error(f"  ❌ Health check failed: {str(e)[:50]}")

            # Check if process crashed
            if self.llm_server_proc.poll() is not None:
                self.get_logger().error(f"  ⚠️ Server process exited with code: {self.llm_server_proc.poll()}")
                return False

        self.get_logger().error("❌ Failed to start LLM server after 3 attempts")
        return False

    def set_speaker_volume(self, volume=0.5):
        """Set USB speaker volume to safe level (0.0-1.0)"""
        try:
            # Convert 0-1 to 0-100 percentage
            volume_percent = int(volume * 100)

            # Extract card number from speaker_device (e.g., "plughw:3,0" -> "3")
            card_num = None
            if ":" in self.speaker_device:
                parts = self.speaker_device.split(":")
                if len(parts) > 1:
                    card_num = parts[1].split(",")[0]

            # Try to set volume with card specification
            controls_to_try = ["PCM", "Speaker", "Master", "Headphone"]

            for control in controls_to_try:
                # Try with card number if we have it
                if card_num:
                    cmd = ["amixer", "-c", card_num, "set", control, f"{volume_percent}%"]
                else:
                    cmd = ["amixer", "set", control, f"{volume_percent}%"]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=2
                )

                if result.returncode == 0:
                    self.get_logger().info(f"  ✅ Set {control} volume to {volume_percent}% on card {card_num if card_num else 'default'}")
                    return

            # If all failed, show what we tried
            self.get_logger().warn(f"  ⚠️  Could not set volume. Tried: {', '.join(controls_to_try)}")

        except Exception as e:
            self.get_logger().warn(f"  ⚠️ Could not set volume: {e}")

    def sleep_mode_callback(self, msg):
        """Handle sleep/wake mode for volume control."""
        try:
            if msg.data and not self.is_sleep_mode:
                # Going to sleep - save current amplitude and mute
                self.saved_amplitude = self.amplitude
                self.amplitude = 0
                self.is_sleep_mode = True
                self.get_logger().info(f"💤 Sleep mode: Volume muted (saved: {self.saved_amplitude})")
            elif not msg.data and self.is_sleep_mode:
                # Waking up - restore amplitude BEFORE responding
                if self.saved_amplitude is not None:
                    self.amplitude = self.saved_amplitude
                    self.get_logger().info(f"🌅 Wake mode: Volume restored to {self.amplitude}")
                    self.saved_amplitude = None
                else:
                    # Fallback to default if no saved value
                    self.amplitude = 100
                    self.get_logger().info(f"🌅 Wake mode: Volume restored to default {self.amplitude}")
                self.is_sleep_mode = False
        except Exception as e:
            self.get_logger().error(f"Error in sleep mode callback: {e}")

    def speak(self, text):
        """Speak text using espeak-ng with optional voice transformation"""
        if not text or self.is_speaking:
            return 0

        # Block TTS during sleep mode
        if self.is_sleep_mode:
            self.get_logger().info("💤 Sleep mode active - skipping TTS (robot is muted)")
            return 0

        tts_time = 0
        temp_files = []
        try:
            self.is_speaking = True

            # BOTH modes need to pause to prevent feedback loop
            # Stop Whisper stream (CPU or Hailo) to prevent it from hearing itself
            pause_start = time.time()
            self.pause_whisper()
            pause_time = time.time() - pause_start
            if self.verbose:
                self.get_logger().info(f"    ⏸️  Paused Whisper in {pause_time:.3f}s")

            # espeak-ng parameters from preset or behavior settings
            if self.voice_transformer and self.voice_transformer.preset_data:
                preset_params = self.voice_transformer.preset_data.get('params', {})
                voice = self.voice_transformer.preset_data.get('voice', 'en+m2')
                speed = str(preset_params.get('speed', self.speed))
                pitch = str(preset_params.get('pitch', self.pitch))
                amplitude = str(preset_params.get('amplitude', self.amplitude))
                word_gap = str(preset_params.get('word_gap', 10))
                capitals = str(preset_params.get('capitals', 100))
            else:
                # Use behavior settings
                voice = "en+m2"
                speed = str(self.speed)
                pitch = str(self.pitch)
                amplitude = str(self.amplitude)
                word_gap = "10"
                capitals = "100"

            # Generate to temp file if using transformations, otherwise play directly
            if self.voice_transformer:
                # Generate espeak output to temp file
                temp_raw = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                temp_files.append(temp_raw.name)

                cmd = [
                    "espeak-ng",
                    "-v", voice,
                    "-s", speed,
                    "-p", pitch,
                    "-a", amplitude,
                    "-g", word_gap,
                    "-k", capitals,
                    "-w", temp_raw.name,
                    text
                ]

                # Time espeak generation
                espeak_start = time.time()
                subprocess.run(cmd, capture_output=True, timeout=10, check=True)
                espeak_time = time.time() - espeak_start

                if self.verbose:
                    self.get_logger().info(f"    🎙️  espeak generation: {espeak_time:.3f}s")

                # Apply transformations (sox commands)
                transform_start = time.time()
                transformed_file = self.voice_transformer.transform_from_preset(temp_raw.name, verbose=self.verbose)
                if transformed_file != temp_raw.name:
                    temp_files.append(str(transformed_file))
                transform_time = time.time() - transform_start

                if self.verbose:
                    self.get_logger().info(f"    🎨 sox transformations: {transform_time:.3f}s")

                # Play transformed audio using aplay with USB speaker device
                play_start = time.time()
                play_cmd = ["aplay", "-q", "-D", self.speaker_device, str(transformed_file)]
                subprocess.run(play_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                play_time = time.time() - play_start

                if self.verbose:
                    self.get_logger().info(f"    🔊 aplay playback: {play_time:.3f}s")

                # Total TTS time includes all steps
                tts_time = espeak_time + transform_time + play_time

                if self.verbose:
                    self.get_logger().info(f"    ✅ Total audio generation: {tts_time:.3f}s for {len(text.split())} words")

            else:
                # No transformation - play directly
                cmd = [
                    "espeak-ng",
                    "-v", voice,
                    "-s", speed,
                    "-p", pitch,
                    "-a", amplitude,
                    "-g", word_gap,
                    "-k", capitals,
                    "-d", self.speaker_device,
                    text
                ]

                start = time.time()
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10
                )
                tts_time = time.time() - start

                if self.verbose:
                    self.get_logger().info(f"    🎧 espeak direct playback: {tts_time:.3f}s for {len(text.split())} words")

        except Exception as e:
            self.get_logger().info(f"  ⚠️ TTS error: {e}")
        finally:
            # Clean up temp files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass

            # BOTH modes need to resume after TTS
            # IMPORTANT: Resume Whisper BEFORE clearing is_speaking flag
            # This ensures we don't start buffering audio from our own voice
            resume_start = time.time()
            self.resume_whisper()
            resume_time = time.time() - resume_start

            if self.verbose:
                self.get_logger().info(f"    ▶️  Resumed Whisper in {resume_time:.3f}s")

            # Now it's safe to clear the speaking flag
            self.is_speaking = False

        return tts_time

    def _generate_and_play_tts(self, text, is_filler=False):
        """Generate and play TTS without blocking whisper (for filler messages)

        This is a simplified version of speak() that doesn't pause/resume whisper.
        Used for filler messages that play DURING processing.
        """
        if not text or self.is_sleep_mode:
            return

        temp_files = []
        try:
            # espeak-ng parameters from preset or behavior settings
            if self.voice_transformer and self.voice_transformer.preset_data:
                preset_params = self.voice_transformer.preset_data.get('params', {})
                voice = self.voice_transformer.preset_data.get('voice', 'en+m2')
                speed = str(preset_params.get('speed', self.speed))
                pitch = str(preset_params.get('pitch', self.pitch))
                amplitude = str(preset_params.get('amplitude', self.amplitude))
                word_gap = str(preset_params.get('word_gap', 10))
                capitals = str(preset_params.get('capitals', 100))
            else:
                # Use behavior settings
                voice = "en+m2"
                speed = str(self.speed)
                pitch = str(self.pitch)
                amplitude = str(self.amplitude)
                word_gap = "10"
                capitals = "100"

            # Generate to temp file if using transformations, otherwise play directly
            if self.voice_transformer:
                # Generate espeak output to temp file
                temp_raw = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                temp_files.append(temp_raw.name)

                cmd = [
                    "espeak-ng",
                    "-v", voice,
                    "-s", speed,
                    "-p", pitch,
                    "-a", amplitude,
                    "-g", word_gap,
                    "-k", capitals,
                    "-w", temp_raw.name,
                    text
                ]

                subprocess.run(cmd, capture_output=True, timeout=10, check=True)

                # Apply transformations (sox commands)
                transformed_file = self.voice_transformer.transform_from_preset(temp_raw.name, verbose=False)
                if transformed_file != temp_raw.name:
                    temp_files.append(str(transformed_file))

                # Play transformed audio using aplay with USB speaker device
                play_cmd = ["aplay", "-q", "-D", self.speaker_device, str(transformed_file)]
                subprocess.run(play_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            else:
                # No transformation - play directly
                cmd = [
                    "espeak-ng",
                    "-v", voice,
                    "-s", speed,
                    "-p", pitch,
                    "-a", amplitude,
                    "-g", word_gap,
                    "-k", capitals,
                    "-d", self.speaker_device,
                    text
                ]

                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10
                )

        except Exception as e:
            if self.verbose:
                self.get_logger().info(f"  ⚠️ Filler TTS error: {e}")
        finally:
            # Clean up temp files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass

    def play_filler_messages(self):
        """Background thread that plays random filler messages in a loop"""
        while not self.filler_active.is_set():
            # Pick a random filler message
            message = random.choice(self.filler_messages)

            # Play it (non-blocking)
            self._generate_and_play_tts(message, is_filler=True)

            # Small delay between messages (0.3-0.8 seconds)
            delay = random.uniform(0.3, 0.8)
            if self.filler_active.wait(timeout=delay):
                # Event was set (stop signal), exit loop
                break

    def start_filler_tts(self):
        """Start playing filler messages in background thread"""
        if self.enable_filler and not self.filler_thread:
            self.filler_active.clear()  # Clear stop signal
            self.filler_thread = threading.Thread(target=self.play_filler_messages, daemon=True)
            self.filler_thread.start()

            if self.verbose:
                self.get_logger().info("  💬 Started filler TTS (thinking sounds)")

    def stop_filler_tts(self):
        """Stop filler messages and wait for thread to finish"""
        if self.filler_thread:
            self.filler_active.set()  # Signal thread to stop
            self.filler_thread.join(timeout=2)  # Wait up to 2 seconds
            self.filler_thread = None

            if self.verbose:
                self.get_logger().info("  🛑 Stopped filler TTS")

    def query_llm(self, text):
        """Query the LLM server"""
        try:
            # Optimized prompt from benchmark: "Character Constraint" winner
            # Achieves 1.09s avg, 14.6 words, 7.5/10 quality
            # Added /nothink and /no_think flags for faster responses
            prompt = f"/nothink /no_think You're Luxo, a helpful robot. Respond in ONE sentence. Never use placeholder text like [Your response]. Always give a real, direct response.\nUser: {text}\nLuxo:"

            payload = {
                "prompt": prompt,
                "n_predict": 30,  # Reduced for shorter responses (from benchmark)
                "temperature": 0.7,  # Balanced creativity/determinism
                "top_k": 40,  # Optimized from benchmark
                "top_p": 0.9,  # Optimized from benchmark
                "stop": ["</think>", "\n\n", "User:", "<|endoftext|>", "Luxo:"],
                "cache_prompt": True,
                "thread_count": 3,  # Use 3 threads
                "repeat_penalty": 1.3,  # Strong repeat penalty from benchmark
                "stream": False
            }

            start = time.time()
            response = requests.post(
                f"{self.server_url}/completion",
                json=payload,
                timeout=5
            )
            llm_time = time.time() - start

            if response.status_code == 200:
                result = response.json()
                answer = result.get("content", "").strip()

                # Clean up response - remove thinking tags and extra lines
                answer = answer.replace("<think>", "").replace("</think>", "")
                answer = answer.split("\n")[0].strip()

                # Remove common formatting artifacts
                answer = answer.strip('*').strip('"').strip("'")

                # Clean parentheticals (e.g., "(smiling)", "(laughing)")
                answer = self.clean_parentheticals(answer)

                # Check if response is a placeholder
                if self.is_placeholder_response(answer):
                    fallback = self.get_random_fallback()
                    if self.verbose:
                        self.get_logger().info(f"  ⚠️  Placeholder detected: '{answer}' → using fallback: '{fallback}'")
                    return fallback, llm_time

                # If empty after cleaning, return default
                if not answer or len(answer) < 2:
                    return "Hmm, not sure.", 0

                return answer, llm_time

        except Exception as e:
            self.get_logger().info(f"  ⚠️ LLM error: {e}")

        return "Sorry, didn't get that.", 0


    def pause_whisper(self):
        """Temporarily stop Whisper stream to prevent feedback during TTS"""
        if self.whisper_proc:
            try:
                # Send SIGTERM and wait for clean shutdown
                self.whisper_proc.terminate()
                try:
                    self.whisper_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate cleanly
                    self.whisper_proc.kill()
                    self.whisper_proc.wait(timeout=1)
            except Exception as e:
                if self.verbose:
                    self.get_logger().info(f"    ⚠️ Error pausing Whisper: {e}")
            finally:
                self.whisper_proc = None

    def resume_whisper(self):
        """Restart Whisper stream after TTS completes"""
        if not self.whisper_proc and self.running:
            # Give the audio device time to settle after TTS
            time.sleep(0.3)

            # Build command based on backend (same logic as run_whisper_streaming)
            if self.use_hailo:
                # Hailo backend - using launcher script
                cmd = [
                    self.whisper_stream,
                    "--step", str(self.whisper_step_ms),
                    "--silence-threshold", str(self.silence_threshold),
                    "--max-speech-duration", str(self.max_speech_duration),
                    "--variant", "base"  # Using base variant for quality
                ]
            else:
                # Whisper stream command balanced for speed and CPU
                cmd = [
                    self.whisper_stream,
                    "-m", self.whisper_model,
                    "--threads", "1",
                    "-l", "en",
                    "-c", "0",
                    "--step", str(self.whisper_step_ms),
                    "--length", str(int(self.max_speech_duration * 1000)),
                    "--keep", "150",
                    "--beam-size", "1",
                    "--audio-ctx", "512"
                ]

            try:
                self.whisper_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                if self.verbose:
                    mode = "Hailo" if self.use_hailo else "CPU"
                    self.get_logger().info(f"    ▶️  Whisper ({mode}) restarted successfully")
            except Exception as e:
                self.get_logger().warn(f"⚠️ Error restarting Whisper: {e}")
                self.whisper_proc = None

    def run_whisper_streaming(self):
        """Run Whisper in streaming mode with silence detection

        NOTE: Audio routing is configured via ~/.asoundrc:
        - ReSpeaker 6-channel input -> Channels 1+4 extracted as stereo
        - This provides optimal quality (tested and verified)
        - SDL uses default ALSA device which maps to our stereo virtual device
        """
        if self.use_hailo:
            self.get_logger().info("🎤 Starting Hailo-accelerated Whisper streaming...")
        else:
            self.get_logger().info("🎤 Starting Whisper streaming...")

        # Build command based on backend
        if self.use_hailo:
            # Hailo backend - using launcher script
            cmd = [
                self.whisper_stream,
                "--step", str(self.whisper_step_ms),
                "--silence-threshold", str(self.silence_threshold),
                "--max-speech-duration", str(self.max_speech_duration),
                "--variant", "base",  # Using base variant for quality
            ]
        else:
            # Whisper stream command balanced for speed and CPU (target 40-50% CPU)
            # Uses default audio device (configured in ~/.asoundrc to be Ch1+4 stereo)
            cmd = [
                self.whisper_stream,
                "-m", self.whisper_model,
                "--threads", "1",        # Balanced thread count
                "-l", "en",              # English language
                "-c", "0",               # Device 0 (uses ALSA default = respeaker_stereo)
                "--step", str(self.whisper_step_ms),  # Process every 1 second
                "--length", str(int(self.max_speech_duration * 1000)),  # Match max_speech_duration (5500ms)
                "--keep", "150",          # Moderate audio overlap
                "--beam-size", "1",       # Greedy decoding for speed
                "--audio-ctx", "512"      # Smaller audio context for speed
            ]

        try:
            self.whisper_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            self.get_logger().info("✅ Whisper streaming started!")
            self.get_logger().info("\n🎙️ LISTENING... Speak into the microphone!\n")
            self.get_logger().info("  💡 Tip: Pause for 1 second after speaking for response\n")
            self.get_logger().info("(Press Ctrl+C to stop)\n")
            self.get_logger().info("-"*50 + "\n")

            # Process Whisper output
            event_count = 0  # Track events for verbose logging

            # Keep reading from whisper output until stopped
            while self.running:
                try:
                    # CRITICAL: Spin ROS executor to process callbacks (like sleep_mode_callback)
                    # Without this, subscriptions never receive messages!
                    rclpy.spin_once(self, timeout_sec=0.0)

                    # Skip buffering during TTS (but keep reading to drain the pipe)
                    # Check for silence timeout BEFORE reading new line
                    # This ensures we process buffered speech even if no new audio comes in
                    if self.audio_buffer and self.last_speech_time and not self.is_speaking:
                        current_time = time.time()
                        silence_duration = current_time - self.last_speech_time

                        should_process = False
                        process_reason = ""

                        # Primary trigger: Silence threshold (simple and fast)
                        if silence_duration >= self.silence_threshold:
                            should_process = True
                            process_reason = f"silence ({silence_duration:.1f}s)"
                        # Secondary trigger: Max speech duration
                        elif self.accumulated_speech_time >= self.max_speech_duration:
                            should_process = True
                            process_reason = f"max speech ({self.accumulated_speech_time:.1f}s)"
                        # Optional early trigger: Text similarity (for very stable transcriptions)
                        elif len(self.audio_buffer) >= 3 and silence_duration >= 0.3:
                            # Only use similarity if we have at least 0.3s silence AND multiple buffers
                            last_text = self.audio_buffer[-1]
                            prev_text = self.audio_buffer[-2]
                            similarity = text_similarity(last_text, prev_text)

                            if similarity >= 0.95:  # Very high similarity (basically identical)
                                should_process = True
                                process_reason = f"transcription settled ({similarity*100:.0f}% similar, {silence_duration:.1f}s silence)"
                                if self.verbose:
                                    self.get_logger().info(f"  🎯 Early trigger: '{prev_text}' → '{last_text}' ({similarity*100:.0f}%)")

                        if should_process:
                            # Take ONLY the last buffered phrase (the most recent/final one)
                            combined_text = self.audio_buffer[-1].strip() if self.audio_buffer else ""

                            # CRITICAL: Check if combined text has actual alphanumeric content
                            combined_cleaned = ''.join(c for c in combined_text if c.isalnum() or c.isspace()).strip()

                            # Only process if we have real content
                            if combined_cleaned and len(combined_cleaned) > 2:
                                pipeline_start = time.time()
                                processing_timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

                                self.get_logger().info(f"\n  ⏸️  [{processing_timestamp}] Processing ({process_reason}): '{combined_text}'")

                                # ===== UNIFIED COMMAND DETECTION =====
                                # Detect ANY command (voice assistant OR robot hardware) from user speech
                                command_type, command_data, canned_response = self.detect_command(combined_text)

                                if command_type:
                                    # Command detected - use canned response, skip LLM
                                    response = canned_response
                                    llm_time = 0
                                    actual_stt_time = 0.8

                                    # Execute hardware commands (publishes to ROS topics)
                                    if command_type == 'robot_hardware':
                                        hw_command = command_data.get('command', 'unknown')
                                        self.execute_hardware_command(hw_command)
                                        self.get_logger().info(f"  🤖 Executing hardware command: {hw_command}")

                                    # Log output
                                    self.get_logger().info(f"\n{'='*50}")
                                    self.get_logger().info(f"👤 USER: {combined_text}")
                                    self.get_logger().info(f"🤖 LUXOPI: {response}")

                                    # Show command type details
                                    if command_type == 'voice_assistant':
                                        action = command_data.get('action', 'unknown')
                                        if action == 'mute':
                                            self.get_logger().info(f"🔇 Voice assistant muted")
                                        elif action == 'unmute':
                                            self.get_logger().info(f"🔊 Voice assistant unmuted")
                                        elif action in ['volume_up', 'volume_down']:
                                            self.get_logger().info(f"🔊 Volume: {self.amplitude}/200")
                                        elif action in ['speed_up', 'speed_down']:
                                            self.get_logger().info(f"⚡ Speed: {self.speed} wpm")
                                        elif action in ['pitch_up', 'pitch_down']:
                                            self.get_logger().info(f"🎵 Pitch: {self.pitch}")
                                        elif action == 'status':
                                            self.get_logger().info(f"📊 Status reported")
                                    elif command_type == 'robot_hardware':
                                        hw_command = command_data.get('command', 'unknown')
                                        self.get_logger().info(f"🤖 Hardware command: {hw_command}")
                                    elif command_type == 'quick_response':
                                        self.get_logger().info(f"⚡ Quick response (no LLM)")

                                    self.get_logger().info(f"{'='*50}\n")

                                    # Speak response if not muted
                                    if self.should_speak():
                                        self.speak(response)

                                    # Clear buffer and continue
                                    self.audio_buffer = []
                                    self.last_speech_time = None
                                    self.first_speech_time = None
                                    self.first_stt_timestamp = None
                                    self.accumulated_speech_time = 0.0
                                    self.last_word_count = 0
                                    self.word_count_stable_iterations = 0
                                    continue

                                # If muted and no command detected, show transcription but don't respond
                                if not self.should_speak():
                                    self.get_logger().info(f"\n{'='*50}")
                                    self.get_logger().info(f"👤 USER: {combined_text}")
                                    self.get_logger().info(f"🔇 (Muted - not responding)")
                                    self.get_logger().info(f"{'='*50}\n")

                                    # Clear buffer and continue
                                    self.audio_buffer = []
                                    self.last_speech_time = None
                                    self.first_speech_time = None
                                    self.first_stt_timestamp = None
                                    self.accumulated_speech_time = 0.0
                                    self.last_word_count = 0
                                    self.word_count_stable_iterations = 0
                                    continue

                                # Use tracked STT time (from marker or default fallback)
                                actual_stt_time = self.last_stt_time

                                # Start filler TTS to fill the gap during LLM processing
                                self.start_filler_tts()

                                # Process synchronously (no queue) to prevent double processing
                                llm_start = time.time()
                                response, llm_time = self.query_llm(combined_text)
                                llm_actual = time.time() - llm_start
                                timestamp_llm = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                                self.get_logger().info(f"  🧠 [{timestamp_llm}] LLM responded in {llm_actual:.3f}s")

                                response_time = actual_stt_time + llm_time

                                # Update metrics
                                self.metrics['queries'] += 1
                                self.metrics['total_stt_time'] += actual_stt_time
                                self.metrics['total_llm_time'] += llm_time
                                self.metrics['fastest_response'] = min(self.metrics['fastest_response'], response_time)
                                self.metrics['slowest_response'] = max(self.metrics['slowest_response'], response_time)
                                self.metrics['fastest_llm'] = min(self.metrics['fastest_llm'], llm_actual)
                                self.metrics['slowest_llm'] = max(self.metrics['slowest_llm'], llm_actual)
                                self.metrics['llm_response_times'].append(llm_actual)

                                # Stop filler TTS now that we're ready to speak the real response
                                self.stop_filler_tts()

                                # Speak the response and track timing
                                tts_start = time.time()
                                timestamp_tts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                                self.get_logger().info(f"  🔊 [{timestamp_tts}] Starting TTS...")
                                tts_time = self.speak(response)  # Returns audio generation + transformation + playback time
                                tts_actual = time.time() - tts_start  # Includes pause/resume overhead
                                timestamp_done = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                                self.get_logger().info(f"  ✅ [{timestamp_done}] TTS pipeline completed in {tts_actual:.3f}s (includes pause/resume)")

                                self.metrics['total_tts_time'] += tts_time

                                pipeline_total = time.time() - pipeline_start

                                # Display response with timing - ALWAYS show USER input
                                self.get_logger().info(f"\n{'='*50}")
                                self.get_logger().info(f"👤 USER: {combined_text}")
                                self.get_logger().info(f"🤖 LUXOPI: {response}")
                                self.get_logger().info(f"⚡ Response: {response_time:.2f}s (STT: ~{actual_stt_time:.1f}s + LLM: {llm_time:.2f}s)")
                                self.get_logger().info(f"🔊 TTS Audio: {tts_time:.2f}s (espeak + sox + playback)")
                                self.get_logger().info(f"⏱️  Total Pipeline: {pipeline_total:.2f}s (includes TTS pause/resume: +{tts_actual - tts_time:.2f}s)")

                                # Goal comparison
                                if response_time < self.goal_time:
                                    self.get_logger().info(f"🎉 < {self.goal_time}s goal!")
                                else:
                                    self.get_logger().warn(f"⚠️ +{response_time - self.goal_time:.2f}s over goal")
                                self.get_logger().info("="*50 + "\n")

                            # Clear buffer regardless
                            self.audio_buffer = []
                            self.last_speech_time = None
                            self.first_speech_time = None
                            self.first_stt_timestamp = None
                            self.accumulated_speech_time = 0.0
                            self.last_word_count = 0  # Reset word count tracker
                            self.word_count_stable_iterations = 0  # Reset stability counter

                    event_start = time.time()  # Start timing this event

                    # Check if Whisper process still exists
                    if not self.whisper_proc:
                        # Process was paused (for TTS), wait for it to resume
                        time.sleep(0.1)
                        continue

                    # Check if process has terminated
                    if self.whisper_proc.poll() is not None:
                        # Process has ended
                        if self.is_speaking:
                            # Expected - we're pausing for TTS, will auto-resume when TTS finishes
                            self.whisper_proc = None
                            time.sleep(0.1)
                            continue
                        else:
                            # Unexpected termination - this shouldn't happen
                            if self.verbose:
                                self.get_logger().info("⚠️ Whisper process ended unexpectedly (should auto-restart after TTS)")
                            self.whisper_proc = None
                            time.sleep(0.1)
                            continue

                    line = self.whisper_proc.stdout.readline()
                    if not line:  # Empty line but process still running
                        continue

                    line_stripped = line.strip()

                    # Check for STT processing marker from hailo-whisper (for accurate timing)
                    if line_stripped == "<<<PROCESSING_START>>>":
                        self.stt_start_time = time.time()  # Capture STT start time
                        if self.verbose:
                            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            self.get_logger().info(f"  🚀 [{timestamp}] STT processing started (marker detected)")
                        continue

                    # Skip completely empty lines without incrementing counter
                    if not line_stripped:
                        continue

                    # Skip lines that are just whitespace or single quotes
                    if len(line_stripped) <= 1:
                        continue

                    # Skip timestamps and special tokens (except [BLANK_AUDIO] which we want to filter)
                    if line_stripped.startswith('[') and line_stripped != '[BLANK_AUDIO]':
                        continue
                    if line_stripped.startswith('<'):
                        continue

                    # Skip lines that look like incomplete output (just quotes or punctuation)
                    if all(c in " '\"\t\n\r" for c in line_stripped):
                        continue

                    # Now we have actual content to process
                    text = line_stripped

                    # Remove ANSI escape codes (like [2K which is "clear line")
                    text = re.sub(r'\[\d+[A-Za-z]', '', text).strip()

                    # Only count this as an event since we're actually processing it
                    if text:  # Double-check we have content
                        # Normalize text for comparison
                        text_lower = text.lower().strip()

                        # Check for blank audio or meaningless content
                        # Exact match patterns (must match entire text)
                        exact_noise_patterns = [
                            "[blank_audio]",
                            "blank audio",
                            "[silence]",
                            "[noise]",
                            "[music]",
                            "...",
                            ".",
                            "'",
                            "''",
                            "'''",
                            "(silence)",
                            "concluded.",
                            "concluded",
                            "(clinking)",
                            "(inaudible)",
                            "(background noise)",
                            "thanks for watching.",
                            "thanks for watching",
                            "you",
                            "yeah.",
                            "yeah",
                            "mm-hmm.",
                            "mm-hmm",
                            "uh-huh.",
                            "uh-huh",
                            "hmm.",
                            "hmm",
                            "ok",
                            "okay",
                            "um",
                            "uh",
                            "ah",
                        ]

                        # Substring patterns (can appear anywhere)
                        substring_patterns = [
                            "[blank_audio]",
                            "[silence]",
                            "[noise]",
                            "[music]",
                            "(silence)",
                            "(inaudible)",
                        ]

                        # Check for exact match
                        is_exact_noise = text_lower in exact_noise_patterns

                        # Check for substring patterns
                        is_substring_noise = any(pattern in text_lower for pattern in substring_patterns)

                        is_noise = is_exact_noise or is_substring_noise

                        # Skip if text is just whitespace, punctuation, or quotes
                        text_cleaned = ''.join(c for c in text if c.isalnum() or c.isspace()).strip()

                        # Check if entire text is wrapped in parentheses (background noise/whispers)
                        # Examples: "(I'm going to go out).", "(something something)"
                        text_stripped = text.strip()
                        is_parenthetical = (text_stripped.startswith('(') and
                                          ')' in text_stripped and
                                          text_stripped.index(')') > text_stripped.index('('))

                        # Filter conditions:
                        # 1. Not a noise pattern
                        # 2. Not wrapped in parentheses (background noise indicator)
                        # 3. Has actual alphanumeric content
                        # 4. More than 4 meaningful characters (stricter filter)
                        # 5. Not just repeated characters (like "mmmm" or "aaaa")
                        # 6. Has at least 2 words or one word with 5+ characters
                        if (not is_noise and
                            not is_parenthetical and
                            text_cleaned and
                            len(text_cleaned) > 4 and
                            not all(c == text_cleaned[0] for c in text_cleaned if c.isalpha())):

                            # Additional check: ensure it has at least one word with 3+ characters
                            words = text_cleaned.split()
                            has_meaningful_word = any(len(word) >= 3 for word in words)

                            if has_meaningful_word:
                                event_count += 1
                                # Reset counter to prevent overflow
                                if event_count > 10000:
                                    event_count = 1

                                stt_process_time = time.time() - event_start

                                # Only buffer speech if we're not currently speaking (ignore robot's own voice)
                                if not self.is_speaking:
                                    # Whisper outputs progressive refinements on separate lines within the text
                                    # Example: "line1\n'line2\n'line3" - we only want the LAST line (final refinement)
                                    # Split by newlines and take ONLY the last line
                                    lines = text.split('\n')
                                    final_text = lines[-1].strip()

                                    # Remove leading quote if present (artifact from Whisper output)
                                    if final_text.startswith("'"):
                                        final_text = final_text[1:].strip()

                                    # Only add if it's not empty after cleaning
                                    if final_text:
                                        # Check if this is identical to the last buffered phrase (avoid duplicates)
                                        is_duplicate = (self.audio_buffer and
                                                       self.audio_buffer[-1].lower().strip() == final_text.lower().strip())

                                        if not is_duplicate:
                                            # Append this final refined phrase to buffer
                                            self.audio_buffer.append(final_text)

                                            # Calculate actual STT time from marker (if available)
                                            if self.stt_start_time is not None:
                                                self.last_stt_time = time.time() - self.stt_start_time
                                                self.stt_start_time = None  # Reset for next run
                                                if self.verbose:
                                                    self.get_logger().info(f"  ⏱️  Calculated STT time: {self.last_stt_time:.3f}s (from marker)")

                                            # Accumulate time for this phrase
                                            self.accumulated_speech_time += self.whisper_step_ms / 1000.0

                                            # Print only the final line, not all the progressive updates
                                            stt_timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                                            self.get_logger().info(f"🎧 [{stt_timestamp}] {final_text}")

                                            # HAILO MODE: Process immediately when we receive a transcription
                                            # Hailo already does VAD/silence detection internally, so when it
                                            # outputs a transcription, it's final and ready to process
                                            if self.use_hailo:
                                                # Force immediate processing for Hailo mode
                                                self.last_speech_time = time.time() - self.silence_threshold - 1
                                                if self.verbose:
                                                    self.get_logger().info(f"  🚀 Hailo transcription received, triggering immediate processing")

                                    current_time = time.time()

                                    # For CPU mode, update last_speech_time normally
                                    # For Hailo mode, it's already been set above to trigger processing
                                    if not self.use_hailo:
                                        self.last_speech_time = current_time

                                    # Track first speech time if this is the start of a new buffer
                                    if not self.first_speech_time:
                                        self.first_speech_time = current_time
                                        self.first_stt_timestamp = stt_timestamp

                                    self.metrics['total_detections'] += 1
                            else:
                                event_count += 1
                                if event_count > 10000:
                                    event_count = 1
                                filter_time = time.time() - event_start

                                if self.verbose:
                                    # Clean text to prevent newlines in output
                                    text_display = text.replace('\n', '\\n').replace('\r', '\\r')
                                    self.get_logger().info(f"  🔇 [{event_count}] Too short: '{text_display}'")
                                self.metrics['filtered_short'] += 1
                        else:
                            event_count += 1
                            if event_count > 10000:
                                event_count = 1
                            filter_time = time.time() - event_start

                            if is_noise:
                                if self.verbose:
                                    text_display = text.replace('\n', '\\n').replace('\r', '\\r')
                                    self.get_logger().info(f"  🔇 [{event_count}] Noise: '{text_display}'")
                                self.metrics['filtered_noise'] += 1
                            elif is_parenthetical:
                                if self.verbose:
                                    text_display = text.replace('\n', '\\n').replace('\r', '\\r')
                                    self.get_logger().info(f"  🔇 [{event_count}] Background/whisper (parenthetical): '{text_display}'")
                                self.metrics['filtered_noise'] += 1
                            else:
                                if self.verbose:
                                    text_display = text.replace('\n', '\\n').replace('\r', '\\r')
                                    self.get_logger().info(f"  🔇 [{event_count}] No content: '{text_display}'")
                                self.metrics['filtered_no_content'] += 1

                except Exception as e:
                    if self.running:
                        self.get_logger().warn(f"⚠️ Error reading whisper output: {e}")
                    break

        except Exception as e:
            self.get_logger().error(f"❌ Whisper error: {e}")

    def show_stats(self):
        """Display session statistics"""
        runtime = time.time() - self.metrics['start_time']

        self.get_logger().info("\n" + "="*60)
        self.get_logger().info("  📊 SESSION STATISTICS")
        self.get_logger().info("="*60)

        self.get_logger().info(f"  Runtime: {runtime:.1f} seconds")
        self.get_logger().info(f"  Queries processed: {self.metrics['queries']}")

        # Show filtering stats
        total_filtered = (self.metrics['filtered_noise'] +
                         self.metrics['filtered_short'] +
                         self.metrics['filtered_no_content'])
        self.get_logger().info(f"  Total detections: {self.metrics['total_detections']}")
        self.get_logger().info(f"  Filtered out: {total_filtered}")
        if total_filtered > 0:
            self.get_logger().info(f"    - Noise/silence: {self.metrics['filtered_noise']}")
            self.get_logger().info(f"    - Too short: {self.metrics['filtered_short']}")
            self.get_logger().info(f"    - No content: {self.metrics['filtered_no_content']}")

        if self.metrics['queries'] > 0:
            avg_stt = self.metrics['total_stt_time'] / self.metrics['queries']
            avg_llm = self.metrics['total_llm_time'] / self.metrics['queries']
            avg_tts = self.metrics['total_tts_time'] / self.metrics['queries']
            avg_response = avg_stt + avg_llm

            self.get_logger().info(f"\n  🎯 PERFORMANCE STATS:")
            self.get_logger().info(f"  Average STT: ~{avg_stt:.1f}s")
            self.get_logger().info(f"  Average LLM: {avg_llm:.3f}s")
            self.get_logger().info(f"  Average Response Time: {avg_response:.2f}s (STT + LLM)")
            self.get_logger().info(f"  Average TTS: {avg_tts:.2f}s")
            self.get_logger().info(f"  Fastest response: {self.metrics['fastest_response']:.2f}s")
            self.get_logger().info(f"  Slowest response: {self.metrics['slowest_response']:.2f}s")

            # LLM response time analysis
            self.get_logger().info(f"\n  🧠 LLM RESPONSE TIME ANALYSIS:")
            self.get_logger().info(f"  Fastest LLM: {self.metrics['fastest_llm']:.3f}s")
            self.get_logger().info(f"  Slowest LLM: {self.metrics['slowest_llm']:.3f}s")
            self.get_logger().info(f"  LLM Variance: {self.metrics['slowest_llm'] - self.metrics['fastest_llm']:.3f}s")
            if len(self.metrics['llm_response_times']) > 0:
                import statistics
                median_llm = statistics.median(self.metrics['llm_response_times'])
                stdev_llm = statistics.stdev(self.metrics['llm_response_times']) if len(self.metrics['llm_response_times']) > 1 else 0
                self.get_logger().info(f"  Median LLM: {median_llm:.3f}s")
                self.get_logger().info(f"  Std Dev: {stdev_llm:.3f}s")

            # Goal achievement stats
            if avg_response < self.goal_time:
                self.get_logger().info(f"\n  🏆 GOAL STATUS: ACHIEVED!")
                self.get_logger().info(f"  Average {avg_response:.2f}s < {self.goal_time}s target ✅")
            else:
                self.get_logger().info(f"\n  ⚠️ GOAL STATUS: {avg_response - self.goal_time:.2f}s over target")

        # System resources
        cpu = psutil.cpu_percent()
        mem = psutil.Process().memory_info().rss / 1024 / 1024
        self.get_logger().info(f"  CPU usage: {cpu:.1f}%")
        self.get_logger().info(f"  Memory usage: {mem:.0f}MB")

        self.get_logger().info("="*60)

    def start(self):
        """Start the voice assistant"""
        self.print_banner()

        # Set speaker volume - higher for transformed voices, lower for normal
        if self.voice_transformer:
            self.get_logger().info("🔊 Setting speaker volume to 100% for transformed voice...")
            self.set_speaker_volume(1.0)
        else:
            self.get_logger().info("🔊 Setting speaker volume to 30% for longevity...")
            self.set_speaker_volume(0.3)

        # Check if models exist
        if not os.path.exists(self.whisper_model):
            self.get_logger().error(f"❌ Whisper model not found: {self.whisper_model}")
            return

        if not os.path.exists(self.llm_model):
            self.get_logger().error(f"❌ LLM model not found: {self.llm_model}")
            return

        # Start LLM server
        if not self.start_llm_server():
            return

        # Start Whisper streaming (blocks until interrupted, processes synchronously)
        try:
            self.run_whisper_streaming()
        except KeyboardInterrupt:
            self.get_logger().info("\n\n🛑 Shutting down...")
            self.stop()

    def stop(self):
        """Clean shutdown with memory cleanup"""
        self.running = False

        # Stop Whisper
        if self.whisper_proc:
            self.whisper_proc.terminate()
            self.whisper_proc.wait(timeout=2)
            self.whisper_proc = None

        # Stop LLM server
        if self.llm_server_proc:
            self.llm_server_proc.terminate()
            self.llm_server_proc.wait(timeout=2)
            self.llm_server_proc = None

        # Show statistics
        self.show_stats()

        # Force garbage collection to free memory
        gc.collect()

        # Clear memory caches
        try:
            # Drop caches if we have permission (usually needs sudo)
            subprocess.run(["sync"], timeout=1)
            # This would need sudo: subprocess.run(["sudo", "sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"])
        except:
            pass

        self.get_logger().info("\n✨ Goodbye! Memory cleaned up.\n")


def main(args=None):
    rclpy.init(args=args)
    node = LuxopiAssistantNode()

    try:
        node.start()
    except KeyboardInterrupt:
        node.get_logger().info("🛑 Shutting down...")
    finally:
        node.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
