# Silent response synthesis

The speech bridge can request Piper response WAV generation for ordinary text
and saved-audio commands. It never plays these files. Default behavior remains
unchanged: synthesis is disabled and the JSONL payload omits `synthesize`.

Enable `LUXOPI_SYNTHESIZE_SPEECH=true` in the combined profile's container
environment, or pass `speech_synthesize:=true` to the common/physics launch.
The bridge ROS parameter is `synthesize_speech`. Explicit launch/ROS parameters
override the environment default. The local service must already have its Piper
voice/output-directory configuration; this flag does not install a voice.

When the service returns `audio_path`, the bridge inspects the actual WAV header
and holds its silent speaking visualization for that duration, capped at 10s.
Missing/invalid WAV files use the configured preview fallback. Files remain owned
by the existing local service; this change does not alter copying, playback or
retention. The simulation text backend accepts the flag but returns no audio and
continues to identify itself as simulation.

Offline evidence: 20 transport/bridge/intent tests passed. They exercise a real
JSONL subprocess receiving both text/audio payloads, execute the actual bridge
worker with a generated WAV, and verify bounded WAV duration and disabled default.
They do not validate neural Piper synthesis or audio hardware; the actual-model
combined-profile HTTP check must separately verify returned WAV files.
