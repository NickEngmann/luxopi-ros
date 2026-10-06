# Hardware-free validation artifacts

These are saved JSON reports from silent, isolated LuxoPI simulator checks.
They contain synthetic fixtures and simulator telemetry, not household audio or
backup archives. Keeping them here makes the evidence survive temporary-file
cleanup. Original logs and failed attempts remain local under `/tmp`.

Each native report includes its production source and runner hashes. The full
continuous report uses a verified passing motion/state prefix; its provenance
manifest links the frozen `123025b` source to the original run. The later core
reports test the `8e8ba06` lifecycle changes and do not repeat that full playlist.
The final UI reports additionally test persistent lighting drafts, actual
color-temperature acknowledgement, and explicit health reasons.

Browser reports record one optional in-browser heartbeat test as skipped; the
separate guarded pause and restart reports verify that fault path. Count that
entry as skipped, not as another executed behavior test. All other recorded
checks passed without page, console or failed HTTP-request errors.

Home and gesture reports observe actual joint feedback and completed action or
state transitions. Speech fixtures use real local models but do not measure
human recognition accuracy. None of these files establishes physical sensor
calibration, safe real-world stopping distance, or CM4/Hailo latency.
