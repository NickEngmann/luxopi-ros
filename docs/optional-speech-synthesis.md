# Silent response synthesis

The speech bridge can request Piper response WAV generation for ordinary text
and saved-audio commands. It never plays these files. Synthesis is disabled in
the base profile and its JSONL payload omits `synthesize`; the combined full
speech/physics profile enables synthesis for its silent speaking preview.

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

Actual combined-profile evidence on 2026-10-05: four supplied Piper fixtures
passed Moonshine recognition, command/LLM response, ROS consumers, and MuJoCo
motion/lighting. Each returned to IDLE. The normal bridge generated four new mono
16kHz Piper WAVs, with durations 1.360, 1.888, 2.352 and 6.128 seconds. No audio
was played. Host evidence: `/tmp/luxopi-latest-full-audio.json` and
`/tmp/luxopi-latest-piper-wavs.json`. Whole-case timings include silent speaking
and action completion: dance 76.240s, blue lamp 2.468s, brightness 3.515s,
general question 8.014s. These are functional synthetic fixtures on the
AGX host, not speech accuracy or Raspberry Pi latency measurements.
