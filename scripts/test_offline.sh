#!/usr/bin/env bash
set -euo pipefail
robot_checkout="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$robot_checkout"
export PYTHONPATH="$robot_checkout/src/luxo_behaviors${PYTHONPATH:+:$PYTHONPATH}"
"${PYTHON:-python3}" -m pytest -q \
  tests src/luxo_behaviors/tests src/luxo_behaviors/test/test_camera_buffering.py "$@"
