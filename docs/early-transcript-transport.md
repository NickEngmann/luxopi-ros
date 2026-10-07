# Early recognized text without waiting for synthesis

The local transport consumes bounded, ID-correlated transcript progress and
publishes it through the speech bridge immediately. Older services that emit only
a final result retain final-transcript fallback. Callbacks suppress publication
during shutdown. A fixed transaction deadline is not extended by progress; more
than eight progress records, malformed protocol, timeout or process exit still
tears down the owned service. Explicit recoverable request errors preserve it.

22 transport/worker tests pass: progress and final result in one pipe write,
stale ID rejection, model PID retention after recoverable error, timeout and
excess-event restart, early/fallback transcript publication, shutdown suppression
and WAV speaking previews. Actual silent Moonshine/Piper validation is recorded
in `/tmp/luxopi-early-asr-client/report.json`; no ROS graph inputs were issued.
