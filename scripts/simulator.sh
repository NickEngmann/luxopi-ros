#!/usr/bin/env bash
# Resolve the checkout independently of the caller's working directory.
set -euo pipefail
checkout_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec docker compose --project-directory "$checkout_dir" -f "$checkout_dir/compose.simulator.yml" "$@"
