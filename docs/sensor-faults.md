# Sensor fault and simulator coverage

`python3 -m pytest tests/test_collision_faults.py -q` executes actual collision
callbacks/evaluation/recovery methods with synthetic inputs and deterministic
clock/service faults. Coverage includes two distinct distance/proximity samples,
threshold severity boundaries, malformed/nonfinite/out-of-range readings, stale
caches, fresh recovery after a gap, absent I2C service, bounded reinitialization
requests, and force-sensor collision preservation while an unrelated range sensor
reads safe or expires. No Blinka, DepthAI, PyAudio, ROS transport or physical
sensors are imported by this offline suite.

Corrections preserve thresholds and published message contracts:

- Timer repeats no longer count as additional physical samples. Previous values
  advance only on valid sensor callbacks, and an expired sample cannot combine
  with the first recovered sample to trigger collision.
- Timeout clearing invalidates cached readings so subsequent evaluation cannot
  reassert a collision based on old data. Invalid distance readings do not refresh
  freshness. The existing timeout policy clears proximity/distance warning; this
  is not a claim that missing sensors establish a physically safe path.
- APDS9960 samples must be within 0–255; VL53L4CD samples must be finite and within
  1–400 cm. Invalid samples do not refresh health and break consecutive-reading
  evidence rather than being paired with an earlier obstacle sample.
- Side range readings between the hard-collision threshold (8 cm) and warning
  threshold (15 cm) publish `severity=warning` while the legacy collision Bool
  remains false. Motion consumers use the atomic severity record for a bounded
  retreat in that outer band. The front APDS count is a relative 0–255 value and
  does not represent a distance in centimeters.
- Required motion coverage is explicit. Hardware with collision sensing enabled
  requires fresh front/left/right classifier records by default; callers can
  configure a smaller/empty direction set for a different sensor profile. A
  sensorless simulator remains optional by default; a physics world-ray fixture
  requires all three range directions unless overridden. Coverage only proves
  that samples are arriving and valid, not that sensor mounts or retreat axes are
  physically calibrated.
- Service readiness probes are nonblocking. Reinitialization requests are capped
  at one per sensor per ten seconds while data remains unavailable.
- Active touch/force collisions remain asserted when another sensor reports safe
  or times out, rather than allowing the periodic distance evaluation to erase it.

Touch/force auto-clear duration and broader missing-sensor movement policy remain
unchanged. A hardware deployment should decide whether loss of coverage requires
motion inhibition; unit tests do not establish physical stopping distance.

## Simulator feature boundaries

The browser injects raw touch, APDS proximity/gestures, VL53 distances, vision
emotion/person-distance, and voice direction fixtures. Collision-node callback
coverage validates raw-sensor → collision classification rather than only injecting
already-classified collision messages. Dashboard's explicit collision buttons
bypass sensor classification and must not count as that evidence. Manual control,
light controls, emotion reactions, dance action execution, and direction-following
joint response require their respective scenario suites.

Simulator launch must exclude live `i2c_device_manager` (Blinka/Adafruit),
`camera_interaction` (DepthAI/blobconverter/OpenCV), and `voice_direction_node`
(PyAudio/WebRTC VAD/USB LEDs). Use the shared-estimator `sim_direction_node` for
silent direction fixtures. Collision classification itself requires only ROS
messages/services, and can run in the simulator unchanged. The live camera/I2C
modules retain their optional native dependencies; installing every vendor driver
is not a prerequisite to the simulation.

## Vision model validation

Current live DepthAI models are `face-detection-retail-0004` and
`emotions-recognition-retail-0003`, compiled for six SHAVEs. Existing camera queues
are bounded to retain fresh inference frames. Simulator emotion injections verify
behavior integration and cannot establish neural-network accuracy or device speed.
No replacement vision weights are selected without comparable target-device
latency/quality evidence.

An executable device-free asset check, in a vision environment with blobconverter
and DepthAI installed, is:

```python
import hashlib
import blobconverter
import depthai as dai
for name in ('face-detection-retail-0004', 'emotions-recognition-retail-0003'):
    path = blobconverter.from_zoo(name=name, shaves=6)
    blob = dai.OpenVINO.Blob(path)
    print(name, path, hashlib.sha256(open(path, 'rb').read()).hexdigest())
    print('inputs:', list(blob.networkInputs), 'outputs:', list(blob.networkOutputs))
```

This validates downloaded compiled assets and input/output metadata, not execution.
When a camera returns, run the current pipeline on a fixed recorded scene set,
log detection/emotion results and capture-to-publish latency distribution, then
compare a candidate using the same frames, SHAVE allocation, device and queue
settings. Keep the baseline if end-to-end p95 latency increases or behavior quality
falls. Depth/stereo/person distance also needs physical calibration; frame injection
alone does not validate it.
