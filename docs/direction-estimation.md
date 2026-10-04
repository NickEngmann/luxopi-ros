# Direction finding: audio-to-angle simulation

The live `MicArray.get_direction` and silent simulator use the same pure
`direction_estimation.estimate_direction` function. It extracts raw microphones
1..4 from six-channel interleaved ReSpeaker PCM, estimates opposite-pair delays
with GCC-PHAT, and preserves the existing sign/calibration/user offset. Four-channel
input remains supported. PyAudio loads only when opening a real `MicArray`.

The 81.27 mm array at 16 kHz has only 3.79 samples of maximum opposite-pair delay.
The previous integer-delay estimator was coarse. The shared estimator uses 16x
correlation interpolation; this refines numerical delay resolution rather than
inventing new microphone bandwidth. On 36 ideal delayed voiced-plus-broadband
fixtures at 10-degree intervals, mean angular error fell from 4.444 to 0.245 degrees,
maximum from 8.138 to 0.455. Median estimator time was 6.452 ms on the AGX Thor CPU
for a 400 ms six-channel window; Raspberry Pi latency is not established.

Run `python3 -m pytest tests/test_direction_estimation.py -q`: 71 cases cover
four/six channels, known directions including 0/359 wraparound, independent noise,
reference-channel isolation, interpolation comparison, circular smoothing,
parallax geometry, input validation and activity timeout. Fixtures are synthetic
plane waves with fractional delays, not room recordings, reverberation, actual
microphone wiring verification or measured acoustic accuracy. Direction deadzone,
mechanical limits and movement are validated separately by motion scenarios.

After sourcing the built workspace:

```
ROS_DOMAIN_ID=73 ROS_LOCALHOST_ONLY=1 python3 -m luxo_behaviors.sim_direction_node
```

Publish `std_msgs/Float32` desired microphone angle to `/sim/audio_direction`.
The node generates six-channel PCM in memory, runs the shared estimator, applies
live robot geometry, then publishes real motion inputs `/voice/direction` and
`/voice/follow_direction` (both robot-frame negative degrees, as in live code),
plus `/voice/active=true`. After 1.5 seconds without another direction event,
`/voice/active=false` is published. `/sim/direction_evidence` String JSON reports
requested angle, measured angle, robot target and fixture settings. No microphone
or speaker is opened. This simulator checks estimator plumbing; VAD is not run on
these synthetic direction-control events. Live WebRTC VAD remains unchanged.

The live direction node now emits an inactive event after the same quiet timeout;
previously it only emitted `true`, leaving listeners without an end-of-speech edge.
Circular statistics are shared with tests and clamp floating-point strength before
logarithms to avoid invalid standard deviations. LED presence is checked before
updates so missing LED hardware does not stop direction processing.
